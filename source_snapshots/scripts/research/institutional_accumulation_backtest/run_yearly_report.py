from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.research.institutional_accumulation_backtest.statistics import (
    regime_validation,
    score_decile_calibration,
    vin_sensitivity_summary,
    yearly_validation,
)


def main() -> None:
    outcomes = pd.read_parquet("data/research/institutional_accumulation/forward_outcomes_panel.parquet")
    out_dir = Path("data/research/institutional_accumulation")
    out_dir.mkdir(parents=True, exist_ok=True)
    yearly_validation(outcomes).to_csv(out_dir / "yearly_validation.csv", index=False)
    score_decile_calibration(outcomes).to_csv(out_dir / "score_decile_calibration.csv", index=False)
    regime_validation(outcomes).to_csv(out_dir / "regime_validation.csv", index=False)
    vin_sensitivity_summary(outcomes).to_csv(out_dir / "vin_sensitivity_summary.csv", index=False)
    outcomes.groupby("caution_proxy").agg(
        n=("ticker", "count"),
        ret_60d_mean=("ret_60d", "mean"),
    ).reset_index().rename(columns={"caution_proxy": "section"}).to_csv(
        out_dir / "warning_validation.csv", index=False
    )
    outcomes.groupby("is_tier12").agg(
        n=("ticker", "count"),
        ret_20d_mean=("ret_20d", "mean"),
        ret_60d_mean=("ret_60d", "mean"),
    ).reset_index().rename(columns={"is_tier12": "event"}).to_csv(
        out_dir / "changes_event_study.csv", index=False
    )
    print("Wrote yearly/regime outputs")


if __name__ == "__main__":
    main()
