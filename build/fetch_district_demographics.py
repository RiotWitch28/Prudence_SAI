#!/usr/bin/env python3
"""
Fetch ACS 5-year 2023 demographic data for each active member's congressional district.
Writes dashboards/data/districts.json, keyed by "STATE-DISTRICT" (e.g. "OH-3").

Usage:
    python3 build/fetch_district_demographics.py

No API key required (Census allows unauthenticated requests at ~500/day).
Run from the repo root: Sovereign AI/
"""

import json
import os
import time
import urllib.request
import urllib.parse
from pathlib import Path

def load_env(env_file):
    """Load key=value pairs from a .env file into os.environ."""
    try:
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip())
    except FileNotFoundError:
        pass

load_env(Path(__file__).parent / ".env")

ROOT = Path(__file__).parent.parent
DASHBOARDS = ROOT / "dashboards"
MEMBERS_JSON = DASHBOARDS / "data" / "members.json"
STATES_JSON = DASHBOARDS / "data" / "states.json"
MEMBERS_DIR = DASHBOARDS / "members"
OUT_FILE = DASHBOARDS / "data" / "districts.json"

# ACS 5-year 2023 variables
VARS = [
    "B01003_001E",  # total population
    "B19013_001E",  # median household income
    "B01002_001E",  # median age
    # education (25+ population)
    "B15003_001E",  # total 25+
    "B15003_022E",  # bachelor's
    "B15003_023E",  # master's
    "B15003_024E",  # professional
    "B15003_025E",  # doctorate
    # poverty
    "B17001_001E",  # total for poverty calc
    "B17001_002E",  # below poverty
    # race
    "B02001_001E",  # total (race)
    "B02001_002E",  # white alone
    "B02001_003E",  # Black/AA
    "B02001_005E",  # Asian
    # hispanic (separate question)
    "B03003_001E",  # total (hispanic)
    "B03003_003E",  # hispanic/latino
    # employment
    "B23025_003E",  # civilian labor force
    "B23025_004E",  # employed
    "B23025_005E",  # unemployed
]

ACS_URL = "https://api.census.gov/data/2023/acs/acs5"

NULL_VALS = {-666666666, -999999999, -888888888, -222222222, -333333333, -444444444}


def safe_int(v):
    try:
        iv = int(v)
        return None if iv in NULL_VALS else iv
    except (TypeError, ValueError):
        return None


def pct(num, den):
    if num is None or den is None or den == 0:
        return None
    return round(num / den * 100, 1)


def fetch_district(state_fips, district_num):
    """Fetch ACS data for one congressional district. Returns raw dict or None."""
    dist_code = district_num.zfill(2)
    params_dict = {
        "get": ",".join(VARS),
        "for": f"congressional district:{dist_code}",
        "in": f"state:{state_fips}",
    }
    api_key = os.environ.get("CENSUS_API_KEY", "").strip()
    if api_key:
        params_dict["key"] = api_key
    params = urllib.parse.urlencode(params_dict)
    url = f"{ACS_URL}?{params}"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            data = json.loads(r.read())
        if len(data) < 2:
            return None
        headers = data[0]
        row = data[1]
        return dict(zip(headers, row))
    except Exception as e:
        print(f"  ERROR fetching state={state_fips} district={dist_code}: {e}")
        return None


def build_district_record(raw):
    """Compute derived stats from raw Census response."""
    pop = safe_int(raw.get("B01003_001E"))
    income = safe_int(raw.get("B19013_001E"))
    age = safe_int(raw.get("B01002_001E"))

    # education
    edu_total = safe_int(raw.get("B15003_001E"))
    bach = safe_int(raw.get("B15003_022E"))
    masters = safe_int(raw.get("B15003_023E"))
    prof = safe_int(raw.get("B15003_024E"))
    doc = safe_int(raw.get("B15003_025E"))
    bach_plus = None
    if all(v is not None for v in [bach, masters, prof, doc]):
        bach_plus = bach + masters + prof + doc
    edu_pct = pct(bach_plus, edu_total)

    # poverty
    pov_total = safe_int(raw.get("B17001_001E"))
    pov_below = safe_int(raw.get("B17001_002E"))
    pov_pct = pct(pov_below, pov_total)

    # race / ethnicity
    race_total = safe_int(raw.get("B02001_001E"))
    white = safe_int(raw.get("B02001_002E"))
    black = safe_int(raw.get("B02001_003E"))
    asian = safe_int(raw.get("B02001_005E"))
    hisp_total = safe_int(raw.get("B03003_001E"))
    hispanic = safe_int(raw.get("B03003_003E"))

    race = {}
    if race_total:
        if white is not None:
            race["white"] = pct(white, race_total)
        if black is not None:
            race["black"] = pct(black, race_total)
        if asian is not None:
            race["asian"] = pct(asian, race_total)
    if hisp_total and hispanic is not None:
        race["hispanic"] = pct(hispanic, hisp_total)

    # employment
    clf = safe_int(raw.get("B23025_003E"))
    employed = safe_int(raw.get("B23025_004E"))
    unemployed = safe_int(raw.get("B23025_005E"))
    unemp_pct = pct(unemployed, clf)

    return {
        "population": pop,
        "median_household_income": income,
        "median_age": age,
        "bachelors_plus_pct": edu_pct,
        "poverty_pct": pov_pct,
        "unemployment_pct": unemp_pct,
        "race_ethnicity": race,
        "source": "Census ACS 5-year 2023",
    }


def main():
    # Load members.json for state/district lookup
    with open(MEMBERS_JSON) as f:
        mdata = json.load(f)
    members_map = mdata.get("members", {})  # keyed by bioguide

    # Load states.json for FIPS lookup
    with open(STATES_JSON) as f:
        sdata = json.load(f)
    fips_by_abbr = {s["abbr"]: s["fips"] for s in sdata.get("states", [])}

    # Active members = subdirectories under dashboards/members/
    active_bios = [d.name for d in MEMBERS_DIR.iterdir() if d.is_dir()]
    print(f"Active members: {len(active_bios)}")

    results = {}
    for bio in sorted(active_bios):
        m = members_map.get(bio)
        if not m:
            print(f"  {bio}: not in members.json, skipping")
            continue

        state_abbr = m.get("state", "")
        district_raw = str(m.get("district", "")).strip()

        if not state_abbr or not district_raw:
            print(f"  {bio} ({m.get('full_name')}): missing state/district, skipping")
            continue

        fips = fips_by_abbr.get(state_abbr)
        if not fips:
            print(f"  {bio} ({m.get('full_name')}): no FIPS for {state_abbr}, skipping")
            continue

        # Normalize district: "At-Large" -> "00", integer -> string
        if district_raw.lower() in ("at-large", "at large", "0"):
            district_num = "00"
        else:
            try:
                district_num = str(int(district_raw))
            except ValueError:
                district_num = "00"

        key = f"{state_abbr}-{district_raw}"  # e.g. "OH-3", "AK-At-Large"
        if key in results:
            print(f"  {bio} ({m.get('full_name')}): {key} already fetched, reusing")
            continue

        print(f"  Fetching {key} (FIPS {fips}, district {district_num.zfill(2)})…")
        raw = fetch_district(fips, district_num)
        if raw:
            results[key] = build_district_record(raw)
            print(f"    pop={results[key]['population']:,} income=${results[key]['median_household_income']:,}" if results[key]['population'] and results[key]['median_household_income'] else f"    fetched (some fields null)")
        else:
            results[key] = None
            print(f"    fetch failed")

        time.sleep(0.3)  # gentle rate limiting

    out = {
        "generated_at": __import__("datetime").datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "vintage": "ACS 5-year 2023",
        "source_url": "https://api.census.gov/data/2023/acs/acs5",
        "districts": results,
    }

    with open(OUT_FILE, "w") as f:
        json.dump(out, f, indent=2)

    print(f"\nWrote {len(results)} districts → {OUT_FILE}")


if __name__ == "__main__":
    main()
