#!/usr/bin/env python3
"""
Extract unique headers from all CSV files in a folder.

Examples:
  python tools/pdf-import/src/extract_csv_headers.py tools/pdf-import/input
  python tools/pdf-import/src/extract_csv_headers.py tools/pdf-import/input --recursive
  python tools/pdf-import/src/extract_csv_headers.py tools/pdf-import/input --output headers.txt
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


ENCODINGS = ("utf-8", "utf-8-sig", "cp1252", "latin-1")


def read_first_row(path: Path, delimiter: str) -> list[str]:
    last_error: UnicodeDecodeError | None = None

    for encoding in ENCODINGS:
        try:
            with path.open("r", encoding=encoding, newline="") as file_handle:
                reader = csv.reader(file_handle, delimiter=delimiter)
                return next(reader, [])
        except UnicodeDecodeError as exc:
            last_error = exc

    if last_error is not None:
        raise last_error
    return []


def get_csv_files(folder: Path, recursive: bool) -> list[Path]:
    pattern = "**/*.csv" if recursive else "*.csv"
    return sorted(path for path in folder.glob(pattern) if path.is_file())


def collect_unique_headers(folder: Path, delimiter: str, recursive: bool) -> list[str]:
    csv_files = get_csv_files(folder, recursive)
    headers: set[str] = set()

    for csv_file in csv_files:
        row = read_first_row(csv_file, delimiter)
        for header in row:
            normalized = str(header).strip().strip('"')
            if normalized:
                headers.add(normalized)

    return sorted(headers, key=lambda value: value.casefold())


def collect_headers_with_files(folder: Path, delimiter: str, recursive: bool) -> dict[str, set[str]]:
    csv_files = get_csv_files(folder, recursive)
    headers_with_files: dict[str, set[str]] = {}

    for csv_file in csv_files:
        row = read_first_row(csv_file, delimiter)
        relative_name = str(csv_file.relative_to(folder)).replace("\\", "/")
        for header in row:
            normalized = str(header).strip().strip('"')
            if not normalized:
                continue
            if normalized not in headers_with_files:
                headers_with_files[normalized] = set()
            headers_with_files[normalized].add(relative_name)

    return headers_with_files


def build_headers_json_payload(headers_with_files: dict[str, set[str]]) -> dict:
    sorted_headers = sorted(headers_with_files.keys(), key=lambda value: value.casefold())
    return {
        "total_headers": len(sorted_headers),
        "headers": sorted_headers,
        "header_sources": [
            {
                "header": header,
                "files": sorted(headers_with_files[header], key=lambda value: value.casefold()),
            }
            for header in sorted_headers
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract unique headers from CSV files in a folder")
    parser.add_argument("folder", type=Path, help="Folder containing CSV files")
    parser.add_argument("--delimiter", default=";", help="CSV delimiter (default: ';')")
    parser.add_argument("--recursive", action="store_true", help="Search CSV files recursively")
    parser.add_argument("--text-output", type=Path, help="Output path for plain text headers list")
    parser.add_argument("--json-output", type=Path, help="Output path for JSON headers + source files")
    parser.add_argument("--print", action="store_true", help="Print headers to console")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    folder: Path = args.folder
    if not folder.exists() or not folder.is_dir():
        parser.error(f"Folder does not exist or is not a directory: {folder}")

    headers = collect_unique_headers(folder, args.delimiter, args.recursive)
    headers_with_files = collect_headers_with_files(folder, args.delimiter, args.recursive)

    text_output: Path = args.text_output or (folder / "headers.txt")
    json_output: Path = args.json_output or (folder / "headers-with-sources.json")

    text_output.parent.mkdir(parents=True, exist_ok=True)
    text_output.write_text("\n".join(headers) + "\n", encoding="utf-8")

    json_payload = build_headers_json_payload(headers_with_files)
    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(json_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Saved {len(headers)} headers to {text_output}")
    print(f"Saved JSON header source map to {json_output}")

    if args.print:
        for header in headers:
            print(header)


if __name__ == "__main__":
    main()
