"""Groq tool-calling orchestration for the WhatsApp bot.

Uses the same model as the rest of the app (see pages/6_financials.py /
pages/9_settings.py: `_GROQ_MODEL = "openai/gpt-oss-120b"`).
"""
import os
import json
from groq import Groq
import tools

_GROQ_MODEL = "openai/gpt-oss-120b"

_SYSTEM_PROMPT = (
    "You are a WhatsApp assistant for Reclaimr, a small manufacturing ERP. "
    "You can answer questions using ONLY the tools provided — never guess or "
    "estimate a number that isn't returned by a tool. If a question is outside "
    "what your tools cover (e.g. 'most profitable customer', 'is this transfer "
    "price optimal'), say plainly that you can't answer that yet — do not "
    "attempt to derive it. Keep replies short and WhatsApp-friendly (a few lines, "
    "no markdown tables). For any write action (updating an order, logging "
    "production), NEVER call the write tool directly — call the matching "
    "*_lookup tool instead so the app can confirm with the user first."
)

READ_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_order_status",
            "description": "Look up the status, product, quantity and dispatch date of a customer's order(s).",
            "parameters": {
                "type": "object",
                "properties": {"customer_name": {"type": "string", "description": "Customer name, full or partial"}},
                "required": ["customer_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_vendor_price_history",
            "description": "Get the last purchase price and price trend for a material from a vendor.",
            "parameters": {
                "type": "object",
                "properties": {
                    "vendor": {"type": "string"},
                    "material": {"type": "string"},
                },
                "required": ["vendor", "material"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_receivables_status",
            "description": "Check whether a customer has paid, and how much (if anything) is still owed.",
            "parameters": {
                "type": "object",
                "properties": {"customer_name": {"type": "string"}},
                "required": ["customer_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_daily_actions",
            "description": "Get today's open action items: orders due/overdue, overdue receivables/payables, "
                            "open complaints, and stagnant orders.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_revenue_summary",
            "description": "Get FY25 revenue/profit summary for a company (Rwox or Elastohorse), or both if unspecified.",
            "parameters": {
                "type": "object",
                "properties": {
                    "month": {"type": "string", "description": "Optional month, if the user asked for one"},
                    "entity": {"type": "string", "description": "'Rwox' or 'Elastohorse'; omit for both"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_order_status_lookup",
            "description": "Find the order(s) matching an update-status request. Does NOT change anything yet — "
                            "just looks up candidates so the app can confirm with the user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "integer", "description": "Order number if the user gave one, e.g. from '#47'"},
                    "customer_name": {"type": "string", "description": "Customer name if no order number was given"},
                    "new_status": {"type": "string", "description": "Target status: received, in_production, or dispatched"},
                },
                "required": ["new_status"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_production_lookup",
            "description": "Prepare a new production log entry for confirmation. Does NOT save it yet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "quantity": {"type": "number"},
                    "product": {"type": "string"},
                    "date": {"type": "string", "description": "Production date, YYYY-MM-DD; default to today if not given"},
                    "batch_reference": {"type": "string"},
                },
                "required": ["quantity", "product"],
            },
        },
    },
]


def run_agent(conn, user_text: str):
    """Runs one turn of the tool-calling loop. Returns (reply_text, pending_write)
    where pending_write is None for read-only turns, or a dict describing a
    write action that needs confirmation: {"action_type", "payload", "summary"}
    or {"clarify": "..."} if the match was ambiguous/not found."""
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        return "The bot isn't configured yet (missing GROQ_API_KEY).", None

    client = Groq(api_key=api_key)
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
    ]

    resp = client.chat.completions.create(
        model=_GROQ_MODEL,
        messages=messages,
        tools=READ_TOOL_SCHEMAS,
        tool_choice="auto",
        max_tokens=500,
        reasoning_effort="low",
    )
    msg = resp.choices[0].message

    if not msg.tool_calls:
        return (msg.content or "Sorry, I didn't get that.").strip(), None

    # Handle exactly one tool call per turn — keeps the confirm flow simple
    # and matches how a WhatsApp back-and-forth naturally works.
    call = msg.tool_calls[0]
    name = call.function.name
    try:
        args = json.loads(call.function.arguments or "{}")
    except json.JSONDecodeError:
        args = {}

    if name == "get_order_status":
        result = tools.get_order_status(conn, args.get("customer_name", ""))
    elif name == "get_vendor_price_history":
        result = tools.get_vendor_price_history(conn, args.get("vendor", ""), args.get("material", ""))
    elif name == "get_receivables_status":
        result = tools.get_receivables_status(conn, args.get("customer_name", ""))
    elif name == "get_daily_actions":
        result = tools.get_daily_actions(conn)
    elif name == "get_revenue_summary":
        result = tools.get_revenue_summary(conn, args.get("month"), args.get("entity"))
    elif name == "update_order_status_lookup":
        return _resolve_order_status_update(conn, args)
    elif name == "log_production_lookup":
        return _resolve_log_production(conn, args)
    else:
        result = "I don't have a tool for that yet."

    # Feed the tool result back so the model can phrase a natural reply.
    messages.append({"role": "assistant", "content": None, "tool_calls": [call]})
    messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
    follow_up = client.chat.completions.create(
        model=_GROQ_MODEL, messages=messages, max_tokens=300, reasoning_effort="low",
    )
    return (follow_up.choices[0].message.content or result).strip(), None


def _resolve_order_status_update(conn, args):
    order_id = args.get("order_id")
    customer_name = args.get("customer_name")
    new_status = args.get("new_status", "").strip()
    matches = tools.find_orders_for_status_update(conn, order_id=order_id, customer_name=customer_name)

    if not matches:
        who = f"order #{order_id}" if order_id else f"customer '{customer_name}'"
        return f"I couldn't find any order for {who}. Can you double-check the order number or customer name?", None
    if len(matches) > 1:
        options = "; ".join(
            f"#{m['id']} ({m['quantity']} {m['quantity_unit']} {m['product']}, currently {m['status']})"
            for m in matches
        )
        return f"Found {len(matches)} matching orders — which one? {options}", None

    m = matches[0]
    summary = (
        f"Order #{m['id']}, {m['customer_name']}, {m['quantity']} {m['quantity_unit']} {m['product']} "
        f"→ marking as {new_status}. Reply YES to confirm."
    )
    pending = {
        "action_type": "update_order_status",
        "payload": {"order_id": m["id"], "new_status": new_status},
        "summary": summary,
    }
    return summary, pending


def _resolve_log_production(conn, args):
    from datetime import date
    quantity = args.get("quantity")
    product = args.get("product", "").strip()
    prod_date = args.get("date") or str(date.today())
    batch_reference = args.get("batch_reference", "")

    if not quantity or not product:
        return "I need at least a quantity and product to log production — can you give me both?", None

    summary = (
        f"Log production: {quantity} of {product} on {prod_date}"
        + (f", batch {batch_reference}" if batch_reference else "")
        + ". Reply YES to confirm."
    )
    pending = {
        "action_type": "log_production",
        "payload": {
            "quantity": quantity, "product": product,
            "date": prod_date, "batch_reference": batch_reference,
        },
        "summary": summary,
    }
    return summary, pending
