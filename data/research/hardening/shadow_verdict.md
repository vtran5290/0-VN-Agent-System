# Shadow Candidate Verdict — B_cloud21_55_partial
**Date:** 2026-05-13

## Comparison Table (all universe × fill mode)

| Universe | Fill | CAGR | maxDD | Sharpe | MAR | OOS avg |
|---|---|---|---|---|---|---|
| full    | fifo     | 8.6%  | -32.4% | 0.906 | 0.26 | 6.8% |
| full    | ema_dist | 9.0%  | -36.2% | 0.834 | 0.25 | 6.8% |
| full    | **momentum** | **10.5%** | -32.6% | **1.045** | **0.32** | 6.8% |
| ex_vic  | ema_dist | 10.1% | -34.6% | 0.892 | 0.29 | 6.8% |
| ex_vic  | momentum | 10.0% | -33.2% | 0.991 | 0.30 | 6.8% |
| ex_vin3 | fifo     | 4.5%  | -32.1% | 0.506 | 0.14 | 6.8% |
| ex_vin3 | ema_dist | 9.9%  | -34.6% | 0.880 | 0.29 | 6.8% |
| **ex_vin3** | **momentum** | **9.9%** | -33.2% | **0.973** | **0.30** | **6.8%** |

## FACTS

**Fill mode matters enormously for the shadow (21/55).**
17,071 signals compete for 20 slots. FIFO on ex_vin3 = CAGR 4.5%. Momentum fill = CAGR 9.9%.

**Momentum fill outperforms ema_dist for the shadow.**
For 21/55 (faster cloud), recent 20-bar momentum better predicts follow-through.
ema_dist Sharpe=0.880 vs momentum Sharpe=0.973 on ex_vin3.

**Full universe FIFO (8.6% / Sharpe 0.906) was accidentally good.**
Alphabetical fill happened to capture VIC early. With ranked fill, full ema_dist Sharpe drops to 0.834.
Full universe is NOT the right basis once fill is properly ranked.

**VHM/VRE removal is marginal for ranked fill.**
ex_vic momentum vs ex_vin3 momentum: 10.0%/0.991 vs 9.9%/0.973 — negligible.
VIC carries ongoing structural/event risk and its removal is standard policy.

**OOS avg_trade = 6.8% across all configurations.** Edge is in individual trades; fill mode
determines which trades receive capital, not signal quality.

## Decision

**Track shadow on EX-VIN3 universe with MOMENTUM fill.**

Paper monitoring config:
- entry_type: cloud_only, ema_fast=21, ema_slow=55
- exit_mode: partial_tp, max_hold=250
- universe: ex_vin3, max_positions=20
- fill_mode: **momentum** (20-bar price ROC, descending)
- Expected: CAGR~9.9%, Sharpe~0.973

Promote shadow to co-primary only if primary remains in drawdown > 6 months
while shadow is flat or positive, OR after an explicit allocation review.

Shadow remains a monitoring / fallback candidate only. Primary for paper trading
remains **B_cloud20_100_partial (ex-VIN3, ema_dist fill)**.