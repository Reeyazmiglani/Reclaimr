import streamlit as st
from datetime import date
from pathlib import Path
from db.schema import init_db


@st.cache_resource
def _get_conn():
    return init_db(Path("db") / "erp.db")

COMPANIES = ["Rwox", "Elastohorse"]
ORDER_STATUSES = ["received", "in_production", "ready", "dispatched", "cancelled"]
UNITS = ["kg", "tonnes", "litres", "units", "bags"]
PRODUCTS = ["Antiordour", "Elastomax HT reclaiming agent", "Pine tar", "Other"]
RATE_TYPE_OPTIONS = ["Per Unit", "Overall Total"]
RATE_TYPE_TO_DB = {"Per Unit": "per_unit", "Overall Total": "overall"}
RATE_TYPE_TO_LABEL = {"per_unit": "Per Unit", "overall": "Overall Total"}

_COLS = [0.4, 0.9, 1.8, 1.6, 0.9, 1.2, 1.2, 1.8, 0.85, 0.85]
_HDRS = ["ID", "Co.", "Customer", "Product", "Qty", "Rate", "Dispatch", "Status", "", ""]


def render_orders_page(conn):
    st.header("Order Entry")

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
                )

                st.markdown("**Dispatch & Transport (optional)**")
                ev1, ev2 = st.columns(2)
                with ev1:
                    e_transport = st.text_input("Transport via (carrier/person)", value=order["transport_via"] or "")
                    e_dispatch_time = st.text_input("Dispatch time (e.g. 10:00 AM)", value=order["dispatch_time"] or "")
                with ev2:
                    e_delivery_deadline = st.text_input("Delivery deadline (e.g. by 5 PM / next day)", value=order["delivery_deadline"] or "")
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
                    conn.execute(
                        "UPDATE orders SET company_id=?, customer_name=?, product=?, "
                        "quantity=?, quantity_unit=?, rate=?, rate_type=?, "
                        "expected_dispatch_date=?, status=?, transport_via=?, dispatch_time=?, "
                        "delivery_deadline=?, notes=? WHERE id=?",
                        (
                            company_row["id"], customer_name.strip(), product.strip(),
                            quantity, quantity_unit, rate, RATE_TYPE_TO_DB[rate_type_label],
                            expected_dispatch_date.isoformat(), e_status,
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
    with st.form("order_form"):
        company = st.selectbox("Company", COMPANIES)
        customer_name = st.text_input("Customer name")
        product_choice = st.selectbox("Product", PRODUCTS)
        product = st.text_input("Specify product") if product_choice == "Other" else product_choice

        qty_col, unit_col = st.columns([2, 1])
        with qty_col:
            quantity = st.number_input("Quantity", min_value=1, value=1, step=1)
        with unit_col:
            quantity_unit = st.selectbox("Unit", UNITS)

        rate_col, rate_type_col = st.columns([2, 1])
        with rate_col:
            rate = st.number_input("Rate", min_value=0.0, value=0.0, step=0.5, format="%.2f")
        with rate_type_col:
            rate_type_label = st.selectbox("Rate type", RATE_TYPE_OPTIONS)

        expected_dispatch_date = st.date_input("Expected dispatch date", value=date.today())

        st.markdown("**Dispatch & Transport (optional)**")
        dv1, dv2 = st.columns(2)
        with dv1:
            transport_via = st.text_input("Transport via (carrier/person)")
            dispatch_time = st.text_input("Dispatch time (e.g. 10:00 AM)")
        with dv2:
            delivery_deadline = st.text_input("Delivery deadline (e.g. by 5 PM / next day)")
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
                conn.execute(
                    "INSERT INTO orders (company_id, customer_name, product, quantity, "
                    "quantity_unit, rate, rate_type, expected_dispatch_date, "
                    "transport_via, dispatch_time, delivery_deadline, notes) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        company_row["id"], customer_name.strip(), product.strip(),
                        quantity, quantity_unit, rate, RATE_TYPE_TO_DB[rate_type_label],
                        expected_dispatch_date.isoformat(),
                        transport_via.strip() or None, dispatch_time.strip() or None,
                        delivery_deadline.strip() or None, notes.strip() or None,
                    ),
                )
                conn.commit()
                st.success("Order saved successfully.")

    # ══════════════════════════════════════════════════════════════════════════════
    # ORDERS TABLE
    # ══════════════════════════════════════════════════════════════════════════════
    st.subheader("Existing Orders")

    # ── Filter bar ───────────────────────────────────────────────────────────────
    fa, fb, fc, fd = st.columns([2, 2, 1.5, 1.5])
    with fa:
        search_customer = st.text_input("Customer", placeholder="Search by name...", key="f_customer")
    with fb:
        search_product = st.text_input("Product", placeholder="Search by product...", key="f_product")
    with fc:
        filter_company = st.selectbox("Company", ["All"] + COMPANIES, key="f_company")
    with fd:
        filter_status = st.selectbox("Status", ["All"] + ORDER_STATUSES, key="f_status")

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
        "o.quantity, o.quantity_unit, o.rate, o.rate_type, o.expected_dispatch_date, o.status "
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
        st.info("No orders match the current filters." if total > 0 else "No orders have been recorded yet.")
    else:
        if len(orders) < total:
            st.caption(f"Showing {len(orders)} of {total} orders — some filtered out")

        today_str = date.today().isoformat()

        # Table header
        hdr = st.columns(_COLS)
        for c, lbl in zip(hdr, _HDRS):
            c.markdown(
                f"<span style='font-size:12px;color:#888;text-transform:uppercase;"
                f"letter-spacing:0.04em'>{lbl}</span>",
                unsafe_allow_html=True,
            )
        st.markdown("<div style='border-bottom:1px solid #333;margin:2px 0 4px'></div>",
                    unsafe_allow_html=True)

        # One row per order
        for o in orders:
            overdue = (o["expected_dispatch_date"] < today_str
                       and o["status"] not in ("dispatched", "cancelled"))
            clr  = "color:#e74c3c;" if overdue else ""
            cell = f"{clr}font-size:14px;padding-top:8px"

            r = st.columns(_COLS)
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
            r[6].markdown(f"<div style='{cell}'>{o['expected_dispatch_date']}</div>", unsafe_allow_html=True)

            cur_idx  = ORDER_STATUSES.index(o["status"]) if o["status"] in ORDER_STATUSES else 0
            new_status = r[7].selectbox(
                "", ORDER_STATUSES, index=cur_idx,
                key=f"s_{o['id']}", label_visibility="collapsed",
            )

            if r[8].button("✏", key=f"e_{o['id']}", use_container_width=True, help="Edit"):
                st.session_state["editing_order_id"] = o["id"]
                st.rerun()

            if r[9].button("✕", key=f"d_{o['id']}", use_container_width=True, help="Delete"):
                st.session_state["confirm_delete_id"] = o["id"]
                st.rerun()

            if new_status != o["status"]:
                conn.execute("UPDATE orders SET status=? WHERE id=?", (new_status, o["id"]))
                conn.commit()
                st.rerun()

    # ── Delete confirmation ──────────────────────────────────────────────────────
    confirm_delete_id = st.session_state.get("confirm_delete_id")
    if confirm_delete_id:
        row = conn.execute(
            "SELECT id, customer_name, product FROM orders WHERE id = ?",
            (confirm_delete_id,),
        ).fetchone()
        if row:
            st.warning(
                f"Delete order #{row['id']} ({row['customer_name']} — {row['product']})? "
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

    if st.button("Clear all", type="secondary"):
        st.session_state["confirm_clear"] = True

    if st.session_state.get("confirm_clear"):
        st.warning("This will permanently delete all orders. Are you sure?")
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
