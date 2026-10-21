"""Owner-only database commands; no HTTP reset endpoint exists."""

from __future__ import annotations

from pathlib import Path

from app import manage
from app.db import connect, init_db
from app.seed import PURCHASES, seed_demo_data


def _purchase_count(db_path: Path) -> int:
    conn = connect(db_path)
    try:
        return int(conn.execute("SELECT COUNT(*) AS n FROM purchases").fetchone()["n"])
    finally:
        conn.close()


def test_reset_demo_requires_explicit_owner_guards(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "manage.db"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("SCHOOLTRACK_DB", str(db_path))
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.delenv("ALLOW_DEMO_RESET", raising=False)

    init_db(db_path)
    seed_demo_data(db_path)
    before = _purchase_count(db_path)
    assert before == len(PURCHASES)

    assert manage.main(["reset-demo", "--yes"]) == 2
    assert _purchase_count(db_path) == before

    monkeypatch.setenv("ALLOW_DEMO_RESET", "true")
    assert manage.main(["reset-demo", "--yes"]) == 0
    assert _purchase_count(db_path) == len(PURCHASES)


def test_reset_demo_refuses_without_confirmation(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "manage-no-confirm.db"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("SCHOOLTRACK_DB", str(db_path))
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("ALLOW_DEMO_RESET", "true")
    init_db(db_path)
    seed_demo_data(db_path)

    assert manage.main(["reset-demo"]) == 2
    assert _purchase_count(db_path) == len(PURCHASES)


def test_there_is_no_public_reset_endpoint(client):
    assert client.post("/api/reset-demo").status_code == 404
    assert client.post("/api/admin/reset").status_code == 404
