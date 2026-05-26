import importlib.util
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import date, timedelta
from pathlib import Path
from db.schema import init_db

st.set_page_config(page_title="Reclaimr", layout="wide")
st.markdown("<style>[data-testid='stSidebarNav']{display:none!important}</style>",
            unsafe_allow_html=True)

# ── Navigation ─────────────────────────────────────────────────────────────────
PAGE_KEYS  = ["Home","Orders","Procurement","Production","Exports","Financials"]
PAGE_FILES = {"Orders":Path("pages")/"1_orders.py",
              "Procurement":Path("pages")/"2_procurement.py",
              "Production":Path("pages")/"3_production.py",
              "Exports":Path("pages")/"4_exports.py",
              "Financials":Path("pages")/"5_financials.py"}
PAGE_FN    = {"Orders":"render_orders_page","Procurement":"render_procurement_page",
              "Production":"render_production_page","Exports":"render_exports_page",
              "Financials":"render_financials_page"}

@st.cache_resource
def get_conn():
    return init_db(Path("db") / "erp.db")

conn = get_conn()

if "page" in st.query_params:
    req = st.query_params["page"]
    if req in PAGE_KEYS: st.session_state["_page"] = req
    del st.query_params["page"]

page = st.sidebar.radio("", PAGE_KEYS,
       index=PAGE_KEYS.index(st.session_state.get("_page","Home")))
st.sidebar.title("Reclaimr")
st.sidebar.text_input("🔍 Search", placeholder="Search...")
st.session_state["_page"] = page

if page != "Home":
    path = PAGE_FILES[page]; spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    getattr(mod, PAGE_FN[page])(conn); st.stop()

# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════
PLOT = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#ccc", margin=dict(t=45,b=30,l=10,r=10))


def qdf(sql, params=None):
    cur = conn.execute(sql, params or [])
    rows = cur.fetchall(); cols = [d[0] for d in cur.description]
    return pd.DataFrame([dict(r) for r in rows], columns=cols) if rows else pd.DataFrame(columns=cols)


def prep_orders(df):
    if df.empty: return df
    dt = pd.to_datetime(df["created_at"], errors="coerce")
    df["month_sort"] = dt.dt.strftime("%Y-%m")
    df["month"]      = dt.dt.strftime("%b %Y")
    df["revenue"] = df.apply(
        lambda r: r["quantity"]*r["rate"] if r["rate_type"]=="per_unit" else r["rate"], axis=1)
    return df


def prep_proc(df):
    if df.empty: return df
    dt = pd.to_datetime(df["purchase_date"], errors="coerce")
    df["month_sort"] = dt.dt.strftime("%Y-%m")
    df["month"]      = dt.dt.strftime("%b %Y")
    df["spend"] = df.apply(
        lambda r: r["quantity"]*r["unit_cost"] if r["price_type"]=="per_unit" else r["unit_cost"], axis=1)
    return df


def prep_prod(df):
    if df.empty: return df
    dt = pd.to_datetime(df["date"], errors="coerce")
    df["month_sort"] = dt.dt.strftime("%Y-%m")
    df["month"]      = dt.dt.strftime("%b %Y")
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
                   curr_color="#3498db", prev_color="#5d6d7e", height=300, prefix="₹"):
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
                    xaxis=dict(gridcolor="#333", type="category", categoryorder="array",
                               categoryarray=all_months),
                    yaxis=dict(gridcolor="#333"),
                    legend=dict(orientation="h", y=-0.25), **PLOT)
    return f


def comparison_line(curr_df, prev_df, val_col, title,
                    curr_color="#3498db", prev_color="#5d6d7e", height=280, count=False):
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
                    xaxis=dict(gridcolor="#333", type="category", categoryorder="array",
                               categoryarray=all_months),
                    yaxis=dict(gridcolor="#333"),
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
        return f"<td style='padding:4px 14px;color:#888'>{label}: —</td>"
    p = (curr-prev)/prev*100
    col = "#2ecc71" if p >= 0 else "#e74c3c"
    arr = "▲" if p >= 0 else "▼"
    return (f"<td style='padding:4px 14px;border-radius:4px;background:#1a1a1a'>"
            f"<span style='color:#aaa'>{label}</span> "
            f"<b style='color:{col}'>{arr} {abs(p):.1f}%</b></td>")


def hbar(x, y, title, color="#e67e22", height=280):
    f = go.Figure(go.Bar(x=x, y=y, orientation="h", marker_color=color,
                         hovertemplate="<b>%{y}</b><br>₹%{x:,.0f}<extra></extra>"))
    f.update_layout(title=title, height=height,
                    xaxis=dict(gridcolor="#333"),
                    yaxis=dict(autorange="reversed", gridcolor="#333"), **PLOT)
    return f


# ══════════════════════════════════════════════════════════════════════════════
# HEADER — period selector only (tabs handle company)
# ══════════════════════════════════════════════════════════════════════════════
today = date.today()
st.title("Reclaimr")
st.caption(f"Today — {today.strftime('%A, %d %B %Y')}")

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
            "Combined Order Count by Month", count=True, curr_color="#9b59b6"), use_container_width=True)

    # Revenue split pie
    if not ord_c.empty:
        rev_co = ord_c.groupby("company")["revenue"].sum().reset_index()
        if rev_co["revenue"].sum() > 0:
            pie = go.Figure(go.Pie(
                labels=rev_co["company"].tolist(), values=rev_co["revenue"].tolist(),
                hole=0.5, marker_colors=["#3498db","#e67e22"],
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

    if overdue.empty and stagnant.empty and not spikes:
        st.success("✅ All orders current, no stagnant jobs, no procurement cost spikes.")
    else:
        if not overdue.empty:
            st.error(f"🔴 **{len(overdue)} {'order' if len(overdue)==1 else 'orders'} past dispatch date** — these need immediate attention")
            st.dataframe(overdue, use_container_width=True, hide_index=True)
        if not stagnant.empty:
            st.warning(f"🟡 **{len(stagnant)} {'order' if len(stagnant)==1 else 'orders'} sitting in 'received' for 7+ days** — check whether production has started")
            st.dataframe(stagnant, use_container_width=True, hide_index=True)
        if spikes:
            st.warning(f"💸 **{len(spikes)} {'material' if len(spikes)==1 else 'materials'} with price increases above 5%** — review vendor quotes before the next purchase")
            st.dataframe(pd.DataFrame(spikes), use_container_width=True, hide_index=True)

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
            "Order Count by Month", curr_color="#9b59b6", count=True), use_container_width=True)

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
            "Production kg by Month", curr_color="#2ecc71", prev_color="#1a5e35",
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
        colors = ["#3498db","#2ecc71","#e67e22","#9b59b6","#e74c3c","#1abc9c"]
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
                            xaxis=dict(gridcolor="#333", type="category",
                                       categoryorder="array", categoryarray=sorted_months),
                            yaxis=dict(gridcolor="#333"),
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
            "Revenue by Month (₹)", curr_color="#e67e22", prev_color="#784212"),
            use_container_width=True)
    with ec2:
        st.plotly_chart(comparison_line(eo, _ep, None,
            "Order Count by Month", curr_color="#f39c12", count=True),
            use_container_width=True)

    if eo.empty:
        st.info("No Elastohorse orders in the selected period. Add one from the Orders page.")
