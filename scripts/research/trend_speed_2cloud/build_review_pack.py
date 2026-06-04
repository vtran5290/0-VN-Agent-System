#!/usr/bin/env python3
"""Build trend_speed_2cloud_research_reviewpack_YYYYMMDD_v2.zip."""

from __future__ import annotations

import shutil
import subprocess
import zipfile
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SRC = REPO / "outputs" / "research" / "trend_speed_2cloud"
PACK = SRC / "review_pack"


def _write_readme(pack: Path) -> None:
    pack.joinpath("README.md").write_text(
        """# Trend Speed × 2-Cloud Research — v2 Review Pack

## v2 changes (decision-grade T2)
- **P0-1:** Pine-equivalent speed reset — cross bar uses `2×(RMA(close,10)-RMA(open,10))`.
- **P0-2:** Exact A3 T2 re-simulation per gate (no `blended×0.85` approximation).
- **P1-1:** Ranking modes `fifo` + `tsa_composite_only` only (no Phase36 `a3_rank_score` on panel).
- **P1-2:** Exit overlay **removed** from conclusions (prior D-series used non-comparable single-leg sim).

## Contracts (unchanged)
- A3: EMA20/100, T1 50%, T2 on ≥4% pullback/30 bars, TP1 +18%, trail 2.5×ATR14, max hold 250, VNINDEX bear blocks T1, breadth <40% blocks T2.
- S3 shadow: EMA21/55, max hold 60, trail 3.5×ATR14 — separate P&L.

## Data
- Panel: `data/research/ema_cloud/ohlcv_panel_ext2012.parquet` (FireAnt SSOT)
- Breadth: `regime_decomposition_breadth.csv`
- 2012-01-03 → 2026-05-22, ex-VIN, ADV≥2B, entry open[t+1], 40 bps RT
""",
        encoding="utf-8",
    )


def _write_indicator_notes(pack: Path) -> None:
    pack.joinpath("indicator_port_notes.md").write_text(
        """# Pine → Python — v2

## Speed reset (fixed v2)
Pine sequence on cross bar:
1. `speed := c - o`
2. `speed := speed + c - o`

Python v2: `speed[i] = 2 * (RMA(close,10) - RMA(open,10))` on cross; else `speed[i-1] + co`.

## T2 gate evaluation
- Pullback detection unchanged (low ≤ T1_entry×0.96 within 30 bars after T1 entry).
- Gate features read at **T2 fill bar** only (causal).
- If pullback occurs but gate/breadth blocks → **T1-only** `blended_net_return = t1_net` (exact).

## Anti-lookahead
- Signal-bar features for entry filters; fill-bar features for T2 gates.
- Rolling ranks: trailing 252 bars, min 60.
""",
        encoding="utf-8",
    )


def main() -> None:
    PACK.mkdir(parents=True, exist_ok=True)
    _write_readme(PACK)
    _write_indicator_notes(PACK)

    code_dir = PACK / "code"
    code_dir.mkdir(exist_ok=True)
    for rel in [
        "src/research/indicators/trend_speed_analyzer.py",
        "scripts/research/trend_speed_2cloud/engine.py",
        "scripts/research/trend_speed_2cloud/run_research.py",
        "tests/test_trend_speed_analyzer.py",
        "tests/test_trend_speed_2cloud_backtest.py",
        "tests/test_trend_speed_v2_cleanup.py",
    ]:
        src = REPO / rel
        if src.exists():
            shutil.copy2(src, code_dir / src.name)

    log_path = PACK / "tests_log.txt"
    try:
        r = subprocess.run(
            [
                str(REPO / ".venv" / "Scripts" / "python.exe"),
                "-m",
                "pytest",
                "tests/test_trend_speed_analyzer.py",
                "tests/test_trend_speed_2cloud_backtest.py",
                "tests/test_trend_speed_v2_cleanup.py",
                "-q",
            ],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=120,
        )
        log_path.write_text(r.stdout + r.stderr, encoding="utf-8")
    except Exception as exc:
        log_path.write_text(str(exc), encoding="utf-8")

    stamp = date.today().strftime("%Y%m%d")
    zip_path = REPO / f"trend_speed_2cloud_research_reviewpack_{stamp}_v2.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in PACK.rglob("*"):
            if f.is_file():
                arc = f.relative_to(SRC).as_posix()
                zf.write(f, arc)
    print(f"Wrote {zip_path}")


if __name__ == "__main__":
    main()
