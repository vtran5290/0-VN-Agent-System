# Earnings intake spec

## Earnings Heatmap Pack
- **Input:** `data/raw/earnings_heatmap_pack.json` — `asof_date`, `heatmap[]` (sector, score 1–5, evidence, watch).
- **Engine:** `python -m scripts.earnings_heatmap_apply` → archive `data/intake/earnings/heatmap/<asof_date>.json`, render `artifacts/earnings_heatmap.md` + `artifacts/earnings_heatmap.csv`.

## Tiered coverage
- **Config:** `data/config/coverage_tiers.yaml` — tier1 (deep), tier2 (machine), tier3 catch-all.
- Council packet prioritizes Tier1 facts; auto deep_request_queue if Tier1 anomaly.

## One-off / Earnings quality flags
- **In weekly_notes / consensus_pack:** `earnings_facts[].regime_tags` or `quality_flags`: `one_off_gain`, `provision_cleanup`, `inventory_gain_loss`, `fx_gain_loss`, `disposal_gain`, `accounting_reversal`.
- **Output:** `python -m scripts.earnings_quality_flags` → `artifacts/earnings_quality_flags.csv` (ticker, flag, source_id).

## Council Packet v2
- **Output:** `artifacts/council_packet_weekly.json` — asof_week, earnings_regime (status, leaders, laggards), top10_focus, invalidators, one_off_watchlist (from `data/config/one_off_watchlist.yaml`).
- **Build:** `python -m scripts.build_council_packet_v2` (after weekly + council_output).

## Earnings Revision Tracker (manual-lite)
- **Path:** `data/intake/earnings/revisions/<asof_date>.csv`
- **Columns:** ticker, revision_signal (up|down|unchanged|unclear), magnitude_if_any, reason_short, source_id.

## Macro ↔ Earnings sensitivity
- **Config:** `data/config/sensitivity_map.yaml` — sector → list of regime variables (e.g. Banks → interbank, OMO, credit_cap).
