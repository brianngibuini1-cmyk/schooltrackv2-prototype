"""Quick backend smoke check against a temporary database.

Run from the project folder:
    python scripts/smoke_check.py
"""

from __future__ import annotations

import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402


def main() -> None:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="schooltrack-smoke-")) / "smoke.db"
    app = create_app(db_path=tmp, seed_demo=True)
    failures: list[str] = []
    with TestClient(app) as client:
        for path in [
            "/api/health",
            "/api/meta",
            "/api/dashboard",
            "/api/purchases",
            "/api/suppliers",
            "/api/reports",
            "/",
        ]:
            response = client.get(path)
            print(f"{path:24} {response.status_code} {response.headers.get('content-type')}")
            if response.status_code != 200:
                failures.append(f"{path} -> {response.status_code}\n{response.text}")

        dashboard = client.get("/api/dashboard").json()
        print(
            "dashboard: approved KES "
            f"{dashboard['approved_total_cents'] / 100:,.2f}; pending "
            f"{dashboard['pending_count']}; records {dashboard['record_count']}"
        )
        purchases = client.get("/api/purchases?per_page=3").json()
        print("purchases:", purchases["total"], "records")
        if purchases["items"]:
            purchase = client.get(
                f"/api/purchases/{purchases['items'][0]['id']}"
            ).json()
            print(
                "first purchase:",
                purchase["reference"],
                purchase["status"],
                f"KES {purchase['total_cents'] / 100:,.2f}",
                f"({len(purchase['items'])} line items)",
            )
        csv_response = client.get("/api/purchases/export.csv")
        print("csv export:", csv_response.status_code, len(csv_response.content), "bytes")
        report = client.get("/api/reports").json()
        print(
            "report:",
            report["record_count"],
            "records;",
            f"KES {report['total_cents'] / 100:,.2f};",
            report["granularity"],
        )
    print("temporary db:", tmp)
    if failures:
        print("\nFAILURES:")
        for failure in failures:
            print(failure)
        raise SystemExit(1)
    print("smoke check passed")


if __name__ == "__main__":
    main()
