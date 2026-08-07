import os
import streamlit as st
from datetime import date, datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from db.schema import init_db
from utils.settings import get_overdue_days

load_dotenv()


DB_PATH = os.getenv("DB_PATH", "db/erp.db")


@st.cache_resource
def _get_conn():
    return init_db(Path(DB_PATH))


_GREEN  = "#1B7F4F"
_YELLOW = "#D97706"
_RED    = "#C0392B"
_BLUE   = "#C17F3E"
_GROQ_MODEL = "openai/gpt-oss-120b"

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
_SYSTEM_PROMPT = (
    "You are a trusted friend who is also a sharp business advisor for Reclaimr — "
    "a small Indian manufacturing and trading business (Rwox manufactures rubber reclaiming "
    "products, Elastohorse trades rubber goods). "
    "Speak plainly and honestly — like texting a friend, not writing a report. "
    "Zero finance jargon. Use ₹ for money. Be specific, not vague. Under 120 words."
)


def _inr(val):
    if val >= 1_00_00_000: return f"₹{val/1_00_00_000:.2f} Cr"
    if val >= 1_00_000:    return f"₹{val/1_00_000:.2f} L"
    if val >= 1_000:       return f"₹{val/1_000:.1f} K"
    return f"₹{val:,.0f}"


def _groq_call(prompt: str) -> str:
    try:
        from groq import Groq
    except ImportError:
        return "ERROR:groq_not_installed"
    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        return "ERROR:no_key"
    client = Groq(api_key=key)
    resp = client.chat.completions.create(
        model=_GROQ_MODEL, max_tokens=300, reasoning_effort="low",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
    )
    return resp.choices[0].message.content


def _ensure_tables(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS monthly_updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month TEXT NOT NULL UNIQUE,
            rwox_sales REAL DEFAULT 0,
            elastohorse_sales REAL DEFAULT 0,
            rwox_cash REAL DEFAULT 0,
            elastohorse_cash REAL DEFAULT 0,
            expenses_json TEXT,
            big_payments_json TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS receivables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            company TEXT NOT NULL DEFAULT '',
            reference TEXT, amount REAL NOT NULL, date TEXT NOT NULL,
            notes TEXT, status TEXT NOT NULL DEFAULT 'outstanding',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS payables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_name TEXT NOT NULL, description TEXT,
            amount REAL NOT NULL, date TEXT NOT NULL,
            notes TEXT, status TEXT NOT NULL DEFAULT 'outstanding',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL, reference_id INTEGER NOT NULL,
            payment_date TEXT NOT NULL, amount_paid REAL NOT NULL,
            notes TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS batch_complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL, order_id INTEGER, customer_name TEXT,
            date TEXT NOT NULL, issue_type TEXT NOT NULL, description TEXT NOT NULL,
            quantity_affected REAL, physical_return INTEGER NOT NULL DEFAULT 0,
            quantity_returned REAL, initial_action TEXT NOT NULL,
            logged_by TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
    """)
    conn.commit()
    try:
        conn.execute("ALTER TABLE receivables ADD COLUMN last_contacted TEXT")
        conn.commit()
    except Exception:
        pass


def _build_ai_context(conn):
    today = date.today().isoformat()
    this_month = date.today().strftime("%Y-%m")
    overdue_days = get_overdue_days(conn)

    orders_row = conn.execute("""
        SELECT COUNT(*) as total,
               SUM(CASE WHEN status='received' THEN 1 ELSE 0 END) as received,
               SUM(CASE WHEN status='in_production' THEN 1 ELSE 0 END) as in_production,
               SUM(CASE WHEN status='dispatched' THEN 1 ELSE 0 END) as dispatched,
               SUM(CASE WHEN date(expected_dispatch_date) < date('now') AND status != 'dispatched' THEN 1 ELSE 0 END) as overdue
        FROM orders WHERE strftime('%Y-%m', created_at) = ?
    """, (this_month,)).fetchone()

    rev = conn.execute("""
        SELECT COALESCE(SUM(CASE WHEN rate_type='per_unit' THEN quantity*rate ELSE rate END), 0)
        FROM orders WHERE strftime('%Y-%m', created_at) = ?
    """, (this_month,)).fetchone()[0]

    rec_row = conn.execute("""
        SELECT COUNT(*) as cnt,
               COALESCE(SUM(r.amount - COALESCE(p_sum,0)), 0) as total
        FROM receivables r
        LEFT JOIN (
            SELECT reference_id, SUM(amount_paid) as p_sum FROM payments
            WHERE type='receivable' GROUP BY reference_id
        ) px ON px.reference_id = r.id
        WHERE r.status != 'paid'
        AND CAST(julianday('now','localtime') - julianday(r.date) AS INTEGER) > ?
    """, (overdue_days,)).fetchone()

    complaints = conn.execute(
        "SELECT COUNT(*) FROM batch_complaints WHERE status != 'resolved'"
    ).fetchone()[0]

    cash_row = conn.execute(
        "SELECT rwox_cash, elastohorse_cash FROM monthly_updates ORDER BY month DESC LIMIT 1"
    ).fetchone()

    prod_row = conn.execute("""
        SELECT COALESCE(SUM(output_kg),0) AS kg,
               COALESCE(SUM(total_batch_cost),0) AS cost
        FROM production_logs
        WHERE strftime('%Y-%m', date) = ?
    """, (this_month,)).fetchone()

    proc_rows = conn.execute("""
        SELECT item, unit_cost FROM procurement ORDER BY purchase_date DESC LIMIT 5
    """).fetchall()

    top_customers = conn.execute("""
        SELECT customer_name,
               SUM(CASE WHEN rate_type='per_unit' THEN quantity*rate ELSE rate END) AS rev
        FROM orders GROUP BY customer_name ORDER BY rev DESC LIMIT 5
    """).fetchall()

    lines = [
        f"Business: Reclaimr (Rwox manufacturing + Elastohorse trading), India",
        f"Today: {today}",
        f"This month's orders: {orders_row['total']} total | "
        f"{orders_row['received']} received | {orders_row['in_production']} in production | "
        f"{orders_row['dispatched']} dispatched | {orders_row['overdue']} overdue",
        f"This month's revenue: {_inr(rev)}",
        f"This month's production: {prod_row['kg']:,.1f} kg, cost {_inr(prod_row['cost'])}",
        f"Overdue receivables (45+ days): {rec_row['cnt']} entries, {_inr(rec_row['total'])}",
        f"Open complaints: {complaints}",
    ]
    if cash_row:
        total_cash = (cash_row["rwox_cash"] or 0) + (cash_row["elastohorse_cash"] or 0)
        lines.append(f"Combined cash in bank: {_inr(total_cash)}")
    if proc_rows:
        lines.append("Recent procurement: " + ", ".join(
            f"{r['item']} @{_inr(r['unit_cost'])}" for r in proc_rows
        ))
    if top_customers:
        lines.append("Top customers by revenue: " + ", ".join(
            f"{r['customer_name']} ({_inr(r['rev'])})" for r in top_customers
        ))
    return "\n".join(lines)


def _card(icon, label, value, sub, alert=False, warn=False):
    bg     = "#FFF0EE" if alert else ("#FFFDE0" if warn else "#FFF8F0")
    border = _RED if alert else (_YELLOW if warn else "#E8D5B7")
    vcol   = _RED if alert else (_YELLOW if warn else "#2C2218")
    return (
        f"<div style='background:{bg};border-radius:10px;padding:16px 14px;"
        f"border:1px solid {border};text-align:center;min-height:116px'>"
        f"<div style='font-size:22px'>{icon}</div>"
        f"<div style='color:{vcol};font-size:22px;font-weight:700;margin:4px 0'>{value}</div>"
        f"<div style='color:#8B6A45;font-size:12px;line-height:1.3'>{label}</div>"
        f"<div style='color:#8B6A45;font-size:11px;margin-top:4px'>{sub}</div>"
        f"</div>"
    )


def _row(icon, text, color):
    return (
        f"<div style='background:#FFF8F0;border-radius:8px;padding:14px 18px;"
        f"margin-bottom:8px;border-left:4px solid {color};border:1px solid #E8D5B7;"
        f"border-left:4px solid {color}'>"
        f"<span style='color:#2C2218;font-size:14px'>{icon} {text}</span>"
        f"</div>"
    )


def _week_item(top, bottom):
    return (
        f"<div style='background:#FFF8F0;border-radius:6px;padding:9px 12px;margin-bottom:6px;"
        f"border:1px solid #E8D5B7'>"
        f"<span style='color:#2C2218;font-size:13px'>{top}</span><br>"
        f"<span style='color:#8B6A45;font-size:11px'>{bottom}</span>"
        f"</div>"
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


def render_intelligence_page(conn):
    st.markdown(_DARK_CSS if st.session_state.get("dark_mode") else _WARM_CSS, unsafe_allow_html=True)
    _ensure_tables(conn)
    today = date.today()
    now_str = datetime.now().strftime("%H:%M")
    this_month = today.strftime("%Y-%m")
    overdue_days = get_overdue_days(conn)

    # ── Live counts for header & metrics ──────────────────────────────────────
    due_today_overdue = conn.execute(
        "SELECT COUNT(*) FROM orders "
        "WHERE date(expected_dispatch_date) <= date('now') AND status != 'dispatched'"
    ).fetchone()[0]

    overdue_rec_row = conn.execute("""
        SELECT COUNT(*) as cnt,
               COALESCE(SUM(r.amount - COALESCE(p_sum,0)), 0) as total
        FROM receivables r
        LEFT JOIN (
            SELECT reference_id, SUM(amount_paid) as p_sum FROM payments
            WHERE type='receivable' GROUP BY reference_id
        ) px ON px.reference_id = r.id
        WHERE r.status != 'paid'
        AND CAST(julianday('now','localtime') - julianday(r.date) AS INTEGER) > ?
    """, (overdue_days,)).fetchone()
    overdue_rec_count  = overdue_rec_row["cnt"]
    overdue_rec_amount = overdue_rec_row["total"]

    open_complaints = conn.execute(
        "SELECT COUNT(*) FROM batch_complaints WHERE status != 'resolved'"
    ).fetchone()[0]

    stagnant_count = conn.execute(
        "SELECT COUNT(*) FROM orders "
        "WHERE date(created_at) <= date('now','-7 days') AND status='received'"
    ).fetchone()[0]

    overdue_pay_count = conn.execute("""
        SELECT COUNT(*) FROM payables p
        WHERE p.status != 'paid'
        AND CAST(julianday('now','localtime') - julianday(p.date) AS INTEGER) > ?
    """, (overdue_days,)).fetchone()[0]

    total_issues = (due_today_overdue + overdue_rec_count + open_complaints
                    + stagnant_count + overdue_pay_count)

    # ── Section 1: Good Morning ────────────────────────────────────────────────
    if total_issues == 0:
        status_line  = "Both businesses are on track — nothing urgent today."
        status_color = _GREEN
    elif total_issues == 1:
        status_line  = "1 thing needs your attention today."
        status_color = _YELLOW
    else:
        status_line  = f"{total_issues} things need your attention today."
        status_color = _RED

    st.markdown(
        f"<div style='background:#FFF8F0;border-radius:14px;padding:24px 28px;"
        f"border:1px solid #E8D5B7;margin-bottom:20px'>"
        f"<h2 style='color:#2C2218;margin:0 0 4px 0'>Good morning 👋</h2>"
        f"<p style='color:#8B6A45;font-size:15px;margin:0 0 10px 0'>"
        f"{today.strftime('%A, %d %B %Y')}</p>"
        f"<p style='color:{status_color};font-size:18px;font-weight:600;margin:0 0 8px 0'>"
        f"{status_line}</p>"
        f"<p style='color:#8B6A45;font-size:12px;margin:0'>Last updated: {now_str}</p>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── Ask Your Business (top) ────────────────────────────────────────────────
    groq_key = os.getenv("GROQ_API_KEY", "")
    if groq_key:
        aq_col, _ = st.columns([6, 2])
        with aq_col:
            question_top = st.text_input(
                "Ask your business anything...",
                placeholder="e.g. Can we meet this week's dispatch targets?",
                key="intel_question",
            )
        abtn_col, _ = st.columns([1, 7])
        with abtn_col:
            ask_top = st.button("Ask 🤖", type="primary",
                                disabled=not question_top.strip(), key="intel_ask")
        if ask_top:
            context = _build_ai_context(conn)
            prompt  = (
                f"Live business data:\n{context}\n\n"
                f"Question: {question_top.strip()}\n\n"
                f"Answer in plain conversational language. "
                f"If yes or no is needed, say it clearly first. Under 100 words."
            )
            with st.spinner("Thinking..."):
                result = _groq_call(prompt)
            if result.startswith("ERROR:"):
                err = result.split(":")[1]
                msgs = {
                    "no_key":             "No GROQ_API_KEY found in .env.",
                    "groq_not_installed": "groq package not installed. Run: pip install groq",
                }
                st.error(msgs.get(err, "Could not get a response — check your API key."))
            else:
                st.session_state["intel_answer"] = (question_top.strip(), result)

        if "intel_answer" in st.session_state:
            q_text, a_text = st.session_state["intel_answer"]
            st.markdown(
                f"<div style='background:#FFF0DC;border-radius:12px;padding:18px 22px;"
                f"border:1px solid #E8D5B7;margin-bottom:8px'>"
                f"<p style='color:#C17F3E;font-size:12px;margin:0 0 6px 0'>"
                f"You asked: <i>{q_text}</i></p>"
                f"<p style='color:#2C2218;line-height:1.8;font-size:15px;margin:0'>"
                f"{a_text.replace(chr(10), '<br>')}"
                f"</p></div>",
                unsafe_allow_html=True,
            )

    st.divider()

    # ── Section 2: 5 Numbers ──────────────────────────────────────────────────
    st.subheader("Today's 5 Numbers")

    cash_row = conn.execute(
        "SELECT rwox_cash, elastohorse_cash, month FROM monthly_updates ORDER BY month DESC LIMIT 1"
    ).fetchone()
    total_cash   = ((cash_row["rwox_cash"] or 0) + (cash_row["elastohorse_cash"] or 0)) if cash_row else None
    cash_display = _inr(total_cash) if total_cash else "—"
    cash_sub     = f"as of {cash_row['month']}" if cash_row else "not yet updated"

    last_month_dt = (today.replace(day=1) - timedelta(days=1))
    last_month    = last_month_dt.strftime("%Y-%m")

    this_rev = conn.execute("""
        SELECT COALESCE(SUM(CASE WHEN rate_type='per_unit' THEN quantity*rate ELSE rate END), 0)
        FROM orders WHERE strftime('%Y-%m', created_at) = ?
    """, (this_month,)).fetchone()[0]

    last_rev = conn.execute("""
        SELECT COALESCE(SUM(CASE WHEN rate_type='per_unit' THEN quantity*rate ELSE rate END), 0)
        FROM orders WHERE strftime('%Y-%m', created_at) = ?
    """, (last_month,)).fetchone()[0]

    fy_monthly_avg = (15_451_424 + 14_972_732) / 12
    rev_target = last_rev if last_rev > 0 else fy_monthly_avg
    rev_pct    = round(this_rev / rev_target * 100, 1) if rev_target > 0 else 0

    n1, n2, n3, n4, n5 = st.columns(5)
    n1.markdown(_card("📦", "Orders due / overdue", str(due_today_overdue),
                      "for dispatch today", alert=due_today_overdue > 0), unsafe_allow_html=True)
    n2.markdown(_card("💰", "Receivables 45+ days",
                      _inr(overdue_rec_amount) if overdue_rec_amount > 0 else "₹0",
                      f"{overdue_rec_count} {'entry' if overdue_rec_count == 1 else 'entries'}",
                      alert=overdue_rec_amount > 0), unsafe_allow_html=True)
    n3.markdown(_card("🏦", "Combined cash in bank", cash_display, cash_sub), unsafe_allow_html=True)
    n4.markdown(_card("⚠️", "Open complaints", str(open_complaints), "unresolved",
                      alert=open_complaints > 0), unsafe_allow_html=True)
    n5.markdown(_card("📈", "Revenue vs target", f"{rev_pct}%",
                      f"{_inr(this_rev)} of {_inr(rev_target)}",
                      alert=rev_pct < 50 and rev_pct > 0,
                      warn=50 <= rev_pct < 80), unsafe_allow_html=True)

    st.divider()

    # ── Section 3: Action List ─────────────────────────────────────────────────
    st.subheader("Action List — What to Do Today")

    # (urgency_days, icon, color, html_text, action_type, record_id)
    # action_type: "dispatch" | "contacted" | "resolve_complaint" | "to_production" | None
    actions = []

    # Overdue orders → Mark Dispatched
    for r in conn.execute("""
        SELECT o.id, o.customer_name, o.product, o.expected_dispatch_date,
               CAST(julianday('now','localtime') - julianday(o.expected_dispatch_date) AS INTEGER) AS days_late
        FROM orders o JOIN companies c ON o.company_id=c.id
        WHERE date(o.expected_dispatch_date) < date('now') AND o.status != 'dispatched'
        ORDER BY o.expected_dispatch_date ASC
    """).fetchall():
        actions.append((r["days_late"], "📦", _RED,
            f"Dispatch <b>{r['customer_name']}</b> order: {r['product']} "
            f"<span style='color:{_RED}'>({r['days_late']} {'day' if r['days_late']==1 else 'days'} overdue)</span>",
            "dispatch", r["id"]))

    # Overdue receivables → Mark as Contacted
    for r in conn.execute("""
        SELECT r.id, r.customer_name, r.amount - COALESCE(SUM(p.amount_paid),0) AS balance,
               CAST(julianday('now','localtime') - julianday(r.date) AS INTEGER) AS days
        FROM receivables r
        LEFT JOIN payments p ON p.type='receivable' AND p.reference_id=r.id
        WHERE r.status != 'paid'
        GROUP BY r.id HAVING days > ?
        ORDER BY days DESC
    """, (overdue_days,)).fetchall():
        actions.append((r["days"], "💰", _RED,
            f"Chase payment from <b>{r['customer_name']}</b>, "
            f"{_inr(r['balance'])} outstanding for "
            f"<span style='color:{_RED}'>{r['days']} days</span>",
            "contacted", r["id"]))

    # Open complaints → Mark Resolved
    for r in conn.execute("""
        SELECT bc.id, bc.customer_name, bc.issue_type,
               CAST(julianday('now','localtime') - julianday(bc.date) AS INTEGER) AS days_open,
               pl.batch_ref
        FROM batch_complaints bc
        JOIN production_logs pl ON bc.batch_id = pl.id
        WHERE bc.status != 'resolved'
        ORDER BY days_open DESC
    """).fetchall():
        customer = r["customer_name"] or "unknown customer"
        actions.append((r["days_open"], "⚠️", _YELLOW,
            f"Follow up on <b>{r['issue_type']}</b> from <b>{customer}</b> "
            f"(batch {r['batch_ref']}), "
            f"<span style='color:{_YELLOW}'>{r['days_open']} days open</span>",
            "resolve_complaint", r["id"]))

    # Overdue payables — no action button (handle from Credit page)
    for r in conn.execute("""
        SELECT p.vendor_name, p.amount - COALESCE(SUM(pm.amount_paid),0) AS balance,
               CAST(julianday('now','localtime') - julianday(p.date) AS INTEGER) AS days
        FROM payables p
        LEFT JOIN payments pm ON pm.type='payable' AND pm.reference_id=p.id
        WHERE p.status != 'paid'
        GROUP BY p.id HAVING days > 30
        ORDER BY days DESC
    """).fetchall():
        actions.append((r["days"], "🧾", _YELLOW,
            f"Pay <b>{r['vendor_name']}</b>, "
            f"{_inr(r['balance'])} due, "
            f"<span style='color:{_YELLOW}'>{r['days']} days outstanding</span>",
            None, None))

    # Stagnant orders → Move to Production
    for r in conn.execute("""
        SELECT o.id, o.customer_name, o.product, o.expected_dispatch_date,
               CAST(julianday('now','localtime') - julianday(o.created_at) AS INTEGER) AS waiting_days
        FROM orders o JOIN companies c ON o.company_id=c.id
        WHERE date(o.created_at) <= date('now','-7 days') AND o.status='received'
        ORDER BY waiting_days DESC
    """).fetchall():
        actions.append((r["waiting_days"], "🏭", _YELLOW,
            f"Start production for <b>{r['customer_name']}</b>: {r['product']}, "
            f"waiting <span style='color:{_YELLOW}'>{r['waiting_days']} days</span>, "
            f"due {r['expected_dispatch_date']}",
            "to_production", r["id"]))

    actions.sort(key=lambda x: x[0], reverse=True)

    _BTN_LABELS = {
        "dispatch":          "✅ Mark Dispatched",
        "contacted":         "📞 Mark Contacted",
        "resolve_complaint": "✅ Mark Resolved",
        "to_production":     "🏭 Move to Production",
    }

    if not actions:
        st.markdown(
            "<div style='background:#F0FFF4;border-radius:10px;padding:20px 24px;"
            "border:1px solid #E8D5B7;text-align:center'>"
            "<span style='color:#1B7F4F;font-size:18px;font-weight:600'>"
            "✅ All clear — nothing urgent today</span>"
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        for i, (_, icon, color, text, action_type, record_id) in enumerate(actions):
            if action_type:
                tcol, bcol = st.columns([7, 2])
            else:
                tcol = st.container()
                bcol = None
            with tcol:
                st.markdown(
                    f"<div style='background:#FFF8F0;border-radius:8px;padding:14px 18px;"
                    f"margin-bottom:4px;border-left:4px solid {color};border:1px solid #E8D5B7;"
                    f"border-left:4px solid {color}'>"
                    f"<span style='color:#2C2218;font-size:14px'>{icon} {text}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            if bcol:
                with bcol:
                    st.markdown("<div style='padding-top:6px'>", unsafe_allow_html=True)
                    if st.button(_BTN_LABELS[action_type],
                                 key=f"act_{action_type}_{record_id}_{i}",
                                 use_container_width=True):
                        if action_type == "dispatch":
                            conn.execute(
                                "UPDATE orders SET status='dispatched' WHERE id=?", (record_id,))
                        elif action_type == "contacted":
                            conn.execute(
                                "UPDATE receivables SET last_contacted=date('now','localtime') WHERE id=?",
                                (record_id,))
                        elif action_type == "resolve_complaint":
                            conn.execute(
                                "UPDATE batch_complaints SET status='resolved' WHERE id=?", (record_id,))
                        elif action_type == "to_production":
                            conn.execute(
                                "UPDATE orders SET status='in_production' WHERE id=?", (record_id,))
                        conn.commit()
                        st.success("Done!")
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)

    st.divider()

    # ── Section 4: This Week at a Glance ──────────────────────────────────────
    st.subheader("This Week at a Glance")

    week_end_s = (today + timedelta(days=7)).isoformat()
    today_s    = today.isoformat()

    wc1, wc2, wc3, wc4 = st.columns(4)

    with wc1:
        st.markdown("**📦 Dispatches Due**")
        rows = conn.execute("""
            SELECT o.customer_name, o.product, o.expected_dispatch_date, c.name AS company
            FROM orders o JOIN companies c ON o.company_id=c.id
            WHERE date(o.expected_dispatch_date) BETWEEN ? AND ? AND o.status != 'dispatched'
            ORDER BY o.expected_dispatch_date ASC
        """, (today_s, week_end_s)).fetchall()
        if rows:
            st.markdown("".join(_week_item(
                f"<b>{r['customer_name']}</b>: {r['product']}",
                f"{r['expected_dispatch_date']} · {r['company']}"
            ) for r in rows), unsafe_allow_html=True)
        else:
            st.caption("None this week")

    with wc2:
        st.markdown("**💰 Payments Expected**")
        rows = conn.execute("""
            SELECT r.customer_name,
                   r.amount - COALESCE(SUM(p.amount_paid),0) AS balance,
                   r.date
            FROM receivables r
            LEFT JOIN payments p ON p.type='receivable' AND p.reference_id=r.id
            WHERE r.status != 'paid' AND date(r.date) BETWEEN ? AND ?
            GROUP BY r.id HAVING balance > 0
            ORDER BY r.date ASC
        """, (today_s, week_end_s)).fetchall()
        if rows:
            st.markdown("".join(_week_item(
                f"<b>{r['customer_name']}</b>",
                f"<span style='color:{_GREEN}'>{_inr(r['balance'])}</span> · {r['date']}"
            ) for r in rows), unsafe_allow_html=True)
        else:
            st.caption("None scheduled")

    with wc3:
        st.markdown("**🧾 Vendor Payments Due**")
        rows = conn.execute("""
            SELECT p.vendor_name,
                   p.amount - COALESCE(SUM(pm.amount_paid),0) AS balance,
                   p.date
            FROM payables p
            LEFT JOIN payments pm ON pm.type='payable' AND pm.reference_id=p.id
            WHERE p.status != 'paid' AND date(p.date) BETWEEN ? AND ?
            GROUP BY p.id HAVING balance > 0
            ORDER BY p.date ASC
        """, (today_s, week_end_s)).fetchall()
        if rows:
            st.markdown("".join(_week_item(
                f"<b>{r['vendor_name']}</b>",
                f"<span style='color:{_RED}'>{_inr(r['balance'])}</span> · {r['date']}"
            ) for r in rows), unsafe_allow_html=True)
        else:
            st.caption("None this week")

    with wc4:
        st.markdown("**🏭 Production Needed**")
        rows = conn.execute("""
            SELECT o.customer_name, o.product, o.expected_dispatch_date, c.name AS company
            FROM orders o JOIN companies c ON o.company_id=c.id
            WHERE o.status IN ('received','in_production')
            AND date(o.expected_dispatch_date) BETWEEN ? AND ?
            ORDER BY o.expected_dispatch_date ASC
        """, (today_s, week_end_s)).fetchall()
        if rows:
            st.markdown("".join(_week_item(
                f"<b>{r['product']}</b> for {r['customer_name']}",
                f"Due {r['expected_dispatch_date']} · {r['company']}"
            ) for r in rows), unsafe_allow_html=True)
        else:
            st.caption("None pending for this week")

    # ── Section 6: Weekly Summary (Mondays only) ───────────────────────────────
    if today.weekday() == 0:
        st.divider()
        st.subheader("Weekly Summary")
        st.caption("Here's how last week went.")

        lw_start = (today - timedelta(days=7)).isoformat()
        lw_end   = (today - timedelta(days=1)).isoformat()

        lw_rev = conn.execute("""
            SELECT COALESCE(SUM(CASE WHEN rate_type='per_unit' THEN quantity*rate ELSE rate END), 0)
            FROM orders WHERE date(created_at) BETWEEN ? AND ?
        """, (lw_start, lw_end)).fetchone()[0]

        lw_dispatched = conn.execute("""
            SELECT COUNT(*) FROM orders WHERE status='dispatched'
            AND date(created_at) BETWEEN ? AND ?
        """, (lw_start, lw_end)).fetchone()[0]

        lw_prod = conn.execute("""
            SELECT COALESCE(SUM(output_kg), 0) FROM production_logs
            WHERE date BETWEEN ? AND ?
        """, (lw_start, lw_end)).fetchone()[0]

        ws1, ws2, ws3 = st.columns(3)
        ws1.metric("Last Week Revenue",     _inr(lw_rev) if lw_rev else "—")
        ws2.metric("Orders Dispatched",     lw_dispatched)
        ws3.metric("Production Output",     f"{lw_prod:,.1f} kg" if lw_prod else "—")

        recurring = conn.execute("""
            SELECT customer_name, COUNT(*) as cnt
            FROM batch_complaints WHERE status != 'resolved' AND customer_name IS NOT NULL
            GROUP BY customer_name HAVING cnt > 1
            ORDER BY cnt DESC LIMIT 3
        """).fetchall()

        if recurring:
            st.markdown("**Recurring issues to watch:**")
            for r in recurring:
                st.markdown(f"- **{r['customer_name']}** — {r['cnt']} open complaints")
        else:
            st.success("✅ No recurring complaints from the same customer.")
