from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from io import StringIO

import pdfplumber


TABLE_TYPES = ("color_list", "conversion", "highlights_shadows", "color_order", "unknown")
KNOWN_LINE_WORDS = {
    "vallejo", "model color", "model air", "tamiya", "mr. color", "gunze", "ak", "real colors", "italeri"
}


@dataclass
class DetectedTable:
    pdf_name: str
    page: int
    table_index: int
    bbox: tuple[float, float, float, float] | None
    headers: list[str]
    rows: list[list[str]]
    table_type: str
    confidence: float


def clean_cell(value: Any) -> str:
    return str(value or "").replace("\n", " ").strip()


def normalize_rows(rows: list[list[Any]]) -> list[list[str]]:
    normalized: list[list[str]] = []
    for row in rows:
        cleaned = [clean_cell(cell) for cell in row]
        if any(cell for cell in cleaned):
            normalized.append(cleaned)
    return normalized


def detect_delimiter(line: str) -> str:
    """
    Detect the delimiter used in a CSV line.
    Returns tab if tabs are present, comma if commas are present (and no tabs),
    otherwise returns space as default.
    """
    if '\t' in line:
        return '\t'
    if ',' in line:
        return ','
    return ' '


def parse_csv_with_smart_delimiter(content: str) -> tuple[list[str], list[list[str]]]:
    """
    Parse CSV content with automatic delimiter detection.
    Handles tab-separated, comma-separated, and space-separated files.
    For space-separated files, attempts to intelligently identify column boundaries.
    
    Returns:
        (headers, rows) where headers and rows have empty columns removed
    """
    lines = content.strip().split('\n')
    if not lines:
        return [], []
    
    # Detect delimiter from first line
    delimiter = detect_delimiter(lines[0])
    
    # Parse using CSV reader for tab/comma, manual parsing for space
    if delimiter in ('\t', ','):
        # Use standard CSV reader
        reader = csv.reader(StringIO(content), delimiter=delimiter)
        parsed_lines = list(reader)
    else:
        # For space-separated files, try to identify column boundaries
        # First, try to find columns using known paint line brand keywords
        parsed_lines = _parse_space_separated(lines)
    
    if not parsed_lines:
        return [], []
    
    # Find the column count from the non-empty longest row
    max_cols = max((len(row) for row in parsed_lines), default=0)
    
    # Normalize all rows to have the same number of columns
    normalized: list[list[str]] = []
    for row in parsed_lines:
        cleaned = [clean_cell(cell).strip() for cell in row]
        # Pad with empty strings if needed
        while len(cleaned) < max_cols:
            cleaned.append('')
        # Truncate if too many columns
        cleaned = cleaned[:max_cols]
        normalized.append(cleaned)
    
    if not normalized:
        return [], []
    
    headers = normalized[0]
    data_rows = normalized[1:] if len(normalized) > 1 else []
    
    # Remove completely empty columns
    non_empty_cols = []
    for col_idx in range(len(headers)):
        has_content = headers[col_idx].strip() != ''
        if not has_content:
            has_content = any(row[col_idx].strip() != '' for row in data_rows if col_idx < len(row))
        if has_content:
            non_empty_cols.append(col_idx)
    
    # Filter to keep only non-empty columns
    filtered_headers = [headers[i] for i in non_empty_cols if i < len(headers)]
    filtered_rows = [[row[i] if i < len(row) else '' for i in non_empty_cols] for row in data_rows]
    
    return filtered_headers, filtered_rows


def _parse_space_separated(lines: list[str]) -> list[list[str]]:
    """
    Parse space-separated CSV data, using paint line keywords and heuristics
    to identify column boundaries.
    """
    if not lines:
        return []
    
    # Paint brand keywords that should indicate column boundaries
    brand_keywords = {
        "mr.color", "mr color", "tamiya", "vallejo", "model color", "model air",
        "ak", "real colors", "italeri", "humbrol", "model master", "lifecolor",
        "gunze", "revell", "testor", "hataka", "ral", "rlm", "fs", "ana", "bs"
    }
    
    header_line = lines[0].lower()
    
    # Try to identify column boundaries by finding brand keywords
    header_words = lines[0].split()
    
    # Build a hypothesis of column boundaries
    col_positions = [0]  # Start of first column
    current_phrase = []
    
    for i, word in enumerate(header_words):
        current_phrase.append(word)
        phrase_lower = ' '.join(current_phrase).lower()
        
        # Check if current phrase matches a brand keyword
        for keyword in brand_keywords:
            if phrase_lower == keyword or phrase_lower.endswith(keyword):
                # Found a potential boundary
                col_positions.append(i + 1)
                current_phrase = []
                break
    
    # If we found at least 2 columns, use this heuristic
    if len(col_positions) > 1:
        col_positions.append(len(header_words))
        return _split_lines_by_positions(lines, col_positions, header_words)
    
    # Fallback: split on multiple consecutive spaces
    parsed_lines = []
    for line in lines:
        # Try to identify multi-space boundaries
        if '  ' in line:  # Multiple spaces
            parts = re.split(r'\s{2,}', line.rstrip())
        else:
            # Single space separated - try position-based split using data patterns
            parts = line.split()
        parsed_lines.append(parts)
    
    return parsed_lines


def _split_lines_by_positions(
    lines: list[str], col_positions: list[int], header_words: list[str]
) -> list[list[str]]:
    """
    Split lines based on identified column positions.
    """
    parsed_lines = []
    
    # For header, use the identified positions
    header_columns = []
    for i in range(len(col_positions) - 1):
        start = col_positions[i]
        end = col_positions[i + 1]
        col_words = header_words[start:end]
        header_columns.append(' '.join(col_words))
    parsed_lines.append(header_columns)
    
    # For data rows, try to align with detected column count
    num_cols = len(col_positions) - 1
    for line in lines[1:]:
        words = line.split()
        if len(words) == num_cols:
            parsed_lines.append(words)
        else:
            # Try to intelligently group words into columns
            # This is a simplified heuristic
            row_parts = []
            words_per_col = len(words) / num_cols if num_cols > 0 else 1
            
            if words_per_col > 1.5:
                # Multiple words per column likely
                col_sizes = []
                remaining = len(words)
                for col_idx in range(num_cols):
                    if col_idx == num_cols - 1:
                        size = remaining
                    else:
                        size = max(1, round((len(words) // num_cols)))
                    col_sizes.append(size)
                    remaining -= size
                
                pos = 0
                for size in col_sizes:
                    end = min(pos + size, len(words))
                    row_parts.append(' '.join(words[pos:end]))
                    pos = end
            else:
                # Simple split when word count matches column count roughly
                row_parts = words
            
            if row_parts:
                # Pad or truncate to match column count
                while len(row_parts) < num_cols:
                    row_parts.append('')
                row_parts = row_parts[:num_cols]
                parsed_lines.append(row_parts)
    
    return parsed_lines


def load_csv_file(csv_path: Path) -> tuple[list[str], list[list[str]]]:
    """
    Load a CSV file and parse it with smart delimiter detection.
    
    Returns:
        (headers, rows) tuple
    """
    content = csv_path.read_text(encoding='utf-8')
    return parse_csv_with_smart_delimiter(content)


def normalize_header(header: str) -> str:
    """
    Normalize a column header by removing extra whitespace, lowercasing,
    and handling common patterns.
    """
    # Remove extra whitespace and convert to lowercase
    normalized = re.sub(r'\s+', ' ', header.strip().lower())
    # Remove common punctuation that might appear in headers
    normalized = re.sub(r'[()./\-_]+', ' ', normalized)
    # Clean up whitespace again
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized


def find_column_index(headers: list[str], keywords: list[str] | str, strict: bool = False) -> int:
    """
    Find the index of a column by matching against keywords.
    
    Args:
        headers: List of column headers
        keywords: String or list of strings to match in column header
        strict: If True, require an exact match; if False, allow partial matches
    
    Returns:
        Column index if found, -1 otherwise
    """
    if isinstance(keywords, str):
        keywords = [keywords]
    
    headers_normalized = [normalize_header(h) for h in headers]
    
    for i, header_norm in enumerate(headers_normalized):
        for keyword in keywords:
            keyword_norm = normalize_header(keyword)
            if strict:
                if header_norm == keyword_norm:
                    return i
            else:
                if keyword_norm in header_norm or header_norm in keyword_norm:
                    return i
    
    return -1


def likely_code(token: str) -> bool:
    return bool(re.match(r"^[A-Z]{0,4}[-.]?\d{1,4}(?:\.\d{1,3})?$", token.strip().upper()))


def extract_rgb(text: str) -> str | None:
    text = text.strip()
    hex_match = re.search(r"#([0-9A-Fa-f]{6})\b", text)
    if hex_match:
        return f"#{hex_match.group(1).upper()}"

    rgb_match = re.search(r"\b(\d{1,3})\s*[,/\-]\s*(\d{1,3})\s*[,/\-]\s*(\d{1,3})\b", text)
    if rgb_match:
        r, g, b = [max(0, min(255, int(v))) for v in rgb_match.groups()]
        return f"#{r:02X}{g:02X}{b:02X}"

    return None


def classify_table(headers: list[str], rows: list[list[str]]) -> tuple[str, float]:
    header_text = " ".join(headers).lower()
    row_text = " ".join(" ".join(r) for r in rows[:8]).lower()

    if any(k in header_text or k in row_text for k in ("highlight", "highlights", "shadow", "shadows")):
        return "highlights_shadows", 0.95

    if any(k in header_text for k in ("position", "order", "rank", "index")):
        return "color_order", 0.9

    line_header_hits = sum(1 for h in headers if any(word in h.lower() for word in KNOWN_LINE_WORDS))
    if line_header_hits >= 2:
        return "conversion", 0.9

    code_like_count = sum(1 for row in rows[:10] for cell in row if likely_code(cell))
    if len(headers) >= 2 and code_like_count >= max(2, len(rows[:10])):
        if any(k in header_text for k in ("conversion", "equivalent", "equivalence", "correspond")):
            return "conversion", 0.8
        return "color_list", 0.75

    if len(headers) >= 2 and any(k in header_text for k in ("code", "id", "name", "color")):
        return "color_list", 0.7

    return "unknown", 0.2


def find_profile(pdf_name: str, profiles: dict[str, Any]) -> dict[str, Any]:
    defaults = profiles.get("defaults", {})
    for profile in profiles.get("profiles", []):
        if profile.get("match", "").lower() in pdf_name.lower():
            merged = dict(defaults)
            merged.update(profile)
            return merged
    return defaults


def detect_tables(pdf_path: Path, profile: dict[str, Any]) -> list[DetectedTable]:
    include_pages = set(profile.get("include_pages", []) or [])
    exclude_pages = set(profile.get("exclude_pages", []) or [])
    forced = {
        (item.get("page"), item.get("table_index")): item.get("type")
        for item in profile.get("force_table_types", [])
    }

    detected: list[DetectedTable] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            if include_pages and page_num not in include_pages:
                continue
            if page_num in exclude_pages:
                continue

            table_settings_list = [
                {"vertical_strategy": "lines", "horizontal_strategy": "lines"},
                {"vertical_strategy": "text", "horizontal_strategy": "lines"},
                {"vertical_strategy": "lines", "horizontal_strategy": "text"},
            ]

            seen_bboxes: set[tuple[int, int, int, int]] = set()
            table_count = 0

            for settings in table_settings_list:
                for tbl in page.find_tables(table_settings=settings):
                    bbox = tuple(int(round(v)) for v in tbl.bbox) if tbl.bbox else None
                    if bbox and bbox in seen_bboxes:
                        continue
                    if bbox:
                        seen_bboxes.add(bbox)

                    rows = normalize_rows(tbl.extract() or [])
                    if len(rows) < 2:
                        continue

                    table_count += 1
                    headers = rows[0]
                    body = rows[1:]

                    forced_type = forced.get((page_num, table_count))
                    if forced_type in TABLE_TYPES:
                        table_type, confidence = forced_type, 1.0
                    else:
                        table_type, confidence = classify_table(headers, body)

                    detected.append(
                        DetectedTable(
                            pdf_name=pdf_path.name,
                            page=page_num,
                            table_index=table_count,
                            bbox=tbl.bbox,
                            headers=headers,
                            rows=body,
                            table_type=table_type,
                            confidence=confidence,
                        )
                    )

    return detected


def parse_color_list(t: DetectedTable) -> list[dict[str, Any]]:
    headers_l = [h.lower() for h in t.headers]
    code_col = next((i for i, h in enumerate(headers_l) if "code" in h or h == "id"), 0)
    name_col = next((i for i, h in enumerate(headers_l) if "name" in h), 1 if len(headers_l) > 1 else 0)
    rgb_col = next((i for i, h in enumerate(headers_l) if "rgb" in h or "hex" in h), -1)

    # Fallback to smart column detection if standard search doesn't find columns
    if code_col == 0 and len(t.headers) > 0 and "code" not in headers_l[0] and "id" != headers_l[0]:
        code_col = find_column_index(t.headers, ["code", "id", "codice", "numero"])
        if code_col == -1:
            code_col = 0
    
    if name_col == 1 and len(t.headers) > 1 and "name" not in headers_l[1]:
        name_col = find_column_index(t.headers, ["name", "nome", "color", "description"])
        if name_col == -1:
            name_col = 1 if len(t.headers) > 1 else 0

    out: list[dict[str, Any]] = []
    for ridx, row in enumerate(t.rows, start=1):
        if max(code_col, name_col) >= len(row):
            continue
        color_id = row[code_col].strip()
        color_name = row[name_col].strip()
        if not color_id or not likely_code(color_id):
            continue

        rgb = None
        if rgb_col >= 0 and rgb_col < len(row):
            rgb = extract_rgb(row[rgb_col])
        if not rgb:
            rgb = extract_rgb(" ".join(row))

        out.append(
            {
                "pdf": t.pdf_name,
                "page": t.page,
                "color_id": color_id,
                "name": color_name,
                "rgb": rgb,
                "row_index": ridx,
            }
        )
    return out


def parse_conversions(t: DetectedTable) -> list[dict[str, Any]]:
    # Normalize and handle empty column headers
    headers = []
    for i, h in enumerate(t.headers):
        normalized = (h.strip() or f"col_{i+1}").strip()
        if normalized != f"col_{i+1}" or any(row[i].strip() for row in t.rows[:10] if i < len(row)):
            headers.append(normalized)
        else:
            headers.append(f"col_{i+1}")
    
    out: list[dict[str, Any]] = []
    for ridx, row in enumerate(t.rows, start=1):
        entries = []
        for i, cell in enumerate(row):
            if not cell.strip():
                continue
            if i < len(headers):
                header = headers[i]
                # Check if this looks like a color code or if header mentions a known paint line
                if likely_code(cell) or any(w in header.lower() for w in KNOWN_LINE_WORDS):
                    entries.append({"color_line": header, "color_code": cell.strip()})
        if len(entries) >= 2:
            out.append(
                {
                    "pdf": t.pdf_name,
                    "page": t.page,
                    "row_index": ridx,
                    "entries": entries,
                }
            )
    return out


def parse_highlights_shadows(t: DetectedTable) -> list[dict[str, Any]]:
    headers_l = [h.lower() for h in t.headers]
    src_col = next((i for i, h in enumerate(headers_l) if "source" in h or "base" in h), 0)
    hi_col = next((i for i, h in enumerate(headers_l) if "highlight" in h), 1 if len(headers_l) > 1 else 0)
    sh_col = next((i for i, h in enumerate(headers_l) if "shadow" in h), 2 if len(headers_l) > 2 else 0)

    # Fallback to smart column detection
    if src_col == 0 and "source" not in headers_l[0] and "base" not in headers_l[0]:
        src_col = find_column_index(t.headers, ["source", "base", "source color"])
        if src_col == -1:
            src_col = 0
    
    if hi_col == 1 and len(headers_l) > 1 and "highlight" not in headers_l[1]:
        hi_col = find_column_index(t.headers, ["highlight", "highlights"])
        if hi_col == -1:
            hi_col = 1 if len(t.headers) > 1 else 0
    
    if sh_col == 2 and len(headers_l) > 2 and "shadow" not in headers_l[2]:
        sh_col = find_column_index(t.headers, ["shadow", "shadows"])
        if sh_col == -1:
            sh_col = 2 if len(t.headers) > 2 else 0

    out: list[dict[str, Any]] = []
    for ridx, row in enumerate(t.rows, start=1):
        if max(src_col, hi_col, sh_col) >= len(row):
            continue
        source = row[src_col].strip()
        highlight = row[hi_col].strip()
        shadow = row[sh_col].strip()
        if source and (highlight or shadow):
            out.append(
                {
                    "pdf": t.pdf_name,
                    "page": t.page,
                    "row_index": ridx,
                    "source_color": source,
                    "highlight_color": highlight,
                    "shadow_color": shadow,
                }
            )
    return out


def parse_color_order(t: DetectedTable) -> list[dict[str, Any]]:
    headers_l = [h.lower() for h in t.headers]
    id_col = next((i for i, h in enumerate(headers_l) if "code" in h or h == "id"), 0)
    pos_col = next((i for i, h in enumerate(headers_l) if "position" in h or "order" in h or "rank" in h), 1 if len(headers_l) > 1 else 0)

    # Fallback to smart column detection
    if id_col == 0 and "code" not in headers_l[0] and "id" != headers_l[0]:
        id_col = find_column_index(t.headers, ["code", "id", "codice", "numero"])
        if id_col == -1:
            id_col = 0
    
    if pos_col == 1 and len(headers_l) > 1 and "position" not in headers_l[1] and "order" not in headers_l[1]:
        pos_col = find_column_index(t.headers, ["position", "order", "rank", "index"])
        if pos_col == -1:
            pos_col = 1 if len(t.headers) > 1 else 0

    out: list[dict[str, Any]] = []
    for ridx, row in enumerate(t.rows, start=1):
        if max(id_col, pos_col) >= len(row):
            continue
        color_id = row[id_col].strip()
        position = row[pos_col].strip()
        if color_id and position:
            out.append(
                {
                    "pdf": t.pdf_name,
                    "page": t.page,
                    "row_index": ridx,
                    "color_id": color_id,
                    "position": position,
                }
            )
    return out


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    keys = sorted({k for r in rows for k in r.keys()})
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def flatten_conversions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        base = {k: row[k] for k in ("pdf", "page", "row_index")}
        for idx, entry in enumerate(row.get("entries", []), start=1):
            out.append({**base, "entry_index": idx, "color_line": entry.get("color_line"), "color_code": entry.get("color_code")})
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract and classify paint tables from PDFs.")
    parser.add_argument("--input-dir", default="../input", help="Directory containing PDF files")
    parser.add_argument("--output-dir", default="../output", help="Directory to write outputs")
    parser.add_argument("--profiles", default="../mappings/profiles.json", help="Profiles JSON path")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    input_dir = (script_dir / args.input_dir).resolve()
    output_dir = (script_dir / args.output_dir).resolve()
    profiles_path = (script_dir / args.profiles).resolve()

    profiles = json.loads(profiles_path.read_text(encoding="utf-8")) if profiles_path.exists() else {"defaults": {}, "profiles": []}

    all_color_list: list[dict[str, Any]] = []
    all_conversions: list[dict[str, Any]] = []
    all_highlights: list[dict[str, Any]] = []
    all_order: list[dict[str, Any]] = []
    all_detected_tables: list[dict[str, Any]] = []

    for pdf_path in sorted(input_dir.glob("*.pdf")):
        profile = find_profile(pdf_path.name, profiles)
        tables = detect_tables(pdf_path, profile)

        pdf_color_list: list[dict[str, Any]] = []
        pdf_conversions: list[dict[str, Any]] = []
        pdf_highlights: list[dict[str, Any]] = []
        pdf_order: list[dict[str, Any]] = []

        for t in tables:
            all_detected_tables.append(
                {
                    "pdf": t.pdf_name,
                    "page": t.page,
                    "table_index": t.table_index,
                    "bbox": t.bbox,
                    "headers": t.headers,
                    "table_type": t.table_type,
                    "confidence": t.confidence,
                    "rows_detected": len(t.rows),
                }
            )

            if t.table_type == "color_list":
                pdf_color_list.extend(parse_color_list(t))
            elif t.table_type == "conversion":
                pdf_conversions.extend(parse_conversions(t))
            elif t.table_type == "highlights_shadows":
                pdf_highlights.extend(parse_highlights_shadows(t))
            elif t.table_type == "color_order":
                pdf_order.extend(parse_color_order(t))

        write_json(output_dir / "per_pdf" / f"{pdf_path.stem}.json", {
            "pdf": pdf_path.name,
            "color_list": pdf_color_list,
            "conversions": pdf_conversions,
            "highlights_shadows": pdf_highlights,
            "color_order": pdf_order,
            "detected_tables": [d for d in all_detected_tables if d["pdf"] == pdf_path.name],
        })

        all_color_list.extend(pdf_color_list)
        all_conversions.extend(pdf_conversions)
        all_highlights.extend(pdf_highlights)
        all_order.extend(pdf_order)

    write_json(output_dir / "detected_tables.json", all_detected_tables)

    write_json(output_dir / "color_list.json", all_color_list)
    write_csv(output_dir / "color_list.csv", all_color_list)

    write_json(output_dir / "conversions.json", all_conversions)
    write_csv(output_dir / "conversions.csv", flatten_conversions(all_conversions))

    write_json(output_dir / "highlights_shadows.json", all_highlights)
    write_csv(output_dir / "highlights_shadows.csv", all_highlights)

    write_json(output_dir / "color_order.json", all_order)
    write_csv(output_dir / "color_order.csv", all_order)

    print(f"Done. Processed PDFs in: {input_dir}")
    print(f"Outputs written to: {output_dir}")


if __name__ == "__main__":
    main()
