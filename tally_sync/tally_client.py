"""Builds and sends the XML requests Tally's local HTTP gateway (default
localhost:9000) accepts as an "ODBC/HTTP-XML" client — the same request
shape documented in Tally's own Developer Reference for a Collection
export (see https://help.tallysolutions.com/developer-reference/... "Case
Study 1 - XML Request and Response Formats" and the Sample XML page).

Two collections are requested:
  1. "Outstanding Ledgers" — every ledger under Sundry Debtors/Sundry
     Creditors with its live CLOSINGBALANCE, straight from Tally's own
     books (the authoritative outstanding figure — we don't recompute it
     from voucher rows the way the PDF-ledger parser has to).
  2. "Vouchers Since Date" — Purchase/Sales/Payment/Receipt vouchers in a
     date range, with each voucher's ledger-entry lines so we can tell
     which party they belong to and which side (Dr/Cr) they hit.

Tally's XML output is famously not strict XML (unescaped bare '&', and it
can emit Windows-1252 bytes inside a document declared as UTF-8) — see
notes in xml_to_ledger.py for how the parser copes with that.
"""
from __future__ import annotations

import requests

_LEDGER_COLLECTION_XML = """<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <TALLYREQUEST>Export</TALLYREQUEST>
  <TYPE>Collection</TYPE>
  <ID>Outstanding Ledgers</ID>
 </HEADER>
 <BODY>
  <DESC>
   <STATICVARIABLES>
    <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>{company_var}
   </STATICVARIABLES>
   <TDL>
    <TDLMESSAGE>
     <COLLECTION NAME="Outstanding Ledgers" ISMODIFY="No">
      <TYPE>Ledger</TYPE>
      <BELONGSTO>Yes</BELONGSTO>
      <FETCH>NAME, PARENT, CLOSINGBALANCE</FETCH>
     </COLLECTION>
    </TDLMESSAGE>
   </TDL>
  </DESC>
 </BODY>
</ENVELOPE>"""

_VOUCHER_COLLECTION_XML = """<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <TALLYREQUEST>Export</TALLYREQUEST>
  <TYPE>Collection</TYPE>
  <ID>Vouchers Since Date</ID>
 </HEADER>
 <BODY>
  <DESC>
   <STATICVARIABLES>
    <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
    <SVFROMDATE TYPE="Date">{from_date}</SVFROMDATE>
    <SVTODATE TYPE="Date">{to_date}</SVTODATE>{company_var}
   </STATICVARIABLES>
   <TDL>
    <TDLMESSAGE>
     <COLLECTION NAME="Vouchers Since Date" ISMODIFY="No">
      <TYPE>Voucher</TYPE>
      <FETCH>DATE, VOUCHERNUMBER, VOUCHERTYPENAME, PARTYLEDGERNAME, NARRATION, ISCANCELLED</FETCH>
      <FETCH>ALLLEDGERENTRIES.LIST</FETCH>
     </COLLECTION>
    </TDLMESSAGE>
   </TDL>
  </DESC>
 </BODY>
</ENVELOPE>"""


def _company_var(company: str | None) -> str:
    if not company:
        return ""
    return f"\n    <SVCURRENTCOMPANY>{company}</SVCURRENTCOMPANY>"


def build_ledger_request(company: str | None = None) -> str:
    """XML request for the live outstanding balance of every ledger
    (i.e. Sundry Debtors + Sundry Creditors accounts, filtered client-side
    by PARENT once parsed — the Tally-side BELONGSTO/PARENT filter syntax
    varies enough across Tally versions that filtering after the fact is
    more reliable than getting a TDL FILTER expression exactly right)."""
    return _LEDGER_COLLECTION_XML.format(company_var=_company_var(company))


def build_voucher_request(from_date: str, to_date: str, company: str | None = None) -> str:
    """XML request for vouchers in [from_date, to_date], both YYYYMMDD."""
    return _VOUCHER_COLLECTION_XML.format(
        from_date=from_date, to_date=to_date, company_var=_company_var(company),
    )


def send_request(tally_url: str, xml_body: str, timeout: int = 60) -> str:
    """POSTs an XML request to Tally's local HTTP gateway and returns the
    raw response text. Tally's own output can mix UTF-8 declarations with
    Windows-1252 bytes, so we decode leniently rather than let requests'
    auto-detected encoding raise or mangle characters."""
    resp = requests.post(
        tally_url, data=xml_body.encode("utf-8"),
        headers={"Content-Type": "text/xml; charset=utf-8"},
        timeout=timeout,
    )
    resp.raise_for_status()
    try:
        return resp.content.decode("utf-8")
    except UnicodeDecodeError:
        return resp.content.decode("cp1252", errors="replace")
