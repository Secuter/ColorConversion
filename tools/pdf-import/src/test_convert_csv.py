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
# Build a lookup for paint line config by alias
paint_line_by_alias = {pl["alias"]: pl for pl in paint_lines}

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

def convert_csv_to_json(csv_path, config):
    # Open CSV
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=';')
        rows = list(reader)    
    
    # Build header mapping: Id, Name, rest = correspondences
    headers = reader.fieldnames
    if not headers:
        raise Exception(f"No headers found in {csv_path}")
    id_col = next((h for h in headers if h.lower() == "id"), None)
    name_col = next((h for h in headers if h.lower() == "name"), None)
    if not id_col or not name_col:
        raise Exception(f"Missing Id or Name column in {csv_path}")

    # Try to map correspondence columns to paint_line keys using alias
    correspondence_cols = [h for h in headers if h not in (id_col, name_col)]
    col_to_paint_line = {}
    for col in correspondence_cols:
        alias = col.strip()
        paint_line = paint_line_by_alias.get(alias)
        if paint_line:
            col_to_paint_line[col] = paint_line["id"]
        else:
            print(f"[WARN] No paint line found for column '{col}' in {csv_path}")
    
    colors = []
    min_digits=config.get("min_digits", 0)
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

for section in sources:
    for entry in sources[section]:
        if entry.get("skip"):
            print(f"{entry['key']}\t\t: [SKIPPED]")
            continue
        if entry.get("merged"):
            csv_path = MERGED / entry["merged"]
            if csv_path.exists():
                print(f"{entry['key']}\t\t: {csv_path}")
                convert_csv_to_json(csv_path, paint_line_by_id[entry["key"]])
            else:
                print(f"{entry['key']}\t\t: [NOT FOUND] {csv_path}")
            
        files = entry.get("files", [])
        if len(files) == 1:
            csv_path = INPUT / files[0]["name"]
            if csv_path.exists():
                print(f"{entry['key']}\t\t: {csv_path}")
                convert_csv_to_json(csv_path, paint_line_by_id[entry["key"]])
            else:
                print(f"{entry['key']}\t\t: [NOT FOUND] {csv_path}")