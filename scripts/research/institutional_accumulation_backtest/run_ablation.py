from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.research.institutional_accumulation_backtest.ablation import (
    component_ablation,
    distribution_flag_validation,
    risk_penalty_calibration,
)


def main() -> None:
    outcomes = pd.read_parquet("data/research/institutional_accumulation/forward_outcomes_panel.parquet")
    out_dir = Path("data/research/institutional_accumulation")
    out_dir.mkdir(parents=True, exist_ok=True)
    component_ablation(outcomes).to_csv(out_dir / "component_ablation_oos.csv", index=False)
    risk_penalty_calibration(outcomes).to_csv(out_dir / "risk_penalty_calibration.csv", index=False)
    distribution_flag_validation(outcomes).to_csv(out_dir / "distribution_flag_validation.csv", index=False)
    print("Wrote ablation outputs")


if __name__ == "__main__":
    main()
