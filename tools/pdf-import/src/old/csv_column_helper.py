#!/usr/bin/env python3
"""
Utility to help convert space-separated CSV files to tab-separated format.
This can be used as a pre-processing step for space-separated tables extracted from PDFs.
"""

from pathlib import Path
import sys


def suggest_column_conversion(csv_path: Path) -> None:
    """
    Analyze a space-separated CSV file and suggest column boundaries.
    """
    content = csv_path.read_text(encoding='utf-8')
    lines = content.split('\n')
    
    if not lines:
        print("Empty file")
        return
    
    header_line = lines[0]
    print(f"File: {csv_path.name}")
    print(f"Header: {header_line}")
    print(f"\nHeader words ({len(header_line.split())} words):")
    
    for i, word in enumerate(header_line.split()):
        print(f"  [{i}] {word}")
    
    print("\n" + "="*70)
    print("RECOMMENDATIONS:")
    print("="*70)
    
    # Check what kind of file this is
    if '\t' in header_line:
        print("✓ File is already tab-separated - parsing should work well!")
    elif ',' in header_line:
        print("✓ File is comma-separated - parsing should work well!")
    else:
        print("✗ File is space-separated (problematic for multi-word columns)")
        print("\nSuggested solutions:")
        print("  1. Copy-paste the table from PDF with explicit tab separation")
        print("  2. Use the convert_to_tab_separated() function below")
        print("  3. Manually edit the file to replace space separators with tabs")
        
        # Show an example conversion
        if len(lines) > 0:
            print("\nExample of how to manually mark column boundaries:")
            print("  Original: Ref. Name BS / FS / RAL Mr. Hobby (GSI) Tamiya Vallejo")
            print("  Mark it:  Ref. Name BS / FS / RAL\tMr. Hobby (GSI)\tTamiya\tVallejo")
            print("            (use \\t or actual TAB characters for column separators)")


def interactive_column_mapper(csv_path: Path) -> None:
    """
    Interactive tool to help map columns in a space-separated file.
    Guides the user through identifying column boundaries.
    """
    content = csv_path.read_text(encoding='utf-8')
    lines = content.split('\n')
    
    if not lines:
        print("Empty file")
        return
    
    print(f"\n{'='*70}")
    print("INTERACTIVE COLUMN MAPPER")
    print(f"{'='*70}")
    print(f"File: {csv_path.name}")
    print(f"\nHeader line:")
    print(lines[0])
    print(f"\nFirst few data rows:")
    for i in range(1, min(6, len(lines))):
        print(f"  {lines[i][:80]}")
    
    print("\n" + "="*70)
    print("ANALYSIS TIPS:")
    print("="*70)
    print("""
For space-separated tables, look for these clues to identify columns:

1. KNOWN KEYWORDS - These are paint brand/standard abbreviations:
   - Brand names: Tamiya, Vallejo, Humbrol, Model Master, Hataka, Lifecolor, etc.
   - Standards: RAL, RLM, FS, ANA, BS, etc.
   - These usually mark column boundaries.

2. DATA PATTERNS - Look at data rows to see:
   - Color codes (like: XF-1, 71.057, RC001, 4301AP)
   - Color names (usually multi-word strings)
   - Numbers that align across rows

3. CONSISTENCY - Verify column count:
   - Count columns in header row
   - Count "columns" in a few data rows
   - They should match!

EXAMPLE - From AK_Conversion.csv:
  Header: Ref. Name BS / FS / RAL Mr. Hobby (GSI) Tamiya Vallejo Hataka...
  
  Actual columns should be:
  [0] Ref. Name BS / FS / RAL
  [1] Mr. Hobby (GSI)
  [2] Tamiya
  [3] Vallejo
  [4] Hataka
  [5] Humbrol
  [6] Model Master
  [7] Lifecolor

BEST PRACTICE:
  When copy-pasting from PDF, try to:
  - Use "Copy table as tab-separated" if available
  - Or paste into a spreadsheet and export as TSV
  - Then convert TSV to CSV if needed
""")


def convert_to_tab_separated(
    input_path: Path,
    output_path: Path,
    column_positions: list[int] | None = None,
) -> None:
    """
    Convert a space-separated file to tab-separated.
    
    Args:
        input_path: Path to space-separated CSV
        output_path: Path to write tab-separated CSV
        column_positions: Optional list of word positions where columns start
                         Used to intelligently split space-separated lines
    """
    content = input_path.read_text(encoding='utf-8')
    lines = content.split('\n')
    
    output_lines = []
    
    for line in lines:
        if not line.strip():
            continue
        
        if column_positions:
            # Split using specified positions
            parts = []
            words = line.split()
            for i in range(len(column_positions)):
                start = column_positions[i]
                end = column_positions[i + 1] if i + 1 < len(column_positions) else len(words)
                parts.append(' '.join(words[start:end]))
            output_lines.append('\t'.join(parts))
        else:
            # Simple approach: replace multiple spaces with tabs
            converted = ' '.join(line.split())  # Normalize whitespace
            output_lines.append(converted)
    
    output_path.write_text('\n'.join(output_lines), encoding='utf-8')
    print(f"Converted file written to: {output_path}")


def main() -> None:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python csv_column_helper.py <csv_file> [options]")
        print("\nOptions:")
        print("  analyze   - Analyze column structure and suggest improvements")
        print("  interactive - Interactive mode to identify columns")
        print("  convert <output_file> - Convert to tab-separated format")
        print("\nExamples:")
        print("  python csv_column_helper.py VMC_Conversion.csv analyze")
        print("  python csv_column_helper.py AK_Conversion.csv interactive")
        print("  python csv_column_helper.py AK_Conversion.csv convert AK_Conversion-fixed.csv")
        return
    
    csv_file = Path(sys.argv[1])
    
    if not csv_file.exists():
        print(f"File not found: {csv_file}")
        return
    
    if len(sys.argv) < 3 or sys.argv[2] == 'analyze':
        suggest_column_conversion(csv_file)
    elif sys.argv[2] == 'interactive':
        interactive_column_mapper(csv_file)
    elif sys.argv[2] == 'convert':
        if len(sys.argv) < 4:
            print("Error: convert option requires output file path")
            return
        output_file = Path(sys.argv[3])
        convert_to_tab_separated(csv_file, output_file)
    else:
        print(f"Unknown option: {sys.argv[2]}")


if __name__ == "__main__":
    main()
