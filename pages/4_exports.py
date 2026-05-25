import streamlit as st
from datetime import date
from pathlib import Path
from db.schema import init_db


@st.cache_resource
def _get_conn():
    return init_db(Path("db") / "erp.db")


COMPANIES      = ["Rwox", "Elastohorse"]
UNITS          = ["kg", "tonnes", "litres", "bags", "cartons"]
PACK_SIZES     = ["1kg bottles", "5kg bottles", "bulk"]
RATE_OPTIONS   = ["Per Unit", "Overall Total"]
CURRENCIES     = ["USD", "EUR", "GBP", "INR"]
STATUSES       = ["received", "in_production", "ready", "dispatched"]
SHIP_TERMS     = ["FOB", "CIF", "EXW", "DAP"]
DEFAULT_XR     = {"USD": 83.50, "EUR": 90.20, "GBP": 105.80, "INR": 1.0}

TABLE_CSS = (
    "<style>"
    ".etbl{width:100%;border-collapse:collapse;font-size:13px;margin-bottom:12px}"
    ".etbl th,.etbl td{border:1px solid #444;padding:7px 11px;text-align:left;white-space:nowrap}"
    ".etbl thead tr{background:#2a2a2a}"
    ".etbl tbody tr:hover{background:#1e2a3a}"
    ".act-btn{display:inline-block;padding:3px 10px;margin:0 2px;border:1px solid #555;"
    "border-radius:4px;text-decoration:none;color:#fff;font-size:12px;white-space:nowrap}"
    ".act-btn:hover{background:#3a3a3a;text-decoration:none;color:#fff}"
    ".act-btn.del{border-color:#c0392b;color:#e74c3c}"
    ".act-btn.del:hover{background:#2d1b1b}"
    ".act-btn.done{border-color:#27ae60;color:#2ecc71}"
    "</style>"
)

STATUS_COLOURS = {
    "received":     "#3498db",
    "in_production":"#e67e22",
    "ready":        "#2ecc71",
    "dispatched":   "#888",
}


def _inr(val):
    if val >= 1_00_00_000: return f"₹{val/1_00_00_000:.2f} Cr"
    if val >= 1_00_000:    return f"₹{val/1_00_000:.2f} L"
    if val >= 1_000:       return f"₹{val/1_000:.1f} K"
    return f"₹{val:,.0f}"


def _calc_inr(rate, qty, rt_label, xr):
    if rt_label == "Per Unit":
        return rate * qty * xr
    return rate * xr


def render_exports_page(conn):
    st.header("Exports")
    this_month = date.today().strftime("%Y-%m")

    # ── Handle query params ────────────────────────────────────────────────────
    params = st.query_params
    if "exp_action" in params:
        action = params.get("exp_action")
        try:    eid = int(params.get("exp_id", 0))
        except: eid = 0
        if action == "edit" and eid:
            st.session_state["editing_exp_id"] = eid
            st.session_state["confirm_del_exp_id"] = None
        elif action == "del" and eid:
            st.session_state["confirm_del_exp_id"] = eid
        elif action == "dispatch" and eid:
            conn.execute("UPDATE exports SET status='dispatched' WHERE id=?", (eid,))
            conn.commit()
        st.query_params.clear(); st.rerun()

    # ── Summary ────────────────────────────────────────────────────────────────
    rev_month  = conn.execute(
        "SELECT COALESCE(SUM(inr_equivalent),0) FROM exports "
        "WHERE strftime('%Y-%m',order_date)=?", (this_month,)).fetchone()[0]
    ord_month  = conn.execute(
        "SELECT COUNT(*) FROM exports WHERE strftime('%Y-%m',order_date)=?",
        (this_month,)).fetchone()[0]

    sm1, sm2 = st.columns(2)
    sm1.metric("Export Revenue This Month", _inr(rev_month), help=f"₹{rev_month:,.0f}")
    sm2.metric("Export Orders This Month",   ord_month)

    # Breakdown tables side by side
    bc1, bc2 = st.columns(2)
    with bc1:
        by_country = conn.execute(
            "SELECT country, COUNT(*) AS orders, SUM(inr_equivalent) AS rev "
            "FROM exports WHERE strftime('%Y-%m',order_date)=? "
            "GROUP BY country ORDER BY rev DESC", (this_month,)).fetchall()
        if by_country:
            st.markdown("**By Country**")
            rows = "".join(
                f"<tr><td>{r['country']}</td><td>{r['orders']}</td>"
                f"<td>{_inr(r['rev'])}</td></tr>" for r in by_country)
            st.markdown(TABLE_CSS +
                "<table class='etbl'><thead><tr>"
                "<th>Country</th><th>Orders</th><th>Revenue (INR)</th>"
                f"</tr></thead><tbody>{rows}</tbody></table>",
                unsafe_allow_html=True)
    with bc2:
        by_curr = conn.execute(
            "SELECT currency, COUNT(*) AS orders, SUM(inr_equivalent) AS rev "
            "FROM exports WHERE strftime('%Y-%m',order_date)=? "
            "GROUP BY currency ORDER BY rev DESC", (this_month,)).fetchall()
        if by_curr:
            st.markdown("**By Currency**")
            rows = "".join(
                f"<tr><td>{r['currency']}</td><td>{r['orders']}</td>"
                f"<td>{_inr(r['rev'])}</td></tr>" for r in by_curr)
            st.markdown(TABLE_CSS +
                "<table class='etbl'><thead><tr>"
                "<th>Currency</th><th>Orders</th><th>Revenue (INR)</th>"
                f"</tr></thead><tbody>{rows}</tbody></table>",
                unsafe_allow_html=True)

    st.divider()

    # ── Edit form ──────────────────────────────────────────────────────────────
    editing_id = st.session_state.get("editing_exp_id")
    if editing_id:
        entry = conn.execute("SELECT e.*, c.name AS company_name FROM exports e "
                             "JOIN companies c ON e.company_id=c.id WHERE e.id=?",
                             (editing_id,)).fetchone()
        if entry:
            st.subheader(f"Editing Export #{editing_id}")
            rt_label = "Per Unit" if entry["rate_type"] == "per_unit" else "Overall Total"

            with st.form("edit_exp_form"):
                ec1, ec2 = st.columns(2)
                with ec1:
                    e_company = st.selectbox("Company", COMPANIES,
                                             index=COMPANIES.index(entry["company_name"]))
                    e_customer = st.text_input("Customer name", value=entry["customer_name"])
                    e_country  = st.text_input("Country", value=entry["country"])
                    e_product  = st.text_input("Product", value=entry["product"])
                    eq, eu = st.columns([2,1])
                    with eq: e_qty  = st.number_input("Quantity", min_value=0.0, value=float(entry["quantity"]), step=1.0, format="%.2f")
                    with eu: e_unit = st.selectbox("Unit", UNITS, index=UNITS.index(entry["quantity_unit"]))
                    e_pack = st.selectbox("Pack size", PACK_SIZES,
                                          index=PACK_SIZES.index(entry["pack_size"]))

                with ec2:
                    er2, ert = st.columns([2,1])
                    with er2: e_rate = st.number_input("Rate", min_value=0.0, value=float(entry["rate"]), step=0.5, format="%.2f")
                    with ert: e_rt   = st.selectbox("Rate type", RATE_OPTIONS,
                                                    index=RATE_OPTIONS.index(rt_label))
                    ecurr, exr = st.columns(2)
                    with ecurr: e_curr = st.selectbox("Currency", CURRENCIES,
                                                       index=CURRENCIES.index(entry["currency"]))
                    with exr:   e_xr   = st.number_input("Exchange rate to INR", min_value=0.0,
                                                          value=float(entry["exchange_rate"]),
                                                          step=0.01, format="%.4f",
                                                          disabled=(entry["currency"]=="INR"))
                    e_inr = _calc_inr(e_rate, e_qty, e_rt, e_xr)
                    st.text_input("INR Equivalent (auto)", value=f"₹{e_inr:,.2f}", disabled=True)
                    eod, edd = st.columns(2)
                    with eod: e_od = st.date_input("Order date", value=date.fromisoformat(entry["order_date"]))
                    with edd: e_dd = st.date_input("Dispatch date", value=date.fromisoformat(entry["expected_dispatch_date"]))
                    est, esh = st.columns(2)
                    with est: e_status = st.selectbox("Status", STATUSES,
                                                       index=STATUSES.index(entry["status"]))
                    with esh: e_ship   = st.selectbox("Shipping terms", SHIP_TERMS,
                                                       index=SHIP_TERMS.index(entry["shipping_terms"]))
                    e_notes = st.text_area("Notes", value=entry["notes"] or "")

                sv, ca, _ = st.columns([1,1,6])
                with sv: save_btn   = st.form_submit_button("Save changes", type="primary")
                with ca: cancel_btn = st.form_submit_button("Cancel")

            if save_btn:
                if not e_customer.strip() or not e_country.strip() or not e_product.strip():
                    st.error("Customer, country and product are required.")
                else:
                    co_row = conn.execute("SELECT id FROM companies WHERE name=?", (e_company,)).fetchone()
                    conn.execute(
                        "UPDATE exports SET company_id=?,customer_name=?,country=?,product=?,"
                        "quantity=?,quantity_unit=?,pack_size=?,rate=?,rate_type=?,currency=?,"
                        "exchange_rate=?,inr_equivalent=?,order_date=?,expected_dispatch_date=?,"
                        "status=?,shipping_terms=?,notes=? WHERE id=?",
                        (co_row["id"], e_customer.strip(), e_country.strip(), e_product.strip(),
                         e_qty, e_unit, e_pack, e_rate,
                         "per_unit" if e_rt=="Per Unit" else "overall",
                         e_curr, e_xr, e_inr, e_od.isoformat(), e_dd.isoformat(),
                         e_status, e_ship, e_notes.strip() or None, editing_id))
                    conn.commit()
                    st.session_state["editing_exp_id"] = None
                    st.rerun()

            if cancel_btn:
                st.session_state["editing_exp_id"] = None; st.rerun()
            st.divider()

    # ── New export order form (regular widgets → real-time INR calc) ───────────
    st.subheader("New Export Order")

    def on_curr_change():
        curr = st.session_state.get("exp_curr", "USD")
        if curr == "INR":
            st.session_state["exp_xr"] = 1.0
        elif f"exp_xr_init_{curr}" not in st.session_state:
            st.session_state["exp_xr"] = DEFAULT_XR.get(curr, 1.0)
            st.session_state[f"exp_xr_init_{curr}"] = True

    fc1, fc2 = st.columns(2)
    with fc1:
        company     = st.selectbox("Company *", COMPANIES, key="exp_company")
        customer    = st.text_input("Customer name *", key="exp_customer")
        country     = st.text_input("Country *", key="exp_country")
        product     = st.text_input("Product *", key="exp_product")
        fq, fu      = st.columns([2,1])
        with fq: quantity     = st.number_input("Quantity *", min_value=0.0, value=1.0, step=1.0, format="%.2f", key="exp_qty")
        with fu: quantity_unit= st.selectbox("Unit", UNITS, key="exp_unit")
        pack_size   = st.selectbox("Pack size", PACK_SIZES, key="exp_pack")

    with fc2:
        fr, frt     = st.columns([2,1])
        with fr:  rate      = st.number_input("Rate *", min_value=0.0, value=0.0, step=0.5, format="%.2f", key="exp_rate")
        with frt: rate_type = st.selectbox("Rate type", RATE_OPTIONS, key="exp_rt")
        fcurr, fxr  = st.columns(2)
        with fcurr: currency = st.selectbox("Currency", CURRENCIES, key="exp_curr", on_change=on_curr_change)
        xr_disabled = (currency == "INR")
        with fxr:
            xr_default = DEFAULT_XR.get(currency, 1.0)
            exchange_rate = st.number_input("Exchange rate to INR",
                                            min_value=0.0, value=xr_default,
                                            step=0.01, format="%.4f",
                                            key="exp_xr", disabled=xr_disabled)
        actual_xr = 1.0 if xr_disabled else exchange_rate
        inr_equiv = _calc_inr(rate, quantity, rate_type, actual_xr)
        st.text_input("INR Equivalent (auto)", value=f"₹{inr_equiv:,.2f}", disabled=True, key="exp_inr_disp")

        fod, fdd    = st.columns(2)
        with fod: order_date    = st.date_input("Order date *", value=date.today(), key="exp_od")
        with fdd: dispatch_date = st.date_input("Expected dispatch *", value=date.today(), key="exp_dd")
        fst, fsh    = st.columns(2)
        with fst: status        = st.selectbox("Status", STATUSES, key="exp_status")
        with fsh: shipping_terms= st.selectbox("Shipping terms", SHIP_TERMS, key="exp_ship")

    notes = st.text_area("Notes (optional)", key="exp_notes")

    if st.button("💾 Save Export Order", type="primary"):
        if not customer.strip() or not country.strip() or not product.strip():
            st.error("Customer name, country and product are required.")
        elif rate == 0:
            st.error("Rate cannot be zero.")
        else:
            co_row = conn.execute("SELECT id FROM companies WHERE name=?", (company,)).fetchone()
            conn.execute(
                "INSERT INTO exports (company_id,customer_name,country,product,quantity,quantity_unit,"
                "pack_size,rate,rate_type,currency,exchange_rate,inr_equivalent,order_date,"
                "expected_dispatch_date,status,shipping_terms,notes) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (co_row["id"], customer.strip(), country.strip(), product.strip(),
                 quantity, quantity_unit, pack_size, rate,
                 "per_unit" if rate_type=="Per Unit" else "overall",
                 currency, actual_xr, inr_equiv,
                 order_date.isoformat(), dispatch_date.isoformat(),
                 status, shipping_terms, notes.strip() or None))
            conn.commit()
            st.success("Export order saved.")
            st.rerun()

    # ── Exports table ──────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Export Orders")

    # Filter bar
    efa, efb, efc, efd = st.columns([2, 2, 1.5, 1.5])
    with efa:
        fexp_customer = st.text_input("Customer", placeholder="Search customer...", key="fexp_customer")
    with efb:
        fexp_country = st.text_input("Country", placeholder="Search country...", key="fexp_country")
    with efc:
        fexp_company = st.selectbox("Company", ["All"] + COMPANIES, key="fexp_company")
    with efd:
        fexp_status = st.selectbox("Status", ["All"] + STATUSES, key="fexp_status")

    efe, eff, efg = st.columns([1.8, 1.8, 1])
    with efe:
        fexp_from = st.date_input("Order date from", value=None, key="fexp_from")
    with eff:
        fexp_to = st.date_input("Order date to", value=None, key="fexp_to")
    with efg:
        st.markdown("<div style='padding-top:28px'>", unsafe_allow_html=True)
        if st.button("✕ Clear filters", key="fexp_clear"):
            for k in ["fexp_customer", "fexp_country", "fexp_company", "fexp_status",
                      "fexp_from", "fexp_to"]:
                st.session_state.pop(k, None)
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    esql = (
        "SELECT e.id, c.name AS company, e.customer_name, e.country, e.product, "
        "e.quantity, e.quantity_unit, e.pack_size, e.rate, e.rate_type, e.currency, "
        "e.exchange_rate, e.inr_equivalent, e.order_date, e.expected_dispatch_date, "
        "e.status, e.shipping_terms, e.notes "
        "FROM exports e JOIN companies c ON e.company_id=c.id WHERE 1=1"
    )
    eqp = []
    if fexp_customer:
        esql += " AND e.customer_name LIKE ?"; eqp.append(f"%{fexp_customer}%")
    if fexp_country:
        esql += " AND e.country LIKE ?"; eqp.append(f"%{fexp_country}%")
    if fexp_company != "All":
        esql += " AND c.name = ?"; eqp.append(fexp_company)
    if fexp_status != "All":
        esql += " AND e.status = ?"; eqp.append(fexp_status)
    if fexp_from:
        esql += " AND e.order_date >= ?"; eqp.append(fexp_from.isoformat())
    if fexp_to:
        esql += " AND e.order_date <= ?"; eqp.append(fexp_to.isoformat())
    esql += " ORDER BY e.order_date DESC, e.created_at DESC"

    exports = conn.execute(esql, eqp).fetchall()

    if not exports:
        st.info("No export orders match the current filters.")
        return

    rows_html = ""
    for ex in exports:
        rt_lbl  = "/ unit" if ex["rate_type"] == "per_unit" else "total"
        sc      = STATUS_COLOURS.get(ex["status"], "#888")
        status_badge = f"<span style='color:{sc};font-weight:600'>{ex['status']}</span>"
        eid_val   = ex["id"]
        disp_btn  = ""  # Done handled below with native Streamlit buttons
        edit_url = f"?page=Exports&exp_action=edit&exp_id={ex['id']}"
        del_url  = f"?page=Exports&exp_action=del&exp_id={ex['id']}"
        rows_html += (
            f"<tr>"
            f"<td>{ex['id']}</td>"
            f"<td>{ex['company']}</td>"
            f"<td>{ex['customer_name']}</td>"
            f"<td>{ex['country']}</td>"
            f"<td>{ex['product']}</td>"
            f"<td>{ex['quantity']} {ex['quantity_unit']}</td>"
            f"<td>{ex['pack_size']}</td>"
            f"<td>{ex['rate']} {ex['currency']} ({rt_lbl})</td>"
            f"<td>{_inr(ex['inr_equivalent'])}</td>"
            f"<td>{ex['order_date']}</td>"
            f"<td>{ex['expected_dispatch_date']}</td>"
            f"<td>{ex['shipping_terms']}</td>"
            f"<td>{status_badge}</td>"
            f"<td>"
            f"{disp_btn}"
            f"<a href='#' onclick=\"window.top.location='{edit_url}';return false;\" class='act-btn'>Edit</a>"
            f"<a href='#' onclick=\"window.top.location='{del_url}';return false;\" class='act-btn del'>Del</a>"
            f"</td>"
            f"</tr>"
        )

    st.markdown(
        TABLE_CSS +
        "<table class='etbl'><thead><tr>"
        "<th>ID</th><th>Company</th><th>Customer</th><th>Country</th><th>Product</th>"
        "<th>Qty</th><th>Pack</th><th>Rate</th><th>INR Value</th>"
        "<th>Order Date</th><th>Dispatch Date</th><th>Terms</th><th>Status</th><th>Actions</th>"
        f"</tr></thead><tbody>{rows_html}</tbody></table>",
        unsafe_allow_html=True)


    # ── Mark as dispatched ─────────────────────────────────────────────────────
    pending_exp = [ex for ex in exports if ex["status"] != "dispatched"]
    if pending_exp:
        st.markdown("##### Mark as Dispatched")
        for ex in pending_exp:
            ea, eb, ec = st.columns([0.6, 5, 1.8])
            ea.markdown(f"**#{ex['id']}**")
            eb.write(f"{ex['customer_name']} ({ex['country']}) — {ex['product']} &nbsp; `{ex['status']}`")
            if ec.button("✓ Mark Done", key=f"exp_done_{ex['id']}", type="primary"):
                conn.execute("UPDATE exports SET status='dispatched' WHERE id=?", (ex["id"],))
                conn.commit()
                st.rerun()

    # Delete confirmation
    conf_id = st.session_state.get("confirm_del_exp_id")
    if conf_id:
        row = conn.execute("SELECT id, customer_name, country FROM exports WHERE id=?",
                           (conf_id,)).fetchone()
        if row:
            st.warning(f"Delete export #{row['id']} ({row['customer_name']} — {row['country']})? Cannot be undone.")
            yc, nc, _ = st.columns([1,1,8])
            with yc:
                if st.button("Yes, delete", type="primary"):
                    conn.execute("DELETE FROM exports WHERE id=?", (conf_id,))
                    conn.commit()
                    st.session_state["confirm_del_exp_id"] = None
                    st.rerun()
            with nc:
                if st.button("Cancel"):
                    st.session_state["confirm_del_exp_id"] = None; st.rerun()
