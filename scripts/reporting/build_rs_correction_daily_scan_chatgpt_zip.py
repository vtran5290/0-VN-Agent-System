"""
Build rs_correction_daily_scan_chatgpt_YYYYMMDD.zip for ChatGPT review.

Usage:
  .venv\\Scripts\\python.exe -m scripts.reporting.build_rs_correction_daily_scan_chatgpt_zip
"""
from __future__ import annotations

import zipfile
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
STAMP = datetime.now().strftime("%Y%m%d")
OUT_DIR = REPO / "outputs" / "review_packages"
OUT_ZIP = OUT_DIR / f"rs_correction_daily_scan_chatgpt_{STAMP}.zip"

FILES: list[tuple[str, str]] = [
    (
        "docs/trading/CHATGPT_RS_CORRECTION_DAILY_SCAN_REVIEW_PROMPT.md",
        "REVIEW_PROMPT.md",
    ),
    ("docs/research/VIN_EMA_CLOUD_BASELINE.md", "docs/VIN_EMA_CLOUD_BASELINE.md"),
    ("docs/trading/CLOUD_DAILY_REPORT_GUIDE.md", "docs/CLOUD_DAILY_REPORT_GUIDE.md"),
    ("docs/trading/CHATGPT_DISTRIBUTION_RISK_DAILY_SCAN_REVIEW_PROMPT.md", "docs/DISTRIBUTION_RISK_PROMPT_REFERENCE.md"),
    ("config/rs_correction_anchor.txt", "config/rs_correction_anchor.txt"),
    ("config/universe_liquid_adv50_2b.txt", "config/universe_liquid_adv50_2b.txt"),
    ("scripts/research/rs_correction_scan.py", "scripts/rs_correction_scan.py"),
    ("scripts/reporting/daily_scan_report.py", "scripts/reporting/daily_scan_report.py"),
    ("scripts/daily_scan_report.py", "scripts/daily_scan_report.py"),
    ("scripts/scan_ssot.py", "scripts/scan_ssot.py"),
    ("scripts/ingest/scan_ssot.py", "scripts/ingest/scan_ssot.py"),
    ("src/trading/reports/rs_correction_card.py", "src/trading/reports/rs_correction_card.py"),
    ("src/trading/reports/distribution_risk_card.py", "src/trading/reports/distribution_risk_card.py"),
    ("src/trading/reports/cloud_daily_report.py", "src/trading/reports/cloud_daily_report.py"),
    ("data/research/market_risk/rs_correction_latest.json", "outputs/rs_correction_latest.json"),
    ("data/research/market_risk/rs_correction_latest.csv", "outputs/rs_correction_latest.csv"),
    ("data/research/market_risk/distribution_risk_latest.json", "outputs/distribution_risk_latest.json"),
    ("data/decision/daily_scan.md", "outputs/daily_scan.md"),
    ("data/decision/daily_scan.json", "outputs/daily_scan.json"),
    ("data/decision/weekly_report.md", "outputs/weekly_report.md"),
    ("data/research/reports/cloud_daily_report_latest.md", "outputs/cloud_daily_report_latest.md"),
    ("data/research/reports/cloud_daily_report_latest.json", "outputs/cloud_daily_report_latest.json"),
    (
        "data/research/portfolio_optimization/missing_work/phase36_daily_scan_latest.csv",
        "outputs/phase36_daily_scan_latest.csv",
    ),
    ("tests/test_rs_correction_lens.py", "tests/test_rs_correction_lens.py"),
    ("tests/test_cloud_daily_report_distribution_risk.py", "tests/test_cloud_daily_report_distribution_risk.py"),
]


def _readme() -> str:
    return f"""RS Correction Lens + Daily Scan — ChatGPT review package
Built: {datetime.now().isoformat(timespec='seconds')}
Zip: {OUT_ZIP.name}

HOW TO USE
==========
1. New ChatGPT chat.
2. Upload this zip.
3. Paste FULL text of REVIEW_PROMPT.md.

REGENERATE
==========
  .venv\\Scripts\\python.exe scripts\\research\\rs_correction_scan.py
  .venv\\Scripts\\python.exe scripts\\reporting\\daily_scan_report.py
  .venv\\Scripts\\python.exe -m scripts.reporting.build_rs_correction_daily_scan_chatgpt_zip

NOT INCLUDED
============
- Full ohlcv parquet
- gitignored portfolio_state.json
"""


def build() -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest: list[str] = []

    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.txt", _readme())
        manifest.append("README.txt")

        for rel, arc in FILES:
            src = REPO / rel
            if src.is_file():
                zf.write(src, arc)
                manifest.append(arc)
            else:
                print(f"  skip missing: {rel}")

        lens_dir = REPO / "src" / "market" / "rs_correction_lens"
        if lens_dir.is_dir():
            for py in sorted(lens_dir.glob("*.py")):
                arc = f"src/market/rs_correction_lens/{py.name}"
                zf.write(py, arc)
                manifest.append(arc)

        zf.writestr("MANIFEST.txt", "\n".join(sorted(manifest)))

    print(f"Wrote {OUT_ZIP} ({OUT_ZIP.stat().st_size / 1024:.1f} KB, {len(manifest)} files)")
    return OUT_ZIP


if __name__ == "__main__":
    build()
