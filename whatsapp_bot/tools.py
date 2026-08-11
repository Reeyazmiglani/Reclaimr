"""Tool implementations backing the Groq function-calling agent.

Read tools execute immediately. Write tools never touch the database
directly — see `resolve_write_tool` / `execute_pending_action` in
main.py for the lookup → confirm → execute flow described in the repo
README.
"""
import json
from datetime import datetime, timedelta

PENDING_ACTION_TTL_MINUTES = 5
CONTEXT_TTL_MINUTES = 5

# ─────────────────────────────────────────────────────────────────────────
# FY25 figures — duplicated from pages/6_financials.py's hardcoded FY25
# dict (Financial Pulse has no per-month breakdown; it's an annual figure
# per company, not a live query). Keep in sync with that file if the
# figures there are ever updated.
# ─────────────────────────────────────────────────────────────────────────
FY25 = {
    "Rwox": {
        "sales": 15_451_424, "gross_profit": 2_682_594, "net_profit": 346_111,
        "cash_bank": 478_342, "stock": 1_925_310, "debtors": 0, "total_assets": 4_593_152,
    },
    "Elastohorse": {
        "sales": 14_972_732, "gross_profit": 2_412_690, "net_profit": 855_058,
        "cash_bank": 670_249, "stock": 201_190, "debtors": 1_320_647, "total_assets": 6_372_835,
    },
}


def _inr(n):
    return f"₹{n:,.0f}"


# ─────────────────────────────────────────────────────────────────────────
# READ TOOLS — execute immediately, no confirmation
# ─────────────────────────────────────────────────────────────────────────

def _format_order_line(r) -> str:
    return (
        f"Order #{r['id']} — {r['customer_name']}: {r['quantity']} {r['quantity_unit']} "
        f"{r['product']}, status: {r['status']}, expected dispatch: {r['expected_dispatch_date']}"
    )


def find_orders_by_customer(conn, customer_name: str, limit: int = 5):
    """Returns raw order rows for a customer_name match — shared by the
    formatted get_order_status reply and by context-capture in groq_agent."""
    return conn.execute(
        "SELECT id, customer_name, product, quantity, quantity_unit, status, "
        "expected_dispatch_date FROM orders WHERE customer_name ILIKE %s "
        f"ORDER BY created_at DESC LIMIT {int(limit)}",
        (f"%{customer_name}%",),
    ).fetchall()


def get_order_by_id(conn, order_id: int):
    """Returns the raw order row for a specific order number, or None."""
    return conn.execute(
        "SELECT id, customer_name, product, quantity, quantity_unit, status, "
        "expected_dispatch_date FROM orders WHERE id=%s",
        (order_id,),
    ).fetchone()


def get_order_status(conn, customer_name: str) -> str:
    rows = find_orders_by_customer(conn, customer_name)
    if not rows:
        return f"No orders found for a customer matching '{customer_name}'."
    return "\n".join(_format_order_line(r) for r in rows)


def get_order_status_by_id(conn, order_id: int) -> str:
    row = get_order_by_id(conn, order_id)
    if not row:
        return f"No order found with number #{order_id}."
    return _format_order_line(row)


def get_vendor_price_history(conn, vendor: str, material: str) -> str:
    rows = conn.execute(
        "SELECT unit_cost, purchase_date FROM procurement "
        "WHERE supplier ILIKE %s AND item ILIKE %s "
        "ORDER BY purchase_date DESC LIMIT 5",
        (f"%{vendor}%", f"%{material}%"),
    ).fetchall()
    if not rows:
        return f"No purchase history found for vendor '{vendor}' / material '{material}'."
    last = rows[0]
    lines = [f"Last price from {vendor} for {material}: {_inr(last['unit_cost'])} on {last['purchase_date']}."]
    if len(rows) > 1:
        prev = rows[1]
        if last["unit_cost"] > prev["unit_cost"]:
            trend = f"up from {_inr(prev['unit_cost'])} on {prev['purchase_date']}"
        elif last["unit_cost"] < prev["unit_cost"]:
            trend = f"down from {_inr(prev['unit_cost'])} on {prev['purchase_date']}"
        else:
            trend = f"unchanged from {prev['purchase_date']}"
        lines.append(f"Trend: {trend}.")
    return "\n".join(lines)


def get_receivables_status(conn, customer_name: str) -> str:
    rows = conn.execute(
        """
        SELECT r.id, r.reference, r.amount, r.date, r.status,
               COALESCE(p.paid, 0) AS paid
        FROM receivables r
        LEFT JOIN (
            SELECT reference_id, SUM(amount_paid) AS paid FROM payments
            WHERE type='receivable' GROUP BY reference_id
        ) p ON p.reference_id = r.id
        WHERE r.customer_name ILIKE %s
        ORDER BY r.date DESC LIMIT 5
        """,
        (f"%{customer_name}%",),
    ).fetchall()
    if not rows:
        return f"No receivables found for a customer matching '{customer_name}'."
    lines = []
    for r in rows:
        owed = float(r["amount"]) - float(r["paid"])
        if owed <= 0:
            lines.append(f"{r['reference'] or ('Ref #' + str(r['id']))} ({r['date']}): fully paid ({_inr(r['amount'])}).")
        elif float(r["paid"]) > 0:
            lines.append(f"{r['reference'] or ('Ref #' + str(r['id']))} ({r['date']}): partially paid — {_inr(owed)} still owed of {_inr(r['amount'])}.")
        else:
            lines.append(f"{r['reference'] or ('Ref #' + str(r['id']))} ({r['date']}): unpaid — {_inr(owed)} owed.")
    return "\n".join(lines)


def get_daily_actions(conn, overdue_days: int = 7) -> str:
    """Mirrors pages/0_overview.py's live action-list counts."""
    due_today_overdue = conn.execute(
        "SELECT COUNT(*) FROM orders "
        "WHERE expected_dispatch_date::date <= CURRENT_DATE AND status != 'dispatched'"
    ).fetchone()[0]

    overdue_rec_row = conn.execute(
        """
        SELECT COUNT(*) as cnt, COALESCE(SUM(r.amount - COALESCE(p_sum,0)), 0) as total
        FROM receivables r
        LEFT JOIN (
            SELECT reference_id, SUM(amount_paid) as p_sum FROM payments
            WHERE type='receivable' GROUP BY reference_id
        ) px ON px.reference_id = r.id
        WHERE r.status != 'paid' AND (CURRENT_DATE - r.date::date) > %s
        """,
        (overdue_days,),
    ).fetchone()

    open_complaints = conn.execute(
        "SELECT COUNT(*) FROM batch_complaints WHERE status != 'resolved'"
    ).fetchone()[0]

    stagnant_count = conn.execute(
        "SELECT COUNT(*) FROM orders "
        "WHERE created_at::date <= CURRENT_DATE - INTERVAL '7 days' AND status='received'"
    ).fetchone()[0]

    overdue_pay_count = conn.execute(
        "SELECT COUNT(*) FROM payables p "
        "WHERE p.status != 'paid' AND (CURRENT_DATE - p.date::date) > %s",
        (overdue_days,),
    ).fetchone()[0]

    total = due_today_overdue + overdue_rec_row["cnt"] + open_complaints + stagnant_count + overdue_pay_count
    if total == 0:
        return "No open actions right now — nothing due, overdue, stagnant, or unresolved."

    lines = [f"{total} open action(s) today:"]
    if due_today_overdue:
        lines.append(f"- {due_today_overdue} order(s) due/overdue for dispatch.")
    if overdue_rec_row["cnt"]:
        lines.append(f"- {overdue_rec_row['cnt']} overdue receivable(s) totalling {_inr(overdue_rec_row['total'])}.")
    if open_complaints:
        lines.append(f"- {open_complaints} open batch complaint(s).")
    if stagnant_count:
        lines.append(f"- {stagnant_count} order(s) stuck at 'received' for over 7 days.")
    if overdue_pay_count:
        lines.append(f"- {overdue_pay_count} overdue payable(s).")
    return "\n".join(lines)


def get_revenue_summary(conn, month: str = None, entity: str = None) -> str:
    """FY25 figures are annual only (no month-level breakdown exists in the
    app yet) — a month argument is acknowledged but can't narrow the answer."""
    entities = [entity] if entity and entity in FY25 else list(FY25.keys())
    if entity and entity not in FY25:
        return f"'{entity}' isn't a recognized company — try 'Rwox' or 'Elastohorse'."
    lines = []
    if month:
        lines.append(f"(Note: revenue is only tracked annually for FY25, not by month — showing full-year figures.)")
    for co in entities:
        d = FY25[co]
        margin = d["net_profit"] / d["sales"] * 100
        lines.append(
            f"{co} FY25: sales {_inr(d['sales'])}, net profit {_inr(d['net_profit'])} ({margin:.1f}% margin), "
            f"cash at bank {_inr(d['cash_bank'])}, debtors {_inr(d['debtors'])}."
        )
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────
# WRITE TOOLS — lookup → confirm → execute
# ─────────────────────────────────────────────────────────────────────────

def find_orders_for_status_update(conn, order_id=None, customer_name=None, status_filter=None):
    """Returns matching order rows for an update_order_status intent."""
    if order_id is not None:
        return conn.execute(
            "SELECT id, customer_name, product, quantity, quantity_unit, status FROM orders WHERE id=%s",
            (order_id,),
        ).fetchall()
    q = "SELECT id, customer_name, product, quantity, quantity_unit, status FROM orders WHERE customer_name ILIKE %s"
    params = [f"%{customer_name}%"]
    if status_filter:
        q += " AND status != 'dispatched'"
    q += " ORDER BY created_at DESC LIMIT 10"
    return conn.execute(q, tuple(params)).fetchall()


def apply_order_status_update(conn, order_id: int, new_status: str):
    conn.execute("UPDATE orders SET status=%s WHERE id=%s", (new_status, order_id))
    conn.commit()


def apply_log_production(conn, quantity: float, product: str, prod_date: str, batch_reference: str):
    conn.execute(
        "INSERT INTO production_log (quantity, product, production_date, batch_reference, created_at) "
        "VALUES (%s, %s, %s, %s, now())",
        (quantity, product, prod_date, batch_reference),
    )
    conn.commit()


def ensure_production_log_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS production_log (
            id SERIAL PRIMARY KEY,
            quantity REAL NOT NULL,
            product TEXT NOT NULL,
            production_date TEXT NOT NULL,
            batch_reference TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT now()
        )
        """
    )
    conn.commit()


# ─────────────────────────────────────────────────────────────────────────
# Pending confirmation storage
# ─────────────────────────────────────────────────────────────────────────

def store_pending_action(conn, phone_number: str, action_type: str, payload: dict, summary: str):
    # A phone number can only have one pending action at a time — replace
    # any stale one rather than piling up ambiguous confirmations.
    conn.execute("DELETE FROM whatsapp_pending_actions WHERE phone_number=%s", (phone_number,))
    expires_at = datetime.utcnow() + timedelta(minutes=PENDING_ACTION_TTL_MINUTES)
    conn.execute(
        "INSERT INTO whatsapp_pending_actions (phone_number, action_type, action_payload, summary, expires_at) "
        "VALUES (%s, %s, %s, %s, %s)",
        (phone_number, action_type, json.dumps(payload), summary, expires_at),
    )
    conn.commit()


def get_pending_action(conn, phone_number: str):
    row = conn.execute(
        "SELECT * FROM whatsapp_pending_actions WHERE phone_number=%s "
        "AND expires_at > now() ORDER BY created_at DESC LIMIT 1",
        (phone_number,),
    ).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "action_type": row["action_type"],
        "payload": json.loads(row["action_payload"]),
        "summary": row["summary"],
    }


def clear_pending_action(conn, phone_number: str):
    conn.execute("DELETE FROM whatsapp_pending_actions WHERE phone_number=%s", (phone_number,))
    conn.commit()


# ─────────────────────────────────────────────────────────────────────────
# Short-term conversational context ("that order", "it", "the same one")
# ─────────────────────────────────────────────────────────────────────────

def store_context(conn, phone_number: str, last_order_id: int = None, last_customer_name: str = None):
    """Remembers the last order/customer discussed with this phone number,
    with a short expiry — same pattern as store_pending_action. Only call
    this with at least one of the two set; both None is a no-op."""
    if last_order_id is None and not last_customer_name:
        return
    conn.execute("DELETE FROM whatsapp_context WHERE phone_number=%s", (phone_number,))
    expires_at = datetime.utcnow() + timedelta(minutes=CONTEXT_TTL_MINUTES)
    conn.execute(
        "INSERT INTO whatsapp_context (phone_number, last_order_id, last_customer_name, expires_at) "
        "VALUES (%s, %s, %s, %s)",
        (phone_number, last_order_id, last_customer_name, expires_at),
    )
    conn.commit()


def get_context(conn, phone_number: str):
    row = conn.execute(
        "SELECT last_order_id, last_customer_name FROM whatsapp_context "
        "WHERE phone_number=%s AND expires_at > now() ORDER BY created_at DESC LIMIT 1",
        (phone_number,),
    ).fetchone()
    if not row:
        return None
    if row["last_order_id"] is None and not row["last_customer_name"]:
        return None
    return {"last_order_id": row["last_order_id"], "last_customer_name": row["last_customer_name"]}


def clear_context(conn, phone_number: str):
    conn.execute("DELETE FROM whatsapp_context WHERE phone_number=%s", (phone_number,))
    conn.commit()


_AFFIRMATIVE = {
    "yes", "y", "yep", "yeah", "confirm", "confirmed", "ok", "okay",
    "haan", "ha", "theek hai", "sahi hai", "go ahead", "do it", "proceed",
}


def is_affirmative(text: str) -> bool:
    return text.strip().strip(".!").lower() in _AFFIRMATIVE
