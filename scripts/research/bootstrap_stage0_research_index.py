"""
Bootstrap Stage 0 research index from raw_extract manifests + ChatGPT 2026-05-24 synthesis.

Usage:
  .venv\\Scripts\\python.exe scripts/research/bootstrap_stage0_research_index.py

Writes:
  data/research/stage0/research_index_2026-05-24.csv
  data/research/stage0/research_index_latest.csv
  data/research/intake/index/research_index.csv  (same rows — intake SSOT)
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BATCHES = (
    ("VCAP", "Vietcap", REPO / "data/intake/raw_extract/2026-05-24/manifest.json"),
    ("HSC", "HSC", REPO / "data/intake/raw_extract/2026-05-24-hsc/manifest.json"),
)
ASOF = "2026-05-24"
EXTRACTION_DATE = "2026-05-24"

DOC_TYPE_MAP = {
    "company_report": "earnings_note",
    "sector_report": "sector_report",
    "macro_report": "macro_strategy",
}

SECTOR_BY_TICKER: dict[str, str] = {
    "CTG": "Banks",
    "VCB": "Banks",
    "HDB": "Banks",
    "TPB": "Banks",
    "VIB": "Banks",
    "STB": "Banks",
    "HPG": "Steel",
    "HSG": "Steel",
    "NKG": "Steel",
    "KDH": "Real estate",
    "NLG": "Real estate",
    "NVL": "Real estate",
    "VGC": "Real estate",
    "DPG": "Real estate",
    "HDG": "Real estate",
    "DXG": "Real estate",
    "KBC": "Real estate",
    "PNJ": "Consumer / Retail",
    "FRT": "Consumer / Retail",
    "MWG": "Consumer / Retail",
    "MCH": "Consumer / Retail",
    "VNM": "Consumer / Retail",
    "DMX": "Consumer / Retail",
    "BSR": "Energy / Oil & Gas",
    "OIL": "Energy / Oil & Gas",
    "PVD": "Energy / Oil & Gas",
    "PVT": "Energy / Oil & Gas",
    "PLX": "Energy / Oil & Gas",
    "POW": "Utilities / Power",
    "REE": "Utilities / Power",
    "PC1": "Utilities / Power",
    "GEG": "Utilities / Power",
    "PGV": "Utilities / Power",
    "HVN": "Aviation / Logistics",
    "VJC": "Aviation / Logistics",
    "VTP": "Aviation / Logistics",
    "STK": "Textile",
    "VHC": "Seafood",
    "DPM": "Chemicals / Fertilizer",
    "DGC": "Chemicals / Fertilizer",
}

IMPROVED = frozenset(
    {"POW", "PNJ", "BSR", "PVD", "HPG", "CTG", "FRT", "PTB", "VCB", "HVN", "VJC"}
)
WEAKENED = frozenset(
    {"NKG", "STK", "DGC", "DPG", "HDG", "PLX", "VTP", "VHC", "KBC", "TPB", "VIB", "STB"}
)

CATALYST_SNIPPET: dict[str, str] = {
    "POW": "Q1 core NPAT ~3x YoY; ~50% FY forecast; project/AGM catalysts",
    "PNJ": "Q1 NPAT after MI +117% YoY; retail +22% YoY",
    "BSR": "Q1 profit from output growth and positive crack spread",
    "PVD": "Core NPAT after MI +3.7x YoY (drilling/well services)",
    "HPG": "Q1 revenue and steel margin improvement (dedupe VCAP_028/029)",
    "CTG": "NIM recovery; execution; asset quality",
    "FRT": "Long Chau growth; FPT Shop profit",
    "PTB": "Wood and RE beat; possible forecast upside",
    "VCB": "Strong credit growth and NIM improvement",
}

RISK_SNIPPET: dict[str, str] = {
    "NKG": "Weak Q1; operating loss; forecast downgrade risk",
    "STK": "Q1 net loss; weak volume; Unitex cost pressure",
    "DGC": "Q1 NPAT after MI -49% YoY; downgrade risk",
    "DPG": "Property sales below expectation",
    "HDG": "Infra 1 provision vs Charm Villas revenue timing",
    "PLX": "Q1 loss from inventory provision after price decline",
    "VTP": "NPAT after MI -44% YoY; fuel and SG&A",
    "VHC": "Profit below forecast; tariff/macro on US export",
    "KBC": "Q1 profit down on lower IP land handover despite backlog",
    "TPB": "NIM and asset-quality pressure",
    "VIB": "NIM decline; non-interest income mix",
    "STB": "Balance-sheet clean-up pressure on Q1 profit",
    "HVN": "Fuel cost risk despite strong Q1",
    "VJC": "Fuel cost risk despite strong Q1",
}

HEADER = [
    "source_id",
    "file_name",
    "source_type",
    "ticker",
    "sector",
    "source_date",
    "broker_or_source",
    "report_title",
    "extraction_date",
    "confidence",
    "thesis_impact",
    "watchlist_action",
    "key_catalyst",
    "key_risk",
    "linked_card_path",
    "status",
]


def _guess_source_type(filename: str, doc_type_guess: str) -> str:
    low = filename.lower()
    if "dhcd" in low or "agm" in low:
        return "agm_note"
    if "gap-go" in low or "management" in low:
        return "management_meeting"
    if "bcnganh" in low or "sector" in low or low.startswith("sf "):
        return "sector_report"
    if "traiphieu" in low or "capnhatvm" in low or "gmail" in low:
        return "macro_strategy"
    if "-mua" in low or "ur " in low:
        return "equity_research"
    if "kqkd" in low or "lnst" in low or "bao-cao-kqkd" in low:
        return "earnings_note"
    return DOC_TYPE_MAP.get(doc_type_guess, "other")


def _title_from_filename(name: str) -> str:
    stem = Path(name).stem.replace("_", " ")
    return stem[:120]


def _impact_action(ticker: str | None) -> tuple[str, str]:
    if not ticker:
        return "UNKNOWN", "NO_ACTION"
    t = ticker.upper()
    if t in IMPROVED:
        return "IMPROVED", "UPGRADE"
    if t in WEAKENED:
        return "WEAKENED", "DOWNGRADE"
    return "UNKNOWN", "NO_ACTION"


def _is_hpg_dup(filename: str) -> bool:
    return "hpg-kqkd" in filename.lower() and "(1)" in filename.lower()


def _ticker_from_entry(entry: dict, house_prefix: str) -> str:
    guess = (entry.get("ticker_guess") or "").strip().upper()
    fname = entry.get("source_filename", "")
    if house_prefix == "HSC":
        m = re.match(r"^(?:FN|CF|SF)[_\s]+([A-Z]{2,5})\b", fname, re.I)
        if m:
            return m.group(1).upper()
        m = re.search(r"\b([A-Z]{2,5})\s+(?:Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b", fname, re.I)
        if m:
            return m.group(1).upper()
    if guess in ("FN", "CF", "SF", "BC", "PET", "DMX"):
        return ""
    return guess


def build_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seq = 0
    hpg_primary_set = False

    for house_prefix, broker, manifest_path in BATCHES:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        for entry in data.get("files", []):
            seq += 1
            source_id = f"{house_prefix}_{seq:03d}"
            fname = entry.get("source_filename", "")
            ticker = _ticker_from_entry(entry, house_prefix)
            text_rel = entry.get("text_file", "").replace("\\", "/")

            if _is_hpg_dup(fname):
                status = "ARCHIVED"
                thesis, action = "UNCHANGED", "NO_ACTION"
                key_risk = "Likely duplicate of VCAP HPG report; do not double-count"
            elif ticker == "HPG" and hpg_primary_set:
                status = "ARCHIVED"
                thesis, action = "UNCHANGED", "NO_ACTION"
                key_risk = "Duplicate HPG extract; use single primary row"
            else:
                status = "RAW_EXTRACTED"
                thesis, action = _impact_action(ticker or None)
                key_risk = RISK_SNIPPET.get(ticker, "")

            if ticker == "HPG" and status == "RAW_EXTRACTED":
                hpg_primary_set = True

            rows.append(
                {
                    "source_id": source_id,
                    "file_name": fname,
                    "source_type": _guess_source_type(
                        fname, entry.get("doc_type_guess", "")
                    ),
                    "ticker": ticker,
                    "sector": SECTOR_BY_TICKER.get(ticker, ""),
                    "source_date": "",
                    "broker_or_source": broker,
                    "report_title": _title_from_filename(fname),
                    "extraction_date": EXTRACTION_DATE,
                    "confidence": "Medium",
                    "thesis_impact": thesis,
                    "watchlist_action": action,
                    "key_catalyst": CATALYST_SNIPPET.get(ticker, ""),
                    "key_risk": key_risk,
                    "linked_card_path": text_rel,
                    "status": status,
                }
            )
    return rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    rows = build_rows()
    stage0 = REPO / "data/research/stage0"
    dated = stage0 / "research_index_2026-05-24.csv"
    latest = stage0 / "research_index_latest.csv"
    intake = REPO / "data/research/intake/index/research_index.csv"

    write_csv(dated, rows)
    write_csv(latest, rows)
    write_csv(intake, rows)

    print(f"Wrote {len(rows)} rows:")
    print(f"  {dated.relative_to(REPO)}")
    print(f"  {latest.relative_to(REPO)}")
    print(f"  {intake.relative_to(REPO)}")
    archived = sum(1 for r in rows if r["status"] == "ARCHIVED")
    print(f"  archived/duplicate: {archived}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
