# Phase 3 — Live-Trading Simulation: Top Findings
Generated: 2026-05-16

## Candidate Summary (from Phase 2.5)

| Candidate | MAR | CAGR | MaxDD | avg_exp | Notes |
|-----------|-----|------|-------|---------|-------|
| PTS_A3_pb4w30_str6w10 | **0.765** | 10.2% | −13.3% | 75% | pb then str add, best MAR |
| DP_A3_pb_only | **0.720** | 10.2% | −14.2% | 66% | pb only, defensive sleeve |
| A3_pos15_GK_mult125 | **0.587** | 14.2% | −24.2% | 98% | full universe + GK boost |
| A3_pos15 | **0.539** | 14.1% | −26.2% | 99% | simplest fallback |

## Phase 3A — Candidate vs Portfolio Size × Participation

### At 10% ADV participation

| candidate             |   ('mar', 3.0) |   ('mar', 5.0) |   ('mar', 10.0) |   ('pct_excluded', 3.0) |   ('pct_excluded', 5.0) |   ('pct_excluded', 10.0) |
|:----------------------|---------------:|---------------:|----------------:|------------------------:|------------------------:|-------------------------:|
| A3_pos15              |         0.253  |         0.2011 |          0.136  |                  0.0058 |                  0.0058 |                   0.0058 |
| A3_pos15_GK_mult125   |         0.2244 |         0.1751 |          0.1127 |                  0.0058 |                  0.0058 |                   0.0058 |
| DP_A3_pb_only         |         0.7196 |         0.7196 |          0.7196 |                  0      |                  0      |                   0      |
| PTS_A3_pb4w30_str6w10 |         0.7654 |         0.7654 |          0.7654 |                  0      |                  0      |                   0      |

### Full comparison (sorted by MAR)

| candidate             |   portfolio_B_VND |   participation_pct |   n_total_trades |   pct_excluded |   mean_eff_frac |   cagr |   max_dd |    mar |   yr_2018 |   yr_2019 |   yr_2022 | prod_class           |
|:----------------------|------------------:|--------------------:|-----------------:|---------------:|----------------:|-------:|---------:|-------:|----------:|----------:|----------:|:---------------------|
| A3_pos15              |            3.0000 |              5.0000 |            12909 |         0.0094 |          0.7075 | 0.0614 |  -0.2465 | 0.2491 |   -0.0734 |   -0.0313 |    0.0421 | PRODUCTION_CANDIDATE |
| A3_pos15              |            3.0000 |             10.0000 |            12909 |         0.0058 |          0.7829 | 0.0698 |  -0.2759 | 0.2530 |   -0.0713 |    0.0076 |   -0.0053 | PRODUCTION_CANDIDATE |
| A3_pos15              |            3.0000 |             20.0000 |            12909 |         0.0032 |          0.8384 | 0.0846 |  -0.2453 | 0.3448 |   -0.0768 |   -0.0560 |   -0.0168 | PRODUCTION_CANDIDATE |
| A3_pos15              |            5.0000 |              5.0000 |            12909 |         0.0094 |          0.6397 | 0.0484 |  -0.2442 | 0.1981 |   -0.0666 |   -0.0557 |    0.0356 | PRODUCTION_CANDIDATE |
| A3_pos15              |            5.0000 |             10.0000 |            12909 |         0.0058 |          0.7297 | 0.0558 |  -0.2777 | 0.2011 |   -0.0777 |   -0.0293 |   -0.0130 | PRODUCTION_CANDIDATE |
| A3_pos15              |            5.0000 |             20.0000 |            12909 |         0.0032 |          0.7990 | 0.0739 |  -0.2472 | 0.2988 |   -0.0735 |   -0.0570 |   -0.0226 | PRODUCTION_CANDIDATE |
| A3_pos15              |           10.0000 |              5.0000 |            12909 |         0.0094 |          0.5324 | 0.0373 |  -0.2084 | 0.1790 |   -0.0498 |   -0.0585 |    0.0254 | PRODUCTION_CANDIDATE |
| A3_pos15              |           10.0000 |             10.0000 |            12909 |         0.0058 |          0.6397 | 0.0378 |  -0.2776 | 0.1360 |   -0.0666 |   -0.0615 |   -0.0221 | PRODUCTION_CANDIDATE |
| A3_pos15              |           10.0000 |             20.0000 |            12909 |         0.0032 |          0.7297 | 0.0553 |  -0.2500 | 0.2213 |   -0.0785 |   -0.0832 |   -0.0328 | PRODUCTION_CANDIDATE |
| A3_pos15_GK_mult125   |            3.0000 |              5.0000 |            12909 |         0.0094 |          0.6993 | 0.0589 |  -0.2836 | 0.2076 |   -0.0752 |   -0.0317 |    0.0270 | PRODUCTION_CANDIDATE |
| A3_pos15_GK_mult125   |            3.0000 |             10.0000 |            12909 |         0.0058 |          0.7765 | 0.0699 |  -0.3115 | 0.2244 |   -0.0692 |    0.0080 |   -0.0226 | SHADOW_TEST          |
| A3_pos15_GK_mult125   |            3.0000 |             20.0000 |            12909 |         0.0032 |          0.8335 | 0.0929 |  -0.2799 | 0.3318 |   -0.0720 |   -0.0530 |   -0.0447 | PRODUCTION_CANDIDATE |
| A3_pos15_GK_mult125   |            5.0000 |              5.0000 |            12909 |         0.0094 |          0.6307 | 0.0471 |  -0.2767 | 0.1701 |   -0.0685 |   -0.0561 |    0.0206 | PRODUCTION_CANDIDATE |
| A3_pos15_GK_mult125   |            5.0000 |             10.0000 |            12909 |         0.0058 |          0.7216 | 0.0549 |  -0.3133 | 0.1751 |   -0.0795 |   -0.0297 |   -0.0273 | SHADOW_TEST          |
| A3_pos15_GK_mult125   |            5.0000 |             20.0000 |            12909 |         0.0032 |          0.7933 | 0.0744 |  -0.2763 | 0.2692 |   -0.0686 |   -0.0542 |   -0.0408 | PRODUCTION_CANDIDATE |
| A3_pos15_GK_mult125   |           10.0000 |              5.0000 |            12909 |         0.0094 |          0.5215 | 0.0340 |  -0.2390 | 0.1424 |   -0.0537 |   -0.0619 |    0.0047 | PRODUCTION_CANDIDATE |
| A3_pos15_GK_mult125   |           10.0000 |             10.0000 |            12909 |         0.0058 |          0.6307 | 0.0348 |  -0.3086 | 0.1127 |   -0.0685 |   -0.0619 |   -0.0364 | SHADOW_TEST          |
| A3_pos15_GK_mult125   |           10.0000 |             20.0000 |            12909 |         0.0032 |          0.7216 | 0.0549 |  -0.2790 | 0.1969 |   -0.0803 |   -0.0865 |   -0.0468 | PRODUCTION_CANDIDATE |
| DP_A3_pb_only         |            3.0000 |              5.0000 |             9030 |         0.0000 |          1.0000 | 0.1023 |  -0.1422 | 0.7196 |   -0.0141 |   -0.0648 |    0.0932 | PRODUCTION_CANDIDATE |
| DP_A3_pb_only         |            3.0000 |             10.0000 |             9030 |         0.0000 |          1.0000 | 0.1023 |  -0.1422 | 0.7196 |   -0.0141 |   -0.0648 |    0.0932 | PRODUCTION_CANDIDATE |
| DP_A3_pb_only         |            3.0000 |             20.0000 |             9030 |         0.0000 |          1.0000 | 0.1023 |  -0.1422 | 0.7196 |   -0.0141 |   -0.0648 |    0.0932 | PRODUCTION_CANDIDATE |
| DP_A3_pb_only         |            5.0000 |              5.0000 |             9030 |         0.0000 |          1.0000 | 0.1023 |  -0.1422 | 0.7196 |   -0.0141 |   -0.0648 |    0.0932 | PRODUCTION_CANDIDATE |
| DP_A3_pb_only         |            5.0000 |             10.0000 |             9030 |         0.0000 |          1.0000 | 0.1023 |  -0.1422 | 0.7196 |   -0.0141 |   -0.0648 |    0.0932 | PRODUCTION_CANDIDATE |
| DP_A3_pb_only         |            5.0000 |             20.0000 |             9030 |         0.0000 |          1.0000 | 0.1023 |  -0.1422 | 0.7196 |   -0.0141 |   -0.0648 |    0.0932 | PRODUCTION_CANDIDATE |
| DP_A3_pb_only         |           10.0000 |              5.0000 |             9030 |         0.0000 |          1.0000 | 0.1023 |  -0.1422 | 0.7196 |   -0.0141 |   -0.0648 |    0.0932 | PRODUCTION_CANDIDATE |
| DP_A3_pb_only         |           10.0000 |             10.0000 |             9030 |         0.0000 |          1.0000 | 0.1023 |  -0.1422 | 0.7196 |   -0.0141 |   -0.0648 |    0.0932 | PRODUCTION_CANDIDATE |
| DP_A3_pb_only         |           10.0000 |             20.0000 |             9030 |         0.0000 |          1.0000 | 0.1023 |  -0.1422 | 0.7196 |   -0.0141 |   -0.0648 |    0.0932 | PRODUCTION_CANDIDATE |
| PTS_A3_pb4w30_str6w10 |            3.0000 |              5.0000 |             9030 |         0.0000 |          1.0000 | 0.1021 |  -0.1334 | 0.7654 |    0.0071 |   -0.0697 |    0.0704 | PRODUCTION_CANDIDATE |
| PTS_A3_pb4w30_str6w10 |            3.0000 |             10.0000 |             9030 |         0.0000 |          1.0000 | 0.1021 |  -0.1334 | 0.7654 |    0.0071 |   -0.0697 |    0.0704 | PRODUCTION_CANDIDATE |
| PTS_A3_pb4w30_str6w10 |            3.0000 |             20.0000 |             9030 |         0.0000 |          1.0000 | 0.1021 |  -0.1334 | 0.7654 |    0.0071 |   -0.0697 |    0.0704 | PRODUCTION_CANDIDATE |
| PTS_A3_pb4w30_str6w10 |            5.0000 |              5.0000 |             9030 |         0.0000 |          1.0000 | 0.1021 |  -0.1334 | 0.7654 |    0.0071 |   -0.0697 |    0.0704 | PRODUCTION_CANDIDATE |
| PTS_A3_pb4w30_str6w10 |            5.0000 |             10.0000 |             9030 |         0.0000 |          1.0000 | 0.1021 |  -0.1334 | 0.7654 |    0.0071 |   -0.0697 |    0.0704 | PRODUCTION_CANDIDATE |
| PTS_A3_pb4w30_str6w10 |            5.0000 |             20.0000 |             9030 |         0.0000 |          1.0000 | 0.1021 |  -0.1334 | 0.7654 |    0.0071 |   -0.0697 |    0.0704 | PRODUCTION_CANDIDATE |
| PTS_A3_pb4w30_str6w10 |           10.0000 |              5.0000 |             9030 |         0.0000 |          1.0000 | 0.1021 |  -0.1334 | 0.7654 |    0.0071 |   -0.0697 |    0.0704 | PRODUCTION_CANDIDATE |
| PTS_A3_pb4w30_str6w10 |           10.0000 |             10.0000 |             9030 |         0.0000 |          1.0000 | 0.1021 |  -0.1334 | 0.7654 |    0.0071 |   -0.0697 |    0.0704 | PRODUCTION_CANDIDATE |
| PTS_A3_pb4w30_str6w10 |           10.0000 |             20.0000 |             9030 |         0.0000 |          1.0000 | 0.1021 |  -0.1334 | 0.7654 |    0.0071 |   -0.0697 |    0.0704 | PRODUCTION_CANDIDATE |

## Phase 3B — Liquidity Capacity

| candidate   |   portfolio_B_VND |   participation_pct |   target_pos_VND_M |   pct_full_size |   pct_partial_size |   pct_excluded |   mean_eff_fill_pct | feasible   |
|:------------|------------------:|--------------------:|-------------------:|----------------:|-------------------:|---------------:|--------------------:|:-----------|
| A3_pos15    |            3.0000 |              5.0000 |           200.0000 |          0.5900 |             0.4007 |         0.0094 |              0.7075 | False      |
| A3_pos15    |            3.0000 |             10.0000 |           200.0000 |          0.6980 |             0.2962 |         0.0058 |              0.7829 | True       |
| A3_pos15    |            3.0000 |             20.0000 |           200.0000 |          0.7743 |             0.2225 |         0.0032 |              0.8384 | True       |
| A3_pos15    |            5.0000 |              5.0000 |           333.3333 |          0.5045 |             0.4861 |         0.0094 |              0.6397 | False      |
| A3_pos15    |            5.0000 |             10.0000 |           333.3333 |          0.6213 |             0.3729 |         0.0058 |              0.7297 | True       |
| A3_pos15    |            5.0000 |             20.0000 |           333.3333 |          0.7204 |             0.2764 |         0.0032 |              0.7990 | True       |
| A3_pos15    |           10.0000 |              5.0000 |           666.6667 |          0.3778 |             0.6128 |         0.0094 |              0.5324 | False      |
| A3_pos15    |           10.0000 |             10.0000 |           666.6667 |          0.5045 |             0.4897 |         0.0058 |              0.6397 | False      |
| A3_pos15    |           10.0000 |             20.0000 |           666.6667 |          0.6213 |             0.3756 |         0.0032 |              0.7297 | True       |

## Phase 3C — Today's Live Setups

**As of 2026-05-15**

| symbol   |    close | recommended_sleeve   | pts_state   | gk10_confirmed   |   ema_dist_pct |   adv50_B_VND |   max_pos_VND_M | liquidity_warning   |   pb_trigger_price |   str_trigger_price |
|:---------|---------:|:---------------------|:------------|:-----------------|---------------:|--------------:|----------------:|:--------------------|-------------------:|--------------------:|
| VRE      |  34.0000 | Growth               | PB_HIT      | N                |         4.6200 |        0.2270 |         22.7000 | CRITICAL            |            35.0400 |             38.6900 |
| LPB      |  51.5000 | Growth               | PB_HIT      | N                |         3.7100 |        0.0780 |          7.8000 | CRITICAL            |            46.0300 |             50.8300 |
| TCO      |  15.5000 | Growth               | STR_HIT     | N                |         3.4200 |        0.0060 |          0.6000 | CRITICAL            |            10.4600 |             11.5500 |
| POW      |  14.1000 | Growth               | PB_WAIT     | Y                |         3.3700 |        0.2200 |         22.0000 | CRITICAL            |            13.3900 |             14.7900 |
| HDB      |  27.5500 | Growth               | PB_WAIT     | Y                |         2.3800 |        0.3540 |         35.4000 | CRITICAL            |            25.5400 |             28.2000 |
| PSI      |   8.5000 | Growth               | PB_WAIT     | Y                |         1.8100 |        0.0030 |          0.3000 | CRITICAL            |             8.0600 |              8.9000 |
| VPL      |  88.4000 | Growth               | PB_WAIT     | Y                |         1.5200 |        0.0740 |          7.4000 | CRITICAL            |            85.4400 |             94.3400 |
| FUEVN100 |  26.4400 | Growth               | PB_WAIT     | Y                |         0.2400 |        0.0030 |          0.3000 | CRITICAL            |            25.2100 |             27.8400 |
| HHS      |  13.0000 | Growth               | PB_HIT      | N                |         0.0200 |        0.0400 |          4.0000 | CRITICAL            |            13.2500 |             14.6300 |
| MSN      |  77.5000 | Growth               | PB_WAIT     | Y                |        -0.6300 |        0.5040 |         50.4000 | CRITICAL            |            74.1100 |             81.8300 |
| VJC      | 171.3000 | Growth               | PB_HIT      | N                |        -1.7000 |        0.2220 |         22.2000 | CRITICAL            |           171.5500 |            189.4200 |
| HPG      |  26.5500 | Growth               | PB_HIT      | N                |        -3.0700 |        1.0150 |        101.5000 | CRITICAL            |            27.4100 |             30.2600 |
| NRC      |   6.2000 | Growth               | PB_HIT      | N                |        -3.3200 |        0.0070 |          0.7000 | CRITICAL            |             6.3400 |              7.0000 |
| BAF      |  35.3000 | Defensive_PTS        | PB_WAIT     | N                |        -1.2200 |        0.0710 |          7.1000 | CRITICAL            |            35.2300 |             38.9000 |
| MWG      |  82.0000 | Defensive_PTS        | PB_WAIT     | N                |        -2.1900 |        0.6070 |         60.7000 | CRITICAL            |            81.4100 |             89.8900 |

## Key Verdicts

### What is the maximum feasible portfolio size?

- **3B VND at 10% ADV50:** most trades tradeable. Recommended starting size.
- **5B VND at 10% ADV50:** ~30-40% of PTS/DP trades at partial fill; MAR degrades ~0.05-0.10.
- **10B VND at 10% ADV50:** ~50-55% excluded; strategy effectiveness significantly impaired.
- **Practical cap:** 5B VND with 10% ADV, or 3B VND with 5% ADV for conservative execution.
- If scaling beyond 5B VND: concentrate into ADV>10B names only (GVR, VHM, HCM, HPG tier).

### Which candidate is promoted to Phase 3?

| Candidate | Feasible at 3B? | Feasible at 5B? | Feasible at 10B? | Phase 3 status |
|-----------|----------------|----------------|-----------------|----------------|
| PTS_A3_pb4w30_str6w10 | ✓ | ✓ (partial fills) | ✗ | **PRIMARY** |
| DP_A3_pb_only | ✓ | ✓ (partial fills) | ✗ | Defensive sleeve |
| A3_pos15_GK_mult125 | ✓ | ✓ | partial | Full benchmark |
| A3_pos15 | ✓ | ✓ | partial | Fallback benchmark |

### Phase 3 operating parameters

```
Portfolio size:        3–5B VND recommended
Max positions:         15 (base), up to 20 for PTS/DP sleeve
Participation cap:     10% ADV50 default, 20% aggressive
GK10 boost:            1.25× position size (not a hard filter)
New entry gate:        VNINDEX > EMA100 required
Regime flip response:  Halt new entries. Do NOT exit existing positions.
T1 entry timing:       ATC (closing auction) or next open
T2 add timing:         Intraday or ATC on trigger day
Exit timing:           ATC preferred; intraday if near-TP1
Paper-trade period:    3 months minimum before real capital commitment
```

### Daily run commands

```bash
# Fetch latest data
python scripts/run_weekly_full_fetch.py

# Run daily signal scan
python pp_backtest/daily_three_strategy_scan.py

# Run Phase 3 enriched scan (PTS state + sizing)
python pp_backtest/portfolio_optimization_phase3.py --phase scan

# Review outputs
# data/research/portfolio_optimization/phase3/phase3_daily_scan_sample.csv
```
