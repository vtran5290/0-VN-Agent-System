# SECTOR_L4_CAUSALITY_FINDINGS

## 1. Run Metadata

- **Run date:** 2026-05-25
- **Panel path:** D:\V\0. VN Agent System\data\research\ema_cloud\ohlcv_panel_ext2012.parquet
- **Panel latest date:** 2026-05-25
- **Start / end date:** 2012-01-01 → 2026-05-25
- **Universe modes:** full, ex-VIN
- **Unknown sectors included:** False
- **Placebo iterations:** 200
- **Repo commit:** f9c7482

---

## 2. FACTS — Data Coverage

- Total symbols in sector map: **273**
- Symbols with valid OHLCV: **272**
- Unknown L4 count: **69**
- Duplicate mapping count: **0**
- Eligible headline symbols (n_bars ≥ min, n≥5 per L4, non-Unknown): **46**
- See: `sector_l4_coverage_audit.csv`, `small_sector_diagnostics.csv`

---

## 3. FACTS — L4 Event Results

- L4 turn events (primary 40/35 definition): **84**
- L4 turn definitions run: **6**
- Top sectors by event count: {'Private Bank': 30, 'Small Broker': 28, 'Small Developer': 26}
- See: `sector_l4_turn_events.csv`

---

## 4. FACTS — Lead/Lag Evidence

- Median excess same-L4 stock turns (t+1 to t+10) vs matched random days: **0.79**
- Median relative lift: **1.167 (116.7%)**
- Sectors classified as "sector_leads": **2** / 3
- See: `sector_stock_lead_lag_summary.csv`

---

## 5. FACTS — Filter Value Evidence

### Stock-cloud baseline
- See: `stock_cloud_baseline_forward_returns.csv`

### L4 gate ≥40% overlay at 60d horizon
- Full universe: Δmean_ret = **0.0076** | Δhit_rate = **0.0163**
- ex-VIN universe: Δmean_ret = **0.0078** | Δhit_rate = **0.0167**
- See: `filter_value_ablation_full.csv`, `filter_value_ablation_ex_vin.csv`

### A3 ledger replay
- ΔMAR (gate vs no-gate, same baseline): **Unknown**
- Ledger verdict: **Unknown**
- See: `a3_ledger_sector_gate_replay.csv`

### Threshold sweep
- See: `threshold_sweep_summary.csv` (train 2012–2019 vs test 2020+)

### Regime stratification
- See: `regime_stratified_full_vs_ex_vin.csv`

---

## 6. FACTS — Leader vs Sector

- % events where leader flipped ≥5 sessions before sector turn: **54.8%**
- See: `leader_vs_sector_classification.csv`

---

## 7. FACTS — False Discovery and Robustness

- Placebo percentile (real vs shuffled-label distribution): **99.5th percentile**
- Passes 95th-percentile placebo gate: **YES**
- See: `placebo_sector_shuffle_summary.csv`, `unknown_coverage_sensitivity.csv`

---

## 8. INTERPRETATION

> **Label:** INTERPRETATION — not fact. Operator must verify.

- If lead/lag excess is ≥15% and placebo passes: partial support for T1 (sector filter adds breadth signal).
- If leader-before-sector >50%: T2 (leader drag) likely; sector breadth is mechanically pulled by one name.
- If placebo ≈ real result: T4 (false sector / noisy mapping) not ruled out.
- If ex-VIN results weaken significantly: T8 (VIN distortion) likely driving full-universe numbers.
- Current prior stance (from prior stress tests): DASHBOARD_WARNING_ONLY — small MAR improvement (+0.022 best prior case).

**Most supported thesis based on this run:** [Operator must fill in after reviewing outputs above]

**What would confirm:** Placebo percentile ≥95; excess turn count ≥15%; ΔMAR ≥ +0.05 on A3 ledger; ex-VIN sign agrees.

**What would deny:** Placebo ≈ real; excess ≈ 0; A3 ΔMAR < 0; results disappear ex-VIN.

---

## 9. DECISION

**Final verdict: RANKING_FEATURE_ONLY**
- Gates passed: 5 / 10
- See: `adoption_gate_summary.csv`, `adoption_gate_detail.csv`

**Explicit statement:** No change to `final_action`, OMS, A3 contract, or S3 promotion based on this run.
Upgrade requires a separate production-change memo approved by the operator.

---

## 10. Operator Notes

- **To watch in daily scan:** Sector L4 turns in non-VIN, non-bank sectors with ≥5 members — use as review-priority signal only, not automatic entry.
- **Do not overinterpret:** A single sector breadth reading is not a trade signal. Breadth ≥40% with leader confirmation is more meaningful.
- **Next tests (P1):** Granger causality, FDR-adjusted multi-sector claims, matched-control non-leader spillover, structural break 2012–2019 vs 2020+.

### If X → do Y

| If X | Do Y |
|---|---|
| ΔMAR ≥ +0.05 on A3 replay AND ex-VIN confirms | Write shadow-rule memo; paper observe for 3 months before hard filter |
| Leader-before-sector >50% in most eligible L4s | Tag as LEADER_DRIVEN; use leader identity as review signal, not sector breadth |
| Placebo ≥95th percentile | Elevate to ranking-feature; re-run P1 Granger tests |
| Placebo ≈ real (fails 95th) | Keep DASHBOARD_WARNING_ONLY; fix sector map before next iteration |
| ex-VIN results significantly weaker than full | Tag M4_vin_distortion_flag; do not cite full-universe numbers for 2025–2026 |



---

## 11. P0.1 ChatGPT Review Adjustments

**Date:** 2026-05-25
**Verdict update:** RANKING_FEATURE_ONLY -> **LOCAL_RANKING_FEATURE_ONLY**

### 11.1 FACTS — A3 Ledger Sector Gate Replay (Enriched Ledger)

> Using research-enriched ledger (sector_l4 joined via symbol, NOT original ledger).
> Original ledger: UNCHANGED.
> Metric: trade-level MAR = mean_trade_return / abs(worst_single_trade). Portfolio NAV not computable
> from this ledger (multiple simultaneous trades; no daily NAV series available).

- L4 ew>=40%: d_tmar=0.0033, retention=0.932, blocked_winners=387, blocked_losers=226, bl_ratio=0.58, gate=FAIL
- **Critical [FACT]:** All sector gate rules block MORE WINNERS than losers (bl_ratio < 1.0).
  The gate filters high-quality momentum entries disproportionately — it would harm A3 performance.
- G3 (A3 MAR gate): FAIL for all rules. bl_ratio threshold is 1.2; best observed is 0.70 (l4_ew_ge_30).
- Full multi-rule table: `a3_ledger_sector_gate_replay_enriched.csv`

### 11.2 FACTS — Filter Value by Sector-Size Bucket

- All sectors (n=any): Δhit_rate_60d = **0.0163** [FACT: dominated by n=1 sectors]
- n>=5 sectors only: Δhit_rate_60d = **0.0445**, Δmean = **0.0295**, n_gate_signals = **496**

- Full breakdown: `filter_value_ablation_by_sector_size.csv`

> **Key finding [FACT]:** The headline +1.63pp Δhit_rate in P0 was dominated by n=1 sectors.
> For n>=5 sectors (the only statistically meaningful group), the figure is:
> Δhit_rate_60d = 0.0445.

### 11.3 FACTS — L3 / Theme-Bucket Feasibility

P1-eligible groupings (n>=5 symbols, >=5 turn events at primary 40/35 threshold):
  - [L3_n_ge_5] Developer: n=26, turns=24
  - [L3_n_ge_5] Commercial Bank: n=24, turns=31
  - [L3_n_ge_5] Brokerage: n=21, turns=21
  - [L3_n_ge_5] General Contractor: n=6, turns=25
  - [L3_n_ge_5] Industrial Park: n=6, turns=41
  - [L4_strict_n_ge_5] Private Bank: n=21, turns=30
  - [L4_strict_n_ge_5] Small Developer: n=14, turns=26
  - [L4_strict_n_ge_5] Small Broker: n=13, turns=28
  - [flag_bucket] high_beta: n=49, turns=26
  - [flag_bucket] real_estate: n=39, turns=25

- Full audit: `sector_grouping_feasibility_audit.csv`

### 11.4 INTERPRETATION

> Label: INTERPRETATION — not fact. Operator must verify.

- If n>=5 sectors show Δhit_rate_60d ≥ 3pp: elevate to RANKING_FEATURE_ONLY globally, not LOCAL.
- If only 2–3 eligible L4 sectors drive result: result is LOCAL (Vietnam market structure constraint).
- L3 groupings with n>=5 and >=5 turns are P1 candidates for Granger causality.
- Flag-based buckets (bank, broker, real_estate) may offer broader coverage at cost of precision.

### 11.5 Narrowed Verdict

**LOCAL_RANKING_FEATURE_ONLY** — applicable only to eligible L4 sectors (Small Broker, Small Developer, Private Bank).
Not a broad Vietnam-market signal.

**Allowed use:** Operator review priority / watchlist booster for specific eligible L4 sectors.
**Not allowed:** OMS hard filter, A3 contract change, S3 promotion, automatic entry signal.

See `adoption_gate_detail.csv` and `adoption_gate_summary.csv` for gate-level detail.
