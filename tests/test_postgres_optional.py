"""Optional real-PostgreSQL integration test.

Run only against a disposable database:

    $env:TEST_DATABASE_URL = "postgresql://.../schooltrack_test?sslmode=require"
    python -m pytest -m postgresql

This test is skipped in the normal suite and never runs against a production
database unless the operator explicitly supplies that URL.
"""

from __future__ import annotations

import os
import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.helpers import create_purchase, create_supplier

pytestmark = [
    pytest.mark.postgresql,
    pytest.mark.skipif(
        not os.environ.get("TEST_DATABASE_URL"),
        reason="TEST_DATABASE_URL is not set; PostgreSQL integration is optional.",
    ),
]


def test_postgres_purchase_filters_reports_and_csv():
    url = os.environ["TEST_DATABASE_URL"]
    suffix = uuid.uuid4().hex[:10]
    app = create_app(database_url=url, seed_demo=False, demo_mode=False)

    with TestClient(app) as client:
        supplier = create_supplier(client, f"Postgres Supplier {suffix}")
        purchase = create_purchase(
            client,
            supplier["id"],
            purchase_date=date.today(),
            category="jss",
            status="pending",
            items=[
                {"description": "Postgres item one", "quantity": 3, "unit_cost": "19.99"},
                {"description": "Postgres item two", "quantity": 2, "unit_cost": "100.00"},
            ],
        )
        assert purchase["total_cents"] == 3 * 1999 + 2 * 10000
        assert purchase["reference"].startswith("ST-")

        filtered = client.get("/api/purchases?category=jss&search=Postgres").json()
        assert filtered["total"] >= 1
        assert any(item["id"] == purchase["id"] for item in filtered["items"])

        approved = client.patch(
            f"/api/purchases/{purchase['id']}/status", json={"status": "approved"}
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"

        report = client.get(f"/api/reports?from={date.today().isoformat()}&to={date.today().isoformat()}&category=jss").json()
        assert report["record_count"] >= 1
        assert report["total_cents"] >= purchase["total_cents"]

        csv_response = client.get("/api/purchases/export.csv?category=jss")
        assert csv_response.status_code == 200
        assert "Postgres item one" in csv_response.text

        supplier_detail = client.get(f"/api/suppliers/{supplier['id']}").json()
        assert supplier_detail["history_total"] >= 1

    # Reopening the app against the same database proves initialization is
    # repeatable and the row persisted.
    with TestClient(create_app(database_url=url, seed_demo=False, demo_mode=False)) as client:
        assert client.get(f"/api/purchases/{purchase['id']}").status_code == 200
