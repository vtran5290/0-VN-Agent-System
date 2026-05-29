# Cloud Daily Report Validation — Data Accumulation Plan

**Date:** 2026-05-29
**Label:** RESEARCH_ONLY_NOT_PRODUCTION

---

## Problem Statement

The Cloud Daily Report validation framework is complete but most quantitative
return tests are **BLOCKED_BY_DATA**. Root cause: only ~2 weeks of phase36
daily scan CSVs exist (2026-05-15 to 2026-05-28), producing insufficient
events per `final_action` class for any return event study.

This document defines what must be accumulated and when to re-run.

---

## Why True Historical Scan Output Is Superior to Reconstructed OHLCV Signals

| Aspect | Reconstructed OHLCV | True Scan Output |
|---|---|---|
| Signal source | Cloud bull indicator recomputed from price | Actual A3 logic as run by operator |
| Timing fidelity | Close-of-day proxy only | Exact EOD timestamp + scan version |
| final_action labels | Must be inferred from conditions | Ground truth from production logic |
| a3_rank_score | Not reproducible exactly | Exact value from scan run |
| Breadth zone | Approximate from OHLCV universe | Exact breadth computed at scan time |
| Liquidity warnings | Must be estimated | Exact liq_warn_T1 as flagged |
| S3 shadow actions | Cannot reconstruct | s3_shadow_action exact from scan |
| Regime determination | OHLCV EMA proxy | Exact regime_bull from scan logic |
| **Verdict** | Valid for directional research (labeled RECONSTRUCTED) | Required for production-grade backtest |

Reconstructed signals may be used for Phase 1 directional research but must
always be labeled `RECONSTRUCTED_NOT_LIVE_SCAN`. Never mix with true outputs.

---

## Daily Scan Archival Plan

### Target path
```
data/research/portfolio_optimization/missing_work/phase36_daily_scan_YYYYMMDD.csv
```

Already partially implemented: files exist from 2026-05-22 onward.

### Implementation
Add to production daily scan run (e.g., `daily_three_strategy_scan_run.cmd`):
```
python scripts/research/archive_daily_scan.py
```

This script should:
1. Read the current `phase36_daily_scan_latest.csv`
2. Copy to `phase36_daily_scan_YYYYMMDD.csv` with today's date
3. Never overwrite existing archives

Do NOT implement production scheduling until explicitly instructed.

---

## Portfolio Snapshot Archival Plan

### Target path
```
data/history/YYYY-MM-DD/portfolio_state.json
data/history/YYYY-MM-DD/current_positions_derived.json
```

Currently only `data/raw/current_positions_derived.json` exists (current state only).

### Required fields for portfolio overlay backtest
- `as_of_date`
- Per-position: `symbol`, `qty`, `avg_cost`, `current_price`, `action_at_time`
- NAV at date (user-updated)

### Implementation
Add daily archival step to operator workflow. Do NOT implement automatically.

---

## Minimum History Required by Validation Type

| Validation | Min Events | Min Trading Days | Current | Ready? |
|---|---|---|---|---|
| NEW_T1 return event study | N ≥ 20 | ~60 days | 0 events | NO |
| ADD_T2 return event study | N ≥ 20 | ~90 days | 0 events | NO |
| WAIT_PB return event study | N ≥ 20 | ~90 days | 0 events | NO |
| TRAIL_EXIT vs hold comparison | N ≥ 30 | ~30 days | 376 events (no FWD window) | 30d |
| NO_T2_BREADTH risk control | N ≥ 30 | ~60 days | 157 events (no FWD window) | 30d |
| a3_rank_score decile test | N ≥ 100 | ~90 days | ~100/week | 90d |
| Breadth zone forward returns | N ≥ 50 per zone | ~90 days | partial | 90d |
| T1/T2 gate comparison | N ≥ 30 per regime | ~60 days | partial | 60d |
| RS correction event study | N ≥ 3 correction events | ~180 days | 1 event | 180d |
| C3 decile IC test | N ≥ 200 events | ~60 days | 0 | 60d |
| Portfolio simulation | N ≥ 100 entries | ~180 days | 0 entries | 180d |
| Portfolio overlay backtest | Any historical snapshot | N/A | 0 snapshots | After archival |

---

## Rerun Schedule

### 30-day checkpoint (approx 2026-06-28)
- Re-run: `run_all.py`
- Expected unlocks: TRAIL_EXIT forward window, NO_T2_BREADTH risk window
- Expected status: BLOCKED_BY_DATA → INCONCLUSIVE or RISK_CONTROL_SUPPORTED
- Review: confirm evidence labels with ChatGPT

### 90-day checkpoint (approx 2026-08-27)
- Re-run: `run_all.py`
- Expected unlocks: a3_rank_score decile test, breadth zone event study, T1/T2 comparison
- Expected label upgrades: BLOCKED_BY_DATA → INCONCLUSIVE or DIRECTIONALLY_SUPPORTED for some
- Key question: does NEW_T1 outperform equal-weight liquid universe?

### 180-day checkpoint (approx 2026-11-25)
- Re-run: `run_all.py`
- Expected unlocks: RS correction multi-event study, C3 IC test, portfolio simulation
- Expected label upgrades: RS correction → DIRECTIONALLY_SUPPORTED (if consistent)
- Key question: can RS correction lens be upgraded from INCONCLUSIVE_DIRECTIONAL_ONLY?

---

## Rerun Command

```powershell
.venv\Scripts\python.exe scripts/research/cloud_daily_report_validation/run_all.py
```

---

## Label Upgrade Criteria

Before upgrading any label from BLOCKED_BY_DATA:

1. **N ≥ minimum** per the table above
2. **No look-ahead**: signal date uses only information available at EOD
3. **T+1 entry timing**: forward return starts from next-open, not same-day close
4. **Benchmark comparison**: results shown vs VNINDEX and equal-weight liquid universe
5. **Regime split**: at least bull vs. bear split
6. **Cost adjustment**: gross return and 0.3% round-trip cost-adjusted return both shown

Before upgrading from INCONCLUSIVE to DIRECTIONALLY_SUPPORTED:
- Positive direction in ≥2 independent time windows
- Same direction in bull AND bear regimes (or clearly regime-conditional)

Before upgrading to STATISTICALLY_SUPPORTED:
- t-stat > 1.96 on mean excess return
- Consistent across sub-periods (pre-2024 and 2024+)
- Survives basic multiple-testing caution (Bonferroni or similar)

---

## What Will Not Change Regardless of Data

These outputs are **permanently** classified regardless of accumulation:

| Output | Label | Reason |
|---|---|---|
| S3 Radar | DISPLAY_ONLY | Paper-shadow by design — s3_no_real_order_flag enforced |
| C3 rating | DISPLAY_ONLY | OOS IC near zero in 2024+ (prior analysis) |
| mode/NAV/date | DISPLAY_ONLY | Informational formatting only |
| Delta changes | DISPLAY_ONLY | Workflow change tracking only |
| Appendix | DISPLAY_ONLY | Data display only |
| Portfolio overlay VERIFY | DISPLAY_ONLY | Data consistency check only |

---

## RESEARCH_ONLY_NOT_PRODUCTION

This document describes research validation plans only.
No production trading behavior is changed by any recommendation in this plan.
All label upgrades require explicit human review and approval.
