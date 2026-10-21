"""Search, date, category, status, supplier and pagination filters plus CSV."""

from __future__ import annotations

import csv
import io
from datetime import date

import pytest

from tests.helpers import create_purchase, create_supplier, days_ago


@pytest.fixture
def world(client):
    """Five purchases across two suppliers, two sections and three statuses."""
    alpha = create_supplier(client, "Alpha School Supplies", contact_person="Grace Alpha")
    baraka = create_supplier(client, "Baraka Stationers", contact_person="Peter Baraka")

    first = create_purchase(
        client,
        alpha["id"],
        purchase_date=days_ago(40),
        category="primary",
        status="approved",
        payment_method="cash",
        invoice_number="INV-001",
        items=[{"description": "Exercise books", "quantity": 100, "unit_cost": "45.00"}],
        notes="Primary exercise books",
    )
    second = create_purchase(
        client,
        alpha["id"],
        purchase_date=days_ago(20),
        category="jss",
        status="pending",
        payment_method="bank_transfer",
        invoice_number="INV-002",
        items=[{"description": "Science beakers", "quantity": 10, "unit_cost": "350.00"}],
        notes="JSS laboratory glassware",
    )
    third = create_purchase(
        client,
        baraka["id"],
        purchase_date=days_ago(5),
        category="primary",
        status="approved",
        payment_method="cheque",
        invoice_number="INV-003",
        items=[{"description": "Printer toner", "quantity": 2, "unit_cost": "6500.00"}],
        notes="Primary office printer",
    )
    fourth = create_purchase(
        client,
        baraka["id"],
        purchase_date=days_ago(40),
        category="jss",
        status="pending",
        payment_method="mpesa",
        invoice_number="INV-004",
        items=[{"description": "Football kit", "quantity": 1, "unit_cost": "1450.00"}],
        notes="JSS games kit",
    )
    client.patch(f"/api/purchases/{fourth['id']}/status", json={"status": "rejected"})
    fifth = create_purchase(
        client,
        alpha["id"],
        purchase_date=days_ago(5),
        category="primary",
        status="pending",
        payment_method="cash",
        invoice_number="INV-005",
        items=[{"description": "Cleaning soap", "quantity": 5, "unit_cost": "180.00"}],
        notes="Primary hygiene",
    )
    return {
        "alpha": alpha,
        "baraka": baraka,
        "records": [first, second, third, fourth, fifth],
        "first": first,
        "second": second,
        "third": third,
        "fourth": fourth,
        "fifth": fifth,
    }


def references(response):
    return {item["reference"] for item in response.json()["items"]}


def test_category_filter_keeps_primary_and_jss_separate(client, world):
    primary = client.get("/api/purchases?category=primary").json()
    assert primary["total"] == 3
    assert all(item["category"] == "primary" for item in primary["items"])

    jss = client.get("/api/purchases?category=jss").json()
    assert jss["total"] == 2
    assert all(item["category"] == "jss" for item in jss["items"])

    every = client.get("/api/purchases").json()
    assert every["total"] == 5


def test_date_filters_are_inclusive(client, world):
    start = days_ago(20).isoformat()
    end = days_ago(5).isoformat()

    window = client.get(f"/api/purchases?from={start}&to={end}").json()
    assert window["total"] == 3
    assert {item["id"] for item in window["items"]} == {
        world["second"]["id"],
        world["third"]["id"],
        world["fifth"]["id"],
    }

    from_only = client.get(f"/api/purchases?from={days_ago(20).isoformat()}").json()
    assert from_only["total"] == 3

    to_only = client.get(f"/api/purchases?to={days_ago(20).isoformat()}").json()
    assert to_only["total"] == 3


def test_category_and_date_filters_combine(client, world):
    response = client.get(
        f"/api/purchases?category=primary&from={days_ago(10).isoformat()}&to={date.today().isoformat()}"
    ).json()
    assert response["total"] == 2
    assert {item["id"] for item in response["items"]} == {
        world["third"]["id"],
        world["fifth"]["id"],
    }


def test_search_matches_reference_supplier_invoice_and_items(client, world):
    by_reference = client.get("/api/purchases?search=ST-").json()
    assert by_reference["total"] == 5

    by_supplier = client.get("/api/purchases?search=Baraka").json()
    assert by_supplier["total"] == 2
    assert {item["id"] for item in by_supplier["items"]} == {
        world["third"]["id"],
        world["fourth"]["id"],
    }

    by_invoice = client.get("/api/purchases?search=INV-003").json()
    assert by_invoice["total"] == 1
    assert by_invoice["items"][0]["id"] == world["third"]["id"]

    by_item = client.get("/api/purchases?search=beakers").json()
    assert by_item["total"] == 1
    assert by_item["items"][0]["id"] == world["second"]["id"]

    no_match = client.get("/api/purchases?search=nothing-matches-this").json()
    assert no_match["total"] == 0
    assert no_match["items"] == []


def test_status_filter(client, world):
    approved = client.get("/api/purchases?status=approved").json()
    assert approved["total"] == 2
    assert all(item["status"] == "approved" for item in approved["items"])

    pending = client.get("/api/purchases?status=pending").json()
    assert pending["total"] == 2

    rejected = client.get("/api/purchases?status=rejected").json()
    assert rejected["total"] == 1
    assert rejected["items"][0]["id"] == world["fourth"]["id"]


def test_supplier_filter(client, world):
    response = client.get(f"/api/purchases?supplier_id={world['alpha']['id']}").json()
    assert response["total"] == 3
    assert {item["supplier_id"] for item in response["items"]} == {world["alpha"]["id"]}


def test_pagination_and_filtered_total(client, world):
    first_page = client.get("/api/purchases?per_page=2&page=1").json()
    assert first_page["total"] == 5
    assert first_page["pages"] == 3
    assert first_page["page"] == 1
    assert len(first_page["items"]) == 2
    # The register total covers every filtered row, including the rejected record.
    assert first_page["filtered_total_cents"] == 2_335_000

    last_page = client.get("/api/purchases?per_page=2&page=3").json()
    assert len(last_page["items"]) == 1

    beyond = client.get("/api/purchases?per_page=2&page=99").json()
    assert beyond["items"] == []
    assert beyond["total"] == 5

    filtered = client.get("/api/purchases?category=primary&per_page=10").json()
    assert filtered["filtered_total_cents"] == 1_840_000


def test_invalid_filter_values_are_rejected(client, world):
    bad_status = client.get("/api/purchases?status=lost")
    assert bad_status.status_code == 422

    bad_category = client.get("/api/purchases?category=secondary")
    assert bad_category.status_code == 422

    inverted = client.get("/api/purchases?from=2026-06-01&to=2026-05-01")
    assert inverted.status_code == 422


def test_dashboard_respects_the_section_filter(client, world):
    all_sections = client.get("/api/dashboard").json()
    assert all_sections["approved_total_cents"] == 1_750_000
    assert all_sections["approved_count"] == 2
    assert all_sections["pending_count"] == 2
    assert all_sections["pending_total_cents"] == 440_000
    assert all_sections["record_count"] == 4
    assert all_sections["rejected_count"] == 1
    assert all_sections["supplier_count"] == 2

    primary = client.get("/api/dashboard?category=primary").json()
    assert primary["approved_total_cents"] == 1_750_000
    assert primary["approved_count"] == 2
    assert primary["pending_count"] == 1
    assert primary["record_count"] == 3

    jss = client.get("/api/dashboard?category=jss").json()
    assert jss["approved_total_cents"] == 0
    assert jss["pending_count"] == 1
    assert jss["rejected_count"] == 1
    assert jss["record_count"] == 1


def test_csv_export_contains_the_filtered_rows(client, world):
    response = client.get("/api/purchases/export.csv?category=jss")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    assert response.content.startswith("\ufeff".encode("utf-8"))

    text = response.content.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    assert len(rows) == 2
    assert {row["Reference"] for row in rows} == {
        world["second"]["reference"],
        world["fourth"]["reference"],
    }
    assert all(row["School section"] == "Junior Secondary (JSS)" for row in rows)
    assert rows[0]["Supplier"] in {"Alpha School Supplies", "Baraka Stationers"}
    assert "Amount (KSh)" in rows[0]


def test_csv_export_obeys_search_and_dates(client, world):
    response = client.get("/api/purchases/export.csv?search=toner")
    rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert len(rows) == 1
    assert rows[0]["Reference"] == world["third"]["reference"]

    response = client.get(
        f"/api/purchases/export.csv?from={days_ago(5).isoformat()}&to={date.today().isoformat()}"
    )
    rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert len(rows) == 2
