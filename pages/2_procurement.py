import streamlit as st
from datetime import date
from pathlib import Path
from db.schema import init_db


@st.cache_resource
def _get_conn():
    return init_db(Path("db") / "erp.db")


UNITS = ["kg", "tonnes", "litres", "bags"]
PRICE_TYPE_OPTIONS = ["Price per unit", "Total Payment"]
PRICE_TYPE_TO_DB = {"Price per unit": "per_unit", "Total Payment": "total"}
PRICE_TYPE_TO_LABEL = {"per_unit": "Price per unit", "total": "Total Payment"}

TABLE_CSS = (
    "<style>"
    ".orders-table{width:100%;border-collapse:collapse;font-size:14px;margin-bottom:16px}"
    ".orders-table th,.orders-table td{border:1px solid #444;padding:8px 12px;text-align:left;vertical-align:middle}"
    ".orders-table thead tr{background-color:#2a2a2a}"
    ".orders-table tbody tr:hover{background-color:#1e2a3a}"
    ".act-btn{display:inline-block;padding:3px 10px;margin:0 2px;border:1px solid #555;"
    "border-radius:4px;text-decoration:none;color:#fff;font-size:12px;white-space:nowrap}"
    ".act-btn:hover{background-color:#3a3a3a;text-decoration:none;color:#fff}"
    ".act-btn.del{border-color:#c0392b;color:#e74c3c}"
    ".act-btn.del:hover{background-color:#2d1b1b}"
    "</style>"
)


def render_procurement_page(conn):
    st.header("Procurement — Rwox")

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
            "SELECT * FROM procurement WHERE id = ?", (editing_id,)
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
                    "Purchase date", value=date.fromisoformat(entry["purchase_date"])
                )
                notes = st.text_area("Notes (optional)", value=entry["notes"] or "")

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
                        "UPDATE procurement SET supplier=?, item=?, quantity=?, quantity_unit=?, "
                        "unit_cost=?, price_type=?, purchase_date=?, notes=? WHERE id=?",
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
    with st.form("proc_form"):
        vendor = st.text_input("Vendor name")
        material = st.text_input("Material name")

        qty_col, unit_col = st.columns([2, 1])
        with qty_col:
            quantity = st.number_input("Quantity", min_value=0.0, value=1.0, step=0.5, format="%.2f")
        with unit_col:
            quantity_unit = st.selectbox("Unit", UNITS)

        price_col, price_type_col = st.columns([2, 1])
        with price_col:
            price = st.number_input("Amount", min_value=0.0, value=0.0, step=0.5, format="%.2f")
        with price_type_col:
            price_type_label = st.selectbox("Price type", PRICE_TYPE_OPTIONS)

        purchase_date = st.date_input("Purchase date", value=date.today())
        notes = st.text_area("Notes (optional)")
        submitted = st.form_submit_button("Save Entry")

    if submitted:
        if not vendor.strip() or not material.strip():
            st.error("Vendor and material name are required.")
        else:
            conn.execute(
                "INSERT INTO procurement (company_id, supplier, item, quantity, quantity_unit, "
                "unit_cost, price_type, purchase_date, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (company_id, vendor.strip(), material.strip(), quantity, quantity_unit,
                 price, PRICE_TYPE_TO_DB[price_type_label],
                 purchase_date.isoformat(), notes.strip() or None),
            )
            conn.commit()
            st.success("Entry saved.")

    # ── Records table ──────────────────────────────────────────────────────────
    st.subheader("Procurement Records")

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
        "FROM procurement WHERE company_id = ?"
    )
    pqp = [company_id]
    if fp_vendor:
        psql += " AND supplier LIKE ?"; pqp.append(f"%{fp_vendor}%")
    if fp_material:
        psql += " AND item LIKE ?"; pqp.append(f"%{fp_material}%")
    if fp_from:
        psql += " AND purchase_date >= ?"; pqp.append(fp_from.isoformat())
    if fp_to:
        psql += " AND purchase_date <= ?"; pqp.append(fp_to.isoformat())
    psql += " ORDER BY purchase_date DESC"

    entries = conn.execute(psql, pqp).fetchall()

    if not entries:
        st.info("No procurement records match the current filters.")
        return

    rows_html = "".join(
        f"<tr><td>{e['id']}</td><td>{e['supplier'] or '—'}</td><td>{e['item']}</td>"
        f"<td>{e['quantity']} {e['quantity_unit']}</td>"
        f"<td>{e['unit_cost']} "
        f"({'/ unit' if e['price_type'] == 'per_unit' else 'total'})</td>"
        f"<td>{e['purchase_date']}</td><td>{e['notes'] or '—'}</td>"
        f"<td><a href='#' onclick=\"window.top.location='?page=Procurement&p_action=edit&p_id={e['id']}';return false;\" class='act-btn'>Edit</a>"
        f"<a href='#' onclick=\"window.top.location='?page=Procurement&p_action=del&p_id={e['id']}';return false;\" class='act-btn del'>Del</a></td></tr>"
        for e in entries
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
            "SELECT id, supplier, item FROM procurement WHERE id = ?", (confirm_del_id,)
        ).fetchone()
        if row:
            st.warning(
                f"Delete entry #{row['id']} ({row['supplier']} — {row['item']})? "
                "This cannot be undone."
            )
            yes_col, no_col, _ = st.columns([1, 1, 8])
            with yes_col:
                if st.button("Yes, delete", type="primary"):
                    conn.execute("DELETE FROM procurement WHERE id = ?", (confirm_del_id,))
                    conn.commit()
                    st.session_state["confirm_del_proc_id"] = None
                    st.rerun()
            with no_col:
                if st.button("Cancel"):
                    st.session_state["confirm_del_proc_id"] = None
                    st.rerun()

    # ── Price history by vendor ────────────────────────────────────────────────
    st.subheader("Price History by Vendor")
    vendors = conn.execute(
        "SELECT DISTINCT supplier FROM procurement "
        "WHERE company_id = ? AND supplier IS NOT NULL ORDER BY supplier",
        (company_id,),
    ).fetchall()

    for vendor_row in vendors:
        vendor_name = vendor_row["supplier"]
        history = conn.execute(
            "SELECT item, quantity, quantity_unit, unit_cost, price_type, purchase_date "
            "FROM procurement WHERE company_id = ? AND supplier = ? "
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


