#!/bin/bash
# Downloads SOD Detail Transaction CSVs (Q1 2016 – Q4 2024)
# Run from Terminal: bash download_sod_files.sh

DEST="$(dirname "$0")"
echo "Saving files to: $DEST"
echo ""

download() {
  local filename="$1"
  local url="$2"
  local dest="$DEST/$filename"

  if [ -f "$dest" ] && [ -s "$dest" ]; then
    echo "SKIP (exists): $filename"
    return
  fi

  printf "Downloading: %-40s " "$filename"
  http_code=$(curl -s -L -A "Mozilla/5.0" -o "$dest" -w "%{http_code}" "$url")
  if [ "$http_code" = "200" ] && [ -s "$dest" ]; then
    size=$(du -sh "$dest" | cut -f1)
    echo "✓ ($size)"
  else
    echo "✗ FAILED ($http_code)"
    rm -f "$dest"
  fi
}

# 2016
download "JAN-MAR-2016-DETAIL.csv"   "https://www.house.gov/sites/default/files/uploads/documents/JAN-MAR-2016-SOD-DETAIL-GRID_REVISED_9_26_16.csv"
download "APR-JUN-2016-DETAIL.csv"   "https://www.house.gov/sites/default/files/uploads/documents/APR-JUNE-2016-SOD-DETAIL-GRID-REVISE-9_26_16.csv"
download "JUL-SEP-2016-DETAIL.csv"   "https://www.house.gov/sites/default/files/uploads/documents/JULY-SEPT-2016-SOD-DETAIL-GRID.csv"
download "OCT-DEC-2016-DETAIL.csv"   "https://www.house.gov/sites/default/files/uploads/documents/OCT-DEC%202016%20DETAIL%20GRID.csv"

# 2017
download "JAN-MAR-2017-DETAIL.csv"   "https://www.house.gov/sites/default/files/uploads/documents/SODs/JAN-MAR%202017%20DETAIL%20GRID.csv"
download "APR-JUN-2017-DETAIL.csv"   "https://www.house.gov/sites/default/files/uploads/documents/APR-JUN%202017%20DETAIL%20GRID.csv"
download "JUL-SEP-2017-DETAIL.csv"   "https://www.house.gov/sites/default/files/uploads/documents/SODs/JUL-SEPT%202017%20SOD%20DETAIL%20GRID.csv"
download "OCT-DEC-2017-DETAIL.csv"   "https://www.house.gov/sites/default/files/uploads/documents/SODs/OCT-DEC%202017%20SOD%20DETAIL%20GRID.csv"

# 2018
download "JAN-MAR-2018-DETAIL.csv"   "https://www.house.gov/sites/default/files/uploads/documents/JAN-MAR%202018%20SOD%20DETAIL%20GRID.csv"
download "APR-JUN-2018-DETAIL.csv"   "https://www.house.gov/sites/default/files/uploads/documents/SODs/APR-JUNE-2018-SOD-DETAIL-GRID.csv"
download "JUL-SEP-2018-DETAIL.csv"   "https://www.house.gov/sites/default/files/uploads/documents/SODs/JULY-SEPTEMBER%202018%20SOD%20DETAIL%20GRID.csv"
download "OCT-DEC-2018-DETAIL.csv"   "https://www.house.gov/sites/default/files/uploads/documents/SODs/OCT-DEC%202018%20SOD%20DETAIL%20GRID.csv"

# 2019
download "JAN-MAR-2019-DETAIL.csv"   "https://www.house.gov/sites/default/files/uploads/documents/SODs/JAN-MAR%202019%20SOD%20DETAIL%20GRID.CSV"
download "APR-JUN-2019-DETAIL.csv"   "https://www.house.gov/sites/default/files/uploads/documents/SODs/APR-JUN%202019%20SOD%20DETAIL%20GRID.csv"
download "JUL-SEP-2019-DETAIL.csv"   "https://www.house.gov/sites/default/files/uploads/documents/SODs/JUL-SEPT%202019%20SOD%20DETAIL%20GRID.csv"
download "OCT-DEC-2019-DETAIL.csv"   "https://www.house.gov/sites/default/files/uploads/documents/SODs/OCT-DEC-2019-SOD-DETAIL-GRID.csv"

# 2020
download "JAN-MAR-2020-DETAIL.csv"   "https://www.house.gov/sites/default/files/uploads/documents/SODs/JAN-MAR-2020-SOD-DETAIL-GRID_FINAL.csv"
download "APR-JUN-2020-DETAIL.csv"   "https://www.house.gov/sites/default/files/uploads/documents/SODs/APR-JUN-2020-SOD-DETAIL-GRID_FINAL.csv"
download "JUL-SEP-2020-DETAIL.csv"   "https://www.house.gov/sites/default/files/uploads/documents/SODs/2020q3/JULY-SEPT-2020-SOD-DETAIL-GRID-FINAL.csv"
download "OCT-DEC-2020-DETAIL.csv"   "https://www.house.gov/sites/default/files/uploads/documents/SODs/2020q4/OCT-DEC%202020%20SOD%20DETAIL%20GRID_FINAL.csv"

# 2021
download "JAN-MAR-2021-DETAIL.csv"   "https://www.house.gov/sites/default/files/uploads/documents/SODs/2021q1/JAN_MAR_2021_SOD_DETAIL_GRID_FINAL.csv"
download "APR-JUN-2021-DETAIL.csv"   "https://www.house.gov/sites/default/files/uploads/documents/SODs/2021q2/APR-JUN%202021%20SOD%20DETAIL%20GRID_FINAL.csv"
download "JUL-SEP-2021-DETAIL.csv"   "https://www.house.gov/sites/default/files/uploads/documents/SODs/2021q3/JULY-2021-SOD-DETAIL-GRID-FINAL.csv"
download "OCT-DEC-2021-DETAIL.csv"   "https://www.house.gov/sites/default/files/uploads/documents/SODs/2021q4/OCT-DEC-2021-SOD-DETAIL-GRID-FINAL.csv"

# 2022
download "JAN-MAR-2022-DETAIL.csv"   "https://www.house.gov/sites/default/files/2022-05/JAN-MAR-2022-SOD-DETAIL-GRID-FINAL.csv"
download "APR-JUN-2022-DETAIL.csv"   "https://www.house.gov/sites/default/files/2022-08/APR-JUNE-2022-SOD-DETAIL-GRID-FINAL.csv"
download "JUL-SEP-2022-DETAIL.csv"   "https://www.house.gov/sites/default/files/2022-11/JULY-SEPT-2022-SOD-DETAIL-GRID-FINAL.csv"
download "OCT-DEC-2022-DETAIL.csv"   "https://www.house.gov/sites/default/files/2023-02/OCT-DEC-2022-SOD-DETAIL-GRID-FINAL.csv"

# 2023
download "JAN-MAR-2023-DETAIL.csv"   "https://www.house.gov/sites/default/files/2023-05/JAN-MAR-2023-SOD-DETAIL-GRID-FINAL.csv"
download "APR-JUN-2023-DETAIL.csv"   "https://www.house.gov/sites/default/files/2023-08/APRIL-JUNE%202023%20SOD%20DETAIL%20GRID-FINAL.csv"
download "JUL-SEP-2023-DETAIL.csv"   "https://www.house.gov/sites/default/files/2023-11/JULY-SEPTEMBER-2023-SOD-DETAIL-GRID-FINAL.csv"
download "OCT-DEC-2023-DETAIL.csv"   "https://www.house.gov/sites/default/files/2024-02/OCT-DEC-2023-SOD-DETAIL-GRID-FINAL.csv"

# 2024
download "JAN-MAR-2024-DETAIL.csv"   "https://www.house.gov/sites/default/files/2024-05/JAN-MAR-2024-SOD-DETAIL-GRID-FINAL.csv"
download "APR-JUN-2024-DETAIL.csv"   "https://www.house.gov/sites/default/files/2024-08/APRIL-JUNE-2024-SOD-DETAIL-GRID-FINAL.csv"
download "JUL-SEP-2024-DETAIL.csv"   "https://www.house.gov/sites/default/files/2024-11/JULY-SEPTEMBER_2024_SOD_DETAIL_GRID-FINAL.csv"
download "OCT-DEC-2024-DETAIL.csv"   "https://www.house.gov/sites/default/files/2025-02/OCTOBER-DECEMBER-2024-SOD-DETAIL-GRID-FINAL.csv"

echo ""
echo "All done. Files saved to: $DEST"
