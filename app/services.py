"""Business logic: pricing, references, filtering, reporting and export.

All financial totals are calculated here from integer cents. The browser's
totals are a convenience preview only.
"""

from __future__ import annotations

import csv
import io
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from .db import Connection, is_unique_violation, transaction
from .errors import ConflictError, NotFoundError
from .schemas import (
    CATEGORY_LABELS,
    CATEGORY_ORDER,
    PAYMENT_METHOD_LABELS,
    PAYMENT_METHOD_ORDER,
    PurchaseCreate,
    SupplierCreate,
    category_label,
    payment_method_label,
    status_label,
)

MONTH_NAMES = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def to_cents(value: Decimal) -> int:
    """Convert a validated 2-dp decimal amount to integer cents."""
    return int((value * 100).to_integral_value(rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class PurchaseFilters:
    search: str = ""
    category: str | None = None
    status: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    supplier_id: int | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _build_where(
    filters: PurchaseFilters, status_scope: str | None = None
) -> tuple[str, list[object]]:
    clauses: list[str] = []
    params: list[object] = []

    if status_scope in {"approved", "pending", "rejected"}:
        clauses.append("p.status = ?")
        params.append(status_scope)
    elif status_scope == "active":
        clauses.append("p.status <> 'rejected'")
    elif filters.status:
        clauses.append("p.status = ?")
        params.append(filters.status)

    if filters.category:
        clauses.append("p.category = ?")
        params.append(filters.category)

    if filters.supplier_id is not None:
        clauses.append("p.supplier_id = ?")
        params.append(filters.supplier_id)

    if filters.date_from:
        clauses.append("p.purchase_date >= ?")
        params.append(filters.date_from.isoformat())
    if filters.date_to:
        clauses.append("p.purchase_date <= ?")
        params.append(filters.date_to.isoformat())

    term = filters.search.strip()
    if term:
        like = f"%{_escape_like(term)}%"
        # LOWER() makes search behaviour case-insensitive on both SQLite and
        # PostgreSQL without relying on SQLite-only COLLATE NOCASE syntax.
        clauses.append(
            "("
            "LOWER(p.reference) LIKE LOWER(?) ESCAPE '\\' "
            "OR LOWER(s.name) LIKE LOWER(?) ESCAPE '\\' "
            "OR LOWER(COALESCE(p.invoice_number, '')) LIKE LOWER(?) ESCAPE '\\' "
            "OR EXISTS (SELECT 1 FROM purchase_items si "
            "           WHERE si.purchase_id = p.id "
            "           AND LOWER(si.description) LIKE LOWER(?) ESCAPE '\\')"
            ")"
        )
        params.extend([like, like, like, like])

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


PURCHASE_SELECT = """
SELECT p.*, s.name AS supplier_name,
       (SELECT COUNT(*) FROM purchase_items i WHERE i.purchase_id = p.id) AS item_count,
       (SELECT i.description FROM purchase_items i
         WHERE i.purchase_id = p.id ORDER BY i.position, i.id LIMIT 1) AS first_item
  FROM purchases p
  JOIN suppliers s ON s.id = p.supplier_id
"""


def _row_to_summary(row: Any) -> dict:
    item_count = row["item_count"] or 0
    first_item = row["first_item"] or ""
    summary = first_item
    if item_count > 1:
        summary = f"{first_item} +{item_count - 1} more"
    return {
        "id": row["id"],
        "reference": row["reference"],
        "purchase_date": row["purchase_date"],
        "supplier_id": row["supplier_id"],
        "supplier_name": row["supplier_name"],
        "category": row["category"],
        "category_label": category_label(row["category"]),
        "payment_method": row["payment_method"],
        "payment_method_label": payment_method_label(row["payment_method"]),
        "invoice_number": row["invoice_number"] or "",
        "status": row["status"],
        "status_label": status_label(row["status"]),
        "item_count": item_count,
        "items_summary": summary,
        "total_cents": row["total_cents"],
        "is_demo": bool(row["is_demo"]),
        "created_at": row["created_at"],
    }


def _fetch_purchase_rows(
    conn: Connection,
    filters: PurchaseFilters,
    *,
    limit: int | None = None,
    offset: int = 0,
) -> list[Any]:
    where, params = _build_where(filters)
    sql = PURCHASE_SELECT + where + " ORDER BY p.purchase_date DESC, p.id DESC"
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params = [*params, limit, offset]
    return conn.execute(sql, params).fetchall()


def _get_purchase_row(conn: Connection, purchase_id: int) -> Any | None:
    return conn.execute(
        PURCHASE_SELECT + " WHERE p.id = ?", (purchase_id,)
    ).fetchone()


# ---------------------------------------------------------------------------
# Purchases
# ---------------------------------------------------------------------------


def next_reference_preview(conn: Connection, purchase_date: date) -> str:
    row = conn.execute(
        "SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM purchases"
    ).fetchone()
    return f"ST-{purchase_date.year}-{row['next_id']:05d}"


def create_purchase(
    conn: Connection, payload: PurchaseCreate, *, is_demo: bool = False
) -> dict:
    """Validate ownership rules, price the lines and persist atomically."""
    supplier = conn.execute(
        "SELECT id FROM suppliers WHERE id = ?", (payload.supplier_id,)
    ).fetchone()
    if supplier is None:
        raise NotFoundError("That supplier no longer exists. Choose another supplier.")

    line_rows: list[tuple[str, int, int, int, int]] = []
    subtotal_cents = 0
    for position, item in enumerate(payload.items, start=1):
        unit_cost_cents = to_cents(item.unit_cost)
        line_total_cents = unit_cost_cents * item.quantity
        subtotal_cents += line_total_cents
        line_rows.append(
            (
                item.description,
                item.quantity,
                unit_cost_cents,
                line_total_cents,
                position,
            )
        )

    total_cents = subtotal_cents  # no taxes or adjustments in this version
    now = utc_now()
    decision_at = now if payload.status == "approved" else None

    with transaction(conn):
        # A temporary, unique placeholder avoids a race between concurrent
        # inserts where two rows might both try to use an empty reference.
        temporary_reference = f"TMP-{uuid.uuid4().hex}"
        row = conn.execute(
            """
            INSERT INTO purchases (
                reference, purchase_date, supplier_id, category, payment_method,
                invoice_number, status, notes, subtotal_cents, total_cents,
                is_demo, created_at, updated_at, decision_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (
                temporary_reference,
                payload.purchase_date.isoformat(),
                payload.supplier_id,
                payload.category,
                payload.payment_method,
                payload.invoice_number.strip() or None,
                payload.status,
                payload.notes,
                subtotal_cents,
                total_cents,
                1 if is_demo else 0,
                now,
                now,
                decision_at,
            ),
        ).fetchone()
        if row is None:  # pragma: no cover - defensive
            raise RuntimeError("The purchase insert did not return an id.")
        purchase_id = int(row["id"])
        reference = f"ST-{payload.purchase_date.year}-{purchase_id:05d}"
        conn.execute(
            "UPDATE purchases SET reference = ? WHERE id = ?", (reference, purchase_id)
        )
        conn.executemany(
            """
            INSERT INTO purchase_items (
                purchase_id, description, quantity, unit_cost_cents,
                line_total_cents, position
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (purchase_id, desc, qty, unit, line_total, pos)
                for desc, qty, unit, line_total, pos in line_rows
            ],
        )

    purchase = get_purchase(conn, purchase_id)
    if purchase is None:  # pragma: no cover - defensive
        raise RuntimeError("Purchase was saved but could not be read back.")
    return purchase


def get_purchase(conn: Connection, purchase_id: int) -> dict | None:
    row = _get_purchase_row(conn, purchase_id)
    if row is None:
        return None
    items = conn.execute(
        """
        SELECT id, description, quantity, unit_cost_cents, line_total_cents, position
          FROM purchase_items
         WHERE purchase_id = ?
         ORDER BY position, id
        """,
        (purchase_id,),
    ).fetchall()
    data = _row_to_summary(row)
    data.update(
        {
            "notes": row["notes"],
            "subtotal_cents": row["subtotal_cents"],
            "total_cents": row["total_cents"],
            "updated_at": row["updated_at"],
            "decision_at": row["decision_at"],
            "items": [
                {
                    "id": item["id"],
                    "description": item["description"],
                    "quantity": item["quantity"],
                    "unit_cost_cents": item["unit_cost_cents"],
                    "line_total_cents": item["line_total_cents"],
                }
                for item in items
            ],
        }
    )
    return data


def update_purchase_status(
    conn: Connection, purchase_id: int, status: str
) -> dict:
    row = conn.execute(
        "SELECT id, status FROM purchases WHERE id = ?", (purchase_id,)
    ).fetchone()
    if row is None:
        raise NotFoundError("Purchase not found.")
    now = utc_now()
    with transaction(conn):
        conn.execute(
            """
            UPDATE purchases
               SET status = ?, updated_at = ?, decision_at = ?
             WHERE id = ?
            """,
            (status, now, None if status == "pending" else now, purchase_id),
        )
    purchase = get_purchase(conn, purchase_id)
    if purchase is None:  # pragma: no cover - defensive
        raise NotFoundError("Purchase not found.")
    return purchase


def list_purchases(
    conn: Connection,
    filters: PurchaseFilters,
    *,
    page: int = 1,
    per_page: int = 10,
) -> dict:
    where, params = _build_where(filters)
    totals = conn.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(p.total_cents), 0) AS total "
        "FROM purchases p JOIN suppliers s ON s.id = p.supplier_id" + where,
        params,
    ).fetchone()
    total = int(totals["n"])
    pages = max(1, (total + per_page - 1) // per_page)
    offset = (page - 1) * per_page
    rows = _fetch_purchase_rows(conn, filters, limit=per_page, offset=offset)
    return {
        "items": [_row_to_summary(row) for row in rows],
        "total": total,
        "filtered_total_cents": int(totals["total"]),
        "page": page,
        "per_page": per_page,
        "pages": pages,
    }


def export_purchases_csv(conn: Connection, filters: PurchaseFilters) -> str:
    rows = _fetch_purchase_rows(conn, filters)
    purchase_ids = [row["id"] for row in rows]
    items_by_purchase: dict[int, list[str]] = {pid: [] for pid in purchase_ids}
    if purchase_ids:
        placeholders = ",".join("?" for _ in purchase_ids)
        item_rows = conn.execute(
            f"""
            SELECT purchase_id, description, quantity, unit_cost_cents
              FROM purchase_items
             WHERE purchase_id IN ({placeholders})
             ORDER BY purchase_id, position, id
            """,
            purchase_ids,
        ).fetchall()
        for item in item_rows:
            items_by_purchase[item["purchase_id"]].append(
                f"{item['quantity']} x {item['description']} "
                f"@ KSh {item['unit_cost_cents'] / 100:.2f}"
            )

    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(
        [
            "Reference",
            "Purchase date",
            "School section",
            "Supplier",
            "Item details",
            "Item count",
            "Payment method",
            "Invoice/receipt no.",
            "Approval status",
            "Amount (KSh)",
            "Notes",
            "Recorded at (UTC)",
            "Demo record",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row["reference"],
                row["purchase_date"],
                category_label(row["category"]),
                row["supplier_name"],
                "; ".join(items_by_purchase.get(row["id"], [])),
                row["item_count"],
                payment_method_label(row["payment_method"]),
                row["invoice_number"] or "",
                status_label(row["status"]),
                f"{row['total_cents'] / 100:.2f}",
                row["notes"],
                row["created_at"],
                "Yes" if row["is_demo"] else "No",
            ]
        )
    # UTF-8 BOM helps Excel display KSh text and punctuation correctly.
    return "\ufeff" + buffer.getvalue()


# ---------------------------------------------------------------------------
# Suppliers
# ---------------------------------------------------------------------------


SUPPLIER_SELECT = """
SELECT s.*,
       COUNT(CASE WHEN p.status <> 'rejected' THEN 1 END) AS purchase_count,
       COALESCE(SUM(CASE WHEN p.status = 'approved' THEN p.total_cents ELSE 0 END), 0)
           AS approved_total_cents,
       COALESCE(SUM(CASE WHEN p.status = 'pending' THEN p.total_cents ELSE 0 END), 0)
           AS pending_total_cents,
       MAX(p.purchase_date) AS last_purchase_date
  FROM suppliers s
  LEFT JOIN purchases p ON p.supplier_id = s.id
"""


def _supplier_row_to_dict(row: Any) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "contact_person": row["contact_person"],
        "phone": row["phone"],
        "email": row["email"],
        "address": row["address"],
        "notes": row["notes"],
        "is_demo": bool(row["is_demo"]),
        "created_at": row["created_at"],
        "purchase_count": int(row["purchase_count"] or 0),
        "approved_total_cents": int(row["approved_total_cents"] or 0),
        "pending_total_cents": int(row["pending_total_cents"] or 0),
        "last_purchase_date": row["last_purchase_date"],
    }


def create_supplier(
    conn: Connection, payload: SupplierCreate, *, is_demo: bool = False
) -> dict:
    now = utc_now()
    try:
        with transaction(conn):
            row = conn.execute(
                """
                INSERT INTO suppliers (
                    name, contact_person, phone, email, address, notes,
                    is_demo, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING id
                """,
                (
                    payload.name,
                    payload.contact_person,
                    payload.phone,
                    payload.email,
                    payload.address,
                    payload.notes,
                    1 if is_demo else 0,
                    now,
                ),
            ).fetchone()
            if row is None:  # pragma: no cover - defensive
                raise RuntimeError("The supplier insert did not return an id.")
            supplier_id = int(row["id"])
    except Exception as exc:
        if is_unique_violation(exc):
            raise ConflictError(
                "A supplier with that name is already registered."
            ) from exc
        raise
    supplier = get_supplier(conn, supplier_id)
    if supplier is None:  # pragma: no cover - defensive
        raise RuntimeError("Supplier was saved but could not be read back.")
    return supplier


def list_suppliers(conn: Connection, search: str = "") -> list[dict]:
    where = ""
    params: list[object] = []
    term = search.strip()
    if term:
        like = f"%{_escape_like(term)}%"
        where = (
            " WHERE (LOWER(s.name) LIKE LOWER(?) ESCAPE '\\' "
            "OR LOWER(s.contact_person) LIKE LOWER(?) ESCAPE '\\' "
            "OR LOWER(s.phone) LIKE LOWER(?) ESCAPE '\\' "
            "OR LOWER(s.email) LIKE LOWER(?) ESCAPE '\\')"
        )
        params = [like, like, like, like]
    rows = conn.execute(
        SUPPLIER_SELECT + where + " GROUP BY s.id ORDER BY LOWER(s.name)",
        params,
    ).fetchall()
    return [_supplier_row_to_dict(row) for row in rows]


def get_supplier(conn: Connection, supplier_id: int) -> dict | None:
    row = conn.execute(
        SUPPLIER_SELECT + " WHERE s.id = ? GROUP BY s.id", (supplier_id,)
    ).fetchone()
    if row is None:
        return None
    supplier = _supplier_row_to_dict(row)
    history = list_purchases(
        conn,
        PurchaseFilters(supplier_id=supplier_id),
        page=1,
        per_page=100,
    )
    supplier["history"] = history["items"]
    supplier["history_total"] = history["total"]
    return supplier


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


def _shift_month(anchor: date, delta: int) -> date:
    month_index = anchor.year * 12 + (anchor.month - 1) + delta
    year, month = divmod(month_index, 12)
    return date(year, month + 1, 1)


def dashboard(conn: Connection, category: str | None = None) -> dict:
    scope_sql = " AND p.category = ?" if category else ""
    scope_params: tuple = (category,) if category else ()

    def totals(status_sql: str) -> Any:
        return conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(p.total_cents), 0) AS total "
            "FROM purchases p WHERE " + status_sql + scope_sql,
            scope_params,
        ).fetchone()

    approved = totals("p.status = 'approved'")
    pending = totals("p.status = 'pending'")
    active = totals("p.status <> 'rejected'")
    rejected = totals("p.status = 'rejected'")

    supplier_count = conn.execute(
        "SELECT COUNT(DISTINCT p.supplier_id) AS n FROM purchases p "
        "WHERE p.status <> 'rejected'" + scope_sql,
        scope_params,
    ).fetchone()["n"]

    today = date.today()
    current_month_start = today.replace(day=1)
    current_month = conn.execute(
        "SELECT COALESCE(SUM(p.total_cents), 0) AS total FROM purchases p "
        "WHERE p.status = 'approved' AND p.purchase_date >= ?" + scope_sql,
        (current_month_start.isoformat(), *scope_params),
    ).fetchone()["total"]

    # Six-month grouped series (including months with no purchases).
    first_month = _shift_month(current_month_start, -5)
    month_rows = conn.execute(
        """
        SELECT substr(p.purchase_date, 1, 7) AS ym, p.category,
               COALESCE(SUM(p.total_cents), 0) AS total
          FROM purchases p
         WHERE p.status = 'approved' AND p.purchase_date >= ?
        """ + scope_sql
        + " GROUP BY substr(p.purchase_date, 1, 7), p.category",
        (first_month.isoformat(), *scope_params),
    ).fetchall()
    by_month: dict[str, dict[str, int]] = {}
    for row in month_rows:
        bucket = by_month.setdefault(row["ym"], {"primary": 0, "jss": 0})
        bucket[row["category"]] += int(row["total"])
    monthly = []
    for index in range(6):
        point = _shift_month(first_month, index)
        key = point.strftime("%Y-%m")
        bucket = by_month.get(key, {"primary": 0, "jss": 0})
        monthly.append(
            {
                "month": key,
                "label": f"{MONTH_NAMES[point.month - 1]} {str(point.year)[2:]}",
                "primary_cents": bucket["primary"],
                "jss_cents": bucket["jss"],
                "total_cents": bucket["primary"] + bucket["jss"],
            }
        )

    category_totals = conn.execute(
        "SELECT p.category, COALESCE(SUM(p.total_cents), 0) AS total "
        "FROM purchases p WHERE p.status = 'approved'" + scope_sql +
        " GROUP BY p.category",
        scope_params,
    ).fetchall()
    category_map = {row["category"]: int(row["total"]) for row in category_totals}
    cat_breakdown = [
        {
            "category": key,
            "label": CATEGORY_LABELS[key],
            "total_cents": category_map.get(key, 0),
        }
        for key in CATEGORY_ORDER
    ]

    recent_rows = conn.execute(
        PURCHASE_SELECT
        + " WHERE 1 = 1"
        + scope_sql
        + " ORDER BY p.purchase_date DESC, p.id DESC LIMIT 6",
        scope_params,
    ).fetchall()
    pending_rows = conn.execute(
        PURCHASE_SELECT
        + " WHERE p.status = 'pending'"
        + scope_sql
        + " ORDER BY p.purchase_date DESC, p.id DESC LIMIT 5",
        scope_params,
    ).fetchall()

    return {
        "category": category,
        "approved_total_cents": int(approved["total"]),
        "approved_count": int(approved["n"]),
        "pending_total_cents": int(pending["total"]),
        "pending_count": int(pending["n"]),
        "record_count": int(active["n"]),
        "record_total_cents": int(active["total"]),
        "rejected_count": int(rejected["n"]),
        "supplier_count": int(supplier_count),
        "current_month_total_cents": int(current_month),
        "monthly": monthly,
        "category_breakdown": cat_breakdown,
        "recent": [_row_to_summary(row) for row in recent_rows],
        "pending": [_row_to_summary(row) for row in pending_rows],
        "demo_purchase_count": int(
            conn.execute(
                "SELECT COUNT(*) AS n FROM purchases WHERE is_demo = 1"
            ).fetchone()["n"]
        ),
    }


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


def report(
    conn: Connection,
    filters: PurchaseFilters,
    *,
    status_scope: str = "approved",
) -> dict:
    if status_scope not in {"approved", "active"}:
        status_scope = "approved"
    where, params = _build_where(filters, status_scope=status_scope)
    totals = conn.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(p.total_cents), 0) AS total "
        "FROM purchases p JOIN suppliers s ON s.id = p.supplier_id" + where,
        params,
    ).fetchone()
    total_cents = int(totals["total"])
    record_count = int(totals["n"])

    # Explicit pending total uses the same scope but the pending status.
    base_filters = PurchaseFilters(
        search=filters.search,
        category=filters.category,
        date_from=filters.date_from,
        date_to=filters.date_to,
        supplier_id=filters.supplier_id,
    )
    pending_total = 0
    if status_scope == "approved":
        p_where, p_params = _build_where(base_filters, status_scope="pending")
        pending_total = int(
            conn.execute(
                "SELECT COALESCE(SUM(p.total_cents), 0) AS total "
                "FROM purchases p JOIN suppliers s ON s.id = p.supplier_id" + p_where,
                p_params,
            ).fetchone()["total"]
        )

    by_supplier_rows = conn.execute(
        """
        SELECT s.id AS supplier_id, s.name AS supplier_name,
               COUNT(*) AS n, COALESCE(SUM(p.total_cents), 0) AS total
          FROM purchases p JOIN suppliers s ON s.id = p.supplier_id
        """
        + where
        + " GROUP BY s.id ORDER BY total DESC, LOWER(s.name)",
        params,
    ).fetchall()
    by_supplier = [
        {
            "supplier_id": row["supplier_id"],
            "supplier_name": row["supplier_name"],
            "count": int(row["n"]),
            "total_cents": int(row["total"]),
        }
        for row in by_supplier_rows
    ]

    by_category_rows = conn.execute(
        "SELECT p.category, COUNT(*) AS n, COALESCE(SUM(p.total_cents), 0) AS total "
        "FROM purchases p JOIN suppliers s ON s.id = p.supplier_id"
        + where
        + " GROUP BY p.category",
        params,
    ).fetchall()
    category_map = {
        row["category"]: (int(row["n"]), int(row["total"]))
        for row in by_category_rows
    }
    by_category = [
        {
            "category": key,
            "label": CATEGORY_LABELS[key],
            "count": category_map.get(key, (0, 0))[0],
            "total_cents": category_map.get(key, (0, 0))[1],
        }
        for key in CATEGORY_ORDER
    ]

    by_payment_rows = conn.execute(
        "SELECT p.payment_method, COUNT(*) AS n, COALESCE(SUM(p.total_cents), 0) AS total "
        "FROM purchases p JOIN suppliers s ON s.id = p.supplier_id"
        + where
        + " GROUP BY p.payment_method",
        params,
    ).fetchall()
    payment_map = {
        row["payment_method"]: (int(row["n"]), int(row["total"]))
        for row in by_payment_rows
    }
    by_payment = [
        {
            "payment_method": key,
            "label": PAYMENT_METHOD_LABELS[key],
            "count": payment_map.get(key, (0, 0))[0],
            "total_cents": payment_map.get(key, (0, 0))[1],
        }
        for key in PAYMENT_METHOD_ORDER
    ]

    date_from = filters.date_from or date(2000, 1, 1)
    date_to = filters.date_to or date.today()
    span_days = (date_to - date_from).days
    if span_days <= 45:
        granularity = "day"
        period_expr = "p.purchase_date"
    elif span_days <= 730:
        granularity = "month"
        period_expr = "substr(p.purchase_date, 1, 7)"
    else:
        granularity = "year"
        period_expr = "substr(p.purchase_date, 1, 4)"
    period_rows = conn.execute(
        f"SELECT {period_expr} AS period, COUNT(*) AS n, "
        "COALESCE(SUM(p.total_cents), 0) AS total "
        "FROM purchases p JOIN suppliers s ON s.id = p.supplier_id"
        + where
        + f" GROUP BY {period_expr} ORDER BY {period_expr}",
        params,
    ).fetchall()
    period_map = {
        row["period"]: (int(row["n"]), int(row["total"])) for row in period_rows
    }

    by_period = []
    if granularity == "month":
        cursor = date_from.replace(day=1)
        last = date_to.replace(day=1)
        while cursor <= last:
            key = cursor.strftime("%Y-%m")
            count, amount = period_map.get(key, (0, 0))
            by_period.append(
                {
                    "period": key,
                    "label": f"{MONTH_NAMES[cursor.month - 1]} {cursor.year}",
                    "count": count,
                    "total_cents": amount,
                }
            )
            cursor = _shift_month(cursor, 1)
    elif granularity == "year":
        for year in range(date_from.year, date_to.year + 1):
            key = str(year)
            count, amount = period_map.get(key, (0, 0))
            by_period.append(
                {
                    "period": key,
                    "label": str(year),
                    "count": count,
                    "total_cents": amount,
                }
            )
    else:
        for key in sorted(period_map):
            parsed = date.fromisoformat(key)
            count, amount = period_map[key]
            by_period.append(
                {
                    "period": key,
                    "label": f"{parsed.day} {MONTH_NAMES[parsed.month - 1]} {parsed.year}",
                    "count": count,
                    "total_cents": amount,
                }
            )

    return {
        "from": date_from.isoformat(),
        "to": date_to.isoformat(),
        "category": filters.category,
        "status_scope": status_scope,
        "granularity": granularity,
        "total_cents": total_cents,
        "record_count": record_count,
        "average_cents": (total_cents // record_count) if record_count else 0,
        "pending_total_cents": pending_total,
        "by_period": by_period,
        "by_supplier": by_supplier,
        "by_category": by_category,
        "by_payment": by_payment,
    }
