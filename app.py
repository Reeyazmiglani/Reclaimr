import importlib.util
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import date, timedelta
from pathlib import Path
from db.schema import init_db

st.set_page_config(page_title="Reclaimr", layout="wide")

_FONT   = ("@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600&display=swap');"
           "@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=block');")
_FONT_F = "* { font-family: 'DM Sans', sans-serif !important; }[class*='material-symbols'] { font-family: 'Material Symbols Rounded' !important; font-style: normal !important; }"
_LIGHT_CSS = (
    "<style>" + _FONT + _FONT_F +
    "[data-testid='stSidebarNav']{display:none!important}"
    "h1{border-bottom:3px solid #C17F3E;padding-bottom:6px;display:inline-block}"
    "[data-testid='metric-container']{background:#FFF8F0;border:1px solid #E8D5B7;"
    "border-radius:10px;padding:14px 18px}"
    "[data-testid='stMetricValue']{color:#2C2218}"
    "[data-testid='stMetricLabel']{color:#8B6A45}"
    "[data-testid='stSidebar']{background:#FFF0DC!important;border-right:1px solid #E8D5B7!important}"
    "hr{border-color:#E8D5B7!important}"
    "[data-testid='stDataFrame'] th{background:#FFF8F0!important;color:#2C2218!important;border:1px solid #E8D5B7!important}"
    "[data-testid='stDataFrame'] td{border-color:#E8D5B7!important}"
    "[data-testid='stDataFrame'] tr:nth-child(even) td{background:#FFF8F0!important}"
    "div[data-baseweb='tab-highlight']{background:#C17F3E!important}"
    "button[data-baseweb='tab'][aria-selected='true']{color:#C17F3E!important}"
    "html body div[data-baseweb='input']{box-shadow:0 0 0 1px #C5A882!important;border:none!important;border-radius:6px!important}"
    "html body div[data-baseweb='textarea']{box-shadow:0 0 0 1px #C5A882!important;border:none!important;border-radius:6px!important}"
    "html body div[data-baseweb='select']>div:first-child{box-shadow:0 0 0 1px #C5A882!important;border:none!important;border-radius:6px!important}"
    "[data-testid='stToggle'] label,[data-testid='stToggle'] p{white-space:nowrap!important}"
    ".act-btn{min-width:38px;text-align:center}"
    "[data-testid='stSidebarNavItems']{display:none!important}"
    ".block-container{padding-top:1rem!important;padding-bottom:1rem!important;overflow:visible!important}"
    "header{display:none!important}"
    "details[data-testid='stExpander'] summary span:first-of-type{font-family:'Material Symbols Rounded'!important;font-style:normal!important}"
    "</style>"
)
_DARK_CSS = (
    "<style>" + _FONT + _FONT_F +
    "[data-testid='stSidebarNav']{display:none!important}"
    "[data-testid='stAppViewContainer']{background:#1A1410!important}"
    "[data-testid='stHeader']{background:#1A1410!important;border-bottom:1px solid #4A3728!important}"
    "h1{border-bottom:3px solid #C17F3E;padding-bottom:6px;display:inline-block;color:#F5E6D3!important}"
    "h2,h3,h4{color:#F5E6D3!important}"
    "p,label,span{color:#F5E6D3!important}"
    "[data-testid='stSidebar'] *{color:#F5E6D3!important}"
    "[class*='material-symbols']{color:inherit!important;font-family:'Material Symbols Rounded'!important;font-style:normal!important}"
    "[data-testid='metric-container']{background:#2C2218!important;border:1px solid #4A3728!important;"
    "border-radius:10px;padding:14px 18px}"
    "[data-testid='stMetricValue']{color:#F5E6D3!important}"
    "[data-testid='stMetricLabel']{color:#C4A882!important}"
    "[data-testid='stSidebar']{background:#1E160E!important;border-right:1px solid #4A3728!important}"
    "hr{border-color:#4A3728!important}"
    "[data-testid='stDataFrame'] th{background:#2C2218!important;color:#F5E6D3!important;border:1px solid #4A3728!important}"
    "[data-testid='stDataFrame'] td{border-color:#4A3728!important;color:#F5E6D3}"
    "[data-testid='stDataFrame'] tr:nth-child(even) td{background:#231C14!important}"
    "div[data-baseweb='tab-highlight']{background:#C17F3E!important}"
    "button[data-baseweb='tab'][aria-selected='true']{color:#C17F3E!important}"
    "html body div[data-baseweb='input']{box-shadow:0 0 0 1px #8B6A45!important;border:none!important;border-radius:6px!important;background:#231C14!important}"
    "div[data-baseweb='input'] input{background:#231C14!important;color:#F5E6D3!important}"
    "html body div[data-baseweb='textarea']{box-shadow:0 0 0 1px #8B6A45!important;border:none!important;border-radius:6px!important;background:#231C14!important}"
    "div[data-baseweb='textarea'] textarea{background:#231C14!important;color:#F5E6D3!important}"
    "html body div[data-baseweb='select']>div:first-child{box-shadow:0 0 0 1px #8B6A45!important;border:none!important;border-radius:6px!important;background:#231C14!important}"
    "div[data-baseweb='select'] span,div[data-baseweb='select'] div{color:#F5E6D3!important}"
    "div[data-baseweb='input'] input::placeholder,div[data-baseweb='textarea'] textarea::placeholder{color:#6B5040!important}"
    "[data-testid='stToggle'] label,[data-testid='stToggle'] p{white-space:nowrap!important}"
    "[data-testid='stForm']{background:#2C2218!important;border-color:#4A3728!important}"
    "[data-testid='stExpander'] details{background:#2C2218!important;border-color:#4A3728!important}"
    "[data-testid='stButton'] button{background:#2C2218!important;color:#F5E6D3!important;border:1px solid #4A3728!important}"
    "[data-testid='stButton'] button:hover{background:#3A2E24!important}"
    ".orders-table thead tr{background:#2C2218!important;color:#F5E6D3!important}"
    ".orders-table th,.orders-table td{border:1px solid #8B6A45!important;color:#F5E6D3!important}"
    ".orders-table tbody tr{background:#1A1410!important}"
    ".orders-table tbody tr:nth-child(even){background:#231C14!important}"
    ".orders-table tbody tr:hover{background:#2C2218!important}"
    ".etbl thead tr{background:#2C2218!important;color:#F5E6D3!important}"
    ".etbl th,.etbl td{border:1px solid #8B6A45!important;color:#F5E6D3!important}"
    ".etbl tbody tr{background:#1A1410!important}"
    ".etbl tbody tr:nth-child(even){background:#231C14!important}"
    ".etbl tbody tr:hover{background:#2C2218!important}"
    ".act-btn{border-color:#4A3728!important;color:#F5E6D3!important;background:#1A1410!important}"
    ".act-btn:hover{background:#2C2218!important;color:#F5E6D3!important}"
    ".act-btn.del{border-color:#C0392B!important;color:#C0392B!important;background:#1A1410!important}"
    "[data-testid='stSidebarNavItems']{display:none!important}"
    ".block-container{padding-top:1rem!important;padding-bottom:1rem!important;overflow:visible!important}"
    "header{display:none!important}"
    "details[data-testid='stExpander'] summary span:first-of-type{font-family:'Material Symbols Rounded'!important;font-style:normal!important}"
    "</style>"
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
_dark = st.session_state.get("dark_mode", False)
st.markdown(_DARK_CSS if _dark else _LIGHT_CSS, unsafe_allow_html=True)

# ── Navigation ─────────────────────────────────────────────────────────────────
PAGE_KEYS  = ["Home","Overview","Orders","Production","Procurement","Exports","Credit","Financials","Forecasting"]
PAGE_FILES = {"Overview":Path("pages")/"0_overview.py",
              "Orders":Path("pages")/"1_orders.py",
              "Production":Path("pages")/"2_production.py",
              "Procurement":Path("pages")/"3_procurement.py",
              "Exports":Path("pages")/"4_exports.py",
              "Credit":Path("pages")/"5_credit.py",
              "Financials":Path("pages")/"6_financials.py",
              "Forecasting":Path("pages")/"7_forecasting.py"}
PAGE_FN    = {"Overview":"render_intelligence_page",
              "Orders":"render_orders_page","Procurement":"render_procurement_page",
              "Production":"render_production_page","Exports":"render_exports_page",
              "Financials":"render_financials_page","Forecasting":"render_forecasting_page",
              "Credit":"render_credit_page"}

@st.cache_resource
def get_conn():
    return init_db(Path("db") / "erp.db")

conn = get_conn()

if "page" in st.query_params:
    req = st.query_params["page"]
    if req in PAGE_KEYS: st.session_state["_page"] = req
    del st.query_params["page"]

st.sidebar.markdown(_LOGO_HTML, unsafe_allow_html=True)
page = st.sidebar.radio("", PAGE_KEYS,
       index=PAGE_KEYS.index(st.session_state.get("_page","Home")))
st.sidebar.text_input("🔍 Search", placeholder="Search...")
st.session_state["_page"] = page

_, _dm_col = st.columns([0.75, 0.25])
with _dm_col:
    st.toggle("🌙 Dark mode", key="dark_mode", value=st.session_state.get("dark_mode", False))

if page != "Home":
    path = PAGE_FILES[page]; spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    getattr(mod, PAGE_FN[page])(conn); st.stop()

st.markdown(
    "<div style='text-align:center;padding:30px 0 20px 0'>"
    "<svg width='120' height='120' viewBox='0 0 100 100' xmlns='http://www.w3.org/2000/svg'>"
    "<path d='M 50 10 A 40 40 0 1 0 85 65' fill='none' stroke='#C17F3E' stroke-width='5' stroke-linecap='round'/>"
    "<polygon points='85,50 95,68 75,68' fill='#C17F3E'/>"
    "<circle cx='50' cy='50' r='8' fill='#C17F3E'/>"
    "<circle cx='50' cy='50' r='3.5' fill='#FDFAF6'/>"
    "</svg>"
    "<div style='font-family:DM Sans,sans-serif;font-size:28px;font-weight:700;color:#C17F3E;margin-top:8px'>Reclaimr</div>"
    "<div style='font-family:DM Sans,sans-serif;font-size:11px;letter-spacing:2px;color:#8B6A45;margin-top:4px'>MANUFACTURING ERP</div>"
    "</div>",
    unsafe_allow_html=True,
)

# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════
_dark = st.session_state.get("dark_mode", False)
PLOT = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#F5E6D3" if _dark else "#2C2218", margin=dict(t=45,b=30,l=10,r=10))


def qdf(sql, params=None):
    cur = conn.execute(sql, params or [])
    rows = cur.fetchall(); cols = [d[0] for d in cur.description]
    return pd.DataFrame([dict(r) for r in rows], columns=cols) if rows else pd.DataFrame(columns=cols)


def prep_orders(df):
    if df.empty: return df
    dt = pd.to_datetime(df["created_at"], errors="coerce")
    df["month_sort"] = dt.dt.strftime("%Y-%m")
    df["month"]      = dt.dt.strftime("%b '%y")
    df["revenue"] = df.apply(
        lambda r: r["quantity"]*r["rate"] if r["rate_type"]=="per_unit" else r["rate"], axis=1)
    return df


def prep_proc(df):
    if df.empty: return df
    dt = pd.to_datetime(df["purchase_date"], errors="coerce")
    df["month_sort"] = dt.dt.strftime("%Y-%m")
    df["month"]      = dt.dt.strftime("%b '%y")
    df["spend"] = df.apply(
        lambda r: r["quantity"]*r["unit_cost"] if r["price_type"]=="per_unit" else r["unit_cost"], axis=1)
    return df


def prep_prod(df):
    if df.empty: return df
    dt = pd.to_datetime(df["date"], errors="coerce")
    df["month_sort"] = dt.dt.strftime("%Y-%m")
    df["month"]      = dt.dt.strftime("%b '%y")
    return df


def delta(curr, prev):
    if prev == 0: return None
    return f"{((curr-prev)/prev)*100:+.1f}%"


def by_month(df, val_col, agg="sum"):
    if df.empty: return pd.DataFrame(columns=["month_sort","month",val_col])
    g = df.groupby(["month_sort","month"])[val_col]
    g = g.sum() if agg=="sum" else g.count()
    return g.reset_index(name=val_col).sort_values("month_sort")


def count_by_month(df):
    if df.empty: return pd.DataFrame(columns=["month_sort","month","n"])
    return (df.groupby(["month_sort","month"]).size()
            .reset_index(name="n").sort_values("month_sort"))


def comparison_bar(curr_df, prev_df, val_col, title,
                   curr_color="#C17F3E", prev_color="#8B6A45", height=300, prefix="₹"):
    """Side-by-side bars: current period vs previous period by month."""
    cm = by_month(curr_df, val_col)
    pm = by_month(prev_df, val_col)
    # All months in chronological order
    all_months = pd.concat([cm[["month_sort","month"]], pm[["month_sort","month"]]]) \
                   .drop_duplicates().sort_values("month_sort")["month"].tolist()
    hover = f"<b>%{{x}}</b><br>{prefix}%{{y:,.0f}}<extra></extra>" if prefix == "₹" \
            else "<b>%{x}</b><br>%{y:,.1f} kg<extra></extra>"
    traces = []
    if not cm.empty:
        traces.append(go.Bar(x=cm["month"], y=cm[val_col], name="This Period",
                             marker_color=curr_color, hovertemplate=hover))
    if not pm.empty:
        traces.append(go.Bar(x=pm["month"], y=pm[val_col], name="Prev Period",
                             marker_color=prev_color, opacity=0.65, hovertemplate=hover))
    f = go.Figure(traces)
    f.update_layout(title=title, height=height, barmode="group",
                    xaxis=dict(gridcolor="#E8D5B7", type="category", categoryorder="array",
                               categoryarray=all_months, tickangle=0),
                    yaxis=dict(gridcolor="#E8D5B7"),
                    legend=dict(orientation="h", y=-0.25), **PLOT)
    return f


def comparison_line(curr_df, prev_df, val_col, title,
                    curr_color="#C17F3E", prev_color="#8B6A45", height=280, count=False):
    """Line chart comparing current vs previous period."""
    if count:
        cm = count_by_month(curr_df); pm = count_by_month(prev_df)
        vc = "n"
    else:
        cm = by_month(curr_df, val_col); pm = by_month(prev_df, val_col)
        vc = val_col
    all_months = pd.concat(
        [cm[["month_sort","month"]], pm[["month_sort","month"]]]) \
        .drop_duplicates().sort_values("month_sort")["month"].tolist()
    traces = []
    if not cm.empty:
        traces.append(go.Scatter(x=cm["month"], y=cm[vc], name="This Period",
            mode="lines+markers", line=dict(color=curr_color, width=2), marker=dict(size=7),
            hovertemplate="<b>%{x}</b><br>%{y:,.0f}<extra></extra>"))
    if not pm.empty:
        traces.append(go.Scatter(x=pm["month"], y=pm[vc], name="Prev Period",
            mode="lines+markers", line=dict(color=prev_color, width=2, dash="dot"),
            marker=dict(size=6), opacity=0.7,
            hovertemplate="<b>%{x}</b><br>%{y:,.0f}<extra></extra>"))
    f = go.Figure(traces)
    f.update_layout(title=title, height=height,
                    xaxis=dict(gridcolor="#E8D5B7", type="category", categoryorder="array",
                               categoryarray=all_months, tickangle=0),
                    yaxis=dict(gridcolor="#E8D5B7"),
                    legend=dict(orientation="h", y=-0.3), **PLOT)
    return f


def inr(val):
    """Format a rupee value compactly: Cr / L / K."""
    if val >= 1_00_00_000:  return f"₹{val/1_00_00_000:.2f} Cr"
    if val >= 1_00_000:     return f"₹{val/1_00_000:.2f} L"
    if val >= 1_000:        return f"₹{val/1_000:.1f} K"
    return f"₹{val:,.0f}"


def pct_badge(curr, prev, label):
    if prev == 0:
        return f"<td style='padding:4px 14px;color:#8B6A45'>{label}: N/A</td>"
    p = (curr-prev)/prev*100
    col = "#1B7F4F" if p >= 0 else "#C0392B"
    arr = "▲" if p >= 0 else "▼"
    return (f"<td style='padding:4px 14px;border-radius:4px;background:#FFF8F0;"
            f"border:1px solid #E8D5B7'>"
            f"<span style='color:#8B6A45'>{label}</span> "
            f"<b style='color:{col}'>{arr} {abs(p):.1f}%</b></td>")


def _html_table(df):
    _dark = st.session_state.get("dark_mode", False)
    hdr_bg  = "#2C2218" if _dark else "#FFF0DC"
    hdr_clr = "#F5E6D3" if _dark else "#2C2218"
    row_bg  = "#1A1410" if _dark else "#FFFFFF"
    alt_bg  = "#231C14" if _dark else "#FFF8F0"
    bdr     = "#4A3728" if _dark else "#E8D5B7"
    txt     = "#F5E6D3" if _dark else "#2C2218"
    def _fmt(v):
        if pd.isna(v): return "—"
        if isinstance(v, float) and v == int(v): return str(int(v))
        return str(v)
    headers = "".join(f"<th>{c}</th>" for c in df.columns)
    rows = "".join(
        "<tr>" + "".join(f"<td>{_fmt(v)}</td>" for v in r) + "</tr>"
        for _, r in df.iterrows()
    )
    return (
        f"<style>.erp-tbl{{width:100%;border-collapse:collapse;font-size:14px;margin-bottom:8px}}"
        f".erp-tbl th{{background:{hdr_bg};color:{hdr_clr};font-weight:600;padding:8px 12px;"
        f"border:1px solid {bdr};text-align:left}}"
        f".erp-tbl td{{padding:8px 12px;border:1px solid {bdr};color:{txt}}}"
        f".erp-tbl tbody tr{{background:{row_bg}}}"
        f".erp-tbl tbody tr:nth-child(even){{background:{alt_bg}}}"
        f"</style>"
        f"<table class='erp-tbl'><thead><tr>{headers}</tr></thead><tbody>{rows}</tbody></table>"
    )


def hbar(x, y, title, color="#C17F3E", height=280):
    f = go.Figure(go.Bar(x=x, y=y, orientation="h", marker_color=color,
                         hovertemplate="<b>%{y}</b><br>₹%{x:,.0f}<extra></extra>"))
    f.update_layout(title=title, height=height,
                    xaxis=dict(gridcolor="#E8D5B7"),
                    yaxis=dict(autorange="reversed", gridcolor="#E8D5B7"), **PLOT)
    return f


# ══════════════════════════════════════════════════════════════════════════════
# HEADER — period selector only (tabs handle company)
# ══════════════════════════════════════════════════════════════════════════════
today = date.today()
st.title("Reclaimr")
st.caption(f"Today: {today.strftime('%A, %d %B %Y')}")

PRESETS = ["This Month","This Quarter","Last Quarter",
           "Last 3 Months","Last 6 Months","This Year","Custom Range"]

pc1, pc2 = st.columns([3, 2])
with pc1:
    preset = st.selectbox("", PRESETS, index=3, label_visibility="collapsed")
with pc2:
    compare = st.toggle("📊 Compare to previous period", value=True)

# Custom range pickers
cs_date = ce_date = None
if preset == "Custom Range":
    cr1, cr2 = st.columns(2)
    with cr1:
        cs_date = st.date_input("From", value=today.replace(day=1), key="cr_from")
    with cr2:
        ce_date = st.date_input("To",   value=today,                key="cr_to")

# Resolve start / end
import calendar as _cal
if preset == "This Month":
    s = today.replace(day=1); e = today
elif preset == "This Quarter":
    q = (today.month-1)//3; s = date(today.year, q*3+1, 1); e = today
elif preset == "Last Quarter":
    q = (today.month-1)//3
    if q == 0: s=date(today.year-1,10,1); e=date(today.year-1,12,31)
    else:
        lm = q*3; s=date(today.year,(q-1)*3+1,1)
        e=date(today.year,lm,_cal.monthrange(today.year,lm)[1])
elif preset == "Last 3 Months":
    m3=today.month-3; y3=today.year+(m3-1)//12; m3=(m3-1)%12+1
    s=date(y3,m3,1); e=today
elif preset == "Last 6 Months":
    m6=today.month-6; y6=today.year+(m6-1)//12; m6=(m6-1)%12+1
    s=date(y6,m6,1); e=today
elif preset == "This Year":
    s=date(today.year,1,1); e=today
else:
    s=cs_date or today.replace(day=1); e=ce_date or today

days = (e-s).days
pe = s-timedelta(days=1); ps = pe-timedelta(days=days)
ss, es, pss, pes = s.isoformat(), e.isoformat(), ps.isoformat(), pe.isoformat()

co_rows = {r["name"]: r["id"] for r in [dict(r) for r in conn.execute("SELECT name,id FROM companies")]}
rwox_id   = co_rows.get("Rwox")
elasto_id = co_rows.get("Elastohorse")

st.caption(f"**{s.strftime('%d %b %Y')} → {e.strftime('%d %b %Y')}**  ·  "
           f"vs prev: {ps.strftime('%d %b %Y')} → {pe.strftime('%d %b %Y')}")
st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# DATA LOAD
# ══════════════════════════════════════════════════════════════════════════════
def load_orders(s, e):
    return prep_orders(qdf(
        "SELECT o.id, c.name AS company, o.customer_name, o.product, "
        "o.quantity, o.rate, o.rate_type, o.status, o.created_at "
        "FROM orders o JOIN companies c ON o.company_id=c.id "
        "WHERE date(o.created_at) BETWEEN ? AND ?", [s, e]))

def load_proc(s, e):
    return prep_proc(qdf(
        "SELECT p.id, c.name AS company, p.supplier, p.item, "
        "p.quantity, p.unit_cost, p.price_type, p.purchase_date "
        "FROM procurement p JOIN companies c ON p.company_id=c.id "
        "WHERE p.purchase_date BETWEEN ? AND ?", [s, e]))

def load_prod(s, e):
    return prep_prod(qdf(
        f"SELECT id, date, output_kg, COALESCE(cartons_1kg,0) AS c1, COALESCE(cartons_5kg,0) AS c5 "
        f"FROM production_logs WHERE date BETWEEN ? AND ? AND company_id={rwox_id}", [s, e]))

ord_c  = load_orders(ss, es);  ord_p  = load_orders(pss, pes)
proc_c = load_proc(ss, es);    proc_p = load_proc(pss, pes)
prod_c = load_prod(ss, es);    prod_p = load_prod(pss, pes)

# Pending count
pend = conn.execute("SELECT COUNT(*) FROM orders WHERE status IN ('received','in_production')").fetchone()[0]

# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════
tab1, tab2, tab3 = st.tabs(["📊 Both Companies", "🏭 Rwox", "🏪 Elastohorse"])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — OVERVIEW
# ─────────────────────────────────────────────────────────────────────────────
with tab1:
    cr = ord_c["revenue"].sum() if not ord_c.empty else 0
    pr = ord_p["revenue"].sum() if not ord_p.empty else 0
    co = len(ord_c); po = len(ord_p)
    cs = proc_c["spend"].sum() if not proc_c.empty else 0
    ps2= proc_p["spend"].sum() if not proc_p.empty else 0
    ck = prod_c["output_kg"].sum() if not prod_c.empty else 0
    pk = prod_p["output_kg"].sum() if not prod_p.empty else 0

    m1,m2,m3,m4,m5 = st.columns(5)
    m1.metric("Total Revenue",      inr(cr),       delta(cr,pr),  help=f"₹{cr:,.0f}")
    m2.metric("Total Orders",        co,            delta(co,po))
    m3.metric("Procurement Spend",  inr(cs),       delta(cs,ps2), help=f"₹{cs:,.0f}")
    m4.metric("Production kg",      f"{ck:,.1f}",  delta(ck,pk))
    m5.metric("Pending Orders",      pend,
              "⚠ High" if pend > 5 else None,
              delta_color="inverse" if pend > 5 else "off")

    badges = (pct_badge(cr,pr,"Revenue") + pct_badge(co,po,"Orders") +
              pct_badge(cs,ps2,"Procurement") + pct_badge(ck,pk,"Production"))
    st.markdown(
        f"<table style='border-collapse:separate;border-spacing:6px 0;margin:6px 0'>"
        f"<tr>{badges}</tr></table>",
        unsafe_allow_html=True)

    if compare:
        st.caption("Solid = current period  ·  Faded = prior period")
    st.divider()

    _op = ord_p if compare else pd.DataFrame()
    cc1, cc2 = st.columns(2)
    with cc1:
        st.plotly_chart(comparison_bar(ord_c, _op, "revenue",
            "Combined Revenue by Month (₹)"), use_container_width=True)
    with cc2:
        st.plotly_chart(comparison_line(ord_c, _op, None,
            "Combined Order Count by Month", count=True, curr_color="#1B7F4F"), use_container_width=True)

    # Revenue split pie
    if not ord_c.empty:
        rev_co = ord_c.groupby("company")["revenue"].sum().reset_index()
        if rev_co["revenue"].sum() > 0:
            pie = go.Figure(go.Pie(
                labels=rev_co["company"].tolist(), values=rev_co["revenue"].tolist(),
                hole=0.5, marker_colors=["#C17F3E","#1B7F4F"],
                hovertemplate="<b>%{label}</b><br>₹%{value:,.0f}<br>%{percent}<extra></extra>"))
            pie.update_layout(title="Revenue Split: Rwox vs Elastohorse",
                              height=300, legend=dict(orientation="h",y=-0.2), **PLOT)
            st.plotly_chart(pie, use_container_width=True)

    st.divider()
    st.subheader("Alerts")
    st.caption("Issues that need action today — overdue orders, stagnant jobs, and procurement cost spikes.")

    overdue = qdf(
        "SELECT o.id, c.name AS company, o.customer_name AS customer, o.product, "
        "o.expected_dispatch_date AS due_date, o.status "
        "FROM orders o JOIN companies c ON o.company_id=c.id "
        "WHERE date(o.expected_dispatch_date) < date('now') AND o.status != 'dispatched' "
        "ORDER BY o.expected_dispatch_date")
    stagnant = qdf(
        "SELECT o.id, c.name AS company, o.customer_name AS customer, o.product, "
        "substr(o.created_at,1,10) AS received_on, o.status "
        "FROM orders o JOIN companies c ON o.company_id=c.id "
        "WHERE date(o.created_at) <= date('now','-7 days') AND o.status='received' "
        "ORDER BY o.created_at")

    spikes = []
    if not proc_c.empty and not proc_p.empty:
        cp2 = proc_c.groupby("item")["unit_cost"].mean()
        pp2 = proc_p.groupby("item")["unit_cost"].mean()
        for item in cp2.index:
            if item in pp2.index and pp2[item] > 0:
                pct_chg = (cp2[item]-pp2[item])/pp2[item]*100
                if pct_chg > 5:
                    spikes.append({"Material":item,"Prev ₹":f"{pp2[item]:,.2f}",
                                   "Curr ₹":f"{cp2[item]:,.2f}","Spike":f"+{pct_chg:.1f}%"})

    # Migrate receivables from old Financials schema if needed
    _rec_cols = [r[1] for r in conn.execute("PRAGMA table_info(receivables)").fetchall()]
    if _rec_cols and "party_name" in _rec_cols:
        conn.executescript("""
            ALTER TABLE receivables RENAME TO receivables_old;
            CREATE TABLE receivables (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                company TEXT NOT NULL DEFAULT '',
                reference TEXT, amount REAL NOT NULL, date TEXT NOT NULL,
                notes TEXT, status TEXT NOT NULL DEFAULT 'outstanding',
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );
            INSERT INTO receivables (id, customer_name, company, reference, amount, date, notes, status, created_at)
            SELECT r.id, r.party_name, COALESCE(c.name,''), NULL,
                   r.amount, r.as_of_date, r.notes, r.status, r.created_at
            FROM receivables_old r LEFT JOIN companies c ON r.company_id = c.id;
            DROP TABLE receivables_old;
        """)
        conn.commit()

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS batch_complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT, batch_id INTEGER NOT NULL,
            order_id INTEGER, customer_name TEXT, date TEXT NOT NULL,
            issue_type TEXT NOT NULL, description TEXT NOT NULL,
            quantity_affected REAL, physical_return INTEGER NOT NULL DEFAULT 0,
            quantity_returned REAL, initial_action TEXT NOT NULL,
            logged_by TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS batch_allocations (
            id INTEGER PRIMARY KEY AUTOINCREMENT, batch_id INTEGER NOT NULL,
            order_id INTEGER NOT NULL, allocated_kg REAL NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
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
    """)
    conn.commit()

    unresolved_complaints = conn.execute(
        "SELECT COUNT(*) FROM batch_complaints WHERE status != 'resolved'"
    ).fetchone()[0]

    over_alloc = qdf(
        "SELECT pl.batch_ref, pl.date, pl.output_kg, SUM(ba.allocated_kg) AS total_allocated "
        "FROM batch_allocations ba "
        "JOIN production_logs pl ON ba.batch_id = pl.id "
        "GROUP BY ba.batch_id "
        "HAVING SUM(ba.allocated_kg) > pl.output_kg "
        "ORDER BY pl.date DESC")

    overdue_rec = qdf("""
        SELECT r.customer_name, r.company,
               r.amount - COALESCE(SUM(p.amount_paid),0) AS balance,
               r.date,
               CAST(julianday('now','localtime') - julianday(r.date) AS INTEGER) AS days
        FROM receivables r
        LEFT JOIN payments p ON p.type='receivable' AND p.reference_id=r.id
        WHERE r.status != 'paid'
        GROUP BY r.id
        HAVING days > 45
        ORDER BY days DESC""")

    overdue_pay = qdf("""
        SELECT p.vendor_name,
               p.amount - COALESCE(SUM(pm.amount_paid),0) AS balance,
               p.date,
               CAST(julianday('now','localtime') - julianday(p.date) AS INTEGER) AS days
        FROM payables p
        LEFT JOIN payments pm ON pm.type='payable' AND pm.reference_id=p.id
        WHERE p.status != 'paid'
        GROUP BY p.id
        HAVING days > 45
        ORDER BY days DESC""")

    all_clear = (overdue.empty and stagnant.empty and not spikes
                 and unresolved_complaints == 0 and over_alloc.empty
                 and overdue_rec.empty and overdue_pay.empty)
    if all_clear:
        st.success("✅ All orders current, no stagnant jobs, no procurement spikes, no open complaints, no overdue credit.")
    else:
        if not overdue_rec.empty:
            total_overdue_r = overdue_rec["balance"].sum()
            st.error(
                f"🔴 **{len(overdue_rec)} receivable(s) overdue 45+ days**, "
                f"₹{total_overdue_r:,.2f} outstanding. Go to Credit page."
            )
            st.markdown(_html_table(overdue_rec.rename(columns={
                "customer_name": "Customer Name", "company": "Company",
                "balance": "Balance", "date": "Date", "days": "Days"
            })), unsafe_allow_html=True)
        if not overdue_pay.empty:
            total_overdue_p = overdue_pay["balance"].sum()
            st.error(
                f"🔴 **{len(overdue_pay)} payable(s) overdue 45+ days**, "
                f"₹{total_overdue_p:,.2f} outstanding. Go to Credit page."
            )
            st.markdown(_html_table(overdue_pay.rename(columns={
                "vendor_name": "Vendor Name", "balance": "Balance",
                "date": "Date", "days": "Days"
            })), unsafe_allow_html=True)
        if unresolved_complaints > 0:
            st.error(f"🔴 **{unresolved_complaints} unresolved {'complaint' if unresolved_complaints==1 else 'complaints'}** — go to Production → Complaints & Returns to action them")
        if not over_alloc.empty:
            st.error(f"🔴 **{len(over_alloc)} {'batch' if len(over_alloc)==1 else 'batches'} over-allocated**, allocated kg exceeds produced kg")
            st.markdown(_html_table(over_alloc.rename(columns={
                "batch_ref": "Batch Ref", "date": "Date",
                "output_kg": "Output (kg)", "total_allocated": "Allocated (kg)"
            })), unsafe_allow_html=True)
        if not overdue.empty:
            st.error(f"🔴 **{len(overdue)} {'order' if len(overdue)==1 else 'orders'} past dispatch date**, these need immediate attention")
            st.markdown(_html_table(overdue.rename(columns={
                "id": "ID", "company": "Company", "customer": "Customer",
                "product": "Product", "due_date": "Due Date", "status": "Status"
            })), unsafe_allow_html=True)
        if not stagnant.empty:
            st.warning(f"🟡 **{len(stagnant)} {'order' if len(stagnant)==1 else 'orders'} sitting in 'received' for 7+ days**, check whether production has started")
            st.markdown(_html_table(stagnant.rename(columns={
                "id": "ID", "company": "Company", "customer": "Customer",
                "product": "Product", "received_on": "Received On", "status": "Status"
            })), unsafe_allow_html=True)
        if spikes:
            st.warning(f"💸 **{len(spikes)} {'material' if len(spikes)==1 else 'materials'} with price increases above 5%** — review vendor quotes before the next purchase")
            st.markdown(_html_table(pd.DataFrame(spikes)), unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — RWOX
# ─────────────────────────────────────────────────────────────────────────────
with tab2:
    ro = ord_c[ord_c["company"]=="Rwox"].copy()  if not ord_c.empty  else pd.DataFrame()
    rp = ord_p[ord_p["company"]=="Rwox"].copy()  if not ord_p.empty  else pd.DataFrame()
    rc = proc_c[proc_c["company"]=="Rwox"].copy() if not proc_c.empty else pd.DataFrame()
    rcp= proc_p[proc_p["company"]=="Rwox"].copy() if not proc_p.empty else pd.DataFrame()

    rr=ro["revenue"].sum() if not ro.empty else 0; rrp=rp["revenue"].sum() if not rp.empty else 0
    ron=len(ro); ronp=len(rp)
    rs=rc["spend"].sum() if not rc.empty else 0; rsp=rcp["spend"].sum() if not rcp.empty else 0
    rkg=prod_c["output_kg"].sum() if not prod_c.empty else 0
    rkgp=prod_p["output_kg"].sum() if not prod_p.empty else 0

    rm1,rm2,rm3,rm4 = st.columns(4)
    rm1.metric("Revenue",           inr(rr),       delta(rr,rrp),  help=f"₹{rr:,.0f}")
    rm2.metric("Orders",             ron,           delta(ron,ronp))
    rm3.metric("Procurement Spend", inr(rs),       delta(rs,rsp),  help=f"₹{rs:,.0f}")
    rm4.metric("Production kg",     f"{rkg:,.1f}", delta(rkg,rkgp))

    badges2 = (pct_badge(rr,rrp,"Revenue")+pct_badge(ron,ronp,"Orders")+
               pct_badge(rs,rsp,"Procurement")+pct_badge(rkg,rkgp,"Production"))
    st.markdown(f"<table style='border-collapse:separate;border-spacing:6px 0;margin:6px 0'>"
                f"<tr>{badges2}</tr></table>", unsafe_allow_html=True)

    if compare:
        st.caption("Solid = current period  ·  Faded = prior period")
    st.divider()

    _rp = rp if compare else pd.DataFrame()
    _rcp= rcp if compare else pd.DataFrame()
    _pp2= prod_p if compare else pd.DataFrame()

    rc1, rc2 = st.columns(2)
    with rc1:
        st.plotly_chart(comparison_bar(ro, _rp, "revenue",
            "Revenue by Month (₹)"), use_container_width=True)
    with rc2:
        st.plotly_chart(comparison_line(ro, _rp, None,
            "Order Count by Month", curr_color="#1B7F4F", count=True), use_container_width=True)

    rc3, rc4 = st.columns(2)
    with rc3:
        if not rc.empty and rc["supplier"].notna().any():
            vs = rc.groupby("supplier")["spend"].sum().nlargest(10).reset_index()
            st.plotly_chart(hbar(vs["spend"].tolist(), vs["supplier"].tolist(),
                "Procurement Spend by Vendor (₹)"), use_container_width=True)
        else:
            st.info("No procurement data for this period.")
    with rc4:
        st.plotly_chart(comparison_bar(prod_c, _pp2, "output_kg",
            "Production kg by Month", curr_color="#1B7F4F", prev_color="#8B6A45",
            prefix="", height=280), use_container_width=True)

    # Procurement price trend per material
    if not rc.empty:
        st.markdown("**Procurement Price Trend per Material**")
        mat_dates = rc.copy().sort_values("purchase_date")
        # Average unit_cost per item per month, sorted chronologically
        mat_avg = (mat_dates.groupby(["item","month_sort","month"])["unit_cost"]
                   .mean().reset_index().sort_values("month_sort"))
        # Sorted month labels for x-axis ordering
        sorted_months = (mat_avg[["month_sort","month"]].drop_duplicates()
                         .sort_values("month_sort")["month"].tolist())
        materials = mat_avg["item"].dropna().unique()[:6]
        colors = ["#C17F3E","#1B7F4F","#D97706","#8B6A45","#C0392B","#2C2218"]
        traces = []
        for i, mat in enumerate(materials):
            sub = mat_avg[mat_avg["item"]==mat].sort_values("month_sort")
            if len(sub) >= 1:
                traces.append(go.Scatter(
                    x=sub["month"], y=sub["unit_cost"], name=mat,
                    mode="lines+markers", line=dict(color=colors[i%len(colors)],width=2),
                    marker=dict(size=7),
                    hovertemplate=f"<b>{mat}</b><br>%{{x}}<br>₹%{{y:,.2f}}/unit<extra></extra>"))
        if traces:
            f = go.Figure(traces)
            f.update_layout(title="Price / Unit Trend by Material (₹)", height=300,
                            xaxis=dict(gridcolor="#E8D5B7", type="category",
                                       categoryorder="array", categoryarray=sorted_months),
                            yaxis=dict(gridcolor="#E8D5B7"),
                            legend=dict(orientation="h",y=-0.3), **PLOT)
            st.plotly_chart(f, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — ELASTOHORSE
# ─────────────────────────────────────────────────────────────────────────────
with tab3:
    eo = ord_c[ord_c["company"]=="Elastohorse"].copy() if not ord_c.empty else pd.DataFrame()
    ep = ord_p[ord_p["company"]=="Elastohorse"].copy() if not ord_p.empty else pd.DataFrame()

    er=eo["revenue"].sum() if not eo.empty else 0; erp=ep["revenue"].sum() if not ep.empty else 0
    eon=len(eo); eonp=len(ep)

    em1,em2 = st.columns(2)
    em1.metric("Revenue", inr(er), delta(er,erp), help=f"₹{er:,.0f}")
    em2.metric("Orders",   eon,            delta(eon,eonp))

    badges3 = pct_badge(er,erp,"Revenue")+pct_badge(eon,eonp,"Orders")
    st.markdown(f"<table style='border-collapse:separate;border-spacing:6px 0;margin:6px 0'>"
                f"<tr>{badges3}</tr></table>", unsafe_allow_html=True)

    if compare:
        st.caption("Solid = current period  ·  Faded = prior period")
    st.divider()

    _ep = ep if compare else pd.DataFrame()
    ec1, ec2 = st.columns(2)
    with ec1:
        st.plotly_chart(comparison_bar(eo, _ep, "revenue",
            "Revenue by Month (₹)", curr_color="#C17F3E", prev_color="#8B6A45"),
            use_container_width=True)
    with ec2:
        st.plotly_chart(comparison_line(eo, _ep, None,
            "Order Count by Month", curr_color="#D97706", count=True),
            use_container_width=True)

    if eo.empty:
        st.info("No Elastohorse orders in the selected period. Add one from the Orders page.")
