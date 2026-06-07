#!/usr/bin/env python3
"""
add_disclosure.py — fetch + parse each member's House Financial Disclosure PDF
(from the master-list "Most Recent House Financial Disclosure" link) and inject a
`disclosure` block into their existing data/members/<bio>/data.{json,js}.

Fast pass: does NOT re-pull FEC/SOD. Run after build_member.py.
  build/.venv/bin/python build/add_disclosure.py <BIOGUIDE|--all>
"""
import json, os, sys, io, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fd_parser import parse as parse_fd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEM = os.path.join(ROOT, "dashboards", "members")
MANIFEST = os.path.join(ROOT, "data", "members", "sample_members_10.json")


def midpoint(rng):
    """Approx midpoint of a '$a - $b' range string (for rough net-worth bands)."""
    if not rng:
        return 0
    nums = [int(x.replace(",", "")) for x in __import__("re").findall(r"[\d,]+", rng)]
    if not nums:
        return 0
    return sum(nums) / len(nums)


def summarize(fd):
    a_lo = a_hi = l_lo = l_hi = 0
    import re
    def bounds(rng):
        n = [int(x.replace(",", "")) for x in re.findall(r"[\d,]+", rng or "")]
        return (n[0], n[-1]) if n else (0, 0)
    for r in fd["schedule_a"]:
        lo, hi = bounds(r.get("value")); a_lo += lo; a_hi += hi
    for r in fd["schedule_d"]:
        lo, hi = bounds(r.get("amount")); l_lo += lo; l_hi += hi
    return {"asset_low": a_lo, "asset_high": a_hi,
            "liability_low": l_lo, "liability_high": l_hi,
            "net_low": a_lo - l_hi, "net_high": a_hi - l_lo}


def run(bio, member):
    d = os.path.join(MEM, bio)
    dj = os.path.join(d, "data.json")
    if not os.path.exists(dj):
        print(f"  {bio}: no data.json — run build_member first"); return False
    url = (member.get("disclosures") or {}).get("most_recent")
    if not url:
        print(f"  {bio}: no FD link in manifest — skipped"); return False
    try:
        fd = parse_fd(url)
    except Exception as e:
        print(f"  {bio}: FD parse failed ({e})"); return False
    fd["summary"] = summarize(fd)
    # cache the source PDF for provenance
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        open(os.path.join(d, "fd_source.pdf"), "wb").write(
            urllib.request.urlopen(req, timeout=60).read())
    except Exception:
        pass
    payload = json.load(open(dj))
    payload["disclosure"] = fd
    json.dump(payload, open(dj, "w"), indent=1)
    with open(os.path.join(d, "data.js"), "w") as f:
        f.write("window.MEMBER_DATA = "); json.dump(payload, f); f.write(";\n")
    c = fd["counts"]; s = fd["summary"]
    print(f"  {bio} {member['last_name']:<16} assets={c['schedule_a']:>2} txns={c['schedule_b']:>2} "
          f"liab={c['schedule_d']} | net ~${s['net_low']:,.0f}..${s['net_high']:,.0f}")
    return True


def main():
    args = sys.argv[1:]
    man = json.load(open(MANIFEST))["members"]
    targets = ([m for m in man if m["bioguide_id"] != "S001193"] if args and args[0] == "--all"
               else [m for m in man if m["bioguide_id"] in set(args)])
    ok = 0
    for m in targets:
        if run(m["bioguide_id"], m):
            ok += 1
    print(f"done: {ok}/{len(targets)} members got disclosure data")


if __name__ == "__main__":
    main()
