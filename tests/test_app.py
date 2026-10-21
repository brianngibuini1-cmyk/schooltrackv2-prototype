"""Application shell, metadata, static assets and error envelopes."""

from __future__ import annotations

from datetime import date


def test_health_and_meta(client):
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    meta = client.get("/api/meta")
    assert meta.status_code == 200
    body = meta.json()
    assert body["currency"] == "KES"
    assert body["currency_symbol"] == "KSh"
    assert body["demo_mode"] is False
    assert body["writes_enabled"] is True
    assert body["storage_backend"] == "sqlite"
    assert [item["value"] for item in body["categories"]] == ["primary", "jss"]
    assert [item["value"] for item in body["payment_methods"]] == [
        "cash",
        "mpesa",
        "bank_transfer",
        "cheque",
        "other",
    ]
    assert [item["value"] for item in body["statuses"]] == ["pending", "approved", "rejected"]
    assert body["today"] == date.today().isoformat()
    assert body["demo_purchase_count"] == 0


def test_frontend_shell_and_assets_are_served(client):
    index = client.get("/")
    assert index.status_code == 200
    assert "SchoolTrack" in index.text
    assert "Mwangaza Academy" in index.text
    assert "/static/js/app.js" in index.text

    for path in [
        "/static/css/app.css",
        "/static/js/app.js",
        "/static/js/views/purchase-form.js",
        "/static/vendor/chart.umd.min.js",
        "/static/favicon.svg",
    ]:
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.content, path


def test_openapi_schema_is_local_and_swagger_cdn_is_disabled(client):
    schema = client.get("/api/openapi.json")
    assert schema.status_code == 200
    assert schema.json()["info"]["title"] == "SchoolTrack API"
    assert "/api/purchases" in schema.json()["paths"]
    assert client.get("/api/docs").status_code == 404


def test_api_404_uses_the_json_error_envelope(client):
    response = client.get("/api/purchases/99999")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {
        "error": {"message": "Purchase not found.", "fields": {}}
    }

    unknown = client.get("/api/not-a-real-endpoint")
    assert unknown.status_code == 404
    assert unknown.json()["error"]["message"]


def test_invalid_enum_and_unknown_extra_fields_are_rejected(client):
    bad_category = client.get("/api/dashboard?category=all")
    assert bad_category.status_code == 422
    assert "message" in bad_category.json()["error"]

    supplier = client.post("/api/suppliers", json={"name": "Valid Supplier"}).json()
    payload = {
        "purchase_date": date.today().isoformat(),
        "supplier_id": supplier["id"],
        "category": "primary",
        "payment_method": "cash",
        "status": "pending",
        "items": [{"description": "Chalk", "quantity": 1, "unit_cost": "10.00"}],
        "total_cents": 1,
    }
    rejection = client.post("/api/purchases", json=payload)
    assert rejection.status_code == 422
    fields = rejection.json()["error"]["fields"]
    assert "total_cents" in fields


def test_date_range_validation_returns_a_clear_message(client):
    response = client.get("/api/purchases?from=2026-05-01&to=2026-04-01")
    assert response.status_code == 422
    message = response.json()["error"]["message"]
    assert "from" in message.lower() and "before" in message.lower()


def test_security_headers_are_present(client):
    response = client.get("/api/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-frame-options"] == "DENY"
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["cache-control"] == "no-store"


def test_health_has_no_configuration_secrets(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["ready"] is True
    assert "password" not in response.text.lower()
    assert "database_url" not in response.text.lower()
    assert client.get("/healthz").status_code == 200
