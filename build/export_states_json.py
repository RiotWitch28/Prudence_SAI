"""Extract state metadata from python-us into a single JSON for browser use.

Stubs `jellyfish` (only used at runtime for phonetic lookup; we just need static data).
"""
import json
import sys
import types
from pathlib import Path

# Stub jellyfish so we can import without installing it
jf = types.ModuleType("jellyfish")
jf.metaphone = lambda s: ""
sys.modules["jellyfish"] = jf

sys.path.insert(0, "/Users/amandakoski/Downloads/python-us-main")
from us import states as S  # noqa: E402

out = []
for st in S.STATES_AND_TERRITORIES + S.OBSOLETE:
    out.append({
        "fips": st.fips,
        "abbr": st.abbr,
        "name": st.name,
        "ap_abbr": st.ap_abbr,
        "capital": st.capital,
        "capital_tz": st.capital_tz,
        "time_zones": list(st.time_zones) if st.time_zones else [],
        "statehood_year": st.statehood_year,
        "is_territory": st.is_territory,
        "is_obsolete": st.is_obsolete,
        "is_contiguous": st.is_contiguous,
        "is_continental": st.is_continental,
        "is_commonwealth": st in S.COMMONWEALTHS,
        "shapefile_urls": st.shapefile_urls(),
    })

result = {
    "generated_from": "unitedstates/python-us v4.0.0.dev0",
    "shapefile_vintage": "Census TIGER 2010",
    "count": len(out),
    "states": out,
}

dest = Path("/Users/amandakoski/Documents/Claude/Suffrage and Sass/Sovereign AI/dashboards/data/states.json")
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_text(json.dumps(result, indent=2))
print(f"Wrote {len(out)} records → {dest} ({dest.stat().st_size:,} bytes)")
