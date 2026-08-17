"""Parses Tally's Collection-export XML responses into the same
ParsedLedger/LedgerRow shape utils/ledger_parser.py produces from the
vendor/customer ledger PDFs, so the whatsapp_bot /tally-sync endpoint can
reconcile Tally-sourced data with the exact same validation approach the
PDF importer uses — no separate parsing/validation logic duplicated here.

Tally's XML is not strict XML: it emits bare unescaped '&' inside
NARRATION/NAME text fairly often, and attribute-less empty tags
(e.g. <CLOSINGBALANCE/>) are common. xml.etree chokes on the former, so we
patch obviously-bare ampersands before parsing rather than write a whole
tolerant hand-rolled parser.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.ledger_parser import LedgerRow, ParsedLedger  # noqa: E402

_DEBTOR_CREDITOR_PARENTS = {"sundry debtors", "sundry creditors"}

# Matches '&' not already part of a real entity (&amp; &lt; &gt; &quot;
# &apos; or a numeric &#123;/&#x1F;) — Tally routinely emits raw '&' inside
# NARRATION text (e.g. "Ram & Sons") which breaks strict XML parsing.
_BARE_AMPERSAND_RE = re.compile(r"&(?!amp;|lt;|gt;|quot;|apos;|#\d+;|#x[0-9A-Fa-f]+;)")


def _clean_xml(text: str) -> str:
    text = _BARE_AMPERSAND_RE.sub("&amp;", text)
    # Tally sometimes emits stray control characters (e.g. from a NARRATION
    # field pasted from Excel) that are illegal in XML 1.0.
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    return text


def _text(el, tag: str) -> str | None:
    child = el.find(tag)
    if child is None or child.text is None:
        return None
    return child.text.strip() or None


def _to_iso_date(tally_date: str) -> str | None:
    """Tally dates come back as YYYYMMDD."""
    if not tally_date or len(tally_date) != 8 or not tally_date.isdigit():
        return None
    return f"{tally_date[0:4]}-{tally_date[4:6]}-{tally_date[6:8]}"


def parse_outstanding_ledgers(xml_text: str) -> dict[str, dict]:
    """Returns {ledger_name: {"parent": str, "closing_balance": float,
    "closing_side": "To"|"By"}}, filtered to Sundry Debtors/Sundry
    Creditors ledgers only.

    Sign convention (per Tally's own XML export): CLOSINGBALANCE is
    positive for a debit balance, negative for a credit balance. In the
    ParsedLedger convention (see utils/ledger_parser.py) a debit balance
    is "By" (they owe us) and a credit balance is "To" (we owe them).
    """
    root = ET.fromstring(_clean_xml(xml_text))
    out: dict[str, dict] = {}
    for ledger_el in root.iter("LEDGER"):
        name = ledger_el.get("NAME") or _text(ledger_el, "NAME")
        parent = _text(ledger_el, "PARENT")
        if not name or not parent or parent.strip().lower() not in _DEBTOR_CREDITOR_PARENTS:
            continue
        raw = _text(ledger_el, "CLOSINGBALANCE")
        if raw is None:
            continue
        value = float(raw.replace(",", ""))
        out[name] = {
            "parent": parent,
            "closing_balance": abs(value),
            "closing_side": "By" if value >= 0 else "To",
        }
    return out


# Maps Tally's own VOUCHERTYPENAME straight through — these are the exact
# names Reeyaz's Tally is configured with (confirmed against the printed
# vendor/customer ledger PDFs, which show the same "SALE GST" / "Purchase"
# / "Payment" / "Receipt" vocabulary utils/ledger_parser.py already parses).
_RELEVANT_VCH_TYPES = {"sale gst", "sales", "purchase", "payment", "receipt"}


def parse_vouchers(xml_text: str) -> list[dict]:
    """Returns a flat list of {date, vch_type, vch_no, party, amount,
    side} — one per voucher, already resolved to the party ledger's own
    Dr/Cr side (side = "To" for a debit entry, "By" for a credit entry,
    matching the printed-ledger convention utils/ledger_parser.py uses)."""
    root = ET.fromstring(_clean_xml(xml_text))
    rows = []
    for v in root.iter("VOUCHER"):
        if (_text(v, "ISCANCELLED") or "No").strip().lower() == "yes":
            continue
        vch_type_raw = _text(v, "VOUCHERTYPENAME") or ""
        if vch_type_raw.strip().lower() not in _RELEVANT_VCH_TYPES:
            continue
        date = _to_iso_date(_text(v, "DATE") or "")
        vch_no = _text(v, "VOUCHERNUMBER")
        party = _text(v, "PARTYLEDGERNAME")
        if not date or not party:
            continue

        # Find the party's own line among the voucher's ledger entries —
        # that's the one whose sign tells us Dr ("To") vs Cr ("By").
        amount = None
        side = None
        for entry in v.findall("ALLLEDGERENTRIES.LIST"):
            entry_ledger = _text(entry, "LEDGERNAME")
            if entry_ledger != party:
                continue
            raw_amt = _text(entry, "AMOUNT")
            is_positive = (_text(entry, "ISDEEMEDPOSITIVE") or "No").strip().lower() == "yes"
            if raw_amt is None:
                continue
            amount = abs(float(raw_amt.replace(",", "")))
            side = "To" if is_positive else "By"
            break
        if amount is None:
            continue

        rows.append({
            "date": date,
            "vch_type": "SALE GST" if vch_type_raw.strip().lower() in ("sale gst", "sales") else vch_type_raw.strip().title(),
            "vch_no": vch_no,
            "party": party,
            "amount": amount,
            "side": side,
        })
    return rows


def build_parsed_ledgers(
    outstanding: dict[str, dict],
    vouchers: list[dict],
    company: str | None,
    period_start: str | None,
    period_end: str | None,
) -> list[ParsedLedger]:
    """Groups vouchers by party ledger and produces one ParsedLedger per
    party that has either an outstanding balance or new voucher activity
    — the same object shape scripts/import_financial_data.py's
    _reconcile_and_insert() consumes from the PDF importer, so the
    whatsapp_bot endpoint can share that validation logic."""
    parties = set(outstanding.keys()) | {v["party"] for v in vouchers}
    results = []
    for party in sorted(parties):
        rows = [
            LedgerRow(
                date=v["date"], side=v["side"] or "To", particulars=party,
                vch_type=v["vch_type"], vch_no=v["vch_no"], amount=v["amount"],
            )
            for v in vouchers if v["party"] == party
        ]
        info = outstanding.get(party, {})
        results.append(ParsedLedger(
            source_file=f"tally_sync:{party}",
            company=company,
            party_name=party,
            period_start=period_start,
            period_end=period_end,
            rows=rows,
            closing_balance=info.get("closing_balance"),
            closing_side=info.get("closing_side"),
        ))
    return results
