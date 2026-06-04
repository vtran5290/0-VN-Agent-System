# SECTOR_L4_CLOUD_CAUSALITY_TEST_PLAN

**Saved:** 2026-05-25
**Status:** PATCHED — approved for P0 implementation
**Source:** SECTOR_L4_CLOUD_CAUSALITY_TEST_PLAN (user-provided 2026-05-25) + audit patches from `2026-05-25_ReviewPack_SectorL4CausalityPlanAudit.md`
**Production status:** Sector L4 = DASHBOARD_WARNING_ONLY. No OMS/A3/S3 changes.

---

## PATCHES APPLIED (2026-05-25)

The following decisions were finalized after the repo audit and supersede any conflicting wording in the original plan body:

### P1 — E01 Baseline
- Force-rerun `E01_existing_stress_rule_reconciliation` from scratch on:
  `data/research/portfolio_optimization/phase25/phase25a_dp_trade_ledger.csv`
- Prior MAR numbers (no_cap = 0.416, breadth-gate = 0.434) are historical diagnostics only — they came from different run configurations and must not be compared as the same baseline.
- All new gate tests must run against a single consistent ledger.

### P2 — M0 Breadth Definition
- `M0_primary = M0_primary_ex_vin_market_cloud_breadth` = fraction of ex-VIN eligible universe with EMA20/100 cloud_bull = True per date.
- Also compute and report `M0_full_market_cloud_breadth` as sensitivity check.
- Do NOT use `regime_decomposition_breadth.csv` as M0 — that file tracks A3/S3 strategy breadth, not general market cloud breadth.
- `regime_decomposition_breadth.csv` may be included only as a diagnostic reference.

### P3 — A3/S3 Ledger Scope
- P0 adoption gates use A3 ledger only: `data/research/portfolio_optimization/phase25/phase25a_dp_trade_ledger.csv`
- S3 ledger (`s3_best_dp_trade_ledger.csv`) is optional P2 appendix only.
- S3 results must not affect adoption verdict or production wording.

### P4 — ADV / Liquidity Weighting
- Compute `adv20 = rolling_mean(value, 20)` and `adv50 = rolling_mean(value, 50)` from the OHLCV panel `value` column (turnover in VND).
- Label ADV-weighted sector breadth as `l4_breadth_liquidity_weighted`, not "cap-weighted breadth" — native market cap is not available.
- Add "native market cap" to `missing_fields_to_add.md`.

---

## 1. Executive Summary

### Objective

Design a rigorous, laptop-computable research program to answer one decision question:

> When an L4 sector cloud "turns positive", is it a useful stock-selection filter, or is it mainly caused by one or two large/liquid leaders pulling the sector metric while the rest of the sector follows weakly or not at all?

This plan is for **Stage 0 / manual decision-support only**. It must not change Phase36 production logic, OMS routing, `final_action`, or A3 entry/exit contracts. Current Phase36 use of Sector L4 remains **dashboard warning only** via `sector_l4_stress_flag` until the adoption gates in this plan are passed.

### Starting point from prior repo work

Prior L4 stress testing already found only small improvement from simple L4 breadth entry gates and significant harm from max-name-per-L4 concentration caps. Therefore this plan should not try to "prove" the sector layer by rerunning the same stress rules. It must test **causality, lead/lag, leader concentration, regime dependence, and production P&L value**.

Baseline stance before new tests:
- **Production hard block:** reject for now.
- **Dashboard warning:** keep.
- **Ranking / review-priority feature:** possible only if lead/lag and information-value evidence is robust.
- **Shadow filter:** possible only if A3 ledger replay shows material incremental MAR / drawdown improvement.
- **Hard filter:** only possible after strict pass gates; default expectation is that hard filter will be difficult to justify.

### P0 / P1 / P2 priority

| Priority | Implement first | Why |
|---|---|---|
| **P0** | Event dataset, L4 turn definitions, stock cloud turn windows, threshold sweep, leader classification, filter-value ablation, regime stratification, full vs ex-VIN reporting, coverage audit | These answer the core operator question with simple auditable evidence. |
| **P1** | Granger tests, matched-control spillover, false-discovery control, placebo shuffles, structural-break tests, visualizations | These protect against false causality and sector-mapping artifacts. |
| **P2** | Factor models, ML ranking, macro/foreign-flow interaction models, sector-specific thresholds | Only after P0/P1 show real signal. Fancy models should not rescue a weak base signal. |

### What would falsify using Sector L4 beyond dashboard warning

Do **not** upgrade Sector L4 if any of the following are true:

1. L4 turn days do not produce higher next 5/10/20-session stock cloud-turn counts than matched random days.
2. Stock-level cloud turn + L4 gate does not improve 20/60/120d forward returns after controlling for market breadth and VNINDEX / ex-VIN regime.
3. A3 ledger replay does not improve **MAR by at least +0.05** without materially worsening max drawdown or blocking too many winners.
4. Cap-weight / ADV-weight sector cloud works but equal-weight breadth does not; this points to **leader drag**, not broad sector health.
5. Non-leaders do not outperform matched controls after leader turns.
6. Results vanish in ex-VIN universe or during VIN-distortion windows.
7. Placebo shuffled L4 labels perform similarly to real L4 labels.
8. Positive results are concentrated in very small sectors, `Unknown`, or one unstable subperiod.

### Recommended adoption path

1. **Reject as filter** if P0/P1 results are weak or leader-driven.
2. **Keep dashboard warning only** if evidence is mixed, unstable, or regime-dependent but still useful for concentration awareness.
3. **Adopt as review-priority / ranking feature** if L4 lead/lag is real but A3 ledger MAR uplift is below the hard-filter gate.
4. **Shadow as sector gate** if A3 ledger uplift is material but not yet stable across ex-VIN and subperiod splits.
5. **Adopt as hard production filter** only if it passes all adoption gates in Section 6.

---

## 2. Thesis Registry (T1…T10)

| ID | Thesis | If true, operator would… | Primary evidence required |
|---|---|---|---|
| **T1 — Sector filter** | L4 cloud turn leads many stocks in the L4 within 5–20 sessions; breadth adds value vs stock-only cloud. | Use L4 breadth as a sector health filter or ranking booster. | Event windows, filter ablation, A3 ledger replay. |
| **T2 — Leader drag** | One leader by ADV/cap/return flips first and mechanically pulls the sector; laggards have weaker follow-through. | Track leader identity; sector turn alone is weak for non-leaders. | Leader-before-sector classification, non-leader spillover test. |
| **T3 — Coincident breadth** | Sector and component stocks flip together; no independent lead. | Do not add sector layer; stock cloud is enough. | Zero lead/lag advantage after controls. |
| **T4 — False sector** | L4 mapping is noisy; result is spurious or driven by `Unknown` / tiny sectors. | Fix mapping, use L3, or use theme buckets instead. | Coverage sensitivity, placebo, small-sector diagnostics. |
| **T5 — Regime gated** | L4 filter works only when VNINDEX bull + market breadth normal/defensive, not in broad bear regimes. | Use L4 only under market-regime gate. | M0/M1/M2 stratified results and interactions. |
| **T6 — Small-cap catch-up** | L4 turns first through liquid leaders, then smaller non-leaders catch up after 10–30 sessions. | Use sector turn as watchlist seed, not immediate buy filter. | Follower event study by ADV bucket, lagged follow-through. |
| **T7 — Foreign-flow / liquidity impulse** | Sector turn only matters on high-liquidity or foreign-flow impulse days. | Treat L4 as stronger when liquidity confirmation is present. | Interaction with volume/turnover/foreign-flow if available; otherwise liquidity proxy. |
| **T8 — VIN distortion thesis** | 2025–2026 sector/index conclusions are distorted by VIN group returns and must be ex-VIN checked. | Do not trust full-index conclusions without ex-VIN confirmation. | Full vs ex-VIN divergence and VIN distortion flags. |
| **T9 — Bank-sector special case** | Banks behave differently because they are large, numerous, liquid, and policy/rate sensitive. | Use bank-specific thresholds and concentration warnings. | Sector-specific diagnostics; bank vs non-bank interaction. |
| **T10 — Policy/theme bucket beats formal L4** | Vietnam rotations sometimes follow policy/theme buckets more than formal L4 labels. | Add theme tags for review, but keep formal L4 as audit baseline. | L4 vs theme-bucket comparison; placebo-adjusted effect. |

---

## 3. Test Catalog

| test_id | thesis | priority | hypothesis | inputs | method | outputs | primary metric | pass criterion | fail action |
|---|---|---|---|---|---|---|---|---|---|
| **A01_l4_turn_event_build** | T1/T4/T8 | P0 | L4 turn events can be defined consistently. | sector_l4_daily_panel, sector map, OHLCV. | Build primary turn event: l4_breadth_equal_weight crosses above 40% from below; reset after below 35%. Add variants. | sector_l4_turn_events.csv | Event count by L4 and definition. | ≥10 eligible L4 sectors with enough events. | Stop and fix event generation. |
| **A02_stock_turn_window_distribution** | T1/T3 | P0 | After an L4 turn, more stocks in that L4 flip cloud within 1–10 sessions than random days. | OHLCV, cloud, sector map, L4 events. | Count stock cloud turns in event sector at t+1…t+10 vs matched random dates. | sector_stock_lead_lag_summary.csv | Excess stock-turn count vs matched baseline. | Median excess ≥ +1 stock or ≥ +15% relative lift; bootstrap CI excludes 0. | Keep dashboard only. |
| **B01_stock_cloud_baseline_forward_return** | T1/T3 | P0 | Stock cloud turns alone have measurable forward return profile. | OHLCV, stock cloud turns, liquidity filters. | Compute forward returns after stock cloud turns for 20/60/120d; full/ex-VIN; by regime. | stock_cloud_baseline_forward_returns.csv | Mean/median return, hit rate. | Establish baseline. | If baseline weak, do not optimize sector gate. |
| **B02_l4_gate_filter_ablation** | T1/T5 | P0 | L4 breadth gate improves stock cloud turn outcomes vs baseline. | B01 baseline, L4 breadth, M0/M1/M2. | Overlay rules: breadth ≥30/40/50, just-turned positive, variants. | filter_value_ablation.csv | Δhit rate, Δmean return, Δmedian return. | Δhit_rate ≥ +3pp and Δmean_return ≥ +1% at 60d; retention ≥85%; ex-VIN same sign. | No adoption. |
| **B03_regime_stratified_filter_value** | T5/T8 | P0 | L4 gate adds value after controlling for market breadth and regime. | Filter ablation, M0/M1/M2/M4. | Stratify by regime. | regime_stratified_full_vs_ex_vin.csv | Incremental return/hit-rate in each regime. | Positive in VNINDEX bull + M0 normal/defense; not negative ex-VIN. | Dashboard/ranking under valid regimes. |
| **B04_threshold_sweep** | T1/T5 | P0 | Optimal threshold can be selected without overfitting. | L4 breadth, stock turns, forward returns. | Sweep 30/25, 35/30, 40/35, 45/40, 50/45; train 2012–2019, test 2020+. | threshold_sweep_summary.csv | OOS ΔMAR / Δreturn / Δhit. | Choose simplest threshold with stable OOS benefit. 40/35 primary. | Keep 40/35 for reporting. |
| **B05_a3_ledger_filter_value_probe** | T1/E | P0 | Sector filter improves A3 production-like ledger. | A3 ledger (phase25a_dp_trade_ledger.csv), L4 metrics, stock map. | Replay A3 trades with sector conditions as entry annotations/gates. | a3_ledger_sector_gate_replay.csv | ΔMAR, ΔmaxDD, CAGR, blocked winners/losers. | ΔMAR ≥ +0.05; maxDD not worse by >1pp; blocked losers > blocked winners by ≥1.2x. | Do not upgrade. |
| **C01_leader_identity_panel** | T2/T6 | P0 | Each L4 event can be classified by leader source. | L4 events, adv50, returns. | Identify leaders: max_adv50, first_cloud_flip, top_5d_return. | leader_vs_sector_classification.csv | % events with leader preceding sector by ≥5 sessions. | If >50% of turns are leader-before-sector, T2 likely. | Leader as review context. |
| **D01_coverage_sensitivity_unknown** | T4 | P0 | Unknown mappings do not drive results. | Sector map, L4 events, all prior outputs. | Run headline tables excluding Unknown, including Unknown. | unknown_coverage_sensitivity.csv | Delta in headline metrics. | Conclusion unchanged when Unknown excluded. | Fix map before adoption. |
| **D02_small_sector_diagnostics** | T4 | P0 | Tiny L4 sectors create false precision. | Sector map, event counts. | Bucket by symbol count: n<3, n=3–4, n≥5, n≥10. | small_sector_diagnostics.csv | Result contribution by sector-size bucket. | Headline result driven by n≥5 sectors. | Exclude n<5 from causality tests. |
| **D03_placebo_shuffle_l4_labels** | T4 | P0 | Real L4 grouping has more signal than random grouping. | Sector map, stock panel. | Shuffle symbols across L4 labels preserving sector size; 200 iterations (P0); 500 (P1). | placebo_sector_shuffle_summary.csv | Real metric percentile vs placebo. | Real result >95th percentile. | Reject sector layer. |
| **E01_existing_stress_rule_reconciliation** | E/T1 | P0 | New findings reconcile with prior stress tests. | phase25a_dp_trade_ledger.csv (rerun from scratch), prior CSV as reference. | Rerun old 30/40/50 rules on same ledger baseline; compare new gate variants. | stress_rule_reconciliation.csv | ΔMAR vs prior. | New rule beats old best by ≥+0.03 MAR before further work. | Do not proceed to hard filter. |

---

## 4. Implementation Spec

### Directory

```
scripts/research/sector_l4_causality/
  __init__.py
  config.py          # all path constants + run parameters
  io.py              # panel loader, ADV computation, enriched panel cacher
  cloud.py           # wraps ema_cloud(close, 20, 100) from indicators.py
  coverage.py        # sector map audit → sector_l4_coverage_audit.csv
  regimes.py         # M0/M1/M2/M3/M4 overlays (computed from stock panel, NOT regime_decomposition_breadth.csv)
  l4_events.py       # sector daily panel + L4 turn events
  stock_events.py    # stock cloud turn events + forward returns
  lead_lag.py        # A02 lead/lag summary
  leader.py          # C01 leader classification
  filter_value.py    # B01–B05 filter value and ledger replay
  placebo.py         # D03 placebo shuffles
  adoption_gates.py  # pass/fail gate evaluation + adoption_gate_summary.csv
  report.py          # SECTOR_L4_CAUSALITY_FINDINGS.md generator
  run_all.py         # CLI orchestrator
```

### CLI

```
python -m scripts.research.sector_l4_causality.run_all --start 2012-01-01 --end latest
```

Flags:
- `--output-dir data/research/sector_l4_causality/`
- `--include-unknown false`
- `--min-l4-symbols 5`
- `--min-history-years 3`
- `--run-placebo true`
- `--placebo-iters 200`
- `--full-and-ex-vin true`
- `--write-report true`

### Reuse Map (PATCHED)

| Need | Source | Rule |
|---|---|---|
| OHLCV panel | `data/research/ema_cloud/ohlcv_panel_ext2012.parquet` | Read-only. Cols: symbol,date,open,high,low,close,volume,value |
| adv20 / adv50 | Compute from `value` in io.py | `adv20 = value.rolling(20).mean()` per symbol |
| EMA cloud | `pp_backtest/ema_levels/indicators.py → ema_cloud(close, 20, 100)` | Reuse exactly. Returns `cloud_bull` bool series. |
| A3 entry signal | `pp_backtest/ema_levels/entry.py → cloud_only_entry` | Optional only; do not redefine. |
| Sector map | `data/research/portfolio_optimization/missing_work/sector_l4_map_coverage.csv` | Audit coverage first. |
| L4 daily panel | Always rebuild in l4_events.py | stale `sector_l4_daily_metrics.csv` is reference only. |
| M0 market breadth | Compute in regimes.py from stock panel | Do NOT use `regime_decomposition_breadth.csv` as M0. |
| VNINDEX full | `data/fireant_ssot/ta_vnindex.parquet` | EMA20/100 bull flag. |
| VNINDEX ex-VIN | `data/research/vnindex_ex_vin_daily_series.csv` | Derived proxy; label accordingly. |
| VIN distortion | `docs/research/VIN_EMA_CLOUD_BASELINE.md` | Tag 2025–2026 windows. |
| A3 ledger | `data/research/portfolio_optimization/phase25/phase25a_dp_trade_ledger.csv` | P0 adoption gates use A3 only. |
| S3 ledger | `data/research/portfolio_optimization/missing_work/s3_best_dp_trade_ledger.csv` | P2 appendix only; do not affect verdict. |
| Liquidity-weighted breadth | Derived from adv50 | Label as `l4_breadth_liquidity_weighted`, NOT "cap-weighted". |

---

## 5. Output Schema (key tables)

See plan body for full column definitions. All outputs go to `data/research/sector_l4_causality/`.

Required artifacts:
- `run_config.json`
- `sector_l4_coverage_audit.csv`
- `stock_daily_cloud_panel.parquet`
- `sector_l4_daily_panel.parquet`
- `stock_cloud_turn_events.csv`
- `sector_l4_turn_events.csv`
- `sector_stock_lead_lag_summary.csv`
- `filter_value_ablation.csv`
- `regime_stratified_full_vs_ex_vin.csv`
- `threshold_sweep_summary.csv`
- `leader_vs_sector_classification.csv`
- `placebo_sector_shuffle_summary.csv`
- `adoption_gate_summary.csv`
- `a3_ledger_sector_gate_replay.csv`
- `stress_rule_reconciliation.csv`
- `missing_fields_to_add.md`
- `SECTOR_L4_CAUSALITY_FINDINGS.md`

---

## 6. Pass/Fail Gates for Adoption

### Hard-filter candidate (all must be true)

1. L4 turns produce ≥15% excess same-L4 stock cloud turns vs matched random days within 10 sessions.
2. Rule improves 60d forward hit rate by ≥3pp and mean return by ≥1% vs stock-cloud baseline.
3. A3 ledger ΔMAR ≥ +0.05; maxDD not worse by >1pp; blocked losers / winners ≥1.2x.
4. Rule retains ≥85% of baseline A3 trades unless ΔMAR ≥ +0.10.
5. Benefit remains positive after M0 (ex-VIN primary) and M1/M2 bull/bear controls.
6. Headline result does not disappear in ex-VIN universe and not concentrated in VIN-distortion windows.
7. Real L4 result above 95th percentile of placebo shuffled-sector results.
8. Conclusion unchanged excluding Unknown; headline result driven by n≥5 sectors.
9. Same direction in 2012–2019 and 2020–latest; no subperiod contributes >70% of effect.
10. Rule is simple enough to explain in one sentence and audit daily.

### Ranking-feature only (if hard-filter gates not met but)
- Lead/lag event evidence is positive, or follower CAR vs controls is positive.
- A3 ledger ΔMAR is positive but < +0.05.
- Full and ex-VIN signs agree.
- Does not alter `final_action`, sizing, OMS, or A3 contracts.

### Default verdict
`DASHBOARD_WARNING_ONLY` — unless hard-filter or ranking-feature gates are explicitly passed.

---

## 7. Non-Negotiables

- Do not change A3 production logic.
- Do not change OMS.
- Do not change `final_action` in daily scan.
- Do not promote S3.
- Do not use stale `sector_l4_daily_metrics.csv` as source.
- Do not use `regime_decomposition_breadth.csv` as M0.
- Do not call liquidity-weighted breadth "cap-weighted" unless true market cap exists.
- Facts and interpretations must be separated in `SECTOR_L4_CAUSALITY_FINDINGS.md`.
- All outputs to `data/research/sector_l4_causality/` only.
