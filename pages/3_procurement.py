import os
import json
import streamlit as st
import pandas as pd
from datetime import date
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq
from db.schema import init_db
from utils.voice import transcribe_audio
from utils.export import export_to_excel, export_to_pdf
from utils.auth import require_auth, render_logout_button


DATABASE_URL = os.getenv("DATABASE_URL")


@st.cache_resource
def _get_conn():
    return init_db(DATABASE_URL)


require_auth(_get_conn())
render_logout_button()

UNITS = ["kg", "tonnes", "litres", "bags"]
PRICE_TYPE_OPTIONS = ["Price per unit", "Total Payment"]
PRICE_TYPE_TO_DB = {"Price per unit": "per_unit", "Total Payment": "total"}
PRICE_TYPE_TO_LABEL = {"per_unit": "Price per unit", "total": "Total Payment"}

_WARM_CSS = (
    "<style>"
    "@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600&display=swap');"
    "* { font-family: 'DM Sans', sans-serif !important; }"
    "[class*='material-symbols'], [data-testid='stIconMaterial'] { font-family: 'Material Symbols Rounded' !important; font-style: normal !important; font-variation-settings: inherit; }"
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
    "[class*='material-symbols'], [data-testid='stIconMaterial'] { font-family: 'Material Symbols Rounded' !important; font-style: normal !important; font-variation-settings: inherit; }"
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


def _extract_procurement_from_voice(text: str):
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
                        "Extract purchase details from this spoken text and return ONLY a JSON object "
                        "with these exact keys: vendor, material, quantity, unit, price, price_type, purchase_date. "
                        "If any field is not mentioned set it to null. "
                        "unit must be one of: kg, tonnes, litres, bags. "
                        "price_type must be 'Price per unit' or 'Total Payment'. "
                        "purchase_date must be in YYYY-MM-DD format if mentioned."
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


def render_procurement_page(conn):
    st.markdown(_DARK_CSS if st.session_state.get("dark_mode") else _WARM_CSS, unsafe_allow_html=True)
    st.header("Procurement")
    st.caption("Log purchases as they happen and build a price history that tells you when a vendor is overcharging.")

    rwox = conn.execute("SELECT id FROM companies WHERE name = 'Rwox'").fetchone()
    if not rwox:
        st.error("Rwox company not found in database.")
        return
    company_id = rwox["id"]

    # Detect Edit / Del clicks from HTML table links via query params
    params = st.query_params
    if "p_action" in params:
        action = params.get("p_action")
        try:
            entry_id = int(params.get("p_id", 0))
        except (ValueError, TypeError):
            entry_id = 0
        if action == "edit" and entry_id:
            st.session_state["editing_proc_id"] = entry_id
            st.session_state["confirm_del_proc_id"] = None
        elif action == "del" and entry_id:
            st.session_state["confirm_del_proc_id"] = entry_id
        st.query_params.clear()
        st.rerun()

    # ── Edit form ──────────────────────────────────────────────────────────────
    editing_id = st.session_state.get("editing_proc_id")
    if editing_id:
        entry = conn.execute(
            "SELECT * FROM procurement WHERE id = %s", (editing_id,)
        ).fetchone()

        if entry:
            st.subheader(f"Editing Entry #{editing_id}")
            current_unit = entry["quantity_unit"] if entry["quantity_unit"] in UNITS else UNITS[0]
            current_price_label = PRICE_TYPE_TO_LABEL.get(entry["price_type"], "Price per unit")

            with st.form("edit_proc_form"):
                vendor = st.text_input("Vendor name", value=entry["supplier"] or "")
                material = st.text_input("Material name", value=entry["item"])

                qty_col, unit_col = st.columns([2, 1])
                with qty_col:
                    quantity = st.number_input("Quantity", min_value=0.0, value=float(entry["quantity"]), step=0.5, format="%.2f")
                with unit_col:
                    quantity_unit = st.selectbox("Unit", UNITS, index=UNITS.index(current_unit))

                price_col, price_type_col = st.columns([2, 1])
                with price_col:
                    price = st.number_input("Amount", min_value=0.0, value=float(entry["unit_cost"]), step=0.5, format="%.2f")
                with price_type_col:
                    price_type_label = st.selectbox(
                        "Price type", PRICE_TYPE_OPTIONS,
                        index=PRICE_TYPE_OPTIONS.index(current_price_label),
                    )

                purchase_date = st.date_input(
                    "Date", value=date.fromisoformat(entry["purchase_date"])
                )
                notes = st.text_area("Notes", value=entry["notes"] or "")

                save_col, cancel_col, _ = st.columns([1, 1, 6])
                with save_col:
                    save_btn = st.form_submit_button("Save changes", type="primary")
                with cancel_col:
                    cancel_btn = st.form_submit_button("Cancel")

            if save_btn:
                if not vendor.strip() or not material.strip():
                    st.error("Vendor and material name are required.")
                else:
                    conn.execute(
                        "UPDATE procurement SET supplier=%s, item=%s, quantity=%s, quantity_unit=%s, "
                        "unit_cost=%s, price_type=%s, purchase_date=%s, notes=%s WHERE id=%s",
                        (vendor.strip(), material.strip(), quantity, quantity_unit,
                         price, PRICE_TYPE_TO_DB[price_type_label],
                         purchase_date.isoformat(), notes.strip() or None, editing_id),
                    )
                    conn.commit()
                    st.session_state["editing_proc_id"] = None
                    st.rerun()

            if cancel_btn:
                st.session_state["editing_proc_id"] = None
                st.rerun()

            st.divider()

    # ── New entry form ─────────────────────────────────────────────────────────
    with st.expander("🎤 Voice Input — speak to auto-fill (optional)"):
        audio_value = st.audio_input("🎤 Speak your purchase")
        st.caption("Example: 'Bought 50 kg pine tar from Sharma at 200 per kg'")
        if audio_value is not None:
            _audio_hash = hash(audio_value.getvalue())
            if _audio_hash != st.session_state.get("voice_proc_audio_hash"):
                st.session_state["voice_proc_audio_hash"] = _audio_hash
                with st.spinner("Processing voice input with AI..."):
                    _raw = transcribe_audio(audio_value)
                    _ext = _extract_procurement_from_voice(_raw) if _raw else None
                if _ext:
                    st.session_state["voice_proc_prefill"] = _ext
                    st.session_state["voice_proc_raw"] = _raw
                else:
                    st.session_state["voice_proc_error"] = True
                st.rerun()
        if st.session_state.get("voice_proc_error"):
            st.error("Could not extract details — fill the form manually.")
            st.session_state.pop("voice_proc_error", None)
        _vp = st.session_state.get("voice_proc_prefill", {})
        if _vp:
            st.success(f'Extracted from: "{st.session_state.get("voice_proc_raw", "")}"')
            vc1, vc2, vc3 = st.columns(3)
            vc1.metric("Vendor", _vp.get("vendor") or "—")
            vc2.metric("Material", _vp.get("material") or "—")
            vc3.metric("Qty / Price", f"{_vp.get('quantity') or '—'} {_vp.get('unit') or ''} @ {_vp.get('price') or '—'}")
            if st.button("✕ Clear voice pre-fill", key="clr_vp"):
                st.session_state.pop("voice_proc_prefill", None)
                st.session_state.pop("voice_proc_raw", None)
                st.rerun()

    pf = st.session_state.get("voice_proc_prefill", {})
    with st.form("proc_form"):
        vendor = st.text_input("Vendor name", value=pf.get("vendor") or "")
        material = st.text_input("Material name", value=pf.get("material") or "")

        qty_col, unit_col = st.columns([2, 1])
        with qty_col:
            try:
                _qty = float(pf["quantity"]) if pf.get("quantity") else 1.0
            except (ValueError, TypeError):
                _qty = 1.0
            quantity = st.number_input("Quantity", min_value=0.0, value=_qty, step=0.5, format="%.2f")
        with unit_col:
            _ui = UNITS.index(pf["unit"]) if pf.get("unit") in UNITS else 0
            quantity_unit = st.selectbox("Unit", UNITS, index=_ui)

        price_col, price_type_col = st.columns([2, 1])
        with price_col:
            try:
                _pr = float(pf["price"]) if pf.get("price") else 0.0
            except (ValueError, TypeError):
                _pr = 0.0
            price = st.number_input("Amount", min_value=0.0, value=_pr, step=0.5, format="%.2f")
        with price_type_col:
            _pti = PRICE_TYPE_OPTIONS.index(pf["price_type"]) if pf.get("price_type") in PRICE_TYPE_OPTIONS else 0
            price_type_label = st.selectbox("Price type", PRICE_TYPE_OPTIONS, index=_pti)

        try:
            _dd = date.fromisoformat(pf["purchase_date"]) if pf.get("purchase_date") else date.today()
        except (ValueError, TypeError):
            _dd = date.today()
        purchase_date = st.date_input("Date", value=_dd)
        notes = st.text_area("Notes (optional)", placeholder="Add notes...")
        submitted = st.form_submit_button("Save Entry")

    if submitted:
        if not vendor.strip() or not material.strip():
            st.error("Vendor and material name are required.")
        else:
            conn.execute(
                "INSERT INTO procurement (company_id, supplier, item, quantity, quantity_unit, "
                "unit_cost, price_type, purchase_date, notes) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (company_id, vendor.strip(), material.strip(), quantity, quantity_unit,
                 price, PRICE_TYPE_TO_DB[price_type_label],
                 purchase_date.isoformat(), notes.strip() or None),
            )
            conn.commit()
            st.session_state.pop("voice_proc_prefill", None)
            st.session_state.pop("voice_proc_raw", None)
            st.success("Purchase recorded.")

    # ── Records table ──────────────────────────────────────────────────────────
    st.subheader("Purchase Records")

    # Filter bar
    pfa, pfb, pfc, pfd = st.columns([2, 2, 1.8, 1.8])
    with pfa:
        fp_vendor = st.text_input("Vendor", placeholder="Search vendor...", key="fp_vendor")
    with pfb:
        fp_material = st.text_input("Material", placeholder="Search material...", key="fp_material")
    with pfc:
        fp_from = st.date_input("Date from", value=None, key="fp_from")
    with pfd:
        fp_to = st.date_input("Date to", value=None, key="fp_to")
    pfg_col, _ = st.columns([1, 6])
    with pfg_col:
        if st.button("✕ Clear filters", key="fp_clear"):
            for k in ["fp_vendor", "fp_material", "fp_from", "fp_to"]:
                st.session_state.pop(k, None)
            st.rerun()

    psql = (
        "SELECT id, supplier, item, quantity, quantity_unit, unit_cost, price_type, purchase_date, notes "
        "FROM procurement WHERE company_id = %s"
    )
    pqp = [company_id]
    if fp_vendor:
        psql += " AND supplier LIKE %s"; pqp.append(f"%{fp_vendor}%")
    if fp_material:
        psql += " AND item LIKE %s"; pqp.append(f"%{fp_material}%")
    if fp_from:
        psql += " AND purchase_date >= %s"; pqp.append(fp_from.isoformat())
    if fp_to:
        psql += " AND purchase_date <= %s"; pqp.append(fp_to.isoformat())
    psql += " ORDER BY purchase_date DESC"

    entries = conn.execute(psql, pqp).fetchall()

    if not entries:
        st.info("No records match, adjust the filters above.")
        return

    # ── Download buttons for the currently filtered table (ALL matching rows) ───
    _export_df = pd.DataFrame([dict(e) for e in entries])
    _dl1, _dl2, _ = st.columns([1, 1, 4])
    with _dl1:
        st.download_button(
            "⬇ Download as Excel",
            data=export_to_excel(_export_df, "procurement.xlsx"),
            file_name="procurement.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_proc_xlsx",
        )
    with _dl2:
        st.download_button(
            "⬇ Download as PDF",
            data=export_to_pdf(_export_df, "Purchase Records", "procurement.pdf"),
            file_name="procurement.pdf",
            mime="application/pdf",
            key="dl_proc_pdf",
        )

    # ── Top 10 most recent by default (query is already purchase_date DESC),
    # same filters; full history on demand ────────────────────────────────────
    view_full = st.toggle("View full history", value=False, key="proc_view_full")
    display_entries = entries if view_full else entries[:10]
    if not view_full and len(entries) > 10:
        st.caption(f"Showing the 10 most recent of {len(entries)} matching records — toggle above for full history.")

    rows_html = "".join(
        f"<tr><td>{e['id']}</td><td>{e['supplier'] or '—'}</td><td>{e['item']}</td>"
        f"<td>{e['quantity']} {e['quantity_unit']}</td>"
        f"<td>{e['unit_cost']} "
        f"({'/ unit' if e['price_type'] == 'per_unit' else 'total'})</td>"
        f"<td>{e['purchase_date']}</td><td>{e['notes'] or '—'}</td>"
        f"<td><a href='#' onclick=\"window.top.location='?page=Procurement&p_action=edit&p_id={e['id']}';return false;\" class='act-btn'>Edit</a>"
        f"<a href='#' onclick=\"window.top.location='?page=Procurement&p_action=del&p_id={e['id']}';return false;\" class='act-btn del'>Del</a></td></tr>"
        for e in display_entries
    )
    st.markdown(
        TABLE_CSS
        + "<table class='orders-table'><thead><tr>"
        "<th>ID</th><th>Vendor</th><th>Material</th><th>Quantity</th>"
        "<th>Price</th><th>Date</th><th>Notes</th><th>Actions</th>"
        f"</tr></thead><tbody>{rows_html}</tbody></table>",
        unsafe_allow_html=True,
    )

    # Delete confirmation
    confirm_del_id = st.session_state.get("confirm_del_proc_id")
    if confirm_del_id:
        row = conn.execute(
            "SELECT id, supplier, item FROM procurement WHERE id = %s", (confirm_del_id,)
        ).fetchone()
        if row:
            st.warning(
                f"Delete entry #{row['id']} ({row['supplier']}, {row['item']})? "
                "This cannot be undone."
            )
            yes_col, no_col, _ = st.columns([1, 1, 8])
            with yes_col:
                if st.button("Yes, delete", type="primary"):
                    conn.execute("DELETE FROM procurement WHERE id = %s", (confirm_del_id,))
                    conn.commit()
                    st.session_state["confirm_del_proc_id"] = None
                    st.rerun()
            with no_col:
                if st.button("Cancel"):
                    st.session_state["confirm_del_proc_id"] = None
                    st.rerun()

    # ── Price history by vendor ────────────────────────────────────────────────
    st.subheader("Price History by Vendor")
    st.caption("Last 5 purchases per vendor. Use this to spot price drift before it hits your margins.")
    vendors = conn.execute(
        "SELECT DISTINCT supplier FROM procurement "
        "WHERE company_id = %s AND supplier IS NOT NULL ORDER BY supplier",
        (company_id,),
    ).fetchall()

    for vendor_row in vendors:
        vendor_name = vendor_row["supplier"]
        history = conn.execute(
            "SELECT item, quantity, quantity_unit, unit_cost, price_type, purchase_date "
            "FROM procurement WHERE company_id = %s AND supplier = %s "
            "ORDER BY purchase_date DESC LIMIT 5",
            (company_id, vendor_name),
        ).fetchall()

        st.markdown(f"**{vendor_name}**")
        hist_rows = "".join(
            f"<tr><td>{h['item']}</td><td>{h['quantity']} {h['quantity_unit']}</td>"
            f"<td>{h['unit_cost']} ({'/ unit' if h['price_type'] == 'per_unit' else 'total'})</td>"
            f"<td>{h['purchase_date']}</td></tr>"
            for h in history
        )
        st.markdown(
            TABLE_CSS
            + "<table class='orders-table' style='margin-bottom:20px'><thead><tr>"
            "<th>Material</th><th>Quantity</th><th>Price</th><th>Date</th>"
            f"</tr></thead><tbody>{hist_rows}</tbody></table>",
            unsafe_allow_html=True,
        )


