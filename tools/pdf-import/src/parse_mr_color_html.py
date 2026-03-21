"""
Parse Mr. Color Lacquer Conversion HTML table into JSON for the site.

Input:  tools/pdf-import/input/MrColor Laquer Conversion.html
Output: tools/pdf-import/output/mr-color.json  (site-ready format)

HTML structure
--------------
One outer <div class="color_container_9"> whose children are a flat list of
<div> elements in groups of 12 (one row), preceded by HTML comment markers:

    <!-- mrh001 include -->      ← start of row
    <div>…</div> × 12           ← columns (see COLUMNS below)
    <!-- end mrh001 include -->  ← end of row

Column order (0-indexed)
------------------------
  0  color name
  1  AMMO  (Ammo by Mig Jimenez Acrylic)
  2  AV    (Acrylicos Vallejo – 70.xxx = VMC, 71.xxx = VMA)
  3  GSI   (Gunze: Cxxx = Mr.Color Lacquer, Hxxx = Mr.Hobby Aqueous, Nxxx = same)
  4  HAT   (Hataka – Axx = Acrylic, Cxx = Lacquer)
  5  LC    (Lifecolor Acrylic)
  6  MIS   (Mission Models Acrylic)
  7  MRP   (Mr.Paint – plain = Lacquer, Axxx = Acrylic)
  8  REV   (Revell – 32xxx = Enamel, 36xxx = Acrylic)
  9  TAM   (Tamiya – X/XF = Acrylic, other = Lacquer)
 10  TES   (Testors Enamel)
 11  XTRA  (XtraColour – X = Enamel, XA = Acrylic)

The primary series is Mr.Color Lacquer (C-numbers).
Rows without a C-number are skipped (Mr. Hobby-only colours without
a lacquer equivalent).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    from bs4 import BeautifulSoup, Comment
except ImportError:
    sys.exit("beautifulsoup4 is not installed. Run: pip install beautifulsoup4")

# ── paths ──────────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[3]
INPUT_HTML = REPO_ROOT / "tools/pdf-import/input/MrColor Laquer Conversion.html"
LEGACY_INPUT_HTML = REPO_ROOT / "tools/pdf-import/input/Mr Color Laquer Conversion.html"
OUTPUT_JSON = REPO_ROOT / "tools/pdf-import/output/mr-color.json"

# Number of columns per row
COLS = 12

# ── helpers ────────────────────────────────────────────────────────────────────

def rgb_to_hex(style: str) -> str | None:
    """Extract inline background-color: rgb(r, g, b) and return #rrggbb."""
    m = re.search(r"background-color:\s*rgb\((\d+),\s*(\d+),\s*(\d+)\)", style)
    if m:
        r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"#{r:02X}{g:02X}{b:02X}"
    # Named colors used in the HTML (clear / fluorescent)
    named = re.search(r"background-color:\s*(\w+);", style)
    if named:
        name = named.group(1).lower()
        palette = {
            "black": "#000000",
            "white": "#FFFFFF",
            "red": "#FF0000",
            "yellow": "#FFFF00",
            "orange": "#FFA500",
            "blue": "#0000FF",
            "green": "#008000",
            "dimgray": "#696969",
        }
        return palette.get(name)
    return None


def cell_text(div) -> list[str]:
    """Return a list of non-empty text tokens from a div (splits on <br>)."""
    texts: list[str] = []
    for item in div.contents:
        t = str(item).strip()
        if t and t != "&nbsp;" and t != "\xa0":
            texts.append(t)
    return [t for t in texts if t]


def div_text(div) -> list[str]:
    """Like cell_text but uses .get_text with newline separator."""
    raw = div.get_text(separator="\n")
    return [t.strip() for t in raw.split("\n") if t.strip() and t.strip() != "\xa0"]


# ── correspondence helpers ─────────────────────────────────────────────────────

def make_corr(manufacturer: str, series: str, raw_id: str) -> dict:
    return {"manufacturer": manufacturer, "series": series, "id": raw_id}


def parse_vallejo(tokens: list[str]) -> list[dict]:
    """70.xxx → VMC, 71.xxx → VMA."""
    result = []
    for t in tokens:
        if re.match(r"70\.\d", t):
            result.append(make_corr("Vallejo", "Vallejo Model Color", t))
        elif re.match(r"71\.\d", t):
            result.append(make_corr("Vallejo", "Vallejo Model Air", t))
    return result


def parse_tamiya(tokens: list[str]) -> list[dict]:
    """Tamiya: X-/XF- = Acrylic, AS-/TS- = Spray/Lacquer, LP- = Panel Line."""
    result = []
    for t in tokens:
        if re.match(r"(XF|X)\d", t):
            result.append(make_corr("Tamiya", "Tamiya Acrylic", t))
        elif re.match(r"(TS|AS|LP)\d", t):
            result.append(make_corr("Tamiya", "Tamiya Lacquer", t))
    return result


def parse_revell(tokens: list[str]) -> list[dict]:
    result = []
    for t in tokens:
        if re.match(r"3[26]\d{3}", t):
            result.append(make_corr("Revell", "Revell", t))
    return result


def parse_ammo(tokens: list[str]) -> list[dict]:
    result = []
    for t in tokens:
        if re.match(r"\d{4}", t):
            result.append(make_corr("Ammo", "Ammo by Mig", t))
    return result


def parse_hataka(tokens: list[str]) -> list[dict]:
    result = []
    for t in tokens:
        if re.match(r"[ABC]\d{2,3}", t):
            result.append(make_corr("Hataka", "Hataka", t))
    return result


def parse_lifecolor(tokens: list[str]) -> list[dict]:
    result = []
    for t in tokens:
        if re.match(r"LC\d{3}", t):
            result.append(make_corr("Lifecolor", "Lifecolor", t))
    return result


def parse_mission(tokens: list[str]) -> list[dict]:
    result = []
    for t in tokens:
        if re.match(r"(MMP|MMA|MMC|MMM)\d{3}", t):
            result.append(make_corr("Mission Models", "Mission Models", t))
    return result


def parse_mrpaint(tokens: list[str]) -> list[dict]:
    result = []
    for t in tokens:
        if re.match(r"(MRP)?[A-Z]?\d{3,}", t) or re.match(r"\d{3,}", t):
            result.append(make_corr("Mr. Paint", "Mr. Paint", t))
    return result


def parse_testors(tokens: list[str]) -> list[dict]:
    result = []
    for t in tokens:
        if re.match(r"\d{3,}", t):
            result.append(make_corr("Testors", "Testors", t))
    return result


def parse_xtracolour(tokens: list[str]) -> list[dict]:
    result = []
    for t in tokens:
        if re.match(r"X[A]?\d{3}", t):
            series = "XtraColour Acrylic" if t.startswith("XA") else "XtraColour"
            result.append(make_corr("XtraColour", series, t))
    return result


# ── main parse ─────────────────────────────────────────────────────────────────

def parse_gsi_column(tokens: list[str]) -> dict:
    """Return {'mr_color': ['001','002'], 'mr_hobby': ['001'], 'mr_hobby_n': ['001']}."""
    result: dict[str, list[str]] = {"C": [], "H": [], "N": []}
    for t in tokens:
        m = re.fullmatch(r"([CHN])(\d+)", t)
        if m:
            prefix, num = m.group(1), m.group(2)
            result[prefix].append(num)
    return result


def parse_html(html_path: Path) -> list[dict]:
    html = html_path.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")

    # Collect all direct children of the container (divs + comments)
    container = soup.find("div", class_=re.compile(r"color_container"))
    if container is None:
        # Fall back: search entire document
        container = soup

    nodes = list(container.children)

    # Group into row blocks using comment markers like "mrh001 include"
    row_start_re = re.compile(r"^\s*(mr[a-z]\d+)\s+include\s*$")
    row_end_re   = re.compile(r"^\s*end\s+(mr[a-z]\d+)\s+include\s*$")

    rows: list[tuple[str, list]] = []   # (comment_id, [div, ...])
    current_id: str | None = None
    current_divs: list = []

    for node in nodes:
        if isinstance(node, Comment):
            text = str(node).strip()
            m_start = row_start_re.match(text)
            m_end   = row_end_re.match(text)
            if m_start:
                # Flush any open row (safety)
                if current_id and current_divs:
                    rows.append((current_id, current_divs))
                current_id = m_start.group(1)
                current_divs = []
            elif m_end and current_id:
                rows.append((current_id, current_divs))
                current_id = None
                current_divs = []
        elif node.name == "div" and current_id:
            current_divs.append(node)

    # Also flush any unclosed final row
    if current_id and current_divs:
        rows.append((current_id, current_divs))

    colors: list[dict] = []

    for comment_id, divs in rows:
        if len(divs) < COLS:
            # row has fewer than expected divs – skip header / partial rows
            continue

        # Exactly COLS divs: take the first COLS
        cols = divs[:COLS]

        # Background hex from the first div's style
        style = cols[0].get("style", "")
        hex_color = rgb_to_hex(style)

        # Column texts
        col_texts = [div_text(d) for d in cols]

        name_tokens = col_texts[0]
        name = " / ".join(name_tokens) if name_tokens else ""

        # GSI column (index 3) → extract C, H, N numbers
        gsi = parse_gsi_column(col_texts[3])
        c_nums = gsi["C"]   # Mr. Color Lacquer IDs (bare numbers)
        h_nums = gsi["H"]   # Mr. Hobby Aqueous

        # Skip rows that have no C-number (Mr. Hobby-only entries)
        if not c_nums:
            continue

        primary_id = c_nums[0]

        # Build correspondences from the other columns
        correspondences: list[dict] = []

        correspondences += parse_vallejo(col_texts[2])
        correspondences += parse_hataka(col_texts[4])
        correspondences += parse_lifecolor(col_texts[5])
        correspondences += parse_mission(col_texts[6])
        correspondences += parse_mrpaint(col_texts[7])
        correspondences += parse_revell(col_texts[8])
        correspondences += parse_tamiya(col_texts[9])
        correspondences += parse_testors(col_texts[10])
        correspondences += parse_xtracolour(col_texts[11])

        # AMMO column
        correspondences += parse_ammo(col_texts[1])

        # Mr. Hobby cross-reference (same manufacturer, different series)
        # H-numbers and N-numbers are stored WITH their prefix (H001, N001)
        for hnum in h_nums:
            correspondences.append(make_corr("GSI Creos", "Mr. Hobby Aqueous", f"H{hnum}"))
        for nnum in gsi["N"]:
            correspondences.append(make_corr("GSI Creos", "Mr. Hobby Aqueous", f"N{nnum}"))

        # Additional C-numbers if the GSI column listed multiple C codes
        for extra_c in c_nums[1:]:
            correspondences.append(make_corr("GSI Creos", "Mr. Color", f"C{extra_c}"))

        entry: dict = {
            "id": primary_id,
            "name": name,
        }
        if hex_color:
            entry["rgb"] = hex_color
        if correspondences:
            entry["correspondences"] = correspondences

        colors.append(entry)

    return colors


def main() -> None:
    input_html = INPUT_HTML if INPUT_HTML.exists() else LEGACY_INPUT_HTML
    if not input_html.exists():
        sys.exit(f"Input file not found: {INPUT_HTML}")

    print(f"Parsing {input_html.name} …")
    colors = parse_html(input_html)
    print(f"  {len(colors)} Mr. Color entries found")

    output: dict = {
        "series": "Mr. Color",
        "manufacturer": "GSI Creos",
        "prefixes": ["C", "GX"],
        "default_prefix": "C",
        "suffixes": [],
        "default_suffix": "",
        "colors": colors,
    }

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"  Written to {OUTPUT_JSON.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
