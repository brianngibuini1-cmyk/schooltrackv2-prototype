"""Runtime configuration for SchoolTrack.

Local development defaults to SQLite. A deployment sets ``DATABASE_URL`` to a
PostgreSQL connection string. Demo behavior is explicit through ``DEMO_MODE``;
nothing secret is ever included in API responses or logs.

Environment variables are documented in README.md and DEPLOYMENT.md.
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = Path(__file__).resolve().parent / "static"
DEFAULT_DB_PATH = BASE_DIR / "data" / "schooltrack.db"

APP_NAME = "SchoolTrack"
SCHOOL_NAME = "Mwangaza Academy"
SCHOOL_SUBTITLE = "Primary & Junior Secondary"

CURRENCY_CODE = "KES"
CURRENCY_SYMBOL = "KSh"
DEMO_WARNING = (
    "Fictional data only. Do not enter real financial, personal or confidential "
    "information."
)

DEFAULT_MAX_REQUEST_BYTES = 256 * 1024
DEFAULT_RATE_LIMIT_WRITES = 30
DEFAULT_RATE_LIMIT_WINDOW_SECONDS = 60

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off", ""}


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    return default


def env_int(name: str, default: int, *, minimum: int = 1) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, value)


def resolve_db_path() -> Path:
    """Return the configured local SQLite path (absolute)."""

    raw = os.environ.get("SCHOOLTRACK_DB", "").strip()
    path = Path(raw).expanduser() if raw else DEFAULT_DB_PATH
    if not path.is_absolute():
        path = (BASE_DIR / path).resolve()
    return path


def demo_mode_enabled() -> bool:
    """Public interactive-demo behavior is opt-in."""

    return env_bool("DEMO_MODE", False)


def demo_writes_enabled(demo_mode_value: bool | None = None) -> bool:
    """Whether visitors may create/approve records.

    Outside demo mode writes are always available (local/owner use). In demo
    mode the default is enabled, but an owner can set
    ``DEMO_WRITES_ENABLED=false`` for a read-only public demo.
    """

    is_demo = demo_mode_enabled() if demo_mode_value is None else demo_mode_value
    if not is_demo:
        return True
    return env_bool("DEMO_WRITES_ENABLED", True)


def seed_demo_enabled() -> bool:
    """Seeding is explicit; startup never silently inserts demo rows.

    ``SCHOOLTRACK_SEED`` remains as a backwards-compatible alias, but the new
    documented setting is ``SEED_DEMO_DATA``. The default is off so a
    production database cannot be populated with demonstration records by
    accident.
    """

    if "SEED_DEMO_DATA" in os.environ:
        return env_bool("SEED_DEMO_DATA", False)
    if "SCHOOLTRACK_SEED" in os.environ:
        return env_bool("SCHOOLTRACK_SEED", False)
    return False


def seed_enabled() -> bool:
    """Backward-compatible alias for older local scripts."""

    return seed_demo_enabled()


def max_request_bytes() -> int:
    return env_int("MAX_REQUEST_BYTES", DEFAULT_MAX_REQUEST_BYTES, minimum=1024)


def rate_limit_writes() -> int:
    return env_int("RATE_LIMIT_WRITES", DEFAULT_RATE_LIMIT_WRITES, minimum=1)


def rate_limit_window_seconds() -> int:
    return env_int(
        "RATE_LIMIT_WINDOW_SECONDS", DEFAULT_RATE_LIMIT_WINDOW_SECONDS, minimum=1
    )


def trust_proxy_headers() -> bool:
    return env_bool("TRUST_PROXY_HEADERS", False)


def allow_demo_reset() -> bool:
    """Owner-controlled CLI reset guard; never exposed as an HTTP endpoint."""

    return env_bool("ALLOW_DEMO_RESET", False)
