#!/usr/bin/env python3
"""
Main parsing script for paint line data sources.
Handles CSV (pass-through), PDF (table/image), and HTML parsing.
Updates column header mappings as new headers are encountered.
"""

import json
import os
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
        logger.warning(f"column-headers.json not found, creating new")
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
    logger.info(f"Saved column header mappings to {HEADERS_CONFIG}")


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
        logger.warning(f"Unknown column header: '{header}' - added to review list")
        return True
    
    return False


def process_paint_lines(sources, headers_config):
    """Process paint lines from sources.json."""
    paint_lines = sources.get("paintLines", [])
    
    logger.info(f"Found {len(paint_lines)} paint lines to process")
    
    for paint_line in paint_lines:
        key = paint_line.get("key")
        files = paint_line.get("files", [])
        
        logger.info(f"\nProcessing: {key}")
        
        for file_obj in files:
            filename = file_obj.get("name")
            file_format = file_obj.get("format", "csv")  # Default to csv if no format
            source_file = INPUT_DIR / filename
            
            if not source_file.exists():
                logger.warning(f"  ✗ File not found: {filename}")
                continue
            
            # If no format specified (defaults to csv), it's ready
            if file_format == "csv":
                logger.info(f"  ✓ CSV ready: {filename}")
            
            elif file_format == "html":
                logger.info(f"  Parsing HTML: {filename}")
                parse_html_file(source_file, key, file_obj, headers_config)
            
            elif file_format == "pdf-table":
                logger.info(f"  Parsing PDF (table): {filename}")
                pages = file_obj.get("pages")
                if pages:
                    logger.info(f"    Pages: {pages}")
                table_title = file_obj.get("tableTitle")
                if table_title:
                    logger.info(f"    Table title: {table_title}")
                parse_pdf_file(source_file, key, file_obj, headers_config, "table")
            
            elif file_format == "pdf-image":
                logger.info(f"  Parsing PDF (image/OCR): {filename}")
                pages = file_obj.get("pages")
                if pages:
                    logger.info(f"    Pages: {pages}")
                parse_pdf_file(source_file, key, file_obj, headers_config, "image")


def process_standards(sources, headers_config):
    """Process color standards from sources.json."""
    standards = sources.get("standards", [])
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Found {len(standards)} color standards to process")
    
    for standard in standards:
        key = standard.get("key")
        files = standard.get("files", [])
        
        logger.info(f"\nProcessing: {key}")
        
        for file_obj in files:
            filename = file_obj.get("name")
            file_format = file_obj.get("format", "csv")  # Default to csv if no format
            source_file = INPUT_DIR / filename
            
            if not source_file.exists():
                logger.warning(f"  ✗ File not found: {filename}")
                continue
            
            # If no format specified (defaults to csv), it's ready
            if file_format == "csv":
                logger.info(f"  ✓ CSV ready: {filename}")
            
            elif file_format == "html":
                logger.info(f"  Parsing HTML: {filename}")
                parse_html_file(source_file, key, file_obj, headers_config)
            
            elif file_format == "pdf-table":
                logger.info(f"  Parsing PDF (table): {filename}")
                pages = file_obj.get("pages")
                if pages:
                    logger.info(f"    Pages: {pages}")
                parse_pdf_file(source_file, key, file_obj, headers_config, "table")
            
            elif file_format == "pdf-image":
                logger.info(f"  Parsing PDF (image/OCR): {filename}")
                pages = file_obj.get("pages")
                if pages:
                    logger.info(f"    Pages: {pages}")
                parse_pdf_file(source_file, key, file_obj, headers_config, "image")


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
    logger.info(f"    [PDF {pdf_type} parsing stub] - Would parse: {filepath}")
    logger.info(f"    Output key: {key}")
    logger.info(f"    TODO: Implement PDF parsing with pdfplumber (tables) or Tesseract OCR (images)")


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
    logger.info(f"    [HTML parsing stub] - Would parse: {filepath}")
    logger.info(f"    Output key: {key}")
    logger.info(f"    TODO: Implement HTML table extraction with BeautifulSoup")


def main():
    """Main entry point."""
    logger.info("="*60)
    logger.info("Paint Line Parser - Sources Configuration Manager")
    logger.info("="*60)
    
    # Create output directory if needed
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load configurations
    logger.info(f"\nLoading configuration from {SOURCES_FILE}")
    sources = load_sources()
    
    logger.info(f"Loading column header mappings from {HEADERS_CONFIG}")
    headers_config = load_headers_config()
    
    # Process paint lines and standards
    process_paint_lines(sources, headers_config)
    process_standards(sources, headers_config)
    
    # Save updated configurations
    logger.info(f"\n{'='*60}")
    logger.info("Saving updated configurations...")
    save_headers_config(headers_config)
    
    if headers_config.get("unknownHeaders"):
        logger.warning(f"\nFound {len(headers_config['unknownHeaders'])} unknown column headers:")
        for header in headers_config["unknownHeaders"]:
            logger.warning(f"  - {header}")
        logger.warning(f"Please review and add mappings to column-headers.json")
    
    logger.info("\n" + "="*60)
    logger.info("Processing complete!")
    logger.info("="*60)


if __name__ == "__main__":
    main()
