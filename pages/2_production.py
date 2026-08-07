import os
import json
import math
import streamlit as st
import pandas as pd
from datetime import date as date_type, time as time_type, datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq
from db.schema import init_db
from utils.voice import transcribe_audio
from utils.export import export_to_excel, export_to_pdf


@st.cache_resource
def _get_conn():
    return init_db(Path("db") / "erp.db")


_WARM_CSS = (
    "<style>"
    "@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600&display=swap');"
    "* { font-family: 'DM Sans', sans-serif !important; }"
    "[class*='material-symbols'] { font-family: 'Material Symbols Rounded' !important; }"
    "[data-testid='metric-container']{background:#FFF8F0;border:1px solid #E8D5B7;"
    "border-radius:10px;padding:14px 18px}"
    "[data-testid='stMetricValue']{color:#2C2218}"
    "[data-testid='stMetricLabel']{color:#8B6A45}"
    "hr{border-color:#E8D5B7!important}"
    "h1{border-bottom:3px solid #C17F3E;padding-bottom:6px;display:inline-block}"
    "h2,h3{color:#2C2218}"
    "[data-testid='stDataFrame'] th{background:#FFF8F0!important;color:#2C2218!important;"
    "border:1px solid #E8D5B7!important}"
    "[data-testid='stDataFrame'] td{border-color:#E8D5B7!important}"
    "div[data-baseweb='input']{border:1px solid #C5A882!important;border-radius:6px!important}div[data-baseweb='textarea']{border:1px solid #C5A882!important;border-radius:6px!important}div[data-baseweb='select'] > div:first-child{border:1px solid #C5A882!important;border-radius:6px!important}"
    "[data-testid='stSidebarNav']{display:none!important}"
    "[data-testid='stSidebarNavItems']{display:none!important}"
    ".block-container{padding-top:1rem!important;padding-bottom:1rem!important;overflow:visible!important}"
    "header{display:none!important}"
    "details[data-testid='stExpander'] summary span:first-of-type{font-family:'Material Symbols Rounded'!important;font-style:normal!important}"
    "</style>"
)
_DARK_CSS = (
    "<style>"
    "@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600&display=swap');"
    "* { font-family: 'DM Sans', sans-serif !important; }"
    "[class*='material-symbols'] { font-family: 'Material Symbols Rounded' !important; }"
    "[data-testid='stAppViewContainer']{background:#1A1410!important}"
    "[data-testid='stHeader']{background:#1A1410!important}"
    "[data-testid='metric-container']{background:#2C2218!important;border:1px solid #4A3728!important;"
    "border-radius:10px;padding:14px 18px}"
    "[data-testid='stMetricValue']{color:#F5E6D3!important}"
    "[data-testid='stMetricLabel']{color:#C4A882!important}"
    "[data-testid='stSidebar']{background:#1E160E!important}"
    "hr{border-color:#4A3728!important}"
    "h1{border-bottom:3px solid #C17F3E;padding-bottom:6px;display:inline-block;color:#F5E6D3!important}"
    "h2,h3{color:#F5E6D3!important}"
    "[data-testid='stDataFrame'] th{background:#2C2218!important;color:#F5E6D3!important;"
    "border:1px solid #4A3728!important}"
    "[data-testid='stDataFrame'] td{border-color:#4A3728!important}"
    "div[data-baseweb='input']{border:1px solid #4A3728!important;border-radius:6px!important;background:#231C14!important}"
    "div[data-baseweb='input'] input{background:#231C14!important;color:#F5E6D3!important}"
    "div[data-baseweb='textarea']{border:1px solid #4A3728!important;border-radius:6px!important;background:#231C14!important}"
    "div[data-baseweb='textarea'] textarea{background:#231C14!important;color:#F5E6D3!important}"
    "div[data-baseweb='select'] > div:first-child{border:1px solid #4A3728!important;border-radius:6px!important;background:#231C14!important}"
    "[data-testid='stForm']{background:#2C2218!important;border-color:#4A3728!important}"
    "[data-testid='stExpander'] details{background:#2C2218!important;border-color:#4A3728!important}"
    "[data-testid='stSidebarNav']{display:none!important}"
    "[data-testid='stSidebarNavItems']{display:none!important}"
    ".block-container{padding-top:1rem!important;padding-bottom:1rem!important;overflow:visible!important}"
    "header{display:none!important}"
    "details[data-testid='stExpander'] summary span:first-of-type{font-family:'Material Symbols Rounded'!important;font-style:normal!important}"
    "</style>"
)

TABLE_CSS = (
    "<style>"
    ".orders-table{width:100%;border-collapse:collapse;font-size:14px;margin-bottom:16px}"
    ".orders-table th,.orders-table td{border:1px solid #E8D5B7;padding:8px 12px;text-align:left;vertical-align:middle}"
    ".orders-table thead tr{background:#FFF0DC;color:#2C2218;font-weight:600}"
    ".orders-table tbody tr:nth-child(even){background:#FFF8F0}"
    ".orders-table tbody tr:hover{background:#FFEDD5}"
    ".act-btn{display:inline-block;padding:3px 0;margin:0 2px;min-width:38px;text-align:center;border:1px solid #E8D5B7;"
    "border-radius:4px;text-decoration:none;color:#2C2218;font-size:12px;white-space:nowrap}"
    ".act-btn:hover{background:#FFF0DC;text-decoration:none;color:#2C2218}"
    ".act-btn.del{border-color:#C0392B;color:#C0392B}"
    ".act-btn.del:hover{background:#FFF0EE}"
    "</style>"
)


def _order_options(conn, company_id):
    rows = conn.execute(
        "SELECT id, customer_name, product FROM orders WHERE company_id = ? ORDER BY id DESC",
        (company_id,),
    ).fetchall()
    opts = {"(None)": None}
    for r in rows:
        opts[f"#{r['id']}, {r['customer_name']}, {r['product']}"] = r["id"]
    return opts


def _batch_options(conn, company_id):
    rows = conn.execute(
        "SELECT id, batch_ref, date FROM production_logs WHERE company_id = ? ORDER BY date DESC, id DESC",
        (company_id,),
    ).fetchall()
    return {f"{r['batch_ref']} ({r['date']})": r["id"] for r in rows}


def _batch_allocations(conn, batch_id):
    rows = conn.execute(
        "SELECT order_id, allocated_kg FROM batch_allocations WHERE batch_id = ?", (batch_id,)
    ).fetchall()
    return {r["order_id"]: r["allocated_kg"] for r in rows}


def _orders_linked_to_batch(conn, batch_id):
    rows = conn.execute(
        """SELECT DISTINCT o.id, o.customer_name, o.product
           FROM orders o
           WHERE o.id IN (
               SELECT order_id FROM batch_allocations WHERE batch_id = ?
               UNION
               SELECT order_id FROM production_logs WHERE id = ? AND order_id IS NOT NULL
           )
           ORDER BY o.id DESC""",
        (batch_id, batch_id),
    ).fetchall()
    return rows


def _latest_procurement_price(conn, company_id, item_keyword):
    row = conn.execute(
        """SELECT unit_cost FROM procurement
           WHERE company_id = ? AND LOWER(item) LIKE LOWER(?) AND price_type = 'per_unit'
           ORDER BY purchase_date DESC, id DESC LIMIT 1""",
        (company_id, f"%{item_keyword}%"),
    ).fetchone()
    return row["unit_cost"] if row else None


def _batch_revenue(conn, batch_id):
    rows = conn.execute(
        """SELECT ba.allocated_kg, o.rate, o.rate_type
           FROM batch_allocations ba
           JOIN orders o ON ba.order_id = o.id
           WHERE ba.batch_id = ?""",
        (batch_id,),
    ).fetchall()
    if rows:
        return sum(r["allocated_kg"] * r["rate"] for r in rows)
    row = conn.execute(
        """SELECT pl.output_kg, o.rate, o.rate_type
           FROM production_logs pl JOIN orders o ON pl.order_id = o.id
           WHERE pl.id = ?""",
        (batch_id,),
    ).fetchone()
    if row:
        return row["output_kg"] * row["rate"]
    return None


def _parse_time(t_str):
    if not t_str:
        return None
    try:
        parts = t_str.split(":")
        return time_type(int(parts[0]), int(parts[1]))
    except Exception:
        return None


def _run_time_label(start, end):
    if not start or not end:
        return None
    s = datetime.combine(date_type.today(), start)
    e = datetime.combine(date_type.today(), end)
    if e <= s:
        e += timedelta(days=1)
    mins = int((e - s).total_seconds() / 60)
    return mins, f"{mins // 60}h {mins % 60}m"


def _inr(val):
    return f"₹{val:,.2f}"


def _ensure_tables(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS batch_allocations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL,
            order_id INTEGER NOT NULL,
            allocated_kg REAL NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS batch_complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS batch_complaint_updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            update_description TEXT NOT NULL,
            action_taken TEXT NOT NULL,
            status TEXT NOT NULL,
            logged_by TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS production_cost_edits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL,
            edited_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            purple_cost REAL,
            wax_cost REAL,
            mc_cost REAL,
            overhead_cost REAL,
            total_cost REAL,
            cost_per_kg REAL
        );
    """)
    for sql in [
        "ALTER TABLE production_logs ADD COLUMN purple_material_cost REAL",
        "ALTER TABLE production_logs ADD COLUMN wax_cost REAL",
        "ALTER TABLE production_logs ADD COLUMN mc_cost REAL",
        "ALTER TABLE production_logs ADD COLUMN overhead_cost REAL",
        "ALTER TABLE production_logs ADD COLUMN total_batch_cost REAL",
        "ALTER TABLE production_logs ADD COLUMN cost_per_kg REAL",
    ]:
        try:
            conn.execute(sql)
        except Exception:
            pass
    conn.commit()


def _extract_production_from_voice(text: str):
    load_dotenv()
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None
    try:
        client = Groq(api_key=api_key)
        resp = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Extract production batch details from this spoken text and return ONLY a JSON object "
                        "with these exact keys: batch_ref, date, purple_kg, wax_kg, mc_kg. "
                        "If any field is not mentioned set it to null. "
                        "date must be in YYYY-MM-DD format if mentioned. "
                        "purple_kg, wax_kg, mc_kg must be numeric (kg values)."
                    ),
                },
                {"role": "user", "content": text},
            ],
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)
    except Exception:
        return None


_LOGO_HTML = (
    "<div style='padding:12px 16px 8px 16px;display:flex;align-items:center;gap:10px'>"
    "<svg width='30' height='30' viewBox='0 0 100 100' xmlns='http://www.w3.org/2000/svg'>"
    "<path d='M 50 10 A 40 40 0 1 0 85 65' fill='none' stroke='#C17F3E' stroke-width='7' stroke-linecap='round'/>"
    "<polygon points='85,50 95,68 75,68' fill='#C17F3E'/>"
    "<circle cx='50' cy='50' r='8' fill='#C17F3E'/>"
    "<circle cx='50' cy='50' r='3.5' fill='#FDFAF6'/>"
    "</svg>"
    "<span style='font-family:DM Sans,sans-serif;font-size:16px;font-weight:700;color:#C17F3E;letter-spacing:0.02em'>Reclaimr</span>"
    "</div>"
)


def render_production_page(conn):
    _ensure_tables(conn)
    st.markdown(_DARK_CSS if st.session_state.get("dark_mode") else _WARM_CSS, unsafe_allow_html=True)
    st.header("Production")
    st.caption("Daily production logs give you visibility into output, quality, and whether committed delivery dates are still on track.")

    rwox = conn.execute("SELECT id FROM companies WHERE name = 'Rwox'").fetchone()
    if not rwox:
        st.error("Rwox company not found.")
        return
    company_id = rwox["id"]

    # ── Handle action params ───────────────────────────────────────────────────
    params = st.query_params
    if "prod_action" in params:
        action = params.get("prod_action")
        try:
            entry_id = int(params.get("prod_id", 0))
        except (ValueError, TypeError):
            entry_id = 0
        if action == "edit" and entry_id:
            st.session_state["editing_prod_id"] = entry_id
            st.session_state["confirm_del_prod_id"] = None
        elif action == "del" and entry_id:
            st.session_state["confirm_del_prod_id"] = entry_id
        st.query_params.clear()
        st.rerun()

    # ── Monthly summary ────────────────────────────────────────────────────────
    row = conn.execute(
        "SELECT COALESCE(SUM(output_kg),0), COALESCE(SUM(cartons_1kg),0), COALESCE(SUM(cartons_5kg),0), "
        "COALESCE(SUM(total_batch_cost),0) "
        "FROM production_logs WHERE company_id = ? "
        "AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now', 'localtime')",
        (company_id,),
    ).fetchone()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Output This Month (kg)", f"{row[0]:,.1f}")
    c2.metric("1 kg Cartons Packed", int(row[1]))
    c3.metric("5 kg Cartons Packed", int(row[2]))
    c4.metric("Production Cost This Month", _inr(row[3]) if row[3] else "—")
    st.divider()

    # ── Edit form ──────────────────────────────────────────────────────────────
    editing_id = st.session_state.get("editing_prod_id")
    if editing_id:
        entry = conn.execute(
            "SELECT * FROM production_logs WHERE id = ?", (editing_id,)
        ).fetchone()
        if entry:
            st.subheader(f"Editing Entry #{editing_id}")
            order_opts = _order_options(conn, company_id)
            saved_temps = json.loads(entry["temperature_log"]) if entry["temperature_log"] else []
            existing_allocs = _batch_allocations(conn, editing_id)
            non_none_order_opts = {k: v for k, v in order_opts.items() if v is not None}

            # Pre-compute auto costs for captions
            p_price = _latest_procurement_price(conn, company_id, "purple")
            w_price = _latest_procurement_price(conn, company_id, "wax")
            m_price = _latest_procurement_price(conn, company_id, "mc")
            e_purple_val = float(entry["purple_material_kg"])
            e_wax_val = float(entry["wax_kg"])
            e_mc_val = float(entry["mc_kg"])
            auto_purple_cost = round(e_purple_val * p_price, 2) if p_price else None
            auto_wax_cost = round(e_wax_val * w_price, 2) if w_price else None
            auto_mc_cost = round(e_mc_val * m_price, 2) if m_price else None

            with st.form("edit_prod_form"):
                ec1, ec2 = st.columns(2)
                with ec1:
                    e_date = st.date_input("Date", value=date_type.fromisoformat(entry["date"]))
                with ec2:
                    e_batch = st.text_input("Batch reference", value=entry["batch_ref"])

                st.markdown("**Materials used (kg)**")
                ep, ew, em = st.columns(3)
                with ep:
                    e_purple = st.number_input("Purple Material", min_value=0.0, value=e_purple_val, step=0.5, format="%.2f")
                with ew:
                    e_wax = st.number_input("Wax", min_value=0.0, value=e_wax_val, step=0.5, format="%.2f")
                with em:
                    e_mc = st.number_input("MC", min_value=0.0, value=e_mc_val, step=0.5, format="%.2f")
                e_output = round((e_purple + e_wax + e_mc) * 0.9, 2)
                st.text_input("Output kg (auto)", value=str(e_output), disabled=True)

                st.markdown("**Machine timing**")
                es1, es2 = st.columns(2)
                with es1:
                    e_use_start = st.checkbox("Set start time", value=bool(entry["machine_start"]))
                    e_start = st.time_input("Start", value=_parse_time(entry["machine_start"]) or time_type(8, 0), disabled=not e_use_start)
                with es2:
                    e_use_end = st.checkbox("Set end time", value=bool(entry["machine_end"]))
                    e_end = st.time_input("End", value=_parse_time(entry["machine_end"]) or time_type(17, 0), disabled=not e_use_end)

                st.markdown("**Bottles & Cartons**")
                eb1, eb5 = st.columns(2)
                with eb1:
                    e_b1 = st.number_input("1kg bottles", min_value=0, value=int(entry["bottles_1kg"] or 0), step=1)
                with eb5:
                    e_b5 = st.number_input("5kg bottles", min_value=0, value=int(entry["bottles_5kg"] or 0), step=1)
                ecc1, ecc5 = st.columns(2)
                with ecc1:
                    st.text_input("1kg cartons (auto)", value=str(math.floor(e_b1 / 20)), disabled=True)
                with ecc5:
                    st.text_input("5kg cartons (auto)", value=str(math.floor(e_b5 / 20)), disabled=True)

                e_rej = st.number_input("Rejections (kg)", min_value=0.0, value=float(entry["rejections_kg"] or 0), step=0.1, format="%.2f")

                st.markdown("**Linked orders**")
                existing_alloc_labels = [k for k, v in non_none_order_opts.items() if v in existing_allocs]
                e_orders = st.multiselect(
                    "Orders linked to this batch",
                    list(non_none_order_opts.keys()),
                    default=existing_alloc_labels,
                )

                if existing_allocs:
                    st.markdown("**Allocations (kg per order)**")
                    for oid, akg in existing_allocs.items():
                        order_label = next((k for k, v in order_opts.items() if v == oid), f"Order #{oid}")
                        st.number_input(
                            f"kg → {order_label}",
                            min_value=0.0, value=float(akg), step=0.5, format="%.2f",
                            key=f"e_alloc_{oid}",
                        )
                    st.caption("Newly selected orders will be added with 0 kg, save and re-edit to set allocations.")

                # ── Batch Costing (edit) ───────────────────────────────────────
                st.markdown("**Batch Costing**")
                ecp, ecw, ecm = st.columns(3)
                with ecp:
                    e_purple_cost = st.number_input(
                        "Purple cost (₹)",
                        min_value=0.0,
                        value=float(entry["purple_material_cost"] or auto_purple_cost or 0.0),
                        step=100.0, format="%.2f", key="e_pcost",
                    )
                    if auto_purple_cost:
                        st.caption(f"Auto: {_inr(auto_purple_cost)}")
                with ecw:
                    e_wax_cost = st.number_input(
                        "Wax cost (₹)",
                        min_value=0.0,
                        value=float(entry["wax_cost"] or auto_wax_cost or 0.0),
                        step=100.0, format="%.2f", key="e_wcost",
                    )
                    if auto_wax_cost:
                        st.caption(f"Auto: {_inr(auto_wax_cost)}")
                with ecm:
                    e_mc_cost = st.number_input(
                        "MC cost (₹)",
                        min_value=0.0,
                        value=float(entry["mc_cost"] or auto_mc_cost or 0.0),
                        step=100.0, format="%.2f", key="e_mcost",
                    )
                    if auto_mc_cost:
                        st.caption(f"Auto: {_inr(auto_mc_cost)}")
                e_overhead = st.number_input(
                    "Overhead cost (₹): labour, utilities, packaging",
                    min_value=0.0,
                    value=float(entry["overhead_cost"] or 0.0),
                    step=100.0, format="%.2f", key="e_overhead",
                )
                e_total_cost = e_purple_cost + e_wax_cost + e_mc_cost + e_overhead
                e_cpkg = round(e_total_cost / e_output, 2) if e_output > 0 else 0.0
                em1, em2 = st.columns(2)
                em1.metric("Total Batch Cost", _inr(e_total_cost))
                em2.metric("Cost / kg", _inr(e_cpkg))

                st.markdown("**Temperature Log**: one reading per line: `HH:MM | temp°C | note`")
                temp_str = "\n".join(
                    f"{t['time']} | {t['temp']} | {t.get('note','')}"
                    for t in saved_temps
                ) if saved_temps else ""
                e_temp_text = st.text_area("Temperature readings", value=temp_str, height=120)
                e_notes = st.text_area("Notes", value=entry["additional_notes"] or "")

                sv, ca, _ = st.columns([1, 1, 6])
                with sv:
                    save_btn = st.form_submit_button("Save changes", type="primary")
                with ca:
                    cancel_btn = st.form_submit_button("Cancel")

            # Cost edit history (outside form)
            cost_edits = conn.execute(
                "SELECT * FROM production_cost_edits WHERE batch_id = ? ORDER BY edited_at DESC",
                (editing_id,),
            ).fetchall()
            if cost_edits:
                with st.expander("Cost edit history"):
                    for ce in cost_edits:
                        st.markdown(
                            f"**{ce['edited_at']}**: Purple: {_inr(ce['purple_cost'] or 0)}, "
                            f"Wax: {_inr(ce['wax_cost'] or 0)}, MC: {_inr(ce['mc_cost'] or 0)}, "
                            f"Overhead: {_inr(ce['overhead_cost'] or 0)}, "
                            f"Total: {_inr(ce['total_cost'] or 0)}, "
                            f"Cost/kg: {_inr(ce['cost_per_kg'] or 0)}"
                        )

            if save_btn:
                if not e_batch.strip():
                    st.error("Batch reference is required.")
                else:
                    e_c1 = math.floor(e_b1 / 20)
                    e_c5 = math.floor(e_b5 / 20)
                    e_start_str = str(e_start) if e_use_start else None
                    e_end_str = str(e_end) if e_use_end else None
                    e_run = None
                    if e_use_start and e_use_end:
                        rt = _run_time_label(e_start, e_end)
                        if rt:
                            e_run = rt[0]
                    e_temps = []
                    for line in e_temp_text.strip().split("\n"):
                        if "|" in line:
                            parts = [p.strip() for p in line.split("|")]
                            if len(parts) >= 2:
                                try:
                                    e_temps.append({"time": parts[0], "temp": float(parts[1]), "note": parts[2] if len(parts) > 2 else ""})
                                except ValueError:
                                    pass

                    primary_order_id = non_none_order_opts.get(e_orders[0]) if e_orders else None
                    e_total_cost_final = e_purple_cost + e_wax_cost + e_mc_cost + e_overhead
                    e_cpkg_final = round(e_total_cost_final / e_output, 2) if e_output > 0 else 0.0

                    # Log cost edit if costs changed
                    old_total = float(entry["total_batch_cost"] or 0)
                    if abs(e_total_cost_final - old_total) > 0.01:
                        conn.execute(
                            "INSERT INTO production_cost_edits "
                            "(batch_id, purple_cost, wax_cost, mc_cost, overhead_cost, total_cost, cost_per_kg) "
                            "VALUES (?,?,?,?,?,?,?)",
                            (editing_id, e_purple_cost, e_wax_cost, e_mc_cost, e_overhead,
                             e_total_cost_final, e_cpkg_final),
                        )

                    conn.execute(
                        "UPDATE production_logs SET date=?, batch_ref=?, purple_material_kg=?, wax_kg=?, "
                        "mc_kg=?, output_kg=?, machine_start=?, machine_end=?, run_time_minutes=?, "
                        "bottles_1kg=?, bottles_5kg=?, cartons_1kg=?, cartons_5kg=?, rejections_kg=?, "
                        "order_id=?, temperature_log=?, additional_notes=?, "
                        "purple_material_cost=?, wax_cost=?, mc_cost=?, overhead_cost=?, "
                        "total_batch_cost=?, cost_per_kg=? WHERE id=?",
                        (e_date.isoformat(), e_batch.strip(), e_purple, e_wax, e_mc, e_output,
                         e_start_str, e_end_str, e_run,
                         e_b1 or None, e_b5 or None, e_c1 or None, e_c5 or None,
                         e_rej or None, primary_order_id,
                         json.dumps(e_temps) if e_temps else None,
                         e_notes.strip() or None,
                         e_purple_cost or None, e_wax_cost or None, e_mc_cost or None,
                         e_overhead or None, e_total_cost_final or None, e_cpkg_final or None,
                         editing_id),
                    )

                    conn.execute("DELETE FROM batch_allocations WHERE batch_id = ?", (editing_id,))
                    for ol in e_orders:
                        oid = non_none_order_opts.get(ol)
                        if oid:
                            alloc_kg = st.session_state.get(f"e_alloc_{oid}", existing_allocs.get(oid, 0.0))
                            conn.execute(
                                "INSERT INTO batch_allocations (batch_id, order_id, allocated_kg) VALUES (?,?,?)",
                                (editing_id, oid, float(alloc_kg)),
                            )

                    conn.commit()
                    st.session_state["editing_prod_id"] = None
                    st.rerun()
            if cancel_btn:
                st.session_state["editing_prod_id"] = None
                st.rerun()
            st.divider()

    # ── New entry ──────────────────────────────────────────────────────────────
    with st.expander("🎤 Voice Input — speak to auto-fill (optional)"):
        audio_value = st.audio_input("🎤 Speak your production log")
        st.caption("Example: 'Batch B-001, 200 kg purple, 80 kg wax, 20 kg MC'")
        if audio_value is not None:
            _audio_hash = hash(audio_value.getvalue())
            if _audio_hash != st.session_state.get("voice_prod_audio_hash"):
                st.session_state["voice_prod_audio_hash"] = _audio_hash
                with st.spinner("Processing voice input with AI..."):
                    _raw = transcribe_audio(audio_value)
                    _ext = _extract_production_from_voice(_raw) if _raw else None
                if _ext:
                    st.session_state["voice_prod_prefill"] = _ext
                    st.session_state["voice_prod_raw"] = _raw
                else:
                    st.session_state["voice_prod_error"] = True
                st.rerun()
        if st.session_state.get("voice_prod_error"):
            st.error("Could not extract details — fill the form manually.")
            st.session_state.pop("voice_prod_error", None)
        _vp = st.session_state.get("voice_prod_prefill", {})
        if _vp:
            st.success(f'Extracted from: "{st.session_state.get("voice_prod_raw", "")}"')
            vc1, vc2, vc3, vc4 = st.columns(4)
            vc1.metric("Batch Ref", _vp.get("batch_ref") or "—")
            vc2.metric("Purple (kg)", _vp.get("purple_kg") or "—")
            vc3.metric("Wax (kg)", _vp.get("wax_kg") or "—")
            vc4.metric("MC (kg)", _vp.get("mc_kg") or "—")
            ap_col, cl_col, _ = st.columns([1, 1, 4])
            with ap_col:
                if st.button("✓ Apply to form", key="apply_vprod", type="primary"):
                    if _vp.get("batch_ref"):
                        st.session_state["p_batch"] = str(_vp["batch_ref"])
                    for _fk, _sk in [("purple_kg", "p_purple"), ("wax_kg", "p_wax"), ("mc_kg", "p_mc")]:
                        try:
                            st.session_state[_sk] = float(_vp[_fk]) if _vp.get(_fk) else 0.0
                        except (ValueError, TypeError):
                            pass
                    if _vp.get("date"):
                        try:
                            st.session_state["p_date"] = date_type.fromisoformat(_vp["date"])
                        except (ValueError, TypeError):
                            pass
                    st.session_state.pop("voice_prod_prefill", None)
                    st.session_state.pop("voice_prod_raw", None)
                    st.rerun()
            with cl_col:
                if st.button("✕ Clear", key="clr_vprod"):
                    st.session_state.pop("voice_prod_prefill", None)
                    st.session_state.pop("voice_prod_raw", None)
                    st.rerun()

    st.subheader("Log a New Run")

    fd, fb = st.columns(2)
    with fd:
        prod_date = st.date_input("Date *", value=date_type.today(), key="p_date")
    with fb:
        batch_ref = st.text_input("Batch ref * (e.g. Batch-001)", key="p_batch")

    st.markdown("**Materials used (kg) \\***")
    fp, fw, fm = st.columns(3)
    with fp:
        purple_kg = st.number_input("Purple Material", min_value=0.0, value=0.0, step=0.5, format="%.2f", key="p_purple")
    with fw:
        wax_kg = st.number_input("Wax", min_value=0.0, value=0.0, step=0.5, format="%.2f", key="p_wax")
    with fm:
        mc_kg = st.number_input("MC", min_value=0.0, value=0.0, step=0.5, format="%.2f", key="p_mc")

    output_kg = round((purple_kg + wax_kg + mc_kg) * 0.9, 2)
    st.text_input("Output kg (auto: sum × 0.9)", value=str(output_kg), disabled=True, key="p_out")

    # ── Batch Costing (new entry) ──────────────────────────────────────────────
    with st.expander("Batch Costing", expanded=True):
        p_price = _latest_procurement_price(conn, company_id, "purple")
        w_price = _latest_procurement_price(conn, company_id, "wax")
        m_price = _latest_procurement_price(conn, company_id, "mc")

        auto_p_cost = round(purple_kg * p_price, 2) if p_price and purple_kg > 0 else None
        auto_w_cost = round(wax_kg * w_price, 2) if w_price and wax_kg > 0 else None
        auto_m_cost = round(mc_kg * m_price, 2) if m_price and mc_kg > 0 else None

        cc1, cc2, cc3 = st.columns(3)
        with cc1:
            if p_price and purple_kg > 0:
                st.markdown(f"**Purple:** {purple_kg} kg × {_inr(p_price)}/kg = **{_inr(auto_p_cost)}**")
            elif not p_price:
                st.warning("No procurement price found for Purple Material")
            purple_cost = st.number_input(
                "Purple cost (₹)", min_value=0.0,
                value=float(auto_p_cost or 0.0),
                step=100.0, format="%.2f", key="p_pcost",
            )
        with cc2:
            if w_price and wax_kg > 0:
                st.markdown(f"**Wax:** {wax_kg} kg × {_inr(w_price)}/kg = **{_inr(auto_w_cost)}**")
            elif not w_price:
                st.warning("No procurement price found for Wax")
            wax_cost = st.number_input(
                "Wax cost (₹)", min_value=0.0,
                value=float(auto_w_cost or 0.0),
                step=100.0, format="%.2f", key="p_wcost",
            )
        with cc3:
            if m_price and mc_kg > 0:
                st.markdown(f"**MC:** {mc_kg} kg × {_inr(m_price)}/kg = **{_inr(auto_m_cost)}**")
            elif not m_price:
                st.warning("No procurement price found for MC")
            mc_cost = st.number_input(
                "MC cost (₹)", min_value=0.0,
                value=float(auto_m_cost or 0.0),
                step=100.0, format="%.2f", key="p_mcost",
            )

        overhead_cost = st.number_input(
            "Overhead cost (₹): labour, utilities, packaging",
            min_value=0.0, value=0.0, step=100.0, format="%.2f", key="p_overhead",
            help="One manual field for all overhead: labour, electricity, packaging, etc.",
        )

        total_batch_cost = purple_cost + wax_cost + mc_cost + overhead_cost
        cost_per_kg = round(total_batch_cost / output_kg, 2) if output_kg > 0 else 0.0

        sm1, sm2, sm3 = st.columns(3)
        sm1.metric("Material Cost", _inr(purple_cost + wax_cost + mc_cost))
        sm2.metric("Total Batch Cost", _inr(total_batch_cost))
        sm3.metric("Cost / kg", _inr(cost_per_kg) if cost_per_kg else "—")

    with st.expander("Machine timing (optional, captures run duration)"):
        fs1, fs2 = st.columns(2)
        with fs1:
            use_start = st.checkbox("Set start time", key="p_use_start")
            machine_start = st.time_input("Start time", key="p_start", disabled=not use_start)
        with fs2:
            use_end = st.checkbox("Set end time", key="p_use_end")
            machine_end = st.time_input("End time", key="p_end", disabled=not use_end)

        run_time_mins = None
        if use_start and use_end:
            rt = _run_time_label(machine_start, machine_end)
            if rt:
                run_time_mins, label = rt
                overnight = " (overnight)" if machine_end < machine_start else ""
                st.text_input("Total run time", value=label + overnight, disabled=True, key="p_rt")

    with st.expander("Bottles & cartons (optional, auto-calculates cartons at 20 per box)"):
        fb1, fb5 = st.columns(2)
        with fb1:
            bottles_1kg = st.number_input("1kg bottles filled", min_value=0, value=0, step=1, key="p_b1")
        with fb5:
            bottles_5kg = st.number_input("5kg bottles filled", min_value=0, value=0, step=1, key="p_b5")
        cartons_1kg = math.floor(bottles_1kg / 20)
        cartons_5kg = math.floor(bottles_5kg / 20)
        fc1, fc5 = st.columns(2)
        with fc1:
            st.text_input("1kg cartons (÷20)", value=str(cartons_1kg), disabled=True, key="p_c1")
        with fc5:
            st.text_input("5kg cartons (÷20)", value=str(cartons_5kg), disabled=True, key="p_c5")

    with st.expander("Rejections & order allocations (optional)"):
        rejections_kg = st.number_input("Rejections (kg)", min_value=0.0, value=0.0, step=0.1, format="%.2f", key="p_rej")
        order_opts = _order_options(conn, company_id)
        non_none_labels = [k for k, v in order_opts.items() if v is not None]
        linked_orders = st.multiselect("Linked orders", non_none_labels, key="p_orders")

        if linked_orders:
            st.markdown("**Batch Allocation**: specify how many kg from this batch go to each order")
            for lo in linked_orders:
                oid = order_opts[lo]
                st.number_input(f"kg → {lo}", min_value=0.0, value=0.0, step=0.5, format="%.2f", key=f"alloc_{oid}")

            total_allocated = sum(
                st.session_state.get(f"alloc_{order_opts[lo]}", 0.0) for lo in linked_orders
            )
            if output_kg > 0 and total_allocated > output_kg:
                st.markdown(
                    f"<span style='color:#C0392B'>⚠ <b>{total_allocated:.1f} kg allocated</b> out of "
                    f"<b>{output_kg:.1f} kg</b> produced, over-allocated!</span>",
                    unsafe_allow_html=True,
                )
            elif output_kg > 0:
                st.info(f"{total_allocated:.1f} kg allocated out of {output_kg:.1f} kg produced")

        # Est. revenue + margin (if orders linked)
        if linked_orders and total_batch_cost > 0:
            est_revenue = sum(
                st.session_state.get(f"alloc_{order_opts[lo]}", 0.0) *
                (conn.execute("SELECT rate FROM orders WHERE id = ?", (order_opts[lo],)).fetchone() or {"rate": 0})["rate"]
                for lo in linked_orders
            )
            if est_revenue > 0:
                margin = round((est_revenue - total_batch_cost) / est_revenue * 100, 1)
                margin_color = "#1B7F4F" if margin >= 15 else ("#D97706" if margin >= 10 else "#C0392B")
                st.markdown(
                    f"Est. Revenue: **{_inr(est_revenue)}** · Est. Margin: "
                    f"<span style='color:{margin_color};font-weight:bold'>{margin}%</span>",
                    unsafe_allow_html=True,
                )

    with st.expander("Temperature log (optional, up to 6 readings)"):
        if "temp_row_ids" not in st.session_state:
            st.session_state["temp_row_ids"] = []
        if "temp_row_ctr" not in st.session_state:
            st.session_state["temp_row_ctr"] = 0

        for rid in list(st.session_state["temp_row_ids"]):
            tc, tt, tn, td = st.columns([1.2, 1, 3, 0.6])
            with tc:
                st.time_input("Time", key=f"tr_t_{rid}")
            with tt:
                st.number_input("°C", min_value=0.0, value=0.0, step=0.5, format="%.1f", key=f"tr_c_{rid}")
            with tn:
                st.text_input("Note", key=f"tr_n_{rid}")
            with td:
                st.markdown("<div style='padding-top:28px'>", unsafe_allow_html=True)
                if st.button("Del", key=f"tr_d_{rid}"):
                    st.session_state["temp_row_ids"].remove(rid)
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

        if len(st.session_state["temp_row_ids"]) < 6:
            if st.button("＋ Add Reading"):
                new_id = st.session_state["temp_row_ctr"]
                st.session_state["temp_row_ctr"] += 1
                st.session_state["temp_row_ids"].append(new_id)
                st.rerun()
        else:
            st.caption("Maximum 6 readings reached.")

    with st.expander("Additional details (optional)"):
        additional_notes = st.text_area("Process notes", key="p_additional", height=100)

    st.markdown("")
    if st.button("💾 Save Entry", type="primary"):
        if not batch_ref.strip():
            st.error("Batch reference is required.")
        elif purple_kg == 0 and wax_kg == 0 and mc_kg == 0:
            st.error("Enter at least one material quantity.")
        else:
            temp_log = []
            for rid in st.session_state.get("temp_row_ids", []):
                t_val = st.session_state.get(f"tr_t_{rid}")
                c_val = st.session_state.get(f"tr_c_{rid}", 0.0)
                n_val = st.session_state.get(f"tr_n_{rid}", "")
                if c_val and c_val > 0:
                    temp_log.append({"time": str(t_val), "temp": c_val, "note": n_val})

            start_str = str(machine_start) if use_start else None
            end_str = str(machine_end) if use_end else None

            linked_orders_val = st.session_state.get("p_orders", [])
            primary_order_id = order_opts.get(linked_orders_val[0]) if linked_orders_val else None

            p_cost_save = st.session_state.get("p_pcost", 0.0)
            w_cost_save = st.session_state.get("p_wcost", 0.0)
            m_cost_save = st.session_state.get("p_mcost", 0.0)
            o_cost_save = st.session_state.get("p_overhead", 0.0)
            total_save = p_cost_save + w_cost_save + m_cost_save + o_cost_save
            cpkg_save = round(total_save / output_kg, 2) if output_kg > 0 else 0.0

            conn.execute(
                "INSERT INTO production_logs (company_id, date, batch_ref, purple_material_kg, wax_kg, mc_kg, "
                "output_kg, machine_start, machine_end, run_time_minutes, bottles_1kg, bottles_5kg, "
                "cartons_1kg, cartons_5kg, rejections_kg, order_id, temperature_log, additional_notes, "
                "purple_material_cost, wax_cost, mc_cost, overhead_cost, total_batch_cost, cost_per_kg) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (company_id, prod_date.isoformat(), batch_ref.strip(),
                 purple_kg, wax_kg, mc_kg, output_kg,
                 start_str, end_str, run_time_mins,
                 bottles_1kg or None, bottles_5kg or None,
                 cartons_1kg or None, cartons_5kg or None,
                 rejections_kg or None, primary_order_id,
                 json.dumps(temp_log) if temp_log else None,
                 additional_notes.strip() or None,
                 p_cost_save or None, w_cost_save or None, m_cost_save or None,
                 o_cost_save or None, total_save or None, cpkg_save or None),
            )
            new_batch_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            for lo in linked_orders_val:
                oid = order_opts.get(lo)
                if oid:
                    alloc_kg = st.session_state.get(f"alloc_{oid}", 0.0)
                    conn.execute(
                        "INSERT INTO batch_allocations (batch_id, order_id, allocated_kg) VALUES (?,?,?)",
                        (new_batch_id, oid, float(alloc_kg)),
                    )

            conn.commit()
            st.session_state["temp_row_ids"] = []
            for lo in linked_orders_val:
                oid = order_opts.get(lo)
                if oid:
                    st.session_state.pop(f"alloc_{oid}", None)
            st.success("Production run logged.")
            st.rerun()

    # ── Production log table ───────────────────────────────────────────────────
    st.divider()
    st.subheader("Production Log")
    st.caption("Every run on record. Filter by batch or date range to investigate output or quality trends.")

    lfa, lfb, lfc, lfd = st.columns([2, 1.8, 1.8, 1])
    with lfa:
        log_batch = st.text_input("Batch ref", placeholder="Search batch...", key="fprod_batch")
    with lfb:
        log_from = st.date_input("Date from", value=None, key="fprod_from")
    with lfc:
        log_to = st.date_input("Date to", value=None, key="fprod_to")
    with lfd:
        st.markdown("<div style='padding-top:28px'>", unsafe_allow_html=True)
        if st.button("✕ Clear", key="fprod_clear"):
            for k in ["fprod_batch", "fprod_from", "fprod_to"]:
                st.session_state.pop(k, None)
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    lsql = (
        "SELECT pl.*, o.product AS order_product, o.customer_name "
        "FROM production_logs pl LEFT JOIN orders o ON pl.order_id = o.id "
        "WHERE pl.company_id = ?"
    )
    lqp = [company_id]
    if log_batch:
        lsql += " AND pl.batch_ref LIKE ?"; lqp.append(f"%{log_batch}%")
    if log_from:
        lsql += " AND pl.date >= ?"; lqp.append(log_from.isoformat())
    if log_to:
        lsql += " AND pl.date <= ?"; lqp.append(log_to.isoformat())
    lsql += " ORDER BY pl.date DESC, pl.created_at DESC"

    logs = conn.execute(lsql, lqp).fetchall()

    if not logs:
        st.info("No entries match, adjust the filters above.")
    else:
        # ── Download buttons for the currently filtered table (ALL matching rows) ──
        _export_df = pd.DataFrame([dict(l) for l in logs])
        _dl1, _dl2, _ = st.columns([1, 1, 4])
        with _dl1:
            st.download_button(
                "⬇ Download as Excel",
                data=export_to_excel(_export_df, "production_log.xlsx"),
                file_name="production_log.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_prod_xlsx",
            )
        with _dl2:
            st.download_button(
                "⬇ Download as PDF",
                data=export_to_pdf(_export_df, "Production Log", "production_log.pdf"),
                file_name="production_log.pdf",
                mime="application/pdf",
                key="dl_prod_pdf",
            )

        # ── Top 10 most recent by default (query is already date DESC, created_at
        # DESC), same filters; full history on demand ───────────────────────────
        view_full = st.toggle("View full history", value=False, key="prod_view_full")
        display_logs = logs if view_full else logs[:10]
        if not view_full and len(logs) > 10:
            st.caption(f"Showing the 10 most recent of {len(logs)} matching entries — toggle above for full history.")

        rows_html = ""
        for lg in display_logs:
            alloc_count = conn.execute(
                "SELECT COUNT(*) FROM batch_allocations WHERE batch_id = ?", (lg["id"],)
            ).fetchone()[0]
            if alloc_count > 1:
                linked = f"{alloc_count} orders"
            elif alloc_count == 1 or lg["order_product"]:
                if alloc_count == 1:
                    ar = conn.execute(
                        "SELECT o.product, o.customer_name FROM batch_allocations ba "
                        "JOIN orders o ON ba.order_id = o.id WHERE ba.batch_id = ?", (lg["id"],)
                    ).fetchone()
                    linked = f"{ar['product']} ({ar['customer_name']})" if ar else (f"{lg['order_product']} ({lg['customer_name']})" if lg["order_product"] else "—")
                else:
                    linked = f"{lg['order_product']} ({lg['customer_name']})"
            else:
                linked = "—"

            mats = f"{lg['purple_material_kg']} / {lg['wax_kg']} / {lg['mc_kg']}"
            timing = f"{lg['machine_start']}–{lg['machine_end']}" if lg["machine_start"] else "—"
            bottles = f"{int(lg['bottles_1kg'] or 0)} / {int(lg['bottles_5kg'] or 0)}"
            cartons = f"{int(lg['cartons_1kg'] or 0)} / {int(lg['cartons_5kg'] or 0)}"
            cost_str = _inr(lg["total_batch_cost"]) if lg["total_batch_cost"] else "—"
            cpkg_str = _inr(lg["cost_per_kg"]) if lg["cost_per_kg"] else "—"
            edit_url = f"?page=Production&prod_action=edit&prod_id={lg['id']}"
            del_url  = f"?page=Production&prod_action=del&prod_id={lg['id']}"
            rows_html += (
                f"<tr>"
                f"<td>{lg['id']}</td><td>{lg['date']}</td><td>{lg['batch_ref']}</td>"
                f"<td>{mats}</td><td><b>{lg['output_kg']}</b></td>"
                f"<td>{timing}</td><td>{bottles}</td><td>{cartons}</td>"
                f"<td>{lg['rejections_kg'] or '—'}</td><td>{cost_str}</td><td>{cpkg_str}</td><td>{linked}</td>"
                f"<td><a href='#' onclick=\"window.top.location='{edit_url}';return false;\" class='act-btn'>Edit</a>"
                f"<a href='#' onclick=\"window.top.location='{del_url}';return false;\" class='act-btn del'>Del</a></td>"
                f"</tr>"
            )

        st.markdown(
            TABLE_CSS
            + "<table class='orders-table'><thead><tr>"
            "<th>ID</th><th>Date</th><th>Batch</th><th>Purple/Wax/MC kg</th>"
            "<th>Output kg</th><th>Machine time</th><th>Bottles 1kg/5kg</th>"
            "<th>Cartons 1kg/5kg</th><th>Rejections kg</th><th>Batch Cost</th><th>Cost/kg</th><th>Order(s)</th><th>Actions</th>"
            f"</tr></thead><tbody>{rows_html}</tbody></table>",
            unsafe_allow_html=True,
        )

    # Delete confirmation
    confirm_del_id = st.session_state.get("confirm_del_prod_id")
    if confirm_del_id:
        del_row = conn.execute(
            "SELECT id, batch_ref, date FROM production_logs WHERE id = ?", (confirm_del_id,)
        ).fetchone()
        if del_row:
            st.warning(f"Delete entry #{del_row['id']}, {del_row['batch_ref']} on {del_row['date']}? Cannot be undone.")
            yc, nc, _ = st.columns([1, 1, 8])
            with yc:
                if st.button("Yes, delete", type="primary"):
                    conn.execute("DELETE FROM batch_allocations WHERE batch_id = ?", (confirm_del_id,))
                    conn.execute("DELETE FROM production_logs WHERE id = ?", (confirm_del_id,))
                    conn.commit()
                    st.session_state["confirm_del_prod_id"] = None
                    st.rerun()
            with nc:
                if st.button("Cancel"):
                    st.session_state["confirm_del_prod_id"] = None
                    st.rerun()

    # ── Batch Cost Summary ─────────────────────────────────────────────────────
    _render_cost_summary(conn, company_id)

    # ── Complaints & Returns ───────────────────────────────────────────────────
    _render_complaints(conn, company_id)


def _render_cost_summary(conn, company_id):
    st.divider()
    st.subheader("Batch Cost Summary")
    st.caption("Color-coded by margin: green ≥15%, yellow 10–15%, red <10%.")

    rows = conn.execute(
        """SELECT pl.id, pl.batch_ref, pl.date, pl.output_kg,
                  pl.total_batch_cost, pl.cost_per_kg,
                  COALESCE(
                      (SELECT SUM(ba.allocated_kg * o.rate)
                       FROM batch_allocations ba JOIN orders o ON ba.order_id = o.id
                       WHERE ba.batch_id = pl.id),
                      CASE WHEN pl.order_id IS NOT NULL
                           THEN pl.output_kg * (SELECT rate FROM orders WHERE id = pl.order_id)
                           ELSE NULL END
                  ) AS revenue
           FROM production_logs pl
           WHERE pl.company_id = ? AND pl.total_batch_cost IS NOT NULL
           ORDER BY pl.date DESC, pl.id DESC""",
        (company_id,),
    ).fetchall()

    if not rows:
        st.info("No cost data yet, log a batch with costs to see the summary.")
        return

    header = (
        "<tr><th>Batch</th><th>Date</th><th>Output kg</th>"
        "<th>Total Cost</th><th>Cost/kg</th><th>Revenue</th><th>Margin %</th></tr>"
    )
    body = ""
    for r in rows:
        rev = r["revenue"]
        total_cost = r["total_batch_cost"]
        if rev and rev > 0 and total_cost:
            margin = round((rev - total_cost) / rev * 100, 1)
            margin_str = f"{margin}%"
            row_bg = "#F0FFF4" if margin >= 15 else ("#FFFDE0" if margin >= 10 else "#FFF0EE")
            margin_color = "#1B7F4F" if margin >= 15 else ("#D97706" if margin >= 10 else "#C0392B")
        else:
            margin_str = "—"
            row_bg = "#FFF8F0"
            margin_color = "#8B6A45"

        body += (
            f"<tr style='background:{row_bg}'>"
            f"<td>{r['batch_ref']}</td>"
            f"<td>{r['date']}</td>"
            f"<td>{r['output_kg']:,.1f}</td>"
            f"<td>{_inr(total_cost)}</td>"
            f"<td>{_inr(r['cost_per_kg']) if r['cost_per_kg'] else '—'}</td>"
            f"<td>{_inr(rev) if rev else '—'}</td>"
            f"<td style='color:{margin_color};font-weight:bold'>{margin_str}</td>"
            f"</tr>"
        )

    st.markdown(
        TABLE_CSS
        + f"<table class='orders-table'><thead>{header}</thead><tbody>{body}</tbody></table>",
        unsafe_allow_html=True,
    )


def _render_complaints(conn, company_id):
    st.divider()
    st.subheader("Complaints & Returns")
    st.caption("Track quality complaints and physical returns. Each complaint has a full update timeline from first report to resolution.")

    batch_opts = _batch_options(conn, company_id)

    # ── Log new complaint ──────────────────────────────────────────────────────
    with st.expander("Log a New Complaint or Return", expanded=False):
        c_batch_label = st.selectbox(
            "Batch reference",
            ["(Select batch)"] + list(batch_opts.keys()),
            key="c_batch",
        )

        complaint_order_opts = {"(None)": None}
        if c_batch_label != "(Select batch)":
            bid_sel = batch_opts[c_batch_label]
            for r in _orders_linked_to_batch(conn, bid_sel):
                complaint_order_opts[f"#{r['id']}, {r['customer_name']}, {r['product']}"] = r["id"]

        c_order_label = st.selectbox("Linked order", list(complaint_order_opts.keys()), key="c_order")

        _prev_key = "_c_order_prev"
        if st.session_state.get(_prev_key) != c_order_label:
            oid_sel = complaint_order_opts.get(c_order_label)
            if oid_sel:
                orow = conn.execute("SELECT customer_name FROM orders WHERE id = ?", (oid_sel,)).fetchone()
                st.session_state["c_customer"] = orow["customer_name"] if orow else ""
            else:
                st.session_state["c_customer"] = ""
            st.session_state[_prev_key] = c_order_label

        c_customer = st.text_input("Customer name", key="c_customer")
        c_date = st.date_input("Date", value=date_type.today(), key="c_date")
        c_issue_type = st.selectbox(
            "Issue type",
            ["Quality Complaint", "Partial Return", "Full Return"],
            key="c_issue_type",
        )
        c_desc = st.text_area("Issue description", key="c_desc", height=100,
                              placeholder="What exactly is the problem?")
        c_qty_affected = st.number_input(
            "Quantity affected (kg), optional", min_value=0.0, value=0.0, step=0.1, format="%.2f", key="c_qty_affected"
        )
        c_physical = st.checkbox("Physical return? (product is actually coming back)", key="c_physical")
        c_qty_returned = 0.0
        if c_physical:
            c_qty_returned = st.number_input(
                "Quantity returned (kg)", min_value=0.0, value=0.0, step=0.1, format="%.2f", key="c_qty_returned"
            )
        c_action = st.selectbox(
            "Initial action taken",
            ["Under Investigation", "Replacement Sent", "Credit Note Issued", "Resolved"],
            key="c_action",
        )
        c_logged_by = st.text_input("Logged by", key="c_logged_by")

        if st.button("Submit Complaint", type="primary", key="c_submit"):
            if c_batch_label == "(Select batch)":
                st.error("Select a batch reference.")
            elif not c_desc.strip():
                st.error("Issue description is required.")
            elif not c_logged_by.strip():
                st.error("'Logged by' is required.")
            else:
                bid = batch_opts[c_batch_label]
                oid = complaint_order_opts.get(c_order_label)
                status = "resolved" if c_action == "Resolved" else "open"
                conn.execute(
                    "INSERT INTO batch_complaints "
                    "(batch_id, order_id, customer_name, date, issue_type, description, "
                    "quantity_affected, physical_return, quantity_returned, initial_action, logged_by, status) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (bid, oid, c_customer.strip() or None, c_date.isoformat(),
                     c_issue_type, c_desc.strip(),
                     c_qty_affected or None, int(c_physical),
                     c_qty_returned or None, c_action, c_logged_by.strip(), status),
                )
                conn.commit()
                st.success("Complaint logged.")
                st.rerun()

    # ── Follow-up update ───────────────────────────────────────────────────────
    open_complaints = conn.execute(
        """SELECT bc.id, bc.date, bc.issue_type, bc.customer_name, pl.batch_ref, bc.status
           FROM batch_complaints bc
           JOIN production_logs pl ON bc.batch_id = pl.id
           WHERE pl.company_id = ? AND bc.status != 'resolved'
           ORDER BY bc.date DESC""",
        (company_id,),
    ).fetchall()

    if open_complaints:
        with st.expander("Add Follow-up Update to an Existing Complaint", expanded=False):
            upd_opts = {
                f"#{c['id']}, {c['batch_ref']}, {c['customer_name'] or '?'} ({c['issue_type']}) [{c['status']}]": c["id"]
                for c in open_complaints
            }
            upd_sel = st.selectbox("Select complaint", list(upd_opts.keys()), key="upd_sel")
            u_date = st.date_input("Update date", value=date_type.today(), key="upd_date")
            u_desc = st.text_area("Update description", key="upd_desc", height=80)
            u_action = st.selectbox(
                "Action taken",
                ["Under Investigation", "Replacement Sent", "Credit Note Issued", "Resolved"],
                key="upd_action",
            )
            u_status = st.selectbox("New status", ["open", "in_progress", "resolved"], key="upd_status")
            u_logged_by = st.text_input("Logged by", key="upd_logged_by")

            if st.button("Save Update", type="primary", key="upd_submit"):
                if not u_desc.strip():
                    st.error("Update description is required.")
                elif not u_logged_by.strip():
                    st.error("'Logged by' is required.")
                else:
                    cid = upd_opts[upd_sel]
                    conn.execute(
                        "INSERT INTO batch_complaint_updates "
                        "(complaint_id, date, update_description, action_taken, status, logged_by) "
                        "VALUES (?,?,?,?,?,?)",
                        (cid, u_date.isoformat(), u_desc.strip(), u_action, u_status, u_logged_by.strip()),
                    )
                    conn.execute("UPDATE batch_complaints SET status = ? WHERE id = ?", (u_status, cid))
                    conn.commit()
                    st.success("Update saved.")
                    st.rerun()

    # ── All complaints ─────────────────────────────────────────────────────────
    st.markdown("#### All Complaints")
    all_complaints = conn.execute(
        """SELECT bc.id, bc.date, bc.issue_type, bc.customer_name, pl.batch_ref,
                  bc.description, bc.quantity_affected, bc.physical_return, bc.quantity_returned,
                  bc.initial_action, bc.logged_by, bc.status
           FROM batch_complaints bc
           JOIN production_logs pl ON bc.batch_id = pl.id
           WHERE pl.company_id = ?
           ORDER BY bc.date DESC, bc.id DESC""",
        (company_id,),
    ).fetchall()

    if not all_complaints:
        st.info("No complaints logged yet.")
        return

    STATUS_STYLE = {
        "open":        ("🔴", "UNRESOLVED"),
        "in_progress": ("🟡", "IN PROGRESS"),
        "resolved":    ("🟢", "RESOLVED"),
    }

    for c in all_complaints:
        icon, label = STATUS_STYLE.get(c["status"], ("⚪", c["status"].upper()))
        title = (
            f"{icon} #{c['id']}, {c['batch_ref']}, "
            f"{c['customer_name'] or '?'}, {c['issue_type']}, {c['date']}  [{label}]"
        )
        with st.expander(title):
            badge_colors = {"open": "#C0392B", "in_progress": "#D97706", "resolved": "#1B7F4F"}
            badge_col = badge_colors.get(c["status"], "#888")
            st.markdown(
                f"**Status:** <span style='color:{badge_col};font-weight:bold'>{label}</span>",
                unsafe_allow_html=True,
            )
            st.markdown(f"**Issue:** {c['description']}")
            if c["quantity_affected"]:
                st.markdown(f"**Qty affected:** {c['quantity_affected']} kg")
            if c["physical_return"]:
                ret_qty = c["quantity_returned"] or 0
                st.markdown(f"**Physical return:** Yes, {ret_qty} kg returned")
            st.markdown(
                f"**Initial action:** {c['initial_action']}  ·  "
                f"**Logged by:** {c['logged_by']}  ·  *{c['date']}*"
            )

            updates = conn.execute(
                "SELECT * FROM batch_complaint_updates WHERE complaint_id = ? ORDER BY date ASC, created_at ASC",
                (c["id"],),
            ).fetchall()
            if updates:
                st.markdown("---")
                st.markdown("**Update Timeline:**")
                for u in updates:
                    st.markdown(
                        f"**{u['date']}**: {u['update_description']}  "
                        f"*(Action: {u['action_taken']}, Status → {u['status']}, by {u['logged_by']})*"
                    )
