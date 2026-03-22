#!/usr/bin/env python3
"""
Main parsing script for paint line data sources.
Handles CSV (pass-through), PDF (table/image), and HTML parsing.
Updates column header mappings as new headers are encountered.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path
from datetime import datetime
import logging

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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
SCRIPT_DIR = Path(__file__).parent
TOOLS_DIR = SCRIPT_DIR.parent
SOURCES_FILE = TOOLS_DIR / "sources-config.json"
HEADERS_CONFIG = TOOLS_DIR / "mappings" / "column-headers.json"
INPUT_DIR = TOOLS_DIR / "input"
OUTPUT_DIR = TOOLS_DIR / "output"
NORMALIZED_DIR = OUTPUT_DIR / "normalized"


def build_stats():
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


def log_file_status(section, key, filename, status, details=""):
    message = f"[{section}] {key} | {filename} | {status}"
    if details:
        message = f"{message} ({details})"
    logger.info(message)


def load_sources():
    """Load sources-config.json configuration."""
    try:
        with open(SOURCES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"sources-config.json not found at {SOURCES_FILE}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in sources-config.json: {e}")
        sys.exit(1)


def load_headers_config():
    """Load column header mappings configuration."""
    try:
        with open(HEADERS_CONFIG, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "column_mappings": {},
            "lastUpdated": datetime.now().isoformat()
        }


def save_headers_config(config):
    """Save column header mappings configuration."""
    config["lastUpdated"] = datetime.now().isoformat()
    with open(HEADERS_CONFIG, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def normalize_header(header):
    """Normalize a header string for comparison."""
    normalized = str(header).strip().lower()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def find_mapped_header(header, headers_config):
    """Find the normalized column name for a header, or return None if unknown."""
    normalized = normalize_header(header)
    
    # Check if this exact header is already in a mapping
    for mapped_name, variant in headers_config.get("column_mappings", {}).items():
        if normalize_header(variant) == normalized:
            return mapped_name
    
    return None


def register_unknown_header(header, headers_config):
    """Register an unknown header for manual review and add identity mapping."""
    normalized = normalize_header(header)
    column_mappings = headers_config.get("column_mappings", {})
    
    # Check if already registered
    if header not in column_mappings:
        # Add identity mapping (source and destination equal to the found value)
        column_mappings[header] = header
        headers_config["column_mappings"] = column_mappings
        # logger.warning(f"Unknown column header: '{header}' - added to review list")
        return True
    
    return False


def parse_pages_spec(pages: str | None) -> list[int] | None:
    if not pages:
        return None

    result: set[int] = set()
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
            result.update(range(start, end + 1))
        else:
            try:
                result.add(int(token))
            except ValueError:
                continue

    return sorted(result) if result else None


def slugify(filename: str) -> str:
    base = Path(filename).stem.lower()
    return re.sub(r"[^a-z0-9]+", "-", base).strip("-")


def normalize_table_rows(rows: list[list[str]]) -> list[list[str]]:
    cleaned_rows: list[list[str]] = []
    for row in rows:
        cleaned = [str(cell or "").replace("\n", " ").strip() for cell in row]
        if any(cleaned):
            cleaned_rows.append(cleaned)

    if not cleaned_rows:
        return []

    width = max(len(row) for row in cleaned_rows)
    normalized = [row + [""] * (width - len(row)) for row in cleaned_rows]
    return normalized


def map_headers(headers: list[str], headers_config: dict) -> list[str]:
    mapped: list[str] = []
    for idx, header in enumerate(headers):
        header_text = str(header).strip()
        if not header_text:
            # Keep empty headers as empty strings
            mapped.append("")
        else:
            mapped_name = find_mapped_header(header_text, headers_config)
            if mapped_name:
                mapped.append(mapped_name)
            else:
                register_unknown_header(header_text, headers_config)
                mapped.append(header_text)
    return mapped


def build_output_path(source_file: Path) -> Path:
    return NORMALIZED_DIR / f"{slugify(source_file.name)}.csv"


def clean_rows(rows: list[list[str]]) -> list[list[str]]:
    """
    Clean rows by:
    - Replacing " / " with "/" in all cells
    - Excluding rows with first cell "Notes"
    - Excluding repeated header rows (first cell matches header's first cell, only if header is not empty)
    """
    if not rows or len(rows) < 1:
        return rows
    
    header_row = rows[0]
    header_first_cell = (header_row[0] or "").strip().lower() if header_row else ""
    
    cleaned: list[list[str]] = [header_row]
    
    for row in rows[1:]:
        if not row:
            continue
        
        # Clean cells: replace " / " with "/"
        cleaned_row = [
            cell.replace(" / ", "/") if cell else cell
            for cell in row
        ]
        
        # Skip rows with first cell "Notes"
        first_cell = (cleaned_row[0] or "").strip().lower()
        if first_cell == "notes":
            continue
        
        # Skip repeated header rows (first cell matches header's first cell)
        # Only do this check if the header's first cell is not empty
        if header_first_cell and first_cell == header_first_cell:
            continue
        
        cleaned.append(cleaned_row)
    
    return cleaned


def write_csv(rows: list[list[str]], target_path: Path) -> int:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with target_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerows(rows)
    return len(rows)


def extract_tables_from_html(filepath: Path) -> list[list[str]]:
    all_rows: list[list[str]] = []

    html = filepath.read_text(encoding="utf-8", errors="replace")

    if BeautifulSoup is not None:
        soup = BeautifulSoup(html, "html.parser")
        tables = soup.find_all("table")
        for table in tables:
            trs = table.find_all("tr")
            for tr in trs:
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
                header_row = [str(col).strip() for col in frame.columns.tolist()]
                all_rows.append(header_row)
                for row in frame.values.tolist():
                    all_rows.append([str(cell).strip() for cell in row])
            if all_rows:
                return normalize_table_rows(all_rows)
        except Exception:
            pass

    # Fallback for conversion pages that use comment-delimited <div> blocks
    div_pattern = re.compile(r"<div[^>]*>(.*?)</div>", re.I | re.S)

    # First, extract headers between two <!-- color_title include --> comments
    color_title_pattern = re.compile(
        r"<!--\s*color_title\s+include\s*-->(.*?)<!--\s*color_title\s+include\s*-->",
        re.I | re.S,
    )
    header_row: list[str] = []
    color_title_match = color_title_pattern.search(html)
    if color_title_match:
        header_section = color_title_match.group(1)
        for raw_cell in div_pattern.findall(header_section):
            text = re.sub(r"<br\s*/?>", "/", raw_cell, flags=re.I)
            text = re.sub(r"<[^>]+>", "", text)
            text = text.replace("&nbsp;", " ").strip()
            # Include all cells, even empty ones
            header_row.append(text)

    html_rows: list[list[str]] = []
    # If we found headers from color_title, add them first
    if header_row:
        html_rows.append(header_row)
    
    # Extract all data blocks: <!-- xxxxx include --> ... <!-- end xxxxx include -->
    block_pattern = re.compile(
        r"<!--\s*([a-z0-9_]+)\s+include\s*-->(.*?)<!--\s*end\s+\1\s+include\s*-->",
        re.I | re.S,
    )
    for block_name, block in block_pattern.findall(html):
        # Skip the color_title block since we already processed it
        if block_name.lower() == "color_title":
            continue
        cells: list[str] = []
        for raw_cell in div_pattern.findall(block):
            text = re.sub(r"<br\s*/?>", "/", raw_cell, flags=re.I)
            text = re.sub(r"<[^>]+>", "", text)
            text = text.replace("&nbsp;", " ").strip()
            # Include all cells, even empty ones
            cells.append(text)
        # Only add rows that have actual content
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
            tables = page.extract_tables()
            for table in tables or []:
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
            for i in range(len(data.get("text", []))):
                text = (data["text"][i] or "").strip()
                conf = data.get("conf", ["-1"])[i]
                if not text:
                    continue
                try:
                    conf_value = float(conf)
                except ValueError:
                    conf_value = -1
                if conf_value < 20:
                    continue
                top = int(data["top"][i])
                left = int(data["left"][i])
                items.append((top, left, text))

            if not items:
                continue

            items.sort(key=lambda x: (x[0], x[1]))
            grouped_lines: list[list[tuple[int, str]]] = []
            current_line: list[tuple[int, str]] = []
            current_top = items[0][0]
            threshold = 14

            for top, left, text in items:
                if abs(top - current_top) > threshold and current_line:
                    grouped_lines.append(current_line)
                    current_line = [(left, text)]
                    current_top = top
                else:
                    current_line.append((left, text))

            if current_line:
                grouped_lines.append(current_line)

            for line in grouped_lines:
                line.sort(key=lambda x: x[0])
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


def prepare_rows_with_mapped_headers(rows: list[list[str]], headers_config: dict) -> list[list[str]]:
    if not rows:
        return []

    candidate = rows[0]
    filled_cells = [cell for cell in candidate if str(cell).strip()]
    alpha_cells = [cell for cell in filled_cells if re.search(r"[A-Za-z]", str(cell))]
    digit_heavy_cells = [
        cell for cell in filled_cells
        if re.search(r"\d", str(cell)) and not re.search(r"[A-Za-z]{3,}", str(cell))
    ]

    looks_like_header = bool(
        filled_cells
        and len(alpha_cells) >= max(2, len(filled_cells) // 2)
        and len(digit_heavy_cells) <= len(filled_cells) // 2
    )

    if looks_like_header:
        mapped_header = map_headers(candidate, headers_config)
        return [mapped_header] + rows[1:]

    generated_header = [f"column_{idx + 1}" for idx in range(len(candidate))]
    return [generated_header] + rows


def process_paint_lines(sources, headers_config, stats):
    """Process paint lines from sources-config.json."""
    paint_lines = sources.get("paintLines", [])
    
    for paint_line in paint_lines:
        key = paint_line.get("key")
        files = paint_line.get("files", [])        
        
        for file_obj in files:
            filename = file_obj.get("name")
            file_format = file_obj.get("format", "csv")  # Default to csv if no format
            source_file = INPUT_DIR / filename
            stats["total"] += 1
            
            if not source_file.exists():
                stats["missing"] += 1
                log_file_status("PAINT", key, filename, "MISSING")
                continue
            
            # If no format specified (defaults to csv), it's ready
            if file_format == "csv":
                stats["csv"] += 1
                log_file_status("PAINT", key, filename, "CSV READY")
            
            elif file_format == "html":
                stats["html"] += 1
                log_file_status("PAINT", key, filename, "PARSE HTML")
                ok, details = parse_html_file(source_file, key, file_obj, headers_config)
                if ok:
                    stats["written"] += 1
                    log_file_status("PAINT", key, filename, "HTML EXTRACTED", details)
                else:
                    stats["failed"] += 1
                    log_file_status("PAINT", key, filename, "HTML FAILED", details)
            
            elif file_format == "pdf-table":
                stats["pdf_table"] += 1
                pages = file_obj.get("pages")
                table_title = file_obj.get("tableTitle")
                details = []
                if pages:
                    details.append(f"pages={pages}")
                if table_title:
                    details.append(f"title={table_title}")
                log_file_status("PAINT", key, filename, "PARSE PDF TABLE", ", ".join(details))
                ok, parsed_details = parse_pdf_file(source_file, key, file_obj, headers_config, "table")
                if ok:
                    stats["written"] += 1
                    log_file_status("PAINT", key, filename, "PDF TABLE EXTRACTED", parsed_details)
                else:
                    stats["failed"] += 1
                    log_file_status("PAINT", key, filename, "PDF TABLE FAILED", parsed_details)
            
            elif file_format == "pdf-image":
                stats["pdf_image"] += 1
                pages = file_obj.get("pages")
                details = f"pages={pages}" if pages else ""
                log_file_status("PAINT", key, filename, "PARSE PDF IMAGE", details)
                ok, parsed_details = parse_pdf_file(source_file, key, file_obj, headers_config, "image")
                if ok:
                    stats["written"] += 1
                    log_file_status("PAINT", key, filename, "PDF IMAGE EXTRACTED", parsed_details)
                else:
                    stats["failed"] += 1
                    log_file_status("PAINT", key, filename, "PDF IMAGE FAILED", parsed_details)

            else:
                log_file_status("PAINT", key, filename, f"SKIP UNKNOWN FORMAT: {file_format}")


def process_standards(sources, headers_config, stats):
    """Process color standards from sources-config.json."""
    standards = sources.get("standards", [])
    
    for standard in standards:
        key = standard.get("key")
        files = standard.get("files", [])
        
        for file_obj in files:
            filename = file_obj.get("name")
            file_format = file_obj.get("format", "csv")  # Default to csv if no format
            source_file = INPUT_DIR / filename
            stats["total"] += 1
            
            if not source_file.exists():
                stats["missing"] += 1
                log_file_status("STD", key, filename, "MISSING")
                continue
            
            # If no format specified (defaults to csv), it's ready
            if file_format == "csv":
                stats["csv"] += 1
                log_file_status("STD", key, filename, "CSV READY")
            
            elif file_format == "html":
                stats["html"] += 1
                log_file_status("STD", key, filename, "PARSE HTML")
                ok, details = parse_html_file(source_file, key, file_obj, headers_config)
                if ok:
                    stats["written"] += 1
                    log_file_status("STD", key, filename, "HTML EXTRACTED", details)
                else:
                    stats["failed"] += 1
                    log_file_status("STD", key, filename, "HTML FAILED", details)
            
            elif file_format == "pdf-table":
                stats["pdf_table"] += 1
                pages = file_obj.get("pages")
                details = f"pages={pages}" if pages else ""
                log_file_status("STD", key, filename, "PARSE PDF TABLE", details)
                ok, parsed_details = parse_pdf_file(source_file, key, file_obj, headers_config, "table")
                if ok:
                    stats["written"] += 1
                    log_file_status("STD", key, filename, "PDF TABLE EXTRACTED", parsed_details)
                else:
                    stats["failed"] += 1
                    log_file_status("STD", key, filename, "PDF TABLE FAILED", parsed_details)
            
            elif file_format == "pdf-image":
                stats["pdf_image"] += 1
                pages = file_obj.get("pages")
                details = f"pages={pages}" if pages else ""
                log_file_status("STD", key, filename, "PARSE PDF IMAGE", details)
                ok, parsed_details = parse_pdf_file(source_file, key, file_obj, headers_config, "image")
                if ok:
                    stats["written"] += 1
                    log_file_status("STD", key, filename, "PDF IMAGE EXTRACTED", parsed_details)
                else:
                    stats["failed"] += 1
                    log_file_status("STD", key, filename, "PDF IMAGE FAILED", parsed_details)

            else:
                log_file_status("STD", key, filename, f"SKIP UNKNOWN FORMAT: {file_format}")


def parse_pdf_file(filepath, key, metadata, headers_config, pdf_type):
    """
    Parse a PDF file (table or image format).
    Currently logs intent; actual parsing via external script or library.
    
    Args:
        filepath: Path to the PDF file
        key: Unique identifier for this source
        metadata: File object metadata (may contain pages, tableTitle, etc.)
        headers_config: Column header mappings configuration
        pdf_type: Either 'table' or 'image' (for OCR)
    """
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

        rows = prepare_rows_with_mapped_headers(rows, headers_config)
        rows = clean_rows(rows)
        output_path = build_output_path(filepath)
        row_count = write_csv(rows, output_path)
        return True, f"rows={row_count}, out={output_path.name}"
    except Exception as exc:
        return False, str(exc)


def parse_html_file(filepath, key, metadata, headers_config):
    """
    Parse an HTML file (table extraction).
    Currently logs intent; actual parsing via external script or library.
    
    Args:
        filepath: Path to the HTML file
        key: Unique identifier for this source
        metadata: File object metadata
        headers_config: Column header mappings configuration
    """
    try:
        rows = extract_tables_from_html(filepath)
        if not rows:
            return False, "no tables found"

        rows = prepare_rows_with_mapped_headers(rows, headers_config)
        rows = clean_rows(rows)
        output_path = build_output_path(filepath)
        row_count = write_csv(rows, output_path)
        return True, f"rows={row_count}, out={output_path.name}"
    except Exception as exc:
        return False, str(exc)


def main():
    """Main entry point."""
    logger.info("="*60)

    # Create output directory if needed
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load configurations
    sources = load_sources()
    
    headers_config = load_headers_config()

    stats = build_stats()
    
    # Process paint lines and standards
    process_paint_lines(sources, headers_config, stats)
    process_standards(sources, headers_config, stats)
    
    # Save updated configurations
    save_headers_config(headers_config)

    logger.info("="*60)
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
    logger.info("="*60)

if __name__ == "__main__":
    main()
