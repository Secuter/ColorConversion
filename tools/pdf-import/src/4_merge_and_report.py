#!/usr/bin/env python3
"""
Step 4: Merge and Compare Paint Line CSVs

For each paint line in sources-csv.json with 2+ CSVs:
- Merge all color mappings into one CSV (union of all rows, deduped by Id if present, else by Name)
- Create a report of differences (rows with same Id/Name but different data)
- If a color is present only in 1 CSV, it's OK (not a diff)
"""
import csv
import json
from pathlib import Path
from collections import defaultdict

SOURCES_JSON = Path(__file__).parent / "../sources-csv.json"
CSV_DIRS = [
    Path(__file__).parent.parent / "input",
    Path(__file__).parent.parent / "output"
]
MERGE_DIR = Path(__file__).parent.parent / "output" / "merged"
REPORT_DIR = Path(__file__).parent.parent / "merge_reports"
MERGE_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(exist_ok=True)

ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")

# Helper: Read CSV with fallback encodings, always delimiter=';'
def read_csv(path):
    for enc in ENCODINGS:
        try:
            with path.open("r", encoding=enc) as f:
                return list(csv.DictReader(f, delimiter=';'))
        except Exception:
            continue
    raise RuntimeError(f"Could not read {path} with any encoding")

def merge_and_compare(paint_key, file_names):
    # Find all CSVs for this paint line
    csv_paths = []
    for name in file_names:
        for d in CSV_DIRS:
            p = d / name
            if p.exists():
                csv_paths.append(p)
                break
    if len(csv_paths) < 2:
        return  # nothing to do
    # Read all rows from all files
    all_rows = []
    for p in csv_paths:
        rows = read_csv(p)
        for row in rows:
            row['__source'] = p.name
        all_rows.append(rows)
    # Build merged set by Id (if present), else by Name
    key_fields = [k for k in ("Id", "Name") if any(k in row for rows in all_rows for row in rows)]
    if not key_fields:
        print(f"[WARN] No Id/Name in {paint_key}, skipping.")
        return
    key_field = key_fields[0]
    merged = {}
    sources_for_key = defaultdict(list)
    for rows in all_rows:
        for row in rows:
            key = row.get(key_field, "").strip()
            if not key:
                continue
            if key not in merged:
                merged[key] = row.copy()
            sources_for_key[key].append(row)
    # Write merged CSV
    all_columns = set()
    for row in merged.values():
        all_columns.update(row.keys())
    all_columns.discard('__source')
    sorted_cols = []
    if "Id" in all_columns:
        sorted_cols.append("Id")
    if "Name" in all_columns:
        sorted_cols.append("Name")
    rest = [c for c in all_columns if c not in sorted_cols]
    sorted_cols += sorted(rest, key=str.casefold)
    merge_path = MERGE_DIR / f"{paint_key}_merged.csv"
    with merge_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=sorted_cols, delimiter=';')
        writer.writeheader()
        for row in merged.values():
            writer.writerow({col: row.get(col, "") for col in sorted_cols})
    # Compare for differences
    diffs = []
    for key, rows in sources_for_key.items():
        if len(rows) < 2:
            continue  # only in one file, that's OK
        # Compare all rows for this key
        base = rows[0]
        for other in rows[1:]:
            for col in sorted_cols:
                if col in ("__source", key_field, "Name"):
                    continue
                v1 = (base.get(col, "") or "").strip()
                v2 = (other.get(col, "") or "").strip()
                if v1 != v2:
                    diffs.append({
                        "key": key,
                        "field": col,
                        "value1": v1,
                        "value2": v2,
                        "source1": base['__source'],
                        "source2": other['__source']
                    })
    # Write report
    report_path = REPORT_DIR / f"{paint_key}_diff_report.txt"
    with report_path.open("w", encoding="utf-8") as f:
        if not diffs:
            f.write("No differences found.\n")
        else:
            for d in diffs:
                f.write(f"Key: {d['key']} | Field: {d['field']}\n  {d['source1']}: {d['value1']}\n  {d['source2']}: {d['value2']}\n\n")
    print(f"Merged: {merge_path.name} | Report: {report_path.name}")

def main():
    with open(SOURCES_JSON, encoding="utf-8") as f:
        data = json.load(f)
    for section in ("paintLines", "standards"):
        for entry in data.get(section, []):
            files = [f["name"] for f in entry.get("files", []) if f["name"].lower().endswith('.csv')]
            if len(files) > 1:
                merge_and_compare(entry["key"], files)

if __name__ == "__main__":
    main()
