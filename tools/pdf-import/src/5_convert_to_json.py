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

# Helper: parse a CSV file into color dicts
# (Assumes columns: id, name, rgb, correspondences, etc. Adjust as needed)
def parse_csv(csv_path):
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=';')
        rows = list(reader)
    # Normalize fields
    colors = []
    for row in rows:
        color = {
            "id": row.get("id") or row.get("ID") or row.get("code") or row.get("Code"),
            "name": row.get("name") or row.get("Name"),
            "rgb": row.get("rgb") or row.get("RGB"),
            # Correspondences: parse as JSON if present, else empty list
            "correspondences": json.loads(row["correspondences"]) if row.get("correspondences") else []
        }
        # Remove None fields
        color = {k: v for k, v in color.items() if v is not None}
        colors.append(color)
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
    colors = parse_csv(csv_path)
    # Compose output JSON
    out_json = {
        "series": config["series"],
        "manufacturer": config["manufacturer"],
        "prefixes": config.get("prefixes", []),
        "colors": colors
    }
    out_path = DATA / f"{key}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out_json, f, ensure_ascii=False, indent=2)
    print(f"Wrote {out_path}")
