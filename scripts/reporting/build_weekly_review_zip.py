"""
Build vn_weekly_report_command_center_review.zip for external AI review.

Usage:
  python -m scripts.reporting.build_weekly_review_zip
"""
from __future__ import annotations

import json
import zipfile
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / "outputs" / "review_packages"
ZIP_PATH = OUT_DIR / "vn_weekly_report_command_center_review.zip"

# (repo_relative_path, zip_internal_path)
FILES: list[tuple[str, str]] = [
    ("docs/reporting/WEEKLY_REPORT_COMMAND_CENTER_REVIEW_PROMPT.md", "REVIEW_PROMPT.md"),
    ("docs/reporting/WEEKLY_REPORT_STRATEGY_SYNC.md", "docs/reporting/WEEKLY_REPORT_STRATEGY_SYNC.md"),
    ("docs/trading/REAL_CAPITAL_READINESS.md", "docs/trading/REAL_CAPITAL_READINESS.md"),
    ("docs/research/VIN_EMA_CLOUD_BASELINE.md", "docs/research/VIN_EMA_CLOUD_BASELINE.md"),
    ("docs/ema_cloud_strategy_spec.md", "docs/ema_cloud_strategy_spec.md"),
    ("docs/WEEKLY_FULL_FETCH.md", "docs/WEEKLY_FULL_FETCH.md"),
    ("scripts/ingest/portfolio_decision_enrich.py", "scripts/ingest/portfolio_decision_enrich.py"),
    ("scripts/ingest/normalize_weekly_report.py", "scripts/ingest/normalize_weekly_report.py"),
    ("scripts/ingest/run_weekly_update.py", "scripts/ingest/run_weekly_update.py"),
    ("scripts/reporting/render_weekly_report.py", "scripts/reporting/render_weekly_report.py"),
    ("templates/weekly_report.html.j2", "templates/weekly_report.html.j2"),
    ("templates/weekly_report_portfolio_blocks.j2", "templates/weekly_report_portfolio_blocks.j2"),
    ("tests/test_portfolio_command_center_report.py", "tests/test_portfolio_command_center_report.py"),
    ("data/decision/weekly_report.md", "samples/weekly_report.md"),
    ("reports/latest/index.html", "samples/index.html"),
    (
        "data/research/portfolio_optimization/missing_work/phase36_daily_scan_schema.csv",
        "data/phase36_daily_scan_schema.csv",
    ),
    (
        "data/research/portfolio_optimization/missing_work/phase36_daily_scan_sample.csv",
        "data/phase36_daily_scan_sample.csv",
    ),
    ("data/master/sector_map.csv", "data/sector_map.csv"),
    ("config/watchlist.txt", "config/watchlist.txt"),
]

OPTIONAL = [
    ("data/processed/weekly_report.json", "samples/weekly_report_full.json"),
    ("data/raw/manual_inputs.json", "samples/manual_inputs.json"),
    ("data/alerts/sell_signals.json", "samples/sell_signals.json"),
    ("data/raw/tech_status.json", "samples/tech_status.json"),
    ("data/raw/current_positions_derived.json", "samples/current_positions_derived.json"),
    ("data/decision/allocation_plan.json", "samples/allocation_plan.json"),
    ("data/state/regime_state.json", "samples/regime_state.json"),
]


def _trimmed_payload(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    keys = [
        "metadata",
        "regime_engine",
        "portfolio_command_center",
        "regime_rules",
        "wow_since_last_week",
        "position_decisions",
        "portfolio_risk_summary",
        "sector_exposure",
        "watchlist_board",
        "decision_layer",
        "decision_review",
        "data_freshness",
        "execution_monitoring",
        "probability_allocation",
    ]
    out = {k: raw.get(k) for k in keys if k in raw}
    # truncate large row lists
    for block in ("position_decisions", "watchlist_board"):
        if block in out and isinstance(out[block], dict):
            rows = out[block].get("rows") or out[block].get("candidates")
            if isinstance(rows, list) and len(rows) > 5:
                key = "rows" if "rows" in out[block] else "candidates"
                out[block] = {**out[block], key: rows[:5], f"{key}_truncated": len(rows)}
    return out


def build() -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    readme = OUT_DIR / "README.txt"
    readme.write_text(
        "VN Weekly Report — Portfolio Command Center review package\n"
        f"Built: {datetime.now().isoformat(timespec='seconds')}\n\n"
        "1. Open REVIEW_PROMPT.md — copy prompt into external AI\n"
        "2. Attach this zip (or vn_weekly_report_command_center_review.zip)\n"
        "3. Open samples/index.html in a browser for visual check\n"
        "4. Read docs/reporting/WEEKLY_REPORT_STRATEGY_SYNC.md for B_cloud20_100 alignment plan\n",
        encoding="utf-8",
    )

    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(readme, "README.txt")
        for rel, arc in FILES:
            src = REPO / rel
            if src.exists():
                zf.write(src, arc)
        for rel, arc in OPTIONAL:
            src = REPO / rel
            if src.exists():
                zf.write(src, arc)
        proc = REPO / "data/processed/weekly_report.json"
        if proc.exists():
            trimmed = json.dumps(_trimmed_payload(proc), indent=2, ensure_ascii=False)
            zf.writestr("samples/processed_weekly_report_keys.json", trimmed)

    print(f"Wrote {ZIP_PATH} ({ZIP_PATH.stat().st_size / 1024:.1f} KB)")
    return ZIP_PATH


if __name__ == "__main__":
    build()
