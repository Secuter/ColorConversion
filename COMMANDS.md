# ColorConversion - Commands Reference

## Vue Site (Frontend)

### Prerequisites
```bash
# Install Node.js dependencies (run once)
npm install
```

### Running the Development Server
```bash
# Start the Vite dev server (hot reload enabled)
npm run dev
```
The site will typically be available at `http://localhost:5173`

### Building for Production
```bash
# Build the Vue site for production
npm run build
```

### Preview Production Build
```bash
# Preview the production build locally
npm run preview
```

---

## Python Scripts (PDF Import Tools)

### Prerequisites
```bash
# Navigate to the tools/pdf-import directory
cd tools/pdf-import

# Install Python dependencies (one-time setup)
pip install -r requirements.txt
```

### Extract Tables from PDFs
```bash
# Extract color tables from PDF files
python src/extract_tables.py
```

### Build JSON from Extracted Data (New 3-Step Pipeline)
```bash
# Run the complete pipeline: extract → compare → build
python src/build_json.py --step all

# Or run individual steps:

# Step 1: Extract and normalize all sources to CSV
python src/build_json.py --step extract

# Step 2: Compare multi-source paint lines and detect discrepancies
python src/build_json.py --step compare

# Step 3: Generate final website JSON files
python src/build_json.py --step build
```

**Pipeline Details:**
- **Extract:** Normalizes CSV/PDF/HTML sources to unified CSV format in `output/normalized/`, handles multiple encodings and delimiters (✓ tab, comma, semicolon, pipe), integrates OCR fallback for image PDFs.
- **Compare:** Detects discrepancies across multi-source paint lines, persists resolution choices in `mappings/source_resolution.json`.
- **Build:** Generates final `src/data/*.json` files from configured sources in `mappings/sources.config.json`, applies header filtering and split correction.

**Configuration:**
- Paint sources and types are defined in: `mappings/sources.config.json`
- Preferred sources and discrepancy tracking: `mappings/source_resolution.json` (auto-generated)

### Parse Mr. Color HTML Conversion Table
```bash
# Parse the Mr Color Lacquer Conversion HTML into site-ready JSON.
# Input:  tools/pdf-import/input/Mr Color Laquer Conversion.html
# Output: tools/pdf-import/output/mr-color.json
python src/parse_mr_color_html.py
```

### Helper Scripts

#### CSV Column Helper
```bash
# Analyze CSV column structure
python csv_column_helper.py
```

#### Test CSV Parsing
```bash
# Test and validate CSV parsing functionality
python test_csv_parsing.py
```

---

## Quick Start Example

1. **Setup Vue Site:**
   ```bash
   npm install
   npm run dev
   ```

2. **Setup Python Environment:**
   ```bash
   cd tools/pdf-import
   pip install -r requirements.txt
   ```

3. **Process PDFs:**
   ```bash
   python src/extract_tables.py
   python src/build_json.py
   ```

---

## Directory References

- **Vue Source:** `src/`
- **Python Tools:** `tools/pdf-import/`
- **Data Output:** `tools/pdf-import/output/`
- **Input PDFs:** `tools/pdf-import/input/` (place PDFs here)
