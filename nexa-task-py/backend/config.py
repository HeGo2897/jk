"""Reads config.ini.

Any value can be overridden with an environment variable named NEXA_<SECTION>_<KEY>,
for example  mysql.password  ->  NEXA_MYSQL_PASSWORD  (so the password need not be stored in a file).
"""
from __future__ import annotations

import configparser
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    def __init__(self, path: str | Path | None = None, overrides: dict | None = None):
        self._parser = configparser.ConfigParser(interpolation=None)
        file = Path(path) if path else BASE_DIR / "config.ini"
        if file.exists():
            self._parser.read(file, encoding="utf-8")
        self._overrides = overrides or {}          # {(section, key): value}  - used by the tests

    def get(self, section: str, key: str, default: str = "") -> str:
        if (section, key) in self._overrides:
            return str(self._overrides[(section, key)]).strip()
        env = os.environ.get(f"NEXA_{section}_{key}".upper())
        if env:
            return env.strip()
        return self._parser.get(section, key, fallback=default).strip()

    def get_int(self, section: str, key: str, default: int) -> int:
        try:
            return int(self.get(section, key, str(default)))
        except ValueError:
            return default

    def get_bool(self, section: str, key: str, default: bool) -> bool:
        return self.get(section, key, str(default)).lower() in ("1", "true", "yes", "on")

    def get_path(self, section: str, key: str, default: str) -> Path:
        """A path from the config; relative paths are resolved against the backend folder."""
        p = Path(self.get(section, key, default))
        return p if p.is_absolute() else (BASE_DIR / p).resolve()
