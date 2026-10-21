"""Supplier registration, duplicate detection and purchase history."""

from __future__ import annotations

from tests.helpers import create_purchase, create_supplier, days_ago, supplier_payload


def test_register_a_supplier(client):
    response = client.post("/api/suppliers", json=supplier_payload("  Acme School Supplies  "))
    assert response.status_code == 201, response.text
    supplier = response.json()

    assert supplier["name"] == "Acme School Supplies"
    assert supplier["contact_person"] == "Amina Test"
    assert supplier["phone"] == "0712 000 111"
    assert supplier["email"] == "supplier@example.test"
    assert supplier["is_demo"] is False
    assert supplier["created_at"]
    assert supplier["purchase_count"] == 0
    assert supplier["approved_total_cents"] == 0
    assert supplier["pending_total_cents"] == 0
    assert supplier["last_purchase_date"] is None


def test_supplier_names_are_unique_case_insensitively(client):
    create_supplier(client, "Unique Traders")
    response = client.post("/api/suppliers", json=supplier_payload("unique traders"))
    assert response.status_code == 409
    assert "already registered" in response.json()["error"]["message"]


def test_supplier_validation(client):
    invalid_email = client.post(
        "/api/suppliers", json=supplier_payload("Email Test", email="not-an-email")
    )
    assert invalid_email.status_code == 422
    assert "email" in invalid_email.json()["error"]["fields"]

    invalid_phone = client.post(
        "/api/suppliers", json=supplier_payload("Phone Test", phone="call me")
    )
    assert invalid_phone.status_code == 422
    assert "phone" in invalid_phone.json()["error"]["fields"]

    short_name = client.post("/api/suppliers", json=supplier_payload("x"))
    assert short_name.status_code == 422
    assert "name" in short_name.json()["error"]["fields"]

    blank_name = client.post("/api/suppliers", json=supplier_payload("   "))
    assert blank_name.status_code == 422

    extra = client.post("/api/suppliers", json={"name": "Extra Field Ltd", "id": 4})
    assert extra.status_code == 422


def test_supplier_search(client):
    create_supplier(client, "Nakuru Books Depot", contact_person="Mary Wambui", phone="0700 111 222")
    create_supplier(
        client,
        "Eldoret Lab Supplies",
        contact_person="John Kiptoo",
        email="lab@eldoret.example",
    )

    by_name = client.get("/api/suppliers?search=books").json()
    assert by_name["total"] == 1
    assert by_name["items"][0]["name"] == "Nakuru Books Depot"

    by_contact = client.get("/api/suppliers?search=kiptoo").json()
    assert by_contact["total"] == 1

    by_phone = client.get("/api/suppliers?search=0700").json()
    assert by_phone["total"] == 1

    by_email = client.get("/api/suppliers?search=eldoret.example").json()
    assert by_email["total"] == 1

    everything = client.get("/api/suppliers").json()
    assert everything["total"] == 2
    assert [item["name"] for item in everything["items"]] == [
        "Eldoret Lab Supplies",
        "Nakuru Books Depot",
    ]


def test_supplier_detail_includes_purchase_history_and_totals(client):
    supplier = create_supplier(client, "History Supplier")
    approved = create_purchase(
        client,
        supplier["id"],
        status="approved",
        purchase_date=days_ago(30),
        items=[{"description": "Desks", "quantity": 2, "unit_cost": "4800.00"}],
    )
    pending = create_purchase(
        client,
        supplier["id"],
        status="pending",
        purchase_date=days_ago(10),
        items=[{"description": "Chairs", "quantity": 4, "unit_cost": "2500.00"}],
    )
    rejected = create_purchase(
        client,
        supplier["id"],
        status="pending",
        purchase_date=days_ago(5),
        items=[{"description": "Coffee table", "quantity": 1, "unit_cost": "15000.00"}],
    )
    client.patch(f"/api/purchases/{rejected['id']}/status", json={"status": "rejected"})

    response = client.get(f"/api/suppliers/{supplier['id']}")
    assert response.status_code == 200
    detail = response.json()

    assert detail["purchase_count"] == 2
    assert detail["approved_total_cents"] == approved["total_cents"]
    assert detail["pending_total_cents"] == pending["total_cents"]
    assert detail["last_purchase_date"] == days_ago(5).isoformat()
    assert detail["history_total"] == 3
    assert [item["id"] for item in detail["history"]] == [
        rejected["id"],
        pending["id"],
        approved["id"],
    ]


def test_missing_supplier_returns_404(client):
    response = client.get("/api/suppliers/424242")
    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Supplier not found."
