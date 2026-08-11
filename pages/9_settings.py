import os
import io
import streamlit as st
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from db.schema import init_db
from utils.settings import (
    get_dark_mode, set_dark_mode,
    get_overdue_days, set_setting,
    get_stock_thresholds, set_stock_thresholds,
    get_company_details, set_company_details,
)
from utils.auth import (
    require_auth, render_logout_button,
    get_pending_users, get_all_users, approve_user, remove_user,
    get_pending_whatsapp_numbers, get_all_whatsapp_numbers,
    approve_whatsapp_number, remove_whatsapp_number,
)
from utils.responsive_css import RESPONSIVE_CSS

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


@st.cache_resource
def _get_conn():
    return init_db(DATABASE_URL)


require_auth(_get_conn())
render_logout_button()


_GREEN  = "#1B7F4F"
_YELLOW = "#D97706"
_RED    = "#C0392B"
_BLUE   = "#C17F3E"
_GROQ_MODEL = "openai/gpt-oss-120b"  # the model used by the AI Q&A / Financial Pulse advisor

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

COMPANIES = ["Rwox", "Elastohorse"]


def render_settings_page(conn):
    st.markdown(_DARK_CSS if st.session_state.get("dark_mode") else _WARM_CSS, unsafe_allow_html=True)
    st.markdown(RESPONSIVE_CSS, unsafe_allow_html=True)
    st.header("Settings")
    st.caption("Most settings below are shared app-wide; the Team & Access section is per-account.")

    user = st.session_state.get("auth_user", {})

    # ══════════════════════════════════════════════════════════════════════
    # 0 — TEAM & ACCESS (owner only)
    # ══════════════════════════════════════════════════════════════════════
    if user.get("role") == "owner":
        st.subheader("Team & Access")
        pending = get_pending_users(conn)
        if pending:
            st.markdown(f"**{len(pending)} pending {'request' if len(pending)==1 else 'requests'}**")
            for p in pending:
                pc1, pc2, pc3 = st.columns([3, 1, 1])
                pc1.write(f"{p['name']} (`{p['username']}`) — requested {p['created_at']}")
                if pc2.button("✅ Approve", key=f"approve_{p['id']}"):
                    approve_user(conn, p["id"])
                    st.success(f"Approved {p['name']}.")
                    st.rerun()
                if pc3.button("🗑 Reject", key=f"reject_{p['id']}"):
                    remove_user(conn, p["id"])
                    st.info(f"Rejected {p['name']}.")
                    st.rerun()
        else:
            st.caption("No pending signup requests.")

        with st.expander("All accounts"):
            for u in get_all_users(conn):
                uc1, uc2, uc3 = st.columns([3, 1, 1])
                uc1.write(f"{u['name']} (`{u['username']}`) — {u['role']}"
                          + ("" if u["approved"] else " · pending"))
                uc2.write("")
                if u["role"] != "owner" and uc3.button("🗑 Remove", key=f"remove_{u['id']}"):
                    remove_user(conn, u["id"])
                    st.rerun()

        st.markdown("**WhatsApp numbers**")
        pending_wa = get_pending_whatsapp_numbers(conn)
        if pending_wa:
            st.markdown(f"**{len(pending_wa)} pending WhatsApp {'request' if len(pending_wa)==1 else 'requests'}**")
            for p in pending_wa:
                wc1, wc2, wc3 = st.columns([3, 1, 1])
                label = p["display_name"] or "(no name)"
                wc1.write(f"{label} (`{p['phone_number']}`) — messaged {p['created_at']}")
                if wc2.button("✅ Approve", key=f"wa_approve_{p['id']}"):
                    # auth is currently disabled (see utils/auth.py's
                    # _AUTH_DISABLED_USER), so the "logged in" user is a
                    # sentinel with id=0 that doesn't exist in `users` —
                    # passing it as added_by trips the FK constraint. `or
                    # None` maps that falsy sentinel id to NULL; a real
                    # user id (once auth is re-enabled) passes through.
                    approve_whatsapp_number(conn, p["id"], user.get("id") or None)
                    st.success(f"Approved {p['phone_number']}.")
                    st.rerun()
                if wc3.button("🗑 Reject", key=f"wa_reject_{p['id']}"):
                    remove_whatsapp_number(conn, p["id"])
                    st.info(f"Rejected {p['phone_number']}.")
                    st.rerun()
        else:
            st.caption("No pending WhatsApp requests.")

        with st.expander("All WhatsApp numbers"):
            all_wa = get_all_whatsapp_numbers(conn)
            if not all_wa:
                st.caption("No WhatsApp numbers on file yet.")
            for n in all_wa:
                nc1, nc2, nc3 = st.columns([3, 1, 1])
                label = n["display_name"] or "(no name)"
                nc1.write(f"{label} (`{n['phone_number']}`)"
                          + ("" if n["approved"] else " · pending"))
                nc2.write("")
                if nc3.button("🗑 Remove", key=f"wa_remove_{n['id']}"):
                    remove_whatsapp_number(conn, n["id"])
                    st.rerun()

        st.divider()

    # ══════════════════════════════════════════════════════════════════════
    # 1 — APPEARANCE
    # ══════════════════════════════════════════════════════════════════════
    st.subheader("Appearance")
    saved_dark = get_dark_mode(conn)
    new_dark = st.toggle("🌙 Dark mode", value=st.session_state.get("dark_mode", saved_dark), key="settings_dark_toggle")
    if new_dark != saved_dark:
        set_dark_mode(conn, new_dark)
        # session_state["dark_mode"] is owned by the sidebar toggle's widget key
        # and can't be written directly from here — hand it off for app.py to
        # apply on the next rerun, before that widget is (re)created.
        st.session_state["_dark_mode_sync"] = new_dark
        st.rerun()
    st.caption("Also controllable from the sidebar toggle on any page — both read and write the same saved setting, so they stay in sync.")

    st.divider()

    # ══════════════════════════════════════════════════════════════════════
    # 2 — ALERT THRESHOLDS
    # ══════════════════════════════════════════════════════════════════════
    st.subheader("Alert Thresholds")

    current_overdue = get_overdue_days(conn)
    new_overdue = st.number_input(
        "Overdue receivables/payables (days)",
        min_value=1, value=current_overdue, step=1,
        help="Used on the Credit page and the Overview alerts to flag receivables/payables as overdue.",
    )
    if st.button("Save overdue threshold"):
        set_setting(conn, "overdue_days", str(int(new_overdue)))
        st.success(f"Saved — overdue threshold is now {int(new_overdue)} days.")
        st.rerun()

    st.markdown("**Low-stock thresholds** (also editable from the Inventory page — same saved values)")
    thresholds = get_stock_thresholds(conn)
    tcols = st.columns(len(thresholds))
    new_thresholds = {}
    for col, (item, val) in zip(tcols, thresholds.items()):
        new_thresholds[item] = col.number_input(item, min_value=0.0, value=float(val), step=10.0, key=f"set_thr_{item}")
    if st.button("Save stock thresholds"):
        set_stock_thresholds(conn, new_thresholds)
        st.success("Stock thresholds saved.")
        st.rerun()

    st.divider()

    # ══════════════════════════════════════════════════════════════════════
    # 3 — COMPANY DETAILS
    # ══════════════════════════════════════════════════════════════════════
    st.subheader("Company Details")
    st.caption("Used on the dispatch note PDF (Orders page). Leave blank to omit a field from the note.")

    details = get_company_details(conn)
    updated_details = {}
    cols = st.columns(2)
    for col, co in zip(cols, COMPANIES):
        d = details.get(co, {"address": "", "gstin": "", "contact": ""})
        with col:
            st.markdown(f"**{co}**")
            addr = st.text_area("Address", value=d.get("address", ""), key=f"co_addr_{co}", height=80)
            gstin = st.text_input("GSTIN", value=d.get("gstin", ""), key=f"co_gstin_{co}")
            contact = st.text_input("Contact number", value=d.get("contact", ""), key=f"co_contact_{co}")
            updated_details[co] = {"address": addr.strip(), "gstin": gstin.strip(), "contact": contact.strip()}

    if st.button("Save company details"):
        set_company_details(conn, updated_details)
        st.success("Company details saved — the dispatch note will use these going forward.")
        st.rerun()

    st.divider()

    # ══════════════════════════════════════════════════════════════════════
    # 4 — AI CONNECTION TEST
    # ══════════════════════════════════════════════════════════════════════
    st.subheader("AI Connection")
    st.caption(f"Current model: `{_GROQ_MODEL}` (Groq)")
    if st.button("Test AI Connection"):
        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key:
            st.error("❌ No GROQ_API_KEY found in .env — the AI features will not work until this is set.")
        else:
            try:
                from groq import Groq
                client = Groq(api_key=api_key)
                resp = client.chat.completions.create(
                    model=_GROQ_MODEL,
                    messages=[{"role": "user", "content": "Reply with exactly: OK"}],
                    max_tokens=200, reasoning_effort="low",
                )
                content = (resp.choices[0].message.content or "").strip()
                st.success(f"✅ Connected — model responded: \"{content}\"")
            except ImportError:
                st.error("❌ The `groq` package isn't installed. Run `pip install groq`.")
            except Exception as e:
                st.error(f"❌ Connection failed: {type(e).__name__}: {e}")

    st.divider()

    # ══════════════════════════════════════════════════════════════════════
    # 5 — DATA MANAGEMENT
    # ══════════════════════════════════════════════════════════════════════
    st.subheader("Data Management")

    tables = [r["table_name"] for r in conn.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' ORDER BY table_name"
    ).fetchall()]
    counts = []
    for t in tables:
        try:
            n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        except Exception:
            n = None
        counts.append({"Table": t, "Rows": n})

    st.dataframe(pd.DataFrame(counts), use_container_width=True, hide_index=True)
    st.caption(
        "Running on PostgreSQL — use Railway's own backup/snapshot tools "
        "(or `pg_dump`) for a full database backup; the old local-file "
        "download isn't applicable now that data lives in Postgres."
    )
