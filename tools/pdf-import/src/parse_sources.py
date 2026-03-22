#!/usr/bin/env python3
"""
Part 1: Source parser
- Parses PDF/HTML sources into raw CSV files in output/normalized
- Leaves CSV translation/remapping to remap_sources.py
"""

from __future__ import annotations

import csv
import json
import logging
import re
import sys
from pathlib import Path

import pdfplumber

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover
    BeautifulSoup = None

try:
    import pytesseract
except ImportError:  # pragma: no cover
    pytesseract = None
if pytesseract is not None:
    pytesseract.pytesseract.tesseract_cmd = r"C:/Program Files/Tesseract-OCR/tesseract.exe"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).parent
TOOLS_DIR = SCRIPT_DIR.parent
SOURCES_FILE = TOOLS_DIR / "mappings" / "sources-config.json"
INPUT_DIR = TOOLS_DIR / "input"
OUTPUT_DIR = TOOLS_DIR / "output"
PARSED_DIR = OUTPUT_DIR / "parsed"


def build_stats() -> dict[str, int]:
    return {
        "total": 0,
        "missing": 0,
        "csv": 0,
        "html": 0,
        "pdf_table": 0,
        "pdf_image": 0,
        "written": 0,
        "failed": 0,
    }


def log_file_status(section: str, key: str, filename: str, status: str, details: str = "") -> None:
    message = f"[{section}] {key} | {filename} | {status}"
    if details:
        message = f"{message} ({details})"
    logger.info(message)


def load_sources() -> dict:
    try:
        with SOURCES_FILE.open("r", encoding="utf-8") as file_handle:
            return json.load(file_handle)
    except FileNotFoundError:
        logger.error("sources-config.json not found at %s", SOURCES_FILE)
        sys.exit(1)
    except json.JSONDecodeError as exc:
        logger.error("Invalid JSON in sources-config.json: %s", exc)
        sys.exit(1)


def parse_pages_spec(pages: str | None) -> list[int] | None:
    if not pages:
        return None

    parsed: set[int] = set()
    for part in str(pages).split(","):
        token = part.strip()
        if not token:
            continue
        if "-" in token:
            start_str, end_str = token.split("-", 1)
            try:
                start = int(start_str.strip())
                end = int(end_str.strip())
            except ValueError:
                continue
            if start > end:
                start, end = end, start
            parsed.update(range(start, end + 1))
        else:
            try:
                parsed.add(int(token))
            except ValueError:
                continue

    return sorted(parsed) if parsed else None


def normalize_table_rows(rows: list[list[str]]) -> list[list[str]]:
    cleaned_rows: list[list[str]] = []
    for row in rows:
        cleaned = [str(cell or "").replace("\n", " ").strip() for cell in row]
        if any(cleaned):
            cleaned_rows.append(cleaned)

    if not cleaned_rows:
        return []

    width = max(len(row) for row in cleaned_rows)
    return [row + [""] * (width - len(row)) for row in cleaned_rows]


def build_output_path(source_file: Path) -> Path:
    return PARSED_DIR / f"{source_file.stem}.csv"


def write_csv(rows: list[list[str]], target_path: Path) -> int:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    PARSED_DIR.mkdir(parents=True, exist_ok=True)
    with target_path.open("w", encoding="utf-8", newline="") as file_handle:
        writer = csv.writer(file_handle, delimiter=";")
        writer.writerows(rows)
    return len(rows)


def extract_tables_from_html(filepath: Path) -> list[list[str]]:
    all_rows: list[list[str]] = []
    html = filepath.read_text(encoding="utf-8", errors="replace")

    if BeautifulSoup is not None:
        soup = BeautifulSoup(html, "html.parser")
        tables = soup.find_all("table")
        for table in tables:
            for tr in table.find_all("tr"):
                cells = tr.find_all(["th", "td"])
                values = [cell.get_text(separator=" ", strip=True) for cell in cells]
                if any(values):
                    all_rows.append(values)

    if all_rows:
        return normalize_table_rows(all_rows)

    if pd is not None:
        try:
            tables = pd.read_html(str(filepath))
            for df in tables:
                frame = df.fillna("")
                all_rows.append([str(col).strip() for col in frame.columns.tolist()])
                for row in frame.values.tolist():
                    all_rows.append([str(cell).strip() for cell in row])
            if all_rows:
                return normalize_table_rows(all_rows)
        except Exception:
            pass

    div_pattern = re.compile(r"<div[^>]*>(.*?)</div>", re.I | re.S)

    color_title_pattern = re.compile(
        r"<!--\s*color_title\s+include\s*-->(.*?)<!--\s*color_title\s+include\s*-->",
        re.I | re.S,
    )
    header_row: list[str] = []
    color_title_match = color_title_pattern.search(html)
    if color_title_match:
        for raw_cell in div_pattern.findall(color_title_match.group(1)):
            text = re.sub(r"<br\s*/?>", "/", raw_cell, flags=re.I)
            text = re.sub(r"<[^>]+>", "", text)
            text = text.replace("&nbsp;", " ").strip()
            header_row.append(text)

    html_rows: list[list[str]] = []
    if header_row:
        html_rows.append(header_row)

    block_pattern = re.compile(
        r"<!--\s*([a-z0-9_]+)\s+include\s*-->(.*?)<!--\s*end\s+\1\s+include\s*-->",
        re.I | re.S,
    )
    for block_name, block in block_pattern.findall(html):
        if block_name.lower() == "color_title":
            continue
        cells: list[str] = []
        for raw_cell in div_pattern.findall(block):
            text = re.sub(r"<br\s*/?>", "/", raw_cell, flags=re.I)
            text = re.sub(r"<[^>]+>", "", text)
            text = text.replace("&nbsp;", " ").strip()
            cells.append(text)
        if any(cells):
            html_rows.append(cells)

    if html_rows:
        return normalize_table_rows(html_rows)

    return normalize_table_rows(all_rows)


def extract_tables_from_pdf(filepath: Path, pages: list[int] | None = None) -> list[list[str]]:
    rows: list[list[str]] = []
    with pdfplumber.open(filepath) as pdf:
        selected_pages = pages or list(range(1, len(pdf.pages) + 1))
        for page_num in selected_pages:
            if page_num < 1 or page_num > len(pdf.pages):
                continue
            page = pdf.pages[page_num - 1]
            for table in page.extract_tables() or []:
                for row in table or []:
                    cleaned = [str(cell or "").strip() for cell in row]
                    if any(cleaned):
                        rows.append(cleaned)
    return normalize_table_rows(rows)


def extract_rows_from_pdf_image(filepath: Path, pages: list[int] | None = None) -> list[list[str]]:
    if pytesseract is None:
        return []

    rows: list[list[str]] = []
    with pdfplumber.open(filepath) as pdf:
        selected_pages = pages or list(range(1, len(pdf.pages) + 1))
        for page_num in selected_pages:
            if page_num < 1 or page_num > len(pdf.pages):
                continue

            page = pdf.pages[page_num - 1]
            image = page.to_image(resolution=220).original
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)

            items: list[tuple[int, int, str]] = []
            for idx in range(len(data.get("text", []))):
                text = (data["text"][idx] or "").strip()
                conf = data.get("conf", ["-1"])[idx]
                if not text:
                    continue
                try:
                    conf_value = float(conf)
                except ValueError:
                    conf_value = -1
                if conf_value < 20:
                    continue
                top = int(data["top"][idx])
                left = int(data["left"][idx])
                items.append((top, left, text))

            if not items:
                continue

            items.sort(key=lambda item: (item[0], item[1]))
            grouped_lines: list[list[tuple[int, str]]] = []
            current_line: list[tuple[int, str]] = []
            current_top = items[0][0]

            for top, left, text in items:
                if abs(top - current_top) > 14 and current_line:
                    grouped_lines.append(current_line)
                    current_line = [(left, text)]
                    current_top = top
                else:
                    current_line.append((left, text))

            if current_line:
                grouped_lines.append(current_line)

            for line in grouped_lines:
                line.sort(key=lambda item: item[0])
                merged = " ".join(token for _, token in line)
                parts = [part.strip() for part in re.split(r"\s{2,}|\t|\|", merged) if part.strip()]
                if not parts:
                    parts = [merged.strip()] if merged.strip() else []
                if parts:
                    rows.append(parts)

            if not rows:
                text = pytesseract.image_to_string(image)
                for line in text.splitlines():
                    clean_line = line.strip()
                    if not clean_line:
                        continue
                    parts = [part.strip() for part in re.split(r"\s{2,}|\t|\|", clean_line) if part.strip()]
                    if parts:
                        rows.append(parts)

    return normalize_table_rows(rows)


def parse_pdf_file(filepath: Path, metadata: dict, pdf_type: str) -> tuple[bool, str]:
    try:
        selected_pages = parse_pages_spec(metadata.get("pages"))

        if pdf_type == "table":
            rows = extract_tables_from_pdf(filepath, selected_pages)
        else:
            if pytesseract is None:
                return False, "pytesseract not installed"
            rows = extract_rows_from_pdf_image(filepath, selected_pages)

        if not rows:
            return False, "no rows extracted"

        output_path = build_output_path(filepath)
        row_count = write_csv(rows, output_path)
        return True, f"rows={row_count}, out={output_path.name}"
    except Exception as exc:
        return False, str(exc)


def parse_html_file(filepath: Path) -> tuple[bool, str]:
    try:
        rows = extract_tables_from_html(filepath)
        if not rows:
            return False, "no tables found"

        output_path = build_output_path(filepath)
        row_count = write_csv(rows, output_path)
        return True, f"rows={row_count}, out={output_path.name}"
    except Exception as exc:
        return False, str(exc)


def process_sources(sources_config: dict, stats: dict[str, int]) -> None:
    for line in sources_config.get("lines", []):
        line_id = str(line.get("line_id", "unknown"))
        for source in line.get("sources", []):
            filename = str(source.get("file", "")).strip()
            source_type = str(source.get("type", "csv")).strip().lower()
            source_file = INPUT_DIR / filename

            stats["total"] += 1

            if not source_file.exists():
                stats["missing"] += 1
                log_file_status("LINE", line_id, filename, "MISSING")
                continue

            if source_type == "csv":
                stats["csv"] += 1
                log_file_status("LINE", line_id, filename, "CSV READY")
                continue

            if source_type in {"html", "html-table"}:
                stats["html"] += 1
                log_file_status("LINE", line_id, filename, "PARSE HTML")
                ok, details = parse_html_file(source_file)
                if ok:
                    stats["written"] += 1
                    log_file_status("LINE", line_id, filename, "HTML EXTRACTED", details)
                else:
                    stats["failed"] += 1
                    log_file_status("LINE", line_id, filename, "HTML FAILED", details)
                continue

            if source_type == "pdf-table":
                stats["pdf_table"] += 1
                details = []
                if source.get("pages"):
                    details.append(f"pages={source.get('pages')}")
                if source.get("tableTitle"):
                    details.append(f"title={source.get('tableTitle')}")
                log_file_status("LINE", line_id, filename, "PARSE PDF TABLE", ", ".join(details))
                ok, parsed_details = parse_pdf_file(source_file, source, "table")
                if ok:
                    stats["written"] += 1
                    log_file_status("LINE", line_id, filename, "PDF TABLE EXTRACTED", parsed_details)
                else:
                    stats["failed"] += 1
                    log_file_status("LINE", line_id, filename, "PDF TABLE FAILED", parsed_details)
                continue

            if source_type == "pdf-image":
                stats["pdf_image"] += 1
                details = f"pages={source.get('pages')}" if source.get("pages") else ""
                log_file_status("LINE", line_id, filename, "PARSE PDF IMAGE", details)
                ok, parsed_details = parse_pdf_file(source_file, source, "image")
                if ok:
                    stats["written"] += 1
                    log_file_status("LINE", line_id, filename, "PDF IMAGE EXTRACTED", parsed_details)
                else:
                    stats["failed"] += 1
                    log_file_status("LINE", line_id, filename, "PDF IMAGE FAILED", parsed_details)
                continue

            stats["failed"] += 1
            log_file_status("LINE", line_id, filename, f"UNKNOWN TYPE: {source_type}")


def main() -> None:
    logger.info("=" * 60)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PARSED_DIR.mkdir(parents=True, exist_ok=True)

    sources_config = load_sources()
    stats = build_stats()
    process_sources(sources_config, stats)

    logger.info("=" * 60)
    logger.info(
        "Summary | total=%s csv=%s html=%s pdf-table=%s pdf-image=%s written=%s failed=%s missing=%s",
        stats["total"],
        stats["csv"],
        stats["html"],
        stats["pdf_table"],
        stats["pdf_image"],
        stats["written"],
        stats["failed"],
        stats["missing"],
    )
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
