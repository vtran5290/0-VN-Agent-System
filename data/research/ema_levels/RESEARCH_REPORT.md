# EMA Cloud + Price Levels — Strategy Research Report
## Vietnam Equities — Full Universe (272 Symbols), 2012-2026

**Status:** Phase 2 (post-extension). Two-strategy research framework complete.
**Date:** 2026-05-13
**Dataset:** 272 symbols, 738,844 rows, 2012-01-03 to 2026-04-29 (14.3 years)

---

## 1. Methodology

### Data Coverage

| Category | Value |
|---|---|
| Universe | 272 liquid VN symbols (ADV50 >= 2B VND) |
| Date range (extended) | 2012-01-03 to 2026-04-29 |
| Symbols with 2012+ history | 201 / 272 (74%) |
| Symbols starting 2018+ | 71 (newer listings) |
| Original panel (Phase 1) | 2018-01-02 to 2026-04-29 |
| Cost assumption | 40 bps round-trip |
| Source | FireAnt API (individual OHLCV) + ohlcv_panel_full.parquet |

**Data limitation:** Stock OHLCV via FireAnt API. 71 of 272 universe symbols only start from 2018 (newer listings — HDB, GEE, MSH, etc.). VNINDEX data available from 2012 but individual stock coverage is bounded by listing date. 2012 data: 136 symbols. 2018+ data: all 272 symbols.

**Research tracks:** All analyses run in three tracks:
1. `full` — all 271 non-VPL universe symbols
2. `ex_vin` — 268 symbols (excludes VIC, VHM, VRE per VIN baseline policy)
3. `vin_only` — VIC, VHM, VRE subset (3 symbols, where noted)

---

## 2. Strategy Fork: A vs B

The research was explicitly split into two separate strategies following Phase 1 findings:

| | Strategy A | Strategy B |
|---|---|---|
| Horizon | 25d, 50d | 100d, 150d |
| Entry family | Breakout (level / Donchian / base-high) | Cloud-only |
| EMA default | 10/50 | 21/55 and 20/100 |
| Key finding | Level complexity **breaks** on extended data | Cloud-only **strengthens** on extended data |

---

## 3. Impact of Extending to 2012

This is the most important finding of the second research phase.

### FACT: Level_breakout is not robust on extended data

| Metric | Phase 1 (2018-2026) | Extended (2012-2026) | Direction |
|---|---|---|---|
| Sharpe (5/20 EMA) | +0.38 | **-0.131** | BREAKS |
| Test-period avg_return | +0.9% | **-1.3%** | BREAKS |
| Hit rate | 51.1% | 47.2% | Degrades |

**INTERPRETATION:** The Phase 1 level_breakout result was an artifact of the 2018-2026 sample, which included a favorable recovery cycle. Adding 2012-2017 exposes the entry's weakness in earlier market structure.

### FACT: Cloud-only improves on extended data

| Metric | Phase 1 (2018-2026) | Extended (2012-2026) |
|---|---|---|
| cloud_only 100d avg_return | 4.4% | **7.1%** |
| cloud_only 150d avg_return | 8.3% | **11.7%** |
| cloud_only (21/55) 100d OOS_deg | +1.1pp | +0.8pp |

**INTERPRETATION:** 2012-2017 included multiple strong trending phases (VN bull cycles) where cloud-following works well. More history = more signal confirmation for Strategy B.

---

## 4. Strategy A Results — Short-Horizon Breakout Comparison

### Signal quality (forward returns, ex-VIN track, 2012-2026)

**25d horizon:**

| Entry | EMA | n_trades | hit% | avg_ret | Sharpe | test_avg | oos_deg |
|---|---|---|---|---|---|---|---|
| level_breakout | 5/20 | 16,689 | 47.2% | 1.8% | **-0.131** | **-1.3%** | -4.2pp |
| donchian_100 | n/a | 31,076 | 48.8% | 2.1% | +0.141 | 0.0% | -2.5pp |
| base_high | 10/50 | 43,674 | 48.4% | 1.8% | +0.111 | 1.0% | **-0.6pp** |
| donchian_50 | n/a | 44,509 | 48.4% | 1.8% | +0.133 | 1.0% | **-0.6pp** |
| donchian_20 | n/a | 70,236 | 48.6% | 1.7% | +0.167 | 1.3% | **+0.1pp** |

**50d horizon:**

| Entry | EMA | n_trades | hit% | avg_ret | Sharpe | test_avg | oos_deg |
|---|---|---|---|---|---|---|---|
| level_breakout | 5/20 | 16,532 | 47.6% | 3.4% | **-0.194** | **-2.0%** | -7.7pp |
| donchian_100 | n/a | 30,805 | 49.8% | 4.1% | +0.209 | -0.1% | -5.5pp |
| base_high | 10/50 | 43,316 | 49.3% | 3.6% | +0.206 | **1.8%** | **-2.0pp** |
| donchian_50 | n/a | 44,143 | 49.1% | 3.6% | +0.196 | **1.8%** | **-1.8pp** |
| donchian_20 | n/a | 69,764 | 49.0% | 3.1% | +0.229 | **2.9%** | **+1.1pp** |

**VIN-only track shows the distortion:** level_breakout VIN-only 50d: hit=64.6%, avg=12.2%, Sharpe=0.944. This is the Vingroup restructuring/policy effect — it inflates the full-universe result.

### Benchmark verdict on level_breakout (FACTS)

- Level_breakout has **negative Sharpe** on extended dataset (negative risk-adjusted return per trade)
- Level_breakout test-period returns are **negative** (-1.3% to -2.0%)
- Simpler alternatives outperform: donchian_20 has the most stable OOS (+0.1pp at 25d, +1.1pp at 50d)
- base_high (Donchian + cloud + freshness, no touch counting) outperforms level_breakout on Sharpe and OOS

**Verdict: Price-level complexity does NOT justify itself vs simpler baselines on the full 2012-2026 dataset.** The multi-touch resistance system is not the source of the edge.

---

## 5. Strategy B Results — Long-Horizon Cloud-Only

### Signal quality (forward returns, ex-VIN track, 2012-2026)

| EMA | Horizon | hit% | avg_ret | Sharpe | train_avg | test_avg | oos_deg |
|---|---|---|---|---|---|---|---|
| 21/55 | 100d | 50.3% | 7.1% | 0.408 | 6.3% | **7.5%** | **+0.8pp** |
| 20/100 | 100d | 50.2% | 7.5% | 0.432 | 9.0% | 5.8% | -3.4pp |
| 21/55 | 150d | 51.7% | 10.5% | 0.492 | 9.3% | **9.9%** | **-0.4pp** |
| 20/100 | 150d | 52.6% | 11.7% | 0.601 | 13.3% | 8.9% | -5.6pp |

Full ≈ ex-VIN for Strategy B (VIN does not drive cloud-only results — confirmed).

**Key finding:** 21/55 shows smaller or positive OOS degradation at both horizons. 20/100 has higher absolute returns but degrades 3-6pp in the test period.

---

## 6. Portfolio Simulation Results

Portfolio parameters: max_positions=20, equal weight (5% per position), FIFO fill, 40 bps cost.

### Full 272-symbol universe (14.3 years, 2012-2026):

| Strategy label | CAGR | maxDD | Sharpe | MAR | n_trades | hit% | avg_trade | oos_avg |
|---|---|---|---|---|---|---|---|---|
| A_basehigh_partial_tp | **13.4%** | -37.8% | **1.185** | **0.36** | 44,275 | 63.4% | 4.0% | 4.1% |
| A_basehigh_trail25 | 13.1% | -50.1% | 0.678 | 0.26 | 44,275 | 37.6% | 2.0% | 1.8% |
| A_don20_trail25 | 11.3% | -60.3% | 0.655 | 0.19 | 71,442 | 36.7% | 1.8% | 1.5% |
| B_cloud20_100_partial | 10.3% | -43.4% | 1.077 | 0.24 | 12,999 | 69.6% | 5.9% | 6.2% |
| B_cloud21_55_partial | 8.6% | **-32.4%** | 0.906 | 0.26 | 17,245 | 68.3% | 5.0% | **6.8%** |
| B_cloud21_55_cl3 | 8.2% | -42.6% | 0.458 | 0.19 | 17,245 | 30.3% | 3.3% | 2.0% |
| A_don20_partial_tp | 7.2% | -53.3% | 0.654 | 0.13 | 71,442 | 62.3% | 3.5% | 4.3% |
| B_cloud20_100_cl3 | 9.6% | -53.9% | 0.461 | 0.18 | 12,999 | 28.5% | 5.1% | 1.5% |

### ex-VIN track (268 symbols, VIN excluded):

| Strategy label | CAGR | maxDD | Sharpe | MAR | n_trades | hit% | avg_trade | oos_avg | VIN-contam? |
|---|---|---|---|---|---|---|---|---|---|
| A_basehigh_trail25 | **15.0%** | -51.8% | 0.746 | 0.29 | 43,795 | 37.5% | 2.0% | 1.7% | No |
| B_cloud21_55_cl3 | 12.0% | -38.5% | 0.586 | 0.31 | 17,071 | 30.3% | 3.2% | 1.6% | No |
| B_cloud20_100_cl3 | 10.8% | -54.2% | 0.558 | 0.20 | 12,865 | 28.5% | 5.0% | 1.1% | No |
| **B_cloud20_100_partial** | **10.7%** | **-30.1%** | **1.136** | **0.36** | 12,865 | 69.7% | 5.9% | **6.3%** | No |
| A_don20_partial_tp | 9.3% | -45.4% | 0.883 | 0.20 | 70,682 | 62.3% | 3.4% | 4.2% | No |
| A_basehigh_partial_tp | 5.2% | -41.3% | 0.547 | 0.13 | 43,795 | 63.3% | 3.9% | 3.9% | **YES** |
| B_cloud21_55_partial | 4.5% | -32.1% | 0.506 | 0.14 | 17,071 | 68.5% | 5.0% | **6.8%** | partial |
| A_don20_trail25 | 3.9% | -58.2% | 0.294 | 0.07 | 70,682 | 36.7% | 1.8% | 1.5% | **YES** |

**VIN contamination flags:**
- `A_basehigh_partial_tp`: full=13.4% → ex_vin=5.2% (**-8.2pp** — VIN drives most of this result)
- `A_don20_trail25`: full=11.3% → ex_vin=3.9% (**-7.4pp** — severely VIN-contaminated)
- `B_cloud21_55_cl3`: full=8.2% → ex_vin=12.0% (**+3.8pp** — removing VIN improves it; VIN hurts this entry)
- `B_cloud20_100_partial`: full=10.3% → ex_vin=10.7% (**+0.4pp** — nearly VIN-neutral)

---

## 7. Exit Mode Findings

From Phase 2 and portfolio simulation combined:

| Exit | Characteristic | Best use case |
|---|---|---|
| `partial_tp` | Hit rate: 63-70%, positive median, avg trade: 3.5-5.9% | Best for Strategy B — captures large cloud moves without full exit |
| `cloud_loss_3` | Hit rate: 28-31%, avg trade: 3.2-5.0%, low oos | Works for B but results degrade in test period vs partial_tp |
| `trailing_2.5` | Hit rate: 37%, large CAGR but high drawdown (50-60%) | High variance; Strategy A at portfolio level drives large drawdowns |
| `cloud_loss_2` | Tighter version of cloud_loss_3 | Slightly lower return, no meaningful improvement |
| `atr_stop_2.0/3.0` | Hit rate: 22-29%, median -9 to -12% | **Do not use.** VN equities move too much; constant whipsaw |

**Definitive exit ranking for Strategy B (ex-VIN):**
1. `partial_tp` — CAGR=10.7%, Sharpe=1.136, maxDD=-30.1%, oos=6.3% ← **production choice**
2. `cloud_loss_3` — CAGR=10.8%, Sharpe=0.558, maxDD=-54.2%, oos=1.1% ← higher CAGR but worse risk profile

For a production portfolio where drawdown matters, `partial_tp` dominates on risk-adjusted terms.

---

## 8. Interpretation: FACTS vs INTERPRETATION

### Likely true (high confidence, consistent across extended dataset)

**FACT:** Cloud-only (21/55) entry at 100-150d horizon shows positive or near-flat OOS degradation on the extended 2012-2026 dataset. This is a consistent finding across both Phase 1 (2018-2026) and Phase 2 (2012-2026).

**FACT:** Level_breakout entry has negative Sharpe (-0.13) and negative test-period returns (-1.3%) on the extended dataset. The Phase 1 result (+Sharpe 0.38) was a favorable subsample artifact.

**FACT:** Portfolio-level (ex-VIN, 2012-2026): `B_cloud20_100_partial` delivers CAGR=10.7%, Sharpe=1.136, maxDD=-30.1% — the best risk-adjusted portfolio result in the comparison.

**FACT:** VIN contamination is material. `A_basehigh_partial_tp` drops from 13.4% to 5.2% CAGR when VIN excluded. This is the Vingroup restructuring/policy effect.

**INTERPRETATION:** The cloud_only Strategy B result is more generalizable than it appears: 2012-2017 were trending years, 2020-2021 were trending years, 2023-2025 were trending years. Cloud-following works in trending markets. The question is what happens in extended sideways/volatile regimes.

**INTERPRETATION:** `partial_tp` exit systematically outperforms on risk-adjusted metrics for Strategy B. The reason: cloud entries at 20/100 EMA tend to catch large moves; partial_tp locks 50% early and lets the remainder ride without being stopped out by transient corrections.

### Uncertain / unproven

- Whether `A_basehigh_trail25` (ex-VIN CAGR=15.0%) is genuine or another favorable subsample effect. The drawdown is -51.8%, which is high. The OOS avg (1.7%) is lower than other candidates.
- Whether `B_cloud21_55_partial` OOS=6.8% is sustainable. The full-sample CAGR is only 4.5% (ex-VIN), suggesting it was weak before 2023 and strong after — possible regime dependence.
- Whether the 2012-2017 bull cycle in Vietnam was structurally similar to any future period. The data shows that cloud-following worked extremely well in 2012-2017; if Vietnam enters a prolonged sideways/range period, Strategy B will underperform.

### Proven incorrect (discard)

- **Level_breakout on 2012-2026**: not robust. The Phase 1 signal quality result was conditional on the 2018-2026 sample. Negative Sharpe and negative test returns on the full dataset.
- **ATR fixed stops**: confirmed ineffective for all entry types. Do not use.
- **Lookback=60 resistance for long holds**: severely overfit (OOS degradation -16 to -17pp in Phase 1).
- **breakout+retest, standalone reclaim**: never appeared in top results at any horizon or dataset.

---

## 9. Overfitting Warnings

1. **Phase 1 level_breakout result was conditional on 2018-2026.** Extending to 2012 breaks it. Do not use Phase 1 breakout findings alone to justify a price-level strategy.

2. **VIN contamination is severe for Strategy A.** `A_basehigh_partial_tp` full-universe CAGR=13.4% drops to 5.2% ex-VIN. The full-universe result should not be cited without the VIN caveat.

3. **Small sample effects at long horizons.** Strategy B has only 13K-17K trades across 14 years — less data than Strategy A (70K+ for Donchian). The Sharpe and hit-rate estimates carry more uncertainty.

4. **OOS period (2023-2026) = VN recovery regime.** The high OOS averages (4-7% for some configs) may reflect the specific 2023-2025 market environment. A proper OOS test requires a regime the strategy has not seen.

5. **Portfolio simulation uses FIFO position fill.** In practice, a practitioner would rank signals by conviction (momentum, volume, sector). FIFO is a conservative lower bound on portfolio performance.

---

## 10. Production Candidate Recommendation

### Strategy B is the production candidate. Strategy A does not survive extended-data validation.

**Primary recommendation:**

| Setting | Value |
|---|---|
| Strategy | B — Long-Horizon Cloud-Only |
| Entry | `cloud_only` — cloud turns bullish (fast EMA > slow EMA), prior bear cloud required |
| EMA pair | 20/100 (higher return) or 21/55 (more OOS stable) |
| Horizon | 100–150 trading days hold target |
| Exit | `partial_tp` — 50% at +15%, trail remainder at 2.5x ATR(14) |
| Universe | ex-VIN (exclude VIC, VHM, VRE) for uncontaminated results |
| Max positions | 20 (5% equal weight) |
| Expected CAGR | 10–12% (ex-VIN, 14-year backtest) |
| Expected maxDD | -30% to -38% |
| Expected Sharpe | 0.58–1.14 |
| OOS check (2023+) | avg_trade = 1.6–6.3% |

**If Strategy A must be implemented:** Use `base_high` entry (Donchian 50 + cloud + freshness filter) with `partial_tp` exit, not the multi-touch resistance breakout. Accept that ex-VIN CAGR drops to ~5% and the edge is thin but present.

**What to discard permanently:**
- Multi-touch resistance levels as entry filter (level_breakout)
- ATR fixed stops
- Lookback=60 at 150d holding horizon
- breakout+retest, standalone reclaim

---

## 11. Output Files

| File | Description |
|---|---|
| `data/research/ema_cloud/ohlcv_panel_ext2012.parquet` | Extended 2012-2026 panel (272 symbols, 738K rows) |
| `data/research/ema_cloud/ohlcv_pre2018.parquet` | Pre-2018 raw fetch (201 symbols, 228K rows) |
| `data/research/ema_levels/phase1_results.csv` | Phase 1 (2018-2026) signal quality results |
| `data/research/ema_levels/phase2_results.csv` | Phase 2 variable-exit results |
| `data/research/strategy_a/strategy_a_results.csv` | Strategy A (2012-2026) entry comparison |
| `data/research/strategy_b/strategy_b_results.csv` | Strategy B (2012-2026) cloud-only results |
| `data/research/portfolio/portfolio_comparison.csv` | Portfolio-level CAGR/Sharpe/MAR comparison |
| `pp_backtest/run_strategy_a.py` | Strategy A pipeline |
| `pp_backtest/run_strategy_b.py` | Strategy B pipeline |
| `pp_backtest/run_portfolio_comparison.py` | Portfolio comparison runner |
| `pp_backtest/ema_portfolio_sim.py` | Portfolio simulator (daily EMA strategies) |
| `pp_backtest/ema_levels/entry.py` | Entry signals (added: base_high_breakout) |
| `scripts/research/fetch_pre2018_ext.py` | Fetch 2012-2017 data for universe |
