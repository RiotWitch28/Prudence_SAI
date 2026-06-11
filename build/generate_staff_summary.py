"""generate_staff_summary.py — compute key-staff compensation & tenure averages.

Reads every member's data.js under dashboards/members/<bio>/data.js, identifies
the current holder of each of the four key roles (Chief of Staff, Legislative
Director, Communications Director, Scheduler), computes:

  - avg annual salary  = (office total + overlapping campaign payments)
                         ÷ years with SOD data (2013+)
  - avg tenure         = years with SOD data (2013+) for that person

Averages are split by party (D / R). Output is written to:
  dashboards/staff_summary.js   — loaded by home.html at runtime

Run after adding a new member:
  python3 build/generate_staff_summary.py
"""

import json, re, os
from pathlib import Path
from collections import defaultdict

ROOT     = Path(__file__).resolve().parent.parent
MEMBERS_DIR = ROOT / "dashboards" / "members"
OUT      = ROOT / "dashboards" / "staff_summary.js"

# ── role patterns ────────────────────────────────────────────────────────────
ROLES = {
    "cos":   re.compile(r"CHIEF OF STAFF",            re.I),
    "ld":    re.compile(r"LEGISLATIVE DIRECTOR",      re.I),
    "cd":    re.compile(r"COMMUNICATIONS DIRECTOR",   re.I),
    "sched": re.compile(r"SCHEDULER",                 re.I),
}

# ── name normalisation (matches dashboard logic) ──────────────────────────────
def norm_name(raw: str) -> str:
    cleaned = re.sub(r"[.,]", " ", raw.upper())
    tokens  = [t for t in cleaned.split() if len(t) > 1]
    return " ".join(sorted(tokens))

# ── campaign amount restricted to years the person was in the office ──────────
def camp_amt_for_years(camp_person: dict, active_years: set) -> float:
    total = 0.0
    for txn in camp_person.get("txns", []):
        date = txn.get("date", "")
        try:
            yr = int(date[:4])
        except (ValueError, TypeError):
            continue
        if yr in active_years:
            total += txn.get("amount", 0)
    return total

# ── accumulate per-party lists ────────────────────────────────────────────────
comp_lists   = {"D": defaultdict(list), "R": defaultdict(list)}
tenure_lists = {"D": defaultdict(list), "R": defaultdict(list)}

for bio_dir in sorted(MEMBERS_DIR.iterdir()):
    data_js = bio_dir / "data.js"
    if not data_js.exists():
        continue

    raw = data_js.read_text(encoding="utf-8")
    # strip the JS wrapper: window.MEMBER_DATA = {...};
    json_str = re.sub(r"^\s*window\.MEMBER_DATA\s*=\s*", "", raw).rstrip().rstrip(";")
    try:
        D = json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"  SKIP {bio_dir.name}: JSON error — {e}")
        continue

    party = D.get("member", {}).get("party", "")
    if party not in ("Democrat", "Republican"):
        continue
    party_key = "D" if party == "Democrat" else "R"

    office_indivs = D.get("entities", {}).get("office", {}).get("top_individuals") or []
    camp_indivs   = D.get("entities", {}).get("house",  {}).get("top_individuals") or []

    # index campaign individuals by normalised name
    camp_by_norm = {norm_name(p["name"]): p for p in camp_indivs}

    found = set()
    for person in office_indivs:
        purposes = [t.get("purpose", "") for t in person.get("txns", [])]
        for role, rx in ROLES.items():
            if role in found:
                continue
            if any(rx.search(p) for p in purposes):
                by_year     = person.get("by_year") or {}
                active_years = {int(y) for y in by_year if int(y) >= 2013}
                if not active_years:
                    break
                office_total = sum(by_year.get(str(y), 0) for y in active_years)
                camp_match   = camp_by_norm.get(norm_name(person["name"]))
                camp_overlap = camp_amt_for_years(camp_match, active_years) if camp_match else 0.0
                avg_comp     = round((office_total + camp_overlap) / len(active_years))
                tenure       = len(active_years)
                comp_lists[party_key][role].append(avg_comp)
                tenure_lists[party_key][role].append(tenure)
                found.add(role)
                break

# ── compute averages ──────────────────────────────────────────────────────────
def avg(vals):
    return round(sum(vals) / len(vals)) if vals else None

def avg_f(vals, dp=1):
    return round(sum(vals) / len(vals), dp) if vals else None

role_order = ["cos", "ld", "cd", "sched"]

staff_comp   = {}
staff_tenure = {}

for role in role_order:
    staff_comp[role]   = {}
    staff_tenure[role] = {}
    for p in ("D", "R"):
        c = comp_lists[p][role]
        t = tenure_lists[p][role]
        staff_comp[role][p]   = {"avg": avg(c),   "n": len(c)} if c else None
        staff_tenure[role][p] = {"avg": avg_f(t), "n": len(t)} if t else None

# ── write output ──────────────────────────────────────────────────────────────
role_labels_js = {
    "cos": "Chief of Staff",
    "ld": "Legislative Director",
    "cd": "Communications Director",
    "sched": "Scheduler",
}

lines = [
    "/* AUTO-GENERATED by build/generate_staff_summary.py — do not edit by hand */",
    "/* Run: python3 build/generate_staff_summary.py  after adding a new member */",
    "",
    f"window.STAFF_COMP = {json.dumps(staff_comp, indent=2)};",
    "",
    f"window.STAFF_TENURE = {json.dumps(staff_tenure, indent=2)};",
    "",
    f"window.ROLE_LABELS = {json.dumps(role_labels_js)};",
    "",
]
OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"Written → {OUT}")

# ── summary print ─────────────────────────────────────────────────────────────
role_labels = {"cos": "Chief of Staff", "ld": "Legislative Director",
               "cd": "Communications Director", "sched": "Scheduler"}
print()
for role in role_order:
    d = staff_comp[role].get("D")
    r = staff_comp[role].get("R")
    td = staff_tenure[role].get("D")
    tr = staff_tenure[role].get("R")
    print(f"{role_labels[role]}")
    print(f"  Comp   D: ${d['avg']:,} (n={d['n']})  R: ${r['avg']:,} (n={r['n']})" if d and r else "  Comp   (missing data)")
    print(f"  Tenure D: {td['avg']}yr (n={td['n']})  R: {tr['avg']}yr (n={tr['n']})" if td and tr else "  Tenure (missing data)")
