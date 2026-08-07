import os
import json
import streamlit as st
import pandas as pd
from datetime import date, datetime
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq
from db.schema import init_db
from utils.voice import transcribe_audio
from utils.export import export_to_excel, export_to_pdf, generate_dispatch_note
from utils.settings import get_company_details
from utils.auth import require_auth, render_logout_button


DB_PATH = os.getenv("DB_PATH", "db/erp.db")


@st.cache_resource
def _get_conn():
    return init_db(Path(DB_PATH))


require_auth(_get_conn())
render_logout_button()

COMPANIES = ["Rwox", "Elastohorse"]
ORDER_STATUSES = ["received", "in_production", "ready", "dispatched", "cancelled"]
UNITS = ["kg", "tonnes", "litres", "units", "bags"]
PRODUCTS = ["Anti Odour", "Elastomax HT reclaiming agent", "Pine tar", "Other"]
RATE_TYPE_OPTIONS = ["Per Unit", "Overall Total"]
RATE_TYPE_TO_DB = {"Per Unit": "per_unit", "Overall Total": "overall"}
RATE_TYPE_TO_LABEL = {"per_unit": "Per Unit", "overall": "Overall Total"}

_COLS = [0.35, 0.65, 1.5, 1.4, 0.8, 1.0, 1.0, 1.1, 1.6, 0.7, 0.7]
_HDRS = ["ID", "Co.", "Customer", "Product", "Qty", "Rate", "Dispatch", "Batch Ref", "Status", "", ""]


def _prod_batch_options(conn):
    """Returns (label_list, label→batch_ref dict) from production_logs."""
    rows = conn.execute(
        "SELECT batch_ref, date, output_kg FROM production_logs ORDER BY date DESC, id DESC"
    ).fetchall()
    labels = []
    label_to_ref = {}
    for r in rows:
        try:
            date_fmt = datetime.strptime(r["date"], "%Y-%m-%d").strftime("%d %b %Y")
        except Exception:
            date_fmt = r["date"]
        label = f"{r['batch_ref']} | {date_fmt} | {r['output_kg']:.0f} kg"
        if label not in label_to_ref:
            labels.append(label)
            label_to_ref[label] = r["batch_ref"]
    return labels, label_to_ref


def _resolve_batch_ref(sel, manual, label_to_ref):
    """Convert form selection + manual input to the batch_reference value to save."""
    if sel == "Not yet produced / Enter manually":
        return manual.strip() or None
    if sel == "(Not assigned)":
        return None
    return label_to_ref.get(sel)


_WARM_CSS = (
    "<style>"
    "@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600&display=swap');"
    "* { font-family: 'DM Sans', sans-serif !important; }"
    "[class*='material-symbols'] { font-family: 'Material Symbols Rounded' !important; }"
    "[data-testid='metric-container']{background:#FFF8F0;border:1px solid #E8D5B7;"
    "border-radius:10px;padding:14px 18px}"
    "[data-testid='stMetricValue']{color:#2C2218}"
    "[data-testid='stMetricLabel']{color:#8B6A45}"
    "[data-testid='stSidebar']{background:#FFF0DC!important}"
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


def _extract_order_from_voice(text: str):
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
                        "Extract order details from this spoken text and return ONLY a JSON object "
                        "with these exact keys: company, customer_name, product, quantity, unit, "
                        "rate, rate_type, expected_dispatch. If any field is not mentioned set it "
                        "to null. company must be 'Rwox' or 'Elastohorse'. "
                        "unit must be one of: kg, tonnes, litres, bags, units. "
                        "rate_type must be 'Per Unit' or 'Overall Total'. "
                        "expected_dispatch must be in YYYY-MM-DD format if mentioned."
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


def render_orders_page(conn):
    st.markdown(_DARK_CSS if st.session_state.get("dark_mode") else _WARM_CSS, unsafe_allow_html=True)
    # Ensure batch_reference column exists on cached connections
    try:
        conn.execute("ALTER TABLE orders ADD COLUMN batch_reference TEXT")
        conn.commit()
    except Exception:
        pass

    st.header("Orders")
    st.caption("Track every order from the moment it comes in to the day it ships. Nothing gets forgotten, no customer goes without an update.")

    # ── Handle action params ─────────────────────────────────────────────────────
    params = st.query_params
    if "action" in params:
        action = params.get("action")
        try:
            order_id = int(params.get("id", 0))
        except (ValueError, TypeError):
            order_id = 0
        if action == "edit" and order_id:
            st.session_state["editing_order_id"] = order_id
            st.session_state["confirm_delete_id"] = None
        elif action == "del" and order_id:
            st.session_state["confirm_delete_id"] = order_id
        elif action == "complete" and order_id:
            conn.execute("UPDATE orders SET status='dispatched' WHERE id=?", (order_id,))
            conn.commit()
        st.query_params.clear()
        st.rerun()

    # ── Edit form ────────────────────────────────────────────────────────────────
    editing_id = st.session_state.get("editing_order_id")
    if editing_id:
        order = conn.execute(
            "SELECT o.*, c.name AS company_name FROM orders o "
            "JOIN companies c ON o.company_id = c.id WHERE o.id = ?",
            (editing_id,),
        ).fetchone()

        if order:
            st.subheader(f"Editing Order #{editing_id}")

            e_b_labels, e_b_label_to_ref = _prod_batch_options(conn)
            e_batch_opts = ["(Not assigned)"] + e_b_labels + ["Not yet produced / Enter manually"]
            existing_batch = order["batch_reference"] or ""
            e_default_label = next((l for l, r in e_b_label_to_ref.items() if r == existing_batch), None)
            if e_default_label:
                e_batch_default_idx = e_batch_opts.index(e_default_label)
                e_batch_manual_default = ""
            elif existing_batch:
                e_batch_default_idx = e_batch_opts.index("Not yet produced / Enter manually")
                e_batch_manual_default = existing_batch
            else:
                e_batch_default_idx = 0
                e_batch_manual_default = ""

            with st.form("edit_form"):
                company = st.selectbox(
                    "Company", COMPANIES,
                    index=COMPANIES.index(order["company_name"]),
                )
                customer_name = st.text_input("Customer name", value=order["customer_name"])
                _existing = order["product"] if order["product"] in PRODUCTS else "Other"
                product_choice = st.selectbox("Product", PRODUCTS, index=PRODUCTS.index(_existing))
                _other_val = order["product"] if _existing == "Other" else ""
                product = st.text_input("Specify product", value=_other_val) if product_choice == "Other" else product_choice

                qty_col, unit_col = st.columns([2, 1])
                with qty_col:
                    quantity = st.number_input("Quantity", min_value=1, value=int(order["quantity"]), step=1)
                with unit_col:
                    quantity_unit = st.selectbox(
                        "Unit", UNITS, index=UNITS.index(order["quantity_unit"])
                    )

                rate_col, rate_type_col = st.columns([2, 1])
                with rate_col:
                    rate = st.number_input("Rate", min_value=0.0, value=float(order["rate"]), step=0.5, format="%.2f")
                with rate_type_col:
                    current_label = RATE_TYPE_TO_LABEL.get(order["rate_type"], "Per Unit")
                    rate_type_label = st.selectbox(
                        "Rate type", RATE_TYPE_OPTIONS,
                        index=RATE_TYPE_OPTIONS.index(current_label),
                    )

                expected_dispatch_date = st.date_input(
                    "Expected dispatch date",
                    value=date.fromisoformat(order["expected_dispatch_date"]),
                )

                e_status = st.selectbox(
                    "Status",
                    ORDER_STATUSES,
                    index=ORDER_STATUSES.index(order["status"]) if order["status"] in ORDER_STATUSES else 0,
                    format_func=lambda s: s.replace("_", " ").title(),
                )

                with st.expander("Batch reference (optional)"):
                    e_batch_sel = st.selectbox(
                        "Select batch", e_batch_opts, index=e_batch_default_idx
                    )
                    e_batch_manual = st.text_input(
                        "Manual ref",
                        value=e_batch_manual_default,
                        placeholder="e.g. Batch-001",
                        help="Used when 'Not yet produced / Enter manually' is selected above",
                    )
                    st.caption("Once production is done, go to Production and log the batch to keep records complete.")

                with st.expander("Transport & notes (optional)"):
                    ev1, ev2 = st.columns(2)
                    with ev1:
                        e_transport = st.text_input("Carrier / person", value=order["transport_via"] or "")
                        e_dispatch_time = st.text_input("Dispatch time", value=order["dispatch_time"] or "")
                    with ev2:
                        e_delivery_deadline = st.text_input("Deadline", value=order["delivery_deadline"] or "")
                    e_notes = st.text_area("Notes", value=order["notes"] or "")

                save_col, cancel_col, _ = st.columns([1, 1, 6])
                with save_col:
                    save_btn = st.form_submit_button("Save changes", type="primary")
                with cancel_col:
                    cancel_btn = st.form_submit_button("Cancel")

            if save_btn:
                if not customer_name.strip() or not product.strip():
                    st.error("Customer name and product are required.")
                else:
                    company_row = conn.execute(
                        "SELECT id FROM companies WHERE name = ?", (company,)
                    ).fetchone()
                    new_batch_ref = _resolve_batch_ref(e_batch_sel, e_batch_manual, e_b_label_to_ref)
                    conn.execute(
                        "UPDATE orders SET company_id=?, customer_name=?, product=?, "
                        "quantity=?, quantity_unit=?, rate=?, rate_type=?, "
                        "expected_dispatch_date=?, batch_reference=?, status=?, "
                        "transport_via=?, dispatch_time=?, delivery_deadline=?, notes=? WHERE id=?",
                        (
                            company_row["id"], customer_name.strip(), product.strip(),
                            quantity, quantity_unit, rate, RATE_TYPE_TO_DB[rate_type_label],
                            expected_dispatch_date.isoformat(), new_batch_ref, e_status,
                            e_transport.strip() or None, e_dispatch_time.strip() or None,
                            e_delivery_deadline.strip() or None, e_notes.strip() or None,
                            editing_id,
                        ),
                    )
                    conn.commit()
                    st.session_state["editing_order_id"] = None
                    st.rerun()

            if cancel_btn:
                st.session_state["editing_order_id"] = None
                st.rerun()

            st.divider()

    # ── New order form ───────────────────────────────────────────────────────────
    b_labels, b_label_to_ref = _prod_batch_options(conn)
    batch_opts = ["(Not assigned)"] + b_labels + ["Not yet produced / Enter manually"]

    # ── Optional voice input ─────────────────────────────────────────────────────
    audio_value = st.audio_input("🎤 Speak your order")
    if audio_value is not None:
        _audio_hash = hash(audio_value.getvalue())
        if _audio_hash != st.session_state.get("voice_audio_hash"):
            st.session_state["voice_audio_hash"] = _audio_hash
            with st.spinner("Processing voice input with AI..."):
                _raw = transcribe_audio(audio_value)
                _extracted = _extract_order_from_voice(_raw) if _raw else None
            if _extracted:
                st.session_state["voice_prefill"] = _extracted
                st.session_state["voice_raw"] = _raw
            else:
                st.session_state["voice_error"] = True
            st.rerun()

    if st.session_state.get("voice_error"):
        st.error("Could not extract order details — please try again or fill the form manually.")
        st.session_state.pop("voice_error", None)

    pf = st.session_state.get("voice_prefill", {})
    if pf:
        _summary = " · ".join(filter(None, [
            pf.get("company"), pf.get("customer_name"), pf.get("product"),
            f"{pf.get('quantity')} {pf.get('unit') or ''}".strip() if pf.get("quantity") else None,
        ]))
        _vc, _vb = st.columns([0.88, 0.12])
        with _vc:
            st.info(f"🎤 Pre-filled from voice: {_summary} — edit any field below before saving.")
        with _vb:
            st.write("")
            if st.button("✕ Clear", key="clear_voice"):
                st.session_state.pop("voice_prefill", None)
                st.session_state.pop("voice_raw", None)
                st.rerun()

    # ── New order form ───────────────────────────────────────────────────────────
    with st.form("order_form"):
        _co_idx = COMPANIES.index(pf["company"]) if pf.get("company") in COMPANIES else 0
        company = st.selectbox("Company", COMPANIES, index=_co_idx)

        customer_name = st.text_input("Customer name", value=pf.get("customer_name") or "")

        _pv = pf.get("product") or ""
        _pi = PRODUCTS.index(_pv) if _pv in PRODUCTS else 0
        product_choice = st.selectbox("Product", PRODUCTS, index=_pi)
        if product_choice == "Other":
            product = st.text_input("Specify product", value=_pv if _pv not in PRODUCTS else "")
        else:
            product = product_choice

        qty_col, unit_col = st.columns([2, 1])
        with qty_col:
            try:
                _qty = max(1, int(float(pf["quantity"]))) if pf.get("quantity") else 1
            except (ValueError, TypeError):
                _qty = 1
            quantity = st.number_input("Quantity", min_value=1, value=_qty, step=1)
        with unit_col:
            _ui = UNITS.index(pf["unit"]) if pf.get("unit") in UNITS else 0
            quantity_unit = st.selectbox("Unit", UNITS, index=_ui)

        rate_col, rate_type_col = st.columns([2, 1])
        with rate_col:
            try:
                _rate = float(pf["rate"]) if pf.get("rate") else 0.0
            except (ValueError, TypeError):
                _rate = 0.0
            rate = st.number_input("Rate", min_value=0.0, value=_rate, step=0.5, format="%.2f")
        with rate_type_col:
            _rti = RATE_TYPE_OPTIONS.index(pf["rate_type"]) if pf.get("rate_type") in RATE_TYPE_OPTIONS else 0
            rate_type_label = st.selectbox("Rate type", RATE_TYPE_OPTIONS, index=_rti)

        try:
            _dd = date.fromisoformat(pf["expected_dispatch"]) if pf.get("expected_dispatch") else date.today()
        except (ValueError, TypeError):
            _dd = date.today()
        expected_dispatch_date = st.date_input("Dispatch date", value=_dd)

        with st.expander("Batch reference (optional)"):
            batch_sel = st.selectbox("Select batch", batch_opts)
            batch_manual = st.text_input(
                "Manual ref",
                placeholder="e.g. Batch-001",
                help="Used when 'Not yet produced / Enter manually' is selected above",
            )
            st.caption("Once production is done, go to Production and log the batch to keep records complete.")

        with st.expander("Transport & notes (optional)"):
            dv1, dv2 = st.columns(2)
            with dv1:
                transport_via = st.text_input("Carrier / person")
                dispatch_time = st.text_input("Dispatch time")
            with dv2:
                delivery_deadline = st.text_input("Deadline")
            notes = st.text_area("Notes")

        submitted = st.form_submit_button("Save Order")

    if submitted:
        if not customer_name.strip() or not product.strip():
            st.error("Customer name and product are required.")
        else:
            company_row = conn.execute(
                "SELECT id FROM companies WHERE name = ?", (company,)
            ).fetchone()
            if company_row is None:
                st.error(f"Company '{company}' not found in the database.")
            else:
                batch_ref_val = _resolve_batch_ref(batch_sel, batch_manual, b_label_to_ref)
                conn.execute(
                    "INSERT INTO orders (company_id, customer_name, product, quantity, "
                    "quantity_unit, rate, rate_type, expected_dispatch_date, batch_reference, "
                    "transport_via, dispatch_time, delivery_deadline, notes) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        company_row["id"], customer_name.strip(), product.strip(),
                        quantity, quantity_unit, rate, RATE_TYPE_TO_DB[rate_type_label],
                        expected_dispatch_date.isoformat(), batch_ref_val,
                        transport_via.strip() or None, dispatch_time.strip() or None,
                        delivery_deadline.strip() or None, notes.strip() or None,
                    ),
                )
                conn.commit()
                st.session_state.pop("voice_prefill", None)
                st.session_state.pop("voice_raw", None)
                st.success("Order saved.")

    # ══════════════════════════════════════════════════════════════════════════════
    # ORDERS TABLE
    # ══════════════════════════════════════════════════════════════════════════════
    st.subheader("Order Register")

    # ── Filter bar ───────────────────────────────────────────────────────────────
    fa, fb, fc, fd = st.columns([2, 2, 1.5, 1.5])
    with fa:
        search_customer = st.text_input("Customer", placeholder="Search by name...", key="f_customer")
    with fb:
        search_product = st.text_input("Product", placeholder="Search by product...", key="f_product")
    with fc:
        filter_company = st.selectbox("Company", ["All"] + COMPANIES, key="f_company")
    with fd:
        filter_status = st.selectbox("Status", ["All"] + ORDER_STATUSES, key="f_status",
                                    format_func=lambda s: s if s == "All" else s.replace("_", " ").title())

    fe, ff, fg = st.columns([1.8, 1.8, 1])
    with fe:
        filter_from = st.date_input("Dispatch date from", value=None, key="f_from")
    with ff:
        filter_to = st.date_input("Dispatch date to", value=None, key="f_to")
    with fg:
        st.markdown("<div style='padding-top:28px'>", unsafe_allow_html=True)
        if st.button("✕ Clear filters", key="clear_filters"):
            for k in ["f_customer", "f_product", "f_company", "f_status", "f_from", "f_to"]:
                st.session_state.pop(k, None)
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Build filtered query ─────────────────────────────────────────────────────
    sql = (
        "SELECT o.id, c.name AS company, o.customer_name, o.product, "
        "o.quantity, o.quantity_unit, o.rate, o.rate_type, o.expected_dispatch_date, "
        "o.batch_reference, o.status, o.created_at "
        "FROM orders o JOIN companies c ON o.company_id = c.id WHERE 1=1"
    )
    qp = []
    if search_customer:
        sql += " AND o.customer_name LIKE ?"; qp.append(f"%{search_customer}%")
    if search_product:
        sql += " AND o.product LIKE ?";       qp.append(f"%{search_product}%")
    if filter_company != "All":
        sql += " AND c.name = ?";             qp.append(filter_company)
    if filter_status != "All":
        sql += " AND o.status = ?";           qp.append(filter_status)
    if filter_from:
        sql += " AND o.expected_dispatch_date >= ?"; qp.append(filter_from.isoformat())
    if filter_to:
        sql += " AND o.expected_dispatch_date <= ?"; qp.append(filter_to.isoformat())
    sql += " ORDER BY o.expected_dispatch_date ASC"

    orders = conn.execute(sql, qp).fetchall()
    total  = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]

    if not orders:
        st.info("No orders match, adjust the filters above." if total > 0 else "No orders yet. Use the form above to record the first one.")
    else:
        if len(orders) < total:
            st.caption(f"Showing {len(orders)} of {total} orders, some filtered out")

        # ── Download buttons for the currently filtered/visible table ───────────
        _export_df = pd.DataFrame([dict(o) for o in orders]).drop(columns=["created_at"])
        _dl1, _dl2, _ = st.columns([1, 1, 4])
        with _dl1:
            st.download_button(
                "⬇ Download as Excel",
                data=export_to_excel(_export_df, "orders.xlsx"),
                file_name="orders.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_orders_xlsx",
            )
        with _dl2:
            st.download_button(
                "⬇ Download as PDF",
                data=export_to_pdf(_export_df, "Order Register", "orders.pdf"),
                file_name="orders.pdf",
                mime="application/pdf",
                key="dl_orders_pdf",
            )

        # ── Top 10 most recent by default, same filters; full history on demand ──
        view_full = st.toggle("View full history", value=False, key="orders_view_full")
        if view_full:
            display_orders = orders
        else:
            display_orders = sorted(orders, key=lambda o: o["created_at"] or "", reverse=True)[:10]
            if len(orders) > 10:
                st.caption(f"Showing the 10 most recent of {len(orders)} matching orders — toggle above for full history.")

        show_batch = st.toggle("Show batch column", value=False, key="show_batch_col")
        if show_batch:
            _cols_use = _COLS
            _hdrs_use = _HDRS
        else:
            _cols_use = [0.35, 0.65, 1.5, 1.4, 0.8, 1.0, 1.0, 1.6, 0.7, 0.7]
            _hdrs_use = ["ID", "Co.", "Customer", "Product", "Qty", "Rate", "Dispatch", "Status", "", ""]

        today_str = date.today().isoformat()
        _dark = st.session_state.get("dark_mode", False)
        _txt = "#F5E6D3" if _dark else "#2C2218"
        _lbl_clr = "#C4A882" if _dark else "#8B6A45"
        _div_border = "#4A3728" if _dark else "#E8D5B7"

        hdr = st.columns(_cols_use)
        for col, lbl in zip(hdr, _hdrs_use):
            col.markdown(
                f"<span style='font-size:12px;color:{_lbl_clr};text-transform:uppercase;"
                f"letter-spacing:0.04em'>{lbl}</span>",
                unsafe_allow_html=True,
            )
        st.markdown("<div style='border-bottom:2px solid #C17F3E;margin:2px 0 4px'></div>",
                    unsafe_allow_html=True)

        for o in display_orders:
            overdue = (o["expected_dispatch_date"] < today_str
                       and o["status"] not in ("dispatched", "cancelled"))
            cell = f"color:#C0392B;font-size:14px;padding-top:8px" if overdue else f"color:{_txt};font-size:14px;padding-top:8px"

            r = st.columns(_cols_use)
            r[0].markdown(f"<div style='{cell}'>{o['id']}</div>", unsafe_allow_html=True)
            r[1].markdown(f"<div style='{cell}'>{o['company']}</div>", unsafe_allow_html=True)
            r[2].markdown(f"<div style='{cell}'>{o['customer_name']}</div>", unsafe_allow_html=True)
            r[3].markdown(f"<div style='{cell}'>{o['product']}</div>", unsafe_allow_html=True)
            r[4].markdown(f"<div style='{cell}'>{o['quantity']} {o['quantity_unit']}</div>", unsafe_allow_html=True)
            rate_lbl = "/u" if o["rate_type"] == "per_unit" else "flat"
            r[5].markdown(
                f"<div style='{cell};white-space:nowrap'>{o['rate']} {rate_lbl}</div>",
                unsafe_allow_html=True,
            )
            r[6].markdown(f"<div style='{cell};white-space:nowrap'>{o['expected_dispatch_date']}</div>", unsafe_allow_html=True)

            if show_batch:
                batch_display = o["batch_reference"] or "—"
                r[7].markdown(
                    f"<div style='{cell};color:{_lbl_clr};font-size:13px'>{batch_display}</div>",
                    unsafe_allow_html=True,
                )
                status_col, edit_col, del_col = r[8], r[9], r[10]
            else:
                status_col, edit_col, del_col = r[7], r[8], r[9]

            cur_idx  = ORDER_STATUSES.index(o["status"]) if o["status"] in ORDER_STATUSES else 0
            new_status = status_col.selectbox(
                "", ORDER_STATUSES, index=cur_idx,
                key=f"s_{o['id']}", label_visibility="collapsed",
                format_func=lambda s: s.replace("_", " ").title(),
            )

            if edit_col.button("✏", key=f"e_{o['id']}", use_container_width=True, help="Edit"):
                st.session_state["editing_order_id"] = o["id"]
                st.rerun()

            if del_col.button("✕", key=f"d_{o['id']}", use_container_width=True, help="Delete"):
                st.session_state["confirm_delete_id"] = o["id"]
                st.rerun()

            if new_status != o["status"]:
                conn.execute("UPDATE orders SET status=? WHERE id=?", (new_status, o["id"]))
                conn.commit()
                st.rerun()

            if o["status"] in ("dispatched", "ready"):
                dn_col, _ = st.columns([1.5, 8.5])
                with dn_col:
                    _co_details = get_company_details(conn).get(o["company"], {})
                    _note = generate_dispatch_note({
                        "id": o["id"], "company": o["company"], "customer_name": o["customer_name"],
                        "product": o["product"], "quantity": o["quantity"], "quantity_unit": o["quantity_unit"],
                        "rate": o["rate"], "rate_type": o["rate_type"],
                        "order_date": (o["created_at"] or "")[:10],
                        "expected_dispatch_date": o["expected_dispatch_date"],
                        "actual_dispatch_date": o["expected_dispatch_date"] if o["status"] == "dispatched" else None,
                        "batch_reference": o["batch_reference"],
                        "company_address": _co_details.get("address") or None,
                        "company_gstin": _co_details.get("gstin") or None,
                        "company_contact": _co_details.get("contact") or None,
                    })
                    st.download_button(
                        "📄 Dispatch Note", data=_note,
                        file_name=f"dispatch_note_order_{o['id']}.pdf", mime="application/pdf",
                        key=f"dn_{o['id']}", use_container_width=True,
                    )

            st.markdown(
                f"<div style='border-bottom:1px solid {_div_border};margin:2px 0'></div>",
                unsafe_allow_html=True,
            )

    # ── Delete confirmation ──────────────────────────────────────────────────────
    confirm_delete_id = st.session_state.get("confirm_delete_id")
    if confirm_delete_id:
        row = conn.execute(
            "SELECT id, customer_name, product FROM orders WHERE id = ?",
            (confirm_delete_id,),
        ).fetchone()
        if row:
            st.warning(
                f"Delete order #{row['id']} ({row['customer_name']}, {row['product']})? "
                "This cannot be undone."
            )
            yes_col, no_col, _ = st.columns([1, 1, 8])
            with yes_col:
                if st.button("Yes, delete", type="primary"):
                    conn.execute("DELETE FROM orders WHERE id = ?", (confirm_delete_id,))
                    conn.commit()
                    st.session_state["confirm_delete_id"] = None
                    st.rerun()
            with no_col:
                if st.button("Cancel"):
                    st.session_state["confirm_delete_id"] = None
                    st.rerun()

    st.divider()

    if st.button("Delete all orders", type="secondary"):
        st.session_state["confirm_clear"] = True

    if st.session_state.get("confirm_clear"):
        st.warning("This will permanently delete every order in the system. This cannot be undone.")
        col_yes, col_no, _ = st.columns([1, 1, 6])
        with col_yes:
            if st.button("Yes, delete all", type="primary"):
                conn.execute("DELETE FROM orders")
                conn.commit()
                st.session_state["confirm_clear"] = False
                st.rerun()
        with col_no:
            if st.button("Cancel", key="cancel_clear"):
                st.session_state["confirm_clear"] = False
                st.rerun()
