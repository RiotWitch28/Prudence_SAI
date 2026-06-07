#!/usr/bin/env python3
"""
build_member.py — generalized Financial Universe data pipeline (multi-member).

Generalizes build_swalwell.py: instead of hardcoded Swalwell committee IDs and
local CSVs, it reads a member from data/members/sample_members_10.json, resolves
their FEC candidate IDs to committee IDs, pulls Schedule B disbursements live from
the OpenFEC API, aggregates the same way, filters the all-member SOD files to that
member, and writes:
  - data/members/<bioguide>/data.json
  - data/members/<bioguide>/data.js   (window.MEMBER_DATA = ...; for file:// use)
  - data/members/<bioguide>/reconciliation_report.md

Swalwell-only feeds (CA governor / FPPC, the Alpha Valley outside PAC) are NOT
reproduced here; Swalwell keeps his existing hand-built dashboard as the reference.

Usage:
  python3 build/build_member.py K000391        # one member by bioguide
  python3 build/build_member.py --all          # every member in the manifest (except Swalwell)
"""

import csv, json, os, sys, time, configparser, datetime, unicodedata
import urllib.request, urllib.parse
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
MANIFEST = os.path.join(DATA, "members", "sample_members_10.json")
SECRETS = os.path.join(ROOT, "_source-data", "fec_secrets.txt.txt")

csv.field_size_limit(10_000_000)


# ---------------------------------------------------------------- FEC API
def fec_key():
    cfg = configparser.ConfigParser()
    cfg.read(SECRETS)
    return cfg["fec_api"]["api_auth_key"].strip()


_KEY = None
def fec_get(path, _tries=4, **params):
    global _KEY
    if _KEY is None:
        _KEY = fec_key()
    params["api_key"] = _KEY
    url = "https://api.open.fec.gov/v1/" + path + "?" + urllib.parse.urlencode(params)
    for attempt in range(_tries):
        try:
            with urllib.request.urlopen(url, timeout=40) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:                 # rate limited — back off
                time.sleep(2 * (attempt + 1)); continue
            if attempt == _tries - 1:
                raise
            time.sleep(1.5 * (attempt + 1))
        except Exception:
            if attempt == _tries - 1:
                raise
            time.sleep(1.5 * (attempt + 1))
    return None


# ---------------------------------------------------------------- helpers
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


def year_of(d):
    if not d:
        return None
    try:
        return int(str(d)[:4])
    except ValueError:
        return None


def deaccent(s):
    return "".join(c for c in unicodedata.normalize("NFKD", str(s or ""))
                   if not unicodedata.combining(c)).upper()


# ---------------------------------------------------------------- vendor categorization
# Keyword buckets over vendor name + description (FEC purpose_category is mostly "OTHER").
# id, label, icon, color, keyword list
VENDOR_CATEGORIES = [
    ("media", "Media & Advertising", "📺", "#2a4f7c",
     ["ADVERTIS", "MEDIA", "DIGITAL", "VIDEO", "TELEVIS", "RADIO", "PRODUCTION",
      "CREATIVE", "SOCIAL", "MAILER", "DIRECT MAIL", "PRINTING", "GRAPHIC", "GOOGLE", "META PLATFORMS", "FACEBOOK"]),
    ("fundraising", "Fundraising & Operations", "💰", "#2d6a4f",
     ["FUNDRAIS", "ACTBLUE", "WINRED", "NGP", "ANEDOT", "DONATION", "MERCHANT",
      "PROCESSING", "PAYROLL", "PAYLOCITY", "COMPLIANCE", "ACCOUNTING", "BOOKKEEP", "CRM", " LIST"]),
    ("consulting", "Consulting & Strategy", "🎯", "#b45309",
     ["CONSULT", "STRATEG", "ADVISOR", "ANALYTICS"]),
    ("legal", "Legal Services", "⚖️", "#9b2335",
     ["LEGAL", " LAW", "LAW,", "LLP", "ATTORNEY", "COUNSEL", "PLLC"]),
    ("polling", "Polling & Research", "📊", "#5b21b6", ["POLL", "SURVEY", "RESEARCH"]),
    ("travel", "Travel & Transportation", "✈️", "#0e7490",
     ["TRAVEL", "AIRLINE", "AIRWAYS", "AIR ", "FLIGHT", "UBER", "LYFT", "TAXI",
      "AMTRAK", "RAIL", "CAR SERVICE", "TRANSPORT", "DELTA", "UNITED AIR", "SOUTHWEST AIR"]),
    ("lodging", "Hotels & Lodging", "🏨", "#92400e",
     ["HOTEL", " INN", "RESORT", "LODG", "SUITES", "MARRIOTT", "HILTON", "HYATT",
      "RITZ", "SHERATON", "WESTIN", "LOEWS", "AIRBNB"]),
    ("events", "Events & Catering", "🍽️", "#d97706",
     ["CATERING", "VENUE", "EVENT", "RESTAURANT", "BANQUET", "CAFE"]),
    ("contributions", "Contributions & Transfers", "🔁", "#475569", []),
    ("salary", "Salary & Payroll", "👥", "#1e3a5f", ["SALARY", "PAYROLL", "WAGES"]),
    ("admin", "Administrative & Other", "🗂️", "#64748b",
     ["RENT", "OFFICE", "SUPPL", "EQUIP", "POSTAGE", "BANK", " FEE", "UTILIT",
      "TELEPHONE", "STORAGE", "INSURANCE", "SOFTWARE", "WEB", "HOSTING"]),
]
CATEGORY_META = {c[0]: {"label": c[1], "icon": c[2], "color": c[3]} for c in VENDOR_CATEGORIES}


def categorize(name, purpose_cat, desc):
    pc = (purpose_cat or "").upper().strip()
    # Strong FEC purpose-category signals win over generic name keywords.
    strong = {"TRANSFERS": "contributions", "CONTRIBUTIONS": "contributions",
              "SALARY": "salary", "ADVERTISING": "media", "FUNDRAISING": "fundraising",
              "POLLING": "polling", "TRAVEL": "travel"}
    if pc in strong:
        return strong[pc]
    s = f" {name} {desc} ".upper()
    for cid, _, _, _, kws in VENDOR_CATEGORIES:
        if kws and any(kw in s for kw in kws):
            return cid
    return "media" if pc == "MATERIALS" else "admin"


def by_category_out(cat_totals, cat_vendors, cat_n):
    out = []
    for cid in cat_totals:
        vs = sorted(cat_vendors[cid].items(), key=lambda kv: -kv[1])[:15]
        out.append({"id": cid, "label": CATEGORY_META[cid]["label"],
                    "icon": CATEGORY_META[cid]["icon"], "color": CATEGORY_META[cid]["color"],
                    "total": round(cat_totals[cid], 2), "n": cat_n[cid],
                    "vendors": [{"name": n, "total": round(a, 2)} for n, a in vs]})
    return sorted(out, key=lambda c: -c["total"])


# ---------------------------------------------------------------- FEC resolve + pull
def resolve_committees(fec_id):
    """candidate id (H/S/P...) -> its committees; committee id (C...) -> itself."""
    fec_id = (fec_id or "").strip()
    if not fec_id:
        return []
    if fec_id.startswith("C"):
        meta = fec_get(f"committee/{fec_id}/")
        name = (meta["results"][0]["name"] if meta and meta.get("results") else fec_id)
        return [(fec_id, name)]
    d = fec_get(f"candidate/{fec_id}/committees/", per_page=50)
    out = []
    for c in (d or {}).get("results", []):
        desig = (c.get("designation") or "")
        # principal (P) and authorized (A) committees are the candidate's own money
        if desig in ("P", "A", "") :
            out.append((c.get("committee_id"), c.get("name")))
    return out


def fetch_schedule_b(committee_id, log):
    """Yield every Schedule B disbursement row for a committee (seek pagination)."""
    seek = {}
    pulled = 0
    page = 0
    while True:
        d = fec_get("schedules/schedule_b/", committee_id=committee_id,
                    per_page=100, sort="disbursement_date", **seek)
        if not d:
            break
        results = d.get("results", [])
        if not results:
            break
        for r in results:
            yield r
        pulled += len(results)
        page += 1
        if page % 20 == 0:
            log(f"     ...{committee_id}: {pulled} rows pulled")
        li = (d.get("pagination") or {}).get("last_indexes")
        if not li:
            break
        seek = {k: v for k, v in li.items() if v is not None}
        time.sleep(0.15)   # be polite to the API


# ---------------------------------------------------------------- aggregation
def aggregate_committee(committee_id, label, rows_iter, member, other_committee_names, log):
    last_up = deaccent(member["last_name"])
    seen = set(); rows = 0; dup = 0; memo_n = 0; memo_amt = 0.0; total = 0.0; neg = 0
    by_year = defaultdict(float)
    vendors = defaultdict(lambda: {"amt": 0.0, "n": 0, "cat": "", "txns": []})
    indivs = defaultdict(lambda: {"amt": 0.0, "n": 0, "role": "", "txns": []})
    self_pay = {"amt": 0.0, "n": 0, "txns": []}
    transfers = defaultdict(lambda: {"amt": 0.0, "n": 0})
    dates = []
    cat_totals = defaultdict(float)
    cat_vendors = defaultdict(lambda: defaultdict(float))
    cat_n = defaultdict(int)

    for r in rows_iter:
        sub = r.get("sub_id") or r.get("transaction_id") or ""
        if sub and sub in seen:
            dup += 1; continue
        if sub:
            seen.add(sub)
        if (r.get("memo_code") or "").strip().upper() == "X":
            memo_n += 1; memo_amt += money(r.get("disbursement_amount")); continue
        rows += 1
        amt = money(r.get("disbursement_amount")); total += amt
        if amt < 0:
            neg += 1
        y = year_of(r.get("disbursement_date"))
        if y:
            by_year[y] += amt
        dd = (r.get("disbursement_date") or "")[:10]
        if dd:
            dates.append(dd)
        recip = (r.get("recipient_name") or "").strip()
        etype = (r.get("entity_type") or "").upper()
        purpose = (r.get("disbursement_description")
                   or r.get("disbursement_purpose_category") or "").strip()
        payee_last = (r.get("payee_last_name") or "").strip()
        txn = {"date": dd, "payee": recip, "purpose": purpose,
               "amount": round(amt, 2), "pdf": r.get("pdf_url") or ""}

        # vendor categorization (over ALL rows, for an accurate per-category breakdown)
        bucket = categorize(recip, r.get("disbursement_purpose_category"), purpose)
        cat_totals[bucket] += amt
        cat_n[bucket] += 1
        if recip:
            cat_vendors[bucket][recip] += amt

        # self-payment (reimbursement to the member personally)
        if last_up and last_up in deaccent(recip):
            self_pay["amt"] += amt; self_pay["n"] += 1
            if len(self_pay["txns"]) < 200:
                self_pay["txns"].append(txn)
        # inter-entity transfer (to another of this member's committees)
        ru = recip.upper()
        if ru in other_committee_names and ru != label.upper():
            transfers[recip]["amt"] += amt; transfers[recip]["n"] += 1

        if etype == "IND" or (payee_last and not recip):
            key = recip or f"{payee_last}, {r.get('payee_first_name','')}".strip(", ")
            d = indivs[key]; d["amt"] += amt; d["n"] += 1
            if not d["role"]:
                d["role"] = (r.get("payee_occupation") or purpose or "")[:60]
            if len(d["txns"]) < 100:
                d["txns"].append(txn)
        elif recip:
            d = vendors[recip]; d["amt"] += amt; d["n"] += 1
            if not d["cat"]:
                d["cat"] = (r.get("disbursement_purpose_category") or purpose or "")[:60]
            if len(d["txns"]) < 100:
                d["txns"].append(txn)

    def topn(d, role_key, n=30):
        out = []
        for name, v in sorted(d.items(), key=lambda kv: -kv[1]["amt"])[:n]:
            row = {"name": name, "amt": round(v["amt"], 2), "n": v["n"], "txns": v["txns"]}
            row[role_key] = v.get(role_key, "")
            out.append(row)
        return out

    date_range = [min(dates), max(dates)] if dates else [None, None]
    log(f"  {label} ({committee_id}): {rows} rows, {dup} dup dropped, "
        f"{memo_n} memo excluded (${memo_amt:,.0f}), total ${total:,.0f}, "
        f"{neg} negative, dates {date_range[0]}..{date_range[1]}")
    return {
        "id": committee_id, "label": label, "source_type": "FEC (API)",
        "source_file": "api.open.fec.gov schedule_b", "controlled": True,
        "total": round(total, 2), "count": rows, "dup_dropped": dup,
        "neg_count": neg, "date_range": date_range,
        "by_year": {str(k): round(v, 2) for k, v in sorted(by_year.items())},
        "top_vendors": topn(vendors, "cat"),
        "top_individuals": topn(indivs, "role"),
        "self_payments": {"amt": round(self_pay["amt"], 2), "n": self_pay["n"],
                          "txns": self_pay["txns"]},
        "transfers": [{"to": k, "amt": round(v["amt"], 2), "n": v["n"]}
                      for k, v in transfers.items()],
        "by_category": by_category_out(cat_totals, cat_vendors, cat_n),
        "verification": "from_source",
    }


# ---------------------------------------------------------------- SOD (House office)
def aggregate_sod(member, log):
    sod_dir = os.path.join(DATA, "sod_raw")
    if not os.path.isdir(sod_dir):
        log("  ! no data/sod_raw — skipping office"); return None
    last = deaccent(member["last_name"]); first = deaccent(member["first_name"])
    personnel = 0.0; nonpersonnel = 0.0; rows = 0; files_used = 0
    by_year = defaultdict(float)
    payees = defaultdict(lambda: {"amt": 0.0, "n": 0, "txns": [], "cat": ""})
    matched_orgs = set()
    cat_totals = defaultdict(float)
    cat_vendors = defaultdict(lambda: defaultdict(float))
    cat_n = defaultdict(int)

    def is_member(org):
        o = deaccent(org)
        if last and last in o:
            # confirm with first name when present (guards common surnames);
            # nickname mismatches still pass on last name alone if first absent
            return (not first) or first in o or "HON" in o and last in o
        return False

    for fn in sorted(os.listdir(sod_dir)):
        if not fn.lower().endswith(".csv"):
            continue
        path = os.path.join(sod_dir, fn); used = False
        with open(path, encoding="utf-8", errors="replace") as fh:
            r = csv.reader(fh); hdr = next(r, None)
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
            amt_i = max((i for h, i in idx.items() if h.startswith("AMOUNT")), default=17)
            for row in r:
                if len(row) <= amt_i:
                    continue
                org = row[org_i] if org_i < len(row) else ""
                if not is_member(org):
                    continue
                if (row[seq_i] if seq_i < len(row) else "").strip().upper() != "DETAIL":
                    continue
                rows += 1; used = True; matched_orgs.add(org.strip())
                amt = money(row[amt_i])
                sub = (row[sub_i] if sub_i < len(row) else "").strip().upper()
                ly = (row[year_i] if year_i < len(row) else "").strip()
                vendor = (row[vend_i] if vend_i < len(row) else "").strip()
                desc = (row[desc_i] if desc_i < len(row) else "").strip()
                if "PERSONNEL COMPENSATION" in sub:
                    personnel += amt
                else:
                    nonpersonnel += amt
                office_pc = "SALARY" if "PERSONNEL COMPENSATION" in sub else None
                bucket = categorize(vendor, office_pc, f"{sub} {desc}")
                cat_totals[bucket] += amt
                cat_n[bucket] += 1
                if vendor:
                    cat_vendors[bucket][vendor] += amt
                yr = "".join(ch for ch in ly if ch.isdigit())
                if not yr:
                    m = org.strip()[:4]
                    if m.isdigit() and 2010 <= int(m) <= 2030:
                        yr = m
                if yr:
                    by_year[yr] += amt
                d = payees[vendor or desc or "(unspecified)"]
                d["amt"] += amt; d["n"] += 1
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
    log(f"  House Office (SOD): {rows} rows across {files_used} files, total ${total:,.0f} "
        f"(personnel ${personnel:,.0f} / non ${nonpersonnel:,.0f}); orgs matched: {sorted(matched_orgs)[:3]}"
        + (" ..." if len(matched_orgs) > 3 else ""))
    return {
        "id": f"OFFICE-{member['bioguide_id']}",
        "label": "House Office (MRA) — Statement of Disbursements",
        "source_type": "SOD", "source_file": "data/sod_raw/*DETAIL*.csv",
        "controlled": True, "taxpayer_funded": True, "separate_universe": True,
        "caption": "Taxpayer-funded official office spending (MRA). Separate from all "
                   "campaign money; not reconciled against FEC.",
        "total": round(total, 2), "count": rows,
        "personnel": round(personnel, 2), "nonpersonnel": round(nonpersonnel, 2),
        "by_year": {k: round(v, 2) for k, v in sorted(by_year.items())},
        "top_individuals": [{"name": k, "amt": round(v["amt"], 2), "n": v["n"],
                             "role": v["cat"], "txns": v["txns"]} for k, v in top],
        "top_vendors": [], "verification": "from_source",
        "by_category": by_category_out(cat_totals, cat_vendors, cat_n),
        "matched_orgs": sorted(matched_orgs),
    }


# ---------------------------------------------------------------- cross-check + flags
def api_crosscheck(entities, log):
    checks = []
    for key, ent in entities.items():
        cid = ent.get("id", "")
        if not cid.startswith("C"):
            continue
        t = fec_get(f"committee/{cid}/totals/")
        local = ent["total"]
        if not t or not t.get("results"):
            checks.append({"entity": key, "committee_id": cid, "local_total": round(local, 2),
                           "api_total": None, "status": "api_unavailable"}); continue
        api_total = sum((x.get("disbursements") or 0.0) for x in t["results"])
        diff = local - api_total
        pct = (diff / api_total * 100) if api_total else 0.0
        status = "match" if abs(pct) < 5 else "VARIANCE"
        checks.append({"entity": key, "committee_id": cid, "local_total": round(local, 2),
                       "api_total": round(api_total, 2), "diff": round(diff, 2),
                       "pct": round(pct, 2), "status": status})
        log(f"  cross-check {key} ({cid}): local ${local:,.0f} vs API ${api_total:,.0f} -> {status} ({pct:+.1f}%)")
    return checks


def build_flags(entities):
    """Data-driven, generalizable flags only (no member-specific hand assertions)."""
    flags = []
    for ekey, ent in entities.items():
        for ind in ent.get("top_individuals", [])[:10]:
            if ind["amt"] > 150000 and ind["n"] > 30:
                flags.append({"severity": "REVIEW",
                              "title": f"High-volume individual payee: {ind['name']} ({ent['label']})",
                              "body": f"${ind['amt']:,.0f} across {ind['n']} transactions. "
                                      f"Worth reviewing how the role/purpose is classified.",
                              "evidence": f"{ent['source_type']} {ent.get('id','')}",
                              "drill": {"entity": ekey, "name": ind["name"]}})
    office = entities.get("office", {})
    house = entities.get("house", {})
    if office and house:
        on = {i["name"].split(",")[0].strip().upper() for i in office.get("top_individuals", [])}
        hn = {i["name"].split(",")[0].strip().upper() for i in house.get("top_individuals", [])}
        overlap = sorted(n for n in on & hn if n and len(n) > 2)
        if overlap:
            flags.append({"severity": "REVIEW",
                          "title": "Staff paid from both taxpayer office and campaign",
                          "body": "Surnames among top payees of BOTH the taxpayer-funded House office "
                                  "(SOD) and the House campaign committee: " + ", ".join(overlap[:12]) +
                                  ". Dual payment is legal but worth tracking.",
                          "evidence": "Name overlap between SOD and the campaign committee top payees."})
    return flags


# ---------------------------------------------------------------- main
def build_one(m, log):
    bio = m["bioguide_id"]
    log(f"# {m['first_name']} {m['last_name']} ({bio}) — {m['state']}-{m['district']} {m['party']}")
    fec = m["fec_ids"]
    role_map = [("house", fec.get("house_campaign")), ("senate", fec.get("senate_run")),
                ("pres", fec.get("president_run")), ("pac", fec.get("leadership_pac")),
                ("other_pac", fec.get("other_pac"))]

    # resolve all committees first (so transfers can detect inter-entity movement)
    resolved = []   # (role, committee_id, name)
    for role, fid in role_map:
        if not fid:
            continue
        for cid, name in resolve_committees(fid):
            if cid:
                resolved.append((role, cid, name))
    other_names = {deaccent(n) for _, _, n in resolved}
    log(f"  committees: " + ", ".join(f"{r}:{cid}({n})" for r, cid, n in resolved) or "  (none)")

    entities = {}
    for role, cid, name in resolved:
        ent = aggregate_committee(cid, name or role, fetch_schedule_b(cid, log),
                                  m, other_names, log)
        # if a role has multiple committees, suffix the key
        key = role if role not in entities else f"{role}_{cid[-4:]}"
        entities[key] = ent

    office = aggregate_sod(m, log)
    if office:
        entities["office"] = office

    checks = api_crosscheck(entities, log)
    flags = build_flags(entities)

    fec_campaign = sum(e["total"] for k, e in entities.items() if k != "office")
    office_mra = entities.get("office", {}).get("total", 0.0)

    payload = {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "schema": "member-v1",
        "member": {k: m.get(k) for k in ("bioguide_id", "full_name", "first_name", "last_name",
                                          "state", "district", "party", "gender", "committees",
                                          "links", "status")},
        "entities": entities,
        "rollups": {"fec_campaign": round(fec_campaign, 2), "office_mra": round(office_mra, 2),
                    "note": "FEC campaign committees and the taxpayer-funded House Office (MRA) are "
                            "separate universes and never blended."},
        "api_crosscheck": checks,
        "flags": flags,
        "prudence": {"status": "baseline-pending",
                     "note": "Per-member Prudence analysis is generated in a later phase; this "
                             "member's editable Prudence layer lives alongside this file."},
        "sources": [{"entity": k, "type": e["source_type"], "id": e.get("id"),
                     "file": e.get("source_file")} for k, e in entities.items()],
    }

    out_dir = os.path.join(ROOT, "dashboards", "members", bio)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "data.json"), "w") as f:
        json.dump(payload, f, indent=1)
    with open(os.path.join(out_dir, "data.js"), "w") as f:
        f.write("window.MEMBER_DATA = "); json.dump(payload, f); f.write(";\n")
    return payload, out_dir


def main():
    args = sys.argv[1:]
    man = json.load(open(MANIFEST))
    members = man["members"]
    if not args:
        print("usage: build_member.py <BIOGUIDE> | --all"); sys.exit(1)
    if args[0] == "--all":
        targets = [m for m in members if m["bioguide_id"] != "S001193"]
    else:
        targets = [m for m in members if m["bioguide_id"] in set(args)]
        if not targets:
            print("no matching member in manifest"); sys.exit(1)

    for m in targets:
        recon = []
        def log(msg, _r=recon):
            print(msg); _r.append(msg)
        t0 = time.time()
        payload, out_dir = build_one(m, log)
        log(f"  wrote {out_dir}/data.js  ({os.path.getsize(os.path.join(out_dir,'data.js'))//1024} KB) "
            f"in {time.time()-t0:.0f}s")
        with open(os.path.join(out_dir, "reconciliation_report.md"), "w") as f:
            f.write(f"# {m['first_name']} {m['last_name']} ({m['bioguide_id']}) — build log\n\n```\n"
                    + "\n".join(recon) + "\n```\n")


if __name__ == "__main__":
    main()
