"""Тонкая обёртка над hidapi с журналированием каждого обмена.

Весь обмен с устройствами идёт через этот модуль, чтобы в журнал
(и в отчёт диагностики) попадали сырые байты — по ним можно понять,
что ответило устройство, если что-то пойдёт не так.
"""
from __future__ import annotations

import logging

log = logging.getLogger("hid")

try:  # пакет «hidapi» (cython-hidapi) даёт модуль «hid»
    import hid  # type: ignore
except Exception:  # pragma: no cover - на машине без hidapi
    hid = None


def hx(data, limit: int = 64) -> str:
    data = bytes(data)
    s = " ".join(f"{b:02x}" for b in data[:limit])
    return s + (" …" if len(data) > limit else "")


def hid_available() -> bool:
    return hid is not None


def enumerate_devices(vid: int, pid: int = 0) -> list[dict]:
    if hid is None:
        return []
    try:
        return list(hid.enumerate(vid, pid))
    except Exception as exc:  # pragma: no cover
        log.warning("enumerate(%04x:%04x) не удалось: %s", vid, pid, exc)
        return []


class HidHandle:
    """Открытая HID-коллекция (один «путь» устройства)."""

    def __init__(self, info: dict, tag: str):
        if hid is None:
            raise OSError("Модуль hidapi не установлен")
        self.info = info
        self.tag = tag
        self.dev = hid.device()
        self.dev.open_path(info["path"])
        log.info("[%s] открыто: %s", tag, info.get("path"))

    def close(self) -> None:
        try:
            self.dev.close()
        except Exception:
            pass

    # --- обычные (interrupt) отчёты -------------------------------------
    def write(self, data) -> None:
        data = bytes(data)
        log.debug("[%s] OUT  %s", self.tag, hx(data))
        n = self.dev.write(data)
        if n is None or n < 0:
            raise OSError(f"Запись в устройство не удалась ({self.tag})")

    def read(self, size: int, timeout_ms: int) -> bytes:
        r = bytes(self.dev.read(size, timeout_ms) or b"")
        if r:
            log.debug("[%s] IN   %s", self.tag, hx(r))
        return r

    # --- feature-отчёты --------------------------------------------------
    def send_feature(self, data) -> None:
        data = bytes(data)
        log.debug("[%s] SETF %s", self.tag, hx(data))
        n = self.dev.send_feature_report(data)
        if n is None or n < 0:
            raise OSError(f"SET_FEATURE не удался ({self.tag})")

    def get_feature(self, report_id: int, size: int) -> bytes:
        r = bytes(self.dev.get_feature_report(report_id, size) or b"")
        log.debug("[%s] GETF %s", self.tag, hx(r))
        return r
