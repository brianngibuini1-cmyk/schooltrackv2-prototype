"""Pytest fixtures: every test gets an isolated temporary SQLite database."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "schooltrack-test.db"


@pytest.fixture
def client(db_path: Path):
    app = create_app(db_path=db_path, seed_demo=False)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def seeded_client(tmp_path: Path):
    app = create_app(db_path=tmp_path / "schooltrack-seeded.db", seed_demo=True)
    with TestClient(app) as test_client:
        yield test_client
