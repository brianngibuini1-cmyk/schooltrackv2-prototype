"""Database backend abstraction for SQLite and PostgreSQL.

The application uses one small connection wrapper so the business layer can
keep portable SQL with ``?`` placeholders. SQLite connections are local files;
PostgreSQL connections are created from ``DATABASE_URL``. No credentials are
ever logged by this module.

Schema changes are additive and tracked in ``schema_migrations``. The same
migration list runs on both backends, with only the primary-key and index
syntax varying where the engines genuinely differ.
"""

from __future__ import annotations

import os
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Sequence
from urllib.parse import unquote

try:  # PostgreSQL is optional for local SQLite-only use.
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover - exercised when psycopg is not installed
    psycopg = None
    dict_row = None

SCHEMA_VERSION = 2

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class DatabaseConfigError(RuntimeError):
    """The configured database URL or backend is not usable."""


class DatabaseUnavailable(RuntimeError):
    """The configured database could not be reached or queried."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def translate_placeholders(sql: str) -> str:
    """Translate qmark placeholders to psycopg's ``%s`` form.

    A small parser skips single-quoted SQL strings so a literal question mark
    inside a string can never be mistaken for a bind parameter.
    """

    if "?" not in sql:
        return sql
    output: list[str] = []
    in_string = False
    index = 0
    while index < len(sql):
        character = sql[index]
        if character == "'":
            if in_string and index + 1 < len(sql) and sql[index + 1] == "'":
                output.append("''")
                index += 2
                continue
            in_string = not in_string
            output.append(character)
        elif character == "?" and not in_string:
            output.append("%s")
        else:
            output.append(character)
        index += 1
    return "".join(output)


@dataclass(frozen=True)
class Database:
    """A configured database backend.

    ``url`` is never included in ``repr`` so accidental logging cannot expose
    a PostgreSQL password.
    """

    backend: str
    sqlite_path: Path | None = None
    url: str | None = None

    @classmethod
    def sqlite(cls, path: str | Path) -> "Database":
        return cls(backend="sqlite", sqlite_path=Path(path).expanduser())

    @classmethod
    def from_url(cls, url: str) -> "Database":
        raw = (url or "").strip()
        if not raw:
            raise DatabaseConfigError("DATABASE_URL is empty.")
        if raw.startswith("sqlite:///"):
            path = raw[len("sqlite:///") :]
            # Windows absolute paths arrive as sqlite:///C:/...
            if re.match(r"^/[A-Za-z]:", path):
                path = path[1:]
            return cls.sqlite(Path(unquote(path)))
        if raw.startswith("postgres://"):
            raw = "postgresql://" + raw[len("postgres://") :]
        if raw.startswith("postgresql+psycopg://"):
            raw = "postgresql://" + raw[len("postgresql+psycopg://") :]
        if not raw.startswith("postgresql://"):
            raise DatabaseConfigError(
                "DATABASE_URL must start with postgresql://, postgres:// or sqlite:///."
            )
        return cls(backend="postgresql", url=raw)

    @property
    def is_sqlite(self) -> bool:
        return self.backend == "sqlite"

    @property
    def label(self) -> str:
        return "SQLite" if self.is_sqlite else "PostgreSQL"

    def __repr__(self) -> str:  # noqa: D401 - intentionally redacted
        if self.is_sqlite:
            return f"Database(backend='sqlite', path={str(self.sqlite_path)!r})"
        return "Database(backend='postgresql', url='<redacted>')"

    def connect(self) -> "Connection":
        if self.is_sqlite:
            assert self.sqlite_path is not None
            path = self.sqlite_path
            path.parent.mkdir(parents=True, exist_ok=True)
            raw = sqlite3.connect(
                str(path),
                timeout=15.0,
                isolation_level=None,
                check_same_thread=False,
            )
            raw.row_factory = sqlite3.Row
            raw.execute("PRAGMA foreign_keys = ON")
            raw.execute("PRAGMA journal_mode = WAL")
            raw.execute("PRAGMA synchronous = NORMAL")
            raw.execute("PRAGMA busy_timeout = 15000")
            return Connection(raw, self)

        if psycopg is None:  # pragma: no cover - depends on deployment install
            raise DatabaseConfigError(
                "PostgreSQL support requires psycopg. Install requirements.txt."
            )
        try:
            raw = psycopg.connect(
                self.url,
                autocommit=True,
                row_factory=dict_row,
                connect_timeout=10,
            )
        except Exception as exc:  # noqa: BLE001 - normalized without credentials
            raise DatabaseUnavailable(
                "The PostgreSQL database could not be reached."
            ) from exc
        return Connection(raw, self)

    def ping(self) -> None:
        conn = self.connect()
        try:
            conn.execute("SELECT 1 AS ok").fetchone()
        except Exception as exc:  # noqa: BLE001
            raise DatabaseUnavailable("The database readiness check failed.") from exc
        finally:
            conn.close()

    def init_schema(self) -> None:
        init_db(self)


class Connection:
    """A request-scoped database connection.

    PostgreSQL exceptions are passed through so callers can inspect uniqueness;
    the shared :func:`transaction` helper always rolls back on failure.
    """

    def __init__(self, raw: Any, database: Database) -> None:
        self.raw = raw
        self.database = database

    @property
    def backend(self) -> str:
        return self.database.backend

    def _prepare(self, sql: str) -> str:
        return translate_placeholders(sql) if self.backend == "postgresql" else sql

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> Any:
        statement = self._prepare(sql)
        if params is None:
            return self.raw.execute(statement)
        return self.raw.execute(statement, tuple(params))

    def executemany(self, sql: str, params_seq: Sequence[Sequence[Any]]) -> Any:
        statement = self._prepare(sql)
        if self.backend == "postgresql":
            cursor = self.raw.cursor()
            return cursor.executemany(statement, params_seq)
        return self.raw.executemany(statement, params_seq)

    def close(self) -> None:
        self.raw.close()

    def commit(self) -> None:
        self.raw.commit()

    def rollback(self) -> None:
        self.raw.rollback()


def database_from_env() -> Database:
    """Resolve ``DATABASE_URL`` first, then the local SQLite path."""

    from .config import resolve_db_path

    raw_url = os.environ.get("DATABASE_URL", "").strip()
    if raw_url:
        return Database.from_url(raw_url)
    return Database.sqlite(resolve_db_path())


def as_database(target: Database | str | Path) -> Database:
    if isinstance(target, Database):
        return target
    return Database.sqlite(target)


def connect(db_path: str | Path) -> Connection:
    """Open a SQLite connection with the settings used by the application."""

    return Database.sqlite(db_path).connect()


def _identity(backend: str) -> str:
    if backend == "sqlite":
        return "INTEGER PRIMARY KEY AUTOINCREMENT"
    return "INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY"


def _migration_1(backend: str) -> list[str]:
    identity = _identity(backend)
    return [
        f"""
        CREATE TABLE IF NOT EXISTS suppliers (
            id              {identity},
            name            TEXT    NOT NULL,
            contact_person  TEXT    NOT NULL DEFAULT '',
            phone           TEXT    NOT NULL DEFAULT '',
            email           TEXT    NOT NULL DEFAULT '',
            address         TEXT    NOT NULL DEFAULT '',
            notes           TEXT    NOT NULL DEFAULT '',
            is_demo         INTEGER NOT NULL DEFAULT 0 CHECK (is_demo IN (0, 1)),
            created_at      TEXT    NOT NULL
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS purchases (
            id              {identity},
            reference       TEXT    NOT NULL UNIQUE,
            purchase_date   TEXT    NOT NULL,
            supplier_id     INTEGER NOT NULL REFERENCES suppliers(id) ON DELETE RESTRICT,
            category        TEXT    NOT NULL CHECK (category IN ('primary', 'jss')),
            payment_method  TEXT    NOT NULL CHECK (payment_method IN
                                ('cash', 'mpesa', 'bank_transfer', 'cheque', 'other')),
            invoice_number  TEXT,
            status          TEXT    NOT NULL DEFAULT 'pending'
                                CHECK (status IN ('pending', 'approved', 'rejected')),
            notes           TEXT    NOT NULL DEFAULT '',
            subtotal_cents  INTEGER NOT NULL CHECK (subtotal_cents >= 0),
            total_cents     INTEGER NOT NULL CHECK (total_cents >= 0),
            is_demo         INTEGER NOT NULL DEFAULT 0 CHECK (is_demo IN (0, 1)),
            created_at      TEXT    NOT NULL,
            updated_at      TEXT    NOT NULL,
            decision_at     TEXT
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS purchase_items (
            id                {identity},
            purchase_id       INTEGER NOT NULL REFERENCES purchases(id) ON DELETE CASCADE,
            description       TEXT    NOT NULL,
            quantity          INTEGER NOT NULL CHECK (quantity > 0),
            unit_cost_cents   INTEGER NOT NULL CHECK (unit_cost_cents >= 0),
            line_total_cents  INTEGER NOT NULL CHECK (line_total_cents >= 0),
            position          INTEGER NOT NULL
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_purchases_date ON purchases(purchase_date)",
        "CREATE INDEX IF NOT EXISTS idx_purchases_category ON purchases(category)",
        "CREATE INDEX IF NOT EXISTS idx_purchases_status ON purchases(status)",
        "CREATE INDEX IF NOT EXISTS idx_purchases_supplier ON purchases(supplier_id)",
        "CREATE INDEX IF NOT EXISTS idx_items_purchase ON purchase_items(purchase_id)",
    ]


def _migration_2(backend: str) -> list[str]:
    # A lower(name) unique index gives PostgreSQL and SQLite the same
    # case-insensitive supplier-duplicate rule.
    return [
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_suppliers_name_lower "
        "ON suppliers (LOWER(name))"
    ]


MIGRATIONS = {
    1: _migration_1,
    2: _migration_2,
}


def migration_statements(version: int, backend: str) -> list[str]:
    """Expose migration SQL for tests and documentation."""
    return MIGRATIONS[version](backend)


def init_db(target: Database | str | Path) -> None:
    """Create or upgrade the schema without deleting existing data."""

    database = as_database(target)
    conn = database.connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version    INTEGER PRIMARY KEY,
                applied_at TEXT    NOT NULL
            )
            """
        )
        applied = {
            int(row["version"])
            for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
        }
        for version in sorted(MIGRATIONS):
            if version in applied:
                continue
            with transaction(conn):
                for statement in migration_statements(version, database.backend):
                    conn.execute(statement)
                conn.execute(
                    "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                    (version, _utc_now()),
                )
        if database.is_sqlite:
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    finally:
        conn.close()


def is_empty(target: Database | str | Path) -> bool:
    """True when a database has no suppliers and no purchases."""

    database = as_database(target)
    conn = database.connect()
    try:
        suppliers = conn.execute(
            "SELECT COUNT(*) AS n FROM suppliers"
        ).fetchone()["n"]
        purchases = conn.execute(
            "SELECT COUNT(*) AS n FROM purchases"
        ).fetchone()["n"]
        return int(suppliers) == 0 and int(purchases) == 0
    finally:
        conn.close()


@contextmanager
def transaction(conn: Connection) -> Iterator[Connection]:
    """Write transaction with rollback on any failure.

    SQLite takes the write lock immediately. PostgreSQL uses a normal explicit
    transaction on an autocommit connection. Both paths keep purchase rows and
    line items atomic.
    """

    begin = "BEGIN IMMEDIATE" if conn.backend == "sqlite" else "BEGIN"
    conn.execute(begin)
    try:
        yield conn
    except BaseException:
        try:
            conn.execute("ROLLBACK")
        except Exception:  # pragma: no cover - preserve the original failure
            pass
        raise
    else:
        conn.execute("COMMIT")


def is_unique_violation(exc: BaseException) -> bool:
    """Recognize duplicate-key errors from either driver."""

    if isinstance(exc, sqlite3.IntegrityError):
        return "UNIQUE" in str(exc).upper()
    if psycopg is not None:
        try:
            if isinstance(exc, psycopg.errors.UniqueViolation):
                return True
        except AttributeError:  # pragma: no cover - very old psycopg
            return False
    return False
