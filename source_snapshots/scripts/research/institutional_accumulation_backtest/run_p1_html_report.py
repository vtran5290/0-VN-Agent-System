from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.research.institutional_accumulation_backtest.p1_reporting import write_p1_html_report


def _csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.is_file() else pd.DataFrame()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data/research/institutional_accumulation")
    ap.add_argument("--html-path", default="reports/research/institutional_accumulation/p1_score_inversion_diagnostic.html")
    args = ap.parse_args()

    root = Path(args.data_dir)
    html_path = Path(args.html_path)
    write_p1_html_report(
        html_path,
        summary=_csv(root / "p1_diagnostic_summary.csv"),
        measurement=_csv(root / "p1_measurement_integrity.csv"),
        autopsy=_csv(root / "p1_score_decile_autopsy.csv"),
        components=_csv(root / "p1_component_diagnostics.csv"),
        lead_lag=_csv(root / "p1_feature_lead_lag.csv"),
        buckets=_csv(root / "p1_accumulation_vs_exhaustion.csv"),
        unit_audit=_csv(root / "p1_unit_audit.csv"),
        distribution_flag_diagnostic=_csv(root / "p1_distribution_flag_diagnostic.csv"),
        regimes=_csv(root / "p1_regime_dependency.csv"),
        horizons=_csv(root / "p1_horizon_dependency.csv"),
        thresholds=_csv(root / "p1_tier_threshold_diagnostics.csv"),
    )
    print(f"Wrote P1 HTML report: {html_path}")


if __name__ == "__main__":
    main()

