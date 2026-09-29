"""Application configuration.

Precedence (docs/06 §11): built-in defaults < config file (APP_DATA_DIR/config.toml) < environment variables.
Secrets are never stored in the general configuration file; the portable encryption key lives in
APP_DATA_DIR/secrets/.
"""
from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass, field, fields, replace
from pathlib import Path

APP_NAME = "FinancialManagementPOC"
VERSION = "1.2.0"


def default_data_dir() -> Path:
    """OS-appropriate default application-data directory (separate from binaries, BR-086)."""
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "financial-management-poc"


@dataclass(frozen=True)
class Settings:
    data_dir: Path = field(default_factory=default_data_dir)
    mode: str = "local"  # local | server
    host: str = "127.0.0.1"
    port: int = 8765
    open_browser: bool = True
    # Cookie "Secure" flag: auto = enabled when the request arrived over HTTPS
    secure_cookies: str = "auto"  # auto | true | false
    hsts: bool = False
    # Comma separated list of proxy IPs whose X-Forwarded-* headers are trusted ("" = none)
    trusted_proxies: str = ""
    session_idle_minutes: int = 30
    session_absolute_hours: int = 12
    login_max_failures: int = 5
    login_lockout_seconds: int = 900
    log_level: str = "INFO"
    debug: bool = False  # never enabled in packaged builds
    frontend_dir: Path | None = None

    @property
    def database_dir(self) -> Path:
        return self.data_dir / "database"

    @property
    def database_path(self) -> Path:
        return self.database_dir / "fmpoc.sqlite3"

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.database_path.as_posix()}"

    @property
    def attachments_dir(self) -> Path:
        return self.data_dir / "attachments"

    @property
    def secrets_dir(self) -> Path:
        return self.data_dir / "secrets"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.database_dir, self.attachments_dir, self.secrets_dir, self.logs_dir):
            d.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.secrets_dir, 0o700)
        except OSError:  # pragma: no cover - platform dependent (Windows ACLs)
            pass


_BOOL_TRUE = {"1", "true", "yes", "on"}
_ENV_PREFIX = "FM_"


def _coerce(name: str, value, current):
    target = type(current) if current is not None else str
    if name == "data_dir" or name == "frontend_dir":
        return Path(str(value)) if value not in (None, "") else None
    if target is bool:
        return value if isinstance(value, bool) else str(value).strip().lower() in _BOOL_TRUE
    if target is int:
        return int(value)
    return str(value)


def load_settings(overrides: dict | None = None) -> Settings:
    """Build settings from defaults, config file and environment (then explicit overrides e.g. CLI)."""
    s = Settings()
    env_data_dir = os.environ.get(_ENV_PREFIX + "DATA_DIR")
    data_dir = Path((overrides or {}).get("data_dir") or env_data_dir or s.data_dir)
    s = replace(s, data_dir=data_dir)
    values: dict = {}
    cfg = data_dir / "config.toml"
    if cfg.is_file():
        with cfg.open("rb") as fh:
            values.update(tomllib.load(fh).get("server", {}) or {})
    names = {f.name for f in fields(Settings)}
    for n in names:
        env = os.environ.get(_ENV_PREFIX + n.upper())
        if env is not None:
            values[n] = env
    for k, v in (overrides or {}).items():
        if v is not None:
            values[k] = v
    clean = {}
    for k, v in values.items():
        if k in names and k != "data_dir":
            clean[k] = _coerce(k, v, getattr(s, k))
    s = replace(s, **clean)
    if s.mode not in ("local", "server"):
        raise ValueError("mode must be 'local' or 'server'")
    if s.mode == "local" and "host" not in values:
        s = replace(s, host="127.0.0.1")
    return s


def is_loopback(host: str) -> bool:
    return host in ("127.0.0.1", "::1", "localhost") or host.startswith("127.")
