# GitHub Copilot Instructions — ColorConversion

## Project Overview

**Paint Colors Converter** is a client-side Vue 3 SPA that lets modelers convert paint color codes across different manufacturer lines (Vallejo, Tamiya, AK, AMMO, Humbrol, Mr. Color, Revell, Italeri, etc.).

There is no backend — all data is bundled as static JSON files and all logic runs in the browser.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | Vue 3 (Composition API, `<script setup>`) |
| Language | TypeScript (strict) |
| Build tool | Vite 5 |
| Type checking | vue-tsc |
| Styling | Plain CSS (scoped in `.vue` files) |
| Data | Static JSON files imported at build time |
| No router | Single page, no Vue Router |
| No state manager | No Pinia/Vuex — composables only |

---

## Project Structure

```
src/
  App.vue                    # Root component — UI layout and top-level state
  main.ts                    # App entry point
  types.ts                   # All shared TypeScript interfaces
  style.css                  # Global styles
  counter.ts                 # (utility)
  components/
    ConversionResults.vue    # Results table component
  composables/
    useColorDetection.ts     # Series detection from input codes
    useConversion.ts         # Core conversion logic
  data/
    index.ts                 # Aggregates all JSON series into allSeries[]
    paint-lines.json         # Metadata: series names, manufacturers, prefixes
    *.json                   # One JSON file per paint line (colors + correspondences)

tools/
  pdf-import/                # Python scripts to extract/normalize data from PDFs/CSVs
    src/                     # build_json.py, extract_tables.py, etc.
    input/                   # Raw CSV/HTML sources
    output/                  # Processed CSVs and JSON outputs
    mappings/                # Profile configs for source resolution
```

---

## Key Interfaces (`src/types.ts`)

```ts
PaintColor         // id, name, rgb, correspondences[]
PaintSeries        // series, manufacturer, prefixes[], colors[]
Correspondence     // manufacturer, series, id, note?
MatchedCorrespondence  // extended match with name, rgb, source ('direct'|'reverse')
ConversionResult   // inputCode, normalizedId, sourceColor, sourceSeries, correspondences[]
DetectionResult    // series, confidence ('certain'|'possible'|'unknown'), matchingPrefix
```

---

## Core Logic

### Series Detection (`useColorDetection.ts`)
- `detectSeries(code)` — matches a single code to a series via prefix/suffix
- `autoDetectFromInput(input)` — detects dominant series from multiline input
- `normalizeId(id, series)` — strips prefix/suffix to get the bare numeric/alpha id

### Conversion (`useConversion.ts`)
- `convertColors(codes, sourceSeries, targetManufacturers?)` — main conversion function
- Looks up each code in the source series, then finds `correspondences` in target series
- Supports both **direct** (source → target listed in source JSON) and **reverse** (target → source listed in target JSON) matching
- Deduplicates input codes before processing

### Data (`data/index.ts`)
- All JSON files are imported statically and merged with metadata from `paint-lines.json`
- Exported as `allSeries: PaintSeries[]`
- Adding a new paint line requires: a new JSON file + an entry in `paint-lines.json` + an import in `index.ts`

---

## Coding Conventions

- Use **Composition API** with `<script setup lang="ts">` — no Options API
- Use **`type`** imports: `import type { Foo } from '../types.ts'`
- Include `.ts` extension in all local imports (Vite ESM requirement)
- Prefer `computed()` over methods for derived state
- Keep composables **pure** where possible — no direct DOM access
- CSS is **scoped** per component; global styles go in `style.css`
- No external UI libraries — style from scratch
- Avoid `any` — use proper types from `types.ts`

### CSV Files
- Always use **`;`** as the column separator in all CSV files

---

## Data Format

Each paint line JSON follows this shape:

```json
{
  "series": "Vallejo Model Color",
  "manufacturer": "Vallejo",
  "prefixes": ["70."],
  "colors": [
    {
      "id": "70.950",
      "name": "Black",
      "rgb": "#000000",
      "correspondences": [
        { "manufacturer": "Tamiya", "series": "Tamiya Acrylic", "id": "XF-1" }
      ]
    }
  ]
}
```

---

## Python Tools (`tools/pdf-import/`)

Used to import and normalize paint data from PDFs, CSVs and HTML files.

- **`extract_tables.py`** — extracts tables from raw sources
- **`build_json.py`** — assembles final JSON files consumed by the Vue app
- **`parse_mr_color_html.py`** — HTML-specific parser
- Run with the `.venv` virtual environment activated
- Output goes to `tools/pdf-import/output/`; finalized JSONs are copied to `src/data/`
- Keep **`COMMANDS.md`** up to date whenever scripts are added, renamed, or their arguments change

### Important: Script-Generated Files

**Do NOT manually edit generated files** (e.g., `tools/pdf-import/output/normalized/*.csv`, `tools/pdf-import/mappings/column-headers.json`) when logic or formatting changes are required.

Instead:
1. Update the Python script to implement the desired logic/formatting change
2. Re-run the script to regenerate files correctly
3. Verify outputs and commit the regenerated files

This ensures consistency, prevents accidental regressions, and maintains proper serialization/formatting across the pipeline.

---

## Adding a New Paint Line (checklist)

1. Add `src/data/<new-line>.json` with correct `PaintSeries` shape
2. Add an entry in `src/data/paint-lines.json`
3. Import and register it in `src/data/index.ts`
4. Add correspondences in existing JSONs if cross-references are known

---

## Git Conventions

- Commit messages must be **short and on point**
- List only the features changed or added — no full descriptions or explanations of fixes
- Format: imperative mood, one line per item if multiple things changed
  ```
  Add Revell enamel correspondences for Tamiya
  Fix normalizeId stripping suffix on AK codes
  ```

---

## Deployment

- Built with `npm run build` → static output in `dist/`
- Served by Apache as a static SPA
- `.htaccess` handles Vue Router fallback (`RewriteRule ^ index.html`)
- `index.html` is served with `no-cache` headers; hashed assets use long-lived cache
- CI/CD via GitHub Actions on push to `main`
