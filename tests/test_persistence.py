"""Persistence across restarts and safe, idempotent demo seeding."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.db import init_db
from app.main import create_app
from app.seed import PURCHASES, SUPPLIERS
from tests.helpers import create_purchase, create_supplier


def test_records_survive_an_application_restart(tmp_path: Path):
    db_path = tmp_path / "restart.db"

    first_app = create_app(db_path=db_path, seed_demo=False)
    with TestClient(first_app) as first_client:
        supplier = create_supplier(first_client, "Persistent Supplier")
        purchase = create_purchase(
            first_client,
            supplier["id"],
            items=[
                {"description": "Permanent marker", "quantity": 12, "unit_cost": "250.00"}
            ],
        )
        first_reference = purchase["reference"]
        first_total = purchase["total_cents"]

    assert db_path.exists()

    second_app = create_app(db_path=db_path, seed_demo=False)
    with TestClient(second_app) as second_client:
        fetched = second_client.get(f"/api/purchases/{purchase['id']}")
        assert fetched.status_code == 200
        body = fetched.json()
        assert body["reference"] == first_reference
        assert body["total_cents"] == first_total == 300_000
        assert body["items"][0]["description"] == "Permanent marker"

        listing = second_client.get("/api/purchases").json()
        assert listing["total"] == 1

        supplier_check = second_client.get(f"/api/suppliers/{supplier['id']}").json()
        assert supplier_check["name"] == "Persistent Supplier"
        assert supplier_check["history_total"] == 1


def test_demo_seed_is_idempotent_and_labelled(tmp_path: Path):
    db_path = tmp_path / "demo.db"
    app = create_app(db_path=db_path, seed_demo=True)

    with TestClient(app) as client:
        meta = client.get("/api/meta").json()
        assert meta["demo_purchase_count"] == len(PURCHASES)

        purchases = client.get("/api/purchases?per_page=100").json()
        assert purchases["total"] == len(PURCHASES)
        assert all(item["is_demo"] is True for item in purchases["items"])
        assert all(item["invoice_number"].startswith("DEMO-") for item in purchases["items"])

        suppliers = client.get("/api/suppliers").json()
        assert suppliers["total"] == len(SUPPLIERS)
        assert all(item["is_demo"] is True for item in suppliers["items"])

        dashboard = client.get("/api/dashboard").json()
        assert dashboard["demo_purchase_count"] == len(PURCHASES)
        assert dashboard["record_count"] + dashboard["rejected_count"] == len(PURCHASES)

    restarted = create_app(db_path=db_path, seed_demo=True)
    with TestClient(restarted) as client:
        assert client.get("/api/meta").json()["demo_purchase_count"] == len(PURCHASES)
        assert client.get("/api/purchases?per_page=100").json()["total"] == len(PURCHASES)
        assert client.get("/api/suppliers").json()["total"] == len(SUPPLIERS)


def test_demo_seed_never_overwrites_existing_records(tmp_path: Path):
    db_path = tmp_path / "mixed.db"
    app = create_app(db_path=db_path, seed_demo=False)
    with TestClient(app) as client:
        supplier = create_supplier(client, "Real Test Supplier")
        create_purchase(client, supplier["id"], invoice_number="REAL-001")

    reopened = create_app(db_path=db_path, seed_demo=True)
    with TestClient(reopened) as client:
        meta = client.get("/api/meta").json()
        assert meta["demo_purchase_count"] == 0
        assert client.get("/api/purchases").json()["total"] == 1
        assert client.get("/api/suppliers").json()["total"] == 1


def test_init_db_can_run_repeatedly(db_path: Path):
    init_db(db_path)
    init_db(db_path)
    init_db(db_path)
    assert db_path.exists()


def test_demo_data_is_fictional_and_dated_in_the_past(seeded_client):
    purchases = seeded_client.get("/api/purchases?per_page=100").json()["items"]
    assert purchases
    assert all(item["is_demo"] for item in purchases)
    # The seed uses relative dates so the demonstration is always current.
    assert all(item["purchase_date"] <= seeded_client.get("/api/meta").json()["today"] for item in purchases)
