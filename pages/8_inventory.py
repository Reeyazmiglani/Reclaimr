import streamlit as st
import pandas as pd
from datetime import date
from pathlib import Path
from db.schema import init_db
from utils.settings import get_stock_thresholds, set_stock_thresholds, DEFAULT_STOCK_THRESHOLDS


@st.cache_resource
def _get_conn():
    return init_db(Path("db") / "erp.db")


_GREEN  = "#1B7F4F"
_YELLOW = "#D97706"
_RED    = "#C0392B"
_BLUE   = "#C17F3E"

# Raw materials we can cleanly match procurement.item against (case-insensitive, trimmed).
# Anything in procurement.item that isn't one of these falls into "Other / unmatched"
# instead of silently disappearing — see 3_procurement.py for the item vocabulary
# (Base Oil, Solvent X, and free-text typos like "whatev" show up there too).
RAW_MATERIALS = ["Purple Material", "Wax", "MC"]

# Default low-stock thresholds — centralized in the `settings` table (also
# editable from Settings -> Alert Thresholds) so this page and Settings stay
# in sync, instead of each keeping its own copy.
DEFAULT_THRESHOLDS = DEFAULT_STOCK_THRESHOLDS

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


def _ensure_tables(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS stock_adjustments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            company_id INTEGER NOT NULL,
            item_type TEXT NOT NULL,
            item_name TEXT NOT NULL,
            adjustment_qty REAL NOT NULL,
            reason TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (company_id) REFERENCES companies(id)
        );
        """
    )
    conn.commit()


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _raw_material_balances(conn, company_id):
    """IN (procurement) - OUT (production consumption) per known raw material,
    plus an 'Other / unmatched' bucket for procurement items that don't match
    Purple Material / Wax / MC (see RAW_MATERIALS)."""
    proc_rows = conn.execute(
        "SELECT item, quantity FROM procurement WHERE company_id = ?", (company_id,)
    ).fetchall()

    known_norm = {_norm(m): m for m in RAW_MATERIALS}
    in_totals = {m: 0.0 for m in RAW_MATERIALS}
    other_in = {}
    for r in proc_rows:
        key = _norm(r["item"])
        if key in known_norm:
            in_totals[known_norm[key]] += r["quantity"]
        else:
            label = (r["item"] or "").strip() or "(blank)"
            other_in[label] = other_in.get(label, 0.0) + r["quantity"]

    out_row = conn.execute(
        "SELECT COALESCE(SUM(purple_material_kg),0), COALESCE(SUM(wax_kg),0), "
        "COALESCE(SUM(mc_kg),0) FROM production_logs WHERE company_id = ?",
        (company_id,),
    ).fetchone()
    out_totals = {
        "Purple Material": out_row[0],
        "Wax": out_row[1],
        "MC": out_row[2],
    }

    adj_rows = conn.execute(
        "SELECT item_name, COALESCE(SUM(adjustment_qty),0) AS adj FROM stock_adjustments "
        "WHERE company_id = ? AND item_type = 'raw_material' GROUP BY item_name",
        (company_id,),
    ).fetchall()
    adj_map = {a["item_name"]: a["adj"] for a in adj_rows}

    rows = []
    for m in RAW_MATERIALS:
        adj = adj_map.get(m, 0.0)
        balance = in_totals[m] - out_totals[m] + adj
        rows.append({
            "Material": m, "IN (kg)": in_totals[m], "OUT (kg)": out_totals[m],
            "Adjustments (kg)": adj, "Balance (kg)": balance,
        })

    other_rows = []
    for label, qty in other_in.items():
        adj = adj_map.get(label, 0.0)
        other_rows.append({
            "Material": label, "IN (kg)": qty, "OUT (kg)": 0.0,
            "Adjustments (kg)": adj, "Balance (kg)": qty + adj,
        })

    return pd.DataFrame(rows), pd.DataFrame(other_rows)


def _finished_goods_balance(conn, company_id):
    """Single generic finished-goods pool in kg (see conversation: orders.product
    doesn't map to bottle size and production_logs carries no product field, so
    per-product/size tracking isn't recoverable from this schema today).

    IN  = (bottles_1kg * 1) + (bottles_5kg * 5), summed across all production runs.
    OUT = dispatched orders where quantity_unit = 'kg'.
    Dispatched orders in other units are surfaced separately, not silently dropped.
    """
    in_row = conn.execute(
        "SELECT COALESCE(SUM(COALESCE(bottles_1kg,0)*1 + COALESCE(bottles_5kg,0)*5),0) "
        "FROM production_logs WHERE company_id = ?",
        (company_id,),
    ).fetchone()
    in_kg = in_row[0]

    out_row = conn.execute(
        "SELECT COALESCE(SUM(quantity),0) FROM orders "
        "WHERE company_id = ? AND status = 'dispatched' AND quantity_unit = 'kg'",
        (company_id,),
    ).fetchone()
    out_kg = out_row[0]

    non_kg = conn.execute(
        "SELECT id, customer_name, product, quantity, quantity_unit FROM orders "
        "WHERE company_id = ? AND status = 'dispatched' AND quantity_unit != 'kg'",
        (company_id,),
    ).fetchall()

    adj_row = conn.execute(
        "SELECT COALESCE(SUM(adjustment_qty),0) FROM stock_adjustments "
        "WHERE company_id = ? AND item_type = 'finished_good'",
        (company_id,),
    ).fetchone()
    adj_kg = adj_row[0]

    balance = in_kg - out_kg + adj_kg
    return in_kg, out_kg, adj_kg, balance, pd.DataFrame([dict(r) for r in non_kg])


def _flag(balance, threshold):
    if balance < threshold * 0.5:
        return _RED, "🔴 Critical"
    if balance < threshold:
        return _YELLOW, "🟡 Low"
    return _GREEN, "🟢 OK"


def render_inventory_page(conn):
    _ensure_tables(conn)
    st.markdown(_DARK_CSS if st.session_state.get("dark_mode") else _WARM_CSS, unsafe_allow_html=True)
    st.header("Inventory")
    st.caption(
        "Live stock, computed from procurement and production records — not a "
        "manually-maintained count. Log a stocktake adjustment below to reconcile "
        "against what's actually on the shelf."
    )

    companies = {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM companies")}
    company = st.selectbox("Company", list(companies.keys()), key="inv_company")
    company_id = companies[company]

    thresholds = get_stock_thresholds(conn)

    with st.expander("⚙ Low-stock thresholds (editable, per item — also editable from Settings)"):
        tcols = st.columns(len(thresholds))
        changed = False
        for col, (item, val) in zip(tcols, thresholds.items()):
            new_val = col.number_input(item, min_value=0.0, value=float(val), step=10.0, key=f"thr_{item}")
            if new_val != val:
                thresholds[item] = new_val
                changed = True
        if changed:
            set_stock_thresholds(conn, thresholds)

    st.divider()

    # ── Raw materials ────────────────────────────────────────────────────────────
    st.subheader("Raw Material Stock")
    raw_df, other_df = _raw_material_balances(conn, company_id)

    rcols = st.columns(len(raw_df))
    for col, (_, row) in zip(rcols, raw_df.iterrows()):
        thr = thresholds.get(row["Material"], 0.0)
        color, label = _flag(row["Balance (kg)"], thr)
        with col:
            st.markdown(
                f"<div style='background:{color}22;border:1px solid {color};border-radius:10px;"
                f"padding:14px 16px'>"
                f"<div style='font-size:12px;color:#8B6A45;text-transform:uppercase'>{row['Material']}</div>"
                f"<div style='font-size:24px;font-weight:700;color:{color}'>{row['Balance (kg)']:.1f} kg</div>"
                f"<div style='font-size:12px;color:{color}'>{label} · threshold {thr:.0f} kg</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
    st.markdown("")
    st.dataframe(raw_df.style.format({
        "IN (kg)": "{:.1f}", "OUT (kg)": "{:.1f}",
        "Adjustments (kg)": "{:.1f}", "Balance (kg)": "{:.1f}",
    }), use_container_width=True, hide_index=True)

    if not other_df.empty:
        st.markdown("**Other / unmatched procurement items** — these don't match Purple Material, Wax, or MC, so they're shown separately rather than silently dropped:")
        st.dataframe(other_df.style.format({
            "IN (kg)": "{:.1f}", "OUT (kg)": "{:.1f}",
            "Adjustments (kg)": "{:.1f}", "Balance (kg)": "{:.1f}",
        }), use_container_width=True, hide_index=True)

    st.divider()

    # ── Finished goods ───────────────────────────────────────────────────────────
    st.subheader("Finished Goods Stock")
    st.caption(
        "Tracked as one generic kg pool: orders don't record which package size "
        "(1kg / 5kg bottle) was dispatched, and production runs don't record which "
        "product they were for — so per-product/size balances aren't derivable from "
        "the current data."
    )
    in_kg, out_kg, adj_kg, fg_balance, non_kg_df = _finished_goods_balance(conn, company_id)
    thr_fg = thresholds.get("Finished Goods (kg)", 0.0)
    color, label = _flag(fg_balance, thr_fg)

    fc1, fc2, fc3, fc4 = st.columns(4)
    fc1.metric("Produced (IN, kg)", f"{in_kg:,.1f}")
    fc2.metric("Dispatched (OUT, kg)", f"{out_kg:,.1f}")
    fc3.metric("Adjustments (kg)", f"{adj_kg:+,.1f}")
    fc4.markdown(
        f"<div style='background:{color}22;border:1px solid {color};border-radius:10px;"
        f"padding:14px 16px'>"
        f"<div style='font-size:12px;color:#8B6A45;text-transform:uppercase'>Balance</div>"
        f"<div style='font-size:24px;font-weight:700;color:{color}'>{fg_balance:,.1f} kg</div>"
        f"<div style='font-size:12px;color:{color}'>{label} · threshold {thr_fg:.0f} kg</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    if not non_kg_df.empty:
        st.warning(
            f"⚠ {len(non_kg_df)} dispatched order(s) recorded in a unit other than kg — "
            "excluded from the kg balance above, shown here instead:"
        )
        st.dataframe(non_kg_df, use_container_width=True, hide_index=True)

    st.divider()

    # ── Stock adjustments (reconciliation) ───────────────────────────────────────
    st.subheader("Log a Stock Adjustment")
    st.caption(
        "Real stocktakes drift from the calculated balance — spillage, miscounts, "
        "damaged stock. Log a correction here instead of editing historical "
        "procurement/production records."
    )
    with st.form("stock_adj_form"):
        ac1, ac2, ac3 = st.columns([1, 1.4, 1])
        with ac1:
            adj_date = st.date_input("Date", value=date.today())
        with ac2:
            item_type = st.selectbox("Item type", ["raw_material", "finished_good"],
                                      format_func=lambda v: "Raw Material" if v == "raw_material" else "Finished Good")
            if item_type == "raw_material":
                item_name = st.selectbox("Item", RAW_MATERIALS)
            else:
                item_name = st.selectbox("Item", ["Finished Goods (kg)"])
        with ac3:
            adjustment_qty = st.number_input(
                "Adjustment (kg)", value=0.0, step=1.0, format="%.2f",
                help="Positive to add stock found, negative to remove stock lost/spilled/damaged.",
            )
        reason = st.text_input("Reason", placeholder="e.g. Spillage during transfer, physical stocktake correction")
        submitted = st.form_submit_button("Log Adjustment")

    if submitted:
        if adjustment_qty == 0:
            st.error("Adjustment quantity must be non-zero.")
        else:
            conn.execute(
                "INSERT INTO stock_adjustments (date, company_id, item_type, item_name, "
                "adjustment_qty, reason) VALUES (?, ?, ?, ?, ?, ?)",
                (adj_date.isoformat(), company_id, item_type, item_name,
                 adjustment_qty, reason.strip() or None),
            )
            conn.commit()
            st.success("Adjustment logged.")
            st.rerun()

    st.markdown("**Recent adjustments**")
    adj_history = conn.execute(
        "SELECT date, item_type, item_name, adjustment_qty, reason, created_at "
        "FROM stock_adjustments WHERE company_id = ? ORDER BY date DESC, id DESC LIMIT 20",
        (company_id,),
    ).fetchall()
    if not adj_history:
        st.info("No adjustments logged yet.")
    else:
        hist_df = pd.DataFrame([dict(r) for r in adj_history]).rename(columns={
            "date": "Date", "item_type": "Type", "item_name": "Item",
            "adjustment_qty": "Adjustment (kg)", "reason": "Reason", "created_at": "Logged At",
        })
        hist_df["Type"] = hist_df["Type"].map({"raw_material": "Raw Material", "finished_good": "Finished Good"})
        st.dataframe(hist_df, use_container_width=True, hide_index=True)
