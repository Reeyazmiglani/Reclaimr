"""One-time data migration: local SQLite (db/erp.db) -> PostgreSQL (DATABASE_URL).

Reads every table out of the existing local SQLite file and inserts its rows
into the already-initialized Postgres schema (run db/schema.py's init_db
first, or just import a page module, to make sure tables exist). IDs are
preserved as-is so foreign keys keep pointing at the right rows; each table's
SERIAL sequence is then advanced past the highest migrated id so future
inserts don't collide.

Usage:
    python scripts/migrate_to_postgres.py [path-to-sqlite-db]

DATABASE_URL must be set in the environment (or .env).
"""
import os
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv

from db.connection import connect

# Order matters: tables with FKs must come after the tables they reference.
TABLE_ORDER = [
    "companies",
    "users",
    "orders",
    "procurement",
    "production",
    "exports",
    "production_logs",
    "batch_allocations",
    "batch_complaints",
    "batch_complaint_updates",
    "financial_snapshots",
    "receivables",
    "payables",
    "payments",
    "intercompany_transactions",
    "stock_adjustments",
    "settings",
    "monthly_updates",
    "forecast_targets",
    "production_cost_edits",
]


def _sqlite_tables(sconn) -> list[str]:
    rows = sconn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    present = {r[0] for r in rows}
    # Migrate known tables first (in FK-safe order), then anything unexpected.
    ordered = [t for t in TABLE_ORDER if t in present]
    ordered += sorted(present - set(ordered))
    return ordered


def migrate(sqlite_path: Path, database_url: str) -> dict:
    if not sqlite_path.exists():
        print(f"No local SQLite database found at {sqlite_path} — nothing to migrate.")
        return {}

    sconn = sqlite3.connect(str(sqlite_path))
    sconn.row_factory = sqlite3.Row
    pconn = connect(database_url)

    results = {}
    for table in _sqlite_tables(sconn):
        src_rows = sconn.execute(f"SELECT * FROM {table}").fetchall()
        if not src_rows:
            results[table] = 0
            continue

        cols = src_rows[0].keys()
        col_list = ", ".join(cols)
        placeholders = ", ".join(["%s"] * len(cols))

        cur = pconn.cursor()
        migrated = 0
        for row in src_rows:
            values = [row[c] for c in cols]
            try:
                cur.execute(
                    f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) "
                    f"ON CONFLICT DO NOTHING",
                    values,
                )
                migrated += cur.rowcount
            except Exception as e:
                pconn.rollback()
                print(f"  ! failed on {table} id={row['id'] if 'id' in cols else '?'}: {e}")
                continue
        pconn.commit()

        # Move the SERIAL sequence past the highest migrated id so new
        # inserts don't collide with the migrated rows.
        if "id" in cols:
            try:
                cur.execute(
                    f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM {table}), 1))"
                )
                pconn.commit()
            except Exception:
                pconn.rollback()

        results[table] = migrated

    sconn.close()
    return results


if __name__ == "__main__":
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise SystemExit("DATABASE_URL is not set")

    sqlite_arg = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "db" / "erp.db"

    print(f"Migrating {sqlite_arg} -> Postgres ({db_url.split('@')[-1]})")
    counts = migrate(sqlite_arg, db_url)

    if counts:
        print("\nRows migrated per table:")
        for t, n in counts.items():
            print(f"  {t:<28} {n}")
        print(f"\nTotal: {sum(counts.values())} rows across {len(counts)} tables.")
