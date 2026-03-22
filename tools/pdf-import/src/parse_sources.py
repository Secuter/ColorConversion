#!/usr/bin/env python3
"""
Main parsing script for paint line data sources.
Handles CSV (pass-through), PDF (table/image), and HTML parsing.
Updates column header mappings as new headers are encountered.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
SCRIPT_DIR = Path(__file__).parent
TOOLS_DIR = SCRIPT_DIR.parent
SOURCES_FILE = TOOLS_DIR / "sources.json"
HEADERS_CONFIG = TOOLS_DIR / "mappings" / "column-headers.json"
INPUT_DIR = TOOLS_DIR / "input"
OUTPUT_DIR = TOOLS_DIR / "output"


def build_stats():
    return {
        "total": 0,
        "missing": 0,
        "csv": 0,
        "html": 0,
        "pdf_table": 0,
        "pdf_image": 0,
    }


def log_file_status(section, key, filename, status, details=""):
    message = f"[{section}] {key} | {filename} | {status}"
    if details:
        message = f"{message} ({details})"
    logger.info(message)


def load_sources():
    """Load sources.json configuration."""
    try:
        with open(SOURCES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"sources.json not found at {SOURCES_FILE}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in sources.json: {e}")
        sys.exit(1)


def load_headers_config():
    """Load column header mappings configuration."""
    try:
        with open(HEADERS_CONFIG, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        # logger.warning(f"column-headers.json not found, creating new")
        return {
            "columnMappings": {},
            "unknownHeaders": [],
            "lastUpdated": datetime.now().isoformat()
        }


def save_headers_config(config):
    """Save column header mappings configuration."""
    config["lastUpdated"] = datetime.now().isoformat()
    with open(HEADERS_CONFIG, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    # logger.info(f"Saved column header mappings to {HEADERS_CONFIG}")


def normalize_header(header):
    """Normalize a header string for comparison."""
    return header.strip().lower()


def find_mapped_header(header, headers_config):
    """Find the normalized column name for a header, or return None if unknown."""
    normalized = normalize_header(header)
    
    # Check if this exact header is already in a mapping
    for mapped_name, variants in headers_config.get("columnMappings", {}).items():
        if any(normalize_header(v) == normalized for v in variants):
            return mapped_name
    
    return None


def register_unknown_header(header, headers_config):
    """Register an unknown header for manual review."""
    normalized = normalize_header(header)
    unknown_list = headers_config.get("unknownHeaders", [])
    
    # Check if already registered
    if not any(normalize_header(h) == normalized for h in unknown_list):
        unknown_list.append(header)
        headers_config["unknownHeaders"] = unknown_list
        # logger.warning(f"Unknown column header: '{header}' - added to review list")
        return True
    
    return False


def process_paint_lines(sources, headers_config, stats):
    """Process paint lines from sources.json."""
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
                parse_html_file(source_file, key, file_obj, headers_config)
            
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
                table_title = file_obj.get("tableTitle")
                parse_pdf_file(source_file, key, file_obj, headers_config, "table")
            
            elif file_format == "pdf-image":
                stats["pdf_image"] += 1
                pages = file_obj.get("pages")
                details = f"pages={pages}" if pages else ""
                log_file_status("PAINT", key, filename, "PARSE PDF IMAGE", details)
                parse_pdf_file(source_file, key, file_obj, headers_config, "image")

            else:
                log_file_status("PAINT", key, filename, f"SKIP UNKNOWN FORMAT: {file_format}")


def process_standards(sources, headers_config, stats):
    """Process color standards from sources.json."""
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
                parse_html_file(source_file, key, file_obj, headers_config)
            
            elif file_format == "pdf-table":
                stats["pdf_table"] += 1
                pages = file_obj.get("pages")
                details = f"pages={pages}" if pages else ""
                log_file_status("STD", key, filename, "PARSE PDF TABLE", details)
                parse_pdf_file(source_file, key, file_obj, headers_config, "table")
            
            elif file_format == "pdf-image":
                stats["pdf_image"] += 1
                pages = file_obj.get("pages")
                details = f"pages={pages}" if pages else ""
                log_file_status("STD", key, filename, "PARSE PDF IMAGE", details)
                parse_pdf_file(source_file, key, file_obj, headers_config, "image")

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
    logger.debug(f"stub parse PDF {pdf_type}: key={key}, file={filepath.name}")


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
    logger.debug(f"stub parse HTML: key={key}, file={filepath.name}")


def main():
    """Main entry point."""
    logger.info("Paint Line Parser")
    
    # Create output directory if needed
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load configurations
    logger.info(f"Config: {SOURCES_FILE}")
    sources = load_sources()
    
    logger.info(f"Header mappings: {HEADERS_CONFIG}")
    headers_config = load_headers_config()

    stats = build_stats()
    
    # Process paint lines and standards
    process_paint_lines(sources, headers_config, stats)
    process_standards(sources, headers_config, stats)
    
    # Save updated configurations
    save_headers_config(headers_config)
    logger.info("Header mappings saved")

    logger.info(
        "Summary | total=%s csv=%s html=%s pdf-table=%s pdf-image=%s missing=%s",
        stats["total"],
        stats["csv"],
        stats["html"],
        stats["pdf_table"],
        stats["pdf_image"],
        stats["missing"],
    )
    
    if headers_config.get("unknownHeaders"):
        logger.warning(f"Unknown headers: {len(headers_config['unknownHeaders'])}")
        for header in headers_config["unknownHeaders"]:
            logger.warning(f"  - {header}")
        logger.warning("Review and map them in column-headers.json")
    
    logger.info("Processing complete")


if __name__ == "__main__":
    main()
