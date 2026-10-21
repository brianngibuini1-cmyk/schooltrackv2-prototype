"""SQLite connection behaviour used by FastAPI's worker threads."""

from __future__ import annotations

from pathlib import Path
from threading import Thread

from app.db import connect, init_db


def test_request_connection_can_be_used_by_a_different_worker_thread(tmp_path: Path):
    db_path = tmp_path / "threads.db"
    init_db(db_path)
    conn = connect(db_path)
    result: dict[str, int] = {}

    def worker() -> None:
        result["value"] = conn.execute("SELECT 1 AS value").fetchone()["value"]

    try:
        thread = Thread(target=worker)
        thread.start()
        thread.join(timeout=5)
        assert result["value"] == 1
    finally:
        conn.close()


def test_foreign_keys_are_enforced(tmp_path: Path):
    db_path = tmp_path / "foreign-keys.db"
    init_db(db_path)
    conn = connect(db_path)
    try:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        conn.close()
