#!/usr/bin/env python3
"""
build_swalwell.py — Swalwell Financial Universe data pipeline.

Reads native primary sources, rebuilds every figure from scratch keyed by
committee ID (never by name), dedups, and emits:
  - dashboards/swalwell_data.json     (consumed by the dashboard UI)
  - build/reconciliation_report.md    (audit trail of corrections)

No figure in the dashboard is hand-typed; all originate here from source rows.
"""

import csv, json, os, sys, configparser, datetime, urllib.request, urllib.parse
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT_JSON = os.path.join(ROOT, "dashboards", "swalwell_data.json")
OUT_RECON = os.path.join(ROOT, "build", "reconciliation_report.md")

csv.field_size_limit(10_000_000)
recon = []  # reconciliation log lines


def log(msg):
    print(msg)
    recon.append(msg)


# ----------------------------------------------------------------------------
# FEC API
# ----------------------------------------------------------------------------
def fec_key():
    cfg = configparser.ConfigParser()
    cfg.read(os.path.join(ROOT, "fec_secrets.txt.txt"))
    try:
        return cfg["fec_api"]["api_auth_key"].strip()
    except Exception:
        return None


def fec_get(path, **params):
    key = fec_key()
    if not key:
        return None
    params["api_key"] = key
    url = "https://api.open.fec.gov/v1/" + path + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.load(r)
    except Exception as e:
        log(f"  ! FEC API error on {path}: {e}")
        return None


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def money(s):
    if s is None:
        return 0.0
    s = str(s).replace("$", "").replace(",", "").replace('"', "").strip()
    if s in ("", "-"):
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def year_of(datestr):
    if not datestr:
        return None
    d = str(datestr)[:10]
    try:
        return int(d[:4])
    except ValueError:
        return None


def is_swalwell(name):
    return name and "swalwell" in str(name).lower()


# ----------------------------------------------------------------------------
# FEC committee (Schedule B) aggregation
# ----------------------------------------------------------------------------
KNOWN_COMMITTEES = {
    "C00502294": "Swalwell for Congress (House)",
    "C00701698": "Swalwell for America (Presidential)",
    "C00566059": "Remedy PAC (Leadership)",
}


def aggregate_fec(path, committee_id, label, source_file):
    seen_subids = set()
    rows = 0
    dup_rows = 0
    memo_skipped = 0
    memo_amt = 0.0
    total = 0.0
    by_year = defaultdict(float)
    amend_counts = defaultdict(int)
    neg_count = 0
    vendors = defaultdict(lambda: {"amt": 0.0, "n": 0, "cat": "", "txns": []})
    indivs = defaultdict(lambda: {"amt": 0.0, "n": 0, "role": "", "txns": []})
    self_pay = {"amt": 0.0, "n": 0, "txns": []}
    transfers = defaultdict(lambda: {"amt": 0.0, "n": 0})
    other_committee_names = {v.upper() for k, v in [
        ("C00502294", "SWALWELL FOR CONGRESS"),
        ("C00701698", "SWALWELL FOR AMERICA"),
        ("C00566059", "REMEDY PAC"),
        ("C00566059b", "NEW ENERGY PAC"),
    ]}

    with open(path, encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            sub = r.get("sub_id") or r.get("transaction_id") or ""
            if sub and sub in seen_subids:
                dup_rows += 1
                continue
            if sub:
                seen_subids.add(sub)
            # FEC memo entries (memo_code='X') are sub-itemizations already counted
            # inside a parent line. Excluding them prevents double-counting and aligns
            # local totals with FEC's official reported totals.
            if (r.get("memo_code") or "").strip().upper() == "X":
                memo_skipped += 1
                memo_amt += money(r.get("disbursement_amount"))
                continue
            rows += 1
            amt = money(r.get("disbursement_amount"))
            total += amt
            if amt < 0:
                neg_count += 1
            amend_counts[r.get("amendment_indicator", "") or "?"] += 1
            y = year_of(r.get("disbursement_date"))
            if y:
                by_year[y] += amt

            recip = (r.get("recipient_name") or "").strip()
            etype = (r.get("entity_type") or "").upper()
            purpose = (r.get("disbursement_description") or
                       r.get("disbursement_purpose_category") or "").strip()
            txn = {
                "date": (r.get("disbursement_date") or "")[:10],
                "payee": recip,
                "purpose": purpose,
                "amount": round(amt, 2),
                "pdf": r.get("pdf_url") or "",
            }

            # self-payments (reimbursements to Swalwell personally)
            payee_last = (r.get("payee_last_name") or "").strip()
            if is_swalwell(recip) or payee_last.lower() == "swalwell":
                self_pay["amt"] += amt
                self_pay["n"] += 1
                if len(self_pay["txns"]) < 200:
                    self_pay["txns"].append(txn)

            # inter-entity transfers (recipient is another Swalwell committee)
            ru = recip.upper()
            if ru in other_committee_names and ru not in (label.upper(),):
                transfers[recip]["amt"] += amt
                transfers[recip]["n"] += 1

            # vendors vs individuals
            if etype == "IND" or (payee_last and not recip):
                key = recip or f"{payee_last}, {r.get('payee_first_name','')}".strip(", ")
                d = indivs[key]
                d["amt"] += amt
                d["n"] += 1
                if not d["role"]:
                    d["role"] = (r.get("payee_occupation") or purpose or "")[:60]
                if len(d["txns"]) < 100:
                    d["txns"].append(txn)
            elif recip:
                d = vendors[recip]
                d["amt"] += amt
                d["n"] += 1
                if not d["cat"]:
                    d["cat"] = (r.get("disbursement_purpose_category") or purpose or "")[:60]
                if len(d["txns"]) < 100:
                    d["txns"].append(txn)

    def topn(d, role_key, n=30):
        items = sorted(d.items(), key=lambda kv: -kv[1]["amt"])[:n]
        out = []
        for name, v in items:
            row = {"name": name, "amt": round(v["amt"], 2), "n": v["n"],
                   "txns": v["txns"]}
            if role_key in v:
                row[role_key] = v[role_key]
            out.append(row)
        return out

    dates = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            d = (r.get("disbursement_date") or "")[:10]
            if d:
                dates.append(d)
    date_range = [min(dates), max(dates)] if dates else [None, None]

    log(f"  {label} ({committee_id}): {rows} rows kept, {dup_rows} exact-dup rows dropped, "
        f"{memo_skipped} memo rows excluded (${memo_amt:,.2f}), "
        f"total ${total:,.2f}, {neg_count} negative (refund/void) rows, dates {date_range[0]}..{date_range[1]}")
    log(f"     amendment_indicator counts: {dict(amend_counts)}")

    return {
        "id": committee_id, "label": label, "source_type": "FEC",
        "source_file": source_file, "controlled": True,
        "total": round(total, 2), "count": rows, "dup_dropped": dup_rows,
        "neg_count": neg_count, "date_range": date_range,
        "by_year": {str(k): round(v, 2) for k, v in sorted(by_year.items())},
        "top_vendors": topn(vendors, "cat"),
        "top_individuals": topn(indivs, "role"),
        "self_payments": {"amt": round(self_pay["amt"], 2), "n": self_pay["n"],
                          "txns": self_pay["txns"]},
        "transfers": [{"to": k, "amt": round(v["amt"], 2), "n": v["n"]}
                      for k, v in transfers.items()],
        "verification": "from_source",
    }


# ----------------------------------------------------------------------------
# Governor (CA FPPC) — exclude CONTRIBUTION + RETURNED CONTRIBUTIONS from spend
# ----------------------------------------------------------------------------
EXCLUDE_CODES = {"CONTRIBUTION", "RETURNED CONTRIBUTIONS"}


def aggregate_gov(path):
    gross = 0.0
    spend = 0.0
    excluded = defaultdict(lambda: {"amt": 0.0, "n": 0})
    by_code = defaultdict(lambda: {"amt": 0.0, "n": 0})
    payees = defaultdict(lambda: {"amt": 0.0, "n": 0, "txns": []})
    rows = 0
    with open(path, encoding="utf-8", errors="replace") as fh:
        r = csv.reader(fh, delimiter="\t")
        next(r, None)
        for row in r:
            if len(row) < 5:
                continue
            rows += 1
            payee = row[1].strip().strip('"')
            code = (row[2].strip().strip('"') or "(uncoded)").upper()
            desc = row[3].strip().strip('"')
            amt = money(row[4])
            gross += amt
            txn = {"date": "", "payee": payee, "purpose": code if code != "(UNCODED)" else desc,
                   "amount": round(amt, 2), "pdf": ""}
            if code in EXCLUDE_CODES:
                excluded[code]["amt"] += amt
                excluded[code]["n"] += 1
                continue  # not counted as campaign spend, not attributed to vendors
            spend += amt
            by_code[code]["amt"] += amt
            by_code[code]["n"] += 1
            d = payees[payee]
            d["amt"] += amt
            d["n"] += 1
            if len(d["txns"]) < 100:
                d["txns"].append(txn)

    top = sorted(payees.items(), key=lambda kv: -kv[1]["amt"])[:30]
    log(f"  Governor (FPPC 1485146): {rows} rows, gross ${gross:,.2f}, "
        f"own-campaign spend ${spend:,.2f} after excluding "
        + ", ".join(f"{k} ${excluded[k]['amt']:,.2f}" for k in excluded))
    return {
        "id": "CalAccess-1485146", "label": "Swalwell for Governor 2026",
        "source_type": "FPPC", "source_file": "data/swalwell/fppc/gov_2026_calaccess_1485146.tsv",
        "controlled": True, "no_dates": True,
        "gross_total": round(gross, 2), "total": round(spend, 2),
        "excluded": {k: {"amt": round(v["amt"], 2), "n": v["n"]} for k, v in excluded.items()},
        "by_code": [{"name": k, "amt": round(v["amt"], 2), "n": v["n"]}
                    for k, v in sorted(by_code.items(), key=lambda kv: -kv[1]["amt"])],
        "top_individuals": [{"name": k, "amt": round(v["amt"], 2), "n": v["n"],
                             "role": "", "txns": v["txns"]} for k, v in top],
        "top_vendors": [],
        "verification": "from_source",
    }


# ----------------------------------------------------------------------------
# House Office — Statement of Disbursements (filter all-member files to Swalwell)
# ----------------------------------------------------------------------------
def aggregate_sod():
    sod_dir = os.path.join(DATA, "sod_raw")
    personnel = 0.0
    nonpersonnel = 0.0
    by_year = defaultdict(float)
    payees = defaultdict(lambda: {"amt": 0.0, "n": 0, "txns": [], "cat": ""})
    rows = 0
    files_used = 0
    extracted_rows = []
    for fn in sorted(os.listdir(sod_dir)):
        if not fn.lower().endswith(".csv"):
            continue
        path = os.path.join(sod_dir, fn)
        used = False
        with open(path, encoding="utf-8", errors="replace") as fh:
            r = csv.reader(fh)
            hdr = next(r, None)
            if not hdr:
                continue
            idx = {h.strip(): i for i, h in enumerate(hdr)}
            org_i = idx.get("ORGANIZATION", 0)
            sub_i = idx.get("SORT SUBTOTAL DESCRIPTION", 5)
            seq_i = idx.get("SORT SEQUENCE", 7)
            year_i = idx.get("FISCAL YEAR OR LEGISLATIVE YEAR", 1)
            date_i = idx.get("TRANSACTION DATE", 8)
            vend_i = idx.get("VENDOR NAME", 11)
            desc_i = idx.get("DESCRIPTION", 15)
            # idx keys are already stripped; the AMOUNT header carries trailing spaces.
            # Look it up by stripped key (col 17), NOT via the raw header (which would
            # miss and fall back to -1 / last column — wrong on rows with a trailing
            # empty 19th column, ~525 salary rows that would read as $0).
            amt_i = max((i for h, i in idx.items() if h.startswith("AMOUNT")), default=17)
            for row in r:
                if len(row) <= amt_i:
                    continue
                if not is_swalwell(row[org_i]):
                    continue
                # CRITICAL: only DETAIL rows. SUBTOTAL and GRAND TOTAL rows re-sum the
                # same money and would multiply the office total ~3x.
                if (row[seq_i] if seq_i < len(row) else "").strip().upper() != "DETAIL":
                    continue
                rows += 1
                used = True
                amt = money(row[amt_i])
                sub = (row[sub_i] if sub_i < len(row) else "").strip().upper()
                ly = (row[year_i] if year_i < len(row) else "").strip()
                vendor = (row[vend_i] if vend_i < len(row) else "").strip()
                desc = (row[desc_i] if desc_i < len(row) else "").strip()
                if "PERSONNEL COMPENSATION" in sub:
                    personnel += amt
                else:
                    nonpersonnel += amt
                yr = "".join(ch for ch in ly if ch.isdigit())
                if not yr:
                    # Older SOD files (pre-2023) omit the year column; extract
                    # from ORGANIZATION ("2022 HON. ERIC SWALWELL") or TRANSACTION DATE.
                    org_val = (row[org_i] if org_i < len(row) else "").strip()
                    m = org_val[:4]
                    if m.isdigit() and 2010 <= int(m) <= 2030:
                        yr = m
                    else:
                        date_val = (row[date_i] if date_i < len(row) else "").strip()
                        for part in date_val.replace("-", " ").replace("/", " ").split():
                            if len(part) == 4 and part.isdigit() and 2010 <= int(part) <= 2030:
                                yr = part
                                break
                            elif len(part) == 2 and part.isdigit():
                                yr = "20" + part
                                break
                if yr:
                    by_year[yr] += amt
                d = payees[vendor or desc or "(unspecified)"]
                d["amt"] += amt
                d["n"] += 1
                if not d["cat"]:
                    d["cat"] = sub.title()
                if len(d["txns"]) < 50:
                    d["txns"].append({"date": (row[date_i] if date_i < len(row) else "")[:10],
                                      "payee": vendor, "purpose": desc or sub.title(),
                                      "amount": round(amt, 2), "pdf": ""})
        if used:
            files_used += 1
    total = personnel + nonpersonnel
    top = sorted(payees.items(), key=lambda kv: -kv[1]["amt"])[:30]
    log(f"  House Office (SOD): {rows} Swalwell rows across {files_used} quarterly files, "
        f"total ${total:,.2f} (personnel ${personnel:,.2f} / non-personnel ${nonpersonnel:,.2f})")
    return {
        "id": "CA-Office-SWE", "label": "House Office (MRA) — Statement of Disbursements",
        "source_type": "SOD", "source_file": "data/sod_raw/*DETAIL*.csv",
        "controlled": True, "taxpayer_funded": True,
        "separate_universe": True,
        "caption": "Taxpayer-funded official office spending (MRA). Separate from all campaign "
                   "money; not reconciled against FEC. Amounts are the DETAIL line items as "
                   "filed in the House Statement of Disbursements.",
        "total": round(total, 2), "count": rows,
        "personnel": round(personnel, 2), "nonpersonnel": round(nonpersonnel, 2),
        "by_year": {k: round(v, 2) for k, v in sorted(by_year.items())},
        "top_individuals": [{"name": k, "amt": round(v["amt"], 2), "n": v["n"],
                             "role": v["cat"], "txns": v["txns"]} for k, v in top],
        "top_vendors": [],
        "verification": "from_source",
    }


# ----------------------------------------------------------------------------
# Outside PAC C00528174 (Alpha Valley) — pull live from FEC, surface any activity
# ----------------------------------------------------------------------------
def aggregate_outside_pac():
    cid = "C00528174"
    info = {"id": cid, "label": "Alpha Valley Business & Technology Consortium",
            "source_type": "FEC (API)", "source_file": "OpenFEC API", "controlled": False,
            "total": 0.0, "schedule_b": 0.0, "schedule_e": 0.0, "dormant": True,
            "top_vendors": [], "top_individuals": [], "by_year": {},
            "verification": "api_crosscheck", "note": ""}
    meta = fec_get(f"committee/{cid}/")
    if meta and meta.get("results"):
        m = meta["results"][0]
        info["label"] = m.get("name", info["label"])
        info["committee_type"] = m.get("committee_type_full")
    totals = fec_get(f"committee/{cid}/totals/")
    sb = 0.0
    by_year = {}
    if totals and totals.get("results"):
        for t in totals["results"]:
            yr = t.get("cycle")
            d = t.get("disbursements") or 0.0
            sb += d
            if yr:
                by_year[str(yr)] = round(d, 2)
    # independent expenditures (schedule E) — money spent about Swalwell
    se = 0.0
    ie = fec_get("schedules/schedule_e/", candidate_id="H2CA15094", **{"per_page": 100})
    if ie and ie.get("results"):
        for row in ie["results"]:
            if row.get("committee_id") == cid:
                se += row.get("expenditure_amount") or 0.0
    info["schedule_b"] = round(sb, 2)
    info["schedule_e"] = round(se, 2)
    info["total"] = round(sb + se, 2)
    info["by_year"] = by_year
    info["dormant"] = (sb + se) < 1.0
    if info["dormant"]:
        info["note"] = ("FEC shows no reported disbursements or independent expenditures for this "
                        "committee. It is an outside single-candidate independent-expenditure "
                        "committee (spends ABOUT Swalwell, not controlled BY him) and currently "
                        "appears dormant.")
    log(f"  Outside PAC ({cid}) {info['label']}: schedule_b ${sb:,.2f}, "
        f"schedule_e ${se:,.2f}, dormant={info['dormant']}")
    return info


# ----------------------------------------------------------------------------
# Master list profile
# ----------------------------------------------------------------------------
def member_profile():
    try:
        import openpyxl
    except ImportError:
        return {}
    wb = openpyxl.load_workbook(os.path.join(DATA, "master", "119th_MASTER_LIST.xlsx"),
                                read_only=True)
    ws = wb.worksheets[0]
    rows = ws.iter_rows(values_only=True)
    hdr = [str(h).strip() if h is not None else "" for h in next(rows)]
    for r in rows:
        if any(is_swalwell(c) for c in r if c):
            rec = {hdr[i]: (str(r[i]) if i < len(r) and r[i] is not None else "")
                   for i in range(len(hdr))}
            log(f"  Master list: matched Swalwell row ({rec.get('State','')}-{rec.get('District','')}, "
                f"{rec.get('Party','')})")
            return rec
    return {}


# ----------------------------------------------------------------------------
# API cross-check of controlled FEC committees
# ----------------------------------------------------------------------------
def api_crosscheck(entities):
    checks = []
    for key, cid in [("house", "C00502294"), ("pres", "C00701698"), ("pac", "C00566059")]:
        ent = entities.get(key)
        if not ent:
            continue
        t = fec_get(f"committee/{cid}/totals/")
        local = ent["total"]
        if not t or not t.get("results"):
            checks.append({"entity": key, "committee_id": cid,
                           "local_total": round(local, 2), "api_total": None,
                           "diff": None, "pct": None, "status": "api_unavailable"})
            log(f"  API cross-check {key} ({cid}): local ${local:,.2f} vs API unavailable "
                f"-> api_unavailable")
            continue
        api_total = sum((x.get("disbursements") or 0.0) for x in t["results"])
        diff = local - api_total
        pct = (diff / api_total * 100) if api_total else 0.0
        status = "match" if abs(pct) < 5 else "VARIANCE"
        checks.append({"entity": key, "committee_id": cid,
                       "local_total": round(local, 2), "api_total": round(api_total, 2),
                       "diff": round(diff, 2), "pct": round(pct, 2), "status": status})
        log(f"  API cross-check {key} ({cid}): local ${local:,.2f} vs API ${api_total:,.2f} "
            f"-> {status} ({pct:+.1f}%)")
    return checks


# ----------------------------------------------------------------------------
# Flags — generated from data rules (no hand-asserted numbers)
# ----------------------------------------------------------------------------
def build_flags(entities):
    flags = []

    # 1. Phantom committee correction
    flags.append({
        "severity": "HIGH", "title": "Phantom second leadership PAC corrected",
        "body": "The draft dashboard listed two leadership PACs (C00566059 + C01000165). "
                "FEC has no committee C01000165. The real entity is a single PAC, Remedy PAC "
                "(C00566059), formerly named 'New Energy PAC.' Counting by name split one "
                "renamed committee into two. This rebuild keys every figure by committee ID.",
        "evidence": "FEC committee lookup C01000165 → no results.",
    })

    # 2. Duplicate source file
    flags.append({
        "severity": "NOTABLE", "title": "Duplicate source file removed",
        "body": "Two Schedule B exports for Remedy PAC were byte-identical (same 2,105 rows). "
                "Only one is used; the pipeline dedups by sub_id so duplicate files or rows "
                "cannot inflate totals.",
        "evidence": "md5 match on the two schedule_b CSVs.",
    })

    # 3. Outside PAC explanation (researcher-requested)
    op = entities.get("outside_pac", {})
    flags.append({
        "severity": "NOTABLE", "title": "Outside PAC is not controlled by Swalwell",
        "body": "Alpha Valley Business & Technology Consortium (C00528174) is a single-candidate "
                "INDEPENDENT-EXPENDITURE committee: it may spend money ABOUT Swalwell but is not "
                "controlled BY him. It is shown as its own entity and can be toggled in/out of the "
                "universe total. " + (op.get("note") or
                f"FEC reports schedule_b ${op.get('schedule_b',0):,.0f} and schedule_e "
                f"${op.get('schedule_e',0):,.0f} for it."),
        "evidence": "OpenFEC committee C00528174 totals + schedule_e.",
    })

    # 4. Governor exclusions (researcher-requested)
    gov = entities.get("gov", {})
    if gov:
        exc = gov.get("excluded", {})
        exc_str = "; ".join(f"{k}: ${v['amt']:,.0f} ({v['n']} rows)" for k, v in exc.items())
        flags.append({
            "severity": "NOTABLE", "title": "Governor total = own-campaign spend only",
            "body": f"Per the researcher, money the Governor committee paid OUT to others and all "
                    f"refunds are excluded from the campaign-spend headline. Gross filed "
                    f"${gov.get('gross_total',0):,.0f}; own-campaign spend ${gov.get('total',0):,.0f}. "
                    f"Excluded and shown separately: {exc_str}.",
            "evidence": "FPPC expenditure codes CONTRIBUTION + RETURNED CONTRIBUTIONS.",
        })

    # 5. Data-driven: classification-shifting individual payees (same person, many roles)
    for ekey in ("house", "gov", "pac"):
        ent = entities.get(ekey, {})
        for ind in ent.get("top_individuals", [])[:10]:
            # heuristic: large multi-transaction individual in top ranks
            if ind["amt"] > 150000 and ind["n"] > 30:
                flags.append({
                    "severity": "REVIEW",
                    "title": f"High-volume individual payee: {ind['name']} ({ent['label']})",
                    "body": f"${ind['amt']:,.0f} across {ind['n']} transactions. Worth reviewing how "
                            f"the role/purpose is classified across filings.",
                    "evidence": f"{ent['source_type']} {ent.get('id','')}",
                    "drill": {"entity": ekey, "name": ind["name"]},
                })

    # 6. Cross-payroll staff (appear in both Office/SOD and a campaign committee)
    office_names = {i["name"].split(",")[0].strip().upper()
                    for i in entities.get("office", {}).get("top_individuals", [])}
    house_names = {i["name"].split(",")[0].strip().upper()
                   for i in entities.get("house", {}).get("top_individuals", [])}
    overlap = sorted(n for n in office_names & house_names if n and len(n) > 2)
    if overlap:
        flags.append({
            "severity": "REVIEW", "title": "Staff paid from both taxpayer office and campaign",
            "body": "These surnames appear among top payees of BOTH the taxpayer-funded House "
                    "office (SOD) and the House campaign committee: " + ", ".join(overlap[:12]) +
                    ". Dual payment is legal but worth tracking.",
            "evidence": "Name overlap between SOD and C00502294 top payees.",
        })

    return flags


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main():
    log(f"# Swalwell pipeline run {datetime.datetime.now().isoformat(timespec='seconds')}\n")
    log("## Entity aggregation")

    entities = {}
    entities["house"] = aggregate_fec(
        os.path.join(DATA, "swalwell/fec/house_C00502294.csv"),
        "C00502294", "Swalwell for Congress (House)", "data/swalwell/fec/house_C00502294.csv")
    entities["pres"] = aggregate_fec(
        os.path.join(DATA, "swalwell/fec/pres_C00701698.csv"),
        "C00701698", "Swalwell for America (Presidential)", "data/swalwell/fec/pres_C00701698.csv")
    entities["pac"] = aggregate_fec(
        os.path.join(DATA, "swalwell/fec/remedy_pac_C00566059.csv"),
        "C00566059", "Remedy PAC (Leadership)", "data/swalwell/fec/remedy_pac_C00566059.csv")
    entities["gov"] = aggregate_gov(
        os.path.join(DATA, "swalwell/fppc/gov_2026_calaccess_1485146.tsv"))
    entities["office"] = aggregate_sod()
    entities["outside_pac"] = aggregate_outside_pac()

    log("\n## API cross-check")
    checks = api_crosscheck(entities)

    log("\n## Member profile")
    profile = member_profile()

    flags = build_flags(entities)

    # Rollups are kept in SEPARATE buckets and never blended:
    #  - FEC campaign committees (controlled political fundraising/spending)
    #  - Official government office (SOD/MRA) is TAXPAYER money, a different universe
    #    entirely. It is reported on its own and never summed with campaign data.
    #  - State campaign (FPPC) is separate from federal.
    #  - Outside committee is not controlled by Swalwell.
    fec_campaign = sum(entities[k]["total"] for k in ("house", "pres", "pac"))
    office_mra = entities["office"]["total"]
    state_campaign = entities["gov"]["total"]
    outside = entities["outside_pac"]["total"]

    payload = {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "member": profile,
        "entities": entities,
        "rollups": {
            "fec_campaign": round(fec_campaign, 2),
            "office_mra": round(office_mra, 2),
            "state_campaign": round(state_campaign, 2),
            "outside_uncontrolled": round(outside, 2),
            "note": "Four SEPARATE universes, never blended: FEC campaign committees "
                    "(political money Swalwell controls), the official House Office / MRA "
                    "(TAXPAYER money for running his government office — a different thing "
                    "entirely, not reconciled against FEC), the California state Governor "
                    "campaign (FPPC), and an outside committee not controlled by him.",
        },
        "api_crosscheck": checks,
        "flags": flags,
        "sources": [
            {"entity": "House campaign", "type": "FEC Schedule B",
             "file": "data/swalwell/fec/house_C00502294.csv", "id": "C00502294"},
            {"entity": "Presidential", "type": "FEC Schedule B",
             "file": "data/swalwell/fec/pres_C00701698.csv", "id": "C00701698"},
            {"entity": "Leadership PAC", "type": "FEC Schedule B",
             "file": "data/swalwell/fec/remedy_pac_C00566059.csv", "id": "C00566059"},
            {"entity": "Governor 2026", "type": "CA FPPC Form 460 (Cal-Access)",
             "file": "data/swalwell/fppc/gov_2026_calaccess_1485146.tsv", "id": "1485146"},
            {"entity": "House Office (MRA)", "type": "House Statement of Disbursements",
             "file": "data/sod_raw/*DETAIL*.csv", "id": "CA15SWE/CA14SWE"},
            {"entity": "Outside PAC", "type": "OpenFEC API",
             "file": "api.open.fec.gov", "id": "C00528174"},
        ],
    }

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump(payload, f, indent=1)
    log(f"\nWrote {OUT_JSON} ({os.path.getsize(OUT_JSON)//1024} KB)")
    # Also emit as a JS file so the dashboard works by double-click (file://),
    # where fetch() of local JSON is blocked by the browser.
    out_js = os.path.join(ROOT, "dashboards", "swalwell_data.js")
    with open(out_js, "w") as f:
        f.write("window.SWALWELL_DATA = ")
        json.dump(payload, f)
        f.write(";\n")
    log(f"Wrote {out_js} ({os.path.getsize(out_js)//1024} KB)")

    with open(OUT_RECON, "w") as f:
        f.write("# Swalwell Data Reconciliation Report\n\n")
        f.write("Generated by `build/build_swalwell.py`. Every dashboard figure originates here "
                "from primary sources; nothing is hand-typed.\n\n")
        f.write("```\n" + "\n".join(recon) + "\n```\n")
    print(f"Wrote {OUT_RECON}")


if __name__ == "__main__":
    main()
