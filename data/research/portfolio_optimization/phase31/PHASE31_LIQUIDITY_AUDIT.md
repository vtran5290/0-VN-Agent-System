# Phase 3.1 — Liquidity Unit Audit
Generated: 2026-05-16

## Executive Summary

Three bugs were found that explain why candidate comparison shows 0% exclusion for PTS/DP
while the daily scan shows CRITICAL liquidity for all 56 setups:

### Bug 1 — Daily scan: ADV50 understated by 1000×

```
Panel close is stored in kVND (thousands of VND).
panel['value'] = close_kVND × volume_shares × 1000 → true VND value.
Scan used: adv50 = (close × volume).rolling(50).mean()  ← kVND-unit
Correct:   adv50 = (close × volume × 1000).rolling(50) ← VND
              or = panel['value'].rolling(50)            ← VND (when available)
Result: every stock's ADV50 was 1000× too low → all showed CRITICAL.
```

### Bug 2 — Candidate comparison: PTS/DP have no adv50_value column

```
PTS and DP trade ledgers are built by _sim_pb_then_str, which records:
  entry_date, exit_date, ep1, blended_ep, total_frac, net_return ...
  but does NOT tag adv50_value from the panel.
In _build_equity_adv_capped, the ADV cap branch is:
  if adv_col in df.columns:  ← False for PTS/DP
      ... apply cap ...
  else:
      eff_w = target_w  ← No cap applied at all!
Result: PTS/DP showed n_excluded=0, n_partial=0 for all portfolio sizes.
```

### Bug 3 — _liquidity_warning: mixed units

```
pos_vnd was in VND (e.g., 333M VND for 5B/15-pos portfolio)
adv50 was in kVND-unit (e.g., 1.015B for HPG, should be 1.015T VND)
Comparison: 333M > 1.015B × 0.10 × 2 = 203M → CRITICAL
Correct:    333M vs 1.015T × 0.10 × 2 = 203B → OK (333M << 203B)
```

---

## Task 1 — Unit Check for Known-Liquid Tickers

All 10 tickers confirmed:
- `panel['value']` = `close × volume × 1000` exactly (ratio = 1000.0)
- Close stored in kVND (thousands of VND)
- Volume stored in shares
- `adv50_B_VND` in original scan was in million VND (1000× too small)

| symbol   |   close_last_kVND |   close_est_VND |   vol_last_shares |   ratio_value_vs_closexvol |   adv50_scan_reports_B_VND |   adv50_correct_B_VND |   a3_ledger_adv50_recent_B |   understatement_factor |   correct_target_T1_at_5B_10pct_M |
|:---------|------------------:|----------------:|------------------:|---------------------------:|---------------------------:|----------------------:|---------------------------:|------------------------:|----------------------------------:|
| HPG      |           26.5500 |           26550 |          75838200 |                  1000.0000 |                     1.0147 |             1014.6720 |                  1113.0900 |                    1000 |                          166.7000 |
| MWG      |           82.0000 |           82000 |           6691900 |                  1000.0000 |                     0.6072 |              607.1600 |                   587.2130 |                    1000 |                          166.7000 |
| VPB      |           27.5500 |           27550 |          12744400 |                  1000.0000 |                     0.4391 |              439.0960 |                   461.2980 |                    1000 |                          166.7000 |
| HCM      |           28.7500 |           28750 |           9187900 |                  1000.0000 |                     0.3427 |              342.6580 |                   302.3900 |                    1000 |                          166.7000 |
| VHM      |          158.0000 |          158000 |           4836400 |                  1000.0000 |                     0.7775 |              777.5290 |                   nan      |                    1000 |                          166.7000 |
| MSN      |           77.5000 |           77500 |           4808600 |                  1000.0000 |                     0.5036 |              503.5970 |                   471.9540 |                    1000 |                          166.7000 |
| HDB      |           27.5500 |           27550 |          13065500 |                  1000.0000 |                     0.3543 |              354.3310 |                   308.1440 |                    1000 |                          166.7000 |
| FPT      |           72.9000 |           72900 |           6386100 |                  1000.0000 |                     0.8062 |              806.2030 |                   656.0780 |                    1000 |                          166.7000 |
| SSI      |           27.9000 |           27900 |          13001900 |                  1000.0000 |                     0.8946 |              894.6410 |                   848.4590 |                    1000 |                          166.7000 |
| VND      |           16.4500 |           16450 |           5929500 |                  1000.0000 |                     0.1931 |              193.1380 |                   325.7640 |                    1000 |                          166.7000 |

## Task 2 — Liquidity Formula Audit

### Correct formulas

```
adv50_VND = panel['value'].rolling(50).mean()                    # VND
         OR (close_kVND × volume × 1000).rolling(50).mean()      # VND

# Position sizing
base_pos_VND   = portfolio_VND / max_positions                   # e.g., 5B/15 = 333M
target_T1_VND  = base_pos_VND × gk_mult × t1_frac               # e.g., 333M × 1.0 × 0.5 = 167M
target_full_VND = base_pos_VND × gk_mult                        # e.g., 333M

# ADV participation cap
max_allowed_VND = adv50_VND × participation_rate                 # e.g., 1.015T × 10% = 101.5B

# Effective sizes
eff_T1_VND      = min(target_T1_VND, max_allowed_VND × t1_frac)
eff_full_VND    = min(target_full_VND, max_allowed_VND)

# Warnings (compare in same unit — VND)
liq_warning_T1:   compare target_T1_VND vs max_allowed_VND
liq_warning_full: compare target_full_VND vs max_allowed_VND
```

### Target sizes at reference portfolio (5B VND, 15 positions, 10% ADV)

| Portfolio | max_pos | base_pos_M | target_T1_M | ADV50_min_for_T1_OK_B |
|-----------|---------|------------|-------------|------------------------|
| 1B VND | 15 | 66.7M | 33.3M | 0.33B |
| 3B VND | 15 | 200M  | 100M  | 1.0B  |
| 5B VND | 15 | 333M  | 167M  | 1.67B |
| 10B VND| 15 | 667M  | 333M  | 3.33B |

## Task 3 — Candidate Comparison Audit

### Root cause of phantom 0% exclusion for PTS/DP

PTS and DP trade ledgers (built by `_sim_pb_then_str`, `_sim_dual_path_pb`) record trade
outcomes but do **not** carry `adv50_value` forward. The `_build_equity_adv_capped` function
silently skips the ADV cap when the column is absent, treating all trades as fully liquid.

The A3 ledger does carry `adv50_value` (in correct VND from `panel['value'].rolling(50)`).
That's why A3 shows 0.3-0.9% exclusion (real small-cap illiquid stocks) while PTS/DP show 0.

## Task 4 — Recomputed Capacity (Corrected ADV)

### At 5B VND, 10% ADV participation

| candidate             |   n_total |   pct_full_T1 |   pct_partial_T1 |   pct_excl_T1 |   mean_fill_T1 |   pct_full_final |   pct_excl_final |    mar |   cagr | most_constrained_syms   |
|:----------------------|----------:|--------------:|-----------------:|--------------:|---------------:|-----------------:|-----------------:|-------:|-------:|:------------------------|
| PTS_A3_pb4w30_str6w10 |      9030 |        0.6848 |           0.3070 |        0.0082 |         0.7763 |           0.5255 |           0.0063 | 0.3426 | 0.0543 | HHV,NT2,VC3,VVS,L40     |
| DP_A3_pb_only         |      9030 |        0.6848 |           0.3070 |        0.0082 |         0.7763 |           0.3317 |           0.0065 | 0.4156 | 0.0581 | HHV,NT2,VC3,VVS,L40     |
| A3_pos15              |     12909 |        0.6213 |           0.3694 |        0.0094 |         0.7297 |           0.6213 |           0.0058 | 0.2011 | 0.0558 | HHV,VVS,NT2,L40,VIW     |
| A3_pos15_GK_mult125   |     12909 |        0.6116 |           0.3790 |        0.0094 |         0.7216 |           0.6116 |           0.0058 | 0.1751 | 0.0549 | HHV,VVS,NT2,L40,VIW     |

### Full recomputed table (all portfolio sizes × participation rates)

| candidate             |   portfolio_B_VND |   participation_pct |   pct_full_T1 |   pct_partial_T1 |   pct_excl_T1 |   mean_fill_T1 |   pct_full_final |   pct_excl_final |   mean_fill_final |    mar |   cagr |
|:----------------------|------------------:|--------------------:|--------------:|-----------------:|--------------:|---------------:|-----------------:|-----------------:|------------------:|-------:|-------:|
| A3_pos15              |            1.0000 |              5.0000 |        0.7446 |           0.2422 |        0.0132 |         0.8172 |           0.7446 |           0.0094 |            0.8172 | 0.3581 | 0.0897 |
| A3_pos15              |            1.0000 |             10.0000 |        0.8130 |           0.1776 |        0.0094 |         0.8639 |           0.8130 |           0.0058 |            0.8639 | 0.3423 | 0.0935 |
| A3_pos15              |            1.0000 |             20.0000 |        0.8575 |           0.1367 |        0.0058 |         0.8976 |           0.8575 |           0.0032 |            0.8976 | 0.4100 | 0.1047 |
| A3_pos15              |            3.0000 |              5.0000 |        0.5900 |           0.3969 |        0.0132 |         0.7075 |           0.5900 |           0.0094 |            0.7075 | 0.2491 | 0.0614 |
| A3_pos15              |            3.0000 |             10.0000 |        0.6980 |           0.2927 |        0.0094 |         0.7829 |           0.6980 |           0.0058 |            0.7829 | 0.2530 | 0.0698 |
| A3_pos15              |            3.0000 |             20.0000 |        0.7743 |           0.2198 |        0.0058 |         0.8384 |           0.7743 |           0.0032 |            0.8384 | 0.3448 | 0.0846 |
| A3_pos15              |            5.0000 |              5.0000 |        0.5045 |           0.4823 |        0.0132 |         0.6397 |           0.5045 |           0.0094 |            0.6397 | 0.1981 | 0.0484 |
| A3_pos15              |            5.0000 |             10.0000 |        0.6213 |           0.3694 |        0.0094 |         0.7297 |           0.6213 |           0.0058 |            0.7297 | 0.2011 | 0.0558 |
| A3_pos15              |            5.0000 |             20.0000 |        0.7204 |           0.2738 |        0.0058 |         0.7990 |           0.7204 |           0.0032 |            0.7990 | 0.2988 | 0.0739 |
| A3_pos15              |           10.0000 |              5.0000 |        0.3778 |           0.6090 |        0.0132 |         0.5324 |           0.3778 |           0.0094 |            0.5324 | 0.1790 | 0.0373 |
| A3_pos15              |           10.0000 |             10.0000 |        0.5045 |           0.4861 |        0.0094 |         0.6397 |           0.5045 |           0.0058 |            0.6397 | 0.1360 | 0.0378 |
| A3_pos15              |           10.0000 |             20.0000 |        0.6213 |           0.3729 |        0.0058 |         0.7297 |           0.6213 |           0.0032 |            0.7297 | 0.2213 | 0.0553 |
| A3_pos15_GK_mult125   |            1.0000 |              5.0000 |        0.7382 |           0.2486 |        0.0132 |         0.8119 |           0.7382 |           0.0094 |            0.8119 | 0.3334 | 0.0972 |
| A3_pos15_GK_mult125   |            1.0000 |             10.0000 |        0.8070 |           0.1836 |        0.0094 |         0.8596 |           0.8070 |           0.0058 |            0.8596 | 0.2934 | 0.0927 |
| A3_pos15_GK_mult125   |            1.0000 |             20.0000 |        0.8527 |           0.1415 |        0.0058 |         0.8946 |           0.8527 |           0.0032 |            0.8946 | 0.4019 | 0.1125 |
| A3_pos15_GK_mult125   |            3.0000 |              5.0000 |        0.5819 |           0.4049 |        0.0132 |         0.6993 |           0.5819 |           0.0094 |            0.6993 | 0.2076 | 0.0589 |
| A3_pos15_GK_mult125   |            3.0000 |             10.0000 |        0.6877 |           0.3029 |        0.0094 |         0.7765 |           0.6877 |           0.0058 |            0.7765 | 0.2244 | 0.0699 |
| A3_pos15_GK_mult125   |            3.0000 |             20.0000 |        0.7682 |           0.2260 |        0.0058 |         0.8335 |           0.7682 |           0.0032 |            0.8335 | 0.3318 | 0.0929 |
| A3_pos15_GK_mult125   |            5.0000 |              5.0000 |        0.4946 |           0.4922 |        0.0132 |         0.6307 |           0.4946 |           0.0094 |            0.6307 | 0.1701 | 0.0471 |
| A3_pos15_GK_mult125   |            5.0000 |             10.0000 |        0.6116 |           0.3790 |        0.0094 |         0.7216 |           0.6116 |           0.0058 |            0.7216 | 0.1751 | 0.0549 |
| A3_pos15_GK_mult125   |            5.0000 |             20.0000 |        0.7122 |           0.2820 |        0.0058 |         0.7933 |           0.7122 |           0.0032 |            0.7933 | 0.2692 | 0.0744 |
| A3_pos15_GK_mult125   |           10.0000 |              5.0000 |        0.3641 |           0.6227 |        0.0132 |         0.5215 |           0.3641 |           0.0094 |            0.5215 | 0.1424 | 0.0340 |
| A3_pos15_GK_mult125   |           10.0000 |             10.0000 |        0.4946 |           0.4960 |        0.0094 |         0.6307 |           0.4946 |           0.0058 |            0.6307 | 0.1127 | 0.0348 |
| A3_pos15_GK_mult125   |           10.0000 |             20.0000 |        0.6116 |           0.3826 |        0.0058 |         0.7216 |           0.6116 |           0.0032 |            0.7216 | 0.1969 | 0.0549 |
| DP_A3_pb_only         |            1.0000 |              5.0000 |        0.7870 |           0.2024 |        0.0105 |         0.8516 |           0.3794 |           0.0089 |            0.6316 | 0.5069 | 0.0687 |
| DP_A3_pb_only         |            1.0000 |             10.0000 |        0.8480 |           0.1439 |        0.0082 |         0.8912 |           0.4094 |           0.0065 |            0.6613 | 0.5720 | 0.0743 |
| DP_A3_pb_only         |            1.0000 |             20.0000 |        0.8854 |           0.1090 |        0.0056 |         0.9201 |           0.4285 |           0.0047 |            0.6827 | 0.6271 | 0.0815 |
| DP_A3_pb_only         |            3.0000 |              5.0000 |        0.6574 |           0.3321 |        0.0105 |         0.7574 |           0.3169 |           0.0089 |            0.5620 | 0.3882 | 0.0550 |
| DP_A3_pb_only         |            3.0000 |             10.0000 |        0.7477 |           0.2441 |        0.0082 |         0.8214 |           0.3629 |           0.0065 |            0.6093 | 0.4725 | 0.0646 |
| DP_A3_pb_only         |            3.0000 |             20.0000 |        0.8155 |           0.1788 |        0.0056 |         0.8704 |           0.3938 |           0.0047 |            0.6456 | 0.5301 | 0.0704 |
| DP_A3_pb_only         |            5.0000 |              5.0000 |        0.5782 |           0.4113 |        0.0105 |         0.6963 |           0.2831 |           0.0089 |            0.5171 | 0.3268 | 0.0464 |
| DP_A3_pb_only         |            5.0000 |             10.0000 |        0.6848 |           0.3070 |        0.0082 |         0.7763 |           0.3317 |           0.0065 |            0.5760 | 0.4156 | 0.0581 |
| DP_A3_pb_only         |            5.0000 |             20.0000 |        0.7666 |           0.2278 |        0.0056 |         0.8355 |           0.3703 |           0.0047 |            0.6196 | 0.4864 | 0.0664 |
| DP_A3_pb_only         |           10.0000 |              5.0000 |        0.4484 |           0.5411 |        0.0105 |         0.5947 |           0.2189 |           0.0089 |            0.4417 | 0.2427 | 0.0340 |
| DP_A3_pb_only         |           10.0000 |             10.0000 |        0.5782 |           0.4136 |        0.0082 |         0.6963 |           0.2831 |           0.0065 |            0.5171 | 0.3327 | 0.0463 |
| DP_A3_pb_only         |           10.0000 |             20.0000 |        0.6848 |           0.3095 |        0.0056 |         0.7763 |           0.3317 |           0.0047 |            0.5760 | 0.4156 | 0.0581 |
| PTS_A3_pb4w30_str6w10 |            1.0000 |              5.0000 |        0.7870 |           0.2024 |        0.0105 |         0.8516 |           0.6058 |           0.0087 |            0.7541 | 0.3940 | 0.0618 |
| PTS_A3_pb4w30_str6w10 |            1.0000 |             10.0000 |        0.8480 |           0.1439 |        0.0082 |         0.8912 |           0.6532 |           0.0063 |            0.7896 | 0.5338 | 0.0749 |
| PTS_A3_pb4w30_str6w10 |            1.0000 |             20.0000 |        0.8854 |           0.1090 |        0.0056 |         0.9201 |           0.6836 |           0.0038 |            0.8155 | 0.6205 | 0.0813 |
| PTS_A3_pb4w30_str6w10 |            3.0000 |              5.0000 |        0.6574 |           0.3321 |        0.0105 |         0.7574 |           0.5033 |           0.0087 |            0.6700 | 0.2799 | 0.0451 |
| PTS_A3_pb4w30_str6w10 |            3.0000 |             10.0000 |        0.7477 |           0.2441 |        0.0082 |         0.8214 |           0.5753 |           0.0063 |            0.7272 | 0.3998 | 0.0617 |
| PTS_A3_pb4w30_str6w10 |            3.0000 |             20.0000 |        0.8155 |           0.1788 |        0.0056 |         0.8704 |           0.6283 |           0.0038 |            0.7709 | 0.4871 | 0.0706 |
| PTS_A3_pb4w30_str6w10 |            5.0000 |              5.0000 |        0.5782 |           0.4113 |        0.0105 |         0.6963 |           0.4458 |           0.0087 |            0.6160 | 0.2302 | 0.0360 |
| PTS_A3_pb4w30_str6w10 |            5.0000 |             10.0000 |        0.6848 |           0.3070 |        0.0082 |         0.7763 |           0.5255 |           0.0063 |            0.6869 | 0.3426 | 0.0543 |
| PTS_A3_pb4w30_str6w10 |            5.0000 |             20.0000 |        0.7666 |           0.2278 |        0.0056 |         0.8355 |           0.5891 |           0.0038 |            0.7397 | 0.4242 | 0.0642 |
| PTS_A3_pb4w30_str6w10 |           10.0000 |              5.0000 |        0.4484 |           0.5411 |        0.0105 |         0.5947 |           0.3444 |           0.0087 |            0.5261 | 0.1541 | 0.0235 |
| PTS_A3_pb4w30_str6w10 |           10.0000 |             10.0000 |        0.5782 |           0.4136 |        0.0082 |         0.6963 |           0.4458 |           0.0063 |            0.6160 | 0.2604 | 0.0411 |
| PTS_A3_pb4w30_str6w10 |           10.0000 |             20.0000 |        0.6848 |           0.3095 |        0.0056 |         0.7763 |           0.5255 |           0.0038 |            0.6869 | 0.3426 | 0.0543 |

## Task 5 — Corrected Daily Scan Summary

**As of 2026-05-15** — 56 active setups

### Liquidity warning distribution (T1, at 10% ADV)

| liq_warning_T1   |   count |
|:-----------------|--------:|
| OK               |      55 |
| WARN_NEAR        |       1 |

### Recommendation distribution

| recommendation   |   count |
|:-----------------|--------:|
| full_T1          |      56 |

### Actionable setups (non-Watch_only, non-skip)

| symbol   |   close_VND | recommended_sleeve   | pts_state   | gk10_confirmed   |   ema_dist_pct |   adv50_B_VND |   target_T1_M |   max_allowed_10pct_M |   effective_T1_M | liq_warning_T1   | liq_warning_full_pos   | recommendation   |   pb_trigger_price |   str_trigger_price |
|:---------|------------:|:---------------------|:------------|:-----------------|---------------:|--------------:|--------------:|----------------------:|-----------------:|:-----------------|:-----------------------|:-----------------|-------------------:|--------------------:|
| VRE      |       34000 | Growth               | PB_HIT      | N                |         4.6200 |      226.6950 |      166.7000 |            22669.5000 |         166.7000 | OK               | OK                     | full_T1          |            35.0400 |             38.6900 |
| LPB      |       51500 | Growth               | PB_HIT      | N                |         3.7100 |       78.0040 |      166.7000 |             7800.4000 |         166.7000 | OK               | OK                     | full_T1          |            46.0300 |             50.8300 |
| TCO      |       15500 | Growth               | STR_HIT     | N                |         3.4200 |        5.8520 |      166.7000 |              585.2000 |         166.7000 | OK               | OK                     | full_T1          |            10.4600 |             11.5500 |
| POW      |       14100 | Growth               | PB_WAIT     | Y                |         3.3700 |      220.0250 |      208.3000 |            22002.5000 |         208.3000 | OK               | OK                     | full_T1          |            13.3900 |             14.7900 |
| HDB      |       27550 | Growth               | PB_WAIT     | Y                |         2.3800 |      354.3310 |      208.3000 |            35433.1000 |         208.3000 | OK               | OK                     | full_T1          |            25.5400 |             28.2000 |
| PSI      |        8500 | Growth               | PB_WAIT     | Y                |         1.8100 |        2.6940 |      208.3000 |              269.4000 |         134.7000 | OK               | WARN_OVER              | full_T1          |             8.0600 |              8.9000 |
| VPL      |       88400 | Growth               | PB_WAIT     | Y                |         1.5200 |       74.2210 |      208.3000 |             7422.1000 |         208.3000 | OK               | OK                     | full_T1          |            85.4400 |             94.3400 |
| FUEVN100 |       26440 | Growth               | PB_WAIT     | Y                |         0.2400 |        2.5420 |      208.3000 |              254.2000 |         127.1000 | WARN_NEAR        | WARN_OVER              | full_T1          |            25.2100 |             27.8400 |
| HHS      |       13000 | Growth               | PB_HIT      | N                |         0.0200 |       40.3670 |      166.7000 |             4036.7000 |         166.7000 | OK               | OK                     | full_T1          |            13.2500 |             14.6300 |
| MSN      |       77500 | Growth               | PB_WAIT     | Y                |        -0.6300 |      503.5970 |      208.3000 |            50359.7000 |         208.3000 | OK               | OK                     | full_T1          |            74.1100 |             81.8300 |
| VJC      |      171300 | Growth               | PB_HIT      | N                |        -1.7000 |      222.1250 |      166.7000 |            22212.5000 |         166.7000 | OK               | OK                     | full_T1          |           171.5500 |            189.4200 |
| HPG      |       26550 | Growth               | PB_HIT      | N                |        -3.0700 |     1014.6720 |      166.7000 |           101467.2000 |         166.7000 | OK               | OK                     | full_T1          |            27.4100 |             30.2600 |
| NRC      |        6200 | Growth               | PB_HIT      | N                |        -3.3200 |        7.1090 |      166.7000 |              710.9000 |         166.7000 | OK               | OK                     | full_T1          |             6.3400 |              7.0000 |
| BAF      |       35300 | Defensive_PTS        | PB_WAIT     | N                |        -1.2200 |       71.2160 |      166.7000 |             7121.6000 |         166.7000 | OK               | OK                     | full_T1          |            35.2300 |             38.9000 |
| MWG      |       82000 | Defensive_PTS        | PB_WAIT     | N                |        -2.1900 |      607.1600 |      166.7000 |            60716.0000 |         166.7000 | OK               | OK                     | full_T1          |            81.4100 |             89.8900 |
| ILS      |       24400 | PTS                  | PB_WAIT     | N                |         8.6500 |        2.2840 |      166.7000 |              228.4000 |         114.2000 | OK               | WARN_OVER              | full_T1          |            22.8500 |             25.2300 |
| GVR      |       37750 | PTS                  | PB_WAIT     | N                |         7.8500 |      152.4760 |      166.7000 |            15247.6000 |         166.7000 | OK               | OK                     | full_T1          |            34.4200 |             38.0000 |
| SAB      |       48550 | PTS                  | PB_WAIT     | N                |         3.7800 |       38.9780 |      166.7000 |             3897.8000 |         166.7000 | OK               | OK                     | full_T1          |            44.4000 |             49.0300 |
| E1VFVN30 |       36520 | PTS                  | PB_WAIT     | N                |         2.0100 |       19.4310 |      166.7000 |             1943.1000 |         166.7000 | OK               | OK                     | full_T1          |            34.3400 |             37.9200 |
| VTO      |       12250 | PTS                  | PB_WAIT     | N                |         1.9300 |        4.3400 |      166.7000 |              434.0000 |         166.7000 | OK               | OK                     | full_T1          |            11.4700 |             12.6700 |

## Key Conclusions

### 1. ADV unit fix
- Original scan: `adv50_B_VND` was in units of million VND (mislabeled as billion)
- Fixed: use `panel['value'].rolling(50)` (or `close × volume × 1000`) → true VND
- HPG corrected ADV50: ~1,000B VND/day (not 1B as originally shown)

### 2. PTS/DP exclusion is non-zero after fix
- After tagging adv50_value onto PTS/DP trades, run recomputed capacity table
- Actual exclusion and partial-fill rates depend on portfolio size and participation
- See phase31_liquidity_recomputed.csv for full breakdown

### 3. Recommended operating parameters (post-audit)
- Use `adv50_VND = panel['value'].rolling(50).mean()` (fill NaN with `close × volume × 1000`)
- Compare T1 size (not full position) vs ADV × participation for entry decisions
- Flag full-position eventual fill as a separate 'liq_warning_full' field
- Run `portfolio_optimization_phase31.py` daily (replaces `--phase scan` in phase3)

### 4. No strategy logic changes
- Entry/exit rules, PTS state machine, GK multiplier: unchanged
- Only capacity accounting and scan reporting corrected
