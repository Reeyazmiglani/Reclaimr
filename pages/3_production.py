import json
import math
import streamlit as st
from datetime import date as date_type, time as time_type, datetime, timedelta
from pathlib import Path
from db.schema import init_db


@st.cache_resource
def _get_conn():
    return init_db(Path("db") / "erp.db")


TABLE_CSS = (
    "<style>"
    ".orders-table{width:100%;border-collapse:collapse;font-size:14px;margin-bottom:16px}"
    ".orders-table th,.orders-table td{border:1px solid #444;padding:8px 12px;text-align:left;vertical-align:middle}"
    ".orders-table thead tr{background-color:#2a2a2a}"
    ".orders-table tbody tr:hover{background-color:#1e2a3a}"
    ".act-btn{display:inline-block;padding:3px 10px;margin:0 2px;border:1px solid #555;"
    "border-radius:4px;text-decoration:none;color:#fff;font-size:12px;white-space:nowrap}"
    ".act-btn:hover{background-color:#3a3a3a;text-decoration:none;color:#fff}"
    ".act-btn.del{border-color:#c0392b;color:#e74c3c}"
    ".act-btn.del:hover{background-color:#2d1b1b}"
    "</style>"
)


def _order_options(conn, company_id):
    rows = conn.execute(
        "SELECT id, customer_name, product FROM orders WHERE company_id = ? ORDER BY id DESC",
        (company_id,),
    ).fetchall()
    opts = {"— None —": None}
    for r in rows:
        opts[f"#{r['id']} — {r['customer_name']} — {r['product']}"] = r["id"]
    return opts


def _parse_time(t_str):
    if not t_str:
        return None
    try:
        parts = t_str.split(":")
        return time_type(int(parts[0]), int(parts[1]))
    except Exception:
        return None


def _run_time_label(start, end):
    if not start or not end:
        return None
    s = datetime.combine(date_type.today(), start)
    e = datetime.combine(date_type.today(), end)
    if e <= s:
        e += timedelta(days=1)  # overnight run
    mins = int((e - s).total_seconds() / 60)
    return mins, f"{mins // 60}h {mins % 60}m"


def render_production_page(conn):
    st.header("Production")
    st.caption("Daily production logs give you visibility into output, quality, and whether committed delivery dates are still on track.")

    rwox = conn.execute("SELECT id FROM companies WHERE name = 'Rwox'").fetchone()
    if not rwox:
        st.error("Rwox company not found.")
        return
    company_id = rwox["id"]

    # ── Handle action params ───────────────────────────────────────────────────
    params = st.query_params
    if "prod_action" in params:
        action = params.get("prod_action")
        try:
            entry_id = int(params.get("prod_id", 0))
        except (ValueError, TypeError):
            entry_id = 0
        if action == "edit" and entry_id:
            st.session_state["editing_prod_id"] = entry_id
            st.session_state["confirm_del_prod_id"] = None
        elif action == "del" and entry_id:
            st.session_state["confirm_del_prod_id"] = entry_id
        st.query_params.clear()
        st.rerun()

    # ── Monthly summary ────────────────────────────────────────────────────────
    row = conn.execute(
        "SELECT COALESCE(SUM(output_kg),0), COALESCE(SUM(cartons_1kg),0), COALESCE(SUM(cartons_5kg),0) "
        "FROM production_logs WHERE company_id = ? "
        "AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now', 'localtime')",
        (company_id,),
    ).fetchone()
    c1, c2, c3 = st.columns(3)
    c1.metric("Output This Month (kg)", f"{row[0]:,.1f}")
    c2.metric("1 kg Cartons Packed", int(row[1]))
    c3.metric("5 kg Cartons Packed", int(row[2]))
    st.divider()

    # ── Edit form ──────────────────────────────────────────────────────────────
    editing_id = st.session_state.get("editing_prod_id")
    if editing_id:
        entry = conn.execute(
            "SELECT * FROM production_logs WHERE id = ?", (editing_id,)
        ).fetchone()
        if entry:
            st.subheader(f"Editing Entry #{editing_id}")
            order_opts = _order_options(conn, company_id)
            saved_temps = json.loads(entry["temperature_log"]) if entry["temperature_log"] else []

            with st.form("edit_prod_form"):
                ec1, ec2 = st.columns(2)
                with ec1:
                    e_date = st.date_input("Date", value=date_type.fromisoformat(entry["date"]))
                with ec2:
                    e_batch = st.text_input("Batch reference", value=entry["batch_ref"])

                st.markdown("**Materials used (kg)**")
                ep, ew, em = st.columns(3)
                with ep:
                    e_purple = st.number_input("Purple Material", min_value=0.0, value=float(entry["purple_material_kg"]), step=0.5, format="%.2f")
                with ew:
                    e_wax = st.number_input("Wax", min_value=0.0, value=float(entry["wax_kg"]), step=0.5, format="%.2f")
                with em:
                    e_mc = st.number_input("MC", min_value=0.0, value=float(entry["mc_kg"]), step=0.5, format="%.2f")
                e_output = round((e_purple + e_wax + e_mc) * 0.9, 2)
                st.text_input("Output kg (auto)", value=str(e_output), disabled=True)

                st.markdown("**Machine timing**")
                es1, es2 = st.columns(2)
                with es1:
                    e_use_start = st.checkbox("Set start time", value=bool(entry["machine_start"]))
                    e_start = st.time_input("Start", value=_parse_time(entry["machine_start"]) or time_type(8, 0), disabled=not e_use_start)
                with es2:
                    e_use_end = st.checkbox("Set end time", value=bool(entry["machine_end"]))
                    e_end = st.time_input("End", value=_parse_time(entry["machine_end"]) or time_type(17, 0), disabled=not e_use_end)

                st.markdown("**Bottles & Cartons**")
                eb1, eb5 = st.columns(2)
                with eb1:
                    e_b1 = st.number_input("1kg bottles", min_value=0, value=int(entry["bottles_1kg"] or 0), step=1)
                with eb5:
                    e_b5 = st.number_input("5kg bottles", min_value=0, value=int(entry["bottles_5kg"] or 0), step=1)
                ecc1, ecc5 = st.columns(2)
                with ecc1:
                    st.text_input("1kg cartons (auto)", value=str(math.floor(e_b1 / 20)), disabled=True)
                with ecc5:
                    st.text_input("5kg cartons (auto)", value=str(math.floor(e_b5 / 20)), disabled=True)

                e_rej = st.number_input("Rejections/wastage kg", min_value=0.0, value=float(entry["rejections_kg"] or 0), step=0.1, format="%.2f")

                cur_order = next((k for k, v in order_opts.items() if v == entry["order_id"]), "— None —")
                e_order = st.selectbox("Linked order", list(order_opts.keys()), index=list(order_opts.keys()).index(cur_order))

                st.markdown("**Temperature Log** — one reading per line: `HH:MM | temp°C | note`")
                temp_str = "\n".join(
                    f"{t['time']} | {t['temp']} | {t.get('note','')}"
                    for t in saved_temps
                ) if saved_temps else ""
                e_temp_text = st.text_area("Temperature readings", value=temp_str, height=120)

                e_notes = st.text_area("Additional notes", value=entry["additional_notes"] or "")

                sv, ca, _ = st.columns([1, 1, 6])
                with sv:
                    save_btn = st.form_submit_button("Save changes", type="primary")
                with ca:
                    cancel_btn = st.form_submit_button("Cancel")

            if save_btn:
                if not e_batch.strip():
                    st.error("Batch reference is required.")
                else:
                    e_c1 = math.floor(e_b1 / 20)
                    e_c5 = math.floor(e_b5 / 20)
                    e_start_str = str(e_start) if e_use_start else None
                    e_end_str = str(e_end) if e_use_end else None
                    e_run = None
                    if e_use_start and e_use_end:
                        rt = _run_time_label(e_start, e_end)
                        if rt:
                            e_run = rt[0]
                    # Parse temp log
                    e_temps = []
                    for line in e_temp_text.strip().split("\n"):
                        if "|" in line:
                            parts = [p.strip() for p in line.split("|")]
                            if len(parts) >= 2:
                                try:
                                    e_temps.append({"time": parts[0], "temp": float(parts[1]), "note": parts[2] if len(parts) > 2 else ""})
                                except ValueError:
                                    pass
                    conn.execute(
                        "UPDATE production_logs SET date=?, batch_ref=?, purple_material_kg=?, wax_kg=?, "
                        "mc_kg=?, output_kg=?, machine_start=?, machine_end=?, run_time_minutes=?, "
                        "bottles_1kg=?, bottles_5kg=?, cartons_1kg=?, cartons_5kg=?, rejections_kg=?, "
                        "order_id=?, temperature_log=?, additional_notes=? WHERE id=?",
                        (e_date.isoformat(), e_batch.strip(), e_purple, e_wax, e_mc, e_output,
                         e_start_str, e_end_str, e_run,
                         e_b1 or None, e_b5 or None, e_c1 or None, e_c5 or None,
                         e_rej or None, order_opts[e_order],
                         json.dumps(e_temps) if e_temps else None,
                         e_notes.strip() or None, editing_id),
                    )
                    conn.commit()
                    st.session_state["editing_prod_id"] = None
                    st.rerun()
            if cancel_btn:
                st.session_state["editing_prod_id"] = None
                st.rerun()
            st.divider()

    # ── New entry ──────────────────────────────────────────────────────────────
    st.subheader("Log a New Run")

    # Required fields
    fd, fb = st.columns(2)
    with fd:
        prod_date = st.date_input("Date *", value=date_type.today(), key="p_date")
    with fb:
        batch_ref = st.text_input("Batch reference * (e.g. Batch-001)", key="p_batch")

    st.markdown("**Materials used (kg) \\***")
    fp, fw, fm = st.columns(3)
    with fp:
        purple_kg = st.number_input("Purple Material", min_value=0.0, value=0.0, step=0.5, format="%.2f", key="p_purple")
    with fw:
        wax_kg = st.number_input("Wax", min_value=0.0, value=0.0, step=0.5, format="%.2f", key="p_wax")
    with fm:
        mc_kg = st.number_input("MC", min_value=0.0, value=0.0, step=0.5, format="%.2f", key="p_mc")

    output_kg = round((purple_kg + wax_kg + mc_kg) * 0.9, 2)
    st.text_input("Output kg — auto (sum × 0.9)", value=str(output_kg), disabled=True, key="p_out")

    # Optional: machine timing
    with st.expander("Machine timing (optional — captures run duration)"):
        fs1, fs2 = st.columns(2)
        with fs1:
            use_start = st.checkbox("Set start time", key="p_use_start")
            machine_start = st.time_input("Start time", key="p_start", disabled=not use_start)
        with fs2:
            use_end = st.checkbox("Set end time", key="p_use_end")
            machine_end = st.time_input("End time", key="p_end", disabled=not use_end)

        run_time_mins = None
        if use_start and use_end:
            rt = _run_time_label(machine_start, machine_end)
            if rt:
                run_time_mins, label = rt
                overnight = " (overnight)" if machine_end < machine_start else ""
                st.text_input("Total run time", value=label + overnight, disabled=True, key="p_rt")

    # Optional: bottles & cartons
    with st.expander("Bottles & cartons (optional — auto-calculates cartons at 20 per box)"):
        fb1, fb5 = st.columns(2)
        with fb1:
            bottles_1kg = st.number_input("1kg bottles filled", min_value=0, value=0, step=1, key="p_b1")
        with fb5:
            bottles_5kg = st.number_input("5kg bottles filled", min_value=0, value=0, step=1, key="p_b5")
        cartons_1kg = math.floor(bottles_1kg / 20)
        cartons_5kg = math.floor(bottles_5kg / 20)
        fc1, fc5 = st.columns(2)
        with fc1:
            st.text_input("1kg cartons (÷20)", value=str(cartons_1kg), disabled=True, key="p_c1")
        with fc5:
            st.text_input("5kg cartons (÷20)", value=str(cartons_5kg), disabled=True, key="p_c5")

    # Optional: rejections & linked order
    with st.expander("Rejections & linked order (optional)"):
        rejections_kg = st.number_input("Rejections/wastage kg", min_value=0.0, value=0.0, step=0.1, format="%.2f", key="p_rej")
        order_opts = _order_options(conn, company_id)
        linked_order = st.selectbox("Linked order", list(order_opts.keys()), key="p_order")

    # Temperature log
    with st.expander("Temperature log (optional — up to 6 readings)"):
        if "temp_row_ids" not in st.session_state:
            st.session_state["temp_row_ids"] = []
        if "temp_row_ctr" not in st.session_state:
            st.session_state["temp_row_ctr"] = 0

        for rid in list(st.session_state["temp_row_ids"]):
            tc, tt, tn, td = st.columns([1.2, 1, 3, 0.6])
            with tc:
                st.time_input("Time", key=f"tr_t_{rid}")
            with tt:
                st.number_input("°C", min_value=0.0, value=0.0, step=0.5, format="%.1f", key=f"tr_c_{rid}")
            with tn:
                st.text_input("Note", key=f"tr_n_{rid}")
            with td:
                st.markdown("<div style='padding-top:28px'>", unsafe_allow_html=True)
                if st.button("Del", key=f"tr_d_{rid}"):
                    st.session_state["temp_row_ids"].remove(rid)
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

        if len(st.session_state["temp_row_ids"]) < 6:
            if st.button("＋ Add Reading"):
                new_id = st.session_state["temp_row_ctr"]
                st.session_state["temp_row_ctr"] += 1
                st.session_state["temp_row_ids"].append(new_id)
                st.rerun()
        else:
            st.caption("Maximum 6 readings reached.")

    # Additional details
    with st.expander("Additional details (optional)"):
        additional_notes = st.text_area("Process notes", key="p_additional", height=100)

    # Save
    st.markdown("")
    if st.button("💾 Save Entry", type="primary"):
        if not batch_ref.strip():
            st.error("Batch reference is required.")
        elif purple_kg == 0 and wax_kg == 0 and mc_kg == 0:
            st.error("Enter at least one material quantity.")
        else:
            temp_log = []
            for rid in st.session_state.get("temp_row_ids", []):
                t_val = st.session_state.get(f"tr_t_{rid}")
                c_val = st.session_state.get(f"tr_c_{rid}", 0.0)
                n_val = st.session_state.get(f"tr_n_{rid}", "")
                if c_val and c_val > 0:
                    temp_log.append({"time": str(t_val), "temp": c_val, "note": n_val})

            start_str = str(machine_start) if use_start else None
            end_str = str(machine_end) if use_end else None

            conn.execute(
                "INSERT INTO production_logs (company_id, date, batch_ref, purple_material_kg, wax_kg, mc_kg, "
                "output_kg, machine_start, machine_end, run_time_minutes, bottles_1kg, bottles_5kg, "
                "cartons_1kg, cartons_5kg, rejections_kg, order_id, temperature_log, additional_notes) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (company_id, prod_date.isoformat(), batch_ref.strip(),
                 purple_kg, wax_kg, mc_kg, output_kg,
                 start_str, end_str, run_time_mins,
                 bottles_1kg or None, bottles_5kg or None,
                 cartons_1kg or None, cartons_5kg or None,
                 rejections_kg or None, order_opts.get(linked_order),
                 json.dumps(temp_log) if temp_log else None,
                 additional_notes.strip() or None),
            )
            conn.commit()
            st.session_state["temp_row_ids"] = []
            st.success("Production run logged.")
            st.rerun()

    # ── Production log table ───────────────────────────────────────────────────
    st.divider()
    st.subheader("Production Log")
    st.caption("Every run on record. Filter by batch or date range to investigate output or quality trends.")

    # Filter bar
    lfa, lfb, lfc, lfd = st.columns([2, 1.8, 1.8, 1])
    with lfa:
        log_batch = st.text_input("Batch ref", placeholder="Search batch...", key="fprod_batch")
    with lfb:
        log_from = st.date_input("Date from", value=None, key="fprod_from")
    with lfc:
        log_to = st.date_input("Date to", value=None, key="fprod_to")
    with lfd:
        st.markdown("<div style='padding-top:28px'>", unsafe_allow_html=True)
        if st.button("✕ Clear", key="fprod_clear"):
            for k in ["fprod_batch", "fprod_from", "fprod_to"]:
                st.session_state.pop(k, None)
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    lsql = (
        "SELECT pl.*, o.product AS order_product, o.customer_name "
        "FROM production_logs pl LEFT JOIN orders o ON pl.order_id = o.id "
        "WHERE pl.company_id = ?"
    )
    lqp = [company_id]
    if log_batch:
        lsql += " AND pl.batch_ref LIKE ?"; lqp.append(f"%{log_batch}%")
    if log_from:
        lsql += " AND pl.date >= ?"; lqp.append(log_from.isoformat())
    if log_to:
        lsql += " AND pl.date <= ?"; lqp.append(log_to.isoformat())
    lsql += " ORDER BY pl.date DESC, pl.created_at DESC"

    logs = conn.execute(lsql, lqp).fetchall()

    if not logs:
        st.info("No entries match — adjust the filters above.")
        return

    rows_html = ""
    for lg in logs:
        linked = f"{lg['order_product']} ({lg['customer_name']})" if lg["order_product"] else "—"
        mats = f"{lg['purple_material_kg']} / {lg['wax_kg']} / {lg['mc_kg']}"
        timing = f"{lg['machine_start']}–{lg['machine_end']}" if lg["machine_start"] else "—"
        bottles = f"{int(lg['bottles_1kg'] or 0)} / {int(lg['bottles_5kg'] or 0)}"
        cartons = f"{int(lg['cartons_1kg'] or 0)} / {int(lg['cartons_5kg'] or 0)}"
        edit_url = f"?page=Production&prod_action=edit&prod_id={lg['id']}"
        del_url  = f"?page=Production&prod_action=del&prod_id={lg['id']}"
        rows_html += (
            f"<tr>"
            f"<td>{lg['id']}</td><td>{lg['date']}</td><td>{lg['batch_ref']}</td>"
            f"<td>{mats}</td><td><b>{lg['output_kg']}</b></td>"
            f"<td>{timing}</td><td>{bottles}</td><td>{cartons}</td>"
            f"<td>{lg['rejections_kg'] or '—'}</td><td>{linked}</td>"
            f"<td><a href='#' onclick=\"window.top.location='{edit_url}';return false;\" class='act-btn'>Edit</a>"
            f"<a href='#' onclick=\"window.top.location='{del_url}';return false;\" class='act-btn del'>Del</a></td>"
            f"</tr>"
        )

    st.markdown(
        TABLE_CSS
        + "<table class='orders-table'><thead><tr>"
        "<th>ID</th><th>Date</th><th>Batch</th><th>Purple/Wax/MC kg</th>"
        "<th>Output kg</th><th>Machine time</th><th>Bottles 1kg/5kg</th>"
        "<th>Cartons 1kg/5kg</th><th>Rejections kg</th><th>Order</th><th>Actions</th>"
        f"</tr></thead><tbody>{rows_html}</tbody></table>",
        unsafe_allow_html=True,
    )

    # Delete confirmation
    confirm_del_id = st.session_state.get("confirm_del_prod_id")
    if confirm_del_id:
        row = conn.execute(
            "SELECT id, batch_ref, date FROM production_logs WHERE id = ?", (confirm_del_id,)
        ).fetchone()
        if row:
            st.warning(f"Delete entry #{row['id']} — {row['batch_ref']} on {row['date']}? Cannot be undone.")
            yc, nc, _ = st.columns([1, 1, 8])
            with yc:
                if st.button("Yes, delete", type="primary"):
                    conn.execute("DELETE FROM production_logs WHERE id = ?", (confirm_del_id,))
                    conn.commit()
                    st.session_state["confirm_del_prod_id"] = None
                    st.rerun()
            with nc:
                if st.button("Cancel"):
                    st.session_state["confirm_del_prod_id"] = None
                    st.rerun()
