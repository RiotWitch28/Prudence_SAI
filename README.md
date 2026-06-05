# Sovereign AI — Swalwell Political Finance Dashboard

## Folder Structure

### 📊 `dashboards/` — Active Dashboard App
The live Swalwell Financial Universe Dashboard. Deploy by dragging to netlify.com/drop.
- `swalwell_dashboard copy.html` — Main dashboard (all tabs: Overview, Entities, Flags, Timeline, Member Detail, Sources, Sovereign House AI)
- `swalwell_data.js` — Data payload (entities, transactions, flags)
- `swalwell_data.json` — Same data in JSON format
- `chart.umd.min.js` — Chart.js library

### 📁 `data/` — Processed Data
Cleaned/processed datasets ready for use in the dashboard or analysis.

### 📋 `_source-data/` — Raw Data Exports
Source files from FEC, Congressional APIs, and data services. These are the raw inputs.
- **FEC Files:**
  - `Swalwell for Congress FEC.csv` — Campaign committee filings
  - `SWALWELL-PRESIDENTIAL-RACE-2019 copy.csv` — 2019 presidential campaign data
  - `schedule_b-*.csv` — FEC Schedule B exports (vendor payments, dated)
  
- **Legislative Data:**
  - `119th_MASTER_LIST.xlsx` — Master list of all House members (FY2024)
  - `Swalwell Gov.xls` — Governor-era financial data (FPPC format)
  
- **Scripts & Auth:**
  - `download_sod_files copy.sh` — Script to fetch Statement of Disbursements from House Admin
  - `fec_secrets.txt.txt` — FEC API credentials

### 📚 `_research/` — Research & Reference Materials
Academic papers, policy research, and frameworks used to analyze power imbalance and abuse-enabling structures.
- `papers/` — Research papers (EEOC 2016, grooming models, CRS benchmarks, etc.)

### 🏛️ `_reference/` — Administrative & Reference Documents
House rules, policy guides, and analysis reports.
- `House Admin/` — Congressional handbooks, rules, HR policies, manuals
- `Swalwell Hotel Vendors 2.xlsx` — Reference analysis (hotel/vendor vendors)
- `Swalwell Legal Fees Report.docx` — Legal expenses analysis
- `swalwell vendor profile report.pdf` — Vendor analysis report

### 🗃️ `_archive/` — Old Code & External Libraries
Code prototypes, libraries, and earlier iterations (not actively used).
- `api.congress.gov-main/` — Congress API client library
- `build/` — Build artifacts
- `MRA 2/` — Earlier MRA data prototype

---

## Key Data Notes

| Entity Type | Format | Years | Source | Note |
|---|---|---|---|---|
| **House Office** | First Last | 2015–2025 | Statement of Disbursements (House Admin) | JSON in dashboard; 12–18 column format (pre/post-2023 differ by header) |
| **Campaign** | Last, First | 2015–2025 | FEC | Matches office spending patterns where applicable |
| **Leadership PAC** | Last, First | 2015–2025 | FEC | Separate committee; limited activity |
| **Presidential (2019)** | Last, First | 2018–2019 | FEC | No transaction dates in data (Governor data has no dates either) |
| **Governor (FPPC)** | First Last | Pre-2015 | California FPPC | No transaction dates; separate vendor naming |
| **Outside PAC** | Last, First | 2015–2025 | FEC (C00528174) | Independent expenditure committee; not controlled by Swalwell |

**Name format differences:** House Office uses "FIRST LAST"; FEC uses "LAST, FIRST" — dashboard normalizer handles this automatically.

---

## What's in the Dashboard?

### Tabs
1. **Overview** — Summary stats and entity breakdown
2. **Entities** — Detailed spending view; single & multi-select comparison
3. **Flags** — Severity-filtered anomalies with drill-down
4. **Timeline** — Chronological events with AI-generated summaries
5. **Member Detail** — Staff structure and power analysis (Sovereign House AI module)
6. **Sources** — Data attribution and FEC links

### Sovereign House AI Module
Analyzes office staffing structure against abuse-enabling risk factors (EEOC 2016, grooming models, CRS benchmarks). Includes cross-office benchmark (99th percentile for interns, 73 staff vs. median 33).

---

## How to Use This Folder

1. **To update the dashboard:** Edit files in `dashboards/` → deploy to Netlify
2. **To add new data:** Place raw exports in `_source-data/` → process to `data/` → refresh dashboard data file
3. **To reference rules/policies:** Check `_reference/House Admin/` for current guidance
4. **To cite research:** Check `_research/papers/` for frameworks used in analysis

---

*Last updated: Jun 2026*
