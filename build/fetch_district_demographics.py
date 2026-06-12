#!/usr/bin/env python3
"""
Fetch ACS 5-year 2023 demographic data for each active member's congressional
district AND the state + national context for those same metrics, plus the
GeoJSON boundary polygons from Census TIGERweb.

Writes dashboards/data/districts.json with this shape:
  {
    "generated_at": ..., "vintage": "ACS 5-year 2023",
    "national": {... metrics ...},
    "states":   {"06": {abbr, name, ...metrics, boundary}, ...},
    "districts":{"CA-30": {...metrics, state_fips, boundary, ...}, ...}
  }

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

ACS_URL = "https://api.census.gov/data/2023/acs/acs5"
TIGER_CD_URL = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Legislative/MapServer/0/query"
)
TIGER_STATE_URL = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/0/query"
)

# Headline + composition vars (Batch A — fits in one ACS call along with edu/housing/at-home)
VARS_BATCH_A = [
    # headline
    "B01003_001E",  # total population
    "B19013_001E",  # median household income
    "B01002_001E",  # median age
    # education ladder (B15003: 25+ pop)
    "B15003_001E",
    "B15003_017E",  # regular HS diploma
    "B15003_018E",  # GED
    "B15003_019E",  # some college <1y
    "B15003_020E",  # some college 1+y
    "B15003_021E",  # associate's
    "B15003_022E",  # bachelor's
    "B15003_023E",  # master's
    "B15003_024E",  # professional
    "B15003_025E",  # doctorate
    # poverty
    "B17001_001E",
    "B17001_002E",
    # race
    "B02001_001E",
    "B02001_002E",
    "B02001_003E",
    "B02001_005E",
    # hispanic
    "B03003_001E",
    "B03003_003E",
    # employment
    "B23025_003E",
    "B23025_004E",
    "B23025_005E",
    # housing
    "B25003_001E",  # total occupied units
    "B25003_002E",  # owner-occupied
    "B25003_003E",  # renter-occupied
    "B25077_001E",  # median home value
    "B25064_001E",  # median gross rent
    # at-home
    "B05002_001E",  # place-of-birth denominator
    "B05002_013E",  # foreign-born
    "B06007_001E",  # language at home denominator (5+)
    "B06007_002E",  # speak only English at home
    "B21001_001E",  # veteran-status denominator (18+)
    "B21001_002E",  # veterans
    "B28002_001E",  # internet denominator
    "B28002_002E",  # with internet subscription
]

# Age pyramid — B01001 sex by age. 23 age buckets per sex.
AGE_BUCKETS = [
    ("Under 5", "003", "027"),
    ("5–9", "004", "028"),
    ("10–14", "005", "029"),
    ("15–17", "006", "030"),
    ("18–19", "007", "031"),
    ("20", "008", "032"),
    ("21", "009", "033"),
    ("22–24", "010", "034"),
    ("25–29", "011", "035"),
    ("30–34", "012", "036"),
    ("35–39", "013", "037"),
    ("40–44", "014", "038"),
    ("45–49", "015", "039"),
    ("50–54", "016", "040"),
    ("55–59", "017", "041"),
    ("60–61", "018", "042"),
    ("62–64", "019", "043"),
    ("65–66", "020", "044"),
    ("67–69", "021", "045"),
    ("70–74", "022", "046"),
    ("75–79", "023", "047"),
    ("80–84", "024", "048"),
    ("85+", "025", "049"),
]
VARS_BATCH_B = ["B01001_001E"] + [
    f"B01001_{m}E" for _, m, _ in AGE_BUCKETS
] + [f"B01001_{f}E" for _, _, f in AGE_BUCKETS]

# Collapse the 23 ACS buckets into clean 10-year display groups
DISPLAY_GROUPS = [
    ("0–9",   ["Under 5", "5–9"]),
    ("10–19", ["10–14", "15–17", "18–19"]),
    ("20–29", ["20", "21", "22–24", "25–29"]),
    ("30–39", ["30–34", "35–39"]),
    ("40–49", ["40–44", "45–49"]),
    ("50–59", ["50–54", "55–59"]),
    ("60–69", ["60–61", "62–64", "65–66", "67–69"]),
    ("70–79", ["70–74", "75–79"]),
    ("80+",   ["80–84", "85+"]),
]

NULL_VALS = {-666666666, -999999999, -888888888, -222222222, -333333333, -444444444}


def safe_int(v):
    try:
        iv = int(v)
        return None if iv in NULL_VALS else iv
    except (TypeError, ValueError):
        # Some ACS vars are decimal strings (e.g. medians like "38.7"). Round to int.
        try:
            fv = float(v)
            iv = round(fv)
            return None if iv in NULL_VALS else iv
        except (TypeError, ValueError):
            return None


def safe_float(v, digits=1):
    try:
        fv = float(v)
        if int(fv) in NULL_VALS:
            return None
        return round(fv, digits)
    except (TypeError, ValueError):
        return None


def pct(num, den, digits=1):
    if num is None or den is None or den == 0:
        return None
    return round(num / den * 100, digits)


def fetch_acs(vars_, geo_for, geo_in=None):
    """Call ACS with a vars list + 'for' (+ optional 'in'). Returns headers→values dict or None."""
    params_dict = {"get": ",".join(vars_), "for": geo_for}
    if geo_in:
        params_dict["in"] = geo_in
    key = os.environ.get("CENSUS_API_KEY", "").strip()
    if key:
        params_dict["key"] = key
    url = f"{ACS_URL}?{urllib.parse.urlencode(params_dict)}"
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            data = json.loads(r.read())
        if len(data) < 2:
            return None
        return dict(zip(data[0], data[1]))
    except Exception as e:
        print(f"    ACS error ({geo_for}): {e}")
        return None


def derive_metrics(raw):
    """Compute the common metrics dict from a raw ACS response (Batch A vars)."""
    pop = safe_int(raw.get("B01003_001E"))
    income = safe_int(raw.get("B19013_001E"))
    age = safe_float(raw.get("B01002_001E"))

    # education ladder
    edu_total = safe_int(raw.get("B15003_001E"))
    hs   = sum(filter(None, [safe_int(raw.get(v)) for v in ["B15003_017E", "B15003_018E"]])) or None
    sc   = sum(filter(None, [safe_int(raw.get(v)) for v in ["B15003_019E", "B15003_020E", "B15003_021E"]])) or None
    ba   = safe_int(raw.get("B15003_022E"))
    grad = sum(filter(None, [safe_int(raw.get(v)) for v in ["B15003_023E", "B15003_024E", "B15003_025E"]])) or None
    accounted = sum(x for x in [hs, sc, ba, grad] if x)
    less_hs = edu_total - accounted if edu_total is not None else None
    bach_plus = (ba or 0) + (grad or 0) if (ba is not None or grad is not None) else None
    edu_ladder = {
        "less_than_hs_pct": pct(less_hs, edu_total),
        "hs_pct":           pct(hs,      edu_total),
        "some_college_pct": pct(sc,      edu_total),
        "bachelors_pct":    pct(ba,      edu_total),
        "graduate_pct":     pct(grad,    edu_total),
    }
    bach_plus_pct = pct(bach_plus, edu_total)

    # poverty
    pov_pct = pct(safe_int(raw.get("B17001_002E")), safe_int(raw.get("B17001_001E")))

    # race / ethnicity
    race_total = safe_int(raw.get("B02001_001E"))
    race = {}
    if race_total:
        for label, var in [("white", "B02001_002E"), ("black", "B02001_003E"), ("asian", "B02001_005E")]:
            v = safe_int(raw.get(var))
            if v is not None:
                race[label] = pct(v, race_total)
    h_total = safe_int(raw.get("B03003_001E"))
    h_val = safe_int(raw.get("B03003_003E"))
    if h_total and h_val is not None:
        race["hispanic"] = pct(h_val, h_total)

    # employment
    clf = safe_int(raw.get("B23025_003E"))
    unemp = safe_int(raw.get("B23025_005E"))
    unemp_pct = pct(unemp, clf)

    # housing
    h_total_units = safe_int(raw.get("B25003_001E"))
    owner = safe_int(raw.get("B25003_002E"))
    renter = safe_int(raw.get("B25003_003E"))
    housing = {
        "owner_pct":         pct(owner,  h_total_units),
        "renter_pct":        pct(renter, h_total_units),
        "median_home_value": safe_int(raw.get("B25077_001E")),
        "median_rent":       safe_int(raw.get("B25064_001E")),
    }

    # at-home
    pob_total = safe_int(raw.get("B05002_001E"))
    foreign = safe_int(raw.get("B05002_013E"))
    lang_total = safe_int(raw.get("B06007_001E"))
    eng_only = safe_int(raw.get("B06007_002E"))
    non_eng = lang_total - eng_only if (lang_total is not None and eng_only is not None) else None
    vet_total = safe_int(raw.get("B21001_001E"))
    vets = safe_int(raw.get("B21001_002E"))
    net_total = safe_int(raw.get("B28002_001E"))
    net_with = safe_int(raw.get("B28002_002E"))
    at_home = {
        "foreign_born_pct": pct(foreign, pob_total),
        "non_english_pct":  pct(non_eng, lang_total),
        "veterans_pct":     pct(vets,    vet_total),
        "broadband_pct":    pct(net_with, net_total),
    }

    return {
        "population": pop,
        "median_household_income": income,
        "median_age": age,
        "bachelors_plus_pct": bach_plus_pct,
        "poverty_pct": pov_pct,
        "unemployment_pct": unemp_pct,
        "race_ethnicity": race,
        "education": edu_ladder,
        "housing": housing,
        "at_home": at_home,
    }


def derive_age_pyramid(raw_b):
    """Take Batch B raw response → grouped male/female %s of total population."""
    if not raw_b:
        return None
    total = safe_int(raw_b.get("B01001_001E"))
    if not total:
        return None
    fine_male = {}
    fine_female = {}
    for label, m, f in AGE_BUCKETS:
        fine_male[label] = safe_int(raw_b.get(f"B01001_{m}E"))
        fine_female[label] = safe_int(raw_b.get(f"B01001_{f}E"))
    out_labels, out_male, out_female = [], [], []
    for grp_label, members in DISPLAY_GROUPS:
        m_sum = sum(v for v in (fine_male.get(x) for x in members) if v is not None)
        f_sum = sum(v for v in (fine_female.get(x) for x in members) if v is not None)
        out_labels.append(grp_label)
        out_male.append(round(m_sum / total * 100, 2))
        out_female.append(round(f_sum / total * 100, 2))
    return {"buckets": out_labels, "male": out_male, "female": out_female}


def fetch_geojson(url, where, max_offset=0.005):
    params = {
        "where": where,
        "outFields": "STATE,BASENAME,NAME",
        "returnGeometry": "true",
        "geometryPrecision": "3",
        "maxAllowableOffset": str(max_offset),
        "f": "geojson",
    }
    full = f"{url}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(full, timeout=25) as r:
            d = json.loads(r.read())
        feats = d.get("features") or []
        if not feats:
            return None
        return feats[0].get("geometry")
    except Exception as e:
        print(f"    GeoJSON error ({where}): {e}")
        return None


def fetch_district(state_fips, district_num):
    dist_code = district_num.zfill(2)
    print(f"    ACS batch A…")
    a = fetch_acs(VARS_BATCH_A, f"congressional district:{dist_code}", f"state:{state_fips}")
    print(f"    ACS batch B (age pyramid)…")
    b = fetch_acs(VARS_BATCH_B, f"congressional district:{dist_code}", f"state:{state_fips}")
    print(f"    geometry…")
    geom = fetch_geojson(TIGER_CD_URL, f"STATE='{state_fips}' AND BASENAME='{int(dist_code)}'")
    if not a:
        return None
    rec = derive_metrics(a)
    rec["age_pyramid"] = derive_age_pyramid(b)
    rec["boundary"] = geom
    rec["state_fips"] = state_fips
    rec["source"] = "Census ACS 5-year 2023"
    return rec


def fetch_state(state_fips):
    print(f"    ACS state batch A…")
    a = fetch_acs(VARS_BATCH_A, f"state:{state_fips}")
    print(f"    ACS state batch B (age pyramid)…")
    b = fetch_acs(VARS_BATCH_B, f"state:{state_fips}")
    print(f"    state geometry…")
    geom = fetch_geojson(TIGER_STATE_URL, f"STATE='{state_fips}'", max_offset=0.02)
    if not a:
        return None
    rec = derive_metrics(a)
    rec["age_pyramid"] = derive_age_pyramid(b)
    rec["boundary"] = geom
    rec["source"] = "Census ACS 5-year 2023"
    return rec


def fetch_national():
    print(f"    ACS national batch A…")
    a = fetch_acs(VARS_BATCH_A, "us:1")
    print(f"    ACS national batch B (age pyramid)…")
    b = fetch_acs(VARS_BATCH_B, "us:1")
    if not a:
        return None
    rec = derive_metrics(a)
    rec["age_pyramid"] = derive_age_pyramid(b)
    rec["source"] = "Census ACS 5-year 2023"
    return rec


def main():
    with open(MEMBERS_JSON) as f:
        members_map = (json.load(f).get("members") or {})
    with open(STATES_JSON) as f:
        sdata = json.load(f)
    state_by_abbr = {s["abbr"]: s for s in sdata.get("states", [])}
    fips_by_abbr = {s["abbr"]: s["fips"] for s in sdata.get("states", []) if s.get("fips")}

    active_bios = sorted(d.name for d in MEMBERS_DIR.iterdir() if d.is_dir())
    print(f"Active members: {len(active_bios)}")

    districts = {}
    seen_states = set()

    for bio in active_bios:
        m = members_map.get(bio)
        if not m:
            print(f"  {bio}: not in members.json, skipping")
            continue
        st = (m.get("state") or "").upper()
        dist_raw = str(m.get("district", "")).strip()
        if not st or not dist_raw:
            print(f"  {bio}: missing state/district, skipping")
            continue
        fips = fips_by_abbr.get(st)
        if not fips:
            print(f"  {bio}: no FIPS for {st}, skipping")
            continue
        if dist_raw.lower() in ("at-large", "at large", "0"):
            dnum = "00"
        else:
            try:
                dnum = str(int(dist_raw))
            except ValueError:
                dnum = "00"
        key = f"{st}-{dist_raw}"
        if key in districts:
            print(f"  {bio}: {key} already fetched, reusing")
            continue
        print(f"  Fetching {key} (FIPS {fips}, district {dnum.zfill(2)})…")
        rec = fetch_district(fips, dnum)
        if rec:
            districts[key] = rec
            print(f"    ✓ pop={rec.get('population'):,}" if rec.get('population') else "    ✓ fetched")
        else:
            districts[key] = None
            print(f"    fetch failed")
        seen_states.add(st)
        time.sleep(0.3)

    print(f"\nFetching state-level context for {len(seen_states)} states…")
    states = {}
    for st in sorted(seen_states):
        fips = fips_by_abbr.get(st)
        info = state_by_abbr.get(st, {})
        if not fips:
            continue
        print(f"  {st} (FIPS {fips})…")
        rec = fetch_state(fips)
        if rec:
            rec["abbr"] = st
            rec["name"] = info.get("name", st)
            states[fips] = rec
        time.sleep(0.3)

    print(f"\nFetching national context…")
    national = fetch_national()

    out = {
        "generated_at": __import__("datetime").datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "vintage": "ACS 5-year 2023",
        "source_url": "https://api.census.gov/data/2023/acs/acs5",
        "geometry_source": "Census TIGERweb (Legislative — 119th CDs)",
        "national": national,
        "states": states,
        "districts": districts,
    }
    with open(OUT_FILE, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nWrote {len(districts)} districts + {len(states)} states + national → {OUT_FILE}")


if __name__ == "__main__":
    main()
