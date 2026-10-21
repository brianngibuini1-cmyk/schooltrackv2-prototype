"""Owner-run database management commands.

Examples:
    python -m app.manage init-db
    python -m app.manage seed-demo
    python -m app.manage reset-demo --yes

``reset-demo`` only works when the deployment is explicitly in demo mode and
the owner has set ``ALLOW_DEMO_RESET=true``. There is no public reset route.
"""

from __future__ import annotations

import argparse
import logging
import sys

from .config import allow_demo_reset, demo_mode_enabled
from .db import database_from_env, init_db
from .seed import reset_demo_data, seed_demo_data


def _database():
    return database_from_env()


def command_init_db(_args: argparse.Namespace) -> int:
    database = _database()
    init_db(database)
    print(f"Schema is up to date on {database.label}.")
    return 0


def command_seed_demo(_args: argparse.Namespace) -> int:
    database = _database()
    init_db(database)
    result = seed_demo_data(database)
    if result["seeded"]:
        print(
            f"Seeded {result['purchases']} fictional purchases and "
            f"{result['suppliers']} suppliers into {database.label}."
        )
    else:
        print(f"Database already contains records; nothing seeded ({database.label}).")
    return 0


def command_reset_demo(args: argparse.Namespace) -> int:
    if not args.yes:
        print(
            "Refusing to reset without --yes. This deletes all purchases and suppliers.",
            file=sys.stderr,
        )
        return 2
    if not demo_mode_enabled():
        print("Refusing to reset: DEMO_MODE must be true.", file=sys.stderr)
        return 2
    if not allow_demo_reset():
        print(
            "Refusing to reset: set ALLOW_DEMO_RESET=true for this owner-run command.",
            file=sys.stderr,
        )
        return 2

    database = _database()
    init_db(database)
    deleted_scope = "all purchase and supplier records"
    result = reset_demo_data(database)
    if result["seeded"]:
        print(
            f"Reset {deleted_scope} and reseeded {result['purchases']} fictional "
            f"purchases on {database.label}."
        )
        return 0
    print("Reset did not reseed the database.", file=sys.stderr)
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="SchoolTrack owner database commands (no public reset endpoint)."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help="create or upgrade schema").set_defaults(
        handler=command_init_db
    )

    subparsers.add_parser(
        "seed-demo", help="seed fictional data only when the database is empty"
    ).set_defaults(handler=command_seed_demo)

    reset_parser = subparsers.add_parser(
        "reset-demo",
        help="destructively reset all records and reseed demo data (owner only)",
    )
    reset_parser.add_argument(
        "--yes", action="store_true", help="confirm the destructive reset"
    )
    reset_parser.set_defaults(handler=command_reset_demo)
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
