# Datasets

- `seed/` — Product KB, Policy KB (incl. secret promo), Regulatory sample (RusLawOD-style abstracts for retail).
- `fixtures/` — label inputs for PDF/PNG demos (`label.png.txt`, `label_scan.pdf.txt` used as upload filenames `label.png` / `label_scan.pdf`).

Full RusLawOD corpus: https://github.com/irlcode/RusLawOD — ingest subset via future `pipelines/ingest_ruslaw.py` (XML → Document/Chunk).