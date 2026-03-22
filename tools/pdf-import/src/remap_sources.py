#!/usr/bin/env python3
"""
Part 2: CSV translation/remapping
- Reads CSVs from input (for csv sources) or output/normalized (for parsed html/pdf)
- Applies header mapping, column exclusion, split/merge rules
- Writes final CSVs to output/normalized
"""

from __future__ import annotations

import csv
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).parent
TOOLS_DIR = SCRIPT_DIR.parent
SOURCES_FILE = TOOLS_DIR / "mappings" / "sources-config.json"
HEADERS_CONFIG_FILE = TOOLS_DIR / "mappings" / "column-headers.json"
COLUMN_CONFIG_FILE = TOOLS_DIR / "mappings" / "column-config.json"
INPUT_DIR = TOOLS_DIR / "input"
OUTPUT_DIR = TOOLS_DIR / "output"
NORMALIZED_DIR = OUTPUT_DIR / "normalized"

SKIP_HEADER = "__SKIP_COLUMN__"


def load_json_file(path: Path, missing_message: str) -> dict:
    try:
        with path.open("r", encoding="utf-8") as file_handle:
            return json.load(file_handle)
    except FileNotFoundError:
        logger.error("%s: %s", missing_message, path)
        sys.exit(1)
    except json.JSONDecodeError as exc:
        logger.error("Invalid JSON in %s: %s", path, exc)
        sys.exit(1)


def load_sources() -> dict:
    return load_json_file(SOURCES_FILE, "sources-config.json not found")


def load_column_config() -> dict:
    try:
        with COLUMN_CONFIG_FILE.open("r", encoding="utf-8") as file_handle:
            return json.load(file_handle)
    except FileNotFoundError:
        return {"general": []}


def load_headers_config() -> dict:
    try:
        with HEADERS_CONFIG_FILE.open("r", encoding="utf-8") as file_handle:
            return json.load(file_handle)
    except FileNotFoundError:
        return {"lastUpdated": datetime.now().isoformat()}


def save_headers_config(config: dict) -> None:
    config["lastUpdated"] = datetime.now().isoformat()
    with HEADERS_CONFIG_FILE.open("w", encoding="utf-8") as file_handle:
        json.dump(config, file_handle, indent=2, ensure_ascii=False)


def normalize_header(value: str) -> str:
    normalized = str(value).strip().lower()
    return re.sub(r"\s+", " ", normalized)


def normalize_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", str(value or "")).upper()


def build_output_path(source_file_name: str) -> Path:
    return NORMALIZED_DIR / f"{Path(source_file_name).stem}.csv"


def get_source_config_key(source_filename: str) -> str:
    return Path(source_filename).stem


def read_csv_rows(path: Path) -> list[list[str]]:
    encodings = ["utf-8", "utf-8-sig", "cp1252", "latin-1"]
    last_error: UnicodeDecodeError | None = None

    for encoding in encodings:
        try:
            with path.open("r", encoding=encoding, newline="") as file_handle:
                reader = csv.reader(file_handle, delimiter=";")
                rows = [list(row) for row in reader]
            if encoding != "utf-8":
                logger.warning("Using fallback encoding '%s' for %s", encoding, path.name)
            return rows
        except UnicodeDecodeError as exc:
            last_error = exc

    if last_error is not None:
        raise last_error
    raise UnicodeDecodeError("utf-8", b"", 0, 1, f"Unable to decode {path.name}")


def write_csv_rows(rows: list[list[str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file_handle:
        writer = csv.writer(file_handle, delimiter=";")
        writer.writerows(rows)


def get_file_header_mappings(headers_config: dict, source_filename: str) -> dict:
    file_entry = headers_config.get(source_filename)
    if isinstance(file_entry, dict):
        if "column_mappings" in file_entry and isinstance(file_entry["column_mappings"], dict):
            return file_entry["column_mappings"]
        return file_entry

    legacy = headers_config.get("column_mappings")
    if isinstance(legacy, dict):
        return legacy

    headers_config[source_filename] = {"column_mappings": {}}
    return headers_config[source_filename]["column_mappings"]


def find_mapped_header(header: str, header_mappings: dict) -> str | bool | None:
    normalized = normalize_header(header)
    for source_header, mapped in header_mappings.items():
        if normalize_header(source_header) == normalized:
            return mapped
    return None


def register_unknown_header(header: str, headers_config: dict, source_filename: str) -> None:
    file_mappings = get_file_header_mappings(headers_config, source_filename)
    if header not in file_mappings:
        file_mappings[header] = header


def map_headers(headers: list[str], headers_config: dict, source_filename: str) -> list[str]:
    mapped: list[str] = []
    file_mappings = get_file_header_mappings(headers_config, source_filename)

    for header in headers:
        header_text = str(header).strip()
        result = find_mapped_header(header_text, file_mappings)

        if result is False:
            mapped.append(SKIP_HEADER)
        elif isinstance(result, str):
            mapped.append(result)
        elif header_text:
            register_unknown_header(header_text, headers_config, source_filename)
            mapped.append(header_text)
        else:
            mapped.append("")

    return mapped


def drop_skipped_columns(rows: list[list[str]]) -> list[list[str]]:
    if not rows:
        return rows

    header = rows[0]
    keep_indices = [idx for idx, name in enumerate(header) if name != SKIP_HEADER]
    if len(keep_indices) == len(header):
        return rows

    filtered: list[list[str]] = []
    for row in rows:
        filtered.append([row[idx] if idx < len(row) else "" for idx in keep_indices])
    return filtered


def get_general_rule(column_config: dict, header: str) -> dict | None:
    header_norm = normalize_header(header)
    for item in column_config.get("general", []):
        if normalize_header(item.get("name", "")) == header_norm:
            return item
        for target in item.get("columns", []):
            if normalize_header(target.get("name", "")) == header_norm:
                return item
    return None


def get_always_split_targets(column_config: dict, source_filename: str, header: str) -> list[str] | None:
    file_config = column_config.get(get_source_config_key(source_filename))
    if not isinstance(file_config, dict):
        return None

    header_norm = normalize_header(header)
    for item in file_config.get("always_split", []):
        if normalize_header(item.get("name", "")) == header_norm:
            targets = item.get("targets")
            if isinstance(targets, list):
                return [str(value) for value in targets]
    return None


def split_tokens(value: str, separators: list[str]) -> list[str]:
    if not value:
        return []

    transformed = value
    for sep in separators:
        token = str(sep or "").strip()
        if not token:
            continue
        if token.isalpha():
            transformed = re.sub(rf"\s*\b{re.escape(token)}\b\s*", "/", transformed, flags=re.I)
        else:
            transformed = transformed.replace(token, "/")

    return [part.strip() for part in transformed.split("/") if part.strip()]


def remove_prefix(value: str, prefix: str) -> str:
    if value.upper().startswith(prefix.upper()):
        return value[len(prefix):].strip()
    return value.strip()


def merge_values(current: str, new_value: str, separator: str, warn_context: str | None = None) -> str:
    if not new_value:
        return current
    if not current:
        return new_value

    existing_tokens = [token.strip() for token in current.split(separator) if token.strip()]
    new_tokens = [token.strip() for token in new_value.split(separator) if token.strip()]

    existing_norm = {normalize_id(token) for token in existing_tokens}
    for token in new_tokens:
        token_norm = normalize_id(token)
        if token_norm in existing_norm:
            continue
        if existing_norm and warn_context:
            logger.warning("Different ids merged in %s: '%s' + '%s'", warn_context, current, token)
        existing_tokens.append(token)
        existing_norm.add(token_norm)

    return separator.join(existing_tokens)


def looks_like_color_id(token: str) -> bool:
    return bool(re.search(r"\d", token or ""))


def is_non_paint_column(header: str) -> bool:
    return normalize_header(header) in {
        "",
        "name",
        "id",
        "fs",
        "ral",
        "rlm",
        "ana",
        "bs",
        "ral/rlm/fs/bs",
    }


def has_multiple_color_ids(tokens: list[str]) -> bool:
    return sum(1 for token in tokens if looks_like_color_id(token)) > 1


def apply_column_rules(rows: list[list[str]], source_filename: str, metadata: dict, column_config: dict) -> list[list[str]]:
    if not rows:
        return rows

    header = rows[0]
    data_rows = rows[1:]

    source_key = get_source_config_key(source_filename)
    source_file_config = column_config.get(source_key) if isinstance(column_config.get(source_key), dict) else {}
    has_file_specific_config = bool(source_file_config)

    color_separator = str(metadata.get("color_separator", "/"))
    line_separator = str(metadata.get("line_separator", "/"))

    split_separators = [color_separator]
    if has_file_specific_config and line_separator not in split_separators:
        split_separators.append(line_separator)

    expanded_headers: list[str] = []
    for column_name in header:
        rule = get_general_rule(column_config, column_name)
        always_targets = get_always_split_targets(column_config, source_filename, column_name)

        if always_targets:
            targets = [target for target in always_targets if target != "SKIP"]
            if not targets:
                continue
        elif rule:
            targets = [
                str(item.get("name", "")).strip()
                for item in rule.get("columns", [])
                if str(item.get("name", "")).strip()
            ]
            if not targets:
                targets = [column_name]
        else:
            targets = [column_name]

        for target in targets:
            if target not in expanded_headers:
                expanded_headers.append(target)

    transformed_rows: list[list[str]] = [expanded_headers]

    for row_index, row in enumerate(data_rows, start=2):
        target_values = {column_name: "" for column_name in expanded_headers}

        for col_index, column_name in enumerate(header):
            cell = row[col_index] if col_index < len(row) else ""
            if not cell:
                continue

            rule = get_general_rule(column_config, column_name)
            always_targets = get_always_split_targets(column_config, source_filename, column_name)
            tokens = split_tokens(cell, split_separators)

            if always_targets:
                for target_idx, target_name in enumerate(always_targets):
                    if target_name == "SKIP":
                        continue
                    token_value = tokens[target_idx] if target_idx < len(tokens) else ""
                    if token_value:
                        target_values[target_name] = merge_values(
                            target_values.get(target_name, ""),
                            token_value,
                            color_separator,
                            f"{source_filename}:{column_name}:row{row_index}",
                        )
                continue

            if rule:
                columns_cfg = rule.get("columns", [])
                skip_prefixes = [str(prefix) for prefix in rule.get("skip", [])]

                unresolved_tokens: list[str] = []
                for token in tokens or [cell.strip()]:
                    token_clean = token.strip()
                    if not token_clean:
                        continue

                    if any(token_clean.upper().startswith(prefix.upper()) for prefix in skip_prefixes):
                        continue

                    matched_target = None
                    mapped_value = token_clean

                    for target_cfg in columns_cfg:
                        target_name = str(target_cfg.get("name", "")).strip()
                        prefixes = [str(prefix) for prefix in target_cfg.get("prefixes", [])]

                        if prefixes:
                            for prefix in prefixes:
                                if token_clean.upper().startswith(prefix.upper()):
                                    matched_target = target_name
                                    mapped_value = remove_prefix(token_clean, prefix)
                                    break
                            if matched_target:
                                break
                        else:
                            matched_target = target_name
                            mapped_value = token_clean
                            break

                    if matched_target:
                        target_values[matched_target] = merge_values(
                            target_values.get(matched_target, ""),
                            mapped_value,
                            color_separator,
                            f"{source_filename}:{column_name}:row{row_index}",
                        )
                    else:
                        unresolved_tokens.append(token_clean)

                if (
                    unresolved_tokens
                    and len(tokens) > 1
                    and any(looks_like_color_id(token) for token in unresolved_tokens)
                    and not is_non_paint_column(column_name)
                ):
                    logger.error(
                        "Missing split mapping for %s in %s (row %s): %s",
                        column_name,
                        source_filename,
                        row_index,
                        ", ".join(unresolved_tokens),
                    )
                    raise RuntimeError(
                        f"Unmapped multi-color cell in {source_filename} column '{column_name}' row {row_index}: {cell}"
                    )
                continue

            if len(tokens) > 1 and has_multiple_color_ids(tokens) and not is_non_paint_column(column_name):
                logger.error(
                    "No column config found for multi-color cell in %s column '%s' row %s: %s",
                    source_filename,
                    column_name,
                    row_index,
                    cell,
                )
                raise RuntimeError(
                    f"Missing column config for multi-color cell in {source_filename} column '{column_name}' row {row_index}: {cell}"
                )

            target_values[column_name] = merge_values(target_values.get(column_name, ""), cell, color_separator, None)

        transformed_rows.append([target_values.get(column_name, "") for column_name in expanded_headers])

    return transformed_rows


def clean_rows(rows: list[list[str]]) -> list[list[str]]:
    if not rows:
        return rows

    header_row = rows[0]
    header_first_cell = (header_row[0] or "").strip().lower() if header_row else ""

    cleaned: list[list[str]] = [header_row]
    for row in rows[1:]:
        if not row:
            continue

        normalized_row = [cell.replace(" / ", "/") if cell else cell for cell in row]
        first_cell = (normalized_row[0] or "").strip().lower()

        if first_cell == "notes":
            continue

        if header_first_cell and first_cell == header_first_cell:
            continue

        cleaned.append(normalized_row)

    return cleaned


def prepare_rows_with_mapped_headers(rows: list[list[str]], headers_config: dict, source_filename: str) -> list[list[str]]:
    if not rows:
        return []

    mapped_header = map_headers(rows[0], headers_config, source_filename)
    return [mapped_header] + rows[1:]


def build_stats() -> dict[str, int]:
    return {"total": 0, "missing": 0, "written": 0, "failed": 0}


def resolve_input_csv_path(source_type: str, source_filename: str) -> Path:
    if source_type == "csv":
        return INPUT_DIR / source_filename
    return NORMALIZED_DIR / f"{Path(source_filename).stem}.csv"


def process_sources(sources_config: dict, headers_config: dict, column_config: dict, stats: dict[str, int]) -> None:
    for line in sources_config.get("lines", []):
        line_id = str(line.get("line_id", "unknown"))
        for source in line.get("sources", []):
            source_filename = str(source.get("file", "")).strip()
            source_type = str(source.get("type", "csv")).strip().lower()
            input_csv = resolve_input_csv_path(source_type, source_filename)
            output_csv = build_output_path(source_filename)

            stats["total"] += 1

            if not input_csv.exists():
                stats["missing"] += 1
                logger.info("[REMAP] %s | %s | MISSING INPUT (%s)", line_id, source_filename, input_csv.name)
                continue

            try:
                rows = read_csv_rows(input_csv)
                if not rows:
                    stats["failed"] += 1
                    logger.info("[REMAP] %s | %s | FAILED (empty csv)", line_id, source_filename)
                    continue

                rows = prepare_rows_with_mapped_headers(rows, headers_config, source_filename)
                rows = drop_skipped_columns(rows)
                rows = apply_column_rules(rows, source_filename, source, column_config)
                rows = clean_rows(rows)

                write_csv_rows(rows, output_csv)
                stats["written"] += 1
                logger.info("[REMAP] %s | %s | WRITTEN (%s)", line_id, source_filename, output_csv.name)
            except Exception as exc:
                stats["failed"] += 1
                logger.info("[REMAP] %s | %s | FAILED (%s)", line_id, source_filename, exc)


def main() -> None:
    logger.info("=" * 60)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)

    sources_config = load_sources()
    headers_config = load_headers_config()
    column_config = load_column_config()

    stats = build_stats()
    process_sources(sources_config, headers_config, column_config, stats)

    save_headers_config(headers_config)

    logger.info("=" * 60)
    logger.info(
        "Summary | total=%s written=%s failed=%s missing=%s",
        stats["total"],
        stats["written"],
        stats["failed"],
        stats["missing"],
    )
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
