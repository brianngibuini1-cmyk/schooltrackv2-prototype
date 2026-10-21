"""Expenditure report grouping, scopes and date boundaries."""

from __future__ import annotations

from datetime import date

import pytest

from tests.helpers import create_purchase, create_supplier, days_ago


@pytest.fixture
def report_world(client):
    alpha = create_supplier(client, "Alpha School Supplies")
    baraka = create_supplier(client, "Baraka Stationers")

    create_purchase(
        client,
        alpha["id"],
        purchase_date=days_ago(40),
        category="primary",
        status="approved",
        payment_method="cash",
        items=[{"description": "Exercise books", "quantity": 100, "unit_cost": "45.00"}],
    )
    create_purchase(
        client,
        alpha["id"],
        purchase_date=days_ago(20),
        category="jss",
        status="approved",
        payment_method="bank_transfer",
        items=[{"description": "Science beakers", "quantity": 10, "unit_cost": "350.00"}],
    )
    pending = create_purchase(
        client,
        baraka["id"],
        purchase_date=days_ago(5),
        category="primary",
        status="pending",
        payment_method="mpesa",
        items=[{"description": "Printer toner", "quantity": 2, "unit_cost": "6500.00"}],
    )
    rejected = create_purchase(
        client,
        baraka["id"],
        purchase_date=days_ago(60),
        category="jss",
        status="pending",
        payment_method="cheque",
        items=[{"description": "Football kit", "quantity": 1, "unit_cost": "1450.00"}],
    )
    client.patch(f"/api/purchases/{rejected['id']}/status", json={"status": "rejected"})
    create_purchase(
        client,
        alpha["id"],
        purchase_date=days_ago(5),
        category="primary",
        status="approved",
        payment_method="cash",
        items=[{"description": "Cleaning soap", "quantity": 5, "unit_cost": "180.00"}],
    )
    create_purchase(
        client,
        baraka["id"],
        purchase_date=days_ago(10),
        category="primary",
        status="approved",
        payment_method="bank_transfer",
        items=[{"description": "Whiteboard markers", "quantity": 3, "unit_cost": "2500.00"}],
    )
    return {"alpha": alpha, "baraka": baraka, "pending": pending, "rejected": rejected}


def report(client, **params):
    query = "&".join(f"{key}={value}" for key, value in params.items())
    response = client.get(f"/api/reports?{query}")
    assert response.status_code == 200, response.text
    return response.json()


def test_approved_report_totals(report_world, client):
    body = report(
        client,
        **{"from": days_ago(70).isoformat(), "to": date.today().isoformat()}
    )
    assert body["status_scope"] == "approved"
    assert body["record_count"] == 4
    assert body["total_cents"] == 1_640_000
    assert body["average_cents"] == 410_000
    assert body["pending_total_cents"] == 1_300_000
    assert body["granularity"] == "month"
    assert body["from"] == days_ago(70).isoformat()
    assert body["to"] == date.today().isoformat()


def test_active_scope_includes_pending_but_not_rejected(report_world, client):
    body = report(
        client,
        **{
            "from": days_ago(70).isoformat(),
            "to": date.today().isoformat(),
            "status": "active",
        },
    )
    assert body["status_scope"] == "active"
    assert body["record_count"] == 5
    assert body["total_cents"] == 2_940_000
    assert body["pending_total_cents"] == 0

    with_rejected = report(
        client,
        **{"from": days_ago(70).isoformat(), "to": date.today().isoformat()},
    )
    assert with_rejected["total_cents"] == 1_640_000


def test_category_isolation_in_reports(report_world, client):
    primary = report(
        client,
        **{
            "from": days_ago(70).isoformat(),
            "to": date.today().isoformat(),
            "category": "primary",
        },
    )
    assert primary["record_count"] == 3
    assert primary["total_cents"] == 1_290_000
    assert primary["by_category"][0]["count"] == 3
    assert primary["by_category"][1]["count"] == 0

    jss = report(
        client,
        **{
            "from": days_ago(70).isoformat(),
            "to": date.today().isoformat(),
            "category": "jss",
        },
    )
    assert jss["record_count"] == 1
    assert jss["total_cents"] == 350_000
    assert jss["by_category"][0]["count"] == 0
    assert jss["by_category"][1]["count"] == 1


def test_grouping_by_supplier_category_and_payment(report_world, client):
    approved = report(
        client,
        **{"from": days_ago(70).isoformat(), "to": date.today().isoformat()},
    )
    by_supplier = {row["supplier_name"]: row for row in approved["by_supplier"]}
    assert by_supplier["Alpha School Supplies"]["count"] == 3
    assert by_supplier["Alpha School Supplies"]["total_cents"] == 890_000
    assert by_supplier["Baraka Stationers"]["count"] == 1
    assert by_supplier["Baraka Stationers"]["total_cents"] == 750_000
    assert approved["by_supplier"][0]["supplier_name"] == "Alpha School Supplies"

    by_category = {row["category"]: row for row in approved["by_category"]}
    assert by_category["primary"]["count"] == 3
    assert by_category["primary"]["total_cents"] == 1_290_000
    assert by_category["jss"]["count"] == 1
    assert by_category["jss"]["total_cents"] == 350_000

    by_payment = {row["payment_method"]: row for row in approved["by_payment"]}
    assert by_payment["cash"]["total_cents"] == 540_000
    assert by_payment["bank_transfer"]["total_cents"] == 1_100_000
    assert by_payment["mpesa"]["count"] == 0
    assert by_payment["cheque"]["count"] == 0

    active = report(
        client,
        **{
            "from": days_ago(70).isoformat(),
            "to": date.today().isoformat(),
            "status": "active",
        },
    )
    by_supplier = {row["supplier_name"]: row for row in active["by_supplier"]}
    assert by_supplier["Baraka Stationers"]["total_cents"] == 2_050_000
    assert by_supplier["Baraka Stationers"]["count"] == 2
    assert active["by_supplier"][0]["supplier_name"] == "Baraka Stationers"


def test_date_range_boundaries_are_inclusive(report_world, client):
    body = report(
        client,
        **{"from": days_ago(20).isoformat(), "to": days_ago(10).isoformat()},
    )
    assert body["record_count"] == 2
    assert body["total_cents"] == 1_100_000
    assert body["granularity"] == "day"
    assert {row["period"] for row in body["by_period"]} == {
        days_ago(20).isoformat(),
        days_ago(10).isoformat(),
    }


def test_period_granularity_switches_with_the_range(report_world, client):
    daily = report(
        client,
        **{"from": days_ago(25).isoformat(), "to": date.today().isoformat()},
    )
    assert daily["granularity"] == "day"

    monthly = report(
        client,
        **{"from": days_ago(70).isoformat(), "to": date.today().isoformat()},
    )
    assert monthly["granularity"] == "month"
    assert monthly["by_period"][-1]["period"] == date.today().strftime("%Y-%m")

    yearly = report(
        client,
        **{"from": date(date.today().year - 10, 1, 1).isoformat(), "to": date.today().isoformat()},
    )
    assert yearly["granularity"] == "year"
    assert yearly["by_period"][-1]["period"] == str(date.today().year)


def test_empty_report_is_well_formed(report_world, client):
    body = report(client, **{"from": "2010-01-01", "to": "2010-12-31"})
    assert body["record_count"] == 0
    assert body["total_cents"] == 0
    assert body["average_cents"] == 0
    assert body["by_supplier"] == []
    assert len(body["by_period"]) == 12
    assert all(row["total_cents"] == 0 for row in body["by_period"])


def test_report_validation(report_world, client):
    assert client.get("/api/reports?status=bogus").status_code == 422
    assert client.get("/api/reports?category=secondary").status_code == 422
    assert (
        client.get("/api/reports?from=2026-06-01&to=2026-05-01").status_code == 422
    )
