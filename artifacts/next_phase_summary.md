# Next Phase Summary

## 1. Best ranking by robustness

From walk-forward: **extension_only** (chosen by median MAR across test windows).

## 2. Best simple filter

From filter ablation: **baseline** (best avg MAR across periods).

## 3. Safe NAV range

skipped_liquidity did not exceed 10 up to 100bn; safe range under current assumptions: up to 20–50bn (conservative).

## 4. Recommendation for next research step

- Lock in best ranking and best filter (if not over-filtering).
- Consider paper trading or small live pilot at NAV within safe range.
- Optionally: add sector caps or regime-based exposure in a later phase; no FA yet.
