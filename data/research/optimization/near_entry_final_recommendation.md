# Near-Entry Window — Final Recommendation

Generated: 2026-05-14  | Validation: realistic exit replay (TP1 repriced per entry)

> **Caveat**: Exit is re-simulated from delayed entry price.
> TP1 target reprices to delayed_price × (1 + tp_pct). This is realistic,
> not a simplification. Results supersede earlier same-exit estimates.

## A3_primary

**Baseline**: mean_net=6.61%  hit=67.2%  N=12,900

**Proposed window**: [-10%, +8%]

### Bucket table (realistic replay)

| bucket      |     n | mean_net   | hit_rate   | hit_drop   | ret_vs_orig   | samexit_bias   | WARN   |
|:------------|------:|:-----------|:-----------|:-----------|:--------------|:---------------|:-------|
| [-14%,-12%) |  2685 | 6.10%      | 68.2%      | -0.9%      | 0.92x         | +8.58%         |        |
| [-12%,-10%) |  1139 | 5.61%      | 69.0%      | -1.8%      | 0.85x         | +3.79%         |        |
| [-10%,-8%)  |  2055 | 7.74%      | 69.3%      | -2.1%      | 1.17x         | +3.38%         |        |
| [-8%,-6%)   |  3365 | 6.56%      | 66.3%      | +0.9%      | 0.99x         | +2.22%         |        |
| [-6%,-4%)   |  5970 | 6.53%      | 66.3%      | +0.9%      | 0.99x         | +1.09%         |        |
| [-4%,-2%)   | 10580 | 5.46%      | 64.6%      | +2.6%      | 0.83x         | +0.66%         |        |
| [-2%,+0%)   | 16604 | 5.71%      | 65.7%      | +1.6%      | 0.86x         | +0.21%         |        |
| [+0%,+2%)   | 21304 | 6.85%      | 67.5%      | -0.3%      | 1.04x         | -0.15%         |        |
| [+2%,+4%)   |  9126 | 5.61%      | 65.2%      | +2.0%      | 0.85x         | -0.73%         |        |
| [+4%,+6%)   |  5593 | 6.66%      | 66.6%      | +0.6%      | 1.01x         | -1.16%         |        |
| [+6%,+8%)   |  3615 | 7.93%      | 68.8%      | -1.6%      | 1.20x         | -2.17%         |        |
| [+8%,+10%)  |  2265 | 8.44%      | 69.4%      | -2.2%      | 1.28x         | -3.52%         |        |
| [+10%,+12%) |  1434 | 5.97%      | 69.2%      | -2.0%      | 0.90x         | -2.35%         |        |
| [+12%,+14%) |  1082 | 8.54%      | 72.6%      | -5.4%      | 1.29x         | -5.46%         |        |
| >+14%       |  3305 | 10.38%     | 73.9%      | -6.7%      | 1.57x         | -10.53%        |        |

### Quality label summary

| quality        |     n | mean_net   | hit_rate   | hit_drop   | ret_vs_orig   |
|:---------------|------:|:-----------|:-----------|:-----------|:--------------|
| deep_pullback  |  3824 | 5.95%      | 68.4%      | -1.2%      | 0.90x         |
| ideal_pullback | 21970 | 6.13%      | 65.8%      | +1.5%      | 0.93x         |
| acceptable     | 56249 | 6.36%      | 66.6%      | +0.6%      | 0.96x         |
| stretched      |  4777 | 7.72%      | 70.1%      | -2.8%      | 1.17x         |
| momentum_confirmed |  3302 | 10.39%     | 73.9%      | -6.7%      | 1.57x         |

### Mode comparison

| mode              |   n_in_window | pct_included   | mean_net   | hit_rate   |
|:------------------|--------------:|:---------------|:-----------|:-----------|
| A_symmetric_7pct  |         73276 | 81.3%          | 6.22%      | 66.2%      |
| B_asymmetric_hard |         78219 | 86.8%          | 6.30%      | 66.4%      |
| D_mode_c_downside_only |         86820 | 96.3%          | 6.36%      | 66.6%      |

### Verdict

1. **Asymmetric thresholds directionally valid?** YES

2. **Stretched zone (+8% to +14%) still viable?** YES — label as Stretched, do not hard-block

3. **>+14% momentum_confirmed (no hard reject)?** YES — higher historical mean_net; include with label

4. **Recommendation**: Mode C daily scan — downside floor -10% only, no upside cap; label stretched/momentum_confirmed

## S3_shadow

**Baseline**: mean_net=6.35%  hit=65.4%  N=17,313

**Proposed window**: [-6%, +8%]

### Bucket table (realistic replay)

| bucket      |     n | mean_net   | hit_rate   | hit_drop   | ret_vs_orig   | samexit_bias   | WARN   |
|:------------|------:|:-----------|:-----------|:-----------|:--------------|:---------------|:-------|
| [-14%,-12%) |  3889 | 4.84%      | 65.0%      | +0.4%      | 0.76x         | +5.52%         |        |
| [-12%,-10%) |  1657 | 4.62%      | 63.7%      | +1.7%      | 0.73x         | +3.01%         |        |
| [-10%,-8%)  |  2673 | 3.67%      | 63.2%      | +2.2%      | 0.58x         | +2.70%         |        |
| [-8%,-6%)   |  4484 | 3.62%      | 62.9%      | +2.5%      | 0.57x         | +1.70%         |        |
| [-6%,-4%)   |  7877 | 5.75%      | 65.4%      | +0.1%      | 0.91x         | +1.22%         |        |
| [-4%,-2%)   | 14160 | 5.06%      | 63.5%      | +1.9%      | 0.80x         | +0.48%         |        |
| [-2%,+0%)   | 21999 | 4.87%      | 62.4%      | +3.0%      | 0.77x         | +0.18%         |        |
| [+0%,+2%)   | 28410 | 6.73%      | 65.7%      | -0.3%      | 1.06x         | -0.18%         |        |
| [+2%,+4%)   | 12243 | 6.20%      | 65.3%      | +0.1%      | 0.98x         | -0.68%         |        |
| [+4%,+6%)   |  7554 | 7.57%      | 67.5%      | -2.1%      | 1.19x         | -1.51%         |        |
| [+6%,+8%)   |  4953 | 9.67%      | 69.9%      | -4.4%      | 1.52x         | -2.39%         |        |
| [+8%,+10%)  |  3134 | 9.16%      | 70.2%      | -4.7%      | 1.44x         | -2.88%         |        |
| [+10%,+12%) |  1980 | 8.85%      | 71.1%      | -5.7%      | 1.39x         | -3.34%         |        |
| [+12%,+14%) |  1447 | 10.86%     | 74.2%      | -8.8%      | 1.71x         | -5.06%         |        |
| >+14%       |  4416 | 11.63%     | 74.9%      | -9.4%      | 1.83x         | -8.99%         |        |

### Quality label summary

| quality    |     n | mean_net   | hit_rate   | hit_drop   | ret_vs_orig   |
|:-----------|------:|:-----------|:-----------|:-----------|:--------------|
| damaged    | 12703 | 4.13%      | 63.7%      | +1.7%      | 0.65x         |
| ideal      | 22037 | 5.31%      | 64.2%      | +1.3%      | 0.84x         |
| acceptable | 75172 | 6.38%      | 65.2%      | +0.3%      | 1.00x         |
| stretched  |  6549 | 9.46%      | 71.4%      | -5.9%      | 1.49x         |
| momentum_confirmed |  4415 | 11.62%     | 74.9%      | -9.4%      | 1.83x         |

### Mode comparison

| mode              |   n_in_window | pct_included   | mean_net   | hit_rate   |
|:------------------|--------------:|:---------------|:-----------|:-----------|
| A_symmetric_7pct  |         97776 | 80.9%          | 5.96%      | 64.7%      |
| B_asymmetric_hard |         97209 | 80.4%          | 6.13%      | 64.9%      |
| D_mode_c_downside_only |        116461 | 96.3%          | 6.10%      | 65.2%      |

### Verdict

1. **Asymmetric thresholds directionally valid?** YES

2. **Stretched zone (+8% to +14%) still viable?** YES — label as Stretched, do not hard-block

3. **>+14% momentum_confirmed (no hard reject)?** YES — higher historical mean_net; include with label

4. **Recommendation**: Mode C daily scan — downside floor -6% only, no upside cap; label stretched/momentum_confirmed

## Cross-Strategy Decision

| Question | A3 PRIMARY | S3 SHADOW |
|---|---|---|
| Asymmetric thresholds valid? | See A3 bucket table | See S3 bucket table |
| Upside label boundary | +8% (not a hard cap) | +8% (not a hard cap) |
| Downside floor | -10% (pullbacks genuinely better) | -6% (degrades faster) |
| Stretched zone (+8 to +14%) | Label only, not hard block | Label only |
| >+14% | momentum_confirmed — include, do not block | momentum_confirmed — include |
| C_GK | Keep ±7% symmetric — no evidence | ← same |
| Promote to paper-trade rule? | NO — scan triage only for now | NO |

> **Final verdict**: **Mode C for daily scan** — downside floor only, no upside hard cap.
> Label stretched and momentum_confirmed for operator triage; do not hard-reject >+14%.
> Historical mean-net hints are informational only.
> Do NOT automatically promote near-entry logic into backtest strategy rules.
> C_GK remains on symmetric ±7% pending separate validation.

---

*End of near-entry final recommendation*
