"""
Intake pipeline: inbox + manifest → sources, summaries, weekly_notes update.
Run: python -m src.ingest.run
Facts-first: summarize only what is in the file; no hallucination.
"""
from __future__ import annotations
import json
import re
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parents[2]
INBOX = REPO / "data" / "intake" / "inbox"
PROCESSED = REPO / "data" / "intake" / "processed"
REJECTED = REPO / "data" / "intake" / "rejected"
SOURCES = REPO / "data" / "sources"
SUMMARIES = REPO / "data" / "summaries"
MANIFEST_PATH = INBOX / "manifest.json"
NOTES_PATH = REPO / "data" / "raw" / "weekly_notes.json"

TYPE_TO_SOURCE = {
    "macro_report": "macro",
    "sector_report": "sector",
    "company_report": "company",
    "policy_report": "policy",
}
MAX_EXTRACT_CHARS = 2000


def extract_pdf(path: Path) -> Optional[str]:
    try:
        from pypdf import PdfReader
        reader = PdfReader(path)
        parts = []
        for i, page in enumerate(reader.pages):
            if i >= 20:
                break
            t = page.extract_text()
            if t:
                parts.append(t)
        return "\n".join(parts).strip() if parts else None
    except Exception as e:
        logger.warning("PDF extract failed for %s: %s", path.name, e)
        return None


def extract_docx(path: Path) -> Optional[str]:
    try:
        from docx import Document
        doc = Document(path)
        return "\n".join(p.text for p in doc.paragraphs if p.text).strip() or None
    except Exception as e:
        logger.warning("DOCX extract failed for %s: %s", path.name, e)
        return None


def extract_xlsx(path: Path) -> Optional[str]:
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        parts = []
        for sheet in wb.worksheets:
            for row in sheet.iter_rows(max_row=500, values_only=True):
                line = " | ".join(str(c) if c is not None else "" for c in row)
                if line.strip():
                    parts.append(line)
        return "\n".join(parts).strip() if parts else None
    except Exception as e:
        logger.warning("XLSX extract failed for %s: %s", path.name, e)
        return None


def extract_text(path: Path) -> Optional[str]:
    suf = path.suffix.lower()
    if suf == ".pdf":
        return extract_pdf(path)
    if suf in (".docx", ".doc"):
        return extract_docx(path)
    if suf in (".xlsx", ".xls"):
        return extract_xlsx(path)
    if suf == ".txt":
        try:
            return path.read_text(encoding="utf-8", errors="replace").strip()
        except Exception as e:
            logger.warning("TXT read failed for %s: %s", path.name, e)
            return None
    logger.warning("Unsupported extension: %s", suf)
    return None


def text_to_bullets(text: str, max_chars: int = MAX_EXTRACT_CHARS) -> List[str]:
    if not text:
        return []
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        text = text[:max_chars] + "…"
    lines = [ln.strip() for ln in text.split(".") if ln.strip()]
    return [f"- {ln}." for ln in lines[:80]]


def summary_md(entry: Dict[str, Any], bullets: List[str], parse_ok: bool) -> str:
    title = entry.get("filename", "Unknown")
    typ = entry.get("type", "")
    source = entry.get("source", entry.get("firm", ""))
    date_val = entry.get("date", "")
    tags = entry.get("tags", [])
    sector = entry.get("sector", "")
    ticker = entry.get("ticker", "")
    lines = [
        f"# {title}",
        "",
        f"- **Type:** {typ} | **Source:** {source} | **Date:** {date_val}",
    ]
    if sector:
        lines.append(f"- **Sector:** {sector}")
    if ticker:
        lines.append(f"- **Ticker:** {ticker}")
    if tags:
        lines.append(f"- **Tags:** {', '.join(tags)}")
    lines.append("")
    if not parse_ok:
        lines.append("## Status")
        lines.append("- Parse failed or unsupported format; file moved to rejected/.")
        return "\n".join(lines)
    lines.append("## Extracted facts (no interpretation)")
    for b in bullets:
        lines.append(b)
    return "\n".join(lines)


def load_manifest() -> List[Dict[str, Any]]:
    if not MANIFEST_PATH.exists():
        return []
    raw = MANIFEST_PATH.read_text(encoding="utf-8")
    data = json.loads(raw)
    return data if isinstance(data, list) else []


def save_manifest(entries: List[Dict[str, Any]]) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def load_weekly_notes() -> Dict[str, Any]:
    if not NOTES_PATH.exists():
        return {}
    return json.loads(NOTES_PATH.read_text(encoding="utf-8"))


def save_weekly_notes(notes: Dict[str, Any]) -> None:
    NOTES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(NOTES_PATH, "w", encoding="utf-8") as f:
        json.dump(notes, f, ensure_ascii=False, indent=2)


def run() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    REJECTED.mkdir(parents=True, exist_ok=True)
    for sub in ("macro", "policy", "sector", "company"):
        (SOURCES / sub).mkdir(parents=True, exist_ok=True)
        (SUMMARIES / sub).mkdir(parents=True, exist_ok=True)

    entries = load_manifest()
    if not entries:
        logger.info("No manifest.json in inbox or empty list; nothing to do.")
        return

    notes = load_weekly_notes()
    notes.setdefault("intake_takeaways", [])

    now_ym = datetime.now().strftime("%Y-%m")
    updated_manifest = []

    for entry in entries:
        if entry.get("processed"):
            updated_manifest.append(entry)
            continue
        filename = entry.get("filename")
        if not filename:
            updated_manifest.append({**entry, "processed": True, "error": "missing filename"})
            continue
        src_path = INBOX / filename
        if not src_path.is_file():
            logger.warning("File not found: %s", src_path)
            updated_manifest.append({**entry, "processed": True, "error": "file not found"})
            continue

        typ = entry.get("type", "company_report")
        source_folder = TYPE_TO_SOURCE.get(typ, "company")
        dest_dir = SOURCES / source_folder / now_ym
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / filename
        sum_dir = SUMMARIES / source_folder
        sum_path = sum_dir / (src_path.stem + ".md")

        text = extract_text(src_path)
        parse_ok = bool(text and text.strip())
        bullets = text_to_bullets(text, MAX_EXTRACT_CHARS) if text else []
        md = summary_md(entry, bullets, parse_ok)

        if not parse_ok:
            rejected_path = REJECTED / filename
            try:
                import shutil
                shutil.copy2(src_path, rejected_path)
                src_path.unlink()
            except Exception as e:
                logger.warning("Could not move to rejected: %s", e)
            sum_path = SUMMARIES / source_folder / (src_path.stem + "_parse_failed.md")
            sum_path.write_text(md, encoding="utf-8")
            notes["intake_takeaways"].append({
                "filename": filename,
                "type": typ,
                "date": entry.get("date"),
                "tags": entry.get("tags", []),
                "file_link": str(rejected_path),
                "summary": "Parse failed; see summary file.",
            })
            updated_manifest.append({**entry, "processed": True, "error": "parse_failed"})
            continue

        try:
            import shutil
            shutil.copy2(src_path, dest_path)
            processed_path = PROCESSED / filename
            shutil.move(str(src_path), str(processed_path))
        except Exception as e:
            logger.warning("Could not move to sources/processed: %s", e)
            dest_path = src_path  # leave in inbox

        sum_path.write_text(md, encoding="utf-8")
        notes["intake_takeaways"].append({
            "filename": filename,
            "type": typ,
            "date": entry.get("date"),
            "tags": entry.get("tags", []),
            "file_link": str(dest_path),
            "summary_bullets": bullets[:15],
        })
        updated_manifest.append({**entry, "processed": True})

    save_manifest(updated_manifest)
    save_weekly_notes(notes)
    logger.info("Ingest done. Processed %s entries; weekly_notes updated.", len(entries))


if __name__ == "__main__":
    run()
