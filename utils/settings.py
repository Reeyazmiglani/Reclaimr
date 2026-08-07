"""Simple key-value settings store, backed by the `settings` table.

Not per-user (no auth exists in this app yet) — one shared set of app-wide
settings: dark mode, overdue-credit threshold, low-stock thresholds, and
per-company details used on the dispatch note.
"""
import json

DEFAULT_OVERDUE_DAYS = 45
DEFAULT_STOCK_THRESHOLDS = {
    "Purple Material": 200.0,
    "Wax": 150.0,
    "MC": 100.0,
    "Finished Goods (kg)": 300.0,
}
DEFAULT_COMPANY_DETAILS = {
    "Rwox": {"address": "", "gstin": "", "contact": ""},
    "Elastohorse": {"address": "", "gstin": "", "contact": ""},
}


def get_setting(conn, key: str, default: str = "") -> str:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row and row["value"] is not None else default


def set_setting(conn, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()


def get_json_setting(conn, key: str, default: dict) -> dict:
    raw = get_setting(conn, key, "")
    if not raw:
        return dict(default)
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return dict(default)


def set_json_setting(conn, key: str, value: dict) -> None:
    set_setting(conn, key, json.dumps(value))


def get_overdue_days(conn) -> int:
    try:
        return int(float(get_setting(conn, "overdue_days", str(DEFAULT_OVERDUE_DAYS))))
    except (ValueError, TypeError):
        return DEFAULT_OVERDUE_DAYS


def get_stock_thresholds(conn) -> dict:
    return get_json_setting(conn, "stock_thresholds", DEFAULT_STOCK_THRESHOLDS)


def set_stock_thresholds(conn, thresholds: dict) -> None:
    set_json_setting(conn, "stock_thresholds", thresholds)


def get_company_details(conn) -> dict:
    return get_json_setting(conn, "company_details", DEFAULT_COMPANY_DETAILS)


def set_company_details(conn, details: dict) -> None:
    set_json_setting(conn, "company_details", details)


def get_dark_mode(conn) -> bool:
    return get_setting(conn, "dark_mode", "0") == "1"


def set_dark_mode(conn, value: bool) -> None:
    set_setting(conn, "dark_mode", "1" if value else "0")
