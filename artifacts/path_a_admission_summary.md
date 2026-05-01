# Path A Admission Ablation — Summary

- **Best by robustness:** ranking_mode=liquidity_first, max_positions=8
- **Best for 2024-2026Q1:** ranking_mode=liquidity_first, max_positions=8
- **Ranking vs max_positions:** Ranking changes matter more.
- **max_positions 10 or 12 worth it?** Yes (higher chosen_rate or MAR).
- **Any config beats current baseline full-sample MAR?** No.
- **Verdict:** change ranking only (no MAR gain but different admission quality)
