"""
build_json.py
Reads the example CSV files (manually corrected from PDF copy-paste) and
produces the canonical JSON paint-series files consumed by the Vue website.

Outputs:
  src/data/vallejo-model-color.json
  src/data/vallejo-model-air.json
  src/data/ak-real-colors.json
  src/data/italeri.json

Tamiya and Mr. Color JSONs are NOT touched.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from pathlib import Path
from functools import lru_cache
from typing import Any

try:
    import easyocr
    HAS_EASYOCR = True
except ImportError:
    HAS_EASYOCR = False

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR   = Path(__file__).resolve().parent
EXAMPLES_DIR = SCRIPT_DIR.parent / "examples"
INPUT_DIR    = SCRIPT_DIR.parent / "input"
OUTPUT_DIR   = SCRIPT_DIR.parent.parent.parent / "src" / "data"
PAINT_LINES_PATH = OUTPUT_DIR / "paint-lines.json"
MAPPINGS_DIR = SCRIPT_DIR.parent / "mappings"
PIPELINE_OUTPUT_DIR = SCRIPT_DIR.parent / "output"
NORMALIZED_DIR = PIPELINE_OUTPUT_DIR / "normalized"
SOURCE_RESOLUTION_PATH = MAPPINGS_DIR / "source_resolution.json"
PIPELINE_SOURCES_CONFIG_PATH = MAPPINGS_DIR / "sources.config.json"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
MAPPINGS_DIR.mkdir(parents=True, exist_ok=True)
NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)


DEFAULT_PIPELINE_SOURCES: list[dict[str, Any]] = [
    {
        "line_id": "ak-acrylic",
        "sources": [{"file": "AK Acrylics Conversion.csv", "type": "csv"}],
    },
    {
        "line_id": "ak-real-colors",
        "sources": [{"file": "AK Real Colors Conversion.csv", "type": "csv"}],
    },
    {
        "line_id": "ammo-mig",
        "sources": [{"file": "Ammo Mig.pdf", "type": "pdf-image"}],
    },
    {
        "line_id": "ammo-mig-atom",
        "sources": [{"file": "Atom Ammo Mig.pdf", "type": "pdf-table"}],
    },
    {
        "line_id": "federal-standard",
        "sources": [{"file": "Federal Standard.csv", "type": "csv"}],
    },
    {
        "line_id": "humbrol-enamel",
        "sources": [{"file": "Humbrol.csv", "type": "csv"}],
    },
    {
        "line_id": "italeri-acrylic",
        "sources": [
            {"file": "Italeri Conversion.csv", "type": "csv"},
            {"file": "Italeri.csv", "type": "csv"},
        ],
    },
    {
        "line_id": "vallejo-model-air",
        "sources": [
            {"file": "Model Air.pdf", "type": "pdf-table"},
            {"file": "Vallejo Model Air.pdf", "type": "pdf-table"},
        ],
    },
    {
        "line_id": "mr-color-aqueous",
        "sources": [
            {"file": "MrColor Aqueous Conversion.csv", "type": "csv"},
            {"file": "MrColor Aqueous.csv", "type": "csv"},
        ],
    },
    {
        "line_id": "mr-color",
        "sources": [{"file": "MrColor Laquer Conversion.html", "type": "html-table"}],
    },
    {
        "line_id": "revell-acrylic",
        "sources": [
            {"file": "Revell Conversion.csv", "type": "csv"},
            {"file": "Revell.csv", "type": "csv"},
        ],
    },
    {
        "line_id": "revell-enamel",
        "sources": [
            {"file": "Revell Conversion.csv", "type": "csv"},
            {"file": "Revell.csv", "type": "csv"},
        ],
    },
    {
        "line_id": "tamiya-acrylic",
        "sources": [
            {"file": "Tamiya Conversion.html", "type": "html-table"},
            {"file": "Tamiya.csv", "type": "csv"},
        ],
    },
    {
        "line_id": "vallejo-model-color",
        "sources": [{"file": "Vallejo Model Color Conversion.csv", "type": "csv"}],
    },
]


def _load_pipeline_sources() -> list[dict[str, Any]]:
    if not PIPELINE_SOURCES_CONFIG_PATH.exists():
        return DEFAULT_PIPELINE_SOURCES

    try:
        payload = json.loads(PIPELINE_SOURCES_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return DEFAULT_PIPELINE_SOURCES

    lines = payload.get("lines", []) if isinstance(payload, dict) else []
    if not isinstance(lines, list):
        return DEFAULT_PIPELINE_SOURCES

    valid_lines: list[dict[str, Any]] = []
    for line in lines:
        if not isinstance(line, dict):
            continue
        line_id = line.get("line_id")
        sources = line.get("sources")
        if not isinstance(line_id, str) or not line_id.strip() or not isinstance(sources, list):
            continue

        valid_sources: list[dict[str, str]] = []
        for source in sources:
            if not isinstance(source, dict):
                continue
            source_file = source.get("file")
            source_type = source.get("type")
            if not isinstance(source_file, str) or not source_file.strip():
                continue
            if not isinstance(source_type, str) or not source_type.strip():
                continue
            valid_sources.append({"file": source_file, "type": source_type})

        if valid_sources:
            valid_lines.append({"line_id": line_id, "sources": valid_sources})

    return valid_lines or DEFAULT_PIPELINE_SOURCES


PIPELINE_SOURCES: list[dict[str, Any]] = _load_pipeline_sources()

OUTPUT_FILENAME_OVERRIDES: dict[str, str] = {
    "italeri-acrylic": "italeri.json",
}

LEGACY_FILE_ALIASES: dict[str, list[str]] = {
    "VMC_Colors.csv": ["Vallejo Model Colors.csv"],
    "VMC_Conversion.csv": ["Vallejo Model Color Conversion.csv"],
    "VMA_Colors.csv": ["Vallejo Model AirColors.csv"],
    "AK_Conversion.csv": ["AK Real Colors Conversion.csv"],
    "Italeri_Colors.csv": ["Italeri Colors.csv", "Italeri.csv"],
    "Italeri_Conversion.csv": ["Italeri Conversion.csv"],
}


# ---------------------------------------------------------------------------
# Generic CSV helpers
# ---------------------------------------------------------------------------

def _read_tsv(filename: str) -> list[list[str]]:
    """Read a CSV/TSV file from examples/ or input/ with legacy alias fallback."""
    candidates = [EXAMPLES_DIR / filename, INPUT_DIR / filename]
    for alias in LEGACY_FILE_ALIASES.get(filename, []):
        candidates.append(INPUT_DIR / alias)

    path = next((p for p in candidates if p.exists()), candidates[0])
    rows: list[list[str]] = []
    text = ""
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            text = path.read_text(encoding=encoding)
            break
        except UnicodeDecodeError:
            continue
    if not text:
        text = path.read_text(encoding="utf-8", errors="replace")

    sample = text[:8192]
    delimiter = "\t"
    if "," in sample and sample.count(",") > sample.count("\t"):
        delimiter = ","

    reader = csv.reader(text.splitlines(), delimiter=delimiter)
    for row in reader:
        rows.append([c.strip() for c in row])
    return rows


def _nonempty(rows: list[list[str]]) -> list[list[str]]:
    """Drop rows that are entirely blank."""
    return [r for r in rows if any(c for c in r)]


def _read_tsv_with_header(filename: str) -> tuple[list[str], list[list[str]]]:
    rows = _nonempty(_read_tsv(filename))
    if not rows:
        return [], []
    return rows[0], rows[1:]


def _read_tsv_no_header(filename: str) -> list[list[str]]:
    return _nonempty(_read_tsv(filename))


def _slug(name: str) -> str:
    base = name.lower().strip()
    base = re.sub(r"\.[^.]+$", "", base)
    base = re.sub(r"[^a-z0-9]+", "-", base)
    return base.strip("-")


def _normalize_delimited_file(path: Path) -> list[list[str]]:
    rows: list[list[str]] = []
    text = ""
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            text = path.read_text(encoding=encoding)
            break
        except UnicodeDecodeError:
            continue

    if not text:
        text = path.read_text(encoding="utf-8", errors="replace")

    sample = text[:8192]
    delimiter = "\t"
    delimiter_counts = {
        "\t": sample.count("\t"),
        ",": sample.count(","),
        ";": sample.count(";"),
        "|": sample.count("|"),
    }
    best_delimiter = max(delimiter_counts, key=delimiter_counts.get)
    if delimiter_counts[best_delimiter] > 0:
        delimiter = best_delimiter

    reader = csv.reader(text.splitlines(), delimiter=delimiter)
    for row in reader:
        cleaned = [c.strip() for c in row]
        if any(cleaned):
            rows.append(cleaned)
    return rows


def _parse_html_conversion_table(path: Path) -> list[list[str]]:
    """
    Parse conversion HTML files with row blocks like:
      <!-- mrh001 include --> ... 12 div cells ... <!-- end mrh001 include -->
    Returns raw 12-column rows.
    """
    html = path.read_text(encoding="utf-8", errors="replace")

    # All row blocks between include/end markers
    block_pattern = re.compile(
        r"<!--\s*(mr[a-z]\d+)\s+include\s*-->(.*?)<!--\s*end\s*\1\s+include\s*-->",
        re.I | re.S,
    )
    div_pattern = re.compile(r"<div[^>]*>(.*?)</div>", re.I | re.S)

    rows: list[list[str]] = []
    for _, block in block_pattern.findall(html):
        cells: list[str] = []
        for raw in div_pattern.findall(block):
            text = re.sub(r"<br\s*/?>", " / ", raw, flags=re.I)
            text = re.sub(r"<[^>]+>", "", text)
            text = text.replace("&nbsp;", "").strip()
            cells.append(text)
        if len(cells) >= 2 and any(cells):
            rows.append(cells)
    return rows


def _write_normalized_csv(target: Path, rows: list[list[str]]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        for row in rows:
            writer.writerow(row)


def _extract_pdf_with_ocr(pdf_path: Path) -> list[list[str]]:
    """
    Extract text from a PDF using OCR (easyocr).
    Attempts to parse the OCR output into table rows.
    
    Returns a list of rows (each row is a list of strings).
    """
    if not HAS_EASYOCR:
        return []
    
    try:
        import pdfplumber as pdf_lib
        import numpy as np
        if not HAS_PDFPLUMBER:
            return []
    except ImportError:
        return []
    
    rows: list[list[str]] = []
    
    try:
        # Initialize OCR reader (English only for performance)
        reader = easyocr.Reader(['en'], gpu=False)
        
        with pdf_lib.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                print(f"  OCR: Processing page {page_num + 1}/{len(pdf.pages)}...")
                
                # Get page image as numpy array
                pil_image = page.to_image(resolution=150).original
                image_array = np.array(pil_image)
                
                # Run OCR
                results = reader.readtext(image_array)
                
                # Parse OCR results into rows
                # Results are in format: [[bbox], text, confidence]
                # Group by y-coordinate to form rows
                if results:
                    text_blocks: list[tuple[float, str]] = []
                    for (bbox, text, confidence) in results:
                        if confidence > 0.4:  # Filter low-confidence results
                            # Get y-coordinate of center of text
                            y_coords = [b[1] for b in bbox]
                            y_center = (min(y_coords) + max(y_coords)) / 2
                            text_blocks.append((y_center, text.strip()))
                    
                    if text_blocks:
                        # Sort by y-coordinate
                        text_blocks.sort()
                        
                        # Group by row (similar y-coordinates)
                        current_row: list[str] = []
                        last_y = -1
                        row_threshold = 20  # pixels
                        
                        for y, text in text_blocks:
                            if last_y >= 0 and (y - last_y) > row_threshold:
                                # New row
                                if current_row and any(current_row):
                                    rows.append(current_row)
                                current_row = [text]
                            else:
                                # Same row, add to current
                                current_row.append(text)
                            last_y = y
                        
                        # Don't forget the last row
                        if current_row and any(current_row):
                            rows.append(current_row)
    except Exception as e:
        print(f"  OCR failed for {pdf_path.name}: {e}")
        return []
    
    return rows


def _normalize_source(source_file: str, source_type: str) -> dict[str, Any]:
    source_path = INPUT_DIR / source_file
    out_name = f"{_slug(source_file)}.csv"
    out_path = NORMALIZED_DIR / out_name

    result: dict[str, Any] = {
        "source": source_file,
        "type": source_type,
        "normalized_csv": str(out_path.relative_to(SCRIPT_DIR.parent)),
        "status": "ok",
        "rows": 0,
    }

    if not source_path.exists():
        result["status"] = "missing"
        return result

    if source_type == "csv":
        rows = _normalize_delimited_file(source_path)
        _write_normalized_csv(out_path, rows)
        result["rows"] = len(rows)
        return result

    if source_type == "html-table":
        rows = _parse_html_conversion_table(source_path)
        _write_normalized_csv(out_path, rows)
        result["rows"] = len(rows)
        return result

    if source_type in {"pdf-table", "pdf-image"}:
        per_pdf_path = PIPELINE_OUTPUT_DIR / "per_pdf" / f"{source_path.stem}.json"
        if per_pdf_path.exists():
            payload = json.loads(per_pdf_path.read_text(encoding="utf-8"))
            rows: list[list[str]] = []
            for item in payload.get("conversions", []):
                entries = item.get("entries", [])
                rows.append([e.get("color_code", "") for e in entries])
            if not rows:
                for item in payload.get("color_list", []):
                    rows.append([item.get("color_id", ""), item.get("name", "")])
            _write_normalized_csv(out_path, rows)
            result["rows"] = len(rows)
            if not rows and source_type == "pdf-image":
                # Try OCR as fallback for image-based PDFs
                print(f"  No tables extracted from {source_file}, attempting OCR...")
                ocr_rows = _extract_pdf_with_ocr(source_path)
                if ocr_rows:
                    _write_normalized_csv(out_path, ocr_rows)
                    result["rows"] = len(ocr_rows)
                    result["status"] = "ocr-extracted"
                    return result
                result["status"] = "needs-manual-ocr"
            return result
        
        # No per_pdf file found
        if source_type == "pdf-image":
            # Try OCR for image-based PDFs
            print(f"  No extracted tables found for {source_file}, attempting OCR...")
            ocr_rows = _extract_pdf_with_ocr(source_path)
            if ocr_rows:
                _write_normalized_csv(out_path, ocr_rows)
                result["rows"] = len(ocr_rows)
                result["status"] = "ocr-extracted"
                return result
            result["status"] = "needs-manual-ocr"
            return result

        result["status"] = "not-extracted"
        return result

    result["status"] = "unsupported"
    return result


def _read_normalized_csv(path: Path) -> list[list[str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        reader = csv.reader(f)
        return [[c.strip() for c in row] for row in reader if any(c.strip() for c in row)]


def _default_resolution_template() -> dict[str, Any]:
    return {"version": 1, "lines": {}, "discrepancies": {}}


def _load_resolution() -> dict[str, Any]:
    if SOURCE_RESOLUTION_PATH.exists():
        try:
            data = json.loads(SOURCE_RESOLUTION_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("version", 1)
                data.setdefault("lines", {})
                data.setdefault("discrepancies", {})
                return data
        except Exception:
            pass
    return _default_resolution_template()


def _save_resolution(data: dict[str, Any]) -> None:
    SOURCE_RESOLUTION_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _compare_sources(line_id: str, normalized_csvs: list[Path]) -> list[dict[str, Any]]:
    parsed: list[tuple[str, dict[str, list[str]]]] = []
    for csv_path in normalized_csvs:
        rows = _read_normalized_csv(csv_path)
        by_id: dict[str, list[str]] = {}
        for row in rows:
            if not row:
                continue
            rid = row[0].strip()
            if not rid:
                continue
            by_id[rid] = row
        parsed.append((csv_path.name, by_id))

    if len(parsed) < 2:
        return []

    all_ids: set[str] = set()
    for _, data in parsed:
        all_ids.update(data.keys())

    diffs: list[dict[str, Any]] = []
    for rid in sorted(all_ids):
        values: dict[str, list[str]] = {}
        for src_name, data in parsed:
            if rid in data:
                values[src_name] = data[rid]
        if len(values) != len(parsed):
            diffs.append({"id": rid, "type": "missing-in-source", "values": values})
            continue
        unique_rows = {tuple(v) for v in values.values()}
        if len(unique_rows) > 1:
            diffs.append({"id": rid, "type": "value-mismatch", "values": values})
    return diffs


def step_extract() -> dict[str, Any]:
    # Run PDF extractor first so per_pdf jsons are available for pdf-table/pdf-image sources.
    extract_cmd = [
        "python",
        str(SCRIPT_DIR / "extract_tables.py"),
        "--input-dir",
        "../input",
        "--output-dir",
        "../output",
        "--profiles",
        "../mappings/profiles.json",
    ]
    subprocess.run(extract_cmd, cwd=SCRIPT_DIR, check=False)

    report: dict[str, Any] = {"lines": {}}
    for item in PIPELINE_SOURCES:
        line_id = item["line_id"]
        line_results = []
        for src in item["sources"]:
            line_results.append(_normalize_source(src["file"], src["type"]))
        report["lines"][line_id] = line_results

    report_path = PIPELINE_OUTPUT_DIR / "source_extract_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def step_compare() -> dict[str, Any]:
    resolution = _load_resolution()

    for item in PIPELINE_SOURCES:
        line_id = item["line_id"]
        csv_paths: list[Path] = []
        for src in item["sources"]:
            normalized = NORMALIZED_DIR / f"{_slug(src['file'])}.csv"
            if normalized.exists():
                csv_paths.append(normalized)

        line_cfg = resolution["lines"].setdefault(line_id, {
            "preferred_source": csv_paths[0].name if csv_paths else "",
            "overrides": {},
            "notes": "",
        })
        available_source_names = {p.name for p in csv_paths}
        if line_cfg.get("preferred_source") not in available_source_names and csv_paths:
            line_cfg["preferred_source"] = csv_paths[0].name
        elif not line_cfg.get("preferred_source") and csv_paths:
            line_cfg["preferred_source"] = csv_paths[0].name

        resolution["discrepancies"][line_id] = _compare_sources(line_id, csv_paths)

    _save_resolution(resolution)
    return resolution


# ---------------------------------------------------------------------------
# ID normalisation helpers
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _paint_lines_by_id() -> dict[str, dict]:
    if not PAINT_LINES_PATH.exists():
        return {}
    data = json.loads(PAINT_LINES_PATH.read_text(encoding="utf-8"))
    return {
        item["id"]: item
        for item in data
        if isinstance(item, dict) and item.get("id")
    }


def _line_meta(
    line_id: str,
    default_prefix: str = "",
    default_suffix: str = "",
) -> dict:
    meta = _paint_lines_by_id().get(line_id, {})
    prefixes = meta.get("prefixes")
    if prefixes is None:
        prefixes = [default_prefix] if default_prefix else []

    suffixes = meta.get("suffixes")
    if suffixes is None:
        suffixes = [default_suffix] if default_suffix else []

    return {
        "prefixes": prefixes,
        "default_prefix": meta.get("default_prefix", default_prefix),
        "suffixes": suffixes,
        "default_suffix": meta.get("default_suffix", default_suffix),
    }


def _matches_line_affix(
    code: str,
    line_id: str,
    default_prefix: str = "",
    default_suffix: str = "",
) -> bool:
    text = code.strip()
    meta = _line_meta(line_id, default_prefix, default_suffix)
    prefixes = meta["prefixes"]
    suffixes = meta["suffixes"]

    for prefix in prefixes:
        if text.lower().startswith(prefix.lower()):
            remaining = text[len(prefix):]
            return bool(re.match(r"^\d", remaining))

    for suffix in suffixes:
        if text.lower().endswith(suffix.lower()):
            remaining = text[: -len(suffix)] if suffix else text
            return bool(re.search(r"\d$", remaining))

    return False


def _remove_line_affixes(
    code: str,
    line_id: str,
    default_prefix: str = "",
    default_suffix: str = "",
) -> str:
    text = code.strip()
    meta = _line_meta(line_id, default_prefix, default_suffix)
    prefixes = sorted(meta["prefixes"], key=len, reverse=True)
    suffixes = sorted(meta["suffixes"], key=len, reverse=True)

    for prefix in prefixes:
        if text.lower().startswith(prefix.lower()):
            text = text[len(prefix):]
            break

    for suffix in suffixes:
        if suffix and text.lower().endswith(suffix.lower()):
            text = text[: -len(suffix)]
            break

    return text

def _vmc_id(code: str) -> str:
    """'70.951' -> '951'  (strip configured Vallejo Model Color prefix)"""
    return _remove_line_affixes(code, "vallejo-model-color", "70.")


def _vma_id(code: str) -> str:
    """'71.001' -> '001'  (strip configured Vallejo Model Air prefix)"""
    return _remove_line_affixes(code, "vallejo-model-air", "71.")


def _ak_id(code: str) -> str:
    """'RC001' -> '001' (strip configured AK Real Colors prefix)"""
    raw = _remove_line_affixes(code, "ak-real-colors", "RC")
    return raw.lstrip("0").zfill(3)


def is_vmc(code: str) -> bool:
    return _matches_line_affix(code, "vallejo-model-color", "70.")


def is_vma(code: str) -> bool:
    return _matches_line_affix(code, "vallejo-model-air", "71.")


def is_ak(code: str) -> bool:
    return _matches_line_affix(code, "ak-real-colors", "RC")


def _dash_or_empty(v: str) -> bool:
    return not v or v == "-" or v == "—"


# ---------------------------------------------------------------------------
# Correspondence builders (small value-objects)
# ---------------------------------------------------------------------------

def corr(manufacturer: str, series: str, color_id: str, note: str = "") -> dict:
    d: dict = {"manufacturer": manufacturer, "series": series, "id": color_id}
    if note:
        d["note"] = note
    return d


def _gunze_corr(raw: str) -> list[dict]:
    """Parse 'C33/H12' or 'C33' or 'H12' -> correspondences for Gunze Mr. Color."""
    results = []
    for token in raw.split("/"):
        token = token.strip()
        if _dash_or_empty(token):
            continue
        # H-xxx  → Gunze Aqueous Hobby Color
        if re.match(r"^H[-.]?\d", token, re.I):
            num = re.sub(r"^H[-.]?", "", token)
            results.append(corr("Gunze", "Gunze Aqueous", num))
        # C-xxx or just digits with context
        elif re.match(r"^C[-.]?\d", token, re.I):
            num = re.sub(r"^C[-.]?", "", token)
            results.append(corr("Gunze", "Mr. Color", num))
    return results


def _italeri_id(raw: str) -> str:
    """'4301AP - RAF/Royal Navy' -> '4301' (strip configured suffix/prefix)"""
    base = re.split(r"\s*[-–]\s*", raw.strip())[0].strip()
    return _remove_line_affixes(base, "italeri-acrylic", "", "AP")


# ---------------------------------------------------------------------------
# 1.  Vallejo Model Color (VMC)
#     Source: VMC_Colors.csv (id/name), VMC_Conversion.csv (cross-refs)
# ---------------------------------------------------------------------------

def build_vmc() -> dict:
    meta = _line_meta("vallejo-model-color", "70.")
    # ---- colour list ----
    colors_by_id: dict[str, dict] = {}
    for row in _read_tsv_no_header("VMC_Colors.csv"):
        if len(row) < 2:
            continue
        code, name = row[0], row[1]
        if not is_vmc(code):
            continue
        cid = _vmc_id(code)
        colors_by_id[cid] = {
            "id": cid,
            "name": name,
            "rgb": "",
            "correspondences": [],
        }

    # ---- cross-reference table (VMC_Conversion.csv) ----
    # Columns: MC | Name | MA | Name | RAL | RLM | FS | ANA
    header, rows = _read_tsv_with_header("VMC_Conversion.csv")
    for row in rows:
        if len(row) < 2:
            continue
        mc_code = row[0]
        if not is_vmc(mc_code):
            continue
        cid = _vmc_id(mc_code)
        entry = colors_by_id.setdefault(cid, {
            "id": cid,
            "name": row[1] if len(row) > 1 else "",
            "rgb": "",
            "correspondences": [],
        })
        corrs: list[dict] = entry["correspondences"]

        # VMA cross-ref
        ma_code = row[2] if len(row) > 2 else ""
        if is_vma(ma_code):
            corrs.append(corr("Vallejo", "Vallejo Model Air", ma_code))

        # Standards
        ral = row[4] if len(row) > 4 else ""
        if not _dash_or_empty(ral):
            corrs.append(corr("Standard", "RAL", ral))

        rlm = row[5] if len(row) > 5 else ""
        if not _dash_or_empty(rlm):
            corrs.append(corr("Standard", "RLM", re.sub(r"^RLM", "", rlm)))

        fs = row[6] if len(row) > 6 else ""
        if not _dash_or_empty(fs):
            corrs.append(corr("Standard", "FS595", fs))

        ana = row[7] if len(row) > 7 else ""
        if not _dash_or_empty(ana):
            corrs.append(corr("Standard", "ANA", ana))

    return {
        "series": "Vallejo Model Color",
        "manufacturer": "Vallejo",
        "prefixes": meta["prefixes"],
        "default_prefix": meta["default_prefix"],
        "suffixes": meta["suffixes"],
        "default_suffix": meta["default_suffix"],
        "colors": sorted(colors_by_id.values(), key=lambda c: c["id"]),
    }


# ---------------------------------------------------------------------------
# 2.  Vallejo Model Air (VMA)
#     Source: VMA_Colors.csv (id/name), VMC_Conversion.csv (cross-refs MA→MC)
# ---------------------------------------------------------------------------

def build_vma() -> dict:
    meta = _line_meta("vallejo-model-air", "71.")
    # ---- colour list ----
    colors_by_id: dict[str, dict] = {}
    for row in _read_tsv_no_header("VMA_Colors.csv"):
        if len(row) < 2:
            continue
        code, name = row[0], row[1]
        if not is_vma(code):
            continue
        cid = _vma_id(code)
        colors_by_id[cid] = {
            "id": cid,
            "name": name,
            "rgb": "",
            "correspondences": [],
        }

    # ---- cross-reference from VMC_Conversion  (MA → MC link) ----
    # Columns: MC | Name | MA | Name | RAL | RLM | FS | ANA
    _, rows = _read_tsv_with_header("VMC_Conversion.csv")
    for row in rows:
        if len(row) < 3:
            continue
        ma_code = row[2]
        if not is_vma(ma_code):
            continue
        cid = _vma_id(ma_code)
        entry = colors_by_id.setdefault(cid, {
            "id": cid,
            "name": row[3] if len(row) > 3 else "",
            "rgb": "",
            "correspondences": [],
        })
        corrs: list[dict] = entry["correspondences"]

        mc_code = row[0]
        if is_vmc(mc_code):
            corrs.append(corr("Vallejo", "Vallejo Model Color", mc_code))

        ral = row[4] if len(row) > 4 else ""
        if not _dash_or_empty(ral):
            corrs.append(corr("Standard", "RAL", ral))

        rlm = row[5] if len(row) > 5 else ""
        if not _dash_or_empty(rlm):
            corrs.append(corr("Standard", "RLM", re.sub(r"^RLM", "", rlm)))

        fs = row[6] if len(row) > 6 else ""
        if not _dash_or_empty(fs):
            corrs.append(corr("Standard", "FS595", fs))

        ana = row[7] if len(row) > 7 else ""
        if not _dash_or_empty(ana):
            corrs.append(corr("Standard", "ANA", ana))

    return {
        "series": "Vallejo Model Air",
        "manufacturer": "Vallejo",
        "prefixes": meta["prefixes"],
        "default_prefix": meta["default_prefix"],
        "suffixes": meta["suffixes"],
        "default_suffix": meta["default_suffix"],
        "colors": sorted(colors_by_id.values(), key=lambda c: c["id"]),
    }


# ---------------------------------------------------------------------------
# 3.  AK Real Colors
#     Source: AK_Conversion.csv
#     Columns: Code | Name | BS/FS/RAL | Mr. Hobby (GSI) | Tamiya |
#              Vallejo | Hataka | Humbrol | Model Master | Lifecolor
# ---------------------------------------------------------------------------

def build_ak() -> dict:
    meta = _line_meta("ak-real-colors", "RC")
    header, rows = _read_tsv_with_header("AK_Conversion.csv")

    # Locate columns dynamically so ordering changes don't break us
    h = [c.lower() for c in header]
    def col(keywords: list[str]) -> int:
        for kw in keywords:
            for i, h_ in enumerate(h):
                if kw in h_:
                    return i
        return -1

    i_code     = col(["code", "ref"])
    i_name     = col(["name"])
    i_standard = col(["bs", "ral", "fs"])
    i_gunze    = col(["mr", "hobby", "gsi", "gunze"])
    i_tamiya   = col(["tamiya"])
    i_vallejo  = col(["vallejo"])
    i_humbrol  = col(["humbrol"])
    i_mm       = col(["model master"])
    i_lifecol  = col(["lifecolor"])

    colors: list[dict] = []

    for row in rows:
        def get(i: int) -> str:
            return row[i].strip() if i >= 0 and i < len(row) else ""

        code = get(i_code)
        if not is_ak(code):
            continue
        cid = _ak_id(code)
        name = get(i_name)
        if _dash_or_empty(name) or name == "#VALUE!":
            continue

        corrs: list[dict] = []

        # Standards (BS / FS / RAL packed into one column).
        # The column can hold values like "RAL 9005 (Modern RAL 840 HR)" or
        # "FS 34087" or "BS No.28 Silver Grey" — extract only the numeric part.
        standard_raw = get(i_standard)
        for part in re.split(r"\s*/\s*", standard_raw):
            part = part.strip()
            if _dash_or_empty(part):
                continue
            # FS: "FS 34087" or 5-digit number
            fs_m = re.match(r"FS\s*(\d{5})", part, re.I)
            if fs_m or re.match(r"^\d{5}$", part):
                fs_num = fs_m.group(1) if fs_m else part
                corrs.append(corr("Standard", "FS595", fs_num))
                continue
            # RAL: "RAL 9005" or "RAL 9005 (...)" → keep only first 4-digit number
            ral_m = re.match(r"RAL\s*(\d{3,4})", part, re.I)
            if ral_m:
                corrs.append(corr("Standard", "RAL", ral_m.group(1)))
                continue
            # BS: keep the raw token (e.g. "BS No.28")
            if re.match(r"^BS", part, re.I):
                corrs.append(corr("Standard", "BS", part))

        # Gunze  (can be "C33/H12", "C33", "H12" or compound)
        gunze_raw = get(i_gunze)
        if not _dash_or_empty(gunze_raw):
            corrs.extend(_gunze_corr(gunze_raw))

        # Tamiya
        tamiya_raw = get(i_tamiya)
        if not _dash_or_empty(tamiya_raw):
            corrs.append(corr("Tamiya", "Tamiya Acrylic", tamiya_raw))

        # Vallejo (may be 70.xxx = VMC or 71.xxx = VMA; sometimes several)
        vallejo_raw = get(i_vallejo)
        for v_part in re.split(r"[/;,\s]+", vallejo_raw):
            v_part = v_part.strip()
            if _dash_or_empty(v_part):
                continue
            if is_vmc(v_part):
                corrs.append(corr("Vallejo", "Vallejo Model Color", v_part))
            elif is_vma(v_part):
                corrs.append(corr("Vallejo", "Vallejo Model Air", v_part))

        # Humbrol
        humbrol_raw = get(i_humbrol)
        for h_part in re.split(r"[/;,]+", humbrol_raw):
            h_part = h_part.strip()
            if not _dash_or_empty(h_part):
                corrs.append(corr("Humbrol", "Humbrol", h_part))

        # Model Master
        mm_raw = get(i_mm)
        for m_part in re.split(r"[/;,]+", mm_raw):
            m_part = m_part.strip()
            if not _dash_or_empty(m_part):
                corrs.append(corr("Model Master", "Model Master", m_part))

        # Lifecolor
        lc_raw = get(i_lifecol)
        if not _dash_or_empty(lc_raw):
            corrs.append(corr("Lifecolor", "Lifecolor", lc_raw))

        colors.append({
            "id": cid,
            "name": name,
            "rgb": "",
            "correspondences": corrs,
        })

    return {
        "series": "AK Real Colors",
        "manufacturer": "AK Interactive",
        "prefixes": meta["prefixes"],
        "default_prefix": meta["default_prefix"],
        "suffixes": meta["suffixes"],
        "default_suffix": meta["default_suffix"],
        "colors": colors,
    }


# ---------------------------------------------------------------------------
# 4.  Italeri
#     Sources:
#       Italeri_Colors.csv     – Nome | Codice 1 | Codice 2 (FS)
#       Italeri_Conversion.csv – Id | Name | FS | Vallejo | RAL | Gunze |
#                                    Tamiya | Revell | Humbrol
# ---------------------------------------------------------------------------

def build_italeri() -> dict:
    meta = _line_meta("italeri-acrylic", "", "AP")
    colors_by_id: dict[str, dict] = {}

    # ---- color list (provides names and FS hint) ----
    header_c, rows_c = _read_tsv_with_header("Italeri_Colors.csv")
    for row in rows_c:
        if len(row) < 2:
            continue
        name  = row[0].strip()
        code1 = row[1].strip()
        code2 = row[2].strip() if len(row) > 2 else ""
        if not code1:
            continue
        cid = _italeri_id(code1)
        entry = colors_by_id.setdefault(cid, {
            "id": cid,
            "name": name,
            "rgb": "",
            "correspondences": [],
        })
        # FS code from column 2 (format "F.S.34151" or "FS34151")
        fs_raw = re.sub(r"^F\.?S\.?", "", code2.strip(), flags=re.I).strip()
        if fs_raw and not _dash_or_empty(fs_raw):
            c = corr("Standard", "FS595", fs_raw)
            if c not in entry["correspondences"]:
                entry["correspondences"].append(c)

    # ---- conversion table (provides cross-refs) ----
    header_t, rows_t = _read_tsv_with_header("Italeri_Conversion.csv")
    h = [c.lower() for c in header_t]
    def col(keywords: list[str]) -> int:
        for kw in keywords:
            for i, h_ in enumerate(h):
                if kw in h_:
                    return i
        return -1

    i_id      = col(["id"])
    i_name    = col(["name"])
    i_fs      = col(["fs"])
    i_vallejo = col(["vallejo"])
    i_ral     = col(["ral"])
    i_gunze   = col(["gunze"])
    i_tamiya  = col(["tamiya"])
    i_revell  = col(["revell"])
    i_humbrol = col(["humbrol"])

    for row in rows_t:
        def get(i: int) -> str:
            return row[i].strip() if i >= 0 and i < len(row) else ""

        raw_id = get(i_id)
        if not raw_id or not re.match(r"^\d{4}", raw_id):
            continue
        # Italeri conversion CSV uses plain numeric ids (4301), normalize to bare number.
        cid_num = re.match(r"^\d+", raw_id).group()
        entry = colors_by_id.setdefault(cid_num, {
            "id": cid_num,
            "name": get(i_name) if i_name >= 0 else "",
            "rgb": "",
            "correspondences": [],
        })
        corrs: list[dict] = entry["correspondences"]

        # FS
        fs = get(i_fs)
        if not _dash_or_empty(fs):
            fs_clean = re.sub(r"^F\.?S\.?", "", fs, flags=re.I).strip()
            c = corr("Standard", "FS595", fs_clean)
            if c not in corrs:
                corrs.append(c)

        # Vallejo (may be VMC or VMA by prefix)
        vallejo = get(i_vallejo)
        if not _dash_or_empty(vallejo):
            for v_part in re.split(r"[/;,\s]+", vallejo):
                v_part = v_part.strip()
                if _dash_or_empty(v_part):
                    continue
                if is_vmc(v_part):
                    c = corr("Vallejo", "Vallejo Model Color", v_part)
                elif is_vma(v_part):
                    c = corr("Vallejo", "Vallejo Model Air", v_part)
                else:
                    continue
                if c not in corrs:
                    corrs.append(c)

        # RAL
        ral = get(i_ral)
        if not _dash_or_empty(ral):
            c = corr("Standard", "RAL", ral)
            if c not in corrs:
                corrs.append(c)

        # Gunze
        gunze = get(i_gunze)
        if not _dash_or_empty(gunze):
            for gc in _gunze_corr(gunze):
                if gc not in corrs:
                    corrs.append(gc)

        # Tamiya
        tamiya = get(i_tamiya)
        if not _dash_or_empty(tamiya):
            c = corr("Tamiya", "Tamiya Acrylic", tamiya)
            if c not in corrs:
                corrs.append(c)

        # Revell
        revell = get(i_revell)
        if not _dash_or_empty(revell):
            c = corr("Revell", "Revell Aqua Color", revell)
            if c not in corrs:
                corrs.append(c)

        # Humbrol
        humbrol = get(i_humbrol)
        if not _dash_or_empty(humbrol):
            c = corr("Humbrol", "Humbrol", humbrol)
            if c not in corrs:
                corrs.append(c)

    return {
        "series": "Italeri Acrylic",
        "manufacturer": "Italeri",
        "prefixes": meta["prefixes"],
        "default_prefix": meta["default_prefix"],
        "suffixes": meta["suffixes"],
        "default_suffix": meta["default_suffix"],
        "colors": list(colors_by_id.values()),
    }


def _paint_line_item(line_id: str) -> dict[str, Any] | None:
    for item in _paint_lines_by_id().values():
        if item.get("id") == line_id:
            return item
    return None


def _preferred_normalized_source(line_id: str, resolution: dict[str, Any]) -> Path | None:
    line_cfg = resolution.get("lines", {}).get(line_id, {})
    preferred = line_cfg.get("preferred_source", "")
    if preferred:
        p = NORMALIZED_DIR / preferred
        if p.exists():
            return p

    for cfg in PIPELINE_SOURCES:
        if cfg["line_id"] != line_id:
            continue
        for src in cfg["sources"]:
            p = NORMALIZED_DIR / f"{_slug(src['file'])}.csv"
            if p.exists():
                return p
    return None


def _build_simple_series_from_source(line_id: str, resolution: dict[str, Any]) -> dict[str, Any] | None:
    meta = _line_meta(line_id)
    line = _paint_line_item(line_id)
    src = _preferred_normalized_source(line_id, resolution)
    if not line or src is None:
        return None

    rows = _read_normalized_csv(src)
    colors: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    def _is_header_row(values: list[str]) -> bool:
        joined = " ".join(v.strip().lower() for v in values if v and v.strip())
        if not joined:
            return False
        header_markers = (
            "colour name",
            "color name",
            "ral/rlm/fs",
            "revell",
            "tamiya",
            "gunze",
            "humbrol",
            "italeri",
        )
        return any(marker in joined for marker in header_markers)

    for row in rows:
        if not row:
            continue
        if len(row) == 1 and ";" in row[0]:
            row = [cell.strip() for cell in row[0].split(";")]
        if _is_header_row(row):
            continue

        raw_id = row[0].strip()
        if not raw_id or raw_id.lower() in {"id", "code", "colour", "color", "name"}:
            continue

        if not _matches_line_affix(raw_id, line_id, meta.get("default_prefix", ""), meta.get("default_suffix", "")):
            # standards/humbrol can be plain numbers (no prefixes)
            if meta.get("prefixes") or meta.get("suffixes"):
                # Keep rows that contain obvious matching prefixed IDs (anywhere in row)
                candidates = [c for c in row if _matches_line_affix(c, line_id, meta.get("default_prefix", ""), meta.get("default_suffix", ""))]
                if candidates:
                    raw_id = candidates[0]

        norm_id = _remove_line_affixes(raw_id, line_id, meta.get("default_prefix", ""), meta.get("default_suffix", ""))
        norm_id = norm_id.strip()
        if not norm_id or norm_id in seen_ids:
            continue

        name = row[1].strip() if len(row) > 1 else ""
        if not name:
            name = raw_id

        colors.append({
            "id": norm_id,
            "name": name,
            "rgb": "",
            "correspondences": [],
        })
        seen_ids.add(norm_id)

    return {
        "series": line.get("series", line_id),
        "manufacturer": line.get("manufacturer", ""),
        "prefixes": meta["prefixes"],
        "default_prefix": meta["default_prefix"],
        "suffixes": meta["suffixes"],
        "default_suffix": meta["default_suffix"],
        "colors": colors,
    }


def _build_mr_color_from_html() -> dict | None:
    try:
        from parse_mr_color_html import parse_html, INPUT_HTML  # type: ignore
    except Exception:
        return None

    if not INPUT_HTML.exists():
        return None

    meta = _line_meta("mr-color", "C")
    colors = parse_html(INPUT_HTML)
    return {
        "series": "Mr. Color",
        "manufacturer": "GSI Creos",
        "prefixes": meta["prefixes"],
        "default_prefix": meta["default_prefix"],
        "suffixes": meta["suffixes"],
        "default_suffix": meta["default_suffix"],
        "colors": colors,
    }


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------

def write_json(data: dict, filename: str) -> None:
    path = OUTPUT_DIR / filename
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    n = len(data.get("colors", []))
    print(f"  Wrote {n:4d} colors → {path.relative_to(OUTPUT_DIR.parent.parent.parent)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def step_build() -> None:
    print("Building paint-series JSON files...")
    resolution = _load_resolution()

    for config in PIPELINE_SOURCES:
        line_id = config.get("line_id", "")
        if not line_id:
            continue

        if line_id == "mr-color":
            data = _build_mr_color_from_html()
        else:
            data = _build_simple_series_from_source(line_id, resolution)

        if not data:
            continue

        filename = OUTPUT_FILENAME_OVERRIDES.get(line_id, f"{line_id}.json")
        print(f"  {data.get('series', line_id)}")
        write_json(data, filename)

    print("Done.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build website paint JSON data pipeline")
    parser.add_argument(
        "--step",
        choices=["extract", "compare", "build", "all"],
        default="build",
        help="Pipeline step to run",
    )
    args = parser.parse_args()

    if args.step in {"extract", "all"}:
        print("[1/3] Extracting/normalizing sources → CSV")
        step_extract()

    if args.step in {"compare", "all"}:
        print("[2/3] Comparing multi-source paint lines and persisting resolution choices")
        step_compare()

    if args.step in {"build", "all"}:
        print("[3/3] Building website JSON files")
        step_build()


if __name__ == "__main__":
    main()
