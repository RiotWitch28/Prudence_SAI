# Source Data — Raw Exports

Raw data files from FEC, House Administration, and other government sources. **Do not edit these files** — they are replaceable exports.

## FEC Campaign Finance Files
- **`Swalwell for Congress FEC.csv`** (10.7 MB)
  - Campaign committee filings for the "Swalwell for Congress" committee
  - Contains all vendor payments and transaction details
  - Format: FEC standard CSV

- **`SWALWELL-PRESIDENTIAL-RACE-2019 copy.csv`** (960 KB)
  - 2019 presidential campaign (exploratory committee)
  - Ended in March 2019; limited transaction data

- **`schedule_b-2026-06-*.csv`** (1 MB each, 2 versions)
  - Schedule B (vendor payments) extracts
  - Dated exports from FEC API
  - Use whichever is most recent

## Legislative Data
- **`119th_MASTER_LIST.xlsx`** (173 KB)
  - All House members in the 119th Congress (FY2024)
  - Used for benchmarking and staffing comparisons

- **`Swalwell Gov.xls`** (120 KB)
  - California Governor-era financial records (pre-Congress)
  - FPPC format; **has no transaction dates** (cannot be charted by year)

## Scripts & Authentication
- **`download_sod_files copy.sh`** 
  - Bash script to fetch Statement of Disbursements from House Administration
  - Automates data collection

- **`fec_secrets.txt.txt`**
  - FEC API credentials (keep secure)

---

## How to Use These Files

1. **To refresh campaign data:** Re-export Schedule B from FEC → replace the dated CSV file
2. **To update House member list:** Download new 119th MASTER LIST → refresh in `data/`
3. **To get new SOD data:** Run the `download_sod_files` script → process the output

**Note:** All processed/cleaned versions live in `../data/` — that's what the dashboard reads.
