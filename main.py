"""Пульт G733 + AJAZZ — точка входа.

Запуск:  python main.py          — открыть окно
         python main.py --tray   — сразу свернуть в трей (так запускает автозапуск)
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtCore import QLibraryInfo, QLocale, QTimer, QTranslator  # noqa: E402
from PySide6.QtNetwork import QLocalServer, QLocalSocket  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox, QStyleFactory  # noqa: E402

from core.config import APP_ID, APP_TITLE, Config, data_dir, set_autostart  # noqa: E402
from core.hidio import hid_available  # noqa: E402
from core.service import DeviceService  # noqa: E402
from ui import icons  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402
from ui.widgets import STYLE  # noqa: E402


def setup_logging() -> None:
    fh = RotatingFileHandler(data_dir() / "log.txt", maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(fh)
    if sys.stderr:
        sh = logging.StreamHandler()
        sh.setLevel(logging.INFO)
        root.addHandler(sh)


def main() -> int:
    setup_logging()
    log = logging.getLogger("main")
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setQuitOnLastWindowClosed(False)
    app.setStyle(QStyleFactory.create("Fusion"))
    app.setStyleSheet(STYLE)
    app.setWindowIcon(icons.app_icon())
    QLocale.setDefault(QLocale(QLocale.Russian, QLocale.Russia))
    tr = QTranslator(app)
    if tr.load("qtbase_ru", QLibraryInfo.path(QLibraryInfo.TranslationsPath)):
        app.installTranslator(tr)

    # одна копия программы: вторая просто показывает окно первой
    sock = QLocalSocket()
    sock.connectToServer(APP_ID)
    if sock.waitForConnected(300):
        sock.write(b"show")
        sock.waitForBytesWritten(300)
        return 0
    QLocalServer.removeServer(APP_ID)
    server = QLocalServer()
    server.listen(APP_ID)

    if not hid_available():
        QMessageBox.critical(None, APP_TITLE, "Не найден модуль hidapi. Установите зависимости: "
                             "pip install -r requirements.txt")
        return 1

    cfg = Config()
    if cfg["autostart"]:
        set_autostart(True)          # обновить путь, если программу перенесли
    svc = DeviceService(cfg)
    win = MainWindow(svc, cfg)

    def on_new_connection():
        c = server.nextPendingConnection()
        if c:
            c.readyRead.connect(lambda: win.show_page(None))
    server.newConnection.connect(on_new_connection)

    start_hidden = "--tray" in sys.argv and cfg["start_hidden"]
    if not start_hidden:
        win.show()
    QTimer.singleShot(200, svc.poll)
    log.info("запуск: %s", APP_TITLE)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
