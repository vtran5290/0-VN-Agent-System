from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str]) -> None:
    print(">", " ".join(cmd), flush=True)
    subprocess.check_call(cmd)


def main() -> None:
    py = sys.executable
    root = Path(__file__).resolve().parents[3]
    common = [
        py,
        "-m",
    ]
    _run(
        common
        + [
            "scripts.research.institutional_accumulation_backtest.run_panel",
            "--start",
            "2012-01-01",
            "--end",
            "latest",
            "--cadence",
            "weekly",
            "--context-mode",
            "ohlcv_only",
            "--chunk-size",
            "100",
            "--resume",
            "--workers",
            "2",
        ]
    )
    panel = root / "data/research/institutional_accumulation/panel_scores.parquet"
    _run(
        common
        + [
            "scripts.research.institutional_accumulation_backtest.run_outcomes",
            "--panel",
            str(panel).replace("\\", "/"),
            "--resume",
        ]
    )
    _run(common + ["scripts.research.institutional_accumulation_backtest.run_portfolios", "--context-mode", "ohlcv_only"])
    _run(common + ["scripts.research.institutional_accumulation_backtest.run_ablation"])
    _run(common + ["scripts.research.institutional_accumulation_backtest.run_yearly_report"])
    _run(common + ["scripts.research.institutional_accumulation_backtest.run_html_report"])
    _run(common + ["scripts.research.institutional_accumulation_backtest.build_review_pack"])


if __name__ == "__main__":
    main()
