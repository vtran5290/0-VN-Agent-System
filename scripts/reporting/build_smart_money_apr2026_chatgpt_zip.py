"""
Build smart_money_apr2026_chatgpt_review.zip for ChatGPT QA.

Usage:
  python -m scripts.reporting.build_smart_money_apr2026_chatgpt_zip
"""
from __future__ import annotations

import zipfile
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FUNDS_DIR = Path(r"D:\V\1. Current Trade Sys\Reports\Funds April 2026")
STAMP = datetime.now().strftime("%Y%m%d")
OUT_DIR = REPO / "outputs" / "review_packages"
OUT_ZIP = OUT_DIR / f"smart_money_apr2026_chatgpt_review_{STAMP}.zip"
# Stable alias for prompt attachment name
OUT_ZIP_ALIAS = OUT_DIR / "smart_money_apr2026_chatgpt_review.zip"

PROMPT_SRC = REPO / "docs" / "trading" / "CHATGPT_SMART_MONEY_APR2026_REVIEW_PROMPT.md"
DELIVERABLES = [
    ("smart_money_apr_2026_digest.md", "deliverables/smart_money_apr_2026_digest.md"),
    ("smart_money_apr_2026_structured.json", "deliverables/smart_money_apr_2026_structured.json"),
]
EXTRACTED_DIR = FUNDS_DIR / "_extracted_text"


def _readme() -> str:
    return f"""Smart Money April 2026 — ChatGPT review package
Built: {datetime.now().isoformat(timespec="seconds")}
Report month: 2026-04

HOW TO USE
==========
1. New ChatGPT chat.
2. Attach: smart_money_apr2026_chatgpt_review.zip (or dated copy in this folder).
3. Paste full text of REVIEW_PROMPT.md (or: "Follow REVIEW_PROMPT.md in the zip").

CONTENTS
========
REVIEW_PROMPT.md                          — QA audit + fund landscape re-synthesis prompt
README.txt                                — This file
deliverables/smart_money_apr_2026_digest.md
deliverables/smart_money_apr_2026_structured.json
extracted_text/*.txt                      — Raw PDF text per fund file
extracted_text/*_tables.json              — pdfplumber tables
extracted_text/manifest.json
SOURCE_PDF_MANIFEST.txt                   — Original PDFs in source folder (not embedded)

SOURCE FOLDER (operator)
========================
{FUNDS_DIR}

REGENERATE ZIP
==============
  .venv\\Scripts\\python.exe -m scripts.reporting.build_smart_money_apr2026_chatgpt_zip
""".format(FUNDS_DIR=FUNDS_DIR)


def _pdf_manifest() -> str:
    lines = [
        "Source PDFs in folder (not included in zip binary):",
        f"Folder: {FUNDS_DIR}",
        "",
    ]
    if FUNDS_DIR.is_dir():
        for p in sorted(FUNDS_DIR.glob("*.pdf")):
            lines.append(f"  - {p.name}  ({p.stat().st_size:,} bytes)")
    else:
        lines.append("  (folder not found on build machine)")
    lines.append("")
    lines.append("April SSOT: all except vnh-investor-report-march-2026 (1).pdf (March 2026).")
    return "\n".join(lines)


def _add_file(zf: zipfile.ZipFile, src: Path, arc: str) -> None:
    if not src.is_file():
        print(f"SKIP missing: {src}")
        return
    zf.write(src, arcname=arc)
    print(f"  + {arc}")


def build() -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    missing: list[str] = []

    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        if PROMPT_SRC.is_file():
            _add_file(zf, PROMPT_SRC, "REVIEW_PROMPT.md")
        else:
            missing.append(str(PROMPT_SRC))

        zf.writestr("README.txt", _readme())
        print("  + README.txt")

        zf.writestr("SOURCE_PDF_MANIFEST.txt", _pdf_manifest())
        print("  + SOURCE_PDF_MANIFEST.txt")

        for local_name, arc in DELIVERABLES:
            src = FUNDS_DIR / local_name
            if src.is_file():
                _add_file(zf, src, arc)
            else:
                missing.append(str(src))

        if EXTRACTED_DIR.is_dir():
            for f in sorted(EXTRACTED_DIR.iterdir()):
                if f.is_file():
                    _add_file(zf, f, f"extracted_text/{f.name}")
        else:
            missing.append(str(EXTRACTED_DIR))

    # Stable symlink-like copy for prompt filename
    if OUT_ZIP_ALIAS != OUT_ZIP and OUT_ZIP.is_file():
        import shutil

        shutil.copy2(OUT_ZIP, OUT_ZIP_ALIAS)

    # Copy to source folder for operator convenience
    dest = FUNDS_DIR / OUT_ZIP.name
    if FUNDS_DIR.is_dir():
        import shutil

        shutil.copy2(OUT_ZIP, dest)
        shutil.copy2(OUT_ZIP, FUNDS_DIR / "smart_money_apr2026_chatgpt_review.zip")
        print(f"Copied -> {dest}")
        print(f"Copied -> {FUNDS_DIR / 'smart_money_apr2026_chatgpt_review.zip'}")

    # Copy prompt to funds folder
    if FUNDS_DIR.is_dir() and PROMPT_SRC.is_file():
        import shutil

        shutil.copy2(PROMPT_SRC, FUNDS_DIR / "CHATGPT_SMART_MONEY_APR2026_REVIEW_PROMPT.md")
        print(f"Copied prompt -> {FUNDS_DIR / 'CHATGPT_SMART_MONEY_APR2026_REVIEW_PROMPT.md'}")

    print(f"\nWrote {OUT_ZIP} ({OUT_ZIP.stat().st_size:,} bytes)")
    if missing:
        print("Missing:", *missing, sep="\n  ")
    return OUT_ZIP


if __name__ == "__main__":
    build()
