"""Purchase creation, server-side pricing and approval transitions."""

from __future__ import annotations

import re
from datetime import date, timedelta

from tests.helpers import create_purchase, create_supplier, purchase_payload


def test_create_purchase_calculates_totals_on_the_server(client):
    supplier = create_supplier(client)
    payload = purchase_payload(
        supplier["id"],
        items=[
            {"description": "Exercise books, 48 pages", "quantity": 10, "unit_cost": "45.00"},
            {"description": "Blue pens, box of 50", "quantity": 2, "unit_cost": "1000.00"},
            {"description": "Board duster", "quantity": 1, "unit_cost": "0.01"},
        ],
    )

    response = client.post("/api/purchases", json=payload)
    assert response.status_code == 201, response.text
    purchase = response.json()

    assert re.fullmatch(r"ST-\d{4}-\d{5}", purchase["reference"])
    assert purchase["reference"].startswith(f"ST-{date.today().year}-")
    assert purchase["supplier_id"] == supplier["id"]
    assert purchase["supplier_name"] == supplier["name"]
    assert purchase["category"] == "primary"
    assert purchase["status"] == "pending"
    assert purchase["total_cents"] == 10 * 4500 + 2 * 100000 + 1
    assert purchase["subtotal_cents"] == purchase["total_cents"]
    assert purchase["total_cents"] == 245_001
    assert len(purchase["items"]) == 3
    assert [item["description"] for item in purchase["items"]] == [
        "Exercise books, 48 pages",
        "Blue pens, box of 50",
        "Board duster",
    ]
    assert [item["line_total_cents"] for item in purchase["items"]] == [45_000, 200_000, 1]
    assert purchase["items"][0]["unit_cost_cents"] == 4_500
    assert purchase["is_demo"] is False
    assert purchase["created_at"]
    assert purchase["decision_at"] is None


def test_server_rounds_prices_to_integer_cents(client):
    supplier = create_supplier(client)
    purchase = create_purchase(
        client,
        supplier["id"],
        items=[
            {"description": "Item with a two-decimal cost", "quantity": 3, "unit_cost": "19.99"},
            {"description": "Ten-cent item", "quantity": 7, "unit_cost": "0.10"},
        ],
    )
    assert purchase["items"][0]["line_total_cents"] == 5_997
    assert purchase["items"][1]["line_total_cents"] == 70
    assert purchase["total_cents"] == 6_067


def test_references_are_unique_and_sequential(client):
    supplier = create_supplier(client)
    first = create_purchase(client, supplier["id"])
    second = create_purchase(client, supplier["id"])
    third = create_purchase(client, supplier["id"])

    references = [first["reference"], second["reference"], third["reference"]]
    assert len(set(references)) == 3
    assert references[0].endswith("00001")
    assert references[1].endswith("00002")
    assert references[2].endswith("00003")


def test_quantity_must_be_a_positive_whole_number(client):
    supplier = create_supplier(client)
    for quantity in [0, -2, 1.5, "many"]:
        response = client.post(
            "/api/purchases",
            json=purchase_payload(
                supplier["id"],
                items=[{"description": "Chalk", "quantity": quantity, "unit_cost": "10.00"}],
            ),
        )
        assert response.status_code == 422, quantity
        assert "items.0.quantity" in response.json()["error"]["fields"]


def test_unit_cost_validation(client):
    supplier = create_supplier(client)
    cases = ["0", "-5.00", "10000000.01", "12.345", "abc"]
    for cost in cases:
        response = client.post(
            "/api/purchases",
            json=purchase_payload(
                supplier["id"],
                items=[{"description": "Item", "quantity": 1, "unit_cost": cost}],
            ),
        )
        assert response.status_code == 422, cost
        assert "items.0.unit_cost" in response.json()["error"]["fields"]


def test_purchase_requires_at_least_one_item(client):
    supplier = create_supplier(client)
    response = client.post(
        "/api/purchases",
        json=purchase_payload(supplier["id"], items=[]),
    )
    assert response.status_code == 422
    assert "items" in response.json()["error"]["fields"]


def test_item_description_is_required(client):
    supplier = create_supplier(client)
    response = client.post(
        "/api/purchases",
        json=purchase_payload(
            supplier["id"],
            items=[{"description": " ", "quantity": 1, "unit_cost": "10.00"}],
        ),
    )
    assert response.status_code == 422
    assert "items.0.description" in response.json()["error"]["fields"]


def test_future_and_implausible_dates_are_rejected(client):
    supplier = create_supplier(client)
    for value in [date.today() + timedelta(days=1), date(1999, 12, 31)]:
        response = client.post(
            "/api/purchases",
            json=purchase_payload(supplier["id"], purchase_date=value),
        )
        assert response.status_code == 422, value
        assert "purchase_date" in response.json()["error"]["fields"]


def test_unknown_supplier_is_rejected_at_creation(client):
    response = client.post("/api/purchases", json=purchase_payload(99999))
    assert response.status_code == 404
    assert "supplier" in response.json()["error"]["message"].lower()


def test_rejected_status_cannot_be_set_at_creation(client):
    supplier = create_supplier(client)
    response = client.post(
        "/api/purchases",
        json=purchase_payload(supplier["id"], status="rejected"),
    )
    assert response.status_code == 422


def test_more_than_fifty_items_are_rejected(client):
    supplier = create_supplier(client)
    items = [
        {"description": f"Item {number}", "quantity": 1, "unit_cost": "1.00"}
        for number in range(51)
    ]
    response = client.post("/api/purchases", json=purchase_payload(supplier["id"], items=items))
    assert response.status_code == 422


def test_approval_moves_a_purchase_into_approved_expenditure(client):
    supplier = create_supplier(client)
    pending = create_purchase(client, supplier["id"], status="pending")
    approved = create_purchase(client, supplier["id"], status="approved")

    dashboard = client.get("/api/dashboard").json()
    assert dashboard["approved_count"] == 1
    assert dashboard["approved_total_cents"] == approved["total_cents"]
    assert dashboard["pending_count"] == 1
    assert dashboard["pending_total_cents"] == pending["total_cents"]
    assert dashboard["record_count"] == 2

    response = client.patch(
        f"/api/purchases/{pending['id']}/status", json={"status": "approved"}
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["status"] == "approved"
    assert updated["decision_at"] is not None

    dashboard = client.get("/api/dashboard").json()
    assert dashboard["approved_count"] == 2
    assert dashboard["approved_total_cents"] == pending["total_cents"] + approved["total_cents"]
    assert dashboard["pending_count"] == 0


def test_rejected_purchase_is_excluded_from_active_totals(client):
    supplier = create_supplier(client)
    approved = create_purchase(client, supplier["id"], status="approved")
    rejected = create_purchase(client, supplier["id"], status="pending")

    response = client.patch(
        f"/api/purchases/{rejected['id']}/status", json={"status": "rejected"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"

    dashboard = client.get("/api/dashboard").json()
    assert dashboard["approved_total_cents"] == approved["total_cents"]
    assert dashboard["record_count"] == 1
    assert dashboard["record_total_cents"] == approved["total_cents"]
    assert dashboard["rejected_count"] == 1


def test_reopen_a_purchase_as_pending(client):
    supplier = create_supplier(client)
    purchase = create_purchase(client, supplier["id"], status="approved")
    response = client.patch(
        f"/api/purchases/{purchase['id']}/status", json={"status": "pending"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    assert response.json()["decision_at"] is None


def test_status_update_missing_purchase_returns_404(client):
    response = client.patch("/api/purchases/12345/status", json={"status": "approved"})
    assert response.status_code == 404


def test_invalid_invoice_number_is_rejected(client):
    supplier = create_supplier(client)
    response = client.post(
        "/api/purchases",
        json=purchase_payload(supplier["id"], invoice_number="X" * 61),
    )
    assert response.status_code == 422
    assert "invoice_number" in response.json()["error"]["fields"]
