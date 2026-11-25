"""Страница «Мышь AJAZZ AJ159»."""
from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QGridLayout, QLabel,
                               QPushButton, QRadioButton, QSpinBox, QVBoxLayout, QWidget)

from core import ajazz
from . import icons
from .widgets import BatteryCard, Card, ColorButton, muted, row


class MousePage(QWidget):
    def __init__(self, svc, cfg) -> None:
        super().__init__()
        self.setObjectName("page")
        self.svc, self.cfg = svc, cfg
        self.info: dict | None = None
        self.stage_rows: list[tuple[QRadioButton, QSpinBox, ColorButton]] = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 24)
        lay.setSpacing(14)
        t = QLabel("Мышь AJAZZ AJ159")
        t.setObjectName("pageTitle")
        lay.addWidget(t)

        self.batt = BatteryCard("Заряд батареи")
        lay.addWidget(self.batt)

        # --- статус настроек
        c = Card("Устройство")
        self.dev_info = muted("—")
        self.settings_msg = QLabel("")
        self.settings_msg.setObjectName("warn")
        self.settings_msg.setWordWrap(True)
        self.settings_msg.hide()
        self.btn_read = QPushButton("Прочитать настройки с мыши")
        self.btn_read.clicked.connect(self.read_settings)
        self.btn_clock = QPushButton("Синхронизировать часы на док-станции")
        self.btn_clock.clicked.connect(self.sync_clock)
        self.chk_clock = QCheckBox("Автоматически синхронизировать часы при запуске и подключении")
        self.chk_clock.setChecked(cfg["mouse"]["sync_clock"])
        self.chk_clock.toggled.connect(self._save_clock)
        c.add(self.dev_info)
        c.add(self.settings_msg)
        c.add(row(self.btn_read, self.btn_clock, None))
        c.add(self.chk_clock)
        c.add(muted("Перед настройкой закройте фирменную программу AJAZZ — два приложения "
                    "одновременно мешают друг другу."))
        lay.addWidget(c)

        # --- DPI
        self.dpi_card = Card("Чувствительность (DPI)",
                             "Отметьте активную ступень. Кнопка DPI на мыши переключает ступени по кругу; "
                             "цвет — это цвет индикатора ступени.")
        self.dpi_grid = QGridLayout()
        self.dpi_grid.setHorizontalSpacing(14)
        self.dpi_card.add(self.dpi_grid)
        self.stage_group = QButtonGroup(self)
        self.btn_dpi = QPushButton("Применить DPI")
        self.btn_dpi.setObjectName("primary")
        self.btn_dpi.clicked.connect(self.apply_dpi)
        self.dpi_card.add(row(self.btn_dpi, None))
        lay.addWidget(self.dpi_card)

        # --- производительность
        c = Card("Отклик и сенсор")
        g = QGridLayout()
        g.setHorizontalSpacing(14)
        g.setVerticalSpacing(10)
        self.rate = QComboBox()
        for hz in sorted(ajazz.RATE_ENCODE):
            self.rate.addItem(f"{hz} Гц", hz)
        self.lift = QComboBox()
        self.lift.addItems(ajazz.LIFT_LEVELS)
        self.debounce = QSpinBox()
        self.debounce.setRange(0, 10)
        self.debounce.setSuffix(" мс")
        self.sleep = QComboBox()
        for sec, name in ajazz.SLEEP_OPTIONS:
            self.sleep.addItem(name, sec)
        self.angle = QCheckBox("Коррекция прямых линий (angle snapping)")
        self.ripple = QCheckBox("Подавление дрожания (ripple control)")
        rows = [("Частота опроса", self.rate), ("Высота отрыва", self.lift),
                ("Защита от дребезга", self.debounce), ("Переход в сон", self.sleep)]
        for i, (name, w) in enumerate(rows):
            g.addWidget(QLabel(name), i, 0)
            g.addWidget(w, i, 1)
        g.setColumnStretch(2, 1)
        c.add(g)
        c.add(self.angle)
        c.add(self.ripple)
        c.add(muted("8000 Гц работает только через док-станцию и заметно сильнее расходует батарею."))
        self.btn_perf = QPushButton("Применить")
        self.btn_perf.setObjectName("primary")
        self.btn_perf.clicked.connect(self.apply_perf)
        c.add(row(self.btn_perf, None))
        lay.addWidget(c)
        self.perf_card = c

        # --- кнопки
        c = Card("Назначение кнопок")
        g = QGridLayout()
        g.setHorizontalSpacing(14)
        self.button_boxes: dict[int, QComboBox] = {}
        for i, (name, slot) in enumerate(ajazz.BUTTONS):
            cb = QComboBox()
            for a, _ in ajazz.BUTTON_ACTIONS:
                cb.addItem(a)
            g.addWidget(QLabel(name), i, 0)
            g.addWidget(cb, i, 1)
            self.button_boxes[slot] = cb
        g.setColumnStretch(2, 1)
        c.add(g)
        c.add(muted("Если левая кнопка будет отключена или переназначена, мышью станет трудно пользоваться — "
                    "будьте внимательны."))
        self.btn_keys = QPushButton("Применить кнопки")
        self.btn_keys.setObjectName("primary")
        self.btn_keys.clicked.connect(self.apply_buttons)
        c.add(row(self.btn_keys, None))
        lay.addWidget(c)
        self.keys_card = c

        lay.addStretch(1)
        self._settings_enabled(False)

    # ------------------------------------------------------------------
    def _save_clock(self, v: bool) -> None:
        self.cfg["mouse"]["sync_clock"] = v
        self.cfg.save()

    def _settings_enabled(self, on: bool) -> None:
        for w in (self.dpi_card, self.perf_card, self.keys_card):
            w.setEnabled(on)

    def on_state(self, st: dict) -> None:
        low = self.cfg["tray"]["low_threshold"]
        present = st.get("present")
        self.btn_read.setEnabled(bool(present))
        self.btn_clock.setEnabled(bool(present))
        if not present:
            self.batt.set(None, "Док-станция / приёмник AJAZZ не найден.", "#8a8f98")
            self.dev_info.setText("—")
            self._settings_enabled(False)
            return
        p = st.get("percent")
        if p is None:
            self.batt.set(None, "Док-станция найдена, мышь спит или выключена — пошевелите её.", "#8a8f98")
        else:
            self.batt.set(p, "Мышь на связи", icons.level_color(p, True, low).name())
        if not self.info:
            self.dev_info.setText(st.get("name", "AJAZZ"))

    # --- чтение -----------------------------------------------------------
    def read_settings(self) -> None:
        self.settings_msg.setText("Читаю настройки мыши…")
        self.settings_msg.show()
        self.btn_read.setEnabled(False)
        self.svc.submit(self.svc.mouse.read_all, self._read_done)

    def _read_done(self, val, err) -> None:
        self.btn_read.setEnabled(True)
        self.settings_msg.show()
        if err or not val:
            self.info = None
            self._settings_enabled(False)
            self.settings_msg.setText(
                f"Не удалось прочитать настройки: {err}. Заряд батареи и часы работают и без этого. "
                "Если мышь не спит, а ошибка повторяется — сделайте отчёт на вкладке «Диагностика» "
                "и пришлите его мне.")
            return
        self.info = val
        parts = [val["name"]]
        if val.get("firmware"):
            parts.append(f"прошивка {val['firmware']}")
        if val.get("device_id") is not None:
            parts.append(f"ID {val['device_id']}")
        self.dev_info.setText(" · ".join(parts))
        if not val.get("settings_ok"):
            self.settings_msg.setText("Мышь ответила, но в непривычном формате — запись настроек отключена "
                                      "ради безопасности. Пришлите отчёт с вкладки «Диагностика».")
            self._settings_enabled(False)
            return
        self.settings_msg.hide()
        self._fill(val)
        self._settings_enabled(True)

    def _fill(self, v: dict) -> None:
        while self.dpi_grid.count():
            w = self.dpi_grid.takeAt(0).widget()
            if w:
                w.deleteLater()
        for b in self.stage_group.buttons():
            self.stage_group.removeButton(b)
        self.stage_rows = []
        stages = v["dpi"]["stages"]
        shown = [s for s in stages]
        while len(shown) > 1 and shown[-1]["x"] == 0:
            shown.pop()
        for i, s in enumerate(shown):
            rb = QRadioButton(f"Ступень {i + 1}")
            sp = QSpinBox()
            sp.setRange(ajazz.DPI_MIN, ajazz.DPI_MAX)
            sp.setSingleStep(ajazz.DPI_STEP)
            sp.setValue(max(ajazz.DPI_MIN, s["x"]))
            sp.setSuffix(" DPI")
            sp.setButtonSymbols(QSpinBox.NoButtons)
            sp.setMinimumWidth(110)
            cb = ColorButton(QColor(*s["rgb"]).name())
            self.stage_group.addButton(rb, i)
            self.dpi_grid.addWidget(rb, i, 0)
            self.dpi_grid.addWidget(sp, i, 1)
            self.dpi_grid.addWidget(cb, i, 2)
            self.stage_rows.append((rb, sp, cb))
        self.dpi_grid.setColumnStretch(3, 1)
        a = v["dpi"]["active"]
        if a < len(self.stage_rows):
            self.stage_rows[a][0].setChecked(True)
        if v.get("rate"):
            self.rate.setCurrentIndex(self.rate.findData(v["rate"]))
        self.lift.setCurrentIndex(min(v.get("lift", 0), 2))
        self.debounce.setValue(v.get("debounce", 0))
        i = self.sleep.findData(v.get("sleep", 0))
        if i < 0:
            self.sleep.addItem(f"{v['sleep']} с", v["sleep"])
            i = self.sleep.count() - 1
        self.sleep.setCurrentIndex(i)
        self.angle.setChecked(v.get("angle", False))
        self.ripple.setChecked(v.get("ripple", False))
        for slot, cbx in self.button_boxes.items():
            name = (v.get("buttons") or {}).get(slot)
            if name is None:
                continue
            if cbx.findText(name) < 0:
                cbx.insertItem(0, name)
            cbx.setCurrentText(name)

    # --- запись -----------------------------------------------------------
    def apply_dpi(self) -> None:
        vals = [sp.value() for _, sp, _ in self.stage_rows]
        cols = [(c.color().red(), c.color().green(), c.color().blue()) for _, _, c in self.stage_rows]
        act = max(0, self.stage_group.checkedId())
        self.svc.submit(lambda: self.svc.mouse.set_dpi(vals, cols, act), self._report("DPI"))

    def apply_perf(self) -> None:
        hz = self.rate.currentData()
        args = (self.debounce.value(), self.lift.currentIndex(), self.angle.isChecked(),
                self.ripple.isChecked(), self.sleep.currentData())
        m = self.svc.mouse
        self.svc.submit(lambda: m.set_perf(hz, *args), self._report("Настройки сенсора"))

    def apply_buttons(self) -> None:
        changes = []
        current = (self.info or {}).get("buttons") or {}
        for slot, cbx in self.button_boxes.items():
            name = cbx.currentText()
            if name in dict(ajazz.BUTTON_ACTIONS) and name != current.get(slot):
                changes.append((slot, name))
        if not changes:
            self.window().toast("Кнопки: изменений нет")
            return
        m = self.svc.mouse

        def job():
            for slot, name in changes:
                m.set_button(slot, name)
        self.svc.submit(job, self._report("Кнопки"))

    def sync_clock(self) -> None:
        self.svc.submit(self.svc.mouse.sync_clock, self._report("Часы док-станции", reread=False))

    def _report(self, what: str, reread: bool = True):
        def cb(val, err):
            if err:
                self.window().toast(f"{what}: не удалось — {err}", error=True)
            else:
                self.window().toast(f"{what}: применено")
                if reread:
                    self.read_settings()
        return cb
