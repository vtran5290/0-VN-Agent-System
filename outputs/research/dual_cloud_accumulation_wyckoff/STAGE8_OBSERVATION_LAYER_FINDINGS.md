# Stage 8 — Observation Layer / Forward Validation

**Run date:** 2026-05-22

## 1. Safety Confirmation

| Check | Status |
|---|---|
| A3 production contract unchanged | YES — research only |
| S3 remains paper-shadow only | YES |
| S3 does not gate A3 | YES |
| OMS/live/DNSE files untouched | YES — writes only to outputs/research/ |
| final_action unchanged | YES — Stage 8 does not write decision fields |
| All Stage 8 fields observation_only | YES — field_usage='observation_only' |
| old_composite_score marked REJECT | YES — old_composite_rejected_flag=True always |
| Wyckoff SOS diagnostic_only | YES — wyckoff_sos_diagnostic_flag |
| LPS/spring NOT positive ranking signals | YES — wyckoff_lps_rejected_flag/wyckoff_spring_rejected_flag |

## 2. Objective

Stage 8 exports Stage 7 WATCHLIST_ONLY observation fields to support
forward validation over 3–12 months. No trading decisions are made.
The two WATCHLIST_ONLY candidates from Stage 7 are:
- **breakout_value_expansion** (BVE): Q5 delta +4.3pp, 3/3 train/val/test positive
- **tightness_plus_breakout_close_quality** (TPBCQ): Q5 delta +4.3pp, highest Spearman rho

Both remain WATCHLIST_ONLY. Neither is approved for order-generation, sizing, or blocking.

## 3. Output Coverage

| File | Rows |
|---|---|
| stage8_observation_fields.csv | 2855 A3 signals |
| stage8_forward_validation_ledger_template.csv | 920 (2024+ signals) |
| stage8_daily_scan_overlay.csv | 527 (2025+ signals) |

## 4. Signal Counts

| Field | Count |
|---|---|
| A3 signals (total) | 2855 |
| breakout_value_expansion_watchlist_flag (Q4/Q5) | 1142 |
| tightness_plus_breakout_watchlist_flag (Q4/Q5) | 1142 |
| wyckoff_sos_diagnostic_flag | 573 |
| old_composite_rejected_flag | 2855 (all rows) |

## 5. Historical Performance (reference only)

From Stage 7 research (not forward-validated):
- All A3 signals: win_rate=n/a
- BVE Q5: n/a
- These are in-sample backtested numbers. Forward results may differ.

## 6. Forward Validation Design

The ledger template contains blank columns for future fills:
- fwd_5d/10d/20d/40d/63d_return — to be filled as market data arrives
- tp1_hit_63d — whether +15% was reached within 63 bars
- max_adverse/favorable_excursion_63d — drawdown and runup
- actual_trade_taken — operator field (YES/NO/NA)
- operator_note — free text

Forward validation acceptance threshold (from Stage 7 rules):
- Q5 win_rate must exceed all-signals win_rate by ≥5pp over ≥40 new observations
- Confirmation required in ≥2 of: bull regime, bear/sideways, 2024–2025 signals

## 7. By-Year Reference (historical)

|   year |   n_signals |   bve_watchlist |
|-------:|------------:|----------------:|
|   2012 |          27 |               8 |
|   2013 |         102 |              33 |
|   2014 |          98 |              38 |
|   2015 |         110 |              45 |
|   2016 |         115 |              42 |
|   2017 |         163 |              72 |
|   2018 |         156 |              46 |
|   2019 |         167 |              59 |
|   2020 |         274 |             111 |
|   2021 |         212 |              96 |
|   2022 |         197 |              78 |
|   2023 |         314 |             116 |
|   2024 |         393 |             153 |
|   2025 |         372 |             163 |
|   2026 |         155 |              82 |

## 8. FACTS vs INTERPRETATION

**FACTS:**
- Stage 8 exports observation fields only.
- No production or OMS file was modified.
- Both WATCHLIST candidates are below the PARALLEL_PAPER_RESEARCH threshold.
- old_composite_score is REJECTED in all contexts.
- Wyckoff SOS is DIAGNOSTIC ONLY.

**INTERPRETATION (not yet validated):**
- BVE and TPBCQ show 3/3 split-period lift in Stage 7 backtest.
- These results require 3–12 months forward validation before any action.
- Do NOT use Stage 8 quintiles for A3 entry decisions.
- Do NOT gate, size, or block based on Stage 8 fields.

## 9. Open Questions

1. Will BVE Q5 lift hold in 2026 live signals? (test-period delta was +3.2pp)
2. Does TPBCQ Q5 recover test-period weakness (+0.6pp) in fresh live data?
3. Is 2021 regime anomaly (BVE Q5 +26.3pp) replicable or a sampling artifact?
4. Does S3 signal co-occurrence improve or reduce A3 forward returns?

## 10. Next Step

Fill ledger template with actual forward returns as data arrives.
Target: 40+ new Q5 observations before reassessment.
At current A3 rate (~370 signals/year), Q5 adds ~74 new observations/year.
Reassessment window: 6–9 months from first signal capture.