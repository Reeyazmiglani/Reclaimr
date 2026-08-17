"""
Parser for Tally-exported Balance Sheet / Trading Account / Profit & Loss
PDFs (the "data_import/" documents).

These PDFs are NOT proper tables (no ruling lines pdfplumber can detect) —
they're two side-by-side flowing text columns per statement
(Liabilities | Amount | Assets | Amount, or Dr side | Amount | Cr side |
Amount) that were exported in a way where a cell's text reflows
independently of its neighbour, so naive whole-page text extraction
interleaves words from unrelated columns. This module reconstructs each
side of the page from word-level positions instead of trusting
`extract_text()`, then pulls out (label, amount) line items from each
side separately so labels never get glued to the wrong number.

Known source quirk: amounts sometimes wrap onto a second physical line
inside their narrow column (e.g. "2,014,819" then "87" a few points
below) — `_reconstruct_side` re-glues those into "2,014,819.87".
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import pdfplumber

_AMOUNT_TOKEN_RE = re.compile(r"^[\d,\.]+$")
_DATE_RE = re.compile(
    r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)\s+(\d{4})|"
    r"as\s+on\s+31[-/](\d{2})[-/](\d{4})",
    re.IGNORECASE,
)
_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _is_amount_token(text: str) -> bool:
    return bool(_AMOUNT_TOKEN_RE.match(text)) and sum(c.isdigit() for c in text) >= 2


def _is_formatted_amount_token(text: str) -> bool:
    """Stricter than `_is_amount_token` — only real Rupee figures (thousands
    comma or a 2-decimal tail), used for column-split detection so a bare
    page number / year / registration number can't skew the clustering."""
    return _is_amount_token(text) and ("," in text or re.search(r"\.\d{2}$", text))


def _parse_amount(text: str) -> float:
    """Handles the normal "1,518,879.83" case, but also a source PDF
    quirk where the thousands-comma and decimal-point occasionally get
    transposed by the export (e.g. "1.518,879,83" for what should be
    "1,518,879.83") — whichever trailing [.,]\\d{2} group is last is
    treated as the real decimal, everything else as thousands grouping."""
    text = text.strip()
    m = re.search(r"[.,](\d{2})$", text)
    if m:
        integer_part = re.sub(r"[.,]", "", text[: m.start()])
        return float(f"{integer_part}.{m.group(1)}") if integer_part else float(f"0.{m.group(1)}")
    return float(re.sub(r"[.,]", "", text).rstrip("."))


def _cluster_split_x(words: list) -> float | None:
    """Find the x boundary between the left column-pair (label+amount)
    and the right column-pair.

    Two-stage: first find the two x-clusters of *real* Rupee amounts
    (comma/decimal-formatted, so stray bare numbers like a year or a
    membership number can't skew this) to locate where the left amount
    column ends and the right amount column begins. Then, within that
    gap, look at *all* words (not just amounts) to find the actual
    column boundary — which sits much closer to the left amount column
    than to the right one, since column 3 (the right side's labels)
    starts almost immediately after column 2 (the left side's amounts)
    ends."""
    nums = [w for w in words if _is_formatted_amount_token(w["text"])]
    if len(nums) < 2:
        return None
    xs = sorted(set(round(w["x0"], 1) for w in nums))
    if len(xs) < 2:
        return None
    gaps = [(xs[i + 1] - xs[i], xs[i], xs[i + 1]) for i in range(len(xs) - 1)]
    gaps.sort(reverse=True)
    gap_size, left_edge, right_edge = gaps[0]
    if gap_size < 40:
        # amounts aren't clearly two-clustered on this page (e.g. a
        # single-column page) — no split needed
        return None
    left_cluster_max_x1 = max(
        w["x1"] for w in nums if w["x0"] <= left_edge + 0.05
    )
    # The right side's label column starts almost immediately after the
    # left amount column ends (a few points of cell padding) — use the
    # closest word start past left_cluster_max_x1 (but still short of the
    # right amount cluster) as the true boundary, rather than a fixed
    # margin that's wrong for narrower/wider layouts. Restrict to the
    # table's own row band (up to the last amount + a little slack) so a
    # signature block/auditor's-report footer with unrelated column
    # positions further down the page can't pollute this.
    table_bottom = max(w["top"] for w in nums) + 20
    after = [w["x0"] for w in words
             if left_cluster_max_x1 < w["x0"] < right_edge - 0.05 and w["top"] <= table_bottom]
    if after:
        return (left_cluster_max_x1 + min(after)) / 2
    return left_cluster_max_x1 + 1.5


def _row_order(words: list, y_tol: float = 4.0) -> list[dict]:
    """Sort into reading order (top-to-bottom, left-to-right), but bucket
    words into visual rows first — a label and its amount are meant to be
    "the same row" yet often differ by a point or two in raw `top` (label
    text and numerals don't share a baseline), which would otherwise flip
    their left-to-right order and glue an amount to the wrong label."""
    ws = sorted(words, key=lambda w: w["top"])
    rows: list[list[dict]] = []
    cur: list[dict] = []
    cur_top = None
    for w in ws:
        if cur_top is None or abs(w["top"] - cur_top) <= y_tol:
            cur.append(w)
            cur_top = w["top"] if cur_top is None else min(cur_top, w["top"])
        else:
            rows.append(cur)
            cur, cur_top = [w], w["top"]
    if cur:
        rows.append(cur)
    out: list[dict] = []
    for row in rows:
        out.extend(sorted(row, key=lambda w: w["x0"]))
    return out


def _merge_decimal_wraps(words: list) -> list[dict]:
    """A cell whose column is too narrow sometimes wraps its amount onto a
    second physical line (e.g. "2,014,819" then "87" a few points below,
    or "1,925,310." then "00") — re-glue those pairs into one token before
    anything downstream tries to read the number."""
    ws = _row_order(words)
    consumed: set[int] = set()
    out: list[dict] = []
    for i, w in enumerate(ws):
        if i in consumed:
            continue
        text = w["text"]
        if _is_amount_token(text) and not re.search(r"\.\d{2}$", text):
            for j in range(i + 1, min(i + 4, len(ws))):
                if j in consumed:
                    continue
                w2 = ws[j]
                if re.fullmatch(r"\d{1,2}", w2["text"]) and \
                        abs(w2["top"] - w["top"]) < 15 and abs(w2["x0"] - w["x0"]) < 60:
                    text = text.rstrip(".") + "." + w2["text"]
                    consumed.add(j)
                    break
        out.append({**w, "text": text})
    return out


def _tokens_to_items(tokens: list[dict]) -> list[tuple[str, float]]:
    """Walk a side's word stream (already decimal-merged, in reading
    order) and pair each amount token with the label text accumulated
    since the previous amount. Operating on the token stream directly —
    rather than first joining into visual lines — means an amount that
    lands mid-"line" (two unrelated rows merged by y-clustering) still
    gets picked up correctly."""
    items: list[tuple[str, float]] = []
    buf: list[str] = []
    for t in tokens:
        text = t["text"]
        if _is_amount_token(text):
            try:
                amount = _parse_amount(text)
            except ValueError:
                buf.append(text)
                continue
            if amount < 1:
                buf.append(text)
                continue
            label = " ".join(buf).strip().rstrip(":.").strip()
            buf = []
            if label:
                items.append((label, amount))
        else:
            buf.append(text)
    return items


@dataclass
class PageSides:
    left: list[tuple[str, float]] = field(default_factory=list)
    right: list[tuple[str, float]] = field(default_factory=list)
    raw_text: str = ""


def split_page(page) -> PageSides:
    words = page.extract_words()
    raw_text = page.extract_text() or ""
    split_x = _cluster_split_x(words)
    if split_x is None:
        # single-column page (e.g. a ledger) — treat everything as "left"
        tokens = _merge_decimal_wraps(words)
        return PageSides(left=_tokens_to_items(tokens), right=[], raw_text=raw_text)
    left_words = [w for w in words if w["x0"] < split_x]
    right_words = [w for w in words if w["x0"] >= split_x]
    return PageSides(
        left=_tokens_to_items(_merge_decimal_wraps(left_words)),
        right=_tokens_to_items(_merge_decimal_wraps(right_words)),
        raw_text=raw_text,
    )


def _cluster_rows(words: list, y_tol: float = 4.0) -> list[list[dict]]:
    rows: list[list[dict]] = []
    cur: list[dict] = []
    cur_top = None
    for w in sorted(words, key=lambda w: w["top"]):
        if cur_top is None or abs(w["top"] - cur_top) <= y_tol:
            cur.append(w)
            cur_top = w["top"] if cur_top is None else min(cur_top, w["top"])
        else:
            rows.append(cur)
            cur, cur_top = [w], w["top"]
    if cur:
        rows.append(cur)
    return rows


def find_totals_row(page) -> tuple[float | None, float | None]:
    """The bottom "Total ... Total" row is special in two ways: (a) its two
    "Total" labels are short enough that their left/right columns overlap
    in x-range with the row above's amount column, so no single page-wide
    x-split can separate them, and (b) the two amounts don't always land
    at quite the same `top` as each other or as the labels (the right
    column can drift a few extra points down the page). So: find where
    the "Total" label(s) sit, then look for amounts in a generous band
    below that point rather than requiring an exact same-row match."""
    words = page.extract_words()
    total_labels = [w for w in words if w["text"].strip(":").lower() == "total"]
    if not total_labels:
        return None, None
    # bottom-most cluster of "Total" labels (a page can say "Total" earlier
    # too, e.g. in a heading) — take the group with the largest top values
    total_labels.sort(key=lambda w: w["top"])
    band_top = total_labels[-1]["top"]
    for w in reversed(total_labels):
        if band_top - w["top"] <= 15:
            band_top = w["top"]
        else:
            break
    band = [w for w in words if band_top - 2 <= w["top"] <= band_top + 20]
    merged = _merge_decimal_wraps(band)
    amounts = sorted(
        (w for w in merged if _is_formatted_amount_token(w["text"])),
        key=lambda w: w["x0"],
    )
    if len(amounts) >= 2:
        return _parse_amount(amounts[0]["text"]), _parse_amount(amounts[-1]["text"])
    if len(amounts) == 1:
        return _parse_amount(amounts[0]["text"]), None
    return None, None


def find_row_value(page, keywords: list[str], exclude: list[str] | None = None,
                    pick: str = "last") -> float | None:
    """Same idea as `find_totals_row` but for any single labelled figure
    (Sales, Purchases, Gross Profit, Net Profit, Fixed Assets, ...):
    find the row whose text contains one of `keywords`, then read the
    amount(s) in that same row directly (rather than trusting which
    left/right side `split_page` filed it under, which is unreliable for
    short labels that start further left than the split boundary — the
    same issue the totals row has). `pick`="last" takes the right-most
    amount on the row (matches this layout's Amount-column-on-the-right
    convention); "first" takes the left-most."""
    exclude = exclude or []
    for row in _cluster_rows(page.extract_words()):
        merged = _merge_decimal_wraps(row)
        row_text = " ".join(w["text"] for w in sorted(merged, key=lambda w: w["x0"])).lower()
        if not any(k in row_text for k in keywords):
            continue
        if any(x in row_text for x in exclude):
            continue
        amounts = sorted(
            (w for w in merged if _is_formatted_amount_token(w["text"])),
            key=lambda w: w["x0"],
        )
        if not amounts:
            continue
        chosen = amounts[-1] if pick == "last" else amounts[0]
        val = _parse_amount(chosen["text"])
        if val >= 1:
            return val
    return None


def _find(items: list[tuple[str, float]], keywords: list[str], exclude: list[str] | None = None) -> float | None:
    exclude = exclude or []
    for label, amount in items:
        ll = label.lower()
        if any(k in ll for k in keywords) and not any(x in ll for x in exclude):
            return amount
    return None


def _find_all(items: list[tuple[str, float]], keywords: list[str]) -> float:
    total = 0.0
    hit = False
    for label, amount in items:
        ll = label.lower()
        if any(k in ll for k in keywords):
            total += amount
            hit = True
    return total if hit else None


def parse_statement_date(text: str) -> str | None:
    """Returns an ISO date string (YYYY-MM-DD), the statement's 'as on' /
    'year ending' date — always 31 March for these Tally exports, but we
    read the real value rather than assuming."""
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)\s+(\d{4})", text)
    if m:
        day, mon_name, year = m.groups()
        mon = _MONTHS.get(mon_name[:3].lower())
        if mon:
            return f"{int(year):04d}-{mon:02d}-{int(day):02d}"
    m2 = re.search(r"31[-/](\d{2})[-/](\d{4})", text)
    if m2:
        mm, yyyy = m2.groups()
        return f"{yyyy}-{mm}-31"
    return None


def detect_company(text: str) -> str | None:
    """Company name is printed in the document header — look only at the
    first ~300 chars so a company mentioned elsewhere (e.g. as a debtor/
    creditor line item further down) can't misfire."""
    header = text[:300].upper()
    if "ELASTOHORSE" in header:
        return "Elastohorse"
    if "RWOX" in header:
        return "Rwox"
    return None


@dataclass
class ParsedStatement:
    source_file: str
    company: str | None
    statement_date: str | None
    capital_account: float | None = None
    loans: float | None = None
    sundry_creditors: float | None = None
    sundry_debtors: float | None = None
    fixed_assets: float | None = None
    closing_stock: float | None = None
    cash_bank: float | None = None
    sales: float | None = None
    purchases: float | None = None
    gross_profit: float | None = None
    net_profit: float | None = None
    total_liabilities: float | None = None
    total_assets: float | None = None
    is_balanced: bool | None = None
    balance_diff: float | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def import_ok(self) -> bool:
        """The bar for actually writing this statement to the database:
        the books must balance (the hard requirement from the spec) AND
        enough of the core balance-sheet fields were actually found that
        we're not silently storing a mostly-empty/misattributed record
        just because its two Totals coincidentally matched."""
        if self.is_balanced is not True:
            return False
        core = [self.capital_account, self.fixed_assets, self.closing_stock, self.cash_bank]
        missing = sum(1 for v in core if v is None)
        return missing <= 1


def parse_pdf(path, source_name: str | None = None) -> ParsedStatement:
    """`path` may be a filesystem path (str) or any pdfplumber-openable
    file-like object (e.g. a Streamlit upload's BytesIO) — pass
    `source_name` to label the latter case, since a buffer has no filename
    of its own."""
    label = source_name or (path if isinstance(path, str) else "uploaded file")
    with pdfplumber.open(path) as pdf:
        raw_pages = list(pdf.pages)
        pages = [split_page(p) for p in raw_pages]

        full_text = "\n".join(p.raw_text for p in pages)
        company = detect_company(full_text)
        stmt_date = parse_statement_date(full_text)

        result = ParsedStatement(source_file=label, company=company, statement_date=stmt_date)

        # --- locate the Balance Sheet page (left=Liabilities, right=Assets) ---
        # Two complementary readers are used for every field:
        #  1) split_page's per-side item list — handles labels that wrap
        #     across several physical lines before their amount appears
        #     (e.g. "Capital Account" / "(As per annexure A)" / "889,975.22").
        #  2) find_row_value — reads straight off one physical row. Needed
        #     as a fallback for short single-line labels ("Total", "Sales")
        #     whose column starts further left than the page's general
        #     label/amount split boundary, so (1) files them on the wrong
        #     side or loses them at a boundary.
        bs_page = bs_raw_page = None
        for raw_p, p in zip(raw_pages, pages):
            if "balance sheet" in p.raw_text.lower() and "liabilities" in p.raw_text.lower():
                bs_page, bs_raw_page = p, raw_p
                break
        if bs_page:
            liab, assets = bs_page.left, bs_page.right
            left_first_words = " ".join(l for l, _ in bs_page.left[:3]).lower()
            if "asset" in left_first_words and "liabilit" not in left_first_words:
                liab, assets = assets, liab

            result.capital_account = _find(liab, ["capital account", "capital a/c"]) or \
                find_row_value(bs_raw_page, ["capital account", "capital a/c"])
            loans_val = (_find_all(liab, ["unsecured loan", "secured loan"]) or 0) or None
            if loans_val is None:
                secured = find_row_value(bs_raw_page, ["secured loan"], exclude=["unsecured"])
                unsecured = find_row_value(bs_raw_page, ["unsecured loan"])
                loans_val = sum(v for v in (secured, unsecured) if v is not None) or None
            result.loans = loans_val
            result.sundry_creditors = _find(liab, ["sundry creditor"]) or \
                find_row_value(bs_raw_page, ["sundry creditor"])

            result.fixed_assets = _find(assets, ["fixed asset"]) or \
                find_row_value(bs_raw_page, ["fixed asset"])
            result.closing_stock = _find(assets, ["closing stock"]) or \
                find_row_value(bs_raw_page, ["closing stock"])
            result.sundry_debtors = _find(assets, ["sundry debtor"]) or \
                find_row_value(bs_raw_page, ["sundry debtor"])
            # PDF text sometimes garbles "Cash & Bank" into "Cash &B ank"
            # with a stray space inside "Bank" — match on "cash" alone
            result.cash_bank = _find(assets, ["cash"]) or \
                find_row_value(bs_raw_page, ["cash"])

            result.total_liabilities, result.total_assets = find_totals_row(bs_raw_page)

            if result.total_liabilities is not None and result.total_assets is not None:
                diff = abs(result.total_liabilities - result.total_assets)
                result.balance_diff = diff
                result.is_balanced = diff < 2.0  # allow rounding paise
            else:
                result.warnings.append("Could not locate both Total Liabilities and Total Assets")
        else:
            result.warnings.append("Could not locate a Balance Sheet page in this PDF")

        # --- locate Trading Account / P&L page(s) ---
        for raw_p, p in zip(raw_pages, pages):
            tl = p.raw_text.lower()
            left_low = " ".join(l.lower() for l, _ in p.left)
            right_low = " ".join(l.lower() for l, _ in p.right)
            combined = left_low + " " + right_low
            if "trading account" in tl or ("sales" in tl and "purchase" in tl):
                sales = _find(p.right, ["sales"]) or _find(p.left, ["sales"]) or \
                    find_row_value(raw_p, ["sales"], exclude=["sales tax", "sale gst"])
                purchases = _find(p.left, ["purchase"]) or _find(p.right, ["purchase"]) or \
                    find_row_value(raw_p, ["purchase"], exclude=["purchase gst"])
                gp = _find(p.left, ["gross profit"]) or _find(p.right, ["gross profit"]) or \
                    find_row_value(raw_p, ["gross profit"])
                if sales is not None:
                    result.sales = sales
                if purchases is not None:
                    result.purchases = purchases
                if gp is not None:
                    result.gross_profit = gp
            if "net profit" in combined or "net profit" in tl:
                npft = _find(p.left, ["net profit"]) or _find(p.right, ["net profit"]) or \
                    find_row_value(raw_p, ["net profit"], exclude=["net profit ratio"])
                if npft is not None:
                    result.net_profit = npft

    if result.is_balanced and not result.import_ok:
        result.warnings.append(
            "Totals balance, but too many core fields (capital/fixed assets/"
            "closing stock/cash & bank) could not be reliably located — "
            "likely a low-quality scan/export. Flagged for manual review "
            "rather than importing possibly-misattributed numbers."
        )

    return result
