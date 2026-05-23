"""One-off extraction helper for April 2026 fund PDFs."""
from __future__ import annotations

import json
from pathlib import Path

from pypdf import PdfReader

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

FOLDER = Path(r"D:\V\1. Current Trade Sys\Reports\Funds April 2026")
OUT = FOLDER / "_extracted_text"


def extract_pypdf(path: Path) -> str:
    reader = PdfReader(str(path))
    parts = []
    for i, page in enumerate(reader.pages):
        t = page.extract_text() or ""
        parts.append(f"\n--- PAGE {i + 1} ---\n{t}")
    return "\n".join(parts)


def extract_tables(path: Path) -> list:
    if not pdfplumber:
        return []
    tables = []
    with pdfplumber.open(str(path)) as pdf:
        for i, page in enumerate(pdf.pages):
            for ti, table in enumerate(page.extract_tables() or []):
                tables.append({"page": i + 1, "table_index": ti, "rows": table})
    return tables


def main() -> None:
    OUT.mkdir(exist_ok=True)
    manifest = []
    for pdf in sorted(FOLDER.glob("*.pdf")):
        text = extract_pypdf(pdf)
        text_path = OUT / f"{pdf.stem}.txt"
        text_path.write_text(text, encoding="utf-8", errors="replace")
        tables = extract_tables(pdf)
        tables_path = OUT / f"{pdf.stem}_tables.json"
        tables_path.write_text(
            json.dumps(tables, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        manifest.append(
            {
                "file": pdf.name,
                "chars": len(text),
                "pages": text.count("--- PAGE"),
                "tables": len(tables),
            }
        )
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
