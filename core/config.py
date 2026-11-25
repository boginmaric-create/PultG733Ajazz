"""Настройки программы (JSON в %APPDATA%) и автозапуск Windows."""
from __future__ import annotations

import copy
import json
import logging
import os
import sys
from pathlib import Path

log = logging.getLogger("config")

APP_ID = "PultG733Ajazz"
APP_TITLE = "Пульт G733 + AJAZZ"

DEFAULTS: dict = {
    "tray": {
        "show_headset": True,
        "show_mouse": True,
        "style": "glyph_number",     # glyph_number | number | glyph_bar
        "low_threshold": 20,
        "notify_low": True,
        "poll_seconds": 30,
    },
    "autostart": False,
    "start_hidden": True,
    "close_to_tray": True,
    "headset": {
        "apply_on_connect": True,
        "sidetone": None,
        "lighting": None,            # {"zone", "effect", "color", "brightness", "speed"}
        "eq_gains": None,
        "eq_preset": "Ровный",
    },
    "mouse": {"sync_clock": True},
}


def data_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    p = Path(base) / APP_ID
    p.mkdir(parents=True, exist_ok=True)
    return p


def _merge(dst: dict, src: dict) -> dict:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _merge(dst[k], v)
        else:
            dst[k] = v
    return dst


class Config:
    def __init__(self) -> None:
        self.path = data_dir() / "config.json"
        self.data = copy.deepcopy(DEFAULTS)
        try:
            if self.path.exists():
                _merge(self.data, json.loads(self.path.read_text(encoding="utf-8")))
        except Exception as exc:
            log.warning("config.json повреждён, использую настройки по умолчанию: %s", exc)

    def __getitem__(self, key):
        return self.data[key]

    def save(self) -> None:
        try:
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self.path)
        except Exception as exc:
            log.error("не удалось сохранить настройки: %s", exc)


# --- автозапуск ---------------------------------------------------------
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def launch_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --tray'
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe")
    main = Path(__file__).resolve().parent.parent / "main.py"
    return f'"{pyw if pyw.exists() else exe}" "{main}" --tray'


def set_autostart(enabled: bool) -> bool:
    if sys.platform != "win32":
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            if enabled:
                winreg.SetValueEx(k, APP_ID, 0, winreg.REG_SZ, launch_command())
            else:
                try:
                    winreg.DeleteValue(k, APP_ID)
                except FileNotFoundError:
                    pass
        return True
    except OSError as exc:
        log.error("автозапуск: %s", exc)
        return False
