# Path A Weekly MA-pair Ablation – Summary

Screen periods: 2018-2021 + 2024-2026Q1. Confirm periods: 2022-2024 + full_sample.

- **Best config by screen score** (2018-2021 + 2024-2026Q1): support_ma=20, short_ma=10, long_ma=20 (score=0.7817, avg_mar=0.7817)

- Best config by robustness (all 4 periods): support_ma=10, short_ma=5, long_ma=10 (avg_mar=0.2448, score=0.2448)

- Best for 2018-2021: support_ma=20, short_ma=10, long_ma=40 (MAR=0.6420)

- Support 10 vs 20: support_ma=20 better on average.

- **Recent period (2024-2026Q1) vs 2018-2021:** same MAR sign = agree: 8, opposite = conflict: 0. Agrees on balance.

- **Top configs in 2024-2026Q1** (chosen_rate, rejected_max_positions):
  - 20/10/20: chosen_rate=0.02038, rejected_max_positions=1809
  - 10/10/20: chosen_rate=0.03556, rejected_max_positions=1657
  - 20/5/20: chosen_rate=0.01944, rejected_max_positions=2123
  - 10/10/40: chosen_rate=0.03839, rejected_max_positions=1558
  - 20/10/50: chosen_rate=0.02505, rejected_max_positions=1658
  - 20/10/30: chosen_rate=0.02449, rejected_max_positions=1659
  - 20/10/40: chosen_rate=0.025, rejected_max_positions=1672
  - 20/20/40: chosen_rate=0.03056, rejected_max_positions=1482

- Weekly MA/MA materially improves Path A: Yes (baseline MAR=0.0977, best MA-pair full-sample MAR=0.3624)

- Max_positions pressure: see main MD section 7 (configs with most candidates vs best chosen_rate).
