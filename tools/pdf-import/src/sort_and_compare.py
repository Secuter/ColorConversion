#!/usr/bin/env python3
"""
CSV Manager for Paint Data

1. Sort columns in each CSV: 'Id' first, 'Name' second (if present), rest alphabetically.
2. Compare files for each paint line in sources-csv.json: report lines with 2+ files.
"""
import csv
import json
from pathlib import Path

# --- CONFIGURATION ---
SOURCES_JSON = Path(__file__).parent / "../sources-csv.json"
CSV_DIRS = [
    Path(__file__).parent.parent / "input",
    Path(__file__).parent.parent / "output"
]

# --- COLUMN SORTING ---
ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")

def sort_csv_columns(csv_path: Path):
    last_error = None
    for encoding in ENCODINGS:
        try:
            with csv_path.open("r", encoding=encoding) as f:
                reader = csv.DictReader(f, delimiter=';')
                rows = list(reader)
                if not rows:
                    return  # Empty file
                columns = list(rows[0].keys())
                # Sort columns: Id, Name (if present), then rest alphabetically
                sorted_cols = []
                if "Id" in columns:
                    sorted_cols.append("Id")
                if "Name" in columns:
                    sorted_cols.append("Name")
                rest = [c for c in columns if c not in sorted_cols]
                sorted_cols += sorted(rest, key=str.casefold)
            # Write sorted CSV
            with csv_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=sorted_cols, delimiter=';')
                writer.writeheader()
                for row in rows:
                    writer.writerow({col: row.get(col, "") for col in sorted_cols})
            return
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error is not None:
        print(f"[ERROR] Could not decode {csv_path} with any known encoding.")
        raise last_error

# --- MULTI-FILE CHECK ---
def check_multiple_files(sources_json: Path):
    with sources_json.open("r", encoding="utf-8") as f:
        data = json.load(f)
    multi = []
    for section in ("paintLines", "standards"):
        for entry in data.get(section, []):
            files = entry.get("files", [])
            if len(files) > 1:
                multi.append({"key": entry.get("key"), "files": [f["name"] for f in files]})
    if multi:
        print("Paint lines with 2+ files:")
        for entry in multi:
            print(f"- {entry['key']}: {', '.join(entry['files'])}")
    else:
        print("No paint lines with multiple files.")

# --- MAIN ---
def main():
    # 1. Sort columns in all CSVs in input/output
    for csv_dir in CSV_DIRS:
        for csv_path in csv_dir.glob("*.csv"):
            sort_csv_columns(csv_path)
    # 2. Check for paint lines with multiple files
    check_multiple_files(SOURCES_JSON)

if __name__ == "__main__":
    main()
