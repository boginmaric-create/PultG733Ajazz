"""Мышь AJAZZ AJ159 APEX (VID 0x3151) через док-станцию 2.4G 8K (PID 0x5007).

Что известно и откуда:
* Батарея: опрос 0xF7 на управляющей коллекции 0xFFFF/0x02 и чтение
  feature-отчёта — проверено на AJ159 APEX (0x3151:0x5007) в проекте
  AJAZZ Control Center.
* Часы на экране док-станции: команда 0x28 — проверено там же.
* Настройки (DPI, частота опроса, высота отрыва, кнопки и т. д.) —
  протокол платформы «GearHub-V5» этого же производителя чипов, проверен
  на AJAZZ AJ179 PRO и соседних мышах в проекте OpenMouse. Для AJ159 APEX
  программа сначала только ЧИТАЕТ настройки и разрешает запись, лишь если
  мышь прислала правильный ответ.

Формат команды: 64-байтный feature-отчёт без номера (report id 0),
байт 7 = 255 - (сумма байтов 0..6) & 0xFF. Через радиоканал команда
передаётся «эстафетой»: F6 05 (выбрать мышь) → F7 (ждать готовности) →
команда → F7 → FC (забрать ответ) → чтение.
"""
from __future__ import annotations

import datetime as _dt
import logging
import time

from .hidio import HidHandle, enumerate_devices, hx

log = logging.getLogger("ajazz")

VID = 0x3151
CTRL_USAGE_PAGE = 0xFFFF
CTRL_USAGE = 0x02
REPORT_SIZE = 64

PRODUCTS = {
    0x5007: ("dongle", "AJAZZ AJ159 APEX (док-станция 2.4G 8K)"),
    0x4027: ("dongle", "AJAZZ (приёмник 2.4G)"),
    0x402D: ("dongle", "AJAZZ / GearHub (приёмник 2.4G)"),
    0x5008: ("direct", "AJAZZ AJ159 APEX (кабель)"),
    0x4026: ("direct", "AJAZZ / GearHub (кабель)"),
}

CMD_GET_FIRMWARE = 0x80
CMD_GET_DEVICE_ID = 0x8F
CMD_GET_OPT0 = 0xD3
CMD_SET_OPT0 = 0x53
CMD_GET_DPI = 0xD4
CMD_SET_DPI = 0x54
CMD_GET_KEYS = 0xD0
CMD_SET_KEY = 0x50
CMD_SET_CLOCK = 0x28

DONGLE_SELECT = 0xF6
DONGLE_STATUS = 0xF7
DONGLE_NOTICE_READ = 0xFC
TARGET_MOUSE = 0x05

# Байты блока OPTIONPARAM0
OPT0_RATE = 9
OPT0_DEBOUNCE = 10
OPT0_FLAGS = 12
FLAG_RIPPLE = 1 << 2
OPT0_SLEEP_BT = 40
OPT0_SLEEP_24G = 44
OPT0_LIFT = 52
OPT0_ANGLE = 53

DPI_X = 8
DPI_Y = 24
DPI_RGB = 40
MAX_STAGES = 8

RATE_ENCODE = {125: 8, 250: 4, 500: 2, 1000: 1, 2000: 132, 4000: 130, 8000: 129}
RATE_DECODE = {v: k for k, v in RATE_ENCODE.items()}

LIFT_LEVELS = ["Низкая (0,7 мм)", "Средняя (1 мм)", "Высокая (2 мм)"]   # PAW3950
SLEEP_OPTIONS = [(0, "Никогда"), (15, "15 секунд"), (30, "30 секунд"), (60, "1 минута"),
                 (120, "2 минуты"), (300, "5 минут"), (600, "10 минут")]

BUTTONS = [("Левая кнопка", 0), ("Правая кнопка", 1), ("Средняя кнопка (колесо)", 2),
           ("Боковая «Назад»", 3), ("Боковая «Вперёд»", 4), ("Кнопка DPI", 5)]

BUTTON_ACTIONS = [
    ("Левый клик", (1, 0, 0xF0, 0)),
    ("Правый клик", (1, 0, 0xF1, 0)),
    ("Средний клик", (1, 0, 0xF2, 0)),
    ("Назад", (1, 0, 0xF3, 0)),
    ("Вперёд", (1, 0, 0xF4, 0)),
    ("Переключение DPI по кругу", (20, 0, 0, 0)),
    ("DPI +", (20, 0, 1, 0)),
    ("DPI −", (0, 2, 0, 20)),
    ("Отключена", (0, 0, 0, 0)),
]

DPI_MIN, DPI_MAX, DPI_STEP = 50, 30000, 50


class MouseError(Exception):
    pass


class MouseAsleep(MouseError):
    pass


def encode(cmd) -> bytes:
    out = bytearray(max(9, len(cmd)))
    out[:len(cmd)] = bytes(cmd)
    out[7] = (255 - (sum(out[0:7]) & 0xFF)) & 0xFF
    return bytes(out)


def decode_action(b) -> str:
    t = tuple(b[:4])
    for name, val in BUTTON_ACTIONS:
        if val == t:
            return name
    return "Своё назначение (" + " ".join(f"{x:02x}" for x in t) + ")"


class AjazzMouse:
    def __init__(self) -> None:
        self.h: HidHandle | None = None
        self.pid: int | None = None
        self.transport = "dongle"
        self.name = "AJAZZ"
        self.selected = False
        self.settings_ok = False
        self.profile = 0

    # ------------------------------------------------------------------
    @staticmethod
    def find() -> dict | None:
        cands = [d for d in enumerate_devices(VID)
                 if d.get("usage_page") == CTRL_USAGE_PAGE and d.get("usage") == CTRL_USAGE]
        cands.sort(key=lambda d: (d.get("product_id") not in PRODUCTS, d.get("product_id") != 0x5007))
        if cands:
            return cands[0]
        # Linux: usage_page не сообщается — берём интерфейс 2
        for d in enumerate_devices(VID):
            if d.get("interface_number") == 2:
                return d
        return None

    def is_open(self) -> bool:
        return self.h is not None

    def open(self) -> bool:
        info = self.find()
        if not info:
            return False
        self.h = HidHandle(info, "AJAZZ")
        self.pid = info.get("product_id")
        self.transport, self.name = PRODUCTS.get(self.pid, ("dongle", f"AJAZZ (PID {self.pid:04X})"))
        self.selected = False
        self.settings_ok = False
        return True

    def close(self) -> None:
        if self.h:
            self.h.close()
        self.h = None
        self.selected = False
        self.settings_ok = False

    # --- сырой обмен -----------------------------------------------------
    def _send(self, payload) -> None:
        buf = bytearray(REPORT_SIZE + 1)
        p = bytes(payload)[:REPORT_SIZE]
        buf[1:1 + len(p)] = p
        self.h.send_feature(buf)

    def _read(self, report_id: int = 0) -> bytes:
        r = self.h.get_feature(report_id, REPORT_SIZE + 1)
        data = r[1:] if len(r) == REPORT_SIZE + 1 else r
        return bytes(data) + bytes(max(0, REPORT_SIZE - len(data)))

    # --- статус док-станции и батарея -----------------------------------
    def dongle_status(self) -> bytes:
        self._send([DONGLE_STATUS])
        time.sleep(0.03)
        d = self._read(0)
        if not any(d[:8]):
            d5 = self._read(0x05)
            if any(d5[:8]):
                d = d5
        return d

    def battery(self) -> int | None:
        for _ in range(3):
            d = self.dongle_status()
            if d[0] > 1 or d[1] > 100:      # мусор после переподключения
                time.sleep(0.05)
                continue
            if 1 <= d[2] <= 100:
                return d[2]
            time.sleep(0.05)
        return None

    def _wait(self, what: str) -> bool:
        for _ in range(10):
            time.sleep(0.08)
            d = self.dongle_status()
            if what == "send" and d[5] == 1:
                return True
            if what == "read" and d[0] == 1:
                return True
        return False

    # --- команды мыши ----------------------------------------------------
    def command(self, cmd, echoes: bool = True) -> bytes:
        enc = encode(cmd)
        if self.transport == "direct":
            self._send(enc)
            time.sleep(0.015)
            return self._verify(self._read(), cmd[0], echoes)
        if not self.selected:
            self._send([DONGLE_SELECT, TARGET_MOUSE])
            time.sleep(0.05)
            self.selected = True
        if not self._wait("send"):
            raise MouseAsleep("Док-станция не готова к отправке — пошевелите мышь")
        self._send(enc)
        if not self._wait("read"):
            raise MouseAsleep("Мышь не ответила — пошевелите её и повторите")
        self._send([DONGLE_NOTICE_READ])
        time.sleep(0.015)
        return self._verify(self._read(), cmd[0], echoes)

    def write(self, cmd) -> None:
        if not self.settings_ok:
            raise MouseError("Запись заблокирована: настройки мыши не удалось прочитать")
        enc = encode(cmd)
        if self.transport == "direct":
            self._send(enc)
            time.sleep(0.02)
            return
        if not self.selected:
            self._send([DONGLE_SELECT, TARGET_MOUSE])
            time.sleep(0.05)
            self.selected = True
        if not self._wait("send"):
            raise MouseAsleep("Док-станция не готова к отправке — пошевелите мышь")
        self._send(enc)
        time.sleep(0.06)

    @staticmethod
    def _verify(resp: bytes, cmd: int, echoes: bool) -> bytes:
        if not any(resp):
            raise MouseError(f"Команда 0x{cmd:02x}: нет ответа (одни нули)")
        if echoes and resp[0] != cmd:
            raise MouseError(f"Команда 0x{cmd:02x}: в ответе 0x{resp[0]:02x} — {hx(resp[:12])}")
        return resp

    # --- чтение настроек -------------------------------------------------
    def firmware(self) -> str:
        r = self.command([CMD_GET_FIRMWARE])
        return f"v{r[2]}.{r[1]:02d}"

    def device_id(self) -> int:
        r = self.command([CMD_GET_DEVICE_ID])
        return int.from_bytes(r[1:5], "little")

    def read_opt0(self) -> bytes:
        return self.command([CMD_GET_OPT0])

    def read_dpi(self) -> dict:
        r = self.command([CMD_GET_DPI, self.profile])
        count = min(r[3], MAX_STAGES)
        if count == 0:
            raise MouseError("Мышь сообщила 0 ступеней DPI")
        stages = []
        for i in range(count):
            stages.append({
                "x": r[DPI_X + 2 * i] | (r[DPI_X + 1 + 2 * i] << 8),
                "y": r[DPI_Y + 2 * i] | (r[DPI_Y + 1 + 2 * i] << 8),
                "rgb": (r[DPI_RGB + 3 * i], r[DPI_RGB + 1 + 3 * i], r[DPI_RGB + 2 + 3 * i]),
            })
        for s in stages:
            if s["x"] and not (DPI_MIN <= s["x"] <= 42000):
                raise MouseError(f"Неправдоподобное значение DPI {s['x']}: {hx(r[:48])}")
        active = r[2] if r[2] < count else 0
        return {"stages": stages, "active": active}

    def read_keys(self) -> bytes:
        for attempt in range(2):
            r = self.command([CMD_GET_KEYS, self.profile], echoes=False)
            if r[0] < 0x80:
                return r
        raise MouseError("Мышь вернула устаревший ответ вместо таблицы кнопок")

    def read_all(self) -> dict:
        """Безопасное чтение всего — разрешает запись только при успехе."""
        out: dict = {"name": self.name, "pid": self.pid, "transport": self.transport}
        try:
            out["device_id"] = self.device_id()
        except MouseError as exc:
            log.info("ID устройства не прочитан: %s", exc)
        try:
            out["firmware"] = self.firmware()
        except MouseError as exc:
            log.info("версия прошивки не прочитана: %s", exc)
        dpi = self.read_dpi()                     # без этого настройки не открываем
        out["dpi"] = dpi
        opt0 = self.read_opt0()
        out["rate"] = RATE_DECODE.get(opt0[OPT0_RATE])
        out["debounce"] = opt0[OPT0_DEBOUNCE]
        out["ripple"] = bool(opt0[OPT0_FLAGS] & FLAG_RIPPLE)
        out["angle"] = bool(opt0[OPT0_ANGLE])
        out["lift"] = opt0[OPT0_LIFT]
        out["sleep"] = opt0[OPT0_SLEEP_24G] | (opt0[OPT0_SLEEP_24G + 1] << 8)
        try:
            keys = self.read_keys()
            out["buttons"] = {slot: decode_action(keys[slot * 4:slot * 4 + 4]) for _, slot in BUTTONS}
        except MouseError as exc:
            log.info("таблица кнопок не прочитана: %s", exc)
        self.settings_ok = out["rate"] is not None
        out["settings_ok"] = self.settings_ok
        return out

    # --- запись настроек -------------------------------------------------
    def _patch_opt0(self, changes: dict) -> None:
        cur = self.read_opt0()
        block = bytearray(REPORT_SIZE)
        block[8:] = cur[8:REPORT_SIZE]
        block[0] = CMD_SET_OPT0
        block[17] = 255
        block[18] = 8
        for off, val in changes.items():
            block[off] = (val(cur[off]) if callable(val) else val) & 0xFF
        self.write(block)

    def set_perf(self, hz: int, debounce: int, lift: int, angle: bool, ripple: bool, sleep_s: int) -> None:
        """Всё из блока OPTIONPARAM0 — одной записью (иначе вторая запись откатит первую)."""
        s = max(0, min(0xFFFF, int(sleep_s)))
        self._patch_opt0({
            OPT0_RATE: RATE_ENCODE[hz],
            OPT0_DEBOUNCE: max(0, min(10, int(debounce))),
            OPT0_LIFT: max(0, min(2, int(lift))),
            OPT0_ANGLE: 1 if angle else 0,
            OPT0_FLAGS: (lambda c: c | FLAG_RIPPLE) if ripple else (lambda c: c & ~FLAG_RIPPLE),
            OPT0_SLEEP_24G: s & 0xFF, OPT0_SLEEP_24G + 1: s >> 8,
            OPT0_SLEEP_BT: s & 0xFF, OPT0_SLEEP_BT + 1: s >> 8,
        })

    def set_dpi(self, values: list[int], colors: list[tuple[int, int, int]], active: int) -> None:
        """Меняет значения показанных ступеней; остальные слоты сохраняются как были."""
        r = self.command([CMD_GET_DPI, self.profile])
        count = min(r[3], MAX_STAGES)
        cmd = bytearray(REPORT_SIZE)
        cmd[0] = CMD_SET_DPI
        cmd[1] = self.profile
        cmd[2] = max(0, min(active, count - 1))
        cmd[3] = count
        cmd[DPI_X:DPI_RGB + 3 * MAX_STAGES] = r[DPI_X:DPI_RGB + 3 * MAX_STAGES]
        for i, v in enumerate(values[:count]):
            v = max(DPI_MIN, min(DPI_MAX, int(round(v / DPI_STEP) * DPI_STEP)))
            cmd[DPI_X + 2 * i:DPI_X + 2 * i + 2] = v.to_bytes(2, "little")
            cmd[DPI_Y + 2 * i:DPI_Y + 2 * i + 2] = v.to_bytes(2, "little")
        for i, c in enumerate(colors[:count]):
            cmd[DPI_RGB + 3 * i:DPI_RGB + 3 * i + 3] = bytes(c)
        self.write(cmd)

    def set_button(self, slot: int, action_name: str) -> None:
        val = dict(BUTTON_ACTIONS)[action_name]
        cmd = bytearray(REPORT_SIZE)
        cmd[0] = CMD_SET_KEY
        cmd[1] = self.profile
        cmd[2] = slot
        cmd[8:12] = bytes(val)
        self.write(cmd)

    # --- часы на экране док-станции --------------------------------------
    def sync_clock(self) -> None:
        now = _dt.datetime.now()
        pkt = bytearray(encode([CMD_SET_CLOCK])[:8])   # байт 7 = 0xD7
        pkt += bytes([now.year >> 8, now.year & 0xFF, now.month, now.day,
                      now.hour, now.minute, now.second])
        self._send(pkt)

    # --- диагностика -----------------------------------------------------
    def probe_raw(self) -> list[str]:
        lines = []
        for rid in (0, 5):
            try:
                self._send([DONGLE_STATUS])
                time.sleep(0.03)
                lines.append(f"F7 -> отчёт {rid}: {hx(self._read(rid)[:16])}")
            except Exception as exc:
                lines.append(f"F7 -> отчёт {rid}: ошибка {exc}")
        for name, cmd, echo in (("0x8F ID", [CMD_GET_DEVICE_ID], True),
                                ("0x80 прошивка", [CMD_GET_FIRMWARE], True),
                                ("0xD4 DPI", [CMD_GET_DPI, 0], True),
                                ("0xD3 OPT0", [CMD_GET_OPT0], True),
                                ("0xD0 кнопки", [CMD_GET_KEYS, 0], False)):
            try:
                lines.append(f"{name}: {hx(self.command(cmd, echo))}")
            except Exception as exc:
                lines.append(f"{name}: ошибка {exc}")
        return lines
