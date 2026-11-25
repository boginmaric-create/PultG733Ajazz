"""Logitech G733 (приёмник LIGHTSPEED) по протоколу HID++ 2.0.

Номера «функций» (feature index) не зашиты жёстко: программа спрашивает
их у самих наушников через корневую функцию 0x0000. Если наушники
не ответили на этот вопрос, используются номера, известные для G733
из проекта HeadsetControl (батарея 0x08, самоконтроль 0x07, подсветка 0x04).
"""
from __future__ import annotations

import logging
import time

from .hidio import HidHandle, enumerate_devices, hx

log = logging.getLogger("g733")

LOGI_VID = 0x046D
G733_PIDS = (0x0AB5, 0x0AFE, 0x0B1F)
HIDPP_USAGE_PAGE = 0xFF43
HIDPP_USAGE = 0x0202

FEAT_ROOT = 0x0000
FEAT_SET = 0x0001
FEAT_FW = 0x0003
FEAT_ADC = 0x1F20        # напряжение батареи
FEAT_SIDETONE = 0x8300   # самоконтроль
FEAT_LED = 0x8070        # цветовые эффекты подсветки
FEAT_EQ = 0x8310         # встроенный эквалайзер

FEATURE_NAMES = {
    0x0000: "Root", 0x0001: "FeatureSet", 0x0002: "FeatureInfo",
    0x0003: "FirmwareInfo", 0x0005: "DeviceName", 0x0007: "DeviceFriendlyName",
    0x0020: "ConfigChange", 0x1000: "BatteryStatus", 0x1004: "UnifiedBattery",
    0x1F20: "ADCMeasurement", 0x8070: "ColorLEDEffects", 0x8071: "RGBEffects",
    0x8300: "Sidetone", 0x8310: "Equalizer", 0x8320: "HeadsetOut",
}

FALLBACK_INDEX = {FEAT_ADC: 0x08, FEAT_SIDETONE: 0x07, FEAT_LED: 0x04}

SWID = 0x0A

HIDPP_ERRORS = {
    1: "неизвестная ошибка", 2: "неверный аргумент", 3: "вне диапазона",
    4: "аппаратная ошибка", 5: "внутренняя ошибка", 6: "неверный индекс функции",
    7: "неверная функция", 8: "устройство занято", 9: "не поддерживается",
}

# Кривая «напряжение → процент» для G733 (как в HeadsetControl).
BATTERY_CURVE = [(4100, 100), (3950, 80), (3850, 60), (3750, 40),
                 (3650, 20), (3500, 10), (3300, 5), (3150, 0)]

# Эффекты подсветки: внутренний ключ -> идентификатор эффекта HID++
EFFECT_IDS = {"off": 0x0000, "static": 0x0001, "cycle": 0x0003, "breathing": 0x000A}
# Если наушники не сообщили список эффектов — индексы как у G633/G733.
EFFECT_FALLBACK_INDEX = {"off": 0, "static": 1, "breathing": 2, "cycle": 3}


class HidppError(Exception):
    def __init__(self, code: int):
        super().__init__(HIDPP_ERRORS.get(code, f"ошибка 0x{code:02x}"))
        self.code = code


class HeadsetOffline(Exception):
    pass


def voltage_to_percent(mv: int) -> int:
    if mv >= BATTERY_CURVE[0][0]:
        return 100
    for (v_hi, p_hi), (v_lo, p_lo) in zip(BATTERY_CURVE, BATTERY_CURVE[1:]):
        if v_lo <= mv <= v_hi:
            return round(p_lo + (p_hi - p_lo) * (mv - v_lo) / (v_hi - v_lo))
    return 0


class G733:
    def __init__(self) -> None:
        self.h: HidHandle | None = None
        self.pid: int | None = None
        self.features: dict[int, int] = {}
        self.led_zones: list[dict] | None = None
        self.eq_info: dict | None = None

    # ------------------------------------------------------------------
    @staticmethod
    def find() -> dict | None:
        for pid in G733_PIDS:
            for d in enumerate_devices(LOGI_VID, pid):
                if d.get("usage_page") == HIDPP_USAGE_PAGE and d.get("usage") == HIDPP_USAGE:
                    return d
        # запасной вариант: интерфейс 3 (на Linux usage_page не сообщается)
        for pid in G733_PIDS:
            for d in enumerate_devices(LOGI_VID, pid):
                if d.get("interface_number") == 3:
                    return d
        return None

    def is_open(self) -> bool:
        return self.h is not None

    def open(self) -> bool:
        info = self.find()
        if not info:
            return False
        self.h = HidHandle(info, "G733")
        self.pid = info.get("product_id")
        self.reset_cache()
        return True

    def reset_cache(self) -> None:
        self.features = {}
        self.led_zones = None
        self.eq_info = None

    def close(self) -> None:
        if self.h:
            self.h.close()
        self.h = None

    # ------------------------------------------------------------------
    def request(self, index: int, function: int, params=b"", timeout: float = 1.2) -> bytes:
        if not self.h:
            raise OSError("G733 не открыт")
        msg = bytearray(20)
        msg[0] = 0x11
        msg[1] = 0xFF
        msg[2] = index
        msg[3] = ((function & 0x0F) << 4) | SWID
        params = bytes(params)
        msg[4:4 + len(params)] = params
        # выбрасываем накопившиеся уведомления (таймаут 0 в hidapi = ждать вечно, поэтому 1 мс)
        for _ in range(32):
            if not self.h.read(64, 1):
                break
        self.h.write(msg)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            r = self.h.read(64, 100)
            if len(r) < 5 or r[0] not in (0x10, 0x11):
                continue
            if r[2] == 0xFF and r[3] == index and r[4] == msg[3]:
                raise HidppError(r[5] if len(r) > 5 else 0)
            if r[2] == 0x8F and r[3] == index:
                raise HeadsetOffline("приёмник сообщил об ошибке HID++ 1.0")
            if r[2] == index and r[3] == msg[3]:
                return r[4:]
        raise HeadsetOffline("наушники не ответили")

    def feature_index(self, feature_id: int) -> int:
        if feature_id in self.features:
            return self.features[feature_id]
        try:
            r = self.request(0x00, 0, feature_id.to_bytes(2, "big"))
            idx = r[0]
        except HidppError as exc:
            idx = FALLBACK_INDEX.get(feature_id, 0)
            log.warning("Root.getFeature(%04x) вернул «%s», беру запасной индекс %s",
                        feature_id, exc, idx)
            return idx  # не кешируем
        self.features[feature_id] = idx
        log.info("функция 0x%04x -> индекс %d", feature_id, idx)
        return idx

    def has(self, feature_id: int) -> bool:
        return self.feature_index(feature_id) != 0

    # --- батарея ------------------------------------------------------
    def battery(self) -> dict:
        idx = self.feature_index(FEAT_ADC)
        if not idx:
            raise HidppError(9)
        r = self.request(idx, 0)
        mv = (r[0] << 8) | r[1]
        flags = r[2]
        if mv < 2500:
            raise HeadsetOffline(f"нет данных о батарее (U={mv} мВ)")
        charging = flags in (0x03,)
        full = flags in (0x07,)
        return {"percent": 100 if full else voltage_to_percent(mv), "mv": mv,
                "charging": charging, "full": full, "flags": flags}

    # --- самоконтроль -------------------------------------------------
    def get_sidetone(self) -> int | None:
        idx = self.feature_index(FEAT_SIDETONE)
        if not idx:
            return None
        return self.request(idx, 0)[0]

    def set_sidetone(self, level: int) -> None:
        idx = self.feature_index(FEAT_SIDETONE)
        if not idx:
            raise HidppError(9)
        self.request(idx, 1, bytes([max(0, min(100, int(level)))]))

    # --- подсветка ----------------------------------------------------
    def lighting_zones(self) -> list[dict]:
        if self.led_zones is not None:
            return self.led_zones
        idx = self.feature_index(FEAT_LED)
        zones: list[dict] = []
        if not idx:
            self.led_zones = zones
            return zones
        try:
            count = self.request(idx, 0)[0]
            for z in range(min(count, 8)):
                zi = self.request(idx, 1, bytes([z]))
                location = (zi[1] << 8) | zi[2]
                n_eff = zi[3]
                effects = {}
                for e in range(min(n_eff, 16)):
                    ei = self.request(idx, 2, bytes([z, e]))
                    effects[(ei[2] << 8) | ei[3]] = e
                zones.append({"index": z, "location": location, "effects": effects})
                log.info("зона подсветки %d: расположение %d, эффекты %s", z, location,
                         {f"0x{k:04x}": v for k, v in effects.items()})
        except HidppError as exc:
            log.warning("не удалось прочитать зоны подсветки (%s), использую 2 зоны по умолчанию", exc)
            zones = []
        if not zones:
            zones = [{"index": 0, "location": 0, "effects": {}},
                     {"index": 1, "location": 0, "effects": {}}]
        self.led_zones = zones
        return zones

    def set_lighting(self, zone: int | None, effect: str, rgb: tuple[int, int, int],
                     brightness: int, speed: int) -> None:
        idx = self.feature_index(FEAT_LED)
        if not idx:
            raise HidppError(9)
        zones = self.lighting_zones()
        targets = [z for z in zones if zone is None or z["index"] == zone]
        brightness = max(1, min(100, int(brightness)))
        speed = max(1, min(10, int(speed)))
        r, g, b = rgb
        for z in targets:
            eff_index = z["effects"].get(EFFECT_IDS[effect])
            if eff_index is None:
                if z["effects"] and effect != "off":
                    log.warning("зона %d не поддерживает эффект %s", z["index"], effect)
                    continue
                eff_index = EFFECT_FALLBACK_INDEX[effect]
            p = bytearray(10)
            if effect == "static":
                k = brightness / 100
                p[0:3] = bytes([round(r * k), round(g * k), round(b * k)])
            elif effect == "breathing":
                period = 11000 - speed * 1000          # 10 c … 1 c
                p[0:3] = bytes([r, g, b])
                p[3:5] = period.to_bytes(2, "big")
                p[5] = 0
                p[6] = brightness
            elif effect == "cycle":
                period = 22000 - speed * 2000          # 20 c … 2 c
                p[5:7] = period.to_bytes(2, "big")
                p[7] = brightness
            self.request(idx, 3, bytes([z["index"], eff_index]) + bytes(p))
            time.sleep(0.01)

    # --- эквалайзер ---------------------------------------------------
    def equalizer_info(self) -> dict | None:
        if self.eq_info is not None:
            return self.eq_info or None
        idx = self.feature_index(FEAT_EQ)
        if not idx:
            self.eq_info = {}
            return None
        try:
            r = self.request(idx, 0)
            count, db_range = r[0], r[1]
            db_min = r[3] - 256 if r[3] > 127 else r[3]
            db_max = r[4] - 256 if r[4] > 127 else r[4]
            if db_min == 0:
                db_min = -db_range
            if db_max == 0:
                db_max = db_range
            freqs = []
            for start in range(0, count, 7):
                fr = self.request(idx, 1, bytes([start]))
                for k in range(7):
                    if start + k >= count:
                        break
                    freqs.append((fr[1 + 2 * k] << 8) | fr[2 + 2 * k])
            self.eq_info = {"count": count, "min": db_min, "max": db_max, "freqs": freqs}
            try:
                raw = self.request(idx, 2, b"\x00")
                log.info("текущий эквалайзер (сырые байты): %s", hx(raw[:count + 2]))
            except Exception:
                pass
        except HidppError as exc:
            log.warning("эквалайзер не прочитан: %s", exc)
            self.eq_info = {}
            return None
        log.info("эквалайзер: %s", self.eq_info)
        return self.eq_info

    def set_equalizer(self, gains: list[int]) -> None:
        idx = self.feature_index(FEAT_EQ)
        info = self.equalizer_info()
        if not idx or not info:
            raise HidppError(9)
        vals = [max(info["min"], min(info["max"], int(g))) & 0xFF for g in gains[:info["count"]]]
        self.request(idx, 3, bytes([0x02]) + bytes(vals))

    # --- диагностика --------------------------------------------------
    def list_features(self) -> list[tuple[int, int]]:
        idx = self.feature_index(FEAT_SET)
        out = []
        if not idx:
            return out
        count = self.request(idx, 0)[0]
        for i in range(1, count + 1):
            r = self.request(idx, 1, bytes([i]))
            out.append((i, (r[0] << 8) | r[1]))
        return out
