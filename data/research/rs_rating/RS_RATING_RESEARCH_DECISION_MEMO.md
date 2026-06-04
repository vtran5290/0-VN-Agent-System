# RS Rating Research — Decision Memo
_Date: 2026-05-26_

> **SAFETY:** This is a research context lens only. It does **not** set or override
> `final_action`. No production changes. No OMS. No live trading.

---

## Research Question
Does an IBD-style cross-sectional Relative Strength Rating (1–99) applied as an
entry filter improve A3 EMA Cloud entry signals from 2012 to latest available data?

## Data
| Item | Value |
| --- | --- |
| OHLCV panel | `ohlcv_panel_ext2012.parquet` (2012-2026) |
| Benchmark | `ta_vnindex.parquet` |
| Universe | `universe_liquid_adv50_2b.txt` (272 symbols) |
| EX_VIN (excluded from ranking) | VIC, VHM, VRE |
| Min bars before ranking | 252 trading days |
| A3 signal | close > EMA100 AND EMA20 > EMA100 (first bar entering cloud) |
| Forward returns | 21-day and 63-day |

## Variants Tested
| Variant | Family | Description |
| --- | --- | --- |
| A1 | A | IBD standard (40% 12m / 20% each 9/6/3m) |
| A2 | A | Equal weight 12/9/6/3m |
| A3v | A | Recent-heavy 12/9/6/3m (20/20/30/30%) |
| B1 | B | VN4M: 10% 6m / 40% 3m / 30% 2m / 20% 1m |
| B2 | B | Short-heavy: 20% 3m / 50% 2m / 30% 1m |
| B3 | B | Equal weight 6/3/2/1m |
| C1 | C | RS line 3m momentum |
| C2 | C | RS line 1m momentum |
| C3 | C | RS line acceleration (3m minus 6m RS momentum) |
| D1 | D | Sharpe proxy: 3m return / 3m volatility |
| D2 | D | Sortino proxy: 3m return / 3m downside vol |
| D3 | D | Calmar proxy: 3m return / 3m max drawdown |

## Time Splits
| Split | Period | Role |
| --- | --- | --- |
| IS_2012_2016 | 2012-01-01 – 2016-12-31 | In-sample (threshold selection) |
| OOS1_2017_2020 | 2017-01-01 – 2020-12-31 | Out-of-sample 1 |
| OOS2_2021_2023 | 2021-01-01 – 2023-12-31 | Out-of-sample 2 |
| OOS3_2024_now | 2024-01-01 – latest | Out-of-sample 3 (most recent) |

## Overlay Types Tested
- **Display only** (threshold = 0): no filter, baseline comparison
- **Entry filter** at RS ≥ 40 / 50 / 60 / 70 / 80: only take A3 signals where RS rating meets threshold

## Overfitting Guards
- Threshold selected on IS only; never on OOS data.
- Classification requires positive lift in ALL 3 OOS splits for CANDIDATE status.
- PAPER_SHADOW_ONLY requires positive lift in >= 2 of 3 OOS splits.
- Universe is fixed (adv50_2b), not hand-optimised.

## Results

### Baseline (raw A3 signals, no RS filter)
| Split | N signals | Mean fwd21 | Win rate 21d | Mean fwd63 |
| --- | --- | --- | --- | --- |
| IS 2012-2016 | 80,998 | +1.99% | 50.0% | +4.53% |
| OOS1 2017-2020 | 82,466 | +2.19% | 50.6% | +7.14% |
| OOS2 2021-2023 | 84,722 | +1.76% | 50.9% | +4.19% |
| OOS3 2024-now | 58,261 | +0.81% | 45.4% | +3.22% |

Note: OOS3 baseline is materially weaker (45.4% win rate vs 50%+ in earlier periods),
indicating A3 cloud entries are less effective in the 2024-present environment overall.

### Key Findings

**C3 (RS line acceleration = 3m RS momentum minus 6m RS momentum, threshold >= 70):**
- OOS1 lift: +1.00 pp mean fwd21 (filters 82,466 → 16,966 signals, win rate 50.6% → 53.2%)
- OOS2 lift: +1.69 pp mean fwd21 (filters 84,722 → 20,168 signals, win rate 50.9% → 52.9%)
- OOS3 lift: -0.35 pp (breaks down in 2024+, win rate drops 45.4% → 43.8%)
- Interpretation: C3 rewards stocks that are *accelerating* their RS momentum relative to VNINDEX.
  This is a momentum-of-momentum signal, not a raw strength filter. It worked as an effective
  regime discriminator in 2017-2023 but breaks in the current weaker-market environment.

**Family A/B/D variants (threshold >= 80):**
- All show negative lift in OOS1 and OOS2 (filtering to top 20% RS actually hurts 21d returns).
- All show positive lift in OOS3 only (+0.62 to +1.00 pp), which is insufficient for CANDIDATE.
- Interpretation: High-RS entry filter causes mean-reversion drag in bull-market periods.
  Only in the weaker 2024+ period does high-prior-RS predict better forward returns —
  likely because absolute momentum is more predictive in a selective/flat market.
- This is a **regime-reversal** finding: RS filter effect flips sign across market cycles.

**Overfitting note:** All variants chose threshold=80 on IS (highest available), which is a
red flag for threshold overfitting. The IS period (2012-2016) may have a specific market
structure where high-RS filtering appears helpful but does not generalize.

### Classification Summary
| Variant | Family | Best IS Threshold | Classification |
| --- | --- | --- | --- |
| C3 | C | 70 | PAPER_SHADOW_ONLY |
| A1 | A | 80 | WATCHLIST_ONLY |
| A3v | A | 80 | WATCHLIST_ONLY |
| A2 | A | 80 | WATCHLIST_ONLY |
| B2 | B | 80 | WATCHLIST_ONLY |
| B3 | B | 80 | WATCHLIST_ONLY |
| C1 | C | 80 | WATCHLIST_ONLY |
| B1 | B | 80 | WATCHLIST_ONLY |
| C2 | C | 80 | WATCHLIST_ONLY |
| D1 | D | 80 | WATCHLIST_ONLY |
| D2 | D | 80 | WATCHLIST_ONLY |
| D3 | D | 80 | WATCHLIST_ONLY |

### PAPER_SHADOW_ONLY (1 variant(s))
| Variant | Best Thr | IS mean_fwd21 | OOS1 vs raw | OOS2 vs raw | OOS3 vs raw |
| --- | --- | --- | --- | --- | --- |
| C3 | 70 | 1.66 pp | 1.0 pp | 1.69 pp | -0.35 pp |

### WATCHLIST_ONLY (11 variant(s))
| Variant | Best Thr | IS mean_fwd21 | OOS1 vs raw | OOS2 vs raw | OOS3 vs raw |
| --- | --- | --- | --- | --- | --- |
| A1 | 80 | 2.16 pp | -0.78 pp | -1.11 pp | 0.62 pp |
| A2 | 80 | 2.21 pp | -0.72 pp | -1.12 pp | 0.71 pp |
| A3v | 80 | 2.28 pp | -0.66 pp | -1.04 pp | 0.75 pp |
| B1 | 80 | 2.07 pp | -0.44 pp | -0.37 pp | 0.71 pp |
| B2 | 80 | 1.91 pp | -0.31 pp | -0.33 pp | 0.7 pp |
| B3 | 80 | 2.16 pp | -0.49 pp | -0.58 pp | 0.8 pp |
| C1 | 80 | 2.02 pp | -0.38 pp | -0.26 pp | 0.85 pp |
| C2 | 80 | 2.14 pp | -0.07 pp | -0.68 pp | 0.77 pp |
| D1 | 80 | 1.92 pp | -0.38 pp | -0.36 pp | 0.9 pp |
| D2 | 80 | 1.89 pp | -0.39 pp | -0.32 pp | 1.0 pp |
| D3 | 80 | 2.18 pp | -0.46 pp | -0.61 pp | 0.82 pp |

## Decision

**PAPER SHADOW — One variant qualifies: C3 (RS line acceleration >= 70).**

C3 showed consistent positive lift in OOS1 (+1.0 pp) and OOS2 (+1.69 pp) but broke down
in OOS3 2024+ (-0.35 pp). The OOS3 breakdown is a material concern: it suggests C3's edge
may be regime-dependent and is not operative in the current market environment.

**Recommended next steps for operator:**
1. Review `overlay_backtest.csv` rows for C3 — particularly OOS3 data — before committing to paper shadow.
2. If paper shadow is approved: monitor C3 >= 70 filter alongside A3 scan for 30 trading days. Do not act on it.
3. Re-evaluate quarterly. If OOS3 lift turns positive over the next quarter, upgrade to CANDIDATE.
4. All other variants (A, B, D families): WATCHLIST ONLY. Revisit if market regime shifts.

**Operator decision required** before any integration into daily scan.
Do not add RS Rating to final_action logic without explicit written approval.

---

## SSOT Confirmation
- `final_action` is unchanged by this research.
- RS Rating is a research/context lens only.
- No OMS, DNSE, or live trading exposure.
- Real capital: NO-GO.

## Output Files
| File | Contents |
| --- | --- |
| `rs_rating_daily.parquet` | Daily RS ratings (1–99) per symbol × 12 variants |
| `overlay_backtest.csv` | Entry-filter backtest: variant × threshold × split |
| `variant_summary.csv` | IS/OOS metrics + classification per variant |
| `RS_RATING_RESEARCH_DECISION_MEMO.md` | This memo |
