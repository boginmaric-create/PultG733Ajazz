"""Фоновый поток для всего обмена с устройствами + периодический опрос."""
from __future__ import annotations

import logging
import queue
import threading

from PySide6.QtCore import QObject, QTimer, Signal

from .ajazz import AjazzMouse, MouseError
from .g733 import G733, HeadsetOffline, HidppError

log = logging.getLogger("service")


class DeviceService(QObject):
    _deliver = Signal(object, object, object)
    headsetChanged = Signal(dict)
    mouseChanged = Signal(dict)
    headsetConnected = Signal()      # наушники только что появились «в сети»
    mouseConnected = Signal()

    def __init__(self, cfg) -> None:
        super().__init__()
        self.cfg = cfg
        self.g733 = G733()
        self.mouse = AjazzMouse()
        self.headset_state: dict = {"present": False}
        self.mouse_state: dict = {"present": False}
        self._q: queue.Queue = queue.Queue()
        self._polling = False
        self._deliver.connect(self._on_deliver)
        threading.Thread(target=self._run, name="hid-worker", daemon=True).start()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.set_interval(cfg["tray"]["poll_seconds"])

    def set_interval(self, seconds: int) -> None:
        self.timer.start(max(5, int(seconds)) * 1000)

    # --- очередь заданий ----------------------------------------------
    def submit(self, fn, callback=None) -> None:
        self._q.put((fn, callback))

    def _run(self) -> None:
        while True:
            fn, cb = self._q.get()
            try:
                val, err = fn(), None
            except Exception as exc:  # noqa: BLE001
                log.warning("задание %s: %s", getattr(fn, "__name__", fn), exc, exc_info=not isinstance(
                    exc, (HeadsetOffline, HidppError, MouseError, OSError)))
                val, err = None, exc
            if cb is not None:
                self._deliver.emit(cb, val, err)

    def _on_deliver(self, cb, val, err) -> None:
        try:
            cb(val, err)
        except Exception:  # noqa: BLE001
            log.exception("ошибка в обработчике результата")

    # --- опрос ----------------------------------------------------------
    def poll(self) -> None:
        if self._polling:
            return
        self._polling = True
        self.submit(self._poll_job, self._poll_done)

    def _poll_job(self) -> tuple[dict, dict]:
        return self._poll_headset(), self._poll_mouse()

    def _poll_headset(self) -> dict:
        g = self.g733
        try:
            if not g.is_open() and not g.open():
                return {"present": False}
            b = g.battery()
            return {"present": True, "online": True, **b}
        except (HeadsetOffline, HidppError) as exc:
            g.reset_cache()
            return {"present": True, "online": False, "reason": str(exc)}
        except OSError as exc:
            log.info("G733 отключён: %s", exc)
            g.close()
            return {"present": False}

    def _poll_mouse(self) -> dict:
        m = self.mouse
        try:
            if not m.is_open() and not m.open():
                return {"present": False}
            pct = m.battery()
            return {"present": True, "online": pct is not None, "percent": pct, "name": m.name}
        except OSError as exc:
            log.info("AJAZZ отключён: %s", exc)
            m.close()
            return {"present": False}

    def _poll_done(self, val, err) -> None:
        self._polling = False
        if err or val is None:
            return
        hs, ms = val
        was_h = self.headset_state.get("online", False)
        was_m = self.mouse_state.get("present", False)
        self.headset_state, self.mouse_state = hs, ms
        self.headsetChanged.emit(hs)
        self.mouseChanged.emit(ms)
        if hs.get("online") and not was_h:
            self.headsetConnected.emit()
        if ms.get("present") and not was_m:
            self.mouseConnected.emit()
