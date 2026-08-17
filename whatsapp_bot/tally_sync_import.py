"""Receives parsed Tally ledger data from the local tally_sync/ tool and
writes it into payables/receivables/payments.

Mirrors the balance-validation approach scripts/import_financial_data.py's
_reconcile_and_insert() uses for the PDF ledger import: Purchase rows
become payables, SALE GST rows become receivables, Payment/Receipt rows
settle the oldest open invoices first, and the running total is checked
against the source's own stated closing balance. The difference here is
what "the source's own stated balance" means: the PDF importer trusts the
printed ledger's closing-balance line and forces the DB to match it with
an adjusting entry (the PDF is often an incomplete/summarized document).
Tally is the live source of truth, so a mismatch here is unexpected and
gets FLAGGED instead of silently patched with a synthetic entry — see
reconcile_ledger()'s docstring.

This service can't `import scripts.import_financial_data` (separate
Railway root directory, same reason db.py and voice.py are local copies
rather than cross-folder imports) so this deliberately reimplements the
same validation *approach*, not the PDF-specific parsing it doesn't need.
"""
from __future__ import annotations

_TOLERANCE = 1.0  # rupees — matches the PDF importer's tolerance


def ensure_tally_sync_table(conn):
    """Idempotency log: one row per Tally voucher we've ever written, so
    re-running a sync over an overlapping date range never double-inserts
    a payable/receivable/payment."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tally_sync_log (
            id SERIAL PRIMARY KEY,
            voucher_key TEXT NOT NULL UNIQUE,
            row_type TEXT NOT NULL,
            target_id INTEGER,
            synced_at TIMESTAMP NOT NULL DEFAULT now()
        )
        """
    )
    conn.commit()


def _voucher_key(company: str | None, party: str, row: dict) -> str:
    return "|".join([
        company or "", party, row.get("vch_type") or "", row.get("vch_no") or "",
        row.get("date") or "", f"{row.get('amount', 0):.2f}",
    ])


def _claim(conn, voucher_key: str, row_type: str) -> int | None:
    """Returns the new tally_sync_log id if this voucher hasn't been
    synced before, or None if it's a duplicate (already claimed)."""
    cur = conn.execute(
        "INSERT INTO tally_sync_log (voucher_key, row_type) VALUES (%s,%s) "
        "ON CONFLICT (voucher_key) DO NOTHING RETURNING id",
        (voucher_key, row_type),
    )
    row = cur.fetchone()
    return row["id"] if row else None


def _open_invoices(conn, table: str, name_col: str, party: str, company: str | None):
    """Open (not-fully-paid) payables/receivables for a party, oldest
    first, with their true remaining balance computed from the payments
    table rather than trusting the status flag alone."""
    pay_type = "payable" if table == "payables" else "receivable"
    rows = conn.execute(
        f"""
        SELECT t.id, t.date,
               t.amount - COALESCE(SUM(p.amount_paid), 0) AS remaining
        FROM {table} t
        LEFT JOIN payments p ON p.type=%s AND p.reference_id=t.id
        WHERE t.{name_col}=%s AND (t.company=%s OR %s IS NULL)
        GROUP BY t.id, t.date, t.amount
        HAVING t.amount - COALESCE(SUM(p.amount_paid), 0) > 0.01
        ORDER BY t.date ASC
        """,
        (pay_type, party, company, company),
    ).fetchall()
    return [{"id": r["id"], "remaining": r["remaining"]} for r in rows]


def _net_open(conn, table: str, name_col: str, party: str, company: str | None) -> float:
    return sum(i["remaining"] for i in _open_invoices(conn, table, name_col, party, company))


def reconcile_ledger(conn, company: str | None, ledger: dict) -> dict:
    """Writes one party's synced rows into payables/receivables/payments
    and reports the reconciliation against Tally's own stated closing
    balance for that party.

    Unlike the PDF importer, this does NOT insert a synthetic
    brought-forward adjusting entry when the numbers don't match — Tally
    is a live, complete source, so a mismatch here more likely means a
    voucher type we don't recognize, a date-range gap between syncs, or a
    genuine data problem, any of which is worth a human look rather than
    silently papering over.
    """
    party = ledger["party_name"]
    warnings = list(ledger.get("warnings") or [])
    n_payables = n_receivables = n_payments = 0

    settlements = []  # [(kind, row)]
    for row in ledger.get("rows") or []:
        key = _voucher_key(company, party, row)
        vch_type = (row.get("vch_type") or "").strip()

        if vch_type == "Purchase":
            claim_id = _claim(conn, key, "payable")
            if claim_id is None:
                continue
            cur = conn.execute(
                "INSERT INTO payables (vendor_name, description, amount, date, notes, "
                "status, company, voucher_no, source_file) "
                "VALUES (%s,%s,%s,%s,%s,'outstanding',%s,%s,'tally_sync') RETURNING id",
                (party, row.get("particulars") or party, row["amount"], row["date"],
                 f"Synced from Tally (Purchase {row.get('vch_no') or ''})".strip(),
                 company, row.get("vch_no")),
            )
            conn.execute("UPDATE tally_sync_log SET target_id=%s WHERE id=%s",
                         (cur.fetchone()["id"], claim_id))
            n_payables += 1

        elif vch_type == "SALE GST":
            claim_id = _claim(conn, key, "receivable")
            if claim_id is None:
                continue
            cur = conn.execute(
                "INSERT INTO receivables (customer_name, company, reference, amount, date, "
                "notes, status, voucher_no, source_file) "
                "VALUES (%s,%s,%s,%s,%s,%s,'outstanding',%s,'tally_sync') RETURNING id",
                (party, company, row.get("particulars") or party, row["amount"], row["date"],
                 f"Synced from Tally (SALE GST {row.get('vch_no') or ''})".strip(),
                 row.get("vch_no")),
            )
            conn.execute("UPDATE tally_sync_log SET target_id=%s WHERE id=%s",
                         (cur.fetchone()["id"], claim_id))
            n_receivables += 1

        elif vch_type in ("Payment", "Receipt"):
            settlements.append((vch_type, row, key))

        else:
            warnings.append(f"{party}: skipped voucher with unrecognized type '{vch_type}'")

    for kind, row, key in settlements:
        claim_id = _claim(conn, key, "payment")
        if claim_id is None:
            continue
        table, name_col = ("payables", "vendor_name") if kind == "Payment" else ("receivables", "customer_name")
        pay_type = "payable" if kind == "Payment" else "receivable"
        invoices = _open_invoices(conn, table, name_col, party, company)
        remaining = row["amount"]
        for inv in invoices:
            if remaining <= 0:
                break
            applied = min(inv["remaining"], remaining)
            conn.execute(
                "INSERT INTO payments (type, reference_id, payment_date, amount_paid, notes, source_file) "
                "VALUES (%s,%s,%s,%s,%s,'tally_sync')",
                (pay_type, inv["id"], row["date"], applied,
                 f"Matched from Tally sync ({kind}, Vch {row.get('vch_no') or 'n/a'})"),
            )
            remaining -= applied
        if remaining > 0.01:
            conn.execute(
                "INSERT INTO payments (type, reference_id, payment_date, amount_paid, notes, source_file) "
                "VALUES (%s,0,%s,%s,%s,'tally_sync')",
                (pay_type, row["date"], remaining,
                 f"Unmatched against any open invoice (advance {kind.lower()}, Vch {row.get('vch_no') or 'n/a'})"),
            )
        conn.execute("UPDATE tally_sync_log SET target_id=%s WHERE id=%s", (0, claim_id))
        n_payments += 1

    conn.commit()

    net_open_payable = _net_open(conn, "payables", "vendor_name", party, company)
    net_open_receivable = _net_open(conn, "receivables", "customer_name", party, company)

    # sync status flags to match reality (paid vs still outstanding)
    for table, name_col, pay_type in (
        ("payables", "vendor_name", "payable"), ("receivables", "customer_name", "receivable")
    ):
        conn.execute(
            f"""
            UPDATE {table} t SET status = CASE
                WHEN t.amount - COALESCE((SELECT SUM(p.amount_paid) FROM payments p
                    WHERE p.type=%s AND p.reference_id=t.id), 0) <= 0.01
                THEN 'paid' ELSE 'outstanding' END
            WHERE t.{name_col}=%s AND (t.company=%s OR %s IS NULL)
            """,
            (pay_type, party, company, company),
        )
    conn.commit()

    result = {
        "party_name": party, "company": company,
        "n_payables_added": n_payables, "n_receivables_added": n_receivables,
        "n_payments_added": n_payments,
        "net_open_payable": net_open_payable, "net_open_receivable": net_open_receivable,
        "tally_closing_balance": ledger.get("closing_balance"),
        "tally_closing_side": ledger.get("closing_side"),
        "mismatch": False, "diff": 0.0,
    }

    stated = ledger.get("closing_balance")
    if stated is not None:
        stated_signed = stated if ledger.get("closing_side") == "To" else -stated  # +ve = we owe them
        computed_signed = net_open_payable - net_open_receivable
        diff = round(stated_signed - computed_signed, 2)
        if abs(diff) > _TOLERANCE:
            result["mismatch"] = True
            result["diff"] = diff
            warnings.append(
                f"{party}: database net balance (Rs. {computed_signed:,.2f}) doesn't match "
                f"Tally's stated closing balance (Rs. {stated_signed:,.2f}) — diff Rs. {diff:,.2f}. "
                f"Not auto-adjusted; needs a manual look."
            )

    result["warnings"] = warnings
    return result
