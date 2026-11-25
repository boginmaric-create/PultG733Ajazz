"""Главное окно, значки в трее и уведомления."""
from __future__ import annotations

import logging

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                               QMainWindow, QMenu, QScrollArea, QStackedWidget, QSystemTrayIcon,
                               QVBoxLayout, QWidget)

from core.config import APP_TITLE
from . import icons
from .headset_page import HeadsetPage, apply_lighting
from .mouse_page import MousePage
from .other_pages import DiagnosticsPage, TraySettingsPage

log = logging.getLogger("ui")


def scrolled(w: QWidget) -> QScrollArea:
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setWidget(w)
    return sa


class MainWindow(QMainWindow):
    def __init__(self, svc, cfg) -> None:
        super().__init__()
        self.svc, self.cfg = svc, cfg
        self.quitting = False
        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(icons.app_icon())
        self.resize(980, 760)

        root = QWidget()
        root.setObjectName("root")
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        side = QWidget()
        side.setFixedWidth(230)
        side.setStyleSheet("background:#1a1f2b;")
        sv = QVBoxLayout(side)
        sv.setContentsMargins(10, 18, 10, 12)
        logo = QLabel()
        logo.setPixmap(icons.app_icon().pixmap(40, 40))
        title = QLabel(APP_TITLE)
        title.setStyleSheet("font-size:12pt; font-weight:600; color:white;")
        title.setWordWrap(True)
        top = QHBoxLayout()
        top.addWidget(logo)
        top.addWidget(title, 1)
        sv.addLayout(top)
        sv.addSpacing(10)
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        sv.addWidget(self.nav, 1)
        self.toast_lbl = QLabel("")
        self.toast_lbl.setWordWrap(True)
        self.toast_lbl.setStyleSheet("color:#9aa3b5; font-size:9pt; padding:6px;")
        sv.addWidget(self.toast_lbl)
        self._toast_timer = QTimer(self, singleShot=True, interval=7000)
        self._toast_timer.timeout.connect(lambda: self.toast_lbl.setText(""))

        self.stack = QStackedWidget()
        h.addWidget(side)
        h.addWidget(self.stack, 1)
        self.setCentralWidget(root)

        self.headset_page = HeadsetPage(svc, cfg)
        self.mouse_page = MousePage(svc, cfg)
        self.tray_page = TraySettingsPage(cfg, self.on_tray_settings)
        self.diag_page = DiagnosticsPage(svc)
        for name, page in (("🎧  Наушники G733", self.headset_page), ("🖱  Мышь AJAZZ", self.mouse_page),
                           ("🔋  Значки и запуск", self.tray_page), ("🛠  Диагностика", self.diag_page)):
            self.nav.addItem(QListWidgetItem(name))
            self.stack.addWidget(scrolled(page))
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)

        # --- трей
        self.tray_h = QSystemTrayIcon(self)
        self.tray_m = QSystemTrayIcon(self)
        self.menu = QMenu()
        self.act_h = QAction("Наушники: —", self.menu, enabled=False)
        self.act_m = QAction("Мышь: —", self.menu, enabled=False)
        self.menu.addAction(self.act_h)
        self.menu.addAction(self.act_m)
        self.menu.addSeparator()
        self.menu.addAction("Открыть окно", lambda: self.show_page(None))
        self.menu.addAction("Обновить заряд", svc.poll)
        self.menu.addSeparator()
        self.menu.addAction("Выход", self.quit_app)
        for tray, page in ((self.tray_h, 0), (self.tray_m, 1)):
            tray.setContextMenu(self.menu)
            tray.activated.connect(lambda reason, p=page: self._tray_clicked(reason, p))
        self.low_warned = {"headset": False, "mouse": False}

        svc.headsetChanged.connect(self.on_headset)
        svc.mouseChanged.connect(self.on_mouse)
        svc.headsetConnected.connect(self.on_headset_connected)
        svc.mouseConnected.connect(self.on_mouse_connected)
        self.update_tray()

    # ------------------------------------------------------------------
    def toast(self, text: str, error: bool = False) -> None:
        self.toast_lbl.setStyleSheet(f"color:{'#f0524f' if error else '#3ccf6e'}; font-size:9pt; padding:6px;")
        self.toast_lbl.setText(text)
        self._toast_timer.start()

    def show_page(self, idx) -> None:
        if idx is not None:
            self.nav.setCurrentRow(idx)
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _tray_clicked(self, reason, page) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            if self.isVisible() and not self.isMinimized() and self.nav.currentRow() == page:
                self.hide()
            else:
                self.show_page(page)

    def closeEvent(self, e) -> None:
        if self.cfg["close_to_tray"] and not self.quitting and QSystemTrayIcon.isSystemTrayAvailable():
            e.ignore()
            self.hide()
            if not self.cfg.data.get("_hint_shown"):
                self.cfg.data["_hint_shown"] = True
                self.cfg.save()
                tray = self.tray_h if self.tray_h.isVisible() else self.tray_m
                tray.showMessage(APP_TITLE, "Программа продолжает работать в трее. "
                                 "Выход — правой кнопкой по значку.", QSystemTrayIcon.Information, 4000)
        else:
            e.accept()
            self.quit_app()

    def quit_app(self) -> None:
        self.quitting = True
        self.tray_h.hide()
        self.tray_m.hide()
        QApplication.quit()

    # --- состояние устройств -------------------------------------------
    def on_headset(self, st: dict) -> None:
        self.headset_page.on_state(st)
        self.update_tray()

    def on_mouse(self, st: dict) -> None:
        self.mouse_page.on_state(st)
        self.update_tray()

    def on_headset_connected(self) -> None:
        log.info("наушники в сети")
        H = self.cfg["headset"]
        if H["apply_on_connect"]:
            g = self.svc.g733

            def job():
                if H.get("sidetone") is not None:
                    g.set_sidetone(H["sidetone"])
                if H.get("lighting"):
                    apply_lighting(g, H["lighting"])
                if H.get("eq_gains") and g.equalizer_info():
                    g.set_equalizer(H["eq_gains"])
            self.svc.submit(job, lambda v, e: e and log.warning("восстановление настроек: %s", e))
        self.headset_page.load_details()

    def on_mouse_connected(self) -> None:
        if self.cfg["mouse"]["sync_clock"]:
            self.svc.submit(self.svc.mouse.sync_clock, None)
        self.mouse_page.read_settings()

    def on_tray_settings(self) -> None:
        self.svc.set_interval(self.cfg["tray"]["poll_seconds"])
        self.update_tray()

    # --- трей ------------------------------------------------------------
    def update_tray(self) -> None:
        T = self.cfg["tray"]
        hs, ms = self.svc.headset_state, self.svc.mouse_state

        def describe(st, name):
            if not st.get("present"):
                return f"{name}: не подключено", None, False, False
            if not st.get("online") or st.get("percent") is None:
                return f"{name}: нет связи", None, False, False
            ch = st.get("charging", False)
            return f"{name}: {st['percent']}%" + (" — заряжается" if ch else ""), st["percent"], True, ch

        th, ph, oh, ch = describe(hs, "Наушники G733")
        tm, pm, om, cm = describe(ms, "Мышь AJAZZ")
        self.act_h.setText(th)
        self.act_m.setText(tm)
        for tray, kind, text, pct, online, charging, show in (
                (self.tray_h, "headset", th, ph, oh, ch, T["show_headset"]),
                (self.tray_m, "mouse", tm, pm, om, cm, T["show_mouse"])):
            tray.setIcon(icons.tray_icon(kind, pct, online, charging, T["style"], T["low_threshold"]))
            tray.setToolTip(text)
            tray.setVisible(show)
            self._check_low(kind, tray, text, pct, charging)

    def _check_low(self, kind, tray, text, pct, charging) -> None:
        T = self.cfg["tray"]
        if pct is None or charging:
            if charging:
                self.low_warned[kind] = False
            return
        if pct <= T["low_threshold"]:
            if not self.low_warned[kind] and T["notify_low"]:
                tray.showMessage("Низкий заряд", f"{text}. Пора поставить на зарядку.",
                                 QSystemTrayIcon.Warning, 8000)
            self.low_warned[kind] = True
        elif pct > T["low_threshold"] + 5:
            self.low_warned[kind] = False
