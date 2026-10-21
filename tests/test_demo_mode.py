"""Public-demo restrictions, health response and safe failure behavior."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.db import init_db
from app.main import create_app
from app.security import SlidingWindowRateLimiter
from app.seed import PURCHASES, seed_demo_data
from tests.helpers import purchase_payload, supplier_payload


def demo_client(tmp_path: Path, **overrides):
    options = {
        "demo_mode": True,
        "writes_enabled": True,
        "request_limit_bytes": 4096,
        "write_rate_limit": 100,
        "write_rate_window": 60,
        "seed_demo": False,
    }
    options.update(overrides)
    app = create_app(db_path=tmp_path / "demo.db", **options)
    return app, TestClient(app)


def test_demo_meta_and_health_are_explicit(tmp_path: Path):
    app, client = demo_client(tmp_path)
    with client:
        meta = client.get("/api/meta").json()
        assert meta["demo_mode"] is True
        assert meta["writes_enabled"] is True
        assert meta["currency"] == "KES"
        assert meta["currency_symbol"] == "KSh"
        assert "Do not enter real financial" in meta["demo_warning"]
        assert meta["storage_backend"] == "sqlite"

        health = client.get("/api/health")
        assert health.status_code == 200
        body = health.json()
        assert body["status"] == "ok"
        assert body["ready"] is True
        assert body["database"] == "sqlite"
        assert body["demo_mode"] is True
        assert "sqlite_path" not in body
        assert "DATABASE_URL" not in health.text
        assert "postgresql://" not in health.text


def test_read_only_demo_blocks_all_write_methods(tmp_path: Path):
    app, client = demo_client(tmp_path, writes_enabled=False)
    with client:
        meta = client.get("/api/meta").json()
        assert meta["writes_enabled"] is False

        assert client.get("/api/purchases").status_code == 200
        assert client.post("/api/suppliers", json=supplier_payload()).status_code == 403
        assert client.post("/api/purchases", json=purchase_payload(1)).status_code == 403
        assert client.patch("/api/purchases/1/status", json={"status": "approved"}).status_code == 403

        blocked = client.post("/api/suppliers", json=supplier_payload())
        message = blocked.json()["error"]["message"]
        assert "read-only" in message.lower()
        assert blocked.headers["x-frame-options"] == "DENY"
        assert "default-src 'self'" in blocked.headers["content-security-policy"]
        assert client.get("/api/suppliers").json()["total"] == 0


def test_demo_writes_are_flagged_as_fictional(tmp_path: Path):
    from tests.helpers import create_purchase, create_supplier

    app, client = demo_client(tmp_path)
    with client:
        supplier = create_supplier(client, "Fictional Demo Supplier")
        purchase = create_purchase(client, supplier["id"], status="pending")
        assert supplier["is_demo"] is True
        assert purchase["is_demo"] is True

        csv_response = client.get("/api/purchases/export.csv?search=Fictional")
        assert "Yes" in csv_response.text.splitlines()[-1]
        assert client.get("/api/meta").json()["demo_purchase_count"] == 1


def test_rate_limit_applies_to_public_writes(tmp_path: Path):
    app, client = demo_client(tmp_path, write_rate_limit=2)
    with client:
        first = client.post("/api/suppliers", json=supplier_payload("Rate Limit One"))
        second = client.post("/api/suppliers", json=supplier_payload("Rate Limit Two"))
        third = client.post("/api/suppliers", json=supplier_payload("Rate Limit Three"))

        assert first.status_code == 201
        assert second.status_code == 201
        assert third.status_code == 429
        assert int(third.headers["Retry-After"]) >= 1
        assert "Too many changes" in third.json()["error"]["message"]
        assert third.headers["x-frame-options"] == "DENY"


def test_rate_limiter_is_sliding_and_resets(tmp_path: Path):
    clock = {"now": 0.0}
    limiter = SlidingWindowRateLimiter(2, 10, clock=lambda: clock["now"])
    assert limiter.check("a")[0] is True
    assert limiter.check("a")[0] is True
    allowed, retry = limiter.check("a")
    assert allowed is False and retry == 10
    clock["now"] = 11
    assert limiter.check("a")[0] is True
    limiter.reset()
    assert limiter.check("a")[0] is True


def test_oversized_request_is_rejected_without_detail(tmp_path: Path):
    app, client = demo_client(tmp_path, request_limit_bytes=2048)
    with client:
        response = client.post(
            "/api/suppliers",
            content=b"{" + b"x" * 5000 + b"}",
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 413
        assert response.json()["error"]["message"]
        assert "Traceback" not in response.text
        assert response.headers["x-frame-options"] == "DENY"


def test_unhandled_errors_do_not_leak_internal_details(tmp_path: Path, monkeypatch):
    def explode(*_args, **_kwargs):
        raise RuntimeError("database password is super-secret")

    monkeypatch.setattr(main_module, "dashboard", explode)
    app = create_app(db_path=tmp_path / "errors.db", seed_demo=False)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/dashboard")
    assert response.status_code == 500
    assert "super-secret" not in response.text
    assert "Traceback" not in response.text
    assert "database password" not in response.text
    assert response.json()["error"]["message"] == (
        "Something went wrong on the server. Please try again."
    )


def test_startup_does_not_seed_unless_explicit(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("SEED_DEMO_DATA", raising=False)
    monkeypatch.delenv("SCHOOLTRACK_SEED", raising=False)
    app = create_app(db_path=tmp_path / "empty.db", demo_mode=True, seed_demo=None)
    with TestClient(app) as client:
        assert client.get("/api/purchases").json()["total"] == 0
        assert client.get("/api/meta").json()["demo_purchase_count"] == 0

    summary = seed_demo_data(tmp_path / "empty.db")
    assert summary["seeded"] is True
    assert summary["purchases"] == len(PURCHASES)

    with TestClient(create_app(db_path=tmp_path / "empty.db", demo_mode=True, seed_demo=False)) as client:
        assert client.get("/api/purchases?per_page=100").json()["total"] == len(PURCHASES)


def test_demo_mode_can_be_configured_via_environment(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DEMO_WRITES_ENABLED", "false")
    app = create_app(db_path=tmp_path / "env-demo.db", seed_demo=False)
    with TestClient(app) as client:
        meta = client.get("/api/meta").json()
        assert meta["demo_mode"] is True
        assert meta["writes_enabled"] is False


def test_database_schema_initialisation_does_not_seed(tmp_path: Path):
    db_path = tmp_path / "schema-only.db"
    init_db(db_path)
    from app.db import connect

    conn = connect(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) AS n FROM purchases").fetchone()["n"] == 0
        assert conn.execute("SELECT COUNT(*) AS n FROM suppliers").fetchone()["n"] == 0
    finally:
        conn.close()
