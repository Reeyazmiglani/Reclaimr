import streamlit as st
import plotly.graph_objects as go
from datetime import date
import json
import os
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# FY 2024-25 DATA
# ─────────────────────────────────────────────────────────────────────────────
FY25 = {
    "Rwox": {
        "sales":        15_451_424,
        "gross_profit":  2_682_594,
        "net_profit":      346_111,
        "cash_bank":       478_342,
        "stock":         1_925_310,
        "debtors":               0,
        "total_assets":  4_593_152,
    },
    "Elastohorse": {
        "sales":        14_972_732,
        "gross_profit":  2_412_690,
        "net_profit":      855_058,
        "cash_bank":       670_249,
        "stock":           201_190,
        "debtors":       1_320_647,
        "total_assets":  6_372_835,
    },
}

EXPENSES = {
    "Rwox": [
        ("Raw materials",  10_601_525),
        ("Worker wages",      941_800),
        ("Staff salaries",  1_364_000),
        ("Electricity",       145_300),
        ("Diesel / fuel",     235_000),
        ("Transport",         574_214),
        ("Other costs",       500_000),
    ],
    "Elastohorse": [
        ("Stock purchased", 11_028_707),
        ("Staff salaries",     565_900),
        ("Transport",          498_071),
        ("Interest on loans",  313_895),
        ("Other costs",        270_000),
    ],
}

# ─────────────────────────────────────────────────────────────────────────────
# STYLE CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
_GREEN  = "#2ecc71"
_YELLOW = "#f39c12"
_RED    = "#e74c3c"
_BLUE   = "#3498db"

_PIE_COLORS = [
    "#3498db", "#e67e22", "#2ecc71", "#9b59b6",
    "#e74c3c", "#1abc9c", "#f39c12", "#95a5a6",
]

_PLOT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font_color="#ccc",
    margin=dict(t=45, b=30, l=10, r=10),
)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def _inr(val: float) -> str:
    if val >= 1_00_00_000: return f"₹{val/1_00_00_000:.2f} Cr"
    if val >= 1_00_000:    return f"₹{val/1_00_000:.2f} L"
    if val >= 1_000:       return f"₹{val/1_000:.1f} K"
    return f"₹{val:,.0f}"


def _mc(pct: float) -> str:   # margin color
    return _GREEN if pct >= 5 else (_YELLOW if pct >= 2 else _RED)


def _me(pct: float) -> str:   # margin emoji
    return "✅" if pct >= 5 else ("⚠️" if pct >= 2 else "🔴")


def _ensure_tables(conn) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS monthly_updates (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            month             TEXT NOT NULL UNIQUE,
            rwox_sales        REAL DEFAULT 0,
            elastohorse_sales REAL DEFAULT 0,
            rwox_cash         REAL DEFAULT 0,
            elastohorse_cash  REAL DEFAULT 0,
            expenses_json     TEXT,
            big_payments_json TEXT,
            notes             TEXT,
            created_at        TEXT DEFAULT (datetime('now','localtime'))
        );
    """)
    conn.commit()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1 — HOW ARE WE DOING?
# ─────────────────────────────────────────────────────────────────────────────
def _tab_snapshot() -> None:
    st.subheader("FY 2024-25 at a Glance")
    st.caption("Full-year results for both companies. Use this to benchmark monthly performance and understand where margins stand.")

    col1, col2 = st.columns(2)
    for col, co in [(col1, "Rwox"), (col2, "Elastohorse")]:
        d   = FY25[co]
        nm  = d["net_profit"] / d["sales"] * 100
        mc  = _mc(nm)
        me  = _me(nm)
        debtor_html = (
            f"<p style='color:{_RED};margin:6px 0'>⚠️ Customers owe us "
            f"<b>{_inr(d['debtors'])}</b> — check if any is overdue</p>"
            if d["debtors"] > 0
            else f"<p style='color:{_GREEN};margin:6px 0'>✅ No money owed by customers</p>"
        )
        with col:
            st.markdown(
                f"<div style='background:#1a1a2e;border-radius:12px;padding:22px 24px;"
                f"border:1px solid #2a3a5e;margin-bottom:12px'>"
                f"<h3 style='color:#fff;margin:0 0 14px 0'>{co}</h3>"
                f"<p style='color:#fff;font-size:18px;font-weight:700;margin:4px 0'>"
                f"💰 We made {_inr(d['sales'])} in sales this year</p>"
                f"<p style='color:{mc};margin:6px 0'>{me} After all costs, we kept "
                f"<b>{_inr(d['net_profit'])}</b> ({nm:.1f}%)</p>"
                f"<p style='color:#ccc;margin:6px 0'>🏦 Cash in bank right now: "
                f"<b>{_inr(d['cash_bank'])}</b></p>"
                f"{debtor_html}"
                f"<p style='color:#aaa;margin:6px 0'>📦 Unsold stock in warehouse: "
                f"{_inr(d['stock'])}</p>"
                f"</div>",
                unsafe_allow_html=True,
            )

    # Combined card
    t_sales  = FY25["Rwox"]["sales"]      + FY25["Elastohorse"]["sales"]
    t_profit = FY25["Rwox"]["net_profit"] + FY25["Elastohorse"]["net_profit"]
    t_cash   = FY25["Rwox"]["cash_bank"]  + FY25["Elastohorse"]["cash_bank"]
    comb_nm  = t_profit / t_sales * 100

    st.markdown(
        f"<div style='background:#0d2137;border-radius:12px;padding:22px 24px;"
        f"border:1px solid #1a4a7a;margin-bottom:16px'>"
        f"<h3 style='color:{_BLUE};margin:0 0 14px 0'>🌐 Both Businesses Together</h3>"
        f"<div style='display:grid;grid-template-columns:1fr 1fr 1fr;gap:20px'>"
        f"<div><p style='color:#888;font-size:12px;margin:0'>COMBINED SALES</p>"
        f"<p style='color:#fff;font-size:24px;font-weight:700;margin:4px 0'>{_inr(t_sales)}</p></div>"
        f"<div><p style='color:#888;font-size:12px;margin:0'>COMBINED PROFIT</p>"
        f"<p style='color:{_mc(comb_nm)};font-size:24px;font-weight:700;margin:4px 0'>{_inr(t_profit)}</p>"
        f"<p style='color:#888;font-size:12px;margin:0'>{comb_nm:.1f}% of total sales</p></div>"
        f"<div><p style='color:#888;font-size:12px;margin:0'>CASH IN BANK</p>"
        f"<p style='color:#fff;font-size:24px;font-weight:700;margin:4px 0'>{_inr(t_cash)}</p></div>"
        f"</div></div>",
        unsafe_allow_html=True,
    )

    st.divider()
    mc1, mc2, mc3, mc4 = st.columns(4)
    r_nm = FY25["Rwox"]["net_profit"]       / FY25["Rwox"]["sales"] * 100
    e_nm = FY25["Elastohorse"]["net_profit"] / FY25["Elastohorse"]["sales"] * 100
    r_gm = FY25["Rwox"]["gross_profit"]       / FY25["Rwox"]["sales"] * 100
    e_gm = FY25["Elastohorse"]["gross_profit"] / FY25["Elastohorse"]["sales"] * 100
    mc1.metric("Rwox Net Margin",         f"{r_nm:.1f}%", help="% of sales kept as profit after all expenses")
    mc2.metric("Elastohorse Net Margin",  f"{e_nm:.1f}%")
    mc3.metric("Rwox Gross Margin",       f"{r_gm:.1f}%", help="% kept after cost of goods sold only")
    mc4.metric("Elastohorse Gross Margin",f"{e_gm:.1f}%")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2 — WHERE IS YOUR MONEY GOING?
# ─────────────────────────────────────────────────────────────────────────────
def _tab_expenses() -> None:
    st.subheader("Expense Breakdown")
    st.caption("Where every rupee of revenue is going. Any category above 40% of revenue is flagged — that's where cost pressure originates.")

    col1, col2 = st.columns(2)
    for col, co in [(col1, "Rwox"), (col2, "Elastohorse")]:
        sales    = FY25[co]["sales"]
        exp_list = EXPENSES[co]
        labels   = [e[0] for e in exp_list]
        values   = [e[1] for e in exp_list]

        with col:
            st.markdown(f"#### {co}")

            fig = go.Figure(go.Pie(
                labels=labels, values=values,
                marker_colors=_PIE_COLORS,
                hovertemplate="<b>%{label}</b><br>₹%{value:,.0f}<br>%{percent}<extra></extra>",
                hole=0.4,
            ))
            fig.update_layout(height=340, legend=dict(orientation="h", y=-0.4), **_PLOT)
            st.plotly_chart(fig, use_container_width=True)

            for label, amount in exp_list:
                per_100 = amount / sales * 100
                if per_100 > 40:
                    clr, flag = _RED, "🔴"
                elif per_100 > 20:
                    clr, flag = _YELLOW, "⚠️"
                else:
                    clr, flag = "#aaa", "   "

                st.markdown(
                    f"<div style='display:flex;justify-content:space-between;align-items:center;"
                    f"padding:5px 0;border-bottom:1px solid #222'>"
                    f"<span style='color:#ccc'>{flag} {label}</span>"
                    f"<span><b style='color:{clr}'>₹{per_100:.1f}</b>"
                    f"<span style='color:#ccc'> per ₹100 earned</span> &nbsp;"
                    f"<span style='color:#555;font-size:12px'>({_inr(amount)})</span></span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                if per_100 > 40:
                    st.markdown(
                        f"<p style='color:{_RED};font-size:12px;margin:2px 0 4px 20px'>"
                        f"This single expense is more than 40% of revenue — worth watching closely.</p>",
                        unsafe_allow_html=True,
                    )


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3 — HEALTH CHECK
# ─────────────────────────────────────────────────────────────────────────────
def _health_row(emoji: str, title: str,
                rwox_text: str, rwox_color: str,
                elasto_text: str, elasto_color: str,
                action: str | None = None) -> None:
    st.markdown(f"#### {emoji} {title}")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            f"<div style='background:#111;border-radius:8px;padding:14px;"
            f"border-left:4px solid {rwox_color};margin-bottom:8px'>"
            f"<b style='color:{rwox_color}'>Rwox</b><br>"
            f"<span style='color:#ccc;font-size:14px'>{rwox_text}</span></div>",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"<div style='background:#111;border-radius:8px;padding:14px;"
            f"border-left:4px solid {elasto_color};margin-bottom:8px'>"
            f"<b style='color:{elasto_color}'>Elastohorse</b><br>"
            f"<span style='color:#ccc;font-size:14px'>{elasto_text}</span></div>",
            unsafe_allow_html=True,
        )
    if action:
        st.markdown(
            f"<p style='color:{_YELLOW};font-size:13px;margin:0 0 6px 0'>"
            f"💡 Action: {action}</p>",
            unsafe_allow_html=True,
        )
    st.markdown("<br>", unsafe_allow_html=True)


def _tab_health() -> None:
    st.subheader("Health Check")
    st.caption("Five indicators that tell you whether the business is operating within healthy parameters, with a specific action where something needs attention.")

    r = FY25["Rwox"]
    e = FY25["Elastohorse"]
    r_nm = r["net_profit"] / r["sales"] * 100
    e_nm = e["net_profit"] / e["sales"] * 100
    r_monthly_exp = (r["sales"] - r["net_profit"]) / 12
    e_monthly_exp = (e["sales"] - e["net_profit"]) / 12
    r_stock_m = r["stock"] / (r["sales"] / 12)
    e_stock_m = e["stock"] / (e["sales"] / 12)
    e_loan_est = 313_895 / 0.15   # rough estimate: interest / assumed 15% rate
    e_loan_pct = e_loan_est / e["total_assets"] * 100

    # 1. Profit margin
    _health_row(
        _me(min(r_nm, e_nm)),
        "Are we making enough profit?",
        f"Keeping {r_nm:.1f}% of every sale as profit",
        _mc(r_nm),
        f"Keeping {e_nm:.1f}% of every sale as profit",
        _mc(e_nm),
        "Rwox is below 5% — go line by line through expenses and find what can be cut this month."
        if r_nm < 5 else None,
    )

    # 2. Can we pay bills?
    r_ok = r["cash_bank"] >= r_monthly_exp
    e_ok = e["cash_bank"] >= e_monthly_exp
    _health_row(
        "✅" if (r_ok and e_ok) else "🔴",
        "Can we pay our bills next month?",
        (f"Monthly expenses ≈ {_inr(r_monthly_exp)}, cash = {_inr(r['cash_bank'])} — "
         + ("OK ✅" if r_ok else "Tight 🔴")),
        _GREEN if r_ok else _RED,
        (f"Monthly expenses ≈ {_inr(e_monthly_exp)}, cash = {_inr(e['cash_bank'])} — "
         + ("OK ✅" if e_ok else "Tight 🔴")),
        _GREEN if e_ok else _RED,
        "Chase outstanding payments right away. Hold off on big purchases until cash improves."
        if not (r_ok and e_ok) else None,
    )

    # 3. Customers paying on time?
    _health_row(
        "⚠️" if e["debtors"] > 0 else "✅",
        "Are customers paying on time?",
        "No outstanding customer payments — all clear",
        _GREEN,
        f"Customers owe {_inr(e['debtors'])} — check if any invoice is older than 45 days",
        _YELLOW if e["debtors"] > 0 else _GREEN,
        "Call the top 3 customers by amount owed. Ask for payment this week."
        if e["debtors"] > 0 else None,
    )

    # 4. Too much unsold stock?
    r_sw = r_stock_m > 2
    e_sw = e_stock_m > 2
    _health_row(
        "⚠️" if (r_sw or e_sw) else "✅",
        "Are we sitting on too much unsold stock?",
        f"{r_stock_m:.1f} months of stock sitting ({_inr(r['stock'])})",
        _YELLOW if r_sw else _GREEN,
        f"{e_stock_m:.1f} months of stock sitting ({_inr(e['stock'])})",
        _YELLOW if e_sw else _GREEN,
        "Push a sales drive on slow-moving items. Avoid restocking until levels come down."
        if (r_sw or e_sw) else None,
    )

    # 5. Too dependent on loans?
    loan_bad = e_loan_pct > 50
    _health_row(
        "🔴" if loan_bad else "⚠️",
        "Are we too dependent on loans?",
        "No significant loan data available for Rwox",
        "#666",
        f"Estimated loans ≈ {_inr(e_loan_est)} ({e_loan_pct:.0f}% of assets, based on interest paid)",
        _RED if loan_bad else _YELLOW,
        "Prioritise paying down loans before taking new ones. High debt is risky if sales slow down."
        if loan_bad else None,
    )


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4 — MONTHLY UPDATE
# ─────────────────────────────────────────────────────────────────────────────
def _tab_monthly(conn) -> None:
    st.subheader("Monthly Update")
    st.caption("Keep your dashboard current. Three minutes at the start of each month is all it takes.")

    with st.form("monthly_update_form"):
        st.markdown("**Enter current month figures:**")
        month_str = st.text_input("Month (YYYY-MM)", value=date.today().strftime("%Y-%m"))

        sa, sb = st.columns(2)
        with sa:
            r_sales = st.number_input("Rwox — Sales this month (₹)",        min_value=0.0, step=10_000.0, format="%.0f")
            r_cash  = st.number_input("Rwox — Cash in bank today (₹)",       min_value=0.0, step=10_000.0, format="%.0f")
        with sb:
            e_sales = st.number_input("Elastohorse — Sales this month (₹)",  min_value=0.0, step=10_000.0, format="%.0f")
            e_cash  = st.number_input("Elastohorse — Cash in bank today (₹)", min_value=0.0, step=10_000.0, format="%.0f")

        st.markdown("**Main expenses this month** — one per line, format: Name, Amount")
        exp_text = st.text_area("E.g.  Raw materials, 500000", height=90, label_visibility="collapsed")

        st.markdown("**Payments due this month** — one per line, format: Name, Amount")
        pay_text = st.text_area("E.g.  Loan repayment, 200000", height=70, label_visibility="collapsed")

        notes   = st.text_area("Any notes?", height=60)
        save_ok = st.form_submit_button("Save Monthly Update", type="primary")

    if save_ok:
        def _parse(text: str) -> list:
            out = []
            for line in text.strip().splitlines():
                if "," in line:
                    parts = line.rsplit(",", 1)
                    try:
                        out.append({"label": parts[0].strip(),
                                    "amount": float(parts[1].strip().replace(",", ""))})
                    except ValueError:
                        pass
            return out

        conn.execute(
            """INSERT INTO monthly_updates
               (month, rwox_sales, elastohorse_sales, rwox_cash, elastohorse_cash,
                expenses_json, big_payments_json, notes)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(month) DO UPDATE SET
                 rwox_sales=excluded.rwox_sales,
                 elastohorse_sales=excluded.elastohorse_sales,
                 rwox_cash=excluded.rwox_cash,
                 elastohorse_cash=excluded.elastohorse_cash,
                 expenses_json=excluded.expenses_json,
                 big_payments_json=excluded.big_payments_json,
                 notes=excluded.notes""",
            (month_str, r_sales, e_sales, r_cash, e_cash,
             json.dumps(_parse(exp_text)), json.dumps(_parse(pay_text)),
             notes.strip() or None),
        )
        conn.commit()
        st.success("Monthly update saved!")
        st.rerun()

    rows = conn.execute(
        "SELECT month, rwox_sales, elastohorse_sales, rwox_cash, elastohorse_cash "
        "FROM monthly_updates ORDER BY month ASC LIMIT 6"
    ).fetchall()

    if not rows:
        st.info("No monthly updates yet. Enter your first update above.")
        return

    st.divider()
    st.markdown("#### Last 6 Months — Revenue Trend")

    months   = [r["month"] for r in rows]
    r_vals   = [r["rwox_sales"] for r in rows]
    e_vals   = [r["elastohorse_sales"] for r in rows]

    fig = go.Figure()
    fig.add_trace(go.Bar(x=months, y=r_vals, name="Rwox", marker_color=_BLUE,
                         hovertemplate="<b>Rwox</b><br>%{x}<br>₹%{y:,.0f}<extra></extra>"))
    fig.add_trace(go.Bar(x=months, y=e_vals, name="Elastohorse", marker_color="#e67e22",
                         hovertemplate="<b>Elastohorse</b><br>%{x}<br>₹%{y:,.0f}<extra></extra>"))
    fig.update_layout(
        title="Monthly Sales", height=320, barmode="group",
        xaxis=dict(gridcolor="#333"),
        yaxis=dict(gridcolor="#333", tickprefix="₹"),
        legend=dict(orientation="h", y=-0.3),
        **_PLOT,
    )
    st.plotly_chart(fig, use_container_width=True)

    latest = conn.execute(
        "SELECT * FROM monthly_updates ORDER BY month DESC LIMIT 1"
    ).fetchone()

    if latest:
        la, lb = st.columns(2)
        la.metric("Rwox Cash (latest entry)",        _inr(latest["rwox_cash"]))
        lb.metric("Elastohorse Cash (latest entry)", _inr(latest["elastohorse_cash"]))

        if latest["expenses_json"]:
            exps = json.loads(latest["expenses_json"])
            if exps:
                st.markdown(f"**Expenses logged for {latest['month']}:**")
                for ex in exps:
                    st.markdown(f"- {ex['label']}: {_inr(ex['amount'])}")

        if latest["big_payments_json"]:
            pays = json.loads(latest["big_payments_json"])
            if pays:
                st.markdown(f"**Payments due for {latest['month']}:**")
                for p in pays:
                    st.markdown(f"- {p['label']}: {_inr(p['amount'])}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5 — UPLOAD DOCUMENTS
# ─────────────────────────────────────────────────────────────────────────────
def _tab_upload(conn) -> None:
    st.subheader("Upload Financial Statements")
    st.caption("Upload a P&L or Balance Sheet exported from Tally. Numbers are extracted automatically where possible — review them before saving.")

    uploaded = st.file_uploader(
        "Drop your file here — PDF or Excel",
        type=["pdf", "xlsx", "xls"],
    )

    extracted: dict = {}

    if uploaded:
        ext = uploaded.name.rsplit(".", 1)[-1].lower()

        if ext == "pdf":
            try:
                import pdfplumber
                import io
                import re
                raw_bytes = uploaded.read()
                with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
                    full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)

                if full_text.strip():
                    with st.expander("Raw text pulled from the PDF (first 2 000 chars)"):
                        st.text(full_text[:2000])

                    lines = full_text.splitlines()

                    def _find(keyword: str) -> float:
                        for line in lines:
                            if keyword.lower() in line.lower():
                                nums = re.findall(r"[\d,]+\.?\d*", line)
                                if nums:
                                    try:
                                        return float(nums[-1].replace(",", ""))
                                    except ValueError:
                                        pass
                        return 0.0

                    extracted["cash_bank"]   = _find("Cash") or _find("Bank")
                    extracted["receivables"] = _find("Debtors") or _find("Receivables")
                    extracted["payables"]    = _find("Creditors") or _find("Payables")
                    extracted["equity"]      = _find("Capital") or _find("Net Worth")
                    st.success("Text extracted — review and adjust the numbers below before saving.")
                else:
                    st.warning("No text found in PDF. Fill the form below manually.")

            except ImportError:
                st.warning(
                    "pdfplumber is not installed — auto-extraction unavailable. "
                    "Run `pip install pdfplumber` to enable it. Fill the form below manually."
                )
            except Exception as exc:
                st.error(f"Could not read PDF: {exc}")

        elif ext in ("xlsx", "xls"):
            try:
                import pandas as pd
                import io
                df = pd.read_excel(io.BytesIO(uploaded.read()), header=None)
                with st.expander("Excel preview (first 20 rows)"):
                    st.dataframe(df.head(20), use_container_width=True)
                st.info("Excel loaded — fill the key numbers below and save.")
            except ImportError:
                st.warning("openpyxl is not installed. Run `pip install openpyxl` to read Excel files.")
            except Exception as exc:
                st.error(f"Could not read Excel: {exc}")

        st.divider()
        st.markdown("**Confirm the key numbers before saving:**")

        with st.form("confirm_upload_form"):
            co_choice = st.selectbox("Which company is this for?", ["Rwox", "Elastohorse"])
            snap_date = st.date_input("Statement date", value=date.today())

            nc1, nc2 = st.columns(2)
            with nc1:
                cash_in = st.number_input("Cash in bank (₹)",              min_value=0.0, value=float(extracted.get("cash_bank", 0)),   step=1_000.0, format="%.0f")
                recv    = st.number_input("Customers owe us (₹)",           min_value=0.0, value=float(extracted.get("receivables", 0)), step=1_000.0, format="%.0f")
            with nc2:
                pay     = st.number_input("We owe vendors (₹)",             min_value=0.0, value=float(extracted.get("payables", 0)),    step=1_000.0, format="%.0f")
                eq      = st.number_input("Net worth / equity (₹)",         min_value=0.0, value=float(extracted.get("equity", 0)),      step=1_000.0, format="%.0f")
            doc_notes = st.text_area("Notes", value=f"Uploaded: {uploaded.name}")
            save_btn  = st.form_submit_button("Save to Database", type="primary")

        if save_btn:
            row = conn.execute("SELECT id FROM companies WHERE name=?", (co_choice,)).fetchone()
            if row:
                conn.execute(
                    "INSERT INTO financial_snapshots "
                    "(company_id, snapshot_date, cash_balance, receivables, payables, equity, notes) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (row["id"], snap_date.isoformat(), cash_in, recv, pay, eq, doc_notes),
                )
                conn.commit()
                st.success(f"Snapshot saved for {co_choice} as of {snap_date}.")

    snaps = conn.execute(
        "SELECT fs.*, c.name AS company FROM financial_snapshots fs "
        "JOIN companies c ON fs.company_id=c.id ORDER BY fs.snapshot_date DESC LIMIT 10"
    ).fetchall()

    if snaps:
        st.divider()
        st.markdown("#### Previously Saved Snapshots")
        for s in snaps:
            note_html = (
                f"<br><span style='color:#666;font-size:12px'>{s['notes']}</span>"
                if s["notes"] else ""
            )
            st.markdown(
                f"<div style='background:#1a1a1a;border-radius:8px;padding:12px 16px;"
                f"margin-bottom:8px;border:1px solid #333'>"
                f"<b style='color:{_BLUE}'>{s['company']}</b> &nbsp;·&nbsp; {s['snapshot_date']} &nbsp;·&nbsp; "
                f"Cash: {_inr(s['cash_balance'] or 0)} &nbsp;·&nbsp; "
                f"Receivables: {_inr(s['receivables'] or 0)} &nbsp;·&nbsp; "
                f"Payables: {_inr(s['payables'] or 0)}"
                f"{note_html}</div>",
                unsafe_allow_html=True,
            )


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6 — AI ANALYSIS (Groq)
# ─────────────────────────────────────────────────────────────────────────────
_GROQ_MODEL = "llama-3.3-70b-versatile"

_SYSTEM_PROMPT = (
    "You are a trusted friend who also happens to be a sharp business advisor. "
    "You know this small Indian manufacturing and trading business well. "
    "Speak plainly and honestly — like texting a friend, not writing a report. "
    "Zero finance jargon. Use ₹ for money amounts. Be specific, not vague."
)


def _build_context() -> str:
    r = FY25["Rwox"]
    e = FY25["Elastohorse"]
    r_nm = r["net_profit"] / r["sales"] * 100
    e_nm = e["net_profit"] / e["sales"] * 100
    r_sm = r["stock"] / (r["sales"] / 12)
    e_sm = e["stock"] / (e["sales"] / 12)
    return (
        f"Business: Reclaimr — two companies in India\n\n"
        f"Rwox (manufactures rubber reclaiming products):\n"
        f"  Annual sales:  ₹{r['sales']:,.0f}\n"
        f"  Net profit:    ₹{r['net_profit']:,.0f}  ({r_nm:.1f}% margin)\n"
        f"  Cash in bank:  ₹{r['cash_bank']:,.0f}\n"
        f"  Unsold stock:  ₹{r['stock']:,.0f}  ({r_sm:.1f} months of stock)\n"
        f"  Biggest cost:  Raw materials ₹{10_601_525:,.0f} (69% of revenue)\n\n"
        f"Elastohorse (trades rubber and related goods):\n"
        f"  Annual sales:  ₹{e['sales']:,.0f}\n"
        f"  Net profit:    ₹{e['net_profit']:,.0f}  ({e_nm:.1f}% margin)\n"
        f"  Cash in bank:  ₹{e['cash_bank']:,.0f}\n"
        f"  Customers owe: ₹{e['debtors']:,.0f}\n"
        f"  Unsold stock:  ₹{e['stock']:,.0f}  ({e_sm:.1f} months)\n"
        f"  Loan interest: ₹{313_895:,.0f}/year (implies significant borrowing)\n"
    )


def _groq_call(user_prompt: str) -> str:
    try:
        from groq import Groq
    except ImportError:
        return "ERROR:groq_not_installed"

    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        return "ERROR:no_key"

    client = Groq(api_key=key)
    resp = client.chat.completions.create(
        model=_GROQ_MODEL,
        max_tokens=400,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt},
        ],
    )
    return resp.choices[0].message.content


def _advice_box(label: str, text: str) -> None:
    st.markdown(
        f"<div style='background:#0d2137;border-radius:12px;padding:22px 24px;"
        f"border:1px solid #1a4a7a;margin-top:10px'>"
        f"<h4 style='color:{_BLUE};margin:0 0 12px 0'>{label}</h4>"
        f"<p style='color:#ddd;line-height:1.85;font-size:15px;margin:0'>"
        f"{text.replace(chr(10)+chr(10), '</p><p style=&quot;color:#ddd;line-height:1.85;font-size:15px;margin:8px 0 0 0&quot;>').replace(chr(10), '<br>')}"
        f"</p></div>",
        unsafe_allow_html=True,
    )


def _tab_ai() -> None:
    st.subheader("AI Business Advisor")
    st.caption("A structured assessment of both businesses based on your current data, with one prioritised action for the week.")

    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        st.error(
            "GROQ_API_KEY not found in your .env file. "
            "Add it as:  GROQ_API_KEY=your_key_here  and restart the app."
        )
        return

    # ── Main analysis button ─────────────────────────────────────────────────
    if st.button("Analyse My Business 🤖", type="primary", use_container_width=True):
        context = _build_context()
        prompt = (
            f"Based on the financial data below, write exactly 3 short paragraphs "
            f"(do NOT use headers or bullet points — just plain paragraphs):\n"
            f"Paragraph 1: What is going well ✅ (2-3 sentences)\n"
            f"Paragraph 2: What needs attention ⚠️ (2-3 sentences)\n"
            f"Paragraph 3: One specific action to take this week 🎯 (1-2 sentences)\n\n"
            f"Total under 130 words. Start each paragraph directly with the emoji.\n\n"
            f"{context}"
        )

        with st.spinner("Analysing your numbers..."):
            result = _groq_call(prompt)

        if result == "ERROR:groq_not_installed":
            st.error("groq package is not installed. Run: pip install groq")
        elif result == "ERROR:no_key":
            st.error("GROQ_API_KEY not found. Check your .env file.")
        else:
            st.session_state["fin_analysis"] = result

    if "fin_analysis" in st.session_state:
        _advice_box("🤖 Your Business Advisor Says:", st.session_state["fin_analysis"])

    # ── Custom question ──────────────────────────────────────────────────────
    st.divider()
    st.markdown("#### Ask a Specific Question")
    st.caption("Any question about the business — get a direct, data-informed answer in seconds.")

    question = st.text_input(
        "Your question",
        placeholder="e.g. Should I hire another worker for Rwox right now?",
        label_visibility="collapsed",
    )
    ask_btn = st.button("Ask 🤖", disabled=not question.strip())

    if ask_btn and question.strip():
        context = _build_context()
        prompt = (
            f"Here is the financial context for the business:\n{context}\n\n"
            f"The owner asks: {question.strip()}\n\n"
            f"Give a direct, honest answer in 2-4 sentences. "
            f"Speak plainly. Say yes or no clearly if the question needs it. "
            f"Use ₹ for money. Under 80 words."
        )
        with st.spinner("Thinking..."):
            result = _groq_call(prompt)

        if result.startswith("ERROR:"):
            st.error("Could not get a response. Check your GROQ_API_KEY in .env.")
        else:
            _advice_box(f"🤖 On '{question.strip()}':", result)


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
def render_financials_page(conn) -> None:
    _ensure_tables(conn)

    st.header("Financial Pulse")
    st.caption("Your live financial dashboard for both companies — margins, cash position, and business health without waiting for year-end statements.")

    tabs = st.tabs([
        "📊 Annual Overview",
        "💸 Expense Breakdown",
        "🚦 Health Check",
        "📝 Update This Month",
        "📄 Upload Statements",
        "🤖 AI Advisor",
    ])

    with tabs[0]: _tab_snapshot()
    with tabs[1]: _tab_expenses()
    with tabs[2]: _tab_health()
    with tabs[3]: _tab_monthly(conn)
    with tabs[4]: _tab_upload(conn)
    with tabs[5]: _tab_ai()
