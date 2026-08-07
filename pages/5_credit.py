import os
import streamlit as st
from datetime import date, datetime
from pathlib import Path
from dotenv import load_dotenv
from db.schema import init_db
from utils.settings import get_overdue_days
from utils.auth import require_auth, render_logout_button

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "db/erp.db")


@st.cache_resource
def _get_conn():
    return init_db(Path(DB_PATH))


require_auth(_get_conn())
render_logout_button()

COMPANIES = ["Rwox", "Elastohorse"]
OVERDUE_DAYS = 45  # default; overwritten from the Settings page's saved value on each render

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

    for sql in [
        "ALTER TABLE receivables ADD COLUMN last_contacted TEXT",
    ]:
        try:
            conn.execute(sql)
        except Exception:
            pass

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
        return "#C0392B"
    if days >= 30:
        return "#D97706"
    return "#1B7F4F"


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
            f"<span style='font-size:12px;color:#8B6A45;text-transform:uppercase;"
            f"letter-spacing:0.04em'>{h}</span>",
            unsafe_allow_html=True,
        )
    st.markdown(
        "<div style='border-bottom:2px solid #C17F3E;margin:2px 0 6px'></div>",
        unsafe_allow_html=True,
    )


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


def render_credit_page(conn):
    global OVERDUE_DAYS
    OVERDUE_DAYS = get_overdue_days(conn)

    st.markdown(_DARK_CSS if st.session_state.get("dark_mode") else _WARM_CSS, unsafe_allow_html=True)
    _ensure_credit_tables(conn)

    st.header("Credit & Payments")
    st.caption(f"Track who owes you money and who you owe. {OVERDUE_DAYS}-day informal credit threshold (edit in Settings).")

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
    m1.metric("Total Receivables", _inr(total_rec), help="Money owed to us, outstanding balance")
    m2.metric("Total Payables", _inr(total_pay), help="Money we owe vendors, outstanding balance")
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
            f"🔴 **{n} {'customer has' if n == 1 else 'customers have'} not paid in over 45 days**: {names}"
        )
    if overdue_pays:
        names = ", ".join(dict.fromkeys(p["vendor_name"] for p in overdue_pays))
        n = len(overdue_pays)
        st.warning(
            f"🟡 **{n} vendor {'payment is' if n == 1 else 'payments are'} over 45 days old**: {names}"
        )
    if not overdue_recs and not overdue_pays:
        st.success("✅ Everything within 45-day terms.")

    st.divider()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 2 — RECEIVABLES
    # ══════════════════════════════════════════════════════════════════════════
    st.subheader("Receivables: Money Owed to Us")

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
                nr_date = st.date_input("Sale date", value=today)
            nr_notes = st.text_area("Notes", height=70)
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
                f"({rec_row['company']}), Balance due: {_inr(balance_rem)}"
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
                pr_notes = st.text_input("Notes")
                prs, prc, _ = st.columns([1, 1, 6])
                with prs:
                    pr_save = st.form_submit_button("Save Payment", type="primary")
                with prc:
                    pr_cancel = st.form_submit_button("Cancel")

            if pr_save:
                if pr_amount <= 0:
                    st.error("Amount must be greater than zero.")
                elif pr_amount > balance_rem + 0.01:
                    st.error(f"Amount {_inr(pr_amount)} exceeds balance {_inr(balance_rem)}, reduce the amount.")
                else:
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

    # Delete confirm flows
    confirm_del_rec = st.session_state.get("confirm_del_rec_id")
    if confirm_del_rec:
        del_r = conn.execute("SELECT customer_name, amount FROM receivables WHERE id=?", (confirm_del_rec,)).fetchone()
        if del_r:
            st.warning(f"Delete receivable from **{del_r['customer_name']}** ({_inr(del_r['amount'])})? This also removes any payment records. Cannot be undone.")
            dc1, dc2, _ = st.columns([1, 1, 8])
            with dc1:
                if st.button("Yes, delete", key="conf_del_rec_yes", type="primary"):
                    conn.execute("DELETE FROM payments WHERE type='receivable' AND reference_id=?", (confirm_del_rec,))
                    conn.execute("DELETE FROM receivables WHERE id=?", (confirm_del_rec,))
                    conn.commit()
                    st.session_state.pop("confirm_del_rec_id", None)
                    st.rerun()
            with dc2:
                if st.button("Cancel", key="conf_del_rec_no"):
                    st.session_state.pop("confirm_del_rec_id", None)
                    st.rerun()

    # Receivables table
    out_recs = _outstanding_receivables(conn)

    if not out_recs:
        st.success("No outstanding receivables.")
    else:
        # ── Top 10 most recent by default, full history on demand ───────────────
        rec_view_full = st.toggle("View full history", value=False, key="rec_view_full")
        if rec_view_full:
            display_recs = out_recs
        else:
            display_recs = sorted(out_recs, key=lambda r: r["date"] or "", reverse=True)[:10]
            if len(out_recs) > 10:
                st.caption(f"Showing the 10 most recent of {len(out_recs)} outstanding receivables — toggle above for full history.")

        REC_COLS = [1.6, 0.7, 1.1, 1.0, 0.85, 0.75, 1.15, 0.55, 0.45]
        REC_HDRS = ["Customer", "Co.", "Reference", "Amount", "Date", "Days", "Balance", "", ""]
        _table_header(REC_COLS, REC_HDRS)

        # Total is always across ALL outstanding receivables, not just the rows shown.
        total_balance = sum(max(r["amount"] - r["total_paid"], 0) for r in out_recs)
        for rec in display_recs:
            days = (today - date.fromisoformat(rec["date"])).days
            balance = max(rec["amount"] - rec["total_paid"], 0)
            dc = _days_color(days)
            cell = "font-size:14px;padding-top:6px"

            r = st.columns(REC_COLS)
            r[0].markdown(f"<div style='{cell}'>{rec['customer_name']}</div>", unsafe_allow_html=True)
            r[1].markdown(f"<div style='{cell}'>{rec['company']}</div>", unsafe_allow_html=True)
            r[2].markdown(f"<div style='{cell};color:#8B6A45'>{rec['reference'] or '—'}</div>", unsafe_allow_html=True)
            r[3].markdown(f"<div style='{cell}'>{_inr(rec['amount'])}</div>", unsafe_allow_html=True)
            r[4].markdown(f"<div style='{cell};color:#8B6A45'>{rec['date']}</div>", unsafe_allow_html=True)
            r[5].markdown(
                f"<div style='{cell};color:{dc};font-weight:bold'>{days}d</div>",
                unsafe_allow_html=True,
            )
            partial_tag = " <span style='font-size:11px;color:#8B6A45'>(partial)</span>" if rec["status"] == "partial" else ""
            r[6].markdown(
                f"<div style='{cell};color:{dc};font-weight:bold'>{_inr(balance)}{partial_tag}</div>",
                unsafe_allow_html=True,
            )
            if r[7].button("Pay", key=f"pay_rec_{rec['id']}", use_container_width=True):
                st.session_state["paying_rec_id"] = rec["id"]
                st.session_state.pop("paying_pay_id", None)
                st.rerun()
            if r[8].button("Del", key=f"del_rec_{rec['id']}", use_container_width=True):
                st.session_state["confirm_del_rec_id"] = rec["id"]
                st.rerun()

        st.markdown(
            f"<div style='border-top:1px solid #E8D5B7;padding-top:8px;font-size:14px'>"
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
        with st.expander(f"Payment History: {len(paid_recs)} paid receivable(s)", expanded=False):
            for pr in paid_recs:
                ref_str = f" · ref: {pr['reference']}" if pr["reference"] else ""
                st.markdown(
                    f"✅ **{pr['customer_name']}** ({pr['company']}), "
                    f"{_inr(pr['amount'])} · *{pr['date']}*{ref_str}"
                )
                pay_rows = conn.execute(
                    "SELECT * FROM payments WHERE type='receivable' AND reference_id=? "
                    "ORDER BY payment_date ASC",
                    (pr["id"],),
                ).fetchall()
                for pay in pay_rows:
                    note = f", {pay['notes']}" if pay["notes"] else ""
                    st.markdown(f"&nbsp;&nbsp;&nbsp;↳ {pay['payment_date']}: {_inr(pay['amount_paid'])}{note}")

    st.divider()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 3 — PAYABLES
    # ══════════════════════════════════════════════════════════════════════════
    st.subheader("Payables: Money We Owe Vendors")

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
                np_date = st.date_input("Purchase date", value=today, key="np_date")
            np_notes = st.text_area("Notes", height=70, key="np_notes")
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
                f"**Recording payment to: {pay_row['vendor_name']}**, Balance due: {_inr(balance_rem)}"
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
                pp_notes = st.text_input("Notes", key="pp_notes_field")
                pps, ppc, _ = st.columns([1, 1, 6])
                with pps:
                    pp_save = st.form_submit_button("Save Payment", type="primary")
                with ppc:
                    pp_cancel = st.form_submit_button("Cancel")

            if pp_save:
                if pp_amount <= 0:
                    st.error("Amount must be greater than zero.")
                elif pp_amount > balance_rem + 0.01:
                    st.error(f"Amount {_inr(pp_amount)} exceeds balance {_inr(balance_rem)}, reduce the amount.")
                else:
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

    # Payable delete confirm flow
    confirm_del_pay = st.session_state.get("confirm_del_pay_id")
    if confirm_del_pay:
        del_p = conn.execute("SELECT vendor_name, amount FROM payables WHERE id=?", (confirm_del_pay,)).fetchone()
        if del_p:
            st.warning(f"Delete payable to **{del_p['vendor_name']}** ({_inr(del_p['amount'])})? This also removes any payment records. Cannot be undone.")
            dc3, dc4, _ = st.columns([1, 1, 8])
            with dc3:
                if st.button("Yes, delete", key="conf_del_pay_yes", type="primary"):
                    conn.execute("DELETE FROM payments WHERE type='payable' AND reference_id=?", (confirm_del_pay,))
                    conn.execute("DELETE FROM payables WHERE id=?", (confirm_del_pay,))
                    conn.commit()
                    st.session_state.pop("confirm_del_pay_id", None)
                    st.rerun()
            with dc4:
                if st.button("Cancel", key="conf_del_pay_no"):
                    st.session_state.pop("confirm_del_pay_id", None)
                    st.rerun()

    # Payables table
    out_pays = _outstanding_payables(conn)

    if not out_pays:
        st.success("No outstanding payables.")
    else:
        # ── Top 10 most recent by default, full history on demand ───────────────
        pay_view_full = st.toggle("View full history", value=False, key="pay_view_full")
        if pay_view_full:
            display_pays = out_pays
        else:
            display_pays = sorted(out_pays, key=lambda p: p["date"] or "", reverse=True)[:10]
            if len(out_pays) > 10:
                st.caption(f"Showing the 10 most recent of {len(out_pays)} outstanding payables — toggle above for full history.")

        PAY_COLS = [1.7, 1.5, 1.0, 0.85, 0.75, 1.15, 0.55, 0.45]
        PAY_HDRS = ["Vendor", "Description", "Amount", "Date", "Days", "Balance", "", ""]
        _table_header(PAY_COLS, PAY_HDRS)

        # Total is always across ALL outstanding payables, not just the rows shown.
        total_balance_p = sum(max(p["amount"] - p["total_paid"], 0) for p in out_pays)
        for pay in display_pays:
            days = (today - date.fromisoformat(pay["date"])).days
            balance = max(pay["amount"] - pay["total_paid"], 0)
            dc = _days_color(days)
            cell = "font-size:14px;padding-top:6px"

            r = st.columns(PAY_COLS)
            r[0].markdown(f"<div style='{cell}'>{pay['vendor_name']}</div>", unsafe_allow_html=True)
            r[1].markdown(f"<div style='{cell};color:#8B6A45'>{pay['description'] or '—'}</div>", unsafe_allow_html=True)
            r[2].markdown(f"<div style='{cell}'>{_inr(pay['amount'])}</div>", unsafe_allow_html=True)
            r[3].markdown(f"<div style='{cell};color:#8B6A45'>{pay['date']}</div>", unsafe_allow_html=True)
            r[4].markdown(
                f"<div style='{cell};color:{dc};font-weight:bold'>{days}d</div>",
                unsafe_allow_html=True,
            )
            partial_tag = " <span style='font-size:11px;color:#8B6A45'>(partial)</span>" if pay["status"] == "partial" else ""
            r[5].markdown(
                f"<div style='{cell};color:{dc};font-weight:bold'>{_inr(balance)}{partial_tag}</div>",
                unsafe_allow_html=True,
            )
            if r[6].button("Pay", key=f"pay_pay_{pay['id']}", use_container_width=True):
                st.session_state["paying_pay_id"] = pay["id"]
                st.session_state.pop("paying_rec_id", None)
                st.rerun()
            if r[7].button("Del", key=f"del_pay_{pay['id']}", use_container_width=True):
                st.session_state["confirm_del_pay_id"] = pay["id"]
                st.rerun()

        st.markdown(
            f"<div style='border-top:1px solid #E8D5B7;padding-top:8px;font-size:14px'>"
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
        with st.expander(f"Payment History: {len(paid_pays)} paid payable(s)", expanded=False):
            for pp in paid_pays:
                desc_str = f" · {pp['description']}" if pp["description"] else ""
                st.markdown(
                    f"✅ **{pp['vendor_name']}**{desc_str}, "
                    f"{_inr(pp['amount'])} · *{pp['date']}*"
                )
                pay_rows = conn.execute(
                    "SELECT * FROM payments WHERE type='payable' AND reference_id=? "
                    "ORDER BY payment_date ASC",
                    (pp["id"],),
                ).fetchall()
                for pay in pay_rows:
                    note = f", {pay['notes']}" if pay["notes"] else ""
                    st.markdown(f"&nbsp;&nbsp;&nbsp;↳ {pay['payment_date']}: {_inr(pay['amount_paid'])}{note}")
