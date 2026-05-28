import streamlit as st
import plotly.graph_objects as go
from datetime import date, timedelta
import math

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
_RWOX_FIXED_M      = 3_760_314  / 12
_ELASTO_FIXED_M    = 1_647_866  / 12
_RWOX_MAT_PCT      = 10_601_525 / 15_451_424
_ELASTO_COGS_PCT   = 11_028_707 / 14_972_732
_RWOX_NET_MARGIN   = 346_111    / 15_451_424
_ELASTO_NET_MARGIN = 855_058    / 14_972_732
_FALLBACK_PROD_KG     = 8_500.0
_FALLBACK_PRICE       = 150.0
_FALLBACK_RWOX_CASH   = 478_342.0
_FALLBACK_ELASTO_CASH = 670_249.0

_MAT_SHARE = {
    "Purple material": 0.60,
    "Wax":             0.25,
    "MC":              0.10,
    "Other variable":  0.05,
}
_BASE_MAT_MONTHLY   = 10_601_525 / 12
_BASE_ELASTO_COGS_M = 11_028_707 / 12

_PLOT   = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
               font_color="#ccc", margin=dict(t=45, b=30, l=10, r=10))
_GREEN  = "#2ecc71"
_YELLOW = "#f39c12"
_RED    = "#e74c3c"
_BLUE   = "#3498db"
_PURPLE = "#9b59b6"


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def _inr(val: float) -> str:
    if val >= 1_00_00_000: return f"₹{val/1_00_00_000:.2f} Cr"
    if val >= 1_00_000:    return f"₹{val/1_00_000:.2f} L"
    if val >= 1_000:       return f"₹{val/1_000:.1f} K"
    return f"₹{val:,.0f}"


def _color(val: float, good_above: float = 0) -> str:
    return _GREEN if val > good_above else (_YELLOW if val >= 0 else _RED)


def _delta_badge(new: float, old: float, prefix: str = "₹") -> str:
    if old == 0:
        return ""
    diff = new - old
    pct  = diff / old * 100
    clr  = _GREEN if diff >= 0 else _RED
    arr  = "▲" if diff >= 0 else "▼"
    val  = f"{prefix}{abs(diff):,.0f}" if prefix else f"{abs(diff):.1f}%"
    return f"<span style='color:{clr};font-size:13px'>{arr} {val} ({pct:+.1f}%)</span>"


def _kpi(col, label: str, value: str, delta_html: str = "", border_color: str = _BLUE) -> None:
    col.markdown(
        f"<div style='background:#1a1a1a;border-radius:8px;padding:14px 16px;"
        f"border-top:3px solid {border_color};margin-bottom:6px;min-height:90px'>"
        f"<p style='color:#888;font-size:11px;text-transform:uppercase;margin:0'>{label}</p>"
        f"<p style='color:#fff;font-size:18px;font-weight:700;margin:4px 0'>{value}</p>"
        f"<div style='min-height:18px'>{delta_html}</div></div>",
        unsafe_allow_html=True,
    )


def _ensure_tables(conn) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS forecast_targets (
            id                          INTEGER PRIMARY KEY AUTOINCREMENT,
            rwox_monthly_revenue        REAL DEFAULT 0,
            elastohorse_monthly_revenue REAL DEFAULT 0,
            combined_profit_margin      REAL DEFAULT 10,
            monthly_production_kg       REAL DEFAULT 0,
            updated_at                  TEXT DEFAULT (datetime('now','localtime'))
        );
    """)
    conn.commit()


@st.cache_data(ttl=60)
def _load_actuals(_conn) -> dict:
    today  = date.today()
    this_m = today.strftime("%Y-%m")
    t90    = (today - timedelta(days=90)).isoformat()
    t30    = (today - timedelta(days=30)).isoformat()

    ids = {r["name"]: r["id"] for r in
           _conn.execute("SELECT name, id FROM companies").fetchall()}
    rid = ids.get("Rwox")
    eid = ids.get("Elastohorse")

    def _month_rev(cid):
        return _conn.execute(
            "SELECT COALESCE(SUM(CASE WHEN rate_type='per_unit' THEN quantity*rate "
            "ELSE rate END),0) FROM orders "
            "WHERE company_id=? AND strftime('%Y-%m',created_at)=?",
            (cid, this_m)).fetchone()[0]

    def _pending_rev(cid):
        return _conn.execute(
            "SELECT COALESCE(SUM(CASE WHEN rate_type='per_unit' THEN quantity*rate "
            "ELSE rate END),0) FROM orders "
            "WHERE company_id=? AND status IN ('received','in_production','ready')",
            (cid,)).fetchone()[0]

    def _pending_qty(cid):
        return _conn.execute(
            "SELECT COALESCE(SUM(quantity),0) FROM orders "
            "WHERE company_id=? AND status IN ('received','in_production')",
            (cid,)).fetchone()[0]

    pr = _conn.execute(
        "SELECT COALESCE(AVG(m),0) FROM ("
        "  SELECT SUM(output_kg) AS m FROM production_logs "
        "  WHERE company_id=? AND date>=? GROUP BY strftime('%Y-%m',date)"
        ")", (rid, t90)).fetchone()
    avg_prod = pr[0] if pr and pr[0] else _FALLBACK_PROD_KG

    ap = _conn.execute(
        "SELECT COALESCE(AVG(rate),0) FROM ("
        "  SELECT rate FROM orders WHERE company_id=? AND rate_type='per_unit' AND rate>0 "
        "  ORDER BY created_at DESC LIMIT 30"
        ")", (rid,)).fetchone()
    avg_price = ap[0] if ap and ap[0] > 0 else _FALLBACK_PRICE

    def _cash(cid, fallback, mu_col):
        mu = _conn.execute(
            f"SELECT {mu_col} FROM monthly_updates ORDER BY month DESC LIMIT 1"
        ).fetchone()
        if mu and mu[0]:
            return float(mu[0])
        snap = _conn.execute(
            "SELECT cash_balance FROM financial_snapshots WHERE company_id=? "
            "ORDER BY snapshot_date DESC LIMIT 1", (cid,)).fetchone()
        return float(snap[0]) if snap and snap[0] else fallback

    pc = _conn.execute(
        "SELECT COALESCE(SUM(CASE WHEN price_type='per_unit' "
        "THEN quantity*unit_cost ELSE unit_cost END),0) "
        "FROM procurement WHERE purchase_date>=?", (t30,)).fetchone()

    mat = {}
    for row in _conn.execute(
        "SELECT LOWER(item) AS itm, AVG(unit_cost) AS c FROM procurement "
        "WHERE company_id=? AND price_type='per_unit' GROUP BY LOWER(item)",
        (rid,)).fetchall():
        mat[row["itm"]] = row["c"]

    return {
        "rwox_rev_m":       _month_rev(rid),
        "elasto_rev_m":     _month_rev(eid),
        "rwox_pending":     _pending_rev(rid),
        "elasto_pending":   _pending_rev(eid),
        "rwox_pending_qty": _pending_qty(rid),
        "avg_prod_kg":      avg_prod,
        "avg_price":        avg_price,
        "rwox_cash":        _cash(rid, _FALLBACK_RWOX_CASH,   "rwox_cash"),
        "elasto_cash":      _cash(eid, _FALLBACK_ELASTO_CASH, "elastohorse_cash"),
        "proc_last_30d":    pc[0] if pc else 0.0,
        "mat_costs":        mat,
    }


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1 — SET YOUR TARGETS
# ─────────────────────────────────────────────────────────────────────────────
def _tab_targets(conn, actuals: dict, view: str, kp: str) -> None:
    st.subheader("Set Your Targets")
    st.caption("Define what success looks like each month. Progress bars update automatically as orders come in.")

    saved = conn.execute(
        "SELECT * FROM forecast_targets ORDER BY id DESC LIMIT 1"
    ).fetchone()

    with st.form(f"{kp}_targets_form"):
        if view in ("both", "rwox"):
            st.markdown("**Rwox monthly revenue target**")
            r_tgt = st.number_input(
                "Rwox (₹)", min_value=0.0, step=50_000.0, format="%.0f",
                value=float(saved["rwox_monthly_revenue"] if saved else 15_451_424 / 12),
                key=f"{kp}_tgt_r")
        else:
            r_tgt = float(saved["rwox_monthly_revenue"] if saved else 15_451_424 / 12)

        if view in ("both", "elasto"):
            st.markdown("**Elastohorse monthly revenue target**")
            e_tgt = st.number_input(
                "Elastohorse (₹)", min_value=0.0, step=50_000.0, format="%.0f",
                value=float(saved["elastohorse_monthly_revenue"] if saved else 14_972_732 / 12),
                key=f"{kp}_tgt_e")
        else:
            e_tgt = float(saved["elastohorse_monthly_revenue"] if saved else 14_972_732 / 12)

        if view == "both":
            margin_tgt = st.slider(
                "Combined net profit margin target (%)",
                min_value=1, max_value=30,
                value=int(saved["combined_profit_margin"] if saved else 8),
                key=f"{kp}_tgt_m")
        else:
            margin_tgt = int(saved["combined_profit_margin"] if saved else 8)

        if view in ("both", "rwox"):
            prod_tgt = st.number_input(
                "Monthly production target (kg)", min_value=0.0, step=500.0, format="%.0f",
                value=float(saved["monthly_production_kg"] if saved else actuals["avg_prod_kg"]),
                key=f"{kp}_tgt_p")
        else:
            prod_tgt = float(saved["monthly_production_kg"] if saved else actuals["avg_prod_kg"])

        save_ok = st.form_submit_button("Save Targets", type="primary")

    if save_ok:
        conn.execute(
            "INSERT INTO forecast_targets (rwox_monthly_revenue, "
            "elastohorse_monthly_revenue, combined_profit_margin, monthly_production_kg) "
            "VALUES (?,?,?,?)",
            (r_tgt, e_tgt, margin_tgt, prod_tgt))
        conn.commit()
        st.success("Targets saved.")
        st.rerun()

    saved = conn.execute(
        "SELECT * FROM forecast_targets ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if not saved:
        st.info("No targets saved yet — set and save your targets above.")
        return

    st.divider()
    st.markdown("#### Progress This Month")

    def _bar(label, actual, target, unit="₹"):
        if target <= 0:
            return
        pct = min(actual / target * 100, 100)
        clr = _GREEN if pct >= 80 else (_YELLOW if pct >= 50 else _RED)
        em  = "✅" if pct >= 80 else ("⚠️" if pct >= 50 else "🔴")
        a_s = _inr(actual) if unit == "₹" else f"{actual:,.0f} kg"
        t_s = _inr(target) if unit == "₹" else f"{target:,.0f} kg"
        st.markdown(
            f"<div style='margin-bottom:14px'>"
            f"<div style='display:flex;justify-content:space-between;margin-bottom:4px'>"
            f"<span style='color:#ccc'>{em} {label}</span>"
            f"<span style='color:{clr}'><b>{a_s}</b> &nbsp;/&nbsp; {t_s} &nbsp;·&nbsp; {pct:.0f}%</span>"
            f"</div>"
            f"<div style='background:#2a2a2a;border-radius:4px;height:9px'>"
            f"<div style='background:{clr};border-radius:4px;height:9px;width:{pct:.1f}%'></div>"
            f"</div></div>",
            unsafe_allow_html=True,
        )

    if view in ("both", "rwox"):
        _bar("Rwox Revenue",      actuals["rwox_rev_m"],  saved["rwox_monthly_revenue"])
        _bar("Production Output", actuals["avg_prod_kg"], saved["monthly_production_kg"], "kg")
    if view in ("both", "elasto"):
        _bar("Elastohorse Revenue", actuals["elasto_rev_m"], saved["elastohorse_monthly_revenue"])
    if view == "both":
        total_rev = actuals["rwox_rev_m"] + actuals["elasto_rev_m"]
        if total_rev > 0:
            est_profit = (actuals["rwox_rev_m"] * _RWOX_NET_MARGIN +
                          actuals["elasto_rev_m"] * _ELASTO_NET_MARGIN)
            est_margin = est_profit / total_rev * 100
            _bar("Net Profit Margin", est_margin, float(saved["combined_profit_margin"]), "%")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2 — PRICE SENSITIVITY
# ─────────────────────────────────────────────────────────────────────────────
def _pricing_rwox(actuals: dict, kp: str) -> None:
    base_price  = actuals["avg_price"]
    base_vol    = actuals["avg_prod_kg"]
    base_mat_kg = _BASE_MAT_MONTHLY / base_vol if base_vol > 0 else 104.0

    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown("**Price**")
        cur_price = st.number_input("Current avg selling price per kg (₹)",
            min_value=1.0, value=float(round(base_price, 2)),
            step=1.0, format="%.2f", key=f"{kp}_pr_price")
        price_chg = st.slider("Price change", min_value=-20, max_value=30, value=0,
            format="%d%%", key=f"{kp}_pr_pchg")
    with col_r:
        st.markdown("**Volume**")
        cur_vol = st.number_input("Current monthly volume (kg)",
            min_value=0.0, value=float(round(base_vol, 0)),
            step=100.0, format="%.0f", key=f"{kp}_pr_vol")
        vol_chg = st.slider("Volume change", min_value=-20, max_value=30, value=0,
            format="%d%%", key=f"{kp}_pr_vchg")

    new_price = cur_price * (1 + price_chg / 100)
    new_vol   = cur_vol   * (1 + vol_chg   / 100)
    base_rev  = cur_price * cur_vol
    new_rev   = new_price * new_vol
    base_gp   = base_rev - base_mat_kg * cur_vol
    base_np   = base_rev * _RWOX_NET_MARGIN
    new_gp    = new_rev  - base_mat_kg * new_vol
    new_np    = new_gp   - _RWOX_FIXED_M
    breakeven_vol = _RWOX_FIXED_M / (new_price - base_mat_kg) if (new_price - base_mat_kg) > 0 else float("inf")

    st.divider()
    st.markdown("#### Projected Monthly Results")
    k1, k2, k3, k4 = st.columns(4)
    _kpi(k1, "New Revenue",      _inr(new_rev),  _delta_badge(new_rev, base_rev),  _color(new_rev - base_rev))
    _kpi(k2, "New Gross Profit", _inr(new_gp),   _delta_badge(new_gp, base_gp),   _color(new_gp - base_gp))
    _kpi(k3, "New Net Profit",   _inr(new_np),   _delta_badge(new_np, base_np),   _color(new_np))
    gp_pct = new_gp / new_rev * 100 if new_rev > 0 else 0
    _kpi(k4, "Gross Margin",     f"{gp_pct:.1f}%", "", _color(gp_pct - 10))

    if not math.isinf(breakeven_vol):
        be_col, _ = st.columns([2, 3])
        with be_col:
            be_clr = _GREEN if new_vol >= breakeven_vol else _RED
            st.markdown(
                f"<div style='background:#1a1a1a;border-radius:8px;padding:12px 16px;"
                f"border-left:4px solid {be_clr};margin-top:8px'>"
                f"<span style='color:#888'>Break-even at {_inr(new_price)}/kg:</span> "
                f"<b style='color:{be_clr}'>{breakeven_vol:,.0f} kg/month</b>"
                f"{'&nbsp; ✅ above volume' if new_vol >= breakeven_vol else '&nbsp; 🔴 below break-even'}"
                f"</div>", unsafe_allow_html=True)
    else:
        st.error("New price is below material cost — every unit sold loses money.")

    pct_range = list(range(-20, 31, 5))
    rev_line  = [cur_price * (1 + p/100) * new_vol for p in pct_range]
    np_line   = [r - base_mat_kg * new_vol - _RWOX_FIXED_M for r in rev_line]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=pct_range, y=rev_line, name="Revenue",
        mode="lines", line=dict(color=_BLUE, width=2),
        hovertemplate="Price %{x:+d}%<br>Revenue ₹%{y:,.0f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=pct_range, y=np_line, name="Net Profit",
        mode="lines", line=dict(color=_GREEN, width=2, dash="dot"),
        hovertemplate="Price %{x:+d}%<br>Net Profit ₹%{y:,.0f}<extra></extra>"))
    fig.add_vline(x=price_chg, line=dict(color=_YELLOW, dash="dash", width=1))
    fig.add_hline(y=0, line=dict(color=_RED, dash="dot", width=1))
    fig.update_layout(title="Revenue & Profit Sensitivity to Price Change",
        height=300, xaxis=dict(title="Price change (%)", gridcolor="#333"),
        yaxis=dict(gridcolor="#333", tickprefix="₹"),
        legend=dict(orientation="h", y=-0.3), **_PLOT)
    st.plotly_chart(fig, use_container_width=True, key=f"{kp}_price_chart")


def _pricing_elasto(actuals: dict, kp: str) -> None:
    base_rev_m = actuals["elasto_rev_m"] or (14_972_732 / 12)

    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown("**Revenue**")
        cur_rev = st.number_input("Current monthly revenue (₹)",
            min_value=1.0, value=float(round(base_rev_m, -3)),
            step=50_000.0, format="%.0f", key=f"{kp}_pr_rev")
        rev_chg = st.slider("Revenue change", min_value=-20, max_value=30, value=0,
            format="%d%%", key=f"{kp}_pr_rchg")
    with col_r:
        st.markdown("**Gross Margin**")
        cur_gm = st.slider("Gross margin % (currently ~26%)",
            min_value=5, max_value=50, value=26, key=f"{kp}_pr_gm")
        st.caption("Gross margin = (Revenue − Stock cost) / Revenue")

    new_rev       = cur_rev * (1 + rev_chg / 100)
    gross_profit  = new_rev * (cur_gm / 100)
    stock_cost    = new_rev - gross_profit
    net_profit    = gross_profit - _ELASTO_FIXED_M
    base_gp       = cur_rev * 0.263
    base_np       = cur_rev * _ELASTO_NET_MARGIN
    breakeven_rev = _ELASTO_FIXED_M / (cur_gm / 100) if cur_gm > 0 else float("inf")

    st.divider()
    st.markdown("#### Projected Monthly Results")
    k1, k2, k3, k4 = st.columns(4)
    _kpi(k1, "Revenue",      _inr(new_rev),    _delta_badge(new_rev, cur_rev),        _color(new_rev - cur_rev))
    _kpi(k2, "Gross Profit", _inr(gross_profit), _delta_badge(gross_profit, base_gp), _color(gross_profit))
    _kpi(k3, "Net Profit",   _inr(net_profit), _delta_badge(net_profit, base_np),    _color(net_profit))
    _kpi(k4, "Stock Cost",   _inr(stock_cost), "", _YELLOW)

    if not math.isinf(breakeven_rev):
        be_col, _ = st.columns([2, 3])
        with be_col:
            be_clr = _GREEN if new_rev >= breakeven_rev else _RED
            st.markdown(
                f"<div style='background:#1a1a1a;border-radius:8px;padding:12px 16px;"
                f"border-left:4px solid {be_clr};margin-top:8px'>"
                f"<span style='color:#888'>Break-even at {cur_gm}% margin:</span> "
                f"<b style='color:{be_clr}'>{_inr(breakeven_rev)}/month</b>"
                f"{'&nbsp; ✅ above revenue' if new_rev >= breakeven_rev else '&nbsp; 🔴 below break-even'}"
                f"</div>", unsafe_allow_html=True)

    gm_range = list(range(5, 51, 5))
    np_line  = [cur_rev * (g/100) - _ELASTO_FIXED_M for g in gm_range]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=gm_range, y=np_line, name="Net Profit",
        mode="lines+markers", line=dict(color=_PURPLE, width=2),
        hovertemplate="Margin %{x}%<br>Net Profit ₹%{y:,.0f}<extra></extra>"))
    fig.add_vline(x=cur_gm, line=dict(color=_YELLOW, dash="dash", width=1))
    fig.add_hline(y=0, line=dict(color=_RED, dash="dot", width=1))
    fig.update_layout(title="Net Profit Sensitivity to Gross Margin",
        height=300, xaxis=dict(title="Gross margin (%)", gridcolor="#333"),
        yaxis=dict(gridcolor="#333", tickprefix="₹"),
        legend=dict(orientation="h", y=-0.3), **_PLOT)
    st.plotly_chart(fig, use_container_width=True, key=f"{kp}_price_chart")


def _tab_pricing(actuals: dict, view: str, kp: str) -> None:
    st.subheader("What If I Change My Price?")
    if view == "rwox":
        st.caption("Move the sliders and watch every number update instantly. Pre-filled from your actual order and production data.")
        _pricing_rwox(actuals, kp)
    elif view == "elasto":
        st.caption("Adjust your gross margin and revenue to see how profit changes.")
        _pricing_elasto(actuals, kp)
    else:
        st.caption("Explore pricing scenarios for both companies.")
        pt = st.tabs(["🏭 Rwox", "🏪 Elastohorse"])
        with pt[0]:
            _pricing_rwox(actuals, f"{kp}r")
        with pt[1]:
            _pricing_elasto(actuals, f"{kp}e")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3 — COST SENSITIVITY
# ─────────────────────────────────────────────────────────────────────────────
def _materials_rwox(actuals: dict, kp: str) -> None:
    monthly_vol = actuals["avg_prod_kg"]
    sc1, sc2 = st.columns(2)
    with sc1:
        purple_chg = st.slider("Purple material cost change",
            min_value=-20, max_value=30, value=0, format="%d%%", key=f"{kp}_mc_pur")
        wax_chg = st.slider("Wax cost change",
            min_value=-20, max_value=30, value=0, format="%d%%", key=f"{kp}_mc_wax")
    with sc2:
        mc_chg = st.slider("MC cost change",
            min_value=-20, max_value=30, value=0, format="%d%%", key=f"{kp}_mc_mc")
        other_chg = st.slider("Other variable costs change",
            min_value=-20, max_value=30, value=0, format="%d%%", key=f"{kp}_mc_oth")

    changes = {"Purple material": purple_chg, "Wax": wax_chg,
               "MC": mc_chg, "Other variable": other_chg}
    base_mat_total = _BASE_MAT_MONTHLY
    new_mat_total  = sum(base_mat_total * s * (1 + changes[n] / 100) for n, s in _MAT_SHARE.items())
    base_cpk = base_mat_total / monthly_vol if monthly_vol > 0 else 104.0
    new_cpk  = new_mat_total  / monthly_vol if monthly_vol > 0 else base_cpk
    base_price = actuals["avg_price"]
    base_gp    = base_price - base_cpk
    new_gp     = base_price - new_cpk
    base_gm    = base_gp / base_price * 100 if base_price > 0 else 0
    new_gm     = new_gp  / base_price * 100 if base_price > 0 else 0
    base_np_m  = base_price * monthly_vol - base_mat_total - _RWOX_FIXED_M
    new_np_m   = base_price * monthly_vol - new_mat_total  - _RWOX_FIXED_M
    breakeven_price = new_cpk + _RWOX_FIXED_M / monthly_vol if monthly_vol > 0 else new_cpk

    st.divider()
    k1, k2, k3, k4 = st.columns(4)
    _kpi(k1, "Cost per kg (new)", f"₹{new_cpk:.2f}",
         _delta_badge(new_cpk, base_cpk, "₹"), _color(base_cpk - new_cpk))
    _kpi(k2, "Gross margin per kg", f"₹{new_gp:.2f}  ({new_gm:.1f}%)",
         _delta_badge(new_gm, base_gm, ""), _color(new_gp))
    _kpi(k3, "Monthly profit impact", _inr(new_np_m),
         _delta_badge(new_np_m, base_np_m), _color(new_np_m))
    _kpi(k4, "Break-even price", f"₹{breakeven_price:.2f}/kg",
         "", _color(base_price - breakeven_price))

    st.divider()
    st.markdown("**Cost breakdown by material (monthly)**")
    rows_html = ""
    for name, share in _MAT_SHARE.items():
        base_c = base_mat_total * share
        new_c  = base_c * (1 + changes[name] / 100)
        diff   = new_c - base_c
        clr    = _GREEN if diff <= 0 else _RED
        arrow  = "▲" if diff > 0 else ("▼" if diff < 0 else "—")
        rows_html += (
            f"<tr><td style='padding:6px 12px;color:#ccc'>{name}</td>"
            f"<td style='padding:6px 12px;color:#888'>{_inr(base_c)}</td>"
            f"<td style='padding:6px 12px;color:{clr}'><b>{_inr(new_c)}</b></td>"
            f"<td style='padding:6px 12px;color:{clr}'>{arrow} {_inr(abs(diff))} ({changes[name]:+d}%)</td>"
            f"</tr>")
    st.markdown(
        "<table style='width:100%;border-collapse:collapse;font-size:14px'>"
        "<thead><tr style='background:#222'>"
        "<th style='padding:8px 12px;text-align:left;color:#888'>Material</th>"
        "<th style='padding:8px 12px;text-align:left;color:#888'>Current / month</th>"
        "<th style='padding:8px 12px;text-align:left;color:#888'>New / month</th>"
        "<th style='padding:8px 12px;text-align:left;color:#888'>Change</th>"
        f"</tr></thead><tbody>{rows_html}</tbody></table>",
        unsafe_allow_html=True)

    mat_names = list(_MAT_SHARE.keys())
    impacts   = [abs(base_mat_total * _MAT_SHARE[n] * changes[n] / 100) for n in mat_names]
    colors    = [_RED if changes[n] > 0 else _GREEN for n in mat_names]
    fig = go.Figure(go.Bar(x=impacts, y=mat_names, orientation="h", marker_color=colors,
        hovertemplate="<b>%{y}</b><br>₹%{x:,.0f}/month<extra></extra>"))
    fig.update_layout(title="Monthly Cost Impact by Material",
        height=240, xaxis=dict(gridcolor="#333", tickprefix="₹"),
        yaxis=dict(gridcolor="#333"), **_PLOT)
    st.plotly_chart(fig, use_container_width=True, key=f"{kp}_mat_chart")


def _materials_elasto(actuals: dict, kp: str) -> None:
    base_rev_m  = actuals["elasto_rev_m"] or (14_972_732 / 12)
    base_cogs_m = _BASE_ELASTO_COGS_M
    cogs_chg = st.slider("Stock purchase cost change",
        min_value=-20, max_value=30, value=0, format="%d%%", key=f"{kp}_mc_cogs")

    new_cogs_m  = base_cogs_m * (1 + cogs_chg / 100)
    base_gp_m   = base_rev_m - base_cogs_m
    new_gp_m    = base_rev_m - new_cogs_m
    base_np_m   = base_gp_m  - _ELASTO_FIXED_M
    new_np_m    = new_gp_m   - _ELASTO_FIXED_M
    base_gm_pct = base_gp_m  / base_rev_m * 100 if base_rev_m > 0 else 0
    new_gm_pct  = new_gp_m   / base_rev_m * 100 if base_rev_m > 0 else 0

    st.divider()
    k1, k2, k3, k4 = st.columns(4)
    _kpi(k1, "Stock cost / month",  _inr(new_cogs_m),
         _delta_badge(new_cogs_m, base_cogs_m), _color(base_cogs_m - new_cogs_m))
    _kpi(k2, "Gross profit",        _inr(new_gp_m),
         _delta_badge(new_gp_m, base_gp_m), _color(new_gp_m))
    _kpi(k3, "Gross margin %",      f"{new_gm_pct:.1f}%",
         _delta_badge(new_gm_pct, base_gm_pct, ""), _color(new_gm_pct - 10))
    _kpi(k4, "Net profit",          _inr(new_np_m),
         _delta_badge(new_np_m, base_np_m), _color(new_np_m))

    cogs_range = list(range(-20, 31, 5))
    np_line    = [base_rev_m - base_cogs_m*(1+c/100) - _ELASTO_FIXED_M for c in cogs_range]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=cogs_range, y=np_line, name="Net Profit",
        mode="lines+markers", line=dict(color=_PURPLE, width=2),
        hovertemplate="Cost %{x:+d}%<br>Net Profit ₹%{y:,.0f}<extra></extra>"))
    fig.add_vline(x=cogs_chg, line=dict(color=_YELLOW, dash="dash", width=1))
    fig.add_hline(y=0, line=dict(color=_RED, dash="dot", width=1))
    fig.update_layout(title="Net Profit vs Stock Cost Change",
        height=280, xaxis=dict(title="Stock cost change (%)", gridcolor="#333"),
        yaxis=dict(gridcolor="#333", tickprefix="₹"), **_PLOT)
    st.plotly_chart(fig, use_container_width=True, key=f"{kp}_mat_chart")


def _tab_materials(actuals: dict, view: str, kp: str) -> None:
    if view == "rwox":
        st.subheader("What If Raw Material Costs Change?")
        st.caption("Adjust each input cost and see the impact on margin and break-even price.")
        st.markdown("**Cost change sliders** — drag left for cheaper, right for more expensive")
        _materials_rwox(actuals, kp)
    elif view == "elasto":
        st.subheader("What If Stock Costs Change?")
        st.caption("Model how changes in stock purchase prices affect your gross margin and profitability.")
        st.markdown("**Drag left for cheaper, right for more expensive**")
        _materials_elasto(actuals, kp)
    else:
        st.subheader("Cost Sensitivity")
        st.caption("Adjust costs for both companies and see the impact.")
        mt = st.tabs(["🏭 Rwox — Raw Materials", "🏪 Elastohorse — Stock Cost"])
        with mt[0]:
            st.markdown("**Drag left for cheaper, right for more expensive**")
            _materials_rwox(actuals, f"{kp}r")
        with mt[1]:
            st.markdown("**Drag left for cheaper, right for more expensive**")
            _materials_elasto(actuals, f"{kp}e")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4 — ORDER FEASIBILITY
# ─────────────────────────────────────────────────────────────────────────────
def _order_check_rwox(conn, actuals: dict, kp: str) -> None:
    monthly_cap = actuals["avg_prod_kg"]
    committed   = actuals["rwox_pending_qty"]
    available   = max(monthly_cap - committed, 0.0)
    daily_cap   = monthly_cap / 22
    base_cpk    = _BASE_MAT_MONTHLY / monthly_cap if monthly_cap > 0 else 104.0
    avg_margin  = _RWOX_NET_MARGIN * 100

    col_l, col_r = st.columns(2)
    with col_l:
        order_qty  = st.number_input("Order quantity (kg)", min_value=0.0,
            step=100.0, format="%.0f", value=1000.0, key=f"{kp}_oc_qty")
        sell_price = st.number_input("Selling price per kg (₹)", min_value=0.0,
            step=1.0, format="%.2f",
            value=float(round(actuals["avg_price"], 2)), key=f"{kp}_oc_price")
    with col_r:
        delivery_dt = st.date_input("Promised delivery date",
            value=date.today() + timedelta(days=30), key=f"{kp}_oc_date",
            min_value=date.today())
        st.markdown(
            f"<div style='background:#1a1a1a;border-radius:8px;padding:12px;margin-top:8px'>"
            f"<p style='color:#888;font-size:12px;margin:0'>Current capacity</p>"
            f"<p style='color:#fff;margin:4px 0'>{monthly_cap:,.0f} kg/month · {daily_cap:.0f} kg/day</p>"
            f"<p style='color:#888;font-size:12px;margin:0'>Already committed</p>"
            f"<p style='color:#fff;margin:4px 0'>{committed:,.0f} kg &rarr; "
            f"<b style='color:{_GREEN if available > 0 else _RED}'>{available:,.0f} kg available</b></p>"
            f"</div>", unsafe_allow_html=True)

    days_available   = (delivery_dt - date.today()).days
    prod_days_needed = order_qty / daily_cap if daily_cap > 0 else float("inf")
    can_do_normal    = available >= order_qty and prod_days_needed <= days_available
    extra_possible   = available + daily_cap * 0.5 * days_available
    can_do_with_shifts = extra_possible >= order_qty and not can_do_normal

    order_rev    = sell_price * order_qty
    order_mat    = base_cpk * order_qty
    order_gp     = order_rev - order_mat
    order_np     = order_gp - (prod_days_needed / 22) * _RWOX_FIXED_M
    order_gm_pct = order_gp / order_rev * 100 if order_rev > 0 else 0

    st.divider()
    st.markdown("#### Feasibility Assessment")

    if sell_price <= base_cpk:
        verdict, v_clr, icon = "Do Not Take", _RED, "🔴"
        reason = f"Price ₹{sell_price:.2f}/kg is below material cost of ₹{base_cpk:.2f}/kg — every kg sold loses money."
        action = "Increase the price or decline."
    elif can_do_normal:
        verdict, v_clr, icon = "Take It", _GREEN, "✅"
        reason = (f"You have {available:,.0f} kg available and {days_available} days to deliver. "
                  f"Production takes ~{prod_days_needed:.0f} working days.")
        action = "Confirm the order and log it in the system."
    elif can_do_with_shifts:
        verdict, v_clr, icon = "Can Do — With Extra Shifts", _YELLOW, "⚠️"
        reason = (f"Normal capacity falls short by {order_qty - available:,.0f} kg. "
                  f"With 50% overtime you could produce {extra_possible:,.0f} kg in time.")
        action = "Confirm only if you can arrange extra shifts. Factor in overtime wages."
    elif days_available < prod_days_needed:
        verdict, v_clr, icon = "Negotiate Deadline", _YELLOW, "⚠️"
        reason = (f"At {daily_cap:.0f} kg/day, this needs ~{prod_days_needed:.0f} working days "
                  f"but you have {days_available} days.")
        action = f"Ask for {int(prod_days_needed * 1.1) + 5} calendar days."
    else:
        verdict, v_clr, icon = "Capacity Constraint — Negotiate", _YELLOW, "⚠️"
        reason = (f"Available capacity ({available:,.0f} kg) is less than the order ({order_qty:,.0f} kg).")
        action = "Consider a partial order or push the delivery date."

    st.markdown(
        f"<div style='background:#1a1a1a;border-radius:10px;padding:20px 24px;"
        f"border-left:5px solid {v_clr};margin-bottom:16px'>"
        f"<h3 style='color:{v_clr};margin:0 0 8px 0'>{icon} {verdict}</h3>"
        f"<p style='color:#ccc;margin:0 0 8px 0'>{reason}</p>"
        f"<p style='color:{_YELLOW};margin:0'><b>Next step:</b> {action}</p>"
        f"</div>", unsafe_allow_html=True)

    k1, k2, k3, k4 = st.columns(4)
    _kpi(k1, "Order Revenue",   _inr(order_rev), "", _BLUE)
    _kpi(k2, "Gross Profit",    _inr(order_gp),  "", _color(order_gp))
    _kpi(k3, "Gross Margin",    f"{order_gm_pct:.1f}%",
         f"<span style='color:#888;font-size:12px'>Avg: {avg_margin:.1f}%</span>",
         _color(order_gm_pct - avg_margin))
    _kpi(k4, "Est. Net Profit", _inr(order_np),  "", _color(order_np))


def _order_check_elasto(actuals: dict, kp: str) -> None:
    elasto_cash = actuals["elasto_cash"]
    avg_margin  = _ELASTO_NET_MARGIN * 100

    col_l, col_r = st.columns(2)
    with col_l:
        order_val = st.number_input("Order value to customer (₹)", min_value=0.0,
            step=10_000.0, format="%.0f", value=100_000.0, key=f"{kp}_oc_val")
        buy_cost  = st.number_input("Stock you need to buy (₹)", min_value=0.0,
            step=10_000.0, format="%.0f",
            value=float(round(100_000.0 * _ELASTO_COGS_PCT, -3)), key=f"{kp}_oc_cost")
    with col_r:
        payment_dt = st.date_input("Customer payment date",
            value=date.today() + timedelta(days=30), key=f"{kp}_oc_date",
            min_value=date.today())
        st.markdown(
            f"<div style='background:#1a1a1a;border-radius:8px;padding:12px;margin-top:8px'>"
            f"<p style='color:#888;font-size:12px;margin:0'>Cash available now</p>"
            f"<p style='color:#fff;font-size:18px;font-weight:700;margin:4px 0'>{_inr(elasto_cash)}</p>"
            f"</div>", unsafe_allow_html=True)

    gross_profit   = order_val - buy_cost
    days_to_pay    = (payment_dt - date.today()).days
    net_profit     = gross_profit - _ELASTO_FIXED_M * (days_to_pay / 30)
    gm_pct         = gross_profit / order_val * 100 if order_val > 0 else 0
    cash_after_buy = elasto_cash - buy_cost

    st.divider()
    st.markdown("#### Feasibility Assessment")

    if buy_cost > elasto_cash:
        verdict, v_clr, icon = "Cash Shortfall", _RED, "🔴"
        shortfall = buy_cost - elasto_cash
        reason    = (f"Stock purchase of {_inr(buy_cost)} exceeds cash of {_inr(elasto_cash)}. "
                     f"Shortfall: {_inr(shortfall)}.")
        action    = "Arrange supplier credit or a short-term loan before accepting."
    elif gross_profit <= 0:
        verdict, v_clr, icon = "Do Not Take", _RED, "🔴"
        reason    = f"Stock cost {_inr(buy_cost)} exceeds sale value {_inr(order_val)} — this order loses money."
        action    = "Renegotiate the purchase price or sell at a higher rate."
    elif gm_pct < 10:
        verdict, v_clr, icon = "Low Margin — Proceed with Caution", _YELLOW, "⚠️"
        reason    = (f"Gross margin is only {gm_pct:.1f}% — well below the FY25 average of ~26%. "
                     f"After buying stock, {_inr(cash_after_buy)} remains.")
        action    = "Only if cash flow is comfortable and payment risk is low."
    else:
        verdict, v_clr, icon = "Take It", _GREEN, "✅"
        reason    = (f"Cash covers the stock purchase. {_inr(cash_after_buy)} remains after buying. "
                     f"Payment expected in {days_to_pay} days.")
        action    = "Confirm the order. Track the receivable."

    st.markdown(
        f"<div style='background:#1a1a1a;border-radius:10px;padding:20px 24px;"
        f"border-left:5px solid {v_clr};margin-bottom:16px'>"
        f"<h3 style='color:{v_clr};margin:0 0 8px 0'>{icon} {verdict}</h3>"
        f"<p style='color:#ccc;margin:0 0 8px 0'>{reason}</p>"
        f"<p style='color:{_YELLOW};margin:0'><b>Next step:</b> {action}</p>"
        f"</div>", unsafe_allow_html=True)

    k1, k2, k3, k4 = st.columns(4)
    _kpi(k1, "Order Value",    _inr(order_val),    "", _BLUE)
    _kpi(k2, "Gross Profit",   _inr(gross_profit), "", _color(gross_profit))
    _kpi(k3, "Gross Margin",   f"{gm_pct:.1f}%",
         f"<span style='color:#888;font-size:12px'>Avg: {avg_margin:.1f}%</span>",
         _color(gm_pct - avg_margin))
    _kpi(k4, "Cash After Buy", _inr(cash_after_buy), "", _color(cash_after_buy))


def _tab_order_check(conn, actuals: dict, view: str, kp: str) -> None:
    st.subheader("Can I Take This Order?")
    if view == "rwox":
        st.caption("Enter the order details for an instant go/no-go based on production capacity and cost structure.")
        _order_check_rwox(conn, actuals, kp)
    elif view == "elasto":
        st.caption("Check if cash covers the stock purchase and whether the margin is worthwhile.")
        _order_check_elasto(actuals, kp)
    else:
        company = st.radio("Check order for:", ["Rwox (manufacturing)", "Elastohorse (trading)"],
                           horizontal=True, key=f"{kp}_oc_co")
        st.divider()
        if "Rwox" in company:
            _order_check_rwox(conn, actuals, f"{kp}r")
        else:
            _order_check_elasto(actuals, f"{kp}e")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5 — CASH FORECAST
# ─────────────────────────────────────────────────────────────────────────────
def _cash_chart(cash_start, m1_net, recurring_net, color, title):
    weeks        = list(range(0, 14))
    cash_by_week = []
    for w in weeks:
        d = w * 7
        if d <= 30:   c = cash_start + m1_net * (d / 30)
        elif d <= 60: c = (cash_start + m1_net) + recurring_net * ((d - 30) / 30)
        else:         c = (cash_start + m1_net + recurring_net) + recurring_net * ((d - 60) / 30)
        cash_by_week.append(c)

    pt_colors = [_GREEN if v >= 0 else _RED for v in cash_by_week]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[f"Wk {w}" for w in weeks], y=cash_by_week,
        mode="lines+markers", line=dict(color=color, width=2.5),
        marker=dict(size=8, color=pt_colors, line=dict(color="#fff", width=1.5)),
        fill="tozeroy", fillcolor=f"rgba(52,152,219,0.08)",
        hovertemplate="<b>%{x}</b><br>₹%{y:,.0f}<extra></extra>"))
    if min(cash_by_week) < 0:
        fig.add_hline(y=0, line=dict(color=_RED, dash="dash", width=1.5),
                      annotation_text="Zero", annotation_font_color=_RED)
    fig.update_layout(title=title, height=300,
        xaxis=dict(gridcolor="#333"),
        yaxis=dict(gridcolor="#333", tickprefix="₹"), **_PLOT)
    return fig, cash_by_week


def _tab_cash(actuals: dict, view: str, kp: str) -> None:
    st.subheader("Cash Forecast — 30 / 60 / 90 Days")
    st.caption("Project your cash position forward. Pre-filled from actual data — adjust to model different scenarios.")

    if view == "both":
        ca, cb = st.columns(2)
        with ca:
            rwox_cash = st.number_input("Rwox — cash in bank now (₹)",
                min_value=0.0, value=float(actuals["rwox_cash"]),
                step=10_000.0, format="%.0f", key=f"{kp}_cf_rc")
        with cb:
            elasto_cash = st.number_input("Elastohorse — cash in bank now (₹)",
                min_value=0.0, value=float(actuals["elasto_cash"]),
                step=10_000.0, format="%.0f", key=f"{kp}_cf_ec")
        cash_now  = rwox_cash + elasto_cash
        fixed_base = _RWOX_FIXED_M + _ELASTO_FIXED_M
        cogs_base  = actuals["proc_last_30d"] or _BASE_MAT_MONTHLY
        pend_base  = actuals["rwox_pending"] + actuals["elasto_pending"]
        chart_title = "Cash Runway — Combined (Both Companies)"
        chart_color = _BLUE
    else:
        is_rwox    = (view == "rwox")
        cash_now   = actuals["rwox_cash"] if is_rwox else actuals["elasto_cash"]
        fixed_base = _RWOX_FIXED_M if is_rwox else _ELASTO_FIXED_M
        cogs_base  = _BASE_MAT_MONTHLY if is_rwox else _BASE_ELASTO_COGS_M
        pend_base  = actuals["rwox_pending"] if is_rwox else actuals["elasto_pending"]
        name       = "Rwox" if is_rwox else "Elastohorse"
        chart_title = f"Cash Runway — {name}"
        chart_color = _BLUE if is_rwox else _PURPLE
        cash_now = st.number_input(f"{name} — cash in bank now (₹)",
            min_value=0.0, value=float(cash_now),
            step=10_000.0, format="%.0f", key=f"{kp}_cf_cash")

    st.markdown("**Monthly cash flow inputs**")
    cc1, cc2, cc3 = st.columns(3)
    with cc1:
        collections = st.number_input("Expected collections / month (₹)", min_value=0.0,
            value=float(round(pend_base, -3)), step=25_000.0, format="%.0f",
            key=f"{kp}_cf_coll", help="Pre-filled from your pending orders")
    with cc2:
        fixed_out = st.number_input("Fixed expenses / month (₹)", min_value=0.0,
            value=float(round(fixed_base, -3)), step=10_000.0, format="%.0f",
            key=f"{kp}_cf_fix")
    with cc3:
        cogs_out = st.number_input("Stock / materials to buy / month (₹)", min_value=0.0,
            value=float(round(cogs_base, -3)), step=25_000.0, format="%.0f",
            key=f"{kp}_cf_cogs")

    st.markdown("**One-off payments this month** — one per line: Name, Amount")
    oneoff_text = st.text_area("E.g.  Loan repayment, 200000",
        height=75, key=f"{kp}_cf_oo", label_visibility="collapsed")
    oneoff_total = 0.0
    for line in oneoff_text.strip().splitlines():
        if "," in line:
            try:
                oneoff_total += float(line.rsplit(",", 1)[1].strip().replace(",", ""))
            except ValueError:
                pass

    recurring_net = collections - fixed_out - cogs_out
    m1_net  = recurring_net - oneoff_total
    cash_30 = cash_now + m1_net
    cash_60 = cash_30  + recurring_net
    cash_90 = cash_60  + recurring_net

    st.divider()
    km0, km1, km2, km3 = st.columns(4)
    for col, label, val in [(km0,"Now",cash_now),(km1,"Day 30",cash_30),(km2,"Day 60",cash_60),(km3,"Day 90",cash_90)]:
        clr      = _GREEN if val > 0 else _RED
        warn_vis = "visible" if val < 0 else "hidden"
        col.markdown(
            f"<div style='background:#1a1a1a;border-radius:8px;padding:14px;text-align:center;"
            f"border-top:3px solid {clr};min-height:100px'>"
            f"<p style='color:#888;font-size:11px;margin:0'>{label}</p>"
            f"<p style='color:{clr};font-size:19px;font-weight:700;margin:4px 0'>{_inr(val)}</p>"
            f"<span style='color:#e74c3c;font-size:11px;visibility:{warn_vis}'>⚠️ Negative cash</span>"
            f"</div>", unsafe_allow_html=True)

    fig, cash_by_week = _cash_chart(cash_now, m1_net, recurring_net, chart_color, chart_title)
    st.plotly_chart(fig, use_container_width=True, key=f"{kp}_cash_chart")

    if any(v < 0 for v in [cash_30, cash_60, cash_90]):
        first_neg = next((["Day 30","Day 60","Day 90"][i] for i,v in
                          enumerate([cash_30,cash_60,cash_90]) if v < 0), "")
        st.error(f"🔴 Cash turns negative by {first_neg}. "
                 f"Shortfall projected: {_inr(abs(min(cash_30, cash_60, cash_90)))}.")
    else:
        months_runway = cash_now / (fixed_out + cogs_out) if (fixed_out + cogs_out) > 0 else 99
        st.success(f"✅ Cash stays positive through day 90. Runway at current burn: {months_runway:.1f} months.")

    st.caption(f"Monthly recurring net: {_inr(recurring_net)} · One-off this month: {_inr(oneoff_total)}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6 — GROWTH SCENARIOS
# ─────────────────────────────────────────────────────────────────────────────
def _tab_growth(actuals: dict, view: str, kp: str) -> None:
    st.subheader("Growth Scenarios")
    st.caption("Compare three growth paths side by side. Projected from your actual current-month revenue.")

    if view == "rwox":
        base_m      = actuals["rwox_rev_m"]  or (15_451_424 / 12)
        net_margin  = _RWOX_NET_MARGIN
        annual_rev  = 15_451_424
        title       = "Projected Annual Results — Rwox"
        color_main  = _BLUE
        base_prod   = actuals["avg_prod_kg"] or _FALLBACK_PROD_KG

        def _extra(growth_pct):
            extra_kg = max(base_prod * (1 + growth_pct/100) - base_prod, 0)
            return (f"<p style='color:#888;font-size:12px;margin:0'>EXTRA PRODUCTION NEEDED</p>"
                    f"<p style='color:#ccc;font-size:14px;margin:2px 0 10px'>{extra_kg:,.0f} kg/month</p>")

    elif view == "elasto":
        base_m      = actuals["elasto_rev_m"] or (14_972_732 / 12)
        net_margin  = _ELASTO_NET_MARGIN
        annual_rev  = 14_972_732
        title       = "Projected Annual Results — Elastohorse"
        color_main  = _PURPLE

        def _extra(growth_pct):
            extra_stock = max(base_m * (1 + growth_pct/100) - base_m, 0) * _ELASTO_COGS_PCT
            return (f"<p style='color:#888;font-size:12px;margin:0'>EXTRA STOCK NEEDED</p>"
                    f"<p style='color:{_YELLOW};font-size:14px;margin:2px 0 10px'>{_inr(extra_stock)}/month</p>")

    else:
        base_m      = ((actuals["rwox_rev_m"]  or 15_451_424/12) +
                       (actuals["elasto_rev_m"] or 14_972_732/12))
        net_margin  = (346_111 + 855_058) / (15_451_424 + 14_972_732)
        annual_rev  = 15_451_424 + 14_972_732
        title       = "Projected Annual Results — Both Companies"
        color_main  = _GREEN
        base_prod   = actuals["avg_prod_kg"] or _FALLBACK_PROD_KG

        def _extra(growth_pct):
            extra_kg = max(base_prod * (1 + growth_pct/100) - base_prod, 0)
            return (f"<p style='color:#888;font-size:12px;margin:0'>EXTRA RWOX PRODUCTION</p>"
                    f"<p style='color:#ccc;font-size:14px;margin:2px 0 10px'>{extra_kg:,.0f} kg/month</p>")

    wc_ratio = max((1_925_310 + 201_190 + 478_342 + 670_249) /
                   ((15_451_424 + 14_972_732) / 12) / 12, 0.5)

    scenarios = [("Conservative", 5, "#5d6d7e"),
                 ("Base Case",   15, color_main),
                 ("Optimistic",  30, _GREEN)]

    cols = st.columns(3)
    for col, (name, growth_pct, clr) in zip(cols, scenarios):
        factor   = 1 + growth_pct / 100
        proj_m   = base_m * factor
        proj_ann = proj_m * 12
        proj_np  = proj_m * net_margin * (1 - growth_pct * 0.01)
        extra_wc = max(proj_m - base_m, 0) * wc_ratio

        col.markdown(
            f"<div style='background:#1a1a1a;border-radius:10px;padding:20px;"
            f"border-top:4px solid {clr};height:100%'>"
            f"<h3 style='color:{clr};margin:0 0 4px 0'>{name}</h3>"
            f"<p style='color:#888;font-size:13px;margin:0 0 16px 0'>+{growth_pct}% growth</p>"
            f"<hr style='border-color:#333;margin:0 0 12px 0'>"
            f"<p style='color:#888;font-size:12px;margin:0'>MONTHLY REVENUE</p>"
            f"<p style='color:#fff;font-size:20px;font-weight:700;margin:2px 0 10px'>{_inr(proj_m)}</p>"
            f"<p style='color:#888;font-size:12px;margin:0'>ANNUAL REVENUE</p>"
            f"<p style='color:#fff;font-size:16px;font-weight:600;margin:2px 0 10px'>{_inr(proj_ann)}</p>"
            f"<p style='color:#888;font-size:12px;margin:0'>EST. MONTHLY PROFIT</p>"
            f"<p style='color:{_color(proj_np)};font-size:16px;font-weight:600;margin:2px 0 10px'>{_inr(proj_np)}</p>"
            f"{_extra(growth_pct)}"
            f"<p style='color:#888;font-size:12px;margin:0'>EXTRA WORKING CAPITAL</p>"
            f"<p style='color:{_YELLOW if extra_wc > 0 else _GREEN};font-size:14px;font-weight:600;margin:2px 0 0'>{_inr(extra_wc)}</p>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.divider()
    names    = [s[0] for s in scenarios]
    rev_vals = [base_m * (1 + s[1]/100) * 12 for s in scenarios]
    np_vals  = [base_m * (1 + s[1]/100) * net_margin * (1 - s[1]*0.01) * 12 for s in scenarios]
    colors   = [s[2] for s in scenarios]

    fig = go.Figure()
    fig.add_trace(go.Bar(x=names, y=rev_vals, name="Annual Revenue", marker_color=colors,
                         hovertemplate="<b>%{x}</b><br>₹%{y:,.0f}<extra></extra>"))
    fig.add_trace(go.Bar(x=names, y=np_vals, name="Annual Net Profit",
                         marker_color=["rgba(46,204,113,0.6)"]*3,
                         hovertemplate="<b>%{x}</b><br>₹%{y:,.0f}<extra></extra>"))
    fig.update_layout(title=title, height=320, barmode="group",
        xaxis=dict(gridcolor="#333"), yaxis=dict(gridcolor="#333", tickprefix="₹"),
        legend=dict(orientation="h", y=-0.3), **_PLOT)
    st.plotly_chart(fig, use_container_width=True, key=f"{kp}_growth_chart")

    note = "No orders this month — scenarios based on FY25 monthly averages." if base_m == 0 else \
           f"Scenarios modelled from current-month revenue of {_inr(base_m)}."
    st.caption(note)


# ─────────────────────────────────────────────────────────────────────────────
# VIEW RENDERER + ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
def _render_view(conn, actuals: dict, view: str, kp: str) -> None:
    mat_label = "🛒 Stock Costs" if view == "elasto" else "🏭 Material Costs"
    inner = st.tabs([
        "🎯 Set Targets",
        "💲 Price Sensitivity",
        mat_label,
        "📦 Order Check",
        "💵 Cash Forecast",
        "📈 Growth Scenarios",
    ])
    with inner[0]: _tab_targets(conn, actuals, view, kp)
    with inner[1]: _tab_pricing(actuals, view, kp)
    with inner[2]: _tab_materials(actuals, view, kp)
    with inner[3]: _tab_order_check(conn, actuals, view, kp)
    with inner[4]: _tab_cash(actuals, view, kp)
    with inner[5]: _tab_growth(actuals, view, kp)


def render_forecasting_page(conn) -> None:
    _ensure_tables(conn)

    st.header("Scenario Planning")
    st.caption("Play with numbers and see the impact instantly. Every input is pre-filled from your actual data — just move a slider to start exploring.")

    actuals = _load_actuals(conn)

    outer = st.tabs(["📊 Both Companies", "🏭 Rwox", "🏪 Elastohorse"])
    with outer[0]: _render_view(conn, actuals, "both",  "b")
    with outer[1]: _render_view(conn, actuals, "rwox",  "r")
    with outer[2]: _render_view(conn, actuals, "elasto","e")
