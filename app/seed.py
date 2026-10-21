"""Clearly fictional demo data for presentations.

Every seeded supplier and purchase is marked ``is_demo = 1`` and uses invoice
numbers prefixed ``DEMO-``. Seeding runs only when the database has no suppliers
and no purchases, so restarting the app never duplicates or resets records.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path

from .db import (
    Database,
    as_database,
    database_from_env,
    init_db,
    is_empty,
    transaction,
)
from .schemas import PurchaseCreate
from .services import create_purchase, update_purchase_status, utc_now

logger = logging.getLogger("schooltrack.seed")

SUPPLIERS: list[dict[str, str]] = [
    {
        "name": "Mwangaza Educational Supplies Ltd",
        "contact_person": "Grace Wanjiku",
        "phone": "0712 345 001",
        "email": "sales@mwangaza-edu.example",
        "address": "Kenyatta Avenue, Nakuru (fictional address)",
        "notes": "Fictional supplier created for the SchoolTrack demonstration.",
    },
    {
        "name": "Baraka Stationers & Printers",
        "contact_person": "Peter Otieno",
        "phone": "0723 456 002",
        "email": "orders@baraka-stationers.example",
        "address": "Moi Road, Eldoret (fictional address)",
        "notes": "Fictional supplier created for the SchoolTrack demonstration.",
    },
    {
        "name": "Rift Valley Lab & Science Equipment",
        "contact_person": "Dr. Alice Cherono",
        "phone": "0734 567 003",
        "email": "info@riftvalley-lab.example",
        "address": "Industrial Area, Nakuru (fictional address)",
        "notes": "Fictional supplier created for the SchoolTrack demonstration.",
    },
    {
        "name": "Tumaini Furniture Works",
        "contact_person": "Samuel Kiprop",
        "phone": "0745 678 004",
        "email": "works@tumaini-furniture.example",
        "address": "Kapsabet Road, Nandi (fictional address)",
        "notes": "Fictional supplier created for the SchoolTrack demonstration.",
    },
    {
        "name": "Nairobi Digital Copiers",
        "contact_person": "Mercy Njeri",
        "phone": "0756 789 005",
        "email": "support@nairobi-digital.example",
        "address": "Ngong Road, Nairobi (fictional address)",
        "notes": "Fictional supplier created for the SchoolTrack demonstration.",
    },
    {
        "name": "Amani Cleaning & Hygiene Supplies",
        "contact_person": "Janet Achieng",
        "phone": "0767 890 006",
        "email": "hello@amani-cleaning.example",
        "address": "Kisumu Road, Kisumu (fictional address)",
        "notes": "Fictional supplier created for the SchoolTrack demonstration.",
    },
    {
        "name": "Kiptagich Sports & Co-curricular",
        "contact_person": "Daniel Kimutai",
        "phone": "0778 901 007",
        "email": "team@kiptagich-sports.example",
        "address": "Kiptagich Road, Bomet (fictional address)",
        "notes": "Fictional supplier created for the SchoolTrack demonstration.",
    },
]

# days_ago keeps the demo dataset current whenever it is first seeded.
PURCHASES: list[dict] = [
    {
        "days_ago": 2,
        "supplier": "Mwangaza Educational Supplies Ltd",
        "category": "primary",
        "payment_method": "mpesa",
        "invoice_number": "DEMO-INV-1042",
        "status": "pending",
        "notes": "Term 3 exercise books and pens. Pending head teacher approval.",
        "items": [
            ("Exercise books, 48 pages", 600, "45.00"),
            ("Blue ballpoint pens (box of 50)", 6, "1000.00"),
        ],
    },
    {
        "days_ago": 6,
        "supplier": "Rift Valley Lab & Science Equipment",
        "category": "jss",
        "payment_method": "bank_transfer",
        "invoice_number": "DEMO-INV-2214",
        "status": "approved",
        "notes": "JSS integrated science practical equipment.",
        "items": [
            ("Beakers, 250 ml", 24, "350.00"),
            ("Laboratory reagent set", 10, "1250.00"),
            ("Test tubes, borosilicate", 200, "85.00"),
        ],
    },
    {
        "days_ago": 9,
        "supplier": "Rift Valley Lab & Science Equipment",
        "category": "jss",
        "payment_method": "bank_transfer",
        "invoice_number": "DEMO-INV-2240",
        "status": "pending",
        "notes": "Safety goggles for the JSS science laboratory.",
        "items": [("Safety goggles", 40, "450.00")],
    },
    {
        "days_ago": 12,
        "supplier": "Tumaini Furniture Works",
        "category": "primary",
        "payment_method": "cheque",
        "invoice_number": "DEMO-INV-3301",
        "status": "approved",
        "notes": "Replacement desks for Primary Grade 5 and Grade 6.",
        "items": [("Learner desks, wooden top", 25, "4800.00")],
    },
    {
        "days_ago": 16,
        "supplier": "Nairobi Digital Copiers",
        "category": "jss",
        "payment_method": "bank_transfer",
        "invoice_number": "DEMO-INV-4410",
        "status": "pending",
        "notes": "Printer consumables for the JSS computer room.",
        "items": [("Laser printer toner cartridge", 6, "6500.00")],
    },
    {
        "days_ago": 23,
        "supplier": "Amani Cleaning & Hygiene Supplies",
        "category": "primary",
        "payment_method": "cash",
        "invoice_number": "DEMO-INV-5120",
        "status": "approved",
        "notes": "Monthly hygiene supplies for the Primary section.",
        "items": [
            ("Disinfectant, 20 litre", 6, "2400.00"),
            ("Hand soap, 500 ml", 48, "180.00"),
            ("Toilet paper, pack of 10 rolls", 30, "950.00"),
        ],
    },
    {
        "days_ago": 30,
        "supplier": "Kiptagich Sports & Co-curricular",
        "category": "jss",
        "payment_method": "mpesa",
        "invoice_number": "DEMO-INV-6021",
        "status": "approved",
        "notes": "Games equipment for JSS inter-school competitions.",
        "items": [
            ("Football kit, complete", 24, "1450.00"),
            ("Netball", 6, "1800.00"),
        ],
    },
    {
        "days_ago": 38,
        "supplier": "Tumaini Furniture Works",
        "category": "primary",
        "payment_method": "cheque",
        "invoice_number": "DEMO-INV-3310",
        "status": "rejected",
        "notes": "Rejected: not a budgeted item for this term.",
        "items": [("Staffroom coffee table", 2, "15000.00")],
    },
    {
        "days_ago": 44,
        "supplier": "Baraka Stationers & Printers",
        "category": "primary",
        "payment_method": "cash",
        "invoice_number": "DEMO-INV-7102",
        "status": "approved",
        "notes": "Photocopy paper and classroom markers.",
        "items": [
            ("Photocopy paper, A4 ream", 50, "650.00"),
            ("Whiteboard marker, box of 12", 12, "600.00"),
        ],
    },
    {
        "days_ago": 52,
        "supplier": "Mwangaza Educational Supplies Ltd",
        "category": "jss",
        "payment_method": "bank_transfer",
        "invoice_number": "DEMO-INV-1088",
        "status": "approved",
        "notes": "JSS science textbooks for the new curriculum.",
        "items": [("JSS science textbook", 120, "780.00")],
    },
    {
        "days_ago": 60,
        "supplier": "Amani Cleaning & Hygiene Supplies",
        "category": "primary",
        "payment_method": "mpesa",
        "invoice_number": "DEMO-INV-5144",
        "status": "approved",
        "notes": "Classroom cleaning equipment.",
        "items": [
            ("Brooms, heavy duty", 24, "350.00"),
            ("Dustbins, 20 litre", 12, "1250.00"),
        ],
    },
    {
        "days_ago": 72,
        "supplier": "Nairobi Digital Copiers",
        "category": "jss",
        "payment_method": "bank_transfer",
        "invoice_number": "DEMO-INV-4467",
        "status": "approved",
        "notes": "Digital learning tablets for the JSS computer laboratory.",
        "items": [
            ("Learning tablet, 10-inch", 10, "18500.00"),
            ("Protective tablet case", 10, "1200.00"),
        ],
    },
    {
        "days_ago": 85,
        "supplier": "Tumaini Furniture Works",
        "category": "primary",
        "payment_method": "cheque",
        "invoice_number": "DEMO-INV-3355",
        "status": "approved",
        "notes": "Furniture for the Primary staff work area.",
        "items": [
            ("Teacher desk", 8, "9500.00"),
            ("Staff chair", 8, "2500.00"),
        ],
    },
    {
        "days_ago": 97,
        "supplier": "Rift Valley Lab & Science Equipment",
        "category": "jss",
        "payment_method": "bank_transfer",
        "invoice_number": "DEMO-INV-2280",
        "status": "approved",
        "notes": "Laboratory safety and microscope supplies.",
        "items": [
            ("Microscope slides, box of 50", 10, "950.00"),
            ("Laboratory coat", 15, "1600.00"),
        ],
    },
    {
        "days_ago": 110,
        "supplier": "Baraka Stationers & Printers",
        "category": "primary",
        "payment_method": "cash",
        "invoice_number": "DEMO-INV-7155",
        "status": "approved",
        "notes": "Primary creative arts supplies.",
        "items": [
            ("Exercise books, 48 pages", 400, "45.00"),
            ("Colouring pencils, box of 12", 20, "450.00"),
        ],
    },
    {
        "days_ago": 124,
        "supplier": "Mwangaza Educational Supplies Ltd",
        "category": "jss",
        "payment_method": "mpesa",
        "invoice_number": "DEMO-INV-1109",
        "status": "approved",
        "notes": "JSS library reference books and wall maps.",
        "items": [
            ("Library reference book", 60, "950.00"),
            ("Wall map, East Africa", 8, "1200.00"),
        ],
    },
    {
        "days_ago": 139,
        "supplier": "Amani Cleaning & Hygiene Supplies",
        "category": "primary",
        "payment_method": "cash",
        "invoice_number": "DEMO-INV-5177",
        "status": "approved",
        "notes": "Cleaning supplies for the Primary section.",
        "items": [
            ("Cleaning gloves, pair", 30, "120.00"),
            ("Detergent, 5 kg", 20, "450.00"),
            ("Mop and bucket set", 10, "650.00"),
        ],
    },
    {
        "days_ago": 154,
        "supplier": "Kiptagich Sports & Co-curricular",
        "category": "jss",
        "payment_method": "cheque",
        "invoice_number": "DEMO-INV-6070",
        "status": "approved",
        "notes": "JSS athletics uniforms.",
        "items": [("Sports uniform, complete", 20, "2200.00")],
    },
    {
        "days_ago": 168,
        "supplier": "Baraka Stationers & Printers",
        "category": "primary",
        "payment_method": "bank_transfer",
        "invoice_number": "DEMO-INV-7190",
        "status": "approved",
        "notes": "Classroom display and stationery supplies.",
        "items": [
            ("Whiteboard marker", 24, "250.00"),
            ("Manila paper, ream", 10, "480.00"),
        ],
    },
]


def seed_demo_data(target: Database | str | Path) -> dict:
    """Insert demo suppliers and purchases if the database is empty.

    Returns a small summary dict; calling it again is a no-op. The target may
    be a SQLite path or an explicit :class:`Database` (including PostgreSQL).
    """
    database = as_database(target)
    if not is_empty(database):
        return {"seeded": False, "suppliers": 0, "purchases": 0}

    today = date.today()
    now = utc_now()
    conn = database.connect()
    try:
        with transaction(conn):
            for supplier in SUPPLIERS:
                conn.execute(
                    """
                    INSERT INTO suppliers (
                        name, contact_person, phone, email, address, notes,
                        is_demo, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                    """,
                    (
                        supplier["name"],
                        supplier["contact_person"],
                        supplier["phone"],
                        supplier["email"],
                        supplier["address"],
                        supplier["notes"],
                        now,
                    ),
                )
        supplier_ids = {
            row["name"]: row["id"]
            for row in conn.execute("SELECT id, name FROM suppliers").fetchall()
        }

        for spec in PURCHASES:
            purchase_date = today - timedelta(days=int(spec["days_ago"]))
            payload = PurchaseCreate(
                purchase_date=purchase_date,
                supplier_id=supplier_ids[spec["supplier"]],
                category=spec["category"],
                payment_method=spec["payment_method"],
                invoice_number=spec["invoice_number"],
                status="pending" if spec["status"] == "rejected" else spec["status"],
                notes=spec["notes"],
                items=[
                    {"description": desc, "quantity": qty, "unit_cost": cost}
                    for desc, qty, cost in spec["items"]
                ],
            )
            created = create_purchase(conn, payload, is_demo=True)
            if spec["status"] == "rejected":
                update_purchase_status(conn, created["id"], "rejected")
    finally:
        conn.close()

    logger.info("Seeded %s demo suppliers and %s purchases", len(SUPPLIERS), len(PURCHASES))
    return {
        "seeded": True,
        "suppliers": len(SUPPLIERS),
        "purchases": len(PURCHASES),
    }


def reset_demo_data(target: Database | str | Path) -> dict:
    """Owner-only destructive reset of all purchase data.

    This function is intentionally not exposed through HTTP. The management
    CLI requires ``DEMO_MODE=true`` and ``ALLOW_DEMO_RESET=true``.
    """
    database = as_database(target)
    conn = database.connect()
    try:
        with transaction(conn):
            conn.execute("DELETE FROM purchase_items")
            conn.execute("DELETE FROM purchases")
            conn.execute("DELETE FROM suppliers")
    finally:
        conn.close()
    return seed_demo_data(database)


def main() -> None:
    """``python -m app.seed`` — initialise and add demo data if empty."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    database = database_from_env()
    init_db(database)
    result = seed_demo_data(database)
    if result["seeded"]:
        print(
            f"Seeded {result['purchases']} demo purchases and "
            f"{result['suppliers']} demo suppliers into {database.label}."
        )
    else:
        print(f"Database already contains records; nothing seeded ({database.label}).")
    print("All seeded records are fictional and marked as demo data.")


if __name__ == "__main__":
    main()
