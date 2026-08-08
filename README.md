Reclaimr — Lightweight ERP for Rwox & Elastohorse
===============================================

Quick starter for a minimal ERP covering orders and procurement.

Features
- Orders entry form and table
- Procurement entry form and table
- PostgreSQL backend with seeded companies (`Rwox`, `Elastohorse`)

Run locally

1. Create a virtual environment (recommended):

```bash
python -m venv .venv
.
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set `DATABASE_URL` in `.env` (see `.env.example`) to point at your Postgres instance.

4. Start the app:

```bash
streamlit run app.py
```

Project layout
- `app.py` — Streamlit entrypoint and dashboard
- `db/schema.py` — PostgreSQL schema + `init_db()` (creates tables in the DB at `DATABASE_URL` if they don't exist)
- `db/connection.py` — thin wrapper so the rest of the app can keep calling `conn.execute(...).fetchone()/.fetchall()` the way it did against `sqlite3.Connection`, backed by psycopg2
- `scripts/migrate_to_postgres.py` — one-time migration of an old local `db/erp.db` SQLite file into Postgres
- `pages/1_orders.py` — Orders page (form + table)
- `pages/2_procurement.py` — Procurement page (form + table)

Notes & next steps
- Add export/import CSV, filtering, and basic auth as needed.
- Database is PostgreSQL (`DATABASE_URL`); `DB_PATH`/local SQLite is no longer used.
