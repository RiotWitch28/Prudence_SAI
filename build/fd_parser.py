#!/usr/bin/env python3
"""
fd_parser.py — parse a House Financial Disclosure (FD) annual-report PDF into
structured data, using pdfplumber's ruled-table extraction.

Source: the "Most Recent House Financial Disclosure" link in the 119th Master List
(disclosures-clerk.house.gov .../financial-pdfs/<year>/<id>.pdf). These e-filed
reports use bordered tables, so pdfplumber recovers true columns (asset name,
value, income, transactions, liabilities, gifts, travel) without guessing.

Run standalone:  build/.venv/bin/python build/fd_parser.py <pdf-path-or-url>
"""

import re, sys, json, io, urllib.request
import pdfplumber

RANGE = re.compile(r"\$[\d,]+ ?- ?\$?[\d,]+|Over \$[\d,]+")
DATE = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")


def _open(src):
    if src.startswith("http"):
        req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"})
        return pdfplumber.open(io.BytesIO(urllib.request.urlopen(req, timeout=60).read()))
    return pdfplumber.open(src)


def _clean(c):
    if not c:
        return ""
    return re.sub(r"\s+", " ", c.replace("\n", " ")).strip()


def parse_header(text):
    def grab(label):
        m = re.search(rf"{label}\s*:\s*(.+)", text)
        return m.group(1).strip() if m else None
    fid = re.search(r"Filing ID #(\d+)", text)
    return {"name": grab("Name"), "status": grab("Status"),
            "state_district": grab("State/District"), "filing_type": grab("Filing Type"),
            "filing_year": grab("Filing Year"), "filing_date": grab("Filing Date"),
            "filing_id": fid.group(1) if fid else None}


def _is_header(cells):
    j = " | ".join(cells)
    c0 = cells[0]
    if c0 == "Asset" and "Value" in cells[2]:
        return "schedule_a"
    if c0 == "Asset" and "Date" in cells[2]:
        return "schedule_b"
    if c0 == "Source" and "Amount" in j:
        return "schedule_c"
    if "Creditor" in j and "Amount of Liability" in j:
        return "schedule_d"
    if "Parties To" in j:
        return "agreements"
    if "Trip" in c0 or "Trip Details" in j:
        return "schedule_h"
    if c0 == "Position" or (c0 == "Name of Organization"):
        return "schedule_e"
    if c0 == "Gift Source" or ("Description" in c0 and "Value" in j):
        return "schedule_g"
    return None


def _split_code(asset):
    m = re.search(r"\[([A-Z]{2})\]\s*$", asset)
    if m:
        return asset[:m.start()].strip(), m.group(1)
    m = re.search(r"\[([A-Z]{2})\]", asset)
    return (asset[:m.start()].strip(), m.group(1)) if m else (asset, None)


def parse(src):
    pdf = _open(src)
    full_text = "\n".join((p.extract_text() or "") for p in pdf.pages)
    header = parse_header(full_text)

    out = {"schedule_a": [], "schedule_b": [], "schedule_c": [],
           "schedule_d": [], "schedule_e": [], "schedule_g": [],
           "schedule_h": [], "agreements": []}
    current = None
    for pg in pdf.pages:
        for tbl in pg.extract_tables():
            for raw in tbl:
                cells = [_clean(c) for c in raw]
                if not any(cells):
                    continue
                hdr = _is_header(cells)
                if hdr:
                    current = hdr
                    continue
                if cells[0] in ("Filing ID", "") and not any(cells[1:]):
                    continue
                if current == "schedule_a":
                    if not RANGE.search(cells[2] or ""):
                        continue
                    name, code = _split_code(cells[0])
                    out["schedule_a"].append({
                        "asset": name, "type": code, "owner": cells[1] or None,
                        "value": cells[2] or None, "income_type": cells[3] or None,
                        "income": cells[4] or None})
                elif current == "schedule_b":
                    if not DATE.search(cells[2] or ""):
                        continue
                    name, code = _split_code(cells[0])
                    out["schedule_b"].append({
                        "asset": name, "type": code, "owner": cells[1] or None,
                        "date": cells[2] or None, "tx_type": cells[3] or None,
                        "amount": cells[4] or None})
                elif current == "schedule_c":
                    if cells[0] and cells[0] != "Source":
                        out["schedule_c"].append({"source": cells[0],
                            "type": cells[1] or None, "amount": cells[2] or None})
                elif current == "schedule_d":
                    if RANGE.search(cells[-1] or ""):
                        out["schedule_d"].append({"owner": cells[0] or None,
                            "creditor": cells[1] or None, "date_incurred": cells[2] or None,
                            "type": cells[3] or None, "amount": cells[4] or None})
                elif current == "agreements":
                    if cells[0] and cells[0] != "Date":
                        out["agreements"].append({"date": cells[0],
                            "parties": cells[1] or None, "terms": cells[2] or None})
                elif current == "schedule_h":
                    if cells[0] and cells[0] not in ("Trip Details", "Source"):
                        out["schedule_h"].append([c for c in cells if c])
                elif current == "schedule_g":
                    if cells[0] and "Source" not in cells[0]:
                        out["schedule_g"].append([c for c in cells if c])

    return {"source_url": src if src.startswith("http") else None,
            "filing_id": header.get("filing_id"), "pages": len(pdf.pages),
            "header": header,
            "counts": {k: len(v) for k, v in out.items()}, **out}


if __name__ == "__main__":
    print(json.dumps(parse(sys.argv[1]), indent=2, ensure_ascii=False))
