from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.research.institutional_accumulation_backtest.p2_reporting import write_p2_html_report


def _csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.is_file() else pd.DataFrame()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data/research/institutional_accumulation")
    ap.add_argument("--html-path", default="reports/research/institutional_accumulation/p2_research_variants.html")
    args = ap.parse_args()

    root = Path(args.data_dir)
    html_path = Path(args.html_path)
    write_p2_html_report(
        html_path,
        variant_results=_csv(root / "p2_variant_results.csv"),
        top_decile_exhaustion=_csv(root / "p2_top_decile_exhaustion.csv"),
        extension_cap_sweep=_csv(root / "p2_extension_cap_sweep.csv"),
        distribution_gate_sweep=_csv(root / "p2_distribution_gate_sweep.csv"),
        diagnostic_summary=_csv(root / "p2_diagnostic_summary.csv"),
        p1_summary=_csv(root / "p1_diagnostic_summary.csv"),
    )
    print(f"Wrote P2 HTML report: {html_path}")


if __name__ == "__main__":
    main()
