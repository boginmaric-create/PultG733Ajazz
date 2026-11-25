"""Страницы «Значки и запуск» и «Диагностика»."""
from __future__ import annotations

import datetime as dt
import logging
import platform
import sys

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QGridLayout, QHBoxLayout, QLabel,
                               QPlainTextEdit, QPushButton, QRadioButton, QSpinBox, QVBoxLayout, QWidget)

from core import ajazz, g733
from core.config import APP_TITLE, data_dir, set_autostart
from core.hidio import enumerate_devices, hid_available
from . import icons
from .widgets import Card, muted, row

VERSION = "1.0"

STYLES = [("glyph_number", "Значок устройства и число"),
          ("number", "Только число"),
          ("glyph_bar", "Значок устройства и шкала")]


class TraySettingsPage(QWidget):
    def __init__(self, cfg, on_change) -> None:
        super().__init__()
        self.setObjectName("page")
        self.cfg, self.on_change = cfg, on_change
        T = cfg["tray"]
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 24)
        lay.setSpacing(14)
        t = QLabel("Значки и запуск")
        t.setObjectName("pageTitle")
        lay.addWidget(t)

        c = Card("Значки заряда на панели задач",
                 "Значки появляются в области уведомлений рядом с часами. Чтобы они были видны всегда, а не "
                 "прятались под стрелкой «^»: Параметры Windows → Персонализация → Панель задач → "
                 "Другие значки на панели задач → включите «Пульт G733 + AJAZZ» (оба значка). "
                 "Или просто перетащите значки мышью из-под стрелки на панель.")
        self.chk_h = QCheckBox("Показывать значок наушников G733")
        self.chk_h.setChecked(T["show_headset"])
        self.chk_m = QCheckBox("Показывать значок мыши AJAZZ")
        self.chk_m.setChecked(T["show_mouse"])
        c.add(self.chk_h)
        c.add(self.chk_m)

        c.add(QLabel("Вид значка"))
        self.style_group = QButtonGroup(self)
        prev = QHBoxLayout()
        prev.setSpacing(18)
        for i, (key, name) in enumerate(STYLES):
            v = QVBoxLayout()
            rb = QRadioButton(name)
            rb.setChecked(T["style"] == key)
            self.style_group.addButton(rb, i)
            pics = QHBoxLayout()
            for kind, pct, ch in (("headset", 82, False), ("mouse", 15, True)):
                l = QLabel()
                l.setPixmap(icons.render(kind, pct, True, ch, key, 20, 64).scaled(40, 40))
                l.setStyleSheet("background:#0e1118; border-radius:6px; padding:4px;")
                pics.addWidget(l)
            pics.addStretch(1)
            v.addLayout(pics)
            v.addWidget(rb)
            prev.addLayout(v)
        prev.addStretch(1)
        c.add(prev)
        lay.addWidget(c)

        c = Card("Опрос и уведомления")
        g = QGridLayout()
        self.poll = QSpinBox()
        self.poll.setRange(10, 600)
        self.poll.setSuffix(" с")
        self.poll.setValue(T["poll_seconds"])
        self.low = QSpinBox()
        self.low.setRange(5, 50)
        self.low.setSuffix(" %")
        self.low.setValue(T["low_threshold"])
        g.addWidget(QLabel("Обновлять заряд каждые"), 0, 0)
        g.addWidget(self.poll, 0, 1)
        g.addWidget(QLabel("Низкий заряд — ниже"), 1, 0)
        g.addWidget(self.low, 1, 1)
        g.setColumnStretch(2, 1)
        c.add(g)
        self.chk_notify = QCheckBox("Показывать уведомление Windows, когда заряд становится низким")
        self.chk_notify.setChecked(T["notify_low"])
        c.add(self.chk_notify)
        lay.addWidget(c)

        c = Card("Запуск")
        self.chk_auto = QCheckBox("Запускать вместе с Windows")
        self.chk_auto.setChecked(cfg["autostart"])
        self.chk_hidden = QCheckBox("При автозапуске сразу сворачивать в трей")
        self.chk_hidden.setChecked(cfg["start_hidden"])
        self.chk_close = QCheckBox("Крестик окна сворачивает программу в трей (а не закрывает)")
        self.chk_close.setChecked(cfg["close_to_tray"])
        for w in (self.chk_auto, self.chk_hidden, self.chk_close):
            c.add(w)
        if sys.platform != "win32":
            c.add(muted("Автозапуск настраивается только в Windows."))
        lay.addWidget(c)
        lay.addStretch(1)

        for w in (self.chk_h, self.chk_m, self.chk_notify, self.chk_auto, self.chk_hidden, self.chk_close):
            w.toggled.connect(self._save)
        self.style_group.idToggled.connect(lambda *_: self._save())
        self.poll.valueChanged.connect(self._save)
        self.low.valueChanged.connect(self._save)

    def _save(self, *_):
        T = self.cfg["tray"]
        T["show_headset"] = self.chk_h.isChecked()
        T["show_mouse"] = self.chk_m.isChecked()
        T["style"] = STYLES[max(0, self.style_group.checkedId())][0]
        T["poll_seconds"] = self.poll.value()
        T["low_threshold"] = self.low.value()
        T["notify_low"] = self.chk_notify.isChecked()
        if self.cfg["autostart"] != self.chk_auto.isChecked():
            self.cfg.data["autostart"] = self.chk_auto.isChecked()
            set_autostart(self.chk_auto.isChecked())
        self.cfg.data["start_hidden"] = self.chk_hidden.isChecked()
        self.cfg.data["close_to_tray"] = self.chk_close.isChecked()
        self.cfg.save()
        self.on_change()


class DiagnosticsPage(QWidget):
    def __init__(self, svc) -> None:
        super().__init__()
        self.setObjectName("page")
        self.svc = svc
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 24)
        lay.setSpacing(14)
        t = QLabel("Диагностика")
        t.setObjectName("pageTitle")
        lay.addWidget(t)
        c = Card("Отчёт для разработчика",
                 "Если что-то не работает: нажмите «Создать отчёт» (наушники включены, мышь разбужена, "
                 "G HUB и программа AJAZZ закрыты) и пришлите файл. В отчёте только технические "
                 "данные устройств — никаких личных данных.")
        self.btn = QPushButton("Создать отчёт")
        self.btn.setObjectName("primary")
        self.btn.clicked.connect(self.make_report)
        b2 = QPushButton("Скопировать текст")
        b2.clicked.connect(lambda: QGuiApplication.clipboard().setText(self.text.toPlainText()))
        b3 = QPushButton("Открыть папку с журналом")
        b3.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(data_dir()))))
        c.add(row(self.btn, b2, b3, None))
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setMinimumHeight(320)
        c.add(self.text)
        lay.addWidget(c, 1)
        c = Card("О программе")
        c.add(muted(f"{APP_TITLE}, версия {VERSION}. Python {platform.python_version()}, "
                    f"{platform.system()} {platform.release()}.\n"
                    "Протоколы устройств взяты из открытых проектов: HeadsetControl (Logitech HID++), "
                    "AJAZZ Control Center и OpenMouse (мыши AJAZZ на VID 0x3151)."))
        lay.addWidget(c)

    def make_report(self) -> None:
        self.btn.setEnabled(False)
        self.text.setPlainText("Собираю данные… (до 20 секунд)")
        self.svc.submit(self._collect, self._done)

    def _collect(self) -> str:
        L = [f"{APP_TITLE} {VERSION} — отчёт {dt.datetime.now():%Y-%m-%d %H:%M:%S}",
             f"ОС: {platform.platform()}  Python {platform.python_version()}  hidapi: {hid_available()}", ""]
        for vid, name in ((g733.LOGI_VID, "Logitech"), (ajazz.VID, "AJAZZ/0x3151")):
            L.append(f"== HID-устройства {name} ==")
            for d in enumerate_devices(vid):
                L.append(f"  {d.get('vendor_id', 0):04x}:{d.get('product_id', 0):04x} if={d.get('interface_number')} "
                         f"up={d.get('usage_page', 0):04x} u={d.get('usage', 0):04x} «{d.get('product_string')}»")
            L.append("")
        L.append("== G733 ==")
        g = self.svc.g733
        try:
            if not g.is_open() and not g.open():
                L.append("  приёмник не найден")
            else:
                g.reset_cache()
                try:
                    L.append(f"  батарея: {g.battery()}")
                except Exception as exc:
                    L.append(f"  батарея: ошибка {exc}")
                try:
                    for i, fid in g.list_features():
                        L.append(f"  индекс {i:2d}: 0x{fid:04x} {g733.FEATURE_NAMES.get(fid, '')}")
                except Exception as exc:
                    L.append(f"  список функций: ошибка {exc}")
                for name, fn in (("самоконтроль", g.get_sidetone), ("зоны подсветки", g.lighting_zones),
                                 ("эквалайзер", g.equalizer_info)):
                    try:
                        L.append(f"  {name}: {fn()}")
                    except Exception as exc:
                        L.append(f"  {name}: ошибка {exc}")
        except Exception as exc:
            L.append(f"  ошибка: {exc}")
        L.append("")
        L.append("== AJAZZ ==")
        m = self.svc.mouse
        try:
            if not m.is_open() and not m.open():
                L.append("  устройство не найдено")
            else:
                L.append(f"  {m.name}, PID {m.pid:04x}, режим {m.transport}")
                L.extend("  " + s for s in m.probe_raw())
                try:
                    L.append(f"  battery(): {m.battery()}")
                except Exception as exc:
                    L.append(f"  battery(): ошибка {exc}")
        except Exception as exc:
            L.append(f"  ошибка: {exc}")
        text = "\n".join(L)
        path = data_dir() / f"report-{dt.datetime.now():%Y%m%d-%H%M%S}.txt"
        path.write_text(text, encoding="utf-8")
        logging.getLogger("diag").info("отчёт сохранён: %s", path)
        return text + f"\n\nОтчёт сохранён: {path}"

    def _done(self, val, err) -> None:
        self.btn.setEnabled(True)
        self.text.setPlainText(val if val else f"Ошибка: {err}")
