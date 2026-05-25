Reclaimr — Lightweight ERP for Rwox & Elastohorse
===============================================

Quick starter for a minimal ERP covering orders and procurement.

Features
- Orders entry form and table
- Procurement entry form and table
- Simple SQLite backend with seeded companies (`Rwox`, `Elastohorse`)

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

3. Start the app:

```bash
streamlit run app.py
```

Project layout
- `app.py` — Streamlit entrypoint and dashboard
- `db/schema.py` — SQLite schema + `init_db()` (auto-creates `db/erp.db`)
- `pages/1_orders.py` — Orders page (form + table)
- `pages/2_procurement.py` — Procurement page (form + table)

Notes & next steps
- Add export/import CSV, filtering, and basic auth as needed.
- Database is SQLite for simplicity; consider Postgres for multi-user setups.
