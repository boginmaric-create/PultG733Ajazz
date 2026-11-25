"""Страница «Наушники G733»."""
from __future__ import annotations

import math

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QCheckBox, QComboBox, QGridLayout, QLabel, QPushButton,
                               QSlider, QVBoxLayout, QWidget)

from . import icons
from .widgets import BatteryCard, Card, ColorButton, ValueSlider, muted, row

EFFECTS = [("static", "Статичный цвет"), ("breathing", "Дыхание"),
           ("cycle", "Смена цветов (радуга)"), ("off", "Выключена")]

EQ_PRESETS = ["Ровный", "Усиление басов", "Шаги (шутеры)", "Голос / подкасты",
              "Музыка", "Кино", "Свой"]


def preset_gains(name: str, freqs: list[int], lo: int, hi: int) -> list[int]:
    def g(fr: int) -> float:
        x = math.log10(max(fr, 20))
        bell = lambda c, w: math.exp(-((x - c) / w) ** 2)
        if name == "Усиление басов":
            return 7 * max(0.0, min(1.0, (2.6 - x) / 1.0))
        if name == "Шаги (шутеры)":
            return 6 * bell(3.6, 0.35) - 4 * max(0.0, min(1.0, (2.4 - x) / 0.8))
        if name == "Голос / подкасты":
            return 5 * bell(3.3, 0.4) - 4 * max(0.0, min(1.0, (2.2 - x) / 0.8))
        if name == "Музыка":
            return 4 * max(0.0, min(1.0, (2.4 - x) / 0.9)) + 3 * max(0.0, min(1.0, (x - 3.6) / 0.6)) - 1.5 * bell(3.0, 0.35)
        if name == "Кино":
            return 5 * max(0.0, min(1.0, (2.3 - x) / 0.9)) + 2.5 * bell(3.4, 0.35) + 2 * max(0.0, min(1.0, (x - 3.8) / 0.5))
        return 0.0
    return [max(lo, min(hi, round(g(f)))) for f in freqs]


def fmt_freq(f: int) -> str:
    return f"{f / 1000:g} кГц" if f >= 1000 else f"{f} Гц"


class HeadsetPage(QWidget):
    def __init__(self, svc, cfg) -> None:
        super().__init__()
        self.setObjectName("page")
        self.svc, self.cfg = svc, cfg
        self.eq_info = None
        self.eq_sliders: list[QSlider] = []
        self.zones = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 24)
        lay.setSpacing(14)
        t = QLabel("Наушники Logitech G733")
        t.setObjectName("pageTitle")
        lay.addWidget(t)

        # --- батарея
        self.batt = BatteryCard("Заряд батареи")
        lay.addWidget(self.batt)

        # --- самоконтроль
        c = Card("Самоконтроль микрофона",
                 "Насколько громко вы слышите свой голос в наушниках (0 — выключено).")
        self.sidetone = ValueSlider(0, 100, "%")
        self.sidetone.setEnabled(False)
        self._st_timer = QTimer(self, singleShot=True, interval=350)
        self._st_timer.timeout.connect(self.apply_sidetone)
        self.sidetone.valueChanged.connect(lambda _: self._st_timer.start())
        c.add(self.sidetone)
        lay.addWidget(c)

        # --- подсветка
        c = Card("Подсветка", "Применяется сразу к наушникам. Яркость и скорость влияют на выбранный эффект.")
        g = QGridLayout()
        g.setHorizontalSpacing(14)
        g.setVerticalSpacing(10)
        self.zone = QComboBox()
        self.zone.addItem("Все зоны", None)
        self.effect = QComboBox()
        for key, name in EFFECTS:
            self.effect.addItem(name, key)
        self.color = ColorButton("#00b6ff")
        self.bright = ValueSlider(1, 100, "%")
        self.bright.setValue(100)
        self.speed = ValueSlider(1, 10)
        self.speed.setValue(7)
        g.addWidget(QLabel("Зона"), 0, 0)
        g.addWidget(self.zone, 0, 1)
        g.addWidget(QLabel("Эффект"), 1, 0)
        g.addWidget(self.effect, 1, 1)
        g.addWidget(QLabel("Цвет"), 2, 0)
        g.addWidget(self.color, 2, 1, Qt.AlignLeft)
        g.addWidget(QLabel("Яркость"), 3, 0)
        g.addWidget(self.bright, 3, 1)
        g.addWidget(QLabel("Скорость"), 4, 0)
        g.addWidget(self.speed, 4, 1)
        g.setColumnStretch(1, 1)
        c.add(g)
        self.btn_light = QPushButton("Применить подсветку")
        self.btn_light.setObjectName("primary")
        self.btn_light.clicked.connect(self.apply_lighting)
        c.add(row(self.btn_light, None))
        self.effect.currentIndexChanged.connect(self._effect_ui)
        lay.addWidget(c)
        self.light_card = c

        # --- эквалайзер
        self.eq_card = Card("Эквалайзер (встроенный в наушники)")
        self.eq_status = muted("Подключите наушники, чтобы узнать, есть ли встроенный эквалайзер.")
        self.eq_card.add(self.eq_status)
        self.eq_grid = QGridLayout()
        self.eq_grid.setHorizontalSpacing(6)
        self.eq_card.add(self.eq_grid)
        self.eq_preset = QComboBox()
        self.eq_preset.addItems(EQ_PRESETS)
        self.eq_preset.setCurrentText(cfg["headset"].get("eq_preset", "Ровный"))
        self.eq_preset.currentTextChanged.connect(self._apply_preset)
        self.btn_eq = QPushButton("Применить эквалайзер")
        self.btn_eq.setObjectName("primary")
        self.btn_eq.clicked.connect(self.apply_eq)
        self.eq_controls = row(QLabel("Пресет"), self.eq_preset, None, self.btn_eq)
        self.eq_card.add(self.eq_controls)
        self._eq_enable(False)
        lay.addWidget(self.eq_card)

        # --- общие
        c = Card("Поведение")
        self.chk_apply = QCheckBox("Восстанавливать мои настройки при каждом включении наушников")
        self.chk_apply.setChecked(cfg["headset"]["apply_on_connect"])
        self.chk_apply.toggled.connect(self._save_apply)
        c.add(self.chk_apply)
        c.add(muted("Blue VO!CE, DTS Headphone:X и громкость микрофона — это обработка звука на компьютере "
                    "внутри G HUB, а не функции самих наушников, поэтому здесь их нет. "
                    "Громкость микрофона меняется в «Параметры Windows → Звук»."))
        lay.addWidget(c)
        lay.addStretch(1)

        self._load_saved_lighting()
        self._effect_ui()
        self.set_controls_enabled(False)

    # ------------------------------------------------------------------
    def set_controls_enabled(self, on: bool) -> None:
        self.sidetone.setEnabled(on)
        self.btn_light.setEnabled(on)
        self.btn_eq.setEnabled(on and bool(self.eq_info))

    def _effect_ui(self) -> None:
        e = self.effect.currentData()
        self.color.setEnabled(e in ("static", "breathing"))
        self.bright.setEnabled(e != "off")
        self.speed.setEnabled(e in ("breathing", "cycle"))

    def _load_saved_lighting(self) -> None:
        L = self.cfg["headset"].get("lighting")
        if not L:
            return
        i = self.effect.findData(L.get("effect", "static"))
        if i >= 0:
            self.effect.setCurrentIndex(i)
        self.color.setColor(L.get("color", "#00b6ff"))
        self.bright.setValue(L.get("brightness", 100))
        self.speed.setValue(L.get("speed", 7))

    def _save_apply(self, v: bool) -> None:
        self.cfg["headset"]["apply_on_connect"] = v
        self.cfg.save()

    # --- состояние ------------------------------------------------------
    def on_state(self, st: dict) -> None:
        low = self.cfg["tray"]["low_threshold"]
        if not st.get("present"):
            self.batt.set(None, "Приёмник G733 не найден. Вставьте USB-приёмник.", "#8a8f98")
            self.set_controls_enabled(False)
            return
        if not st.get("online"):
            self.batt.set(None, "Приёмник найден, но наушники выключены или вне зоны связи.", "#8a8f98")
            self.set_controls_enabled(False)
            return
        p = st["percent"]
        state = "Заряжается" if st.get("charging") else ("Полностью заряжены" if st.get("full") else "Работают от батареи")
        self.batt.set(p, f"{state} · напряжение {st['mv'] / 1000:.2f} В",
                      icons.level_color(p, True, low).name())
        self.set_controls_enabled(True)

    def load_details(self) -> None:
        """Вызывается, когда наушники появились в сети."""
        g = self.svc.g733

        def job():
            return {"sidetone": g.get_sidetone(), "zones": g.lighting_zones(), "eq": g.equalizer_info()}

        self.svc.submit(job, self._details_done)

    def _details_done(self, val, err) -> None:
        if err or not val:
            return
        if val["sidetone"] is not None:
            self.sidetone.setValue(val["sidetone"])
        self.zones = val["zones"]
        cur = self.zone.currentData()
        self.zone.blockSignals(True)
        self.zone.clear()
        self.zone.addItem("Все зоны", None)
        names = {0: "Зона 1 (логотип / основная)", 1: "Зона 2 (полоса)"}
        for z in self.zones:
            self.zone.addItem(names.get(z["index"], f"Зона {z['index'] + 1}"), z["index"])
        i = self.zone.findData(cur)
        self.zone.setCurrentIndex(max(0, i))
        self.zone.blockSignals(False)
        self._build_eq(val["eq"])

    # --- самоконтроль -----------------------------------------------------
    def apply_sidetone(self) -> None:
        v = self.sidetone.value()
        self.cfg["headset"]["sidetone"] = v
        self.cfg.save()
        self.svc.submit(lambda: self.svc.g733.set_sidetone(v), self._report("Самоконтроль"))

    # --- подсветка --------------------------------------------------------
    def lighting_settings(self) -> dict:
        return {"zone": self.zone.currentData(), "effect": self.effect.currentData(),
                "color": self.color.color().name(), "brightness": self.bright.value(),
                "speed": self.speed.value()}

    def apply_lighting(self) -> None:
        L = self.lighting_settings()
        self.cfg["headset"]["lighting"] = L
        self.cfg.save()
        self.svc.submit(lambda: apply_lighting(self.svc.g733, L), self._report("Подсветка"))

    # --- эквалайзер -------------------------------------------------------
    def _eq_enable(self, on: bool) -> None:
        self.eq_preset.setEnabled(on)
        self.btn_eq.setEnabled(on)

    def _build_eq(self, info) -> None:
        while self.eq_grid.count():
            w = self.eq_grid.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.eq_sliders = []
        self.eq_info = info
        if not info:
            self.eq_status.setText("Эти наушники не сообщают о встроенном эквалайзере. "
                                   "Эквалайзер G HUB для G733 работает программно на ПК — "
                                   "используйте эквалайзер Windows или Equalizer APO.")
            self._eq_enable(False)
            return
        self.eq_status.setText(f"{info['count']} полос, от {info['min']} до +{info['max']} дБ. "
                               "Настройка сохраняется в наушниках.")
        saved = self.cfg["headset"].get("eq_gains") or [0] * info["count"]
        for i, f in enumerate(info["freqs"]):
            s = QSlider(Qt.Vertical)
            s.setRange(info["min"], info["max"])
            s.setValue(saved[i] if i < len(saved) else 0)
            s.setMinimumHeight(150)
            val = QLabel(f"{s.value():+d}")
            val.setAlignment(Qt.AlignCenter)
            s.valueChanged.connect(lambda v, l=val: (l.setText(f"{v:+d}"), self._mark_custom()))
            lab = QLabel(fmt_freq(f))
            lab.setObjectName("muted")
            lab.setAlignment(Qt.AlignCenter)
            self.eq_grid.addWidget(val, 0, i)
            self.eq_grid.addWidget(s, 1, i, Qt.AlignHCenter)
            self.eq_grid.addWidget(lab, 2, i)
            self.eq_sliders.append(s)
        self._eq_enable(True)

    def _mark_custom(self) -> None:
        if not getattr(self, "_preset_loading", False) and self.eq_preset.currentText() != "Свой":
            self.eq_preset.blockSignals(True)
            self.eq_preset.setCurrentText("Свой")
            self.eq_preset.blockSignals(False)

    def _apply_preset(self, name: str) -> None:
        if not self.eq_info or name == "Свой":
            return
        gains = preset_gains(name, self.eq_info["freqs"], self.eq_info["min"], self.eq_info["max"])
        self._preset_loading = True
        for s, v in zip(self.eq_sliders, gains):
            s.setValue(v)
        self._preset_loading = False

    def apply_eq(self) -> None:
        gains = [s.value() for s in self.eq_sliders]
        self.cfg["headset"]["eq_gains"] = gains
        self.cfg["headset"]["eq_preset"] = self.eq_preset.currentText()
        self.cfg.save()
        self.svc.submit(lambda: self.svc.g733.set_equalizer(gains), self._report("Эквалайзер"))

    # ------------------------------------------------------------------
    def _report(self, what: str):
        def cb(val, err):
            win = self.window()
            if err:
                win.toast(f"{what}: не удалось — {err}", error=True)
            else:
                win.toast(f"{what}: применено")
        return cb


def apply_lighting(g, L: dict) -> None:
    from PySide6.QtGui import QColor
    c = QColor(L.get("color", "#00b6ff"))
    g.set_lighting(L.get("zone"), L.get("effect", "static"), (c.red(), c.green(), c.blue()),
                   L.get("brightness", 100), L.get("speed", 7))
