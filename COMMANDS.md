# ColorConversion - Commands Reference

## Vue Site (Frontend)

### Prerequisites
```bash
npm install
```

### Running the Development Server
```bash
npm run dev
```
The site will typically be available at `http://localhost:5173`

### Building for Production
```bash
npm run build
```

### Preview Production Build
```bash
npm run preview
```

---

## Python Scripts (PDF Import Tools)

### Prerequisites
```bash
pip install -r tools/pdf-import/requirements.txt
```

### Parse Sources Configuration
```bash
python tools/pdf-import/src/1_parse_sources.py

python tools/pdf-import/src/2_remap_sources.py

python tools/pdf-import/src/extract_csv_headers.py tools/pdf-import/input

python tools/pdf-import/src/3_sort_csv.py

python tools/pdf-import/src/4_merge_and_report.py
```

---

## Directory References

- **Vue Source:** `src/`
- **Python Tools:** `tools/pdf-import/`
- **Data Output:** `tools/pdf-import/output/`
- **Input PDFs:** `tools/pdf-import/input/` (place PDFs here)
