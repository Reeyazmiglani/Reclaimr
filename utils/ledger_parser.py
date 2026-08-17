"""
Parser for the running vendor/customer ledger PDFs in data_import/
(Alstrong, Dev Rubber, GRP Ltd, HPL Additives, Nirman Trading, Speedways).

Unlike the Balance Sheet PDFs, these are genuinely single-column tables —
pdfplumber's plain `extract_text()` reads them cleanly, so this is a much
simpler line-by-line regex parser: one row per date/particulars/voucher
type/voucher no/amount, in the Tally "Dr side (To ...) / Cr side (By ...)"
convention.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

import pdfplumber

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_DATE_RE = re.compile(r"^(\d{1,2})-([A-Za-z]{3})-(\d{2})$")
_ROW_RE = re.compile(r"^(?:(\d{1,2}-[A-Za-z]{3}-\d{2})\s+)?(To|By)\s+(.*)$")
_AMOUNT_TAIL_RE = re.compile(r"([\d,]+\.\d{2})\s*$")
_VCH_TYPE_RE = re.compile(r"(SALE GST|Payment|Receipt|Purchase)\s*([A-Za-z0-9]+)?$")


def _to_iso_date(d: str) -> str:
    m = _DATE_RE.match(d)
    day, mon, yr = m.groups()
    year = 2000 + int(yr)
    return f"{year:04d}-{_MONTHS[mon.lower()]:02d}-{int(day):02d}"


def _parse_indian_amount(text: str) -> float:
    return float(text.replace(",", ""))


@dataclass
class LedgerRow:
    date: str | None       # ISO date, or None if it's a continuation row
    side: str              # "To" (Dr) or "By" (Cr)
    particulars: str
    vch_type: str | None   # Payment / Receipt / Purchase / SALE GST / None
    vch_no: str | None
    amount: float


@dataclass
class ParsedLedger:
    source_file: str
    company: str | None
    party_name: str | None
    period_start: str | None
    period_end: str | None
    rows: list[LedgerRow] = field(default_factory=list)
    closing_balance: float | None = None
    closing_side: str | None = None  # "To" = we owe them (Cr balance), "By" = they owe us (Dr balance)
    total_debit: float | None = None
    total_credit: float | None = None
    is_balanced: bool | None = None
    warnings: list[str] = field(default_factory=list)


def _detect_company(text: str) -> str | None:
    header = text[:200].upper()
    if "ELASTOHORSE" in header:
        return "Elastohorse"
    if "RWOX" in header:
        return "Rwox"
    return None


def _detect_party_name(lines: list[str]) -> str | None:
    for i, line in enumerate(lines):
        if line.strip() == "Ledger Account" and i > 0:
            return lines[i - 1].strip()
    return None


def parse_ledger_pdf(path: str) -> ParsedLedger:
    with pdfplumber.open(path) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages)

    lines = text.splitlines()
    company = _detect_company(text)
    party_name = _detect_party_name(lines)

    period_m = re.search(r"(\d{1,2}-[A-Za-z]{3}-\d{2})\s+to\s+(\d{1,2}-[A-Za-z]{3}-\d{2})", text)
    period_start = _to_iso_date(period_m.group(1)) if period_m else None
    period_end = _to_iso_date(period_m.group(2)) if period_m else None

    result = ParsedLedger(
        source_file=path, company=company, party_name=party_name,
        period_start=period_start, period_end=period_end,
    )

    current_date: str | None = None
    plain_amount_lines: list[tuple[float, float | None]] = []  # (single amt, or debit/credit pair) for totals detection

    for raw in lines:
        line = raw.strip()
        if not line:
            continue

        m = _ROW_RE.match(line)
        if m:
            date_str, side, rest = m.groups()
            if date_str:
                current_date = _to_iso_date(date_str)
            amt_m = _AMOUNT_TAIL_RE.search(rest)
            if not amt_m:
                continue
            amount = _parse_indian_amount(amt_m.group(1))
            rest_no_amt = rest[: amt_m.start()].strip()
            vt_m = _VCH_TYPE_RE.search(rest_no_amt)
            if vt_m:
                vch_type = vt_m.group(1)
                vch_no = vt_m.group(2)
                particulars = rest_no_amt[: vt_m.start()].strip()
            else:
                vch_type, vch_no = None, None
                particulars = rest_no_amt
            result.rows.append(LedgerRow(
                date=current_date, side=side, particulars=particulars,
                vch_type=vch_type, vch_no=vch_no, amount=amount,
            ))
            continue

        # Totals / closing-balance rows have no "To"/"By" side marker
        if line.lower().startswith("total"):
            continue
        # bare "12,34,567.00 89,01,234.00" column-totals row
        nums = re.findall(r"[\d,]+\.\d{2}", line)
        if len(nums) == 2 and not re.search(r"[A-Za-z]", line):
            result.total_debit = _parse_indian_amount(nums[0])
            result.total_credit = _parse_indian_amount(nums[1])
            continue
        if len(nums) == 1 and not re.search(r"[A-Za-z]", line):
            # grand-total repeat line ("16,70,252.00 16,70,252.00" already
            # matched above as len==2; this branch is the rare odd one out)
            continue

    # closing balance: the one row whose particulars is literally
    # "Closing Balance" (added to whichever side is short, per Tally)
    for row in result.rows:
        if row.particulars.strip().lower() == "closing balance":
            result.closing_balance = row.amount
            result.closing_side = row.side
            result.rows.remove(row)
            break

    if result.total_debit is not None and result.total_credit is not None:
        result.is_balanced = abs(result.total_debit - result.total_credit) < 2.0
        if not result.is_balanced:
            result.warnings.append(
                f"Column totals don't match after adding closing balance: "
                f"Dr {result.total_debit} vs Cr {result.total_credit}"
            )
    else:
        result.warnings.append("Could not locate the column-totals row")

    if not company:
        result.warnings.append("Could not detect which company this ledger belongs to")
    if not party_name:
        result.warnings.append("Could not detect the vendor/customer name")

    return result
