"""Thin wrapper around the WhatsApp Cloud API's /messages endpoint."""
import os
import requests

_GRAPH_VERSION = "v20.0"


def send_text(to_phone: str, body: str) -> bool:
    """Sends a plain-text WhatsApp message. Returns True on success; logs
    and returns False on failure rather than raising — a failed reply
    shouldn't crash the webhook handler (Meta will just retry delivery)."""
    token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    if not token or not phone_number_id:
        print(f"[whatsapp_api] Missing WHATSAPP_ACCESS_TOKEN/WHATSAPP_PHONE_NUMBER_ID — "
              f"would have sent to {to_phone}: {body}")
        return False

    url = f"https://graph.facebook.com/{_GRAPH_VERSION}/{phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": body},
    }
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        if resp.status_code >= 300:
            print(f"[whatsapp_api] Send failed ({resp.status_code}): {resp.text}")
            return False
        return True
    except requests.RequestException as e:
        print(f"[whatsapp_api] Send raised: {e}")
        return False
