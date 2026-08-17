"""Manual local Tally sync tool.

Run this on Reeyaz's own machine (same LAN as the computer running
Tally, with Tally open and its HTTP gateway enabled on port 9000). It is
NOT deployed anywhere and does NOT run on a schedule — invoke it by hand
whenever you want to pull outstanding balances + recent vouchers out of
Tally and push them to the app.

It never touches Postgres directly: it POSTs the parsed data to the
already-deployed whatsapp_bot service's /tally-sync endpoint, which does
the actual database write (see whatsapp_bot/main.py + tally_sync_import.py
there for the reconciliation logic, which mirrors the balance-validation
approach scripts/import_financial_data.py uses for the PDF ledger import).

Usage:
    python tally_sync/sync.py --from-date 2026-08-01 [--to-date 2026-08-17]
                               [--company "Rwox Technologies"] [--dry-run]

Config (tally_sync/.env, see .env.example):
    TALLY_URL, TALLY_COMPANY, WHATSAPP_BOT_URL, TALLY_SYNC_SECRET
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import asdict
from datetime import date, datetime

import requests
from dotenv import load_dotenv

from tally_client import build_ledger_request, build_voucher_request, send_request
from xml_to_ledger import parse_outstanding_ledgers, parse_vouchers, build_parsed_ledgers


def _parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--from-date", required=True, help="YYYY-MM-DD — pull vouchers from this date onward")
    p.add_argument("--to-date", default=None, help="YYYY-MM-DD, defaults to today")
    p.add_argument("--company", default=None, help="Overrides TALLY_COMPANY from .env")
    p.add_argument("--dry-run", action="store_true", help="Fetch + parse + print, but don't POST to whatsapp_bot")
    return p.parse_args()


def _iso_to_tally_date(iso: str) -> str:
    return datetime.strptime(iso, "%Y-%m-%d").strftime("%Y%m%d")


def main():
    load_dotenv()
    args = _parse_args()

    tally_url = os.getenv("TALLY_URL", "http://localhost:9000")
    company = args.company or os.getenv("TALLY_COMPANY") or None
    bot_url = os.getenv("WHATSAPP_BOT_URL")
    secret = os.getenv("TALLY_SYNC_SECRET")

    to_date_iso = args.to_date or date.today().isoformat()
    from_tally, to_tally = _iso_to_tally_date(args.from_date), _iso_to_tally_date(to_date_iso)

    if not args.dry_run and (not bot_url or not secret):
        raise SystemExit(
            "WHATSAPP_BOT_URL and TALLY_SYNC_SECRET must be set in tally_sync/.env "
            "(or pass --dry-run to just fetch/parse/print without syncing)."
        )

    print(f"Connecting to Tally at {tally_url} "
          f"(company={company or 'whichever is currently open'})...")

    try:
        ledger_xml = send_request(tally_url, build_ledger_request(company))
        voucher_xml = send_request(tally_url, build_voucher_request(from_tally, to_tally, company))
    except requests.RequestException as e:
        raise SystemExit(
            f"Couldn't reach Tally's HTTP gateway at {tally_url} ({e}).\n"
            "Check that Tally is open, on the same machine/network, and that its HTTP "
            "gateway is enabled (Gateway of Tally > F1 Help > Settings > Connectivity)."
        )

    outstanding = parse_outstanding_ledgers(ledger_xml)
    vouchers = parse_vouchers(voucher_xml)
    ledgers = build_parsed_ledgers(outstanding, vouchers, company, args.from_date, to_date_iso)

    if not ledgers:
        print("Nothing to sync — no outstanding Sundry Debtor/Creditor balances and no "
              "matching vouchers (Purchase/SALE GST/Payment/Receipt) found in that date range.")
        return

    print(f"\nParsed {len(ledgers)} part{'y' if len(ledgers) == 1 else 'ies'} from Tally "
          f"(vouchers {args.from_date} to {to_date_iso}):")
    for l in ledgers:
        bal = f"Rs. {l.closing_balance:,.2f} ({'we owe them' if l.closing_side == 'To' else 'they owe us'})" \
            if l.closing_balance is not None else "no outstanding balance in Tally"
        print(f"  - {l.party_name}: {len(l.rows)} voucher row(s), Tally's live closing balance: {bal}")

    if args.dry_run:
        print("\n--dry-run set — not sending to whatsapp_bot.")
        return

    payload = {
        "company": company,
        "synced_from_date": args.from_date,
        "synced_to_date": to_date_iso,
        "ledgers": [asdict(l) for l in ledgers],
    }

    print(f"\nPOSTing to {bot_url}/tally-sync ...")
    resp = requests.post(
        f"{bot_url.rstrip('/')}/tally-sync",
        json=payload,
        headers={"X-Tally-Sync-Secret": secret},
        timeout=60,
    )
    if resp.status_code == 401:
        raise SystemExit("Rejected: TALLY_SYNC_SECRET doesn't match what's set on the whatsapp_bot service.")
    resp.raise_for_status()
    result = resp.json()

    print("\n" + "=" * 70)
    print("SYNC RESULT")
    print("=" * 70)
    for r in result.get("parties", []):
        print(f"\n{r['party_name']} ({r.get('company') or 'company not set'})")
        print(f"  new payable rows added:    {r['n_payables_added']}")
        print(f"  new receivable rows added: {r['n_receivables_added']}")
        print(f"  new payment/receipt rows:  {r['n_payments_added']}")
        print(f"  net open payable (DB):     Rs. {r['net_open_payable']:,.2f}")
        print(f"  net open receivable (DB):  Rs. {r['net_open_receivable']:,.2f}")
        if r.get("tally_closing_balance") is not None:
            side = "we owe them" if r["tally_closing_side"] == "To" else "they owe us"
            print(f"  Tally's stated closing balance: Rs. {r['tally_closing_balance']:,.2f} ({side})")
        if r.get("mismatch"):
            print(f"  *** MISMATCH FLAGGED: Rs. {r['diff']:,.2f} difference between the database's "
                  f"net open balance and Tally's stated closing balance — not auto-adjusted, "
                  f"needs a manual look. ***")
        else:
            print("  balance reconciles with Tally within tolerance.")

    if result.get("warnings"):
        print("\nWarnings:")
        for w in result["warnings"]:
            print(f"  - {w}")

    n_mismatch = sum(1 for r in result.get("parties", []) if r.get("mismatch"))
    print(f"\nDone. {len(result.get('parties', []))} part(y/ies) synced, {n_mismatch} flagged with a balance mismatch.")


if __name__ == "__main__":
    sys.exit(main() or 0)
