from db.connection import connect

COMPANIES = [
    ("Rwox", "manufacturing"),
    ("Elastohorse", "trading"),
]


def create_tables(conn) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS companies (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            business_type TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            company_id INTEGER NOT NULL,
            customer_name TEXT NOT NULL,
            product TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            quantity_unit TEXT NOT NULL DEFAULT 'units',
            rate REAL NOT NULL,
            rate_type TEXT NOT NULL DEFAULT 'per_unit',
            expected_dispatch_date TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'localtime', 'YYYY-MM-DD HH24:MI:SS'),
            FOREIGN KEY (company_id) REFERENCES companies(id)
        );

        CREATE TABLE IF NOT EXISTS procurement (
            id SERIAL PRIMARY KEY,
            company_id INTEGER NOT NULL,
            item TEXT NOT NULL,
            quantity REAL NOT NULL,
            quantity_unit TEXT NOT NULL DEFAULT 'kg',
            unit_cost REAL NOT NULL,
            supplier TEXT,
            purchase_date TEXT NOT NULL,
            notes TEXT,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        );

        CREATE TABLE IF NOT EXISTS production (
            id SERIAL PRIMARY KEY,
            company_id INTEGER NOT NULL,
            product TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        );

        CREATE TABLE IF NOT EXISTS exports (
            id SERIAL PRIMARY KEY,
            company_id INTEGER NOT NULL,
            customer_name TEXT NOT NULL,
            country TEXT NOT NULL,
            product TEXT NOT NULL,
            quantity REAL NOT NULL,
            quantity_unit TEXT NOT NULL DEFAULT 'kg',
            pack_size TEXT NOT NULL DEFAULT 'bulk',
            rate REAL NOT NULL,
            rate_type TEXT NOT NULL DEFAULT 'per_unit',
            currency TEXT NOT NULL DEFAULT 'USD',
            exchange_rate REAL NOT NULL DEFAULT 1,
            inr_equivalent REAL NOT NULL,
            order_date TEXT NOT NULL,
            expected_dispatch_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'received',
            shipping_terms TEXT NOT NULL DEFAULT 'FOB',
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT to_char(now(), 'YYYY-MM-DD HH24:MI:SS'),
            FOREIGN KEY (company_id) REFERENCES companies(id)
        );

        CREATE TABLE IF NOT EXISTS production_logs (
            id SERIAL PRIMARY KEY,
            company_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            batch_ref TEXT NOT NULL,
            purple_material_kg REAL NOT NULL DEFAULT 0,
            wax_kg REAL NOT NULL DEFAULT 0,
            mc_kg REAL NOT NULL DEFAULT 0,
            output_kg REAL NOT NULL DEFAULT 0,
            machine_start TEXT,
            machine_end TEXT,
            run_time_minutes INTEGER,
            bottles_1kg INTEGER,
            bottles_5kg INTEGER,
            cartons_1kg REAL,
            cartons_5kg REAL,
            rejections_kg REAL,
            order_id INTEGER,
            temperature_log TEXT,
            additional_notes TEXT,
            created_at TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'localtime', 'YYYY-MM-DD HH24:MI:SS'),
            purple_material_cost REAL,
            wax_cost REAL,
            mc_cost REAL,
            overhead_cost REAL,
            total_batch_cost REAL,
            cost_per_kg REAL,
            FOREIGN KEY (company_id) REFERENCES companies(id),
            FOREIGN KEY (order_id) REFERENCES orders(id)
        );

        CREATE TABLE IF NOT EXISTS batch_allocations (
            id SERIAL PRIMARY KEY,
            batch_id INTEGER NOT NULL,
            order_id INTEGER NOT NULL,
            allocated_kg REAL NOT NULL,
            created_at TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'localtime', 'YYYY-MM-DD HH24:MI:SS'),
            FOREIGN KEY (batch_id) REFERENCES production_logs(id),
            FOREIGN KEY (order_id) REFERENCES orders(id)
        );

        CREATE TABLE IF NOT EXISTS batch_complaints (
            id SERIAL PRIMARY KEY,
            batch_id INTEGER NOT NULL,
            order_id INTEGER,
            customer_name TEXT,
            date TEXT NOT NULL,
            issue_type TEXT NOT NULL,
            description TEXT NOT NULL,
            quantity_affected REAL,
            physical_return INTEGER NOT NULL DEFAULT 0,
            quantity_returned REAL,
            initial_action TEXT NOT NULL,
            logged_by TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            created_at TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'localtime', 'YYYY-MM-DD HH24:MI:SS'),
            FOREIGN KEY (batch_id) REFERENCES production_logs(id),
            FOREIGN KEY (order_id) REFERENCES orders(id)
        );

        CREATE TABLE IF NOT EXISTS batch_complaint_updates (
            id SERIAL PRIMARY KEY,
            complaint_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            update_description TEXT NOT NULL,
            action_taken TEXT NOT NULL,
            status TEXT NOT NULL,
            logged_by TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'localtime', 'YYYY-MM-DD HH24:MI:SS'),
            FOREIGN KEY (complaint_id) REFERENCES batch_complaints(id)
        );

        CREATE TABLE IF NOT EXISTS financial_snapshots (
            id SERIAL PRIMARY KEY,
            company_id INTEGER NOT NULL,
            snapshot_date TEXT NOT NULL,
            cash_balance REAL,
            receivables REAL,
            payables REAL,
            equity REAL,
            notes TEXT,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        );

        CREATE TABLE IF NOT EXISTS receivables (
            id SERIAL PRIMARY KEY,
            customer_name TEXT NOT NULL,
            company TEXT NOT NULL,
            reference TEXT,
            amount REAL NOT NULL,
            date TEXT NOT NULL,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'outstanding',
            created_at TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'localtime', 'YYYY-MM-DD HH24:MI:SS'),
            last_contacted TEXT
        );

        CREATE TABLE IF NOT EXISTS payables (
            id SERIAL PRIMARY KEY,
            vendor_name TEXT NOT NULL,
            description TEXT,
            amount REAL NOT NULL,
            date TEXT NOT NULL,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'outstanding',
            created_at TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'localtime', 'YYYY-MM-DD HH24:MI:SS')
        );

        CREATE TABLE IF NOT EXISTS payments (
            id SERIAL PRIMARY KEY,
            type TEXT NOT NULL,
            reference_id INTEGER NOT NULL,
            payment_date TEXT NOT NULL,
            amount_paid REAL NOT NULL,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'localtime', 'YYYY-MM-DD HH24:MI:SS')
        );

        CREATE TABLE IF NOT EXISTS intercompany_transactions (
            id SERIAL PRIMARY KEY,
            from_company_id INTEGER NOT NULL,
            to_company_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            transaction_date TEXT NOT NULL,
            description TEXT,
            FOREIGN KEY (from_company_id) REFERENCES companies(id),
            FOREIGN KEY (to_company_id) REFERENCES companies(id)
        );

        CREATE TABLE IF NOT EXISTS stock_adjustments (
            id SERIAL PRIMARY KEY,
            date TEXT NOT NULL,
            company_id INTEGER NOT NULL,
            item_type TEXT NOT NULL,
            item_name TEXT NOT NULL,
            adjustment_qty REAL NOT NULL,
            reason TEXT,
            created_at TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'localtime', 'YYYY-MM-DD HH24:MI:SS'),
            FOREIGN KEY (company_id) REFERENCES companies(id)
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """
    )
    conn.commit()


def migrate_db(conn) -> None:
    """Add any columns that might be missing on an older Postgres schema."""
    alter_statements = [
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS quantity_unit TEXT NOT NULL DEFAULT 'units'",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS rate_type TEXT NOT NULL DEFAULT 'per_unit'",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'received'",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS notes TEXT",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS transport_via TEXT",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS dispatch_time TEXT",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_deadline TEXT",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS batch_reference TEXT",
        "ALTER TABLE procurement ADD COLUMN IF NOT EXISTS quantity_unit TEXT NOT NULL DEFAULT 'kg'",
        "ALTER TABLE procurement ADD COLUMN IF NOT EXISTS notes TEXT",
        "ALTER TABLE procurement ADD COLUMN IF NOT EXISTS price_type TEXT NOT NULL DEFAULT 'per_unit'",
        "ALTER TABLE production_logs ADD COLUMN IF NOT EXISTS purple_material_cost REAL",
        "ALTER TABLE production_logs ADD COLUMN IF NOT EXISTS wax_cost REAL",
        "ALTER TABLE production_logs ADD COLUMN IF NOT EXISTS mc_cost REAL",
        "ALTER TABLE production_logs ADD COLUMN IF NOT EXISTS overhead_cost REAL",
        "ALTER TABLE production_logs ADD COLUMN IF NOT EXISTS total_batch_cost REAL",
        "ALTER TABLE production_logs ADD COLUMN IF NOT EXISTS cost_per_kg REAL",
        "ALTER TABLE receivables ADD COLUMN IF NOT EXISTS last_contacted TEXT",
    ]
    cur = conn.cursor()
    for sql in alter_statements:
        cur.execute(sql)
    conn.commit()


def seed_companies(conn) -> None:
    cur = conn.cursor()
    cur.executemany(
        "INSERT INTO companies (name, business_type) VALUES (%s, %s) ON CONFLICT (name) DO NOTHING",
        COMPANIES,
    )
    conn.commit()


def init_db(database_url: str):
    connection = connect(database_url)
    create_tables(connection)
    migrate_db(connection)
    seed_companies(connection)
    connection.commit()
    return connection


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()
    url = os.getenv("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is not set")
    init_db(url)
    print("Initialized PostgreSQL schema")
