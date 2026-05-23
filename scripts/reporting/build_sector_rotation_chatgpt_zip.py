"""
Build vn_sector_rotation_index_chatgpt_review.zip for ChatGPT third-opinion review.

Usage:
  .venv\\Scripts\\python.exe -m scripts.reporting.build_sector_rotation_chatgpt_zip
"""
from __future__ import annotations

import json
import zipfile
from datetime import datetime
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / "outputs" / "review_packages"
OUT_ZIP = OUT_DIR / "vn_sector_rotation_index_chatgpt_review.zip"
ASOF = "2026-05-20"

BUCKETS = {
    "VIN": ["VIC", "VHM", "VRE", "VPL"],
    "BDS_mid": ["NVL", "PDR", "DXG", "KDH", "DIG", "CEO", "NLG", "HDG", "TCH", "NRC"],
    "FPT": ["FPT"],
    "Energy": ["GAS", "PLX", "PVS", "OIL", "PVD", "BSR", "POW", "PC1"],
    "Securities": ["SSI", "HCM", "VND", "VCI", "SHS", "ORS", "VIX"],
    "Banks": ["VCB", "BID", "CTG", "TCB", "MBB", "ACB", "STB", "VPB", "HDB", "TPB", "MSB", "EIB"],
    "NQ79_policy": ["VGI", "SAB", "L40", "VCG", "REE", "MSN"],
}

FILES = [
    (
        "docs/reporting/CHATGPT_SECTOR_ROTATION_INDEX_REVIEW_PROMPT.md",
        "REVIEW_PROMPT.md",
    ),
    (
        "review_outputs/sector_rotation_index_handoff_20260520.md",
        "handoff/sector_rotation_index_handoff_20260520.md",
    ),
    ("docs/research/VIN_EMA_CLOUD_BASELINE.md", "docs/VIN_EMA_CLOUD_BASELINE.md"),
    (
        "data/research/market_risk/distribution_risk_latest.json",
        "data/distribution_risk_latest.json",
    ),
    (
        "data/research/portfolio_optimization/missing_work/phase36_daily_scan_latest.csv",
        "data/phase36_daily_scan_latest.csv",
    ),
    ("data/research/reports/cloud_daily_report_latest.md", "data/cloud_daily_report_latest.md"),
    ("data/research/reports/cloud_daily_report_latest.json", "data/cloud_daily_report_latest.json"),
    ("data/decision/daily_scan.md", "data/daily_scan.md"),
    ("data/raw/current_positions_derived.json", "data/current_positions_derived.json"),
    ("data/raw/current_positions_digest.md", "data/current_positions_digest.md"),
    ("data/raw/tech_status.json", "data/tech_status.json"),
    (
        "data/research/intraday/phase36_intraday_scan_latest_meta.json",
        "data/intraday_scan_latest_meta.json",
    ),
    (
        "data/research/intraday/phase36_intraday_scan_latest.md",
        "data/intraday_scan_latest.md",
    ),
    ("artifacts/vnindex_ex_vin_result.json", "data/vnindex_ex_vin_result_snapshot.json"),
    (
        "data/research/vnindex_low_dist_forward_returns_ex_vin.json",
        "data/vnindex_low_dist_forward_returns_ex_vin.json",
    ),
]


def _sector_returns_csv() -> str:
    panel = REPO / "data/research/ema_cloud/ohlcv_panel_ext2012.parquet"
    if not panel.exists():
        return "symbol,bucket,date,close,ret_1d_pct\n"
    syms = sorted({s for v in BUCKETS.values() for s in v})
    df = pd.read_parquet(panel)
    sub = df[df["symbol"].isin(syms)].copy()
    sub["date"] = pd.to_datetime(sub["date"])
    rows: list[dict] = []
    sym_to_bucket = {s: b for b, lst in BUCKETS.items() for s in lst}
    for sym, g in sub.groupby("symbol"):
        g = g.sort_values("date").tail(2)
        if len(g) < 2:
            continue
        c0, c1 = float(g.iloc[-2]["close"]), float(g.iloc[-1]["close"])
        d = g.iloc[-1]["date"].strftime("%Y-%m-%d")
        rows.append(
            {
                "symbol": sym,
                "bucket": sym_to_bucket.get(sym, ""),
                "date": d,
                "close": c1,
                "ret_1d_pct": round((c1 / c0 - 1) * 100, 2),
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return "symbol,bucket,date,close,ret_1d_pct\n"
    return out.sort_values(["bucket", "ret_1d_pct"]).to_csv(index=False)


def _vnindex_recent_csv() -> str:
    path = REPO / "data/fireant_exports/index_ohlcv/market/VNINDEX.csv"
    if not path.exists():
        return "date,open,high,low,close,volume\n"
    vn = pd.read_csv(path)
    vn["date"] = pd.to_datetime(vn["date"])
    tail = vn.sort_values("date").tail(30)
    return tail.to_csv(index=False)


def _readme() -> str:
    return f"""VN Sector Rotation & Index Leadership — ChatGPT review package
Built: {datetime.now().isoformat(timespec='seconds')}
As-of: {ASOF}

HOW TO USE
==========
1. New ChatGPT chat.
2. Attach: vn_sector_rotation_index_chatgpt_review.zip
3. Paste full text of REVIEW_PROMPT.md (or: "Follow REVIEW_PROMPT.md in the zip").

CONTENTS
========
REVIEW_PROMPT.md              — Copy-paste prompt
handoff/sector_rotation_*.md  — Cursor FACTS + open questions
data/sector_bucket_returns_*  — 1D returns by bucket (FireAnt panel)
data/vnindex_ohlcv_recent.csv — VNINDEX last 30 sessions
data/phase36_daily_scan_*     — EOD scan SSOT
data/distribution_risk_*      — Dist days / ex-VIN lens
data/current_positions_*      — User portfolio context

REGENERATE ZIP
==============
  .venv\\Scripts\\python.exe -m scripts.reporting.build_sector_rotation_chatgpt_zip
"""


def build() -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    readme = OUT_DIR / "README_SECTOR_ROTATION_CHATGPT.txt"
    readme.write_text(_readme(), encoding="utf-8")

    manifest: list[str] = []
    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(readme, "README.txt")
        manifest.append("README.txt")

        zf.writestr(f"data/sector_bucket_returns_{ASOF.replace('-', '')}.csv", _sector_returns_csv())
        manifest.append(f"data/sector_bucket_returns_{ASOF.replace('-', '')}.csv")

        zf.writestr("data/vnindex_ohlcv_recent.csv", _vnindex_recent_csv())
        manifest.append("data/vnindex_ohlcv_recent.csv")

        for rel, arc in FILES:
            src = REPO / rel
            if src.exists():
                zf.write(src, arc)
                manifest.append(arc)
            else:
                print(f"SKIP missing: {rel}")

        zf.writestr("MANIFEST.txt", "\n".join(sorted(manifest)))

    print(f"Wrote {OUT_ZIP} ({OUT_ZIP.stat().st_size / 1024:.1f} KB, {len(manifest)} files)")
    return OUT_ZIP


if __name__ == "__main__":
    build()
