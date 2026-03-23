"""
5_convert_to_json.py

Converts CSVs for each paint line to the JSON format required by the Vue website.

- Paint line configuration is read from src/data/paint-lines.json
- CSV source files are determined by tools/pdf-import/sources-csv.json:
    - If "skip": true, skip this paint line
    - If "merged" is set, use that CSV from output/merged/
    - If not, and only one file in "files", use that from input/
- Output JSON is written to src/data/<paint-line>.json (where <paint-line> is the paint line key)

Usage: python 5_convert_to_json.py
"""
import json
import csv
import os
from pathlib import Path

# Paths
ROOT = Path(__file__).parent.parent.parent.parent
SRC = ROOT / "src"
DATA = SRC / "data"
TOOLS = ROOT / "tools" / "pdf-import"
INPUT = TOOLS / "input"
OUTPUT = TOOLS / "output"
MERGED = OUTPUT / "merged"

PAINT_LINES_JSON = DATA / "paint-lines.json"
SOURCES_CSV_JSON = TOOLS / "sources-csv.json"

# Load paint line config
with open(PAINT_LINES_JSON, encoding="utf-8") as f:
    paint_lines = json.load(f)

# Load sources config
with open(SOURCES_CSV_JSON, encoding="utf-8") as f:
    sources = json.load(f)

# Build a lookup for paint line config by id
paint_line_by_id = {pl["id"]: pl for pl in paint_lines}

# Helper: get CSV path for a paint line entry
def get_csv_path(entry):
    if entry.get("skip"):
        return None
    if "merged" in entry:
        return MERGED / entry["merged"]
    files = entry.get("files", [])
    if len(files) == 1:
        return INPUT / files[0]["name"]
    return None


# Helper: normalize/pad id
def normalize_id(val, min_digits=0):
    if val is None:
        return ""
    val = str(val).strip()
    # Remove any non-digit prefix/suffix
    val = val.lstrip("0") if val.lstrip("0") else val
    if min_digits > 0:
        val = val.zfill(min_digits)
    return val

# Helper: parse a CSV file into color dicts for the new format
def parse_csv(csv_path, paint_line_key, config, paint_line_by_id):
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=';')
        rows = list(reader)
    min_digits = config.get("min_digits", 0)
    # Build header mapping: Id, Name, rest = correspondences
    headers = reader.fieldnames
    if not headers:
        raise Exception(f"No headers found in {csv_path}")
    id_col = next((h for h in headers if h.lower() == "id"), None)
    name_col = next((h for h in headers if h.lower() == "name"), None)
    if not id_col or not name_col:
        raise Exception(f"Missing Id or Name column in {csv_path}")
    # All other columns are correspondences
    correspondence_cols = [h for h in headers if h not in (id_col, name_col)]
    # Try to map correspondence columns to paint_line keys using alias
    col_to_paint_line = {}
    for col in correspondence_cols:
        norm_col = col.lower().replace(" ", "-").replace("_", "-")
        for plid, plconf in paint_line_by_id.items():
            alias = plconf.get("alias", "").lower().replace(" ", "-")
            if norm_col == plid or norm_col == plconf.get("series", "").lower().replace(" ", "-") or (alias and norm_col == alias):
                col_to_paint_line[col] = plid
                break
        else:
            print(f"[WARN] Colonna '{col}' non associata a paint line nota (alias/series/id). Da configurare?")
    colors = []
    for row in rows:
        color_id = normalize_id(row.get(id_col), min_digits)
        color_name = row.get(name_col, "").strip()
        correspondences = []
        for col, plid in col_to_paint_line.items():
            val = row.get(col, "").strip()
            if val:
                corr_id = normalize_id(val, paint_line_by_id.get(plid, {}).get("min_digits", 0))
                correspondences.append({"paint_line": plid, "id": corr_id})
        colors.append({
            "id": color_id,
            "name": color_name,
            "rgb": "",
            "correspondences": correspondences
        })
    return colors

# Process paint lines
for entry in sources["paintLines"]:
    key = entry["key"]
    if entry.get("skip"):
        print(f"Skipping {key}")
        continue
    csv_path = get_csv_path(entry)
    if not csv_path or not csv_path.exists():
        print(f"No CSV found for {key}, skipping.")
        continue
    # Find config for this paint line
    config = paint_line_by_id.get(key)
    if not config:
        print(f"No config for {key} in paint-lines.json, skipping.")
        continue
    # Parse CSV
    colors = parse_csv(csv_path, key, config, paint_line_by_id)
    # Output: just the array of colors
    out_path = DATA / f"{key}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(colors, f, ensure_ascii=False, indent=2)
    print(f"Wrote {out_path}")
