"""
One-time (re-runnable) importer for data_import/:
  Part 2 — Balance Sheet / Trading Account / P&L statements -> financial_snapshots
  Part 3 — vendor/customer running ledgers -> payables / receivables / payments

Safe to re-run: financial_snapshots is upserted on (company_id, snapshot_date);
ledger rows are cleared and re-inserted per source_file before each run so
re-running never duplicates.

Usage:
    python scripts/import_financial_data.py [DATABASE_URL]
(DATABASE_URL defaults to the DATABASE_URL env var / .env file.)
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from db.schema import init_db
from utils.statement_parser import parse_pdf, ParsedStatement
from utils.ledger_parser import parse_ledger_pdf, ParsedLedger

DATA_DIR = Path(__file__).resolve().parent.parent / "data_import"

STATEMENT_FILES = [
    "rwox bs 310325.pdf",
    "elasto bs 310325.pdf",
    "RWOX.pdf",
    "BALANCE SHEET RWOX TECH 31-3-24141.pdf",
    "BALANCE SHEET RWOX  310323.pdf",
    "RWOX BALANCE SHEET 31 MARCH 2022534.pdf",
    "RWOX BALANCE SHEET31 MARCH 2021257.pdf",
]

LEDGER_FILES = [
    "ALSTRONG S CR.pdf",
    "DEV RUBBER.pdf",
    "GRP LTD.pdf",
    "H P L ADDITIVES LTD.pdf",
    "NIRMAN TRADING CO.pdf",
    "SPEEDWAYS.pdf",
]

OUT_OF_SCOPE = ["Rwox DCF Model.xlsx", "RWOX DCF Questions.pdf"]


def import_statements(conn) -> list[ParsedStatement]:
    company_ids = {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM companies").fetchall()}
    results = []
    for fname in STATEMENT_FILES:
        path = DATA_DIR / fname
        if not path.exists():
            print(f"  [MISSING] {fname}")
            continue
        r = parse_pdf(str(path))
        results.append(r)
        if not r.import_ok:
            continue
        co_id = company_ids.get(r.company)
        if not co_id:
            r.warnings.append(f"Unknown company '{r.company}' — not in companies table")
            continue
        conn.execute(
            """
            INSERT INTO financial_snapshots
                (company_id, snapshot_date, cash_balance, receivables, payables, equity,
                 loans, fixed_assets, closing_stock, sales, purchases, gross_profit,
                 net_profit, total_liabilities, total_assets, is_balanced, source_file, notes)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (company_id, snapshot_date) DO UPDATE SET
                cash_balance=EXCLUDED.cash_balance, receivables=EXCLUDED.receivables,
                payables=EXCLUDED.payables, equity=EXCLUDED.equity, loans=EXCLUDED.loans,
                fixed_assets=EXCLUDED.fixed_assets, closing_stock=EXCLUDED.closing_stock,
                sales=EXCLUDED.sales, purchases=EXCLUDED.purchases,
                gross_profit=EXCLUDED.gross_profit, net_profit=EXCLUDED.net_profit,
                total_liabilities=EXCLUDED.total_liabilities, total_assets=EXCLUDED.total_assets,
                is_balanced=EXCLUDED.is_balanced, source_file=EXCLUDED.source_file,
                notes=EXCLUDED.notes
            """,
            (co_id, r.statement_date, r.cash_bank, r.sundry_debtors, r.sundry_creditors,
             r.capital_account, r.loans, r.fixed_assets, r.closing_stock, r.sales,
             r.purchases, r.gross_profit, r.net_profit, r.total_liabilities, r.total_assets,
             r.is_balanced, Path(r.source_file).name,
             f"Imported from {Path(r.source_file).name}"),
        )
    conn.commit()
    return results


def _reconcile_and_insert(conn, ledger: ParsedLedger) -> dict:
    """Purchase rows -> payables, Sale rows -> receivables, then FIFO-match
    Payment rows against open payables and Receipt rows against open
    receivables, inserting one `payments` row per (settlement, invoice)
    pairing consumed.

    Matching is done in two passes (all invoices created first, *then* all
    settlements applied against the full set oldest-first) rather than one
    pass in ledger row order — a receipt can legitimately appear in the
    printed ledger before the sale invoice it ultimately covers (e.g. an
    advance), so gating a settlement to only invoices already inserted at
    that point in the row stream under-matches and leaves a real invoice
    looking falsely open."""
    fname = Path(ledger.source_file).name
    party = ledger.party_name
    company = ledger.company

    # clear any previous import of this exact file so re-runs don't duplicate
    conn.execute("DELETE FROM payments WHERE source_file=%s", (fname,))
    conn.execute("DELETE FROM payables WHERE source_file=%s", (fname,))
    conn.execute("DELETE FROM receivables WHERE source_file=%s", (fname,))

    is_sale_side_ledger = any(row.vch_type == "SALE GST" for row in ledger.rows)

    payable_invoices = []   # [{id, remaining}]
    receivable_invoices = []
    settlements = []        # [(kind, row)] kind = "Payment" | "Receipt", in ledger order
    total_payable_amt = total_receivable_amt = 0.0

    # Pass 1: create every invoice (Purchase -> payable, Sale -> receivable)
    for row in ledger.rows:
        if row.vch_type == "Purchase":
            cur = conn.execute(
                "INSERT INTO payables (vendor_name, description, amount, date, notes, "
                "status, company, voucher_no, source_file) "
                "VALUES (%s,%s,%s,%s,%s,'outstanding',%s,%s,%s) RETURNING id",
                (party, row.particulars, row.amount, row.date,
                 f"Imported ledger entry ({row.vch_type} {row.vch_no or ''})".strip(),
                 company, row.vch_no, fname),
            )
            new_id = cur.fetchone()["id"]
            payable_invoices.append({"id": new_id, "remaining": row.amount, "date": row.date})
            total_payable_amt += row.amount

        elif row.vch_type == "SALE GST" or (
            row.particulars.lower() == "opening balance" and row.side == "To" and is_sale_side_ledger
        ):
            cur = conn.execute(
                "INSERT INTO receivables (customer_name, company, reference, amount, date, "
                "notes, status, voucher_no, source_file) "
                "VALUES (%s,%s,%s,%s,%s,%s,'outstanding',%s,%s) RETURNING id",
                (party, company, row.particulars, row.amount, row.date,
                 f"Imported ledger entry ({row.vch_type or 'Opening Balance'} {row.vch_no or ''})".strip(),
                 row.vch_no, fname),
            )
            new_id = cur.fetchone()["id"]
            receivable_invoices.append({"id": new_id, "remaining": row.amount, "date": row.date})
            total_receivable_amt += row.amount

        elif row.vch_type in ("Payment", "Receipt"):
            settlements.append((row.vch_type, row))

    payable_invoices.sort(key=lambda i: i["date"] or "")
    receivable_invoices.sort(key=lambda i: i["date"] or "")

    # Pass 2: apply settlements FIFO (oldest invoice first) against the
    # *complete* invoice set, in the order they appear in the ledger
    n_payments = 0
    for kind, row in settlements:
        invoices = payable_invoices if kind == "Payment" else receivable_invoices
        pay_type = "payable" if kind == "Payment" else "receivable"
        remaining = row.amount
        for inv in invoices:
            if remaining <= 0:
                break
            if inv["remaining"] <= 0:
                continue
            applied = min(inv["remaining"], remaining)
            conn.execute(
                "INSERT INTO payments (type, reference_id, payment_date, amount_paid, notes, source_file) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (pay_type, inv["id"], row.date, applied,
                 f"Matched from ledger {kind.lower()} (Vch {row.vch_no or 'n/a'})", fname),
            )
            inv["remaining"] -= applied
            remaining -= applied
            n_payments += 1
        if remaining > 0.01:
            conn.execute(
                "INSERT INTO payments (type, reference_id, payment_date, amount_paid, notes, source_file) "
                "VALUES (%s,0,%s,%s,%s,%s)",
                (pay_type, row.date, remaining,
                 f"Unmatched against any open invoice at import time (advance {kind.lower()})", fname),
            )
            n_payments += 1

    net_open_payable = sum(i["remaining"] for i in payable_invoices)
    net_open_receivable = sum(i["remaining"] for i in receivable_invoices)

    # Reconcile against the ledger's own stated closing balance. Some
    # ledgers (Alstrong) carry a running balance that predates/exceeds what
    # the visible Purchase/Sale rows account for — rather than silently
    # storing a payable total that disagrees with the audited closing
    # figure, add one explicit brought-forward adjusting entry so the
    # database total matches the source document exactly, and say so.
    adjustment_note = None
    stated = ledger.closing_balance or 0.0
    stated_signed = stated if ledger.closing_side == "To" else -stated  # +ve = we owe them
    computed_signed = net_open_payable - net_open_receivable
    diff = round(stated_signed - computed_signed, 2)
    if abs(diff) > 1.0:
        if diff > 0:
            conn.execute(
                "INSERT INTO payables (vendor_name, description, amount, date, notes, "
                "status, company, voucher_no, source_file) "
                "VALUES (%s,%s,%s,%s,%s,'outstanding',%s,NULL,%s)",
                (party, "Brought-forward balance (not itemised as a Purchase row in the ledger)",
                 diff, ledger.period_start, "Adjusting entry so imported total matches the "
                 "ledger's stated closing balance", company, fname),
            )
            net_open_payable += diff
        else:
            conn.execute(
                "INSERT INTO receivables (customer_name, company, reference, amount, date, "
                "notes, status, voucher_no, source_file) "
                "VALUES (%s,%s,%s,%s,%s,%s,'outstanding',NULL,%s)",
                (party, company, "Brought-forward balance", -diff, ledger.period_start,
                 "Adjusting entry so imported total matches the ledger's stated closing balance", fname),
            )
            net_open_receivable += -diff
        adjustment_note = (
            f"Added a {'payable' if diff>0 else 'receivable'} adjusting entry of "
            f"Rs. {abs(diff):,.2f} so the imported balance matches the ledger's stated closing "
            f"balance — the Payment/Receipt rows alone didn't fully account for it "
            f"(no per-invoice reference exists in the source for this ledger)."
        )

    # mark final status on whatever's left outstanding
    for inv in payable_invoices:
        status = "paid" if inv["remaining"] <= 0.01 else "outstanding"
        conn.execute("UPDATE payables SET status=%s WHERE id=%s", (status, inv["id"]))
    for inv in receivable_invoices:
        status = "paid" if inv["remaining"] <= 0.01 else "outstanding"
        conn.execute("UPDATE receivables SET status=%s WHERE id=%s", (status, inv["id"]))

    conn.commit()
    return {
        "party": party, "company": company, "file": fname,
        "n_payables": len(payable_invoices), "n_receivables": len(receivable_invoices),
        "n_payments": n_payments,
        "total_payable_amt": total_payable_amt, "total_receivable_amt": total_receivable_amt,
        "net_open_payable": net_open_payable, "net_open_receivable": net_open_receivable,
        "stated_closing_balance": ledger.closing_balance,
        "stated_closing_side": ledger.closing_side,  # "To" = we owe them, "By" = they owe us
        "ledger_balanced": ledger.is_balanced,
        "adjustment_note": adjustment_note,
    }


def import_ledgers(conn) -> list[dict]:
    summaries = []
    for fname in LEDGER_FILES:
        path = DATA_DIR / fname
        if not path.exists():
            print(f"  [MISSING] {fname}")
            continue
        ledger = parse_ledger_pdf(str(path))
        summary = _reconcile_and_insert(conn, ledger)
        summary["warnings"] = ledger.warnings
        summaries.append(summary)
    return summaries


def main():
    load_dotenv()
    db_url = sys.argv[1] if len(sys.argv) > 1 else os.getenv("DATABASE_URL")
    if not db_url:
        raise SystemExit("DATABASE_URL not set (pass as arg or set in .env)")

    conn = init_db(db_url)

    print("=" * 78)
    print("PART 2 — BALANCE SHEET / P&L STATEMENTS")
    print("=" * 78)
    stmt_results = import_statements(conn)
    for r in stmt_results:
        fname = Path(r.source_file).name
        status = "IMPORTED" if r.import_ok else "FAILED / SKIPPED"
        print(f"\n[{status}] {fname}")
        print(f"  company={r.company}  statement_date={r.statement_date}")
        print(f"  total_liabilities={r.total_liabilities}  total_assets={r.total_assets}  "
              f"balanced={r.is_balanced}  diff={r.balance_diff}")
        if r.warnings:
            for w in r.warnings:
                print(f"  WARNING: {w}")

    print("\n" + "=" * 78)
    print("PART 3 — VENDOR / CUSTOMER LEDGERS")
    print("=" * 78)
    ledger_summaries = import_ledgers(conn)
    for s in ledger_summaries:
        print(f"\n{s['file']}  ({s['company']} <-> {s['party']})")
        print(f"  payable invoices: {s['n_payables']}  (total {s['total_payable_amt']:,.2f})")
        print(f"  receivable invoices: {s['n_receivables']}  (total {s['total_receivable_amt']:,.2f})")
        print(f"  payment/receipt rows written: {s['n_payments']}")
        print(f"  open payable after matching: {s['net_open_payable']:,.2f}")
        print(f"  open receivable after matching: {s['net_open_receivable']:,.2f}")
        print(f"  ledger's own stated closing balance: {s['stated_closing_balance']:,.2f} "
              f"({'we owe them' if s['stated_closing_side']=='To' else 'they owe us'})")
        print(f"  ledger internally balanced (Dr==Cr): {s['ledger_balanced']}")
        if s["adjustment_note"]:
            print(f"  NOTE: {s['adjustment_note']}")
        if s["warnings"]:
            for w in s["warnings"]:
                print(f"  WARNING: {w}")

    print("\n" + "=" * 78)
    print("OUT OF SCOPE (not imported, per spec):", ", ".join(OUT_OF_SCOPE))
    print("Fixed asset schedules also skipped — app has no fixed-asset tracking yet.")


if __name__ == "__main__":
    main()
