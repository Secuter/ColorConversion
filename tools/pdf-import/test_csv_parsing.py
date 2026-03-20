#!/usr/bin/env python3
"""
Test script to verify the improved CSV parsing with the example files.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from extract_tables import (
    parse_csv_with_smart_delimiter,
    detect_delimiter,
    normalize_header,
    find_column_index,
)

def test_file(filepath: Path) -> None:
    """Test parsing a single CSV file."""
    print(f"\n{'='*70}")
    print(f"Testing: {filepath.name}")
    print(f"{'='*70}")
    
    content = filepath.read_text(encoding='utf-8')
    lines = content.split('\n')
    
    # Show first line for delimiter detection
    if lines:
        delimiter = detect_delimiter(lines[0])
        print(f"Detected delimiter: {repr(delimiter)}")
        print(f"First line (raw): {repr(lines[0][:100])}")
    
    # Parse the file
    headers, rows = parse_csv_with_smart_delimiter(content)
    
    print(f"\nColumns detected: {len(headers)}")
    print(f"Data rows: {len(rows)}")
    
    print(f"\nColumn headers:")
    for i, h in enumerate(headers):
        print(f"  [{i}] {h}")
    
    print(f"\nNormalized headers:")
    for i, h in enumerate(headers):
        normalized = normalize_header(h)
        print(f"  [{i}] {repr(h)} -> {repr(normalized)}")
    
    print(f"\nFirst 3 data rows:")
    for row_idx, row in enumerate(rows[:3], start=1):
        print(f"  Row {row_idx}: {row}")
    
    # Test column finding
    print(f"\nColumn finding tests:")
    code_col = find_column_index(headers, ["code", "id", "codice", "numero"])
    print(f"  Code/ID column: {code_col} -> {headers[code_col] if code_col >= 0 else 'NOT FOUND'}")
    
    name_col = find_column_index(headers, ["name", "nome", "color", "description"])
    print(f"  Name column: {name_col} -> {headers[name_col] if name_col >= 0 else 'NOT FOUND'}")

def main() -> None:
    """Test all example CSV files."""
    examples_dir = Path(__file__).parent / "examples"
    
    csv_files = sorted(examples_dir.glob("*.csv"))
    if not csv_files:
        print("No CSV files found in examples directory!")
        return
    
    for csv_file in csv_files:
        test_file(csv_file)
    
    print(f"\n{'='*70}")
    print("All tests completed!")
    print(f"{'='*70}")

if __name__ == "__main__":
    main()
