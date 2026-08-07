import streamlit as st
import plotly.graph_objects as go
from datetime import date
import json
import os
import re
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
# STYLE
# ─────────────────────────────────────────────────────────────────────────────
_GREEN  = "#1B7F4F"
_YELLOW = "#D97706"
_RED    = "#C0392B"
_BLUE   = "#C17F3E"
_PURPLE = "#8B6A45"

_PIE_COLORS = ["#C17F3E","#1B7F4F","#D97706","#8B6A45","#C0392B","#2C2218","#C17F3E","#8B6A45"]
_PLOT = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
             font_color="#2C2218", margin=dict(t=45, b=30, l=10, r=10))

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
    "div[data-baseweb='tab-highlight']{background:#C17F3E!important}"
    "button[data-baseweb='tab'][aria-selected='true']{color:#C17F3E!important}"
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

# ─────────────────────────────────────────────────────────────────────────────
# ACCOUNTING GLOSSARY — used for hover tooltips on uploaded statements
# ─────────────────────────────────────────────────────────────────────────────
_TIPS = {
    "Sales": "Total money received from customers for goods or services sold this period.",
    "Revenue": "Total money received from customers, same as Sales.",
    "Turnover": "Total money received from customers, same as Sales or Revenue.",
    "Gross Profit": "Sales minus the direct cost of goods sold. Overhead costs like salaries and rent have NOT been deducted yet, this is a mid-point figure.",
    "Gross Loss": "When the direct cost of goods exceeds revenue, the business lost money even before paying overheads.",
    "Net Profit": "What is actually left after ALL costs are paid. This is the real money the business made.",
    "Net Loss": "When total expenses exceed total revenue, the business made an overall loss for the period.",
    "Cost of Goods Sold": "The direct cost to produce or buy the items sold: raw materials, direct labour.",
    "COGS": "Short for Cost of Goods Sold, the direct cost to make or buy items sold.",
    "Opening Stock": "Value of unsold goods at the start of this period, carried over from the previous one.",
    "Closing Stock": "Value of unsold goods remaining at the end of this period, subtracted to avoid double-counting.",
    "Purchases": "Goods or raw materials bought during the period to sell or use in production.",
    "Direct Expenses": "Costs directly tied to making your product: factory wages, power, inward freight.",
    "Indirect Expenses": "Overhead costs not tied to production: admin salaries, rent, marketing, interest.",
    "Depreciation": "The annual wear-and-tear cost of equipment and vehicles spread over their useful life. No cash leaves the business, but it reduces profit.",
    "Interest on Loans": "The cost of borrowing money, paid to banks or lenders on outstanding loans.",
    "Interest": "The cost of borrowing money, paid to banks or lenders on outstanding loans.",
    "Current Assets": "Things owned that can be turned into cash within 12 months: stock, debtors, cash at bank.",
    "Fixed Assets": "Long-term things owned that last more than a year: machinery, vehicles, buildings.",
    "Total Assets": "Everything the business owns, current assets plus fixed assets combined.",
    "Current Liabilities": "Amounts owed that must be paid within 12 months: creditors, short-term loans.",
    "Long Term Liabilities": "Loans or debts that do not need to be repaid within the next 12 months.",
    "Capital": "Money the owner(s) originally put into the business.",
    "Equity": "The owner's stake in the business, what would be left if all debts were paid and assets sold.",
    "Net Worth": "Same as Equity, the owner's share of the business after all liabilities are settled.",
    "Retained Earnings": "Profits from previous years kept inside the business rather than withdrawn by the owner.",
    "Reserves": "Profits set aside for a specific future purpose, acts as a buffer fund.",
    "Debtors": "Customers who owe you money for goods already delivered but not yet paid for.",
    "Sundry Debtors": "Several customers collectively owing you money. 'Sundry' means miscellaneous/various.",
    "Receivables": "Same as Debtors, money owed to you by customers.",
    "Creditors": "Suppliers or vendors you owe money to for goods already received.",
    "Sundry Creditors": "Several suppliers you collectively owe money to. 'Sundry' means miscellaneous/various.",
    "Payables": "Same as Creditors, money you owe to suppliers.",
    "Stock": "Goods sitting in your warehouse that have not been sold yet.",
    "Inventory": "Same as Stock, unsold goods in your warehouse.",
    "Cash in Hand": "Physical cash held at the office or premises (not in a bank account).",
    "Cash at Bank": "Money sitting in your bank account right now.",
    "Bank Balance": "The current amount of money in your bank account.",
    "Loans": "Money borrowed from a bank or financial institution, to be repaid with interest.",
    "Bank Overdraft": "When your bank account goes into negative, the bank is effectively lending you money short-term.",
    "Working Capital": "Current Assets minus Current Liabilities, cash available for day-to-day operations.",
    "Trading Account": "Shows Gross Profit, Revenue minus cost of goods sold, before overhead expenses are deducted.",
    "Profit & Loss Account": "A summary of all income and expenses over a period, showing whether the business made or lost money.",
    "Balance Sheet": "A snapshot of everything the business owns (assets) and owes (liabilities) on a specific date.",
    "Accumulated Depreciation": "Total depreciation charged on an asset from the day it was bought to today.",
    "Loan from Directors": "Money lent to the company by its own directors, a common form of internal borrowing.",
    "Outstanding Expenses": "Expenses incurred but not yet paid, they are owed and appear as a liability.",
    "Prepaid Expenses": "Expenses paid in advance for a future period, shown as an asset since the benefit is yet to be received.",
    "Advance": "Money paid or received before goods/services are delivered.",
}

_TOOLTIP_CSS = """<style>
.fintip{position:relative;display:inline-block;border-bottom:1px dotted #C17F3E;cursor:help}
.fintip .fintip-t{
    visibility:hidden;background:#FFF8F0;color:#2C2218;text-align:left;
    border-radius:6px;padding:8px 12px;position:absolute;z-index:9999;
    bottom:130%;left:0;min-width:240px;max-width:300px;font-size:12px;line-height:1.6;
    border:1px solid #E8D5B7;box-shadow:0 4px 16px rgba(0,0,0,.12);pointer-events:none;
    white-space:normal;
}
.fintip:hover .fintip-t{visibility:visible}
</style>"""


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def _inr(val: float) -> str:
    if val >= 1_00_00_000: return f"₹{val/1_00_00_000:.2f} Cr"
    if val >= 1_00_000:    return f"₹{val/1_00_000:.2f} L"
    if val >= 1_000:       return f"₹{val/1_000:.1f} K"
    return f"₹{val:,.0f}"

def _mc(pct): return _GREEN if pct >= 5 else (_YELLOW if pct >= 2 else _RED)
def _me(pct): return "✅" if pct >= 5 else ("⚠️" if pct >= 2 else "🔴")


def _tip(label: str) -> str:
    """Wrap label with CSS tooltip if found in glossary."""
    tip = _TIPS.get(label, "")
    if not tip:
        for key, val in _TIPS.items():
            if key.lower() in label.lower():
                tip = val
                break
    if tip:
        return f"<span class='fintip'>{label}<span class='fintip-t'>{tip}</span></span>"
    return label


def _render_stmt_card(title: str, rows: list, accent: str = _BLUE) -> None:
    """
    rows: list of (label, amount, indent_level, is_section_header, is_total)
    indent_level: 0=normal 1=indented  is_section_header: show as label only, no amount
    """
    rows_html = ""
    for label, amount, indent, is_hdr, is_tot in rows:
        pl = 12 + indent * 20
        if is_hdr:
            rows_html += (
                f"<tr><td colspan='2' style='padding:10px {pl}px 4px;color:{accent};"
                f"font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:0.6px;"
                f"border-top:1px solid #E8D5B7'>{label}</td></tr>"
            )
        elif is_tot:
            rows_html += (
                f"<tr style='background:#FFF0DC'>"
                f"<td style='padding:10px {pl}px;color:#2C2218;font-weight:700'>{_tip(label)}</td>"
                f"<td style='padding:10px 12px;text-align:right;color:{_GREEN};"
                f"font-weight:700;font-size:15px'>{_inr(amount)}</td></tr>"
            )
        else:
            rows_html += (
                f"<tr style='border-bottom:1px solid #E8D5B7'>"
                f"<td style='padding:7px {pl}px;color:#2C2218'>{_tip(label)}</td>"
                f"<td style='padding:7px 12px;text-align:right;color:#8B6A45'>{_inr(amount)}</td></tr>"
            )
    st.markdown(
        f"<div style='background:#FDFAF6;border-radius:10px;overflow:hidden;"
        f"border:1px solid #E8D5B7;margin-bottom:16px'>"
        f"<div style='padding:11px 16px;background:#FFF0DC;border-bottom:1px solid #E8D5B7'>"
        f"<span style='color:{accent};font-weight:600;font-size:14px'>{title}</span></div>"
        f"<table style='width:100%;border-collapse:collapse;font-size:14px'>"
        f"<tbody>{rows_html}</tbody></table></div>",
        unsafe_allow_html=True,
    )


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
# STATEMENT PARSING HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def _detect_stmt_type(text: str) -> str:
    tl = text.lower()
    if any(k in tl for k in ["profit & loss", "profit and loss", "trading account", "p&l"]):
        return "pl"
    if "balance sheet" in tl:
        return "bs"
    return "unknown"


def _extract_line_items(text: str) -> list:
    items = []
    num_re = re.compile(r'([\d,]+(?:\.\d+)?)\s*(?:Dr|Cr)?\s*$', re.IGNORECASE)
    for line in text.splitlines():
        line = line.strip()
        if not line or len(line) < 4:
            continue
        match = num_re.search(line)
        if match:
            try:
                amount = float(match.group(1).replace(",", ""))
                if amount < 1:
                    continue
                label = line[:match.start()].strip().rstrip(":.").strip()
                if label and len(label) > 2 and not label.replace(" ","").replace("-","").isdigit():
                    items.append((label, amount))
            except ValueError:
                pass
    return items


def _group_pl(items):
    income_kw  = ["sales","revenue","income","turnover","closing stock"]
    expense_kw = ["purchase","opening stock","wages","salary","salaries","transport",
                  "electricity","diesel","fuel","depreciation","interest","rent",
                  "printing","telephone","repairs","direct","indirect","expenses","cost"]
    total_kw   = ["gross profit","net profit","gross loss","net loss"]
    income, expenses, totals, other = [], [], [], []
    for label, amount in items:
        ll = label.lower()
        if any(k in ll for k in total_kw):
            totals.append((label, amount))
        elif any(k in ll for k in income_kw):
            income.append((label, amount))
        elif any(k in ll for k in expense_kw):
            expenses.append((label, amount))
        else:
            other.append((label, amount))
    return income, expenses, totals, other


def _group_bs(items):
    asset_kw = ["machinery","vehicle","building","furniture","computer","fixed asset",
                "plant","equipment","debtors","receivable","stock","inventory",
                "cash","bank","deposit","prepaid","advance to"]
    liab_kw  = ["capital","equity","net worth","reserve","loan from","borrowing",
                "creditor","payable","overdraft","outstanding","advance from"]
    total_kw = ["total","balance sheet total"]
    assets, liabilities, totals, other = [], [], [], []
    for label, amount in items:
        ll = label.lower()
        if any(k in ll for k in total_kw):
            totals.append((label, amount))
        elif any(k in ll for k in asset_kw):
            assets.append((label, amount))
        elif any(k in ll for k in liab_kw):
            liabilities.append((label, amount))
        else:
            other.append((label, amount))
    return assets, liabilities, totals, other


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1 — ANNUAL OVERVIEW
# ─────────────────────────────────────────────────────────────────────────────
def _tab_snapshot(company: str) -> None:
    st.subheader("FY 2024-25 at a Glance")
    st.caption("Full-year results. Use this to benchmark monthly performance and understand where margins stand.")

    companies = ["Rwox", "Elastohorse"] if company == "both" else [company]
    cols = st.columns(len(companies))

    for col, co in zip(cols, companies):
        d  = FY25[co]
        nm = d["net_profit"] / d["sales"] * 100
        debtor_html = (
            f"<p style='color:{_RED};margin:6px 0'>⚠️ Customers owe us "
            f"<b>{_inr(d['debtors'])}</b>, check if any is overdue</p>"
            if d["debtors"] > 0
            else f"<p style='color:{_GREEN};margin:6px 0'>✅ No money owed by customers</p>"
        )
        with col:
            st.markdown(
                f"<div style='background:#FFF8F0;border-radius:12px;padding:22px 24px;"
                f"border:1px solid #E8D5B7;margin-bottom:12px'>"
                f"<h3 style='color:#2C2218;margin:0 0 14px 0'>{co}</h3>"
                f"<p style='color:#2C2218;font-size:18px;font-weight:700;margin:4px 0'>"
                f"💰 We made {_inr(d['sales'])} in sales this year</p>"
                f"<p style='color:{_mc(nm)};margin:6px 0'>{_me(nm)} After all costs, we kept "
                f"<b>{_inr(d['net_profit'])}</b> ({nm:.1f}%)</p>"
                f"<p style='color:#2C2218;margin:6px 0'>🏦 Cash in bank right now: "
                f"<b>{_inr(d['cash_bank'])}</b></p>"
                f"{debtor_html}"
                f"<p style='color:#8B6A45;margin:6px 0'>📦 Unsold stock in warehouse: "
                f"{_inr(d['stock'])}</p>"
                f"</div>",
                unsafe_allow_html=True,
            )

    if company == "both":
        t_s = FY25["Rwox"]["sales"]      + FY25["Elastohorse"]["sales"]
        t_p = FY25["Rwox"]["net_profit"] + FY25["Elastohorse"]["net_profit"]
        t_c = FY25["Rwox"]["cash_bank"]  + FY25["Elastohorse"]["cash_bank"]
        cnm = t_p / t_s * 100
        st.markdown(
            f"<div style='background:#FFF0DC;border-radius:12px;padding:22px 24px;"
            f"border:1px solid #E8D5B7;margin-bottom:16px'>"
            f"<h3 style='color:{_BLUE};margin:0 0 14px 0'>🌐 Both Businesses Together</h3>"
            f"<div style='display:grid;grid-template-columns:1fr 1fr 1fr;gap:20px'>"
            f"<div><p style='color:#8B6A45;font-size:12px;margin:0'>COMBINED SALES</p>"
            f"<p style='color:#2C2218;font-size:24px;font-weight:700;margin:4px 0'>{_inr(t_s)}</p></div>"
            f"<div><p style='color:#8B6A45;font-size:12px;margin:0'>COMBINED PROFIT</p>"
            f"<p style='color:{_mc(cnm)};font-size:24px;font-weight:700;margin:4px 0'>{_inr(t_p)}</p>"
            f"<p style='color:#8B6A45;font-size:12px;margin:0'>{cnm:.1f}% of total sales</p></div>"
            f"<div><p style='color:#8B6A45;font-size:12px;margin:0'>CASH IN BANK</p>"
            f"<p style='color:#2C2218;font-size:24px;font-weight:700;margin:4px 0'>{_inr(t_c)}</p></div>"
            f"</div></div>",
            unsafe_allow_html=True,
        )

    st.divider()
    metric_cos = ["Rwox", "Elastohorse"] if company == "both" else [company]
    mcols = st.columns(len(metric_cos) * 2)
    for i, co in enumerate(metric_cos):
        d  = FY25[co]
        nm = d["net_profit"] / d["sales"] * 100
        gm = d["gross_profit"] / d["sales"] * 100
        mcols[i*2].metric(f"{co} Net Margin",   f"{nm:.1f}%",
                          help="% of sales kept as profit after ALL expenses")
        mcols[i*2+1].metric(f"{co} Gross Margin", f"{gm:.1f}%",
                            help="% kept after cost of goods sold only (before overheads)")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2 — EXPENSE BREAKDOWN
# ─────────────────────────────────────────────────────────────────────────────
def _tab_expenses(company: str, kp: str) -> None:
    st.subheader("Expense Breakdown")
    st.caption("Where every rupee of revenue is going. Any category above 40% is flagged.")

    companies = ["Rwox", "Elastohorse"] if company == "both" else [company]
    cols = st.columns(len(companies))

    for col, co in zip(cols, companies):
        sales    = FY25[co]["sales"]
        exp_list = EXPENSES[co]
        with col:
            st.markdown(f"#### {co}")
            fig = go.Figure(go.Pie(
                labels=[e[0] for e in exp_list], values=[e[1] for e in exp_list],
                marker_colors=_PIE_COLORS,
                hovertemplate="<b>%{label}</b><br>₹%{value:,.0f}<br>%{percent}<extra></extra>",
                hole=0.4,
            ))
            fig.update_layout(height=340, legend=dict(orientation="h", y=-0.4), **_PLOT)
            st.plotly_chart(fig, use_container_width=True, key=f"{kp}_{co}_exp_pie")

            for label, amount in exp_list:
                per_100 = amount / sales * 100
                clr, flag = (_RED,"🔴") if per_100>40 else (_YELLOW,"⚠️") if per_100>20 else ("#8B6A45","   ")
                st.markdown(
                    f"<div style='display:flex;justify-content:space-between;align-items:center;"
                    f"padding:5px 0;border-bottom:1px solid #E8D5B7'>"
                    f"<span style='color:#2C2218'>{flag} {label}</span>"
                    f"<span><b style='color:{clr}'>₹{per_100:.1f}</b>"
                    f"<span style='color:#2C2218'> per ₹100 earned</span> &nbsp;"
                    f"<span style='color:#8B6A45;font-size:12px'>({_inr(amount)})</span></span>"
                    f"</div>", unsafe_allow_html=True)
                if per_100 > 40:
                    st.markdown(
                        f"<p style='color:{_RED};font-size:12px;margin:2px 0 4px 20px'>"
                        f"This single expense is more than 40% of revenue, worth watching closely.</p>",
                        unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3 — HEALTH CHECK
# ─────────────────────────────────────────────────────────────────────────────
def _hrow_both(emoji, title, r_txt, r_clr, e_txt, e_clr, action=None):
    st.markdown(f"#### {emoji} {title}")
    c1, c2 = st.columns(2)
    for col, name, txt, clr in [(c1,"Rwox",r_txt,r_clr),(c2,"Elastohorse",e_txt,e_clr)]:
        with col:
            st.markdown(
                f"<div style='background:#FFF8F0;border-radius:8px;padding:14px;"
                f"border-left:4px solid {clr};margin-bottom:8px'>"
                f"<b style='color:{clr}'>{name}</b><br>"
                f"<span style='color:#2C2218;font-size:14px'>{txt}</span></div>",
                unsafe_allow_html=True)
    if action:
        st.markdown(f"<p style='color:{_YELLOW};font-size:13px;margin:0 0 6px 0'>💡 Action: {action}</p>",
                    unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)


def _hrow_single(emoji, title, txt, clr, action=None):
    st.markdown(f"#### {emoji} {title}")
    st.markdown(
        f"<div style='background:#FFF8F0;border-radius:8px;padding:14px;"
        f"border-left:4px solid {clr};margin-bottom:8px'>"
        f"<span style='color:#2C2218;font-size:14px'>{txt}</span></div>",
        unsafe_allow_html=True)
    if action:
        st.markdown(f"<p style='color:{_YELLOW};font-size:13px;margin:0 0 6px 0'>💡 Action: {action}</p>",
                    unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)


def _tab_health(company: str) -> None:
    st.subheader("Health Check")
    st.caption("Five indicators showing whether the business is within healthy parameters.")

    r = FY25["Rwox"];  e = FY25["Elastohorse"]
    r_nm = r["net_profit"] / r["sales"] * 100
    e_nm = e["net_profit"] / e["sales"] * 100
    r_me = (r["sales"] - r["net_profit"]) / 12
    e_me = (e["sales"] - e["net_profit"]) / 12
    r_sm = r["stock"] / (r["sales"] / 12)
    e_sm = e["stock"] / (e["sales"] / 12)
    r_ok = r["cash_bank"] >= r_me
    e_ok = e["cash_bank"] >= e_me
    r_sw = r_sm > 2;  e_sw = e_sm > 2
    e_loan = 313_895 / 0.15
    e_lp   = e_loan / e["total_assets"] * 100
    loan_bad = e_lp > 50

    if company == "both":
        _hrow_both(_me(min(r_nm,e_nm)), "Are we making enough profit?",
            f"Keeping {r_nm:.1f}% of every sale as profit", _mc(r_nm),
            f"Keeping {e_nm:.1f}% of every sale as profit", _mc(e_nm),
            "Rwox is below 5%, review expenses line by line and find what can be cut." if r_nm < 5 else None)

        _hrow_both("✅" if (r_ok and e_ok) else "🔴", "Can we pay our bills next month?",
            f"Monthly costs ≈ {_inr(r_me)}, cash = {_inr(r['cash_bank'])}, {'OK ✅' if r_ok else 'Tight 🔴'}",
            _GREEN if r_ok else _RED,
            f"Monthly costs ≈ {_inr(e_me)}, cash = {_inr(e['cash_bank'])}, {'OK ✅' if e_ok else 'Tight 🔴'}",
            _GREEN if e_ok else _RED,
            "Chase outstanding payments. Hold off on big purchases until cash improves." if not (r_ok and e_ok) else None)

        _hrow_both("⚠️" if e["debtors"]>0 else "✅", "Are customers paying on time?",
            "No outstanding customer payments, all clear", _GREEN,
            f"Customers owe {_inr(e['debtors'])}, check if any invoice is older than 45 days",
            _YELLOW if e["debtors"]>0 else _GREEN,
            "Call the top 3 customers by amount owed. Ask for payment this week." if e["debtors"]>0 else None)

        _hrow_both("⚠️" if (r_sw or e_sw) else "✅", "Are we sitting on too much unsold stock?",
            f"{r_sm:.1f} months of stock ({_inr(r['stock'])})", _YELLOW if r_sw else _GREEN,
            f"{e_sm:.1f} months of stock ({_inr(e['stock'])})", _YELLOW if e_sw else _GREEN,
            "Push a sales drive on slow-moving items. Avoid restocking until levels come down." if (r_sw or e_sw) else None)

        _hrow_both("🔴" if loan_bad else "⚠️", "Are we too dependent on loans?",
            "No significant loan data available for Rwox", "#666",
            f"Estimated loans ≈ {_inr(e_loan)} ({e_lp:.0f}% of assets, from interest paid)",
            _RED if loan_bad else _YELLOW,
            "Prioritise paying down loans before taking new ones." if loan_bad else None)

    elif company == "Rwox":
        _hrow_single(_me(r_nm), "Are we making enough profit?",
            f"Keeping {r_nm:.1f}% of every sale as profit after all expenses", _mc(r_nm),
            "Go line by line through expenses and find what can be cut this month." if r_nm < 5 else None)
        _hrow_single("✅" if r_ok else "🔴", "Can we pay our bills next month?",
            f"Monthly costs ≈ {_inr(r_me)}, cash = {_inr(r['cash_bank'])}, {'enough to cover ✅' if r_ok else 'not enough 🔴'}",
            _GREEN if r_ok else _RED,
            "Chase outstanding payments right away. Hold off on big purchases." if not r_ok else None)
        _hrow_single("✅", "Are customers paying on time?",
            "No outstanding customer payments for Rwox, all clear", _GREEN, None)
        _hrow_single("⚠️" if r_sw else "✅", "Are we sitting on too much unsold stock?",
            f"{r_sm:.1f} months of stock sitting in the warehouse ({_inr(r['stock'])})",
            _YELLOW if r_sw else _GREEN,
            "Push a sales drive on slow-moving items. Avoid restocking until levels come down." if r_sw else None)

    else:  # Elastohorse
        _hrow_single(_me(e_nm), "Are we making enough profit?",
            f"Keeping {e_nm:.1f}% of every sale as profit after all expenses", _mc(e_nm), None)
        _hrow_single("✅" if e_ok else "🔴", "Can we pay our bills next month?",
            f"Monthly costs ≈ {_inr(e_me)}, cash = {_inr(e['cash_bank'])}, {'enough to cover ✅' if e_ok else 'not enough 🔴'}",
            _GREEN if e_ok else _RED,
            "Chase outstanding payments right away. Hold off on big purchases." if not e_ok else None)
        _hrow_single("⚠️" if e["debtors"]>0 else "✅", "Are customers paying on time?",
            f"Customers owe {_inr(e['debtors'])}, check if any invoice is older than 45 days"
            if e["debtors"]>0 else "All customer payments are up to date",
            _YELLOW if e["debtors"]>0 else _GREEN,
            "Call the top 3 customers by amount owed. Ask for payment this week." if e["debtors"]>0 else None)
        _hrow_single("⚠️" if e_sw else "✅", "Are we sitting on too much unsold stock?",
            f"{e_sm:.1f} months of stock sitting in the warehouse ({_inr(e['stock'])})",
            _YELLOW if e_sw else _GREEN,
            "Push a sales drive on slow-moving items. Avoid restocking until levels come down." if e_sw else None)
        _hrow_single("🔴" if loan_bad else "⚠️", "Are we too dependent on loans?",
            f"Estimated loans ≈ {_inr(e_loan)} ({e_lp:.0f}% of assets, estimated from interest paid)",
            _RED if loan_bad else _YELLOW,
            "Prioritise paying down loans before taking on new ones. High debt is risky if sales slow." if loan_bad else None)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4 — MONTHLY UPDATE
# ─────────────────────────────────────────────────────────────────────────────
def _tab_monthly(conn, company: str, kp: str) -> None:
    st.subheader("Monthly Update")
    st.caption("Keep your dashboard current. Three minutes at the start of each month is all it takes.")

    prev = conn.execute("SELECT * FROM monthly_updates ORDER BY month DESC LIMIT 1").fetchone()
    r_s0 = float(prev["rwox_sales"]        if prev else 0)
    r_c0 = float(prev["rwox_cash"]         if prev else 0)
    e_s0 = float(prev["elastohorse_sales"] if prev else 0)
    e_c0 = float(prev["elastohorse_cash"]  if prev else 0)

    r_sales = r_s0; r_cash = r_c0; e_sales = e_s0; e_cash = e_c0

    with st.form(f"{kp}_monthly_form"):
        st.markdown("**Enter current month figures:**")
        month_str = st.text_input("Month (YYYY-MM)", value=date.today().strftime("%Y-%m"),
                                  key=f"{kp}_mu_month")
        if company == "both":
            sa, sb = st.columns(2)
            with sa:
                r_sales = st.number_input("Rwox: Sales this month (₹)",
                    min_value=0.0, step=10_000.0, format="%.0f", key=f"{kp}_mu_rs")
                r_cash  = st.number_input("Rwox: Cash in bank today (₹)",
                    min_value=0.0, step=10_000.0, format="%.0f", key=f"{kp}_mu_rc")
            with sb:
                e_sales = st.number_input("Elastohorse: Sales this month (₹)",
                    min_value=0.0, step=10_000.0, format="%.0f", key=f"{kp}_mu_es")
                e_cash  = st.number_input("Elastohorse: Cash in bank today (₹)",
                    min_value=0.0, step=10_000.0, format="%.0f", key=f"{kp}_mu_ec")
        elif company == "Rwox":
            col, _ = st.columns([1, 1])
            with col:
                r_sales = st.number_input("Sales this month (₹)",
                    min_value=0.0, step=10_000.0, format="%.0f", key=f"{kp}_mu_rs")
                r_cash  = st.number_input("Cash in bank today (₹)",
                    min_value=0.0, step=10_000.0, format="%.0f", key=f"{kp}_mu_rc")
        else:
            col, _ = st.columns([1, 1])
            with col:
                e_sales = st.number_input("Sales this month (₹)",
                    min_value=0.0, step=10_000.0, format="%.0f", key=f"{kp}_mu_es")
                e_cash  = st.number_input("Cash in bank today (₹)",
                    min_value=0.0, step=10_000.0, format="%.0f", key=f"{kp}_mu_ec")

        st.markdown("**Main expenses this month**: one per line: Name, Amount")
        exp_text = st.text_area("E.g.  Raw materials, 500000", height=90,
                                label_visibility="collapsed", key=f"{kp}_mu_exp")
        st.markdown("**Payments due this month**: one per line: Name, Amount")
        pay_text = st.text_area("E.g.  Loan repayment, 200000", height=70,
                                label_visibility="collapsed", key=f"{kp}_mu_pay")
        notes    = st.text_area("Any notes?", height=60, key=f"{kp}_mu_notes")
        save_ok  = st.form_submit_button("Save Monthly Update", type="primary")

    if save_ok:
        import re as _re
        if not _re.fullmatch(r"\d{4}-\d{2}", month_str.strip()):
            st.error("Month must be in YYYY-MM format (e.g. 2026-05).")
            st.stop()
        if r_sales == 0 and e_sales == 0:
            st.warning("Both sales figures are zero, are you sure? Save anyway if correct.")

        def _parse(text):
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
               (month,rwox_sales,elastohorse_sales,rwox_cash,elastohorse_cash,
                expenses_json,big_payments_json,notes)
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
             notes.strip() or None))
        conn.commit()
        st.success("Monthly update saved!")
        st.rerun()

    rows = conn.execute(
        "SELECT month,rwox_sales,elastohorse_sales,rwox_cash,elastohorse_cash "
        "FROM monthly_updates ORDER BY month ASC LIMIT 6"
    ).fetchall()
    if not rows:
        st.info("No monthly updates yet, enter your first update above.")
        return

    st.divider()
    st.markdown("#### Last 6 Months: Revenue Trend")
    months = [r["month"] for r in rows]
    fig = go.Figure()
    if company in ("both", "Rwox"):
        fig.add_trace(go.Bar(x=months, y=[r["rwox_sales"] for r in rows],
            name="Rwox", marker_color=_BLUE,
            hovertemplate="<b>Rwox</b><br>%{x}<br>₹%{y:,.0f}<extra></extra>"))
    if company in ("both", "Elastohorse"):
        fig.add_trace(go.Bar(x=months, y=[r["elastohorse_sales"] for r in rows],
            name="Elastohorse", marker_color="#1B7F4F",
            hovertemplate="<b>Elastohorse</b><br>%{x}<br>₹%{y:,.0f}<extra></extra>"))
    fig.update_layout(title="Monthly Sales", height=320, barmode="group",
        xaxis=dict(gridcolor="#E8D5B7"), yaxis=dict(gridcolor="#E8D5B7", tickprefix="₹"),
        legend=dict(orientation="h", y=-0.3), **_PLOT)
    st.plotly_chart(fig, use_container_width=True, key=f"{kp}_monthly_chart")

    latest = conn.execute("SELECT * FROM monthly_updates ORDER BY month DESC LIMIT 1").fetchone()
    if latest:
        la, lb = st.columns(2)
        if company in ("both", "Rwox"):
            la.metric("Rwox Cash (latest)", _inr(latest["rwox_cash"]))
        if company in ("both", "Elastohorse"):
            lb.metric("Elastohorse Cash (latest)", _inr(latest["elastohorse_cash"]))
        if latest["expenses_json"]:
            exps = json.loads(latest["expenses_json"])
            if exps:
                st.markdown(f"**Expenses logged for {latest['month']}:**")
                for ex in exps: st.markdown(f"- {ex['label']}: {_inr(ex['amount'])}")
        if latest["big_payments_json"]:
            pays = json.loads(latest["big_payments_json"])
            if pays:
                st.markdown(f"**Payments due for {latest['month']}:**")
                for p in pays: st.markdown(f"- {p['label']}: {_inr(p['amount'])}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5 — UPLOAD DOCUMENTS
# ─────────────────────────────────────────────────────────────────────────────
def _tab_upload(conn, kp: str, default_company: str = "Rwox") -> None:
    st.subheader("Upload Financial Statements")
    st.caption(
        "Upload a P&L or Balance Sheet from Tally (PDF or Excel). "
        "Numbers are extracted and displayed as a clean statement, "
        "**hover over any underlined term** to see a plain-English explanation."
    )
    st.markdown(_TOOLTIP_CSS, unsafe_allow_html=True)

    uploaded = st.file_uploader(
        "Drop your file here (PDF or Excel)",
        type=["pdf", "xlsx", "xls"],
        key=f"{kp}_uploader",
    )

    extracted: dict = {}
    line_items: list = []
    stmt_type: str   = "unknown"

    if uploaded:
        ext = uploaded.name.rsplit(".", 1)[-1].lower()

        if ext == "pdf":
            try:
                import pdfplumber, io
                with pdfplumber.open(io.BytesIO(uploaded.read())) as pdf:
                    full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)
                if full_text.strip():
                    stmt_type  = _detect_stmt_type(full_text)
                    line_items = _extract_line_items(full_text)

                    def _fa(kws):
                        for lbl, amt in line_items:
                            if any(k.lower() in lbl.lower() for k in kws):
                                return amt
                        return 0.0

                    extracted["cash_bank"]   = _fa(["cash at bank","bank balance","cash in bank","cash"])
                    extracted["receivables"] = _fa(["debtors","receivable","sundry debtor"])
                    extracted["payables"]    = _fa(["creditors","payable","sundry creditor"])
                    extracted["equity"]      = _fa(["capital","net worth","equity"])

                    with st.expander("Raw text from PDF (first 1 500 chars)"):
                        st.text(full_text[:1500])
                else:
                    st.warning("No text found in this PDF, fill the numbers in manually below.")
            except ImportError:
                st.warning("pdfplumber not installed. Run `pip install pdfplumber` to enable auto-extraction.")
            except Exception as exc:
                st.error(f"Could not read PDF: {exc}")

        elif ext in ("xlsx", "xls"):
            try:
                import pandas as pd, io
                df = pd.read_excel(io.BytesIO(uploaded.read()), header=None)
                with st.expander("Excel preview (first 20 rows)"):
                    st.dataframe(df.head(20), use_container_width=True)
                for _, row in df.head(80).iterrows():
                    vals = [v for v in row if v is not None and str(v).strip()]
                    if len(vals) >= 2:
                        label = str(vals[0]).strip()
                        for v in reversed(vals[1:]):
                            try:
                                amt = float(str(v).replace(",",""))
                                if amt > 0 and label and len(label) > 2:
                                    line_items.append((label, amt))
                                break
                            except (ValueError, TypeError):
                                pass
                stmt_type = "unknown"
                st.info("Excel loaded, review the extracted data below.")
            except ImportError:
                st.warning("openpyxl not installed. Run `pip install openpyxl` to read Excel files.")
            except Exception as exc:
                st.error(f"Could not read Excel: {exc}")

        # ── Display extracted statement ───────────────────────────────────────
        if line_items:
            st.divider()
            stmt_label = {"pl":"📊 Profit & Loss Statement",
                          "bs":"📋 Balance Sheet",
                          "unknown":"📄 Extracted Statement"}[stmt_type]
            st.markdown(f"### {stmt_label}")
            st.caption("Hover over any underlined term for a plain-English explanation.")

            if stmt_type == "pl":
                income, expenses, totals, other = _group_pl(line_items)
                col, _ = st.columns([3, 1])
                with col:
                    all_rows = []
                    if income:
                        all_rows.append(("INCOME", 0, 0, True, False))
                        for l, a in income:   all_rows.append((l, a, 1, False, False))
                    if expenses:
                        all_rows.append(("EXPENSES", 0, 0, True, False))
                        for l, a in expenses: all_rows.append((l, a, 1, False, False))
                    if other:
                        all_rows.append(("OTHER ITEMS", 0, 0, True, False))
                        for l, a in other:    all_rows.append((l, a, 1, False, False))
                    for l, a in totals:       all_rows.append((l, a, 0, False, True))
                    _render_stmt_card(stmt_label, all_rows, _BLUE)

            elif stmt_type == "bs":
                assets, liabilities, totals, other = _group_bs(line_items)
                bs_a, bs_l = st.columns(2)
                with bs_a:
                    arows = []
                    if assets:
                        arows.append(("ASSETS", 0, 0, True, False))
                        for l, a in assets: arows.append((l, a, 1, False, False))
                    if other:
                        arows.append(("UNCLASSIFIED", 0, 0, True, False))
                        for l, a in other[:len(other)//2 + 1]: arows.append((l, a, 1, False, False))
                    _render_stmt_card("Assets", arows, _GREEN)
                with bs_l:
                    lrows = []
                    if liabilities:
                        lrows.append(("LIABILITIES & EQUITY", 0, 0, True, False))
                        for l, a in liabilities: lrows.append((l, a, 1, False, False))
                    if other and len(other) > 1:
                        for l, a in other[len(other)//2 + 1:]: lrows.append((l, a, 1, False, False))
                    for l, a in totals: lrows.append((l, a, 0, False, True))
                    _render_stmt_card("Liabilities & Equity", lrows, _PURPLE)

            else:
                all_rows = [("EXTRACTED LINE ITEMS", 0, 0, True, False)]
                for l, a in line_items[:60]: all_rows.append((l, a, 1, False, False))
                _render_stmt_card("Extracted Data", all_rows, _YELLOW)

        # ── Confirm & Save ────────────────────────────────────────────────────
        if uploaded:
            st.divider()
            st.markdown("**Confirm the key numbers and save to the database:**")
            co_opts   = ["Rwox", "Elastohorse"]
            co_idx    = co_opts.index(default_company) if default_company in co_opts else 0

            with st.form(f"{kp}_confirm_upload_form"):
                co_choice = st.selectbox("Which company is this for?", co_opts, index=co_idx,
                                         key=f"{kp}_up_co")
                snap_date = st.date_input("Statement date", value=date.today(), key=f"{kp}_up_date")
                nc1, nc2 = st.columns(2)
                with nc1:
                    cash_in = st.number_input("Cash in bank (₹)", min_value=0.0,
                        value=float(extracted.get("cash_bank", 0)),
                        step=1_000.0, format="%.0f", key=f"{kp}_up_cash")
                    recv    = st.number_input("Customers owe us: Debtors (₹)", min_value=0.0,
                        value=float(extracted.get("receivables", 0)),
                        step=1_000.0, format="%.0f", key=f"{kp}_up_recv")
                with nc2:
                    pay  = st.number_input("We owe vendors: Creditors (₹)", min_value=0.0,
                        value=float(extracted.get("payables", 0)),
                        step=1_000.0, format="%.0f", key=f"{kp}_up_pay")
                    eq   = st.number_input("Net worth / equity (₹)", min_value=0.0,
                        value=float(extracted.get("equity", 0)),
                        step=1_000.0, format="%.0f", key=f"{kp}_up_eq")
                doc_notes = st.text_area("Notes", value=f"Uploaded: {uploaded.name}",
                                         key=f"{kp}_up_notes")
                save_btn  = st.form_submit_button("Save to Database", type="primary")

            if save_btn:
                row = conn.execute("SELECT id FROM companies WHERE name=?", (co_choice,)).fetchone()
                if row:
                    conn.execute(
                        "INSERT INTO financial_snapshots "
                        "(company_id,snapshot_date,cash_balance,receivables,payables,equity,notes) "
                        "VALUES (?,?,?,?,?,?,?)",
                        (row["id"], snap_date.isoformat(), cash_in, recv, pay, eq, doc_notes))
                    conn.commit()
                    st.success(f"Snapshot saved for {co_choice} as of {snap_date}.")

    snaps = conn.execute(
        "SELECT fs.*,c.name AS company FROM financial_snapshots fs "
        "JOIN companies c ON fs.company_id=c.id ORDER BY fs.snapshot_date DESC LIMIT 10"
    ).fetchall()
    if snaps:
        st.divider()
        st.markdown("#### Previously Saved Snapshots")
        for s in snaps:
            note_html = (f"<br><span style='color:#666;font-size:12px'>{s['notes']}</span>"
                         if s["notes"] else "")
            st.markdown(
                f"<div style='background:#FFF8F0;border-radius:8px;padding:12px 16px;"
                f"margin-bottom:8px;border:1px solid #E8D5B7'>"
                f"<b style='color:{_BLUE}'>{s['company']}</b> &nbsp;·&nbsp; {s['snapshot_date']} "
                f"&nbsp;·&nbsp; Cash: {_inr(s['cash_balance'] or 0)} &nbsp;·&nbsp; "
                f"Debtors: {_inr(s['receivables'] or 0)} &nbsp;·&nbsp; "
                f"Creditors: {_inr(s['payables'] or 0)}{note_html}</div>",
                unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6 — AI ADVISOR (Groq)
# ─────────────────────────────────────────────────────────────────────────────
_GROQ_MODEL   = "openai/gpt-oss-120b"
_SYSTEM_PROMPT = (
    "You are a trusted friend who also happens to be a sharp business advisor. "
    "You know this small Indian manufacturing and trading business well. "
    "Speak plainly and honestly, like texting a friend, not writing a report. "
    "Zero finance jargon. Use ₹ for money amounts. Be specific, not vague."
)


def _build_context(company: str) -> str:
    parts = []
    if company in ("both", "Rwox"):
        r    = FY25["Rwox"]
        r_nm = r["net_profit"] / r["sales"] * 100
        r_sm = r["stock"]      / (r["sales"] / 12)
        parts.append(
            f"Rwox (manufactures rubber reclaiming products):\n"
            f"  Annual sales:  ₹{r['sales']:,.0f}\n"
            f"  Net profit:    ₹{r['net_profit']:,.0f}  ({r_nm:.1f}% margin)\n"
            f"  Cash in bank:  ₹{r['cash_bank']:,.0f}\n"
            f"  Unsold stock:  ₹{r['stock']:,.0f}  ({r_sm:.1f} months of stock)\n"
            f"  Biggest cost:  Raw materials ₹{10_601_525:,.0f} (69% of revenue)\n"
        )
    if company in ("both", "Elastohorse"):
        e    = FY25["Elastohorse"]
        e_nm = e["net_profit"] / e["sales"] * 100
        e_sm = e["stock"]      / (e["sales"] / 12)
        parts.append(
            f"Elastohorse (trades rubber and related goods):\n"
            f"  Annual sales:  ₹{e['sales']:,.0f}\n"
            f"  Net profit:    ₹{e['net_profit']:,.0f}  ({e_nm:.1f}% margin)\n"
            f"  Cash in bank:  ₹{e['cash_bank']:,.0f}\n"
            f"  Customers owe: ₹{e['debtors']:,.0f}\n"
            f"  Unsold stock:  ₹{e['stock']:,.0f}  ({e_sm:.1f} months)\n"
            f"  Loan interest: ₹{313_895:,.0f}/year (implies significant borrowing)\n"
        )
    return "Business: Reclaimr, Indian manufacturing and trading group\n\n" + "\n".join(parts)


def _groq_call(user_prompt: str) -> str:
    try:
        from groq import Groq
    except ImportError:
        return "ERROR:groq_not_installed"
    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        return "ERROR:no_key"
    client = Groq(api_key=key)
    resp   = client.chat.completions.create(
        model=_GROQ_MODEL, max_tokens=400, reasoning_effort="low",
        messages=[{"role":"system","content":_SYSTEM_PROMPT},
                  {"role":"user",  "content":user_prompt}])
    return resp.choices[0].message.content


def _advice_box(label: str, text: str) -> None:
    st.markdown(
        f"<div style='background:#FFF0DC;border-radius:12px;padding:22px 24px;"
        f"border:1px solid #E8D5B7;margin-top:10px'>"
        f"<h4 style='color:{_BLUE};margin:0 0 12px 0'>{label}</h4>"
        f"<p style='color:#2C2218;line-height:1.85;font-size:15px;margin:0'>"
        f"{text.replace(chr(10)+chr(10),'</p><p style=&quot;color:#2C2218;line-height:1.85;font-size:15px;margin:8px 0 0 0&quot;>').replace(chr(10),'<br>')}"
        f"</p></div>", unsafe_allow_html=True)


def _tab_ai(company: str, kp: str) -> None:
    co_label = company if company != "both" else "both companies"
    st.subheader("AI Business Advisor")
    st.caption(f"A structured assessment of {co_label} based on your data, with one prioritised action for the week.")

    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        st.error("GROQ_API_KEY not found in your .env file. Add it as: GROQ_API_KEY=your_key_here and restart.")
        return

    if st.button("Analyse My Business 🤖", type="primary", use_container_width=True, key=f"{kp}_ai_btn"):
        context = _build_context(company)
        prompt  = (
            f"Based on the financial data below, write exactly 3 short paragraphs "
            f"(no headers or bullets, plain paragraphs only):\n"
            f"Paragraph 1: What is going well ✅ (2-3 sentences)\n"
            f"Paragraph 2: What needs attention ⚠️ (2-3 sentences)\n"
            f"Paragraph 3: One specific action to take this week 🎯 (1-2 sentences)\n\n"
            f"Total under 130 words. Start each paragraph directly with the emoji.\n\n"
            f"{context}"
        )
        with st.spinner("Analysing your numbers..."):
            result = _groq_call(prompt)
        if result.startswith("ERROR:"):
            st.error("Could not get a response. Check your GROQ_API_KEY in .env.")
        else:
            st.session_state[f"{kp}_analysis"] = result

    if f"{kp}_analysis" in st.session_state:
        _advice_box("🤖 Your Business Advisor Says:", st.session_state[f"{kp}_analysis"])

    st.divider()
    st.markdown("#### Ask a Specific Question")
    st.caption("Any question about the business, a direct, data-informed answer in seconds.")
    question = st.text_input("Your question",
        placeholder="e.g. Should I hire another worker for Rwox right now?",
        label_visibility="collapsed", key=f"{kp}_ai_q")
    if st.button("Ask 🤖", disabled=not question.strip(), key=f"{kp}_ai_ask"):
        context = _build_context(company)
        prompt  = (
            f"Financial context:\n{context}\n\n"
            f"Owner asks: {question.strip()}\n\n"
            f"Direct, honest answer in 2-4 sentences. Say yes or no clearly if needed. "
            f"Use ₹ for money. Under 80 words."
        )
        with st.spinner("Thinking..."):
            result = _groq_call(prompt)
        if result.startswith("ERROR:"):
            st.error("Could not get a response. Check your GROQ_API_KEY in .env.")
        else:
            _advice_box(f"🤖 On '{question.strip()}':", result)


# ─────────────────────────────────────────────────────────────────────────────
# VIEW RENDERER + ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
def _render_view(conn, company: str, kp: str) -> None:
    default_co = company if company != "both" else "Rwox"
    inner = st.tabs([
        "📊 Annual Overview",
        "💸 Expense Breakdown",
        "🚦 Health Check",
        "📝 Update This Month",
        "📄 Upload Statements",
        "🤖 AI Advisor",
    ])
    with inner[0]: _tab_snapshot(company)
    with inner[1]: _tab_expenses(company, kp)
    with inner[2]: _tab_health(company)
    with inner[3]: _tab_monthly(conn, company, kp)
    with inner[4]: _tab_upload(conn, kp, default_co)
    with inner[5]: _tab_ai(company, kp)


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


def render_financials_page(conn) -> None:
    _dark = st.session_state.get("dark_mode", False)
    st.markdown(_DARK_CSS if _dark else _WARM_CSS, unsafe_allow_html=True)
    global _PLOT
    _PLOT = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                 font_color="#F5E6D3" if _dark else "#2C2218", margin=dict(t=45, b=30, l=10, r=10))
    _ensure_tables(conn)
    st.header("Financial Pulse")
    st.caption("Your live financial dashboard, margins, cash position, and business health without waiting for year-end statements.")

    outer = st.tabs(["📊 Both Companies", "🏭 Rwox", "🏪 Elastohorse"])
    with outer[0]: _render_view(conn, "both",        "fb")
    with outer[1]: _render_view(conn, "Rwox",        "fr")
    with outer[2]: _render_view(conn, "Elastohorse", "fe")
