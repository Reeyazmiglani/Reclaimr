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


def download_media(media_id: str) -> bytes | None:
    """Downloads a WhatsApp media attachment (e.g. a voice note) by its
    media ID. Two-step Graph API flow: look up the temporary CDN URL, then
    fetch the bytes from it. Returns None on any failure."""
    token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    if not token:
        print("[whatsapp_api] Missing WHATSAPP_ACCESS_TOKEN — can't download media")
        return None

    headers = {"Authorization": f"Bearer {token}"}
    try:
        meta_resp = requests.get(
            f"https://graph.facebook.com/{_GRAPH_VERSION}/{media_id}",
            headers=headers, timeout=15,
        )
        if meta_resp.status_code >= 300:
            print(f"[whatsapp_api] Media lookup failed ({meta_resp.status_code}): {meta_resp.text}")
            return None
        download_url = meta_resp.json().get("url")
        if not download_url:
            print(f"[whatsapp_api] Media lookup response had no url: {meta_resp.text}")
            return None

        file_resp = requests.get(download_url, headers=headers, timeout=30)
        if file_resp.status_code >= 300:
            print(f"[whatsapp_api] Media download failed ({file_resp.status_code})")
            return None
        return file_resp.content
    except requests.RequestException as e:
        print(f"[whatsapp_api] Media download raised: {e}")
        return None
