"""FastAPI service for the Reclaimr WhatsApp bot.

Deployed as its own Railway service (separate root directory from the
Streamlit app) but pointed at the SAME Postgres database via DATABASE_URL.
See README section "WhatsApp bot service" for deployment notes.
"""
import os
from fastapi import FastAPI, Request, Response
from dotenv import load_dotenv

import db
import tools
import groq_agent
from whatsapp_api import send_text

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN")

app = FastAPI(title="Reclaimr WhatsApp Bot")

_conn = None


def get_conn():
    global _conn
    if _conn is None:
        _conn = db.connect(DATABASE_URL)
        db.ensure_whatsapp_tables(_conn)
        tools.ensure_production_log_table(_conn)
    return _conn


@app.get("/")
def health():
    return {"status": "ok"}


@app.get("/webhook")
def verify_webhook(request: Request):
    """Meta's verification handshake, run once when you save the webhook
    URL in the Meta App dashboard."""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN and VERIFY_TOKEN:
        return Response(content=challenge, media_type="text/plain")
    return Response(status_code=401)


@app.post("/webhook")
async def receive_message(request: Request):
    payload = await request.json()
    conn = get_conn()

    sender_phone, text = _extract_message(payload)
    if not sender_phone or text is None:
        # Not a user text message (e.g. a status/delivery callback) — ack and ignore.
        return {"status": "ignored"}

    phone_row = conn.execute(
        "SELECT approved FROM whatsapp_numbers WHERE phone_number=%s", (sender_phone,)
    ).fetchone()

    if not phone_row:
        conn.execute(
            "INSERT INTO whatsapp_numbers (phone_number, approved) VALUES (%s, FALSE) "
            "ON CONFLICT (phone_number) DO NOTHING",
            (sender_phone,),
        )
        conn.commit()
        send_text(sender_phone, "You're not registered yet — ask the app owner to approve your number in Settings.")
        return {"status": "pending_approval"}

    if not phone_row["approved"]:
        send_text(sender_phone, "Your number is still waiting for approval from the app owner.")
        return {"status": "pending_approval"}

    reply = handle_message(conn, sender_phone, text)
    send_text(sender_phone, reply)
    return {"status": "handled"}


def handle_message(conn, phone: str, text: str) -> str:
    """Core routing logic, separated from the webhook handler so it can be
    unit-tested without a live HTTP request."""
    pending = tools.get_pending_action(conn, phone)
    if pending:
        if tools.is_affirmative(text):
            return _execute_pending(conn, phone, pending)
        # Anything else cancels the stale pending action and is treated as
        # a fresh message rather than silently ignored.
        tools.clear_pending_action(conn, phone)

    reply, pending_write = groq_agent.run_agent(conn, text)
    if pending_write and "clarify" not in pending_write:
        tools.store_pending_action(
            conn, phone,
            pending_write["action_type"], pending_write["payload"], pending_write["summary"],
        )
    return reply


def _execute_pending(conn, phone: str, pending: dict) -> str:
    payload = pending["payload"]
    if pending["action_type"] == "update_order_status":
        tools.apply_order_status_update(conn, payload["order_id"], payload["new_status"])
        tools.clear_pending_action(conn, phone)
        return f"Done — order #{payload['order_id']} marked as {payload['new_status']}."
    if pending["action_type"] == "log_production":
        tools.apply_log_production(
            conn, payload["quantity"], payload["product"], payload["date"], payload.get("batch_reference", "")
        )
        tools.clear_pending_action(conn, phone)
        return f"Done — logged {payload['quantity']} of {payload['product']} on {payload['date']}."
    tools.clear_pending_action(conn, phone)
    return "Something went wrong resolving that confirmation — please try again."


def _extract_message(payload: dict):
    """Pulls (sender_phone, text) out of Meta's webhook payload shape.
    Returns (None, None) for anything that isn't an inbound text message."""
    try:
        entry = payload["entry"][0]
        change = entry["changes"][0]
        value = change["value"]
        messages = value.get("messages")
        if not messages:
            return None, None
        message = messages[0]
        sender = "+" + message["from"].lstrip("+")
        if message.get("type") != "text":
            return sender, None
        text = message["text"]["body"]
        return sender, text
    except (KeyError, IndexError, TypeError):
        return None, None


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True)
