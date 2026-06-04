"""
Batch-extract full text from PDFs for research / knowledge intake.

Usage:
  .venv\\Scripts\\python.exe scripts/ingest/batch_extract_pdfs.py ^
    --source "C:\\Users\\LOLII\\Downloads\\Reports to extract" ^
    --out data/intake/raw_extract/2026-05-24

Writes one .txt per PDF, manifest.json, and INDEX.md. Does not truncate text.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

def _slug(name: str, max_len: int = 120) -> str:
    stem = Path(name).stem
    s = re.sub(r"[^\w\-.]+", "_", stem, flags=re.UNICODE)
    s = re.sub(r"_+", "_", s).strip("_")
    return (s[:max_len] if len(s) > max_len else s) or "document"


def _guess_ticker(filename: str) -> str | None:
    stem = Path(filename).stem
    m = re.match(r"^([A-Za-z]{2,5})[-_]", stem)
    if m:
        return m.group(1).upper()
    m = re.match(r"^([A-Za-z]{2,5})\d", stem)
    if m:
        return m.group(1).upper()
    return None


def _guess_doc_type(filename: str) -> str:
    low = filename.lower()
    if any(x in low for x in ("bcnganh", "sector", "nganh")):
        return "sector_report"
    if "bctraiphieu" in low or "bond" in low:
        return "macro_report"
    if any(x in low for x in ("capnhatvm", "gmail", "macro")):
        return "macro_report"
    if any(x in low for x in ("dhcd", "gap-go", "bccongty")):
        return "company_report"
    if any(x in low for x in ("kqkd", "bao-cao-kqkd", "lnst")):
        return "company_report"
    if "-mua" in low:
        return "company_report"
    return "company_report"


def extract_full_pdf(path: Path) -> tuple[str | None, int, str | None]:
    try:
        from pypdf import PdfReader

        reader = PdfReader(path)
        page_count = len(reader.pages)
        parts: list[str] = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                parts.append(t)
        text = "\n".join(parts).strip()
        if not text:
            return None, page_count, "no_text_extracted"
        return text, page_count, None
    except Exception as e:
        return None, 0, str(e)


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch extract PDF text for knowledge intake")
    parser.add_argument("--source", type=Path, required=True, help="Folder containing PDFs")
    parser.add_argument("--out", type=Path, required=True, help="Output folder under repo")
    parser.add_argument("--copy-pdfs", action="store_true", help="Copy PDFs into out/pdfs/")
    args = parser.parse_args()

    source: Path = args.source
    out: Path = REPO / args.out if not args.out.is_absolute() else args.out
    out.mkdir(parents=True, exist_ok=True)
    txt_dir = out / "text"
    txt_dir.mkdir(parents=True, exist_ok=True)
    if args.copy_pdfs:
        (out / "pdfs").mkdir(parents=True, exist_ok=True)

    pdfs = sorted(source.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs in {source}")
        return 1

    manifest: list[dict] = []
    index_lines = [
        "# PDF text extraction index",
        "",
        f"- **Source folder:** `{source}`",
        f"- **Extracted at:** {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"- **Files:** {len(pdfs)}",
        "",
        "| # | Ticker | Type | Pages | Chars | Status | Text file |",
        "|---|--------|------|-------|-------|--------|-----------|",
    ]

    ok = 0
    failed = 0
    used_slugs: set[str] = set()
    for i, pdf_path in enumerate(pdfs, 1):
        slug = _slug(pdf_path.name)
        if slug in used_slugs:
            slug = f"{slug[:100]}_{i:02d}"
        used_slugs.add(slug)
        txt_path = txt_dir / f"{slug}.txt"
        ticker = _guess_ticker(pdf_path.name)
        doc_type = _guess_doc_type(pdf_path.name)

        text, pages, err = extract_full_pdf(pdf_path)
        status = "ok" if text else "failed"
        if text:
            txt_path.write_text(text, encoding="utf-8")
            ok += 1
        else:
            failed += 1

        if args.copy_pdfs:
            import shutil

            shutil.copy2(pdf_path, out / "pdfs" / pdf_path.name)

        entry = {
            "index": i,
            "source_filename": pdf_path.name,
            "source_path": str(pdf_path),
            "text_file": str(txt_path.relative_to(REPO)).replace("\\", "/"),
            "ticker_guess": ticker,
            "doc_type_guess": doc_type,
            "page_count": pages,
            "char_count": len(text) if text else 0,
            "status": status,
            "error": err,
        }
        manifest.append(entry)
        index_lines.append(
            f"| {i} | {ticker or '—'} | {doc_type} | {pages} | {entry['char_count']} | {status} | `{entry['text_file']}` |"
        )
        line = f"[{i}/{len(pdfs)}] {status:6} {pdf_path.name[:70]}"
        try:
            print(line)
        except UnicodeEncodeError:
            print(line.encode("ascii", errors="replace").decode("ascii"))

    manifest_path = out / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "extracted_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "source_folder": str(source),
                "total": len(pdfs),
                "ok": ok,
                "failed": failed,
                "files": manifest,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (out / "INDEX.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")

    print(f"\nDone: {ok} ok, {failed} failed -> {out}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
