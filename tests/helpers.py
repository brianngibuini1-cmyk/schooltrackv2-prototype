"""Small factories shared by the test modules."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any


def supplier_payload(name: str = "Test Supplier Ltd", **overrides: Any) -> dict:
    payload = {
        "name": name,
        "contact_person": "Amina Test",
        "phone": "0712 000 111",
        "email": "supplier@example.test",
        "address": "Test Road, Nakuru",
        "notes": "Created by an automated test.",
    }
    payload.update(overrides)
    return payload


def create_supplier(client, name: str = "Test Supplier Ltd", **overrides: Any) -> dict:
    response = client.post("/api/suppliers", json=supplier_payload(name, **overrides))
    assert response.status_code == 201, response.text
    return response.json()


def purchase_payload(
    supplier_id: int,
    *,
    purchase_date: date | None = None,
    category: str = "primary",
    status: str = "pending",
    payment_method: str = "mpesa",
    invoice_number: str = "INV-TEST-001",
    items: list[dict] | None = None,
    notes: str = "Test purchase",
    **overrides: Any,
) -> dict:
    payload = {
        "purchase_date": (purchase_date or date.today()).isoformat(),
        "supplier_id": supplier_id,
        "category": category,
        "payment_method": payment_method,
        "invoice_number": invoice_number,
        "status": status,
        "notes": notes,
        "items": items
        if items is not None
        else [
            {"description": "Exercise books, 48 pages", "quantity": 10, "unit_cost": "45.00"},
            {"description": "Blue pens, box of 50", "quantity": 2, "unit_cost": "1000.00"},
        ],
    }
    payload.update(overrides)
    return payload


def create_purchase(client, supplier_id: int, **kwargs: Any) -> dict:
    response = client.post("/api/purchases", json=purchase_payload(supplier_id, **kwargs))
    assert response.status_code == 201, response.text
    return response.json()


def days_ago(days: int) -> date:
    return date.today() - timedelta(days=days)
