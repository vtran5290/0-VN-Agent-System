"""
Build distribution_risk_daily_scan_chatgpt_YYYYMMDD.zip for ChatGPT review.

Usage:
  python -m scripts.reporting.build_distribution_risk_daily_scan_chatgpt_zip
"""
from __future__ import annotations

import zipfile
from datetime import datetime
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
STAMP = datetime.now().strftime("%Y%m%d")
OUT_DIR = REPO / "outputs" / "review_packages"
OUT_ZIP = OUT_DIR / f"distribution_risk_daily_scan_chatgpt_{STAMP}.zip"

# (repo_relative, zip_path) — skip missing with warning
FILES: list[tuple[str, str]] = [
    (
        "docs/trading/CHATGPT_DISTRIBUTION_RISK_DAILY_SCAN_REVIEW_PROMPT.md",
        "REVIEW_PROMPT.md",
    ),
    ("docs/trading/ANALYST_CONTEXT_20260520.md", "ANALYST_CONTEXT_20260520.md"),
    ("docs/trading/CLOUD_DAILY_REPORT_GUIDE.md", "docs/CLOUD_DAILY_REPORT_GUIDE.md"),
    ("docs/research/VIN_EMA_CLOUD_BASELINE.md", "docs/VIN_EMA_CLOUD_BASELINE.md"),
    ("docs/OPERATING_BACKBONE_PARETO.md", "docs/OPERATING_BACKBONE_PARETO.md"),
    ("scripts/research/run_distribution_risk_lens.py", "scripts/run_distribution_risk_lens.py"),
    ("scripts/maintenance/refresh_eod_20260519.py", "scripts/refresh_eod_20260519.py"),
    ("scripts/reporting/daily_scan_report.py", "scripts/reporting/daily_scan_report.py"),
    ("scripts/daily_scan_report.py", "scripts/daily_scan_report.py"),
    ("scripts/scan_ssot.py", "scripts/scan_ssot.py"),
    ("scripts/ingest/__init__.py", "scripts/ingest/__init__.py"),
    ("scripts/ingest/scan_ssot.py", "scripts/ingest/scan_ssot.py"),
    ("src/trading/portfolio_state.py", "src/trading/portfolio_state.py"),
    ("src/trading/reports/cloud_daily_report.py", "src/trading/reports/cloud_daily_report.py"),
    ("src/trading/reports/distribution_risk_card.py", "src/trading/reports/distribution_risk_card.py"),
    ("monitor_distribution_risk.cmd", "monitor_distribution_risk.cmd"),
    ("data/research/market_risk/distribution_risk_latest.json", "outputs/distribution_risk_latest.json"),
    (
        "data/research/market_risk/distribution_days_probability_table.csv",
        "outputs/distribution_days_probability_table.csv",
    ),
    (
        "data/research/market_risk/distribution_days_event_study.csv",
        "outputs/distribution_days_event_study.csv",
    ),
    (
        "data/research/market_risk/distribution_days_warning_backtest.csv",
        "outputs/distribution_days_warning_backtest.csv",
    ),
    ("data/decision/daily_scan.md", "outputs/daily_scan.md"),
    ("data/decision/daily_scan.json", "outputs/daily_scan.json"),
    ("data/research/reports/cloud_daily_report_latest.md", "outputs/cloud_daily_report_latest.md"),
    ("data/research/reports/cloud_daily_report_latest.json", "outputs/cloud_daily_report_latest.json"),
    (
        "data/research/portfolio_optimization/missing_work/phase36_daily_scan_latest.csv",
        "outputs/phase36_daily_scan_latest.csv",
    ),
    (
        "data/research/portfolio_optimization/missing_work/phase36_daily_scan_20260520.csv",
        "outputs/phase36_daily_scan_20260520.csv",
    ),
    ("tests/test_distribution_days.py", "tests/test_distribution_days.py"),
    ("tests/test_distribution_risk_lens.py", "tests/test_distribution_risk_lens.py"),
    (
        "tests/test_cloud_daily_report_distribution_risk.py",
        "tests/test_cloud_daily_report_distribution_risk.py",
    ),
    ("tests/test_cloud_daily_report.py", "tests/test_cloud_daily_report.py"),
    ("tests/test_portfolio_state.py", "tests/test_portfolio_state.py"),
]

LENS_GLOB = "src/market/distribution_risk_lens/*.py"


def _readme() -> str:
    return f"""Distribution Risk Lens + Daily Scan — ChatGPT review package
Built: {datetime.now().isoformat(timespec='seconds')}
Zip: {OUT_ZIP.name}

HOW TO USE
==========
1. Start a new ChatGPT chat.
2. Upload this zip.
3. Paste the FULL text of REVIEW_PROMPT.md (or: "Follow REVIEW_PROMPT.md in the zip").
4. Optional: open outputs/cloud_daily_report_latest.md and outputs/daily_scan.md locally.

REGENERATE
==========
  .venv\\Scripts\\python.exe -m scripts.reporting.build_distribution_risk_daily_scan_chatgpt_zip

REBUILD PIPELINE (EOD)
======================
  See REVIEW_PROMPT.md section "Commands (operator regenerate)"

FORWARD RETURNS FILE
==================
- outputs/distribution_days_forward_returns_2024plus.csv = subset from 2024-01-01 (not full 2012 file)
- outputs/analyst_historical_buckets_20260520.csv = reproducibility summary for ANALYST_CONTEXT filters

NOT INCLUDED (by design)
========================
- data/trading/live/portfolio_state.json (gitignored local SSoT)
- Full distribution_days_forward_returns.csv from 2012 (too large for zip)
- Full ohlcv_panel parquet (too large)
- All timestamped cloud_daily_report_*.html history
"""


def _vnindex_recent_csv() -> str:
    path = REPO / "minervini_backtest" / "data" / "raw" / "VNINDEX.csv"
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    for span in (10, 20, 50):
        ema = df["close"].ewm(span=span, adjust=False).mean()
        df[f"ema{span}"] = ema
        df[f"pct_above_ema{span}"] = (df["close"] / ema - 1) * 100
        df[f"above_ema{span}"] = (df["close"] > ema).astype(int)
    df["vol_ma20"] = df["volume"].rolling(20, min_periods=1).mean()
    df["vol_ratio"] = df["volume"] / df["vol_ma20"]
    df["close_loc"] = (df["close"] - df["low"]) / (df["high"] - df["low"]).replace(0, pd.NA)
    df = df.tail(10)
    return df.to_csv(index=False)


def _forward_returns_excerpt() -> str:
    path = REPO / "data/research/market_risk/distribution_days_forward_returns.csv"
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    sub = df[df["date"] >= pd.Timestamp("2024-01-01")]
    return sub.to_csv(index=False)


def _analyst_historical_buckets_csv() -> str:
    """Reproducibility table for ANALYST_CONTEXT filter labels (vnindex_raw, pre-2026-05-20)."""
    path = REPO / "data/research/market_risk/distribution_days_forward_returns.csv"
    df = pd.read_csv(path)
    df = df[df["index_view"] == "vnindex_raw"].copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    c = df["close"]
    for span in (10, 20, 50):
        ema = c.ewm(span=span, adjust=False).mean()
        df[f"above_ema{span}"] = (df["close"] > ema).astype(int)
    df["vol_ma20"] = df["volume"].rolling(20).mean()
    df["vol_ratio"] = df["volume"] / df["vol_ma20"]
    df["close_loc"] = (df["close"] - df["low"]) / (df["high"] - df["low"])
    df["range_pct"] = (df["high"] - df["low"]) / df["close"].shift(1) * 100
    df["ret1d"] = c.pct_change()
    df["prev_ret"] = df["ret1d"].shift(1)
    cutoff = pd.Timestamp("2026-05-20")
    v = df[df["date"] < cutoff]

    buckets: list[dict] = []

    def _summ(label: str, mask: pd.Series) -> None:
        sub = v[mask]
        row: dict = {"filter_label": label, "n": len(sub)}
        for h, col in [
            (5, "fwd_ret_5d"),
            (10, "fwd_ret_10d"),
            (25, "fwd_ret_25d"),
            (75, "fwd_ret_75d"),
            (100, "fwd_ret_100d"),
        ]:
            s = sub[col].dropna()
            if len(s):
                row[f"mean_{col}"] = float(s.mean())
                row[f"p_neg_{col}"] = float((s < 0).mean())
        buckets.append(row)

    _summ(
        "prior_down_then_strong_close_above_ema10_20",
        (v["prev_ret"] <= -0.005)
        & (v["close_loc"] >= 0.85)
        & (v["vol_ratio"] >= 1.2)
        & (v["above_ema10"] == 1)
        & (v["above_ema20"] == 1),
    )
    _summ(
        "day_after_dist_strong_close_above_ema20_50",
        (v["dist_day_flag"].shift(1) == 1)
        & (v["close_loc"] >= 0.85)
        & (v["above_ema20"] == 1)
        & (v["above_ema50"] == 1),
    )
    _summ(
        "above_ema10_20_50_dist10_2_3",
        (v["above_ema10"] == 1)
        & (v["above_ema20"] == 1)
        & (v["above_ema50"] == 1)
        & (v["dist_count_10d"].between(2, 3)),
    )
    return pd.DataFrame(buckets).to_csv(index=False)


def build() -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest: list[str] = []

    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        readme = _readme()
        zf.writestr("README.txt", readme)
        manifest.append("README.txt")

        for rel, arc in FILES:
            src = REPO / rel
            if src.is_file():
                zf.write(src, arc)
                manifest.append(arc)
            else:
                print(f"  skip missing: {rel}")

        lens_dir = REPO / "src" / "market" / "distribution_risk_lens"
        if lens_dir.is_dir():
            zf.write(lens_dir / "__init__.py", "src/market/distribution_risk_lens/__init__.py")
            manifest.append("src/market/distribution_risk_lens/__init__.py")
            for py in sorted(lens_dir.glob("*.py")):
                if py.name == "__init__.py":
                    continue
                arc = f"src/market/distribution_risk_lens/{py.name}"
                zf.write(py, arc)
                manifest.append(arc)

        market_init = REPO / "src" / "market" / "__init__.py"
        if market_init.is_file():
            zf.write(market_init, "src/market/__init__.py")
            manifest.append("src/market/__init__.py")

        zf.writestr("outputs/VNINDEX_recent_5d.csv", _vnindex_recent_csv())
        manifest.append("outputs/VNINDEX_recent_5d.csv")

        fwd_path = REPO / "data/research/market_risk/distribution_days_forward_returns.csv"
        if fwd_path.is_file():
            zf.writestr(
                "outputs/distribution_days_forward_returns_2024plus.csv",
                _forward_returns_excerpt(),
            )
            manifest.append("outputs/distribution_days_forward_returns_2024plus.csv")
            zf.writestr(
                "outputs/analyst_historical_buckets_20260520.csv",
                _analyst_historical_buckets_csv(),
            )
            manifest.append("outputs/analyst_historical_buckets_20260520.csv")

        zf.writestr("MANIFEST.txt", "\n".join(sorted(manifest)))

    size_kb = OUT_ZIP.stat().st_size / 1024
    print(f"Wrote {OUT_ZIP} ({size_kb:.1f} KB, {len(manifest)} files)")
    return OUT_ZIP


if __name__ == "__main__":
    build()
