"""Manual smoke tests against the real (migrated) Postgres data — no live
webhook needed. Run with:

    python test_tools.py

Requires DATABASE_URL (and GROQ_API_KEY for the confirm-flow tests) in
whatsapp_bot/.env. Prints results rather than asserting exact values,
since the data is live/production — eyeball the output against what you
know is true in the app.
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Windows consoles default to cp1252, which can't print the ₹ sign used in
# revenue-summary output — force UTF-8 so this runs without extra setup.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import db
import tools
import main as bot_main

DATABASE_URL = os.getenv("DATABASE_URL")


def _conn():
    conn = db.connect(DATABASE_URL)
    db.ensure_whatsapp_tables(conn)
    tools.ensure_production_log_table(conn)
    return conn


def test_read_tools(conn):
    print("\n=== get_order_status ===")
    row = conn.execute("SELECT customer_name FROM orders LIMIT 1").fetchone()
    if row:
        print(tools.get_order_status(conn, row["customer_name"]))
    else:
        print("(no orders in DB to test against)")

    print("\n=== get_receivables_status ===")
    row = conn.execute("SELECT customer_name FROM receivables LIMIT 1").fetchone()
    if row:
        print(tools.get_receivables_status(conn, row["customer_name"]))
    else:
        print("(no receivables in DB to test against)")

    print("\n=== get_vendor_price_history ===")
    row = conn.execute("SELECT supplier, item FROM procurement LIMIT 1").fetchone()
    if row:
        print(tools.get_vendor_price_history(conn, row["supplier"], row["item"]))
    else:
        print("(no procurement rows in DB to test against)")

    print("\n=== get_daily_actions ===")
    print(tools.get_daily_actions(conn))

    print("\n=== get_revenue_summary ===")
    print(tools.get_revenue_summary(conn, entity="Rwox"))
    print(tools.get_revenue_summary(conn))


def test_write_confirmation_flow(conn):
    print("\n=== write-confirmation flow: ambiguous match ===")
    test_phone = "+910000000000"
    tools.clear_pending_action(conn, test_phone)

    # Pick a customer name likely to have >1 open order, else fabricate the
    # ambiguity check directly against find_orders_for_status_update.
    row = conn.execute(
        "SELECT customer_name, COUNT(*) c FROM orders GROUP BY customer_name HAVING COUNT(*) > 1 LIMIT 1"
    ).fetchone()
    if row:
        matches = tools.find_orders_for_status_update(conn, customer_name=row["customer_name"])
        print(f"customer '{row['customer_name']}' -> {len(matches)} matches (should ask to clarify, not guess)")
        assert len(matches) > 1
    else:
        # No existing customer happens to have 2+ orders — insert two
        # temporary rows under a throwaway name so the ambiguous-match
        # path (find matches -> clarify, not guess) is still exercised
        # against the real schema, then clean up.
        print("(no customer with multiple orders found — inserting a temporary pair to test the path)")
        test_customer = "__wa_bot_test_customer__"
        company_id = conn.execute("SELECT id FROM companies LIMIT 1").fetchone()["id"]
        conn.execute(
            "INSERT INTO orders (company_id, customer_name, product, quantity, quantity_unit, rate, "
            "expected_dispatch_date, status, created_at) "
            "VALUES (%s,%s,'Test Product A',10,'kg',0,CURRENT_DATE,'received', now()), "
            "(%s,%s,'Test Product B',20,'kg',0,CURRENT_DATE,'received', now())",
            (company_id, test_customer, company_id, test_customer),
        )
        conn.commit()
        try:
            matches = tools.find_orders_for_status_update(conn, customer_name=test_customer)
            print(f"customer '{test_customer}' -> {len(matches)} matches (should ask to clarify, not guess)")
            assert len(matches) == 2
            reply = bot_main.handle_message(conn, "+910000000001",
                                             f"mark {test_customer}'s order as dispatched")
            print("Bot reply to ambiguous write request:", reply)
        finally:
            conn.execute("DELETE FROM orders WHERE customer_name=%s", (test_customer,))
            conn.commit()

    print("\n=== write-confirmation flow: single match -> store -> confirm ===")
    single = conn.execute("SELECT id, customer_name, product FROM orders LIMIT 1").fetchone()
    if single:
        summary = f"Order #{single['id']} test confirmation. Reply YES to confirm."
        tools.store_pending_action(conn, test_phone, "update_order_status",
                                    {"order_id": single["id"], "new_status": single.get("status", "received")},
                                    summary)
        pending = tools.get_pending_action(conn, test_phone)
        print("Stored pending action:", pending["summary"])
        assert pending is not None
        assert tools.is_affirmative("yes") and tools.is_affirmative("haan") and tools.is_affirmative("Confirm.")
        assert not tools.is_affirmative("what?")
        tools.clear_pending_action(conn, test_phone)
        print("Confirmed variants (yes/haan/confirm) recognized; non-affirmative correctly rejected.")
    else:
        print("(no orders in DB — skipping single-match confirm test)")


if __name__ == "__main__":
    if not DATABASE_URL:
        print("DATABASE_URL not set in whatsapp_bot/.env — cannot run.")
        raise SystemExit(1)
    conn = _conn()
    test_read_tools(conn)
    test_write_confirmation_flow(conn)
    print("\nAll smoke tests completed.")
