"""One-off (re-runnable) demo-data seeder for screenshots/portfolio use.

Generates realistic-looking Orders / Procurement / Production data across
the last ~10 months for both companies, so the Home dashboard, Orders,
Procurement and Production pages have something worth looking at instead
of near-empty charts.

Safe to re-run: every row it inserts is tagged with the DEMO_TAG marker in
its notes field, and a re-run deletes-then-reinserts only rows carrying
that tag — it never touches your real data (the 1 real order, the
Tally-imported payables/receivables, etc.).

To remove all demo data later: python scripts/seed_demo_data.py --clear

Usage:
    python scripts/seed_demo_data.py [DATABASE_URL]
(DATABASE_URL defaults to the DATABASE_URL env var / .env file.)
"""
import os
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from db.schema import init_db

DEMO_TAG = "[demo seed]"

CUSTOMERS = [
    "Deccan Tyre Retreaders", "Bharat Rubber Works", "Konkan Auto Components",
    "Silverline Elastomers", "Trident Industrial Rubber", "Om Sai Rubber Udyog",
    "Nova Polymer Traders", "Ganesh Rubber Recyclers", "Shree Balaji Rubbers",
    "Kutch Rubber Industries", "Vishal Tyre Solutions", "Anand Elastomers Pvt Ltd",
]

PRODUCTS = [
    "Reclaimed Rubber Compound (RRC-40)", "Natural Rubber Reclaim (NRR-20)",
    "Butyl Reclaim", "Whole Tyre Reclaim", "EPDM Crumb Rubber", "Tube Reclaim Rubber",
]

RAW_MATERIALS = [
    ("Purple Material (Waste Tube)", 26.0), ("Paraffin Wax", 88.0), ("Master Compound (MC)", 64.0),
]
SUPPLIERS = [
    "Alstrong Enterprises", "Nirman Trading Co", "HPL Additives Ltd",
    "GRP Rubber Traders", "Speedways Materials", "Dev Rubber Supplies",
]

random.seed(42)  # reproducible run-to-run so screenshots don't shuffle


def _months_back(n):
    """List of (year, month) tuples for the last n months, oldest first."""
    out = []
    y, m = date.today().year, date.today().month
    for _ in range(n):
        out.append((y, m))
        m -= 1
        if m == 0:
            m = 12; y -= 1
    return list(reversed(out))


def clear_demo_data(conn):
    for table, col in [("orders", "notes"), ("procurement", "notes"), ("production_logs", "additional_notes")]:
        cur = conn.execute(f"DELETE FROM {table} WHERE {col} LIKE %s", (f"%{DEMO_TAG}%",))
    conn.commit()
    print("Cleared all previously-seeded demo rows from orders/procurement/production_logs.")


def seed_orders(conn, rwox_id, elasto_id):
    months = _months_back(10)
    rows = []
    for i, (y, m) in enumerate(months):
        # Gentle growth trend: more orders in recent months.
        n_orders = random.randint(2, 4) + i // 2
        for _ in range(n_orders):
            company_id = rwox_id if random.random() < 0.65 else elasto_id
            day = random.randint(1, 27)
            created = date(y, m, day)
            product = random.choice(PRODUCTS)
            qty = random.randint(500, 4000)
            rate = round(random.uniform(38, 62), 2)
            dispatch_days = random.randint(5, 18)
            dispatch = created + timedelta(days=dispatch_days)
            is_latest_month = (y, m) == months[-1]
            if is_latest_month and dispatch <= date.today() + timedelta(days=3):
                status = random.choice(["received", "in_production"])
            else:
                status = "dispatched" if dispatch < date.today() else random.choice(
                    ["received", "in_production", "dispatched"])
            rows.append((
                company_id, random.choice(CUSTOMERS), product, qty, "kg",
                rate, "per_unit", dispatch.isoformat(), status,
                f"{DEMO_TAG} generated sample order", created.strftime("%Y-%m-%d %H:%M:%S"),
            ))

    # A couple of deliberately overdue / stagnant orders so the Alerts
    # section on the Home page has something real to show.
    overdue_due = date.today() - timedelta(days=4)
    stagnant_created = date.today() - timedelta(days=9)
    rows.append((rwox_id, "Trident Industrial Rubber", "Reclaimed Rubber Compound (RRC-40)",
                 1200, "kg", 46.0, "per_unit", overdue_due.isoformat(), "in_production",
                 f"{DEMO_TAG} intentionally overdue for the alerts demo",
                 (overdue_due - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")))
    rows.append((elasto_id, "Nova Polymer Traders", "Butyl Reclaim",
                 800, "kg", 52.0, "per_unit", (stagnant_created + timedelta(days=14)).isoformat(), "received",
                 f"{DEMO_TAG} intentionally stagnant for the alerts demo",
                 stagnant_created.strftime("%Y-%m-%d %H:%M:%S")))

    for r in rows:
        conn.execute(
            "INSERT INTO orders (company_id, customer_name, product, quantity, quantity_unit, "
            "rate, rate_type, expected_dispatch_date, status, notes, created_at) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", r,
        )
    conn.commit()
    return len(rows)


def seed_procurement(conn, rwox_id, elasto_id):
    months = _months_back(10)
    rows = []
    for i, (y, m) in enumerate(months):
        for item, base_cost in RAW_MATERIALS:
            # Master Compound gets a deliberate price spike in the most
            # recent month, so the Home page's price-spike alert has
            # something real to flag.
            is_latest = (y, m) == months[-1]
            cost = base_cost * (1.12 if (is_latest and "Master Compound" in item) else 1.0)
            cost *= random.uniform(0.95, 1.05)
            day = random.randint(1, 26)
            purchase_date = date(y, m, day)
            company_id = rwox_id if item != "Master Compound (MC)" or random.random() < 0.8 else elasto_id
            rows.append((
                company_id, item, round(random.uniform(800, 3200), 1), "kg",
                round(cost, 2), random.choice(SUPPLIERS), purchase_date.isoformat(),
                f"{DEMO_TAG} generated sample purchase", "per_unit",
            ))
    for r in rows:
        conn.execute(
            "INSERT INTO procurement (company_id, item, quantity, quantity_unit, unit_cost, "
            "supplier, purchase_date, notes, price_type) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)", r,
        )
    conn.commit()
    return len(rows)


def seed_production(conn, rwox_id):
    months = _months_back(10)
    rows = []
    batch_n = 1
    for (y, m) in months:
        n_batches = random.randint(2, 4)
        for _ in range(n_batches):
            day = random.randint(1, 27)
            d = date(y, m, day)
            purple = round(random.uniform(900, 1800), 1)
            wax = round(purple * random.uniform(0.03, 0.05), 1)
            mc = round(purple * random.uniform(0.08, 0.12), 1)
            output = round((purple + wax + mc) * random.uniform(0.90, 0.96), 1)  # some process loss
            rejections = round(output * random.uniform(0.0, 0.02), 1)
            cartons_1kg = round(output * random.uniform(0.3, 0.4))
            cartons_5kg = round(output * random.uniform(0.08, 0.12))
            purple_cost = round(purple * 26.0, 2)
            wax_cost = round(wax * 88.0, 2)
            mc_cost = round(mc * 64.0, 2)
            overhead = round(output * 4.5, 2)
            total_cost = round(purple_cost + wax_cost + mc_cost + overhead, 2)
            cost_per_kg = round(total_cost / output, 2) if output else None
            rows.append((
                rwox_id, d.isoformat(), f"DEMO-{y}{m:02d}-{batch_n:03d}",
                purple, wax, mc, output, cartons_1kg, cartons_5kg, rejections,
                purple_cost, wax_cost, mc_cost, overhead, total_cost, cost_per_kg,
                f"{DEMO_TAG} generated sample batch",
            ))
            batch_n += 1
    for r in rows:
        conn.execute(
            "INSERT INTO production_logs (company_id, date, batch_ref, purple_material_kg, wax_kg, "
            "mc_kg, output_kg, cartons_1kg, cartons_5kg, rejections_kg, purple_material_cost, "
            "wax_cost, mc_cost, overhead_cost, total_batch_cost, cost_per_kg, additional_notes) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", r,
        )
    conn.commit()
    return len(rows)


def main():
    load_dotenv()
    db_url = sys.argv[-1] if len(sys.argv) > 1 and not sys.argv[-1].startswith("--") else os.getenv("DATABASE_URL")
    if not db_url:
        raise SystemExit("DATABASE_URL not set (pass as arg or set in .env)")

    conn = init_db(db_url)

    if "--clear" in sys.argv:
        clear_demo_data(conn)
        return

    print("Clearing any previous demo seed rows (safe re-run)...")
    clear_demo_data(conn)

    companies = {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM companies").fetchall()}
    rwox_id, elasto_id = companies.get("Rwox"), companies.get("Elastohorse")
    if not rwox_id or not elasto_id:
        raise SystemExit(f"Expected companies 'Rwox' and 'Elastohorse' in the DB, found: {list(companies)}")

    n_orders = seed_orders(conn, rwox_id, elasto_id)
    n_proc = seed_procurement(conn, rwox_id, elasto_id)
    n_prod = seed_production(conn, rwox_id)

    print("=" * 60)
    print(f"Seeded {n_orders} demo orders, {n_proc} demo procurement rows, "
          f"{n_prod} demo production batches, spanning the last 10 months.")
    print("All tagged with '[demo seed]' in their notes field.")
    print("Reload the app's Home page to see it. To remove later:")
    print("  python scripts/seed_demo_data.py --clear")
    print("=" * 60)


if __name__ == "__main__":
    main()
