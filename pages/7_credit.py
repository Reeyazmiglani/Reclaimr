import streamlit as st
from datetime import date, datetime
from pathlib import Path
from db.schema import init_db


@st.cache_resource
def _get_conn():
    return init_db(Path("db") / "erp.db")


COMPANIES = ["Rwox", "Elastohorse"]
OVERDUE_DAYS = 45


def _ensure_credit_tables(conn):
    # Migrate receivables if it still has the old Financials schema (party_name column)
    old_cols = [r[1] for r in conn.execute("PRAGMA table_info(receivables)").fetchall()]
    if old_cols and "party_name" in old_cols:
        conn.executescript("""
            ALTER TABLE receivables RENAME TO receivables_old;
            CREATE TABLE receivables (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                company TEXT NOT NULL DEFAULT '',
                reference TEXT,
                amount REAL NOT NULL,
                date TEXT NOT NULL,
                notes TEXT,
                status TEXT NOT NULL DEFAULT 'outstanding',
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );
            INSERT INTO receivables (id, customer_name, company, reference, amount, date, notes, status, created_at)
            SELECT r.id, r.party_name, COALESCE(c.name, ''), NULL,
                   r.amount, r.as_of_date, r.notes, r.status, r.created_at
            FROM receivables_old r
            LEFT JOIN companies c ON r.company_id = c.id;
            DROP TABLE receivables_old;
        """)

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS receivables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            company TEXT NOT NULL DEFAULT '',
            reference TEXT,
            amount REAL NOT NULL,
            date TEXT NOT NULL,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'outstanding',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS payables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_name TEXT NOT NULL,
            description TEXT,
            amount REAL NOT NULL,
            date TEXT NOT NULL,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'outstanding',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            reference_id INTEGER NOT NULL,
            payment_date TEXT NOT NULL,
            amount_paid REAL NOT NULL,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
    """)
    conn.commit()


def _inr(val):
    return f"₹{val:,.2f}"


def _days_color(days):
    if days > OVERDUE_DAYS:
        return "#e74c3c"
    if days >= 30:
        return "#f39c12"
    return "#2ecc71"


def _outstanding_receivables(conn):
    return conn.execute("""
        SELECT r.id, r.customer_name, r.company, r.reference,
               r.amount, r.date, r.notes, r.status,
               COALESCE(SUM(p.amount_paid), 0) AS total_paid
        FROM receivables r
        LEFT JOIN payments p ON p.type = 'receivable' AND p.reference_id = r.id
        WHERE r.status != 'paid'
        GROUP BY r.id
        ORDER BY r.date ASC
    """).fetchall()


def _outstanding_payables(conn):
    return conn.execute("""
        SELECT p.id, p.vendor_name, p.description,
               p.amount, p.date, p.notes, p.status,
               COALESCE(SUM(pm.amount_paid), 0) AS total_paid
        FROM payables p
        LEFT JOIN payments pm ON pm.type = 'payable' AND pm.reference_id = p.id
        WHERE p.status != 'paid'
        GROUP BY p.id
        ORDER BY p.date ASC
    """).fetchall()


def _table_header(cols, hdrs):
    hdr = st.columns(cols)
    for c, h in zip(hdr, hdrs):
        c.markdown(
            f"<span style='font-size:12px;color:#888;text-transform:uppercase;"
            f"letter-spacing:0.04em'>{h}</span>",
            unsafe_allow_html=True,
        )
    st.markdown(
        "<div style='border-bottom:1px solid #333;margin:2px 0 6px'></div>",
        unsafe_allow_html=True,
    )


def render_credit_page(conn):
    _ensure_credit_tables(conn)

    st.header("Credit & Payments")
    st.caption("Track who owes you money and who you owe. 45-day informal credit threshold.")

    today = date.today()

    # ── SECTION 1 — SUMMARY ───────────────────────────────────────────────────
    out_recs = _outstanding_receivables(conn)
    out_pays = _outstanding_payables(conn)

    total_rec = sum(max(r["amount"] - r["total_paid"], 0) for r in out_recs)
    total_pay = sum(max(p["amount"] - p["total_paid"], 0) for p in out_pays)
    net = total_rec - total_pay

    overdue_recs = [r for r in out_recs if (today - date.fromisoformat(r["date"])).days > OVERDUE_DAYS]
    overdue_pays = [p for p in out_pays if (today - date.fromisoformat(p["date"])).days > OVERDUE_DAYS]
    overdue_count = len(overdue_recs) + len(overdue_pays)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Receivables", _inr(total_rec), help="Money owed to us — outstanding balance")
    m2.metric("Total Payables", _inr(total_pay), help="Money we owe vendors — outstanding balance")
    net_label = "surplus" if net >= 0 else "deficit"
    m3.metric(
        "Net Position",
        _inr(abs(net)),
        delta=f"{'▲' if net >= 0 else '▼'} Net {net_label}",
        delta_color="normal" if net >= 0 else "inverse",
    )
    m4.metric(
        "Overdue (>45 days)",
        overdue_count,
        delta="⚠ Needs action" if overdue_count > 0 else "All within terms",
        delta_color="inverse" if overdue_count > 0 else "off",
    )

    if overdue_recs:
        names = ", ".join(dict.fromkeys(r["customer_name"] for r in overdue_recs))
        n = len(overdue_recs)
        st.error(
            f"🔴 **{n} {'customer has' if n == 1 else 'customers have'} not paid in over 45 days** — {names}"
        )
    if overdue_pays:
        names = ", ".join(dict.fromkeys(p["vendor_name"] for p in overdue_pays))
        n = len(overdue_pays)
        st.warning(
            f"🟡 **{n} vendor {'payment is' if n == 1 else 'payments are'} over 45 days old** — {names}"
        )
    if not overdue_recs and not overdue_pays:
        st.success("✅ Everything within 45-day terms.")

    st.divider()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 2 — RECEIVABLES
    # ══════════════════════════════════════════════════════════════════════════
    st.subheader("Receivables — Money Owed to Us")

    with st.expander("Log New Receivable", expanded=False):
        with st.form("new_rec_form"):
            nr1, nr2 = st.columns(2)
            with nr1:
                nr_customer = st.text_input("Customer name *")
            with nr2:
                nr_company = st.selectbox("Company", COMPANIES)
            nr_ref = st.text_input("Invoice / order reference (optional)")
            nr3, nr4 = st.columns(2)
            with nr3:
                nr_amount = st.number_input("Amount (₹) *", min_value=0.01, value=1000.0, step=500.0, format="%.2f")
            with nr4:
                nr_date = st.date_input("Date of sale", value=today)
            nr_notes = st.text_area("Notes (optional)", height=70)
            nr_submit = st.form_submit_button("Add Receivable", type="primary")

        if nr_submit:
            if not nr_customer.strip():
                st.error("Customer name is required.")
            else:
                conn.execute(
                    "INSERT INTO receivables (customer_name, company, reference, amount, date, notes) "
                    "VALUES (?,?,?,?,?,?)",
                    (nr_customer.strip(), nr_company, nr_ref.strip() or None,
                     nr_amount, nr_date.isoformat(), nr_notes.strip() or None),
                )
                conn.commit()
                st.success("Receivable logged.")
                st.rerun()

    # Payment form (shown when a row's Pay button is clicked)
    paying_rec_id = st.session_state.get("paying_rec_id")
    if paying_rec_id:
        rec_row = conn.execute(
            "SELECT r.*, COALESCE(SUM(p.amount_paid), 0) AS total_paid "
            "FROM receivables r "
            "LEFT JOIN payments p ON p.type='receivable' AND p.reference_id=r.id "
            "WHERE r.id=? GROUP BY r.id",
            (paying_rec_id,),
        ).fetchone()
        if rec_row:
            balance_rem = max(rec_row["amount"] - rec_row["total_paid"], 0)
            st.info(
                f"**Recording payment from: {rec_row['customer_name']}** "
                f"({rec_row['company']}) — Balance due: {_inr(balance_rem)}"
            )
            with st.form(f"pay_rec_{paying_rec_id}"):
                pr1, pr2 = st.columns(2)
                with pr1:
                    pr_date = st.date_input("Payment date", value=today)
                with pr2:
                    pr_amount = st.number_input(
                        "Amount received (₹)", min_value=0.01,
                        value=float(balance_rem), step=500.0, format="%.2f",
                    )
                pr_notes = st.text_input("Notes (optional)")
                prs, prc, _ = st.columns([1, 1, 6])
                with prs:
                    pr_save = st.form_submit_button("Save Payment", type="primary")
                with prc:
                    pr_cancel = st.form_submit_button("Cancel")

            if pr_save:
                conn.execute(
                    "INSERT INTO payments (type, reference_id, payment_date, amount_paid, notes) "
                    "VALUES (?,?,?,?,?)",
                    ("receivable", paying_rec_id, pr_date.isoformat(),
                     pr_amount, pr_notes.strip() or None),
                )
                new_total = rec_row["total_paid"] + pr_amount
                new_status = "paid" if new_total >= rec_row["amount"] else "partial"
                conn.execute("UPDATE receivables SET status=? WHERE id=?", (new_status, paying_rec_id))
                conn.commit()
                st.session_state.pop("paying_rec_id", None)
                st.success("Payment recorded.")
                st.rerun()
            if pr_cancel:
                st.session_state.pop("paying_rec_id", None)
                st.rerun()

    # Receivables table
    out_recs = _outstanding_receivables(conn)

    if not out_recs:
        st.success("No outstanding receivables.")
    else:
        REC_COLS = [1.6, 0.7, 1.1, 1.0, 0.85, 0.75, 1.15, 0.7]
        REC_HDRS = ["Customer", "Co.", "Reference", "Amount", "Date", "Days", "Balance", ""]
        _table_header(REC_COLS, REC_HDRS)

        total_balance = 0.0
        for rec in out_recs:
            days = (today - date.fromisoformat(rec["date"])).days
            balance = max(rec["amount"] - rec["total_paid"], 0)
            total_balance += balance
            dc = _days_color(days)
            cell = "font-size:14px;padding-top:6px"

            r = st.columns(REC_COLS)
            r[0].markdown(f"<div style='{cell}'>{rec['customer_name']}</div>", unsafe_allow_html=True)
            r[1].markdown(f"<div style='{cell}'>{rec['company']}</div>", unsafe_allow_html=True)
            r[2].markdown(f"<div style='{cell};color:#aaa'>{rec['reference'] or '—'}</div>", unsafe_allow_html=True)
            r[3].markdown(f"<div style='{cell}'>{_inr(rec['amount'])}</div>", unsafe_allow_html=True)
            r[4].markdown(f"<div style='{cell};color:#aaa'>{rec['date']}</div>", unsafe_allow_html=True)
            r[5].markdown(
                f"<div style='{cell};color:{dc};font-weight:bold'>{days}d</div>",
                unsafe_allow_html=True,
            )
            partial_tag = " <span style='font-size:11px;color:#aaa'>(partial)</span>" if rec["status"] == "partial" else ""
            r[6].markdown(
                f"<div style='{cell};color:{dc};font-weight:bold'>{_inr(balance)}{partial_tag}</div>",
                unsafe_allow_html=True,
            )
            if r[7].button("Pay", key=f"pay_rec_{rec['id']}", use_container_width=True):
                st.session_state["paying_rec_id"] = rec["id"]
                st.session_state.pop("paying_pay_id", None)
                st.rerun()

        st.markdown(
            f"<div style='border-top:1px solid #333;padding-top:8px;font-size:14px'>"
            f"<b>Total Outstanding: {_inr(total_balance)}</b></div>",
            unsafe_allow_html=True,
        )

    # Paid receivables history
    paid_recs = conn.execute("""
        SELECT r.id, r.customer_name, r.company, r.reference, r.amount, r.date
        FROM receivables r WHERE r.status = 'paid'
        ORDER BY r.date DESC
    """).fetchall()

    if paid_recs:
        with st.expander(f"Payment History — {len(paid_recs)} paid receivable(s)", expanded=False):
            for pr in paid_recs:
                ref_str = f" · ref: {pr['reference']}" if pr["reference"] else ""
                st.markdown(
                    f"✅ **{pr['customer_name']}** ({pr['company']}) — "
                    f"{_inr(pr['amount'])} · *{pr['date']}*{ref_str}"
                )
                pay_rows = conn.execute(
                    "SELECT * FROM payments WHERE type='receivable' AND reference_id=? "
                    "ORDER BY payment_date ASC",
                    (pr["id"],),
                ).fetchall()
                for pay in pay_rows:
                    note = f" — {pay['notes']}" if pay["notes"] else ""
                    st.markdown(f"&nbsp;&nbsp;&nbsp;↳ {pay['payment_date']}: {_inr(pay['amount_paid'])}{note}")

    st.divider()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 3 — PAYABLES
    # ══════════════════════════════════════════════════════════════════════════
    st.subheader("Payables — Money We Owe Vendors")

    with st.expander("Log New Payable", expanded=False):
        with st.form("new_pay_form"):
            np1, np2 = st.columns(2)
            with np1:
                np_vendor = st.text_input("Vendor name *")
            with np2:
                np_desc = st.text_input("Material or service description")
            np3, np4 = st.columns(2)
            with np3:
                np_amount = st.number_input("Amount (₹) *", min_value=0.01, value=1000.0, step=500.0, format="%.2f", key="np_amount")
            with np4:
                np_date = st.date_input("Date of purchase", value=today, key="np_date")
            np_notes = st.text_area("Notes (optional)", height=70, key="np_notes")
            np_submit = st.form_submit_button("Add Payable", type="primary")

        if np_submit:
            if not np_vendor.strip():
                st.error("Vendor name is required.")
            else:
                conn.execute(
                    "INSERT INTO payables (vendor_name, description, amount, date, notes) "
                    "VALUES (?,?,?,?,?)",
                    (np_vendor.strip(), np_desc.strip() or None,
                     np_amount, np_date.isoformat(), np_notes.strip() or None),
                )
                conn.commit()
                st.success("Payable logged.")
                st.rerun()

    # Payment form for payables
    paying_pay_id = st.session_state.get("paying_pay_id")
    if paying_pay_id:
        pay_row = conn.execute(
            "SELECT p.*, COALESCE(SUM(pm.amount_paid), 0) AS total_paid "
            "FROM payables p "
            "LEFT JOIN payments pm ON pm.type='payable' AND pm.reference_id=p.id "
            "WHERE p.id=? GROUP BY p.id",
            (paying_pay_id,),
        ).fetchone()
        if pay_row:
            balance_rem = max(pay_row["amount"] - pay_row["total_paid"], 0)
            st.info(
                f"**Recording payment to: {pay_row['vendor_name']}** — Balance due: {_inr(balance_rem)}"
            )
            with st.form(f"pay_pay_{paying_pay_id}"):
                pp1, pp2 = st.columns(2)
                with pp1:
                    pp_date = st.date_input("Payment date", value=today, key="pp_date")
                with pp2:
                    pp_amount = st.number_input(
                        "Amount paid (₹)", min_value=0.01,
                        value=float(balance_rem), step=500.0, format="%.2f", key="pp_amount",
                    )
                pp_notes = st.text_input("Notes (optional)", key="pp_notes_field")
                pps, ppc, _ = st.columns([1, 1, 6])
                with pps:
                    pp_save = st.form_submit_button("Save Payment", type="primary")
                with ppc:
                    pp_cancel = st.form_submit_button("Cancel")

            if pp_save:
                conn.execute(
                    "INSERT INTO payments (type, reference_id, payment_date, amount_paid, notes) "
                    "VALUES (?,?,?,?,?)",
                    ("payable", paying_pay_id, pp_date.isoformat(),
                     pp_amount, pp_notes.strip() or None),
                )
                new_total = pay_row["total_paid"] + pp_amount
                new_status = "paid" if new_total >= pay_row["amount"] else "partial"
                conn.execute("UPDATE payables SET status=? WHERE id=?", (new_status, paying_pay_id))
                conn.commit()
                st.session_state.pop("paying_pay_id", None)
                st.success("Payment recorded.")
                st.rerun()
            if pp_cancel:
                st.session_state.pop("paying_pay_id", None)
                st.rerun()

    # Payables table
    out_pays = _outstanding_payables(conn)

    if not out_pays:
        st.success("No outstanding payables.")
    else:
        PAY_COLS = [1.7, 1.5, 1.0, 0.85, 0.75, 1.15, 0.7]
        PAY_HDRS = ["Vendor", "Description", "Amount", "Date", "Days", "Balance", ""]
        _table_header(PAY_COLS, PAY_HDRS)

        total_balance_p = 0.0
        for pay in out_pays:
            days = (today - date.fromisoformat(pay["date"])).days
            balance = max(pay["amount"] - pay["total_paid"], 0)
            total_balance_p += balance
            dc = _days_color(days)
            cell = "font-size:14px;padding-top:6px"

            r = st.columns(PAY_COLS)
            r[0].markdown(f"<div style='{cell}'>{pay['vendor_name']}</div>", unsafe_allow_html=True)
            r[1].markdown(f"<div style='{cell};color:#aaa'>{pay['description'] or '—'}</div>", unsafe_allow_html=True)
            r[2].markdown(f"<div style='{cell}'>{_inr(pay['amount'])}</div>", unsafe_allow_html=True)
            r[3].markdown(f"<div style='{cell};color:#aaa'>{pay['date']}</div>", unsafe_allow_html=True)
            r[4].markdown(
                f"<div style='{cell};color:{dc};font-weight:bold'>{days}d</div>",
                unsafe_allow_html=True,
            )
            partial_tag = " <span style='font-size:11px;color:#aaa'>(partial)</span>" if pay["status"] == "partial" else ""
            r[5].markdown(
                f"<div style='{cell};color:{dc};font-weight:bold'>{_inr(balance)}{partial_tag}</div>",
                unsafe_allow_html=True,
            )
            if r[6].button("Pay", key=f"pay_pay_{pay['id']}", use_container_width=True):
                st.session_state["paying_pay_id"] = pay["id"]
                st.session_state.pop("paying_rec_id", None)
                st.rerun()

        st.markdown(
            f"<div style='border-top:1px solid #333;padding-top:8px;font-size:14px'>"
            f"<b>Total Outstanding: {_inr(total_balance_p)}</b></div>",
            unsafe_allow_html=True,
        )

    # Paid payables history
    paid_pays = conn.execute("""
        SELECT p.id, p.vendor_name, p.description, p.amount, p.date
        FROM payables p WHERE p.status = 'paid'
        ORDER BY p.date DESC
    """).fetchall()

    if paid_pays:
        with st.expander(f"Payment History — {len(paid_pays)} paid payable(s)", expanded=False):
            for pp in paid_pays:
                desc_str = f" · {pp['description']}" if pp["description"] else ""
                st.markdown(
                    f"✅ **{pp['vendor_name']}**{desc_str} — "
                    f"{_inr(pp['amount'])} · *{pp['date']}*"
                )
                pay_rows = conn.execute(
                    "SELECT * FROM payments WHERE type='payable' AND reference_id=? "
                    "ORDER BY payment_date ASC",
                    (pp["id"],),
                ).fetchall()
                for pay in pay_rows:
                    note = f" — {pay['notes']}" if pay["notes"] else ""
                    st.markdown(f"&nbsp;&nbsp;&nbsp;↳ {pay['payment_date']}: {_inr(pay['amount_paid'])}{note}")
