# ChatGPT Prompt — Institutional Accumulation Operator Report: Full Backtest Design (2012 → Now)

**Paste this entire file into a new ChatGPT chat (Codex / high reasoning).**  
Optionally attach: `institutional_accumulation_scan_chatgpt.zip` from  
`python -m scripts.reporting.build_institutional_accumulation_scan_chatgpt_zip --as-of YYYY-MM-DD`  
and/or `institutional_accumulation_operator_summary_latest.html` + latest scan CSV.

---

## Your role

You are a **senior quant researcher + Vietnam equity markets specialist + research engineer**.

The operator runs **`institutional_accumulation_operator_summary_latest.html`** daily/weekly as a **stock-picking prioritization dashboard**. Today it is **research-only** (no OMS, no `final_action`). The operator wants a **rigorous, implementable backtest plan** to test whether **every metric, flag, list, warning, and tier rule** shown on that HTML **actually improved stock-picking performance** vs sensible baselines, using **Vietnam OHLCV from 2012 through present**, evaluated across **multiple calendar periods and regimes**.

Your deliverable is a **design document + implementation spec** Cursor can build — **not** live trading changes.

---

## Safety invariants (non-negotiable)

1. **Institutional Accumulation does not set `final_action`, OMS, A3/S3, DNSE, or live orders** today. Backtest is **research validation** unless the operator explicitly promotes later.
2. **Do not** recommend merging this scan into production Phase36 without a separate promotion gate.
3. **Real capital: NO-GO** in your plan unless operator adds an explicit future phase.
4. **Separate FACTS vs INTERPRETATION** in your write-up.
5. **VIN baseline:** Any aggregate or index comparison must include **full universe vs ex-VIN (`VIC`, `VHM`, `VRE`)**; exclude **`VPL`** from VIN event studies until ≥252 daily bars. Cap-weight **VNINDEX** may be Vingroup-skewed in 2025–2026 — state caveat; prefer breadth where relevant.
6. **Fund / Smart Money context:** Current production uses **static April 2026 priors** (`apr2026_default_priors.json`) when monthly JSON is absent. Your plan must address **lookahead / staleness** of fund tags (see §7).

---

## 1. Current state (FACTS — do not assume proven edge)

| Claim | Status |
|-------|--------|
| Operator HTML improves returns | **Unknown — not proven in-repo** |
| Scoring weights (18/38/28/−16) | Design v1.1, not OOS-optimized |
| Tier thresholds (72/58/42, percentiles, fragile floors) | Rule-based |
| `distribution_risk_flag` (≥5 dist days / 25d) | O'Neil-style heuristic on stock OHLCV |
| Operator explain text (`primary_driver`, `reject_failure_reason`, …) | **Derived rules** from same fields — test **underlying booleans/thresholds**, not NLP prose |
| Validation today | Leakage checks, units, pytest — **not** return attribution |
| Related but separate | `minervini_backtest/` accumulation scans, `src/market/distribution_risk_lens/` (index event study) |

**Methodology version in code:** `v1.1` (`src/scans/institutional_accumulation/`).

---

## 2. What must be backtested (complete inventory)

Backtest **each hypothesis group** below. For each metric/flag/list, specify: **signal definition at T**, **holding period(s)**, **universe**, **benchmarks**, **OOS protocol**, **pass/fail criteria** for “improved performance.”

### 2A. Operator HTML sections (11 + header)

Map every section in `institutional_accumulation_operator_summary_{date}.html`  
(`operator_summary_html.py` → `OPERATOR_HTML_SECTION_IDS`):

| Section ID | UI content | Backtest unit |
|------------|------------|---------------|
| `header` | Scan date, regime, context source, methodology | Metadata only |
| `snapshot` | KPI grid: tier counts, emerging count, caution-proxy % | Aggregate tier mix stability + forward universe return conditional on mix |
| `changes` | WoW tier changes, score movers vs prior scan | **Event:** tier upgrade/downgrade; forward return after change |
| `fund-backed` | Top fund-tagged Tier 1–3 (`has_fund_disclosure_tag`) | Portfolio: fund-backed top N vs rest of Tier 1–3 |
| `emerging` | `emerging_accumulation_candidate` (MF≥48, risk≤30, no fund tag, Tier 1–3) | Portfolio: emerging list vs outside_fund Tier 1–3 |
| `rejects` | Important rejects (fund names in Reject tier) | **Avoidance:** do rejected names underperform? (short or zero weight) |
| `distortion` | Caution list: `caution_mask` = vin OR dist OR risk≥45 | Portfolio: caution-flagged within Tier 1–3 vs non-caution |
| `warnings` | Workflow warnings (bucket skew, no Tier 1, sector conc, …) | **Meta:** conditional market/sector forward returns when warning fires |
| `signals` | Tier 2 focus + theme bullets | Same as tier/score tests |
| `playbook` | Static research steps | Not backtested (process only) |
| `files` | Paths | N/A |
| `appendix` | Liquid universe Tier 1/2/3 tables | Full tier backtest on liquid subset |

### 2B. Composite score & components (CSV columns)

**Target composite:** `institutional_accumulation_score`  
**Formula (code):**  
`0.18×score_context + 0.38×score_money_flow + 0.28×score_price_structure − 0.16×score_risk_penalty` (clipped 0–100)

| Field | Type | Backtest as |
|-------|------|-------------|
| `institutional_accumulation_score` | Continuous 0–100 | Quintile/decile spread; monotonicity |
| `score_context` | Continuous | Incremental lift controlling for flow+price |
| `score_money_flow` | Continuous | Same |
| `score_mf_cmf` | Sub-group | Ablation: drop CMF group |
| `score_mf_obv_pvt` | Sub-group | Ablation |
| `score_mf_adl` | Sub-group | Ablation |
| `score_mf_participation` | Sub-group | Ablation |
| `score_price_structure` | Continuous | Ablation |
| `score_risk_penalty` | Continuous 0–100 | Higher penalty → worse forward return? |
| `score_percentile` | Cross-sectional pct | Percentile tier overlay vs fixed floors |

### 2C. Tier system & gates

| Rule | Parameters (`config.py`) | Test |
|------|--------------------------|------|
| Tier 1 | score≥72, MF≥55, risk≤35 | Forward return vs Tier 2/3/Reject |
| Tier 2 fixed | score≥58 (52 fragile), MF≥40, risk≤50 | Spread vs Tier 3 |
| Tier 2 percentile | ≥78th pct, score≥46, MF≥45, risk≤45 | Incremental value vs fixed floor only |
| Tier 3 fixed | score≥42 (38 fragile) | Spread vs Reject |
| Tier 3 percentile | ≥62nd pct, score≥40, risk≤50 | Incremental value |
| Tier 3 consensus floor (fragile) | core + score≥40, MF≥42, risk≤48 | Subsample test |
| Liquidity gate | min_history 120d, ADV20≥2B, ADV50≥1.5B VND | Reject vs liquid near-miss |
| ETF exclusion | `E1VFVN30`, sector `Quỹ mở` | Excluded from universe — document |
| Emerging gate | MF≥48, risk≤30, no fund tag | Emerging vs non-emerging Tier 1–3 |

**Regime switch:** `fragile_uptrend_narrow_leadership` lowers Tier 2/3 floors — stratify all tests **by regime label at T** (reconstruct from priors or proxy macro if needed).

### 2D. Raw indicators (inputs to scores)

All computed **≤ scan_date** on daily OHLCV (`indicators.py`). Test **raw feature** predictive power, not only scaled scores.

**Money flow**

| Feature | Definition (summary) |
|---------|---------------------|
| `cmf20_daily`, `cmf20_weekly` | CMF(20) daily; weekly on Friday week-end |
| `cmf_flow_conflict` | Daily vs weekly CMF sign mismatch |
| `obv_slope_20`, `obv_slope_50` | Normalized OBV linear slope |
| `adl_slope_20` | Chaikin A/D slope |
| `adl_price_divergence_bearish` | Bearish ADL vs price |
| `pvt_slope_20` | PVT slope |
| `up_down_volume_ratio_20` | Up-volume / down-volume 20d |
| `hv_up_days_20`, `hv_down_days_20` | High-volume up/down days |
| `turnover_accel_ratio_5d50d` | 5d avg value / 50d avg value − 1 |
| `distribution_weeks_6` | Weekly down close + rising volume, 6w |

**Price structure**

| Feature | Definition |
|---------|------------|
| `rs_vs_vnindex_20`, `rs_vs_vnindex_60` | Relative return vs VNINDEX |
| `rs_line_slope_20` | RS line slope |
| `holds_ma50`, `holds_ma20` | Close above MA |
| `volatility_contraction_flag` | BB width 120d pctile ≤35 + CMF>0 |
| `pullback_quality_flag` | Shallow pullback, down vol < up vol |
| `close_strength_10d` | Close position in range |
| `extension_pct_above_ma20` | Extension for risk penalty |

**Risk / flags**

| Feature | Rule |
|---------|------|
| `distribution_days_25` | Count: close↓ & vol↑ vs prior bar, 25d window |
| `distribution_risk_flag` | `distribution_days_25 >= 5` |
| `vingroup_distortion_flag` | VIN symbol + RS≥8% + extension≥12% + ≥3 diag reasons |
| `vingroup_distortion_diagnosis` | Text — test flag boolean only |
| One-bar spike | RS>12% & CMF daily slope < −0.005 (`detect_one_bar_spike`) |

**Risk penalty buckets (additive caps in `score_risk_penalty`)**

| Trigger | Penalty |
|---------|---------|
| Extension >25% / >15% | +35 / +20 |
| Dist days ≥6 / ≥4 | +30 / +15 |
| Dist weeks ≥4 / ≥3 | +22 / +12 |
| VIN distortion | +22 |
| Illiquid | +40 |
| CMF conflict | +12 |
| ADL bearish div | +15 |
| One-bar spike | +18 |
| `distribution_risk_flag` (if liquid) | +10 |

→ Test **each penalty component** for incremental forward-return discrimination.

### 2E. Smart Money / fund context (Layer A — special handling)

| Field | Source | Backtest challenge |
|-------|--------|-------------------|
| `fund_context_bucket` | consensus_core, second_ring, commentary, selective, outside | **Point-in-time fund lists** required; static `apr2026` priors are **not** historically accurate pre-2026 |
| `has_fund_disclosure_tag` | bucket ≠ outside | Same |
| `in_consensus_core`, `in_commentary_mention`, … | Priors / monthly JSON | Survivorship / publication lag |
| `score_context` | `context_score()` additive tags | Ablation with/without context block |
| `smart_money_tags` | Theme tags (FTSE, infra, policy, …) | Test each tag's forward return lift |
| `regime_label` | e.g. fragile narrow leadership | Stratify; do not leak future regime |

**Required plan element:** Phase 1 = **OHLCV-only metrics** (no fund lookahead). Phase 2 = **monthly fund JSON time series** when available. Phase 3 = sensitivity using frozen priors (document bias).

### 2F. Operator diagnostics & warnings (JSON `bucket_diagnostics`)

| Diagnostic | Definition | Test |
|------------|------------|------|
| `bucket_mix_percentages_top_tier` | fund_backed %, emerging %, vin %, caution_proxy %, outside % | When outside≥70%, does forward Tier 1–3 basket underperform? |
| `caution_proxy` | vin OR dist OR risk≥45 | Already in §2A distortion |
| `warnings.*` | e.g. no_tier1, sector_concentration, too_few_fund_backed | Binary regime indicators → conditional forward index/stock returns |
| `warning_messages` | Text | Map to boolean flags only |

### 2G. Derived explain columns (do not backtest prose)

| Column | Backtest |
|--------|----------|
| `primary_driver`, `secondary_driver`, `main_risk`, `operator_note` | Skip text — test drivers' **source fields** |
| `reject_failure_reason` | Test components: weak MF, CMF phrase, risk≥35, dist flag, VIN flag, liquidity |

### 2H. Diff / changes block

| Field | Test |
|-------|------|
| `new_tier12`, `dropped_tier12` | Event study 5/10/20/60d after entering/leaving Tier 1–2 |
| `tier_changes` | Upgrade vs downgrade |
| `biggest_score_gains/losses` | Δscore vs forward return correlation |

---

## 3. Data specification (2012 → present)

### 3A. Price data

| Item | Spec |
|------|------|
| **Source** | FireAnt-exported OHLCV in `data/stocks/{TICKER}.csv` (primary); benchmark `data/benchmark/VNINDEX.csv` |
| **Range** | **2012-01-01** through latest available bar (target ≥2026) |
| **Fields** | open, high, low, close, volume; dates YYYY-MM-DD |
| **Integrity** | Flag `missing_bars`, `high_zero_volume`; exclude or winsorize per documented rules |
| **Units** | Respect `price_unit_mode`, `value_scale_factor` — same as `filters.liquidity_metrics()` |
| **Survivorship** | Document bias if universe = today's `data/stocks/` file list only |

### 3B. Point-in-time universe

- **Replicate scan universe policy:** all symbols in `data/stocks/` passing liquidity at **each historical rebalance date** (weekly or monthly — justify cadence).
- **Minimum history:** 120 trading days before first score (match `ScanConfig.min_history_days`).
- **Alternative:** frozen liquidity universe as sensitivity.

### 3C. Benchmarks (required)

1. **VNINDEX** buy-and-hold (total return, same periods)
2. **Equal-weight** all liquid scan-universe names (rebalanced with signal)
3. **Random rank** control (same N as Tier 1 portfolio, 1000 draws)
4. **Score-matched** control: same sector cap, similar ADV, different score quintile
5. **ex-VIN** variants of 1–4 where applicable

### 3D. Forward outcomes (per signal date T)

Report **both** end return and path risk:

| Horizon | Metrics |
|---------|---------|
| 5d, 10d, 20d, 60d, 120d | Cumulative return, excess vs VNINDEX |
| 20d, 60d | Max drawdown from T |
| 60d | Hit rate for −5%, −10% drawdown |
| 60d | Information coefficient (rank corr score vs return) |

**Fill assumption:** Signal known at **close T**; enter **open T+1** (align with A3 backtest convention in `docs/trading/CLOUD_SIGNAL_TIMING_AUDIT.md`). Sensitivity: close T.

**Costs:** Vietnam equity frictions —至少 0.15% round-trip + slippage tier by ADV (specify).

---

## 4. Period structure (must test “different periods”)

Split results **every time**; do not report one full-sample Sharpe only.

### 4A. Calendar years

2012, 2013, …, 2025, 2026 YTD — table: metric lift × year.

### 4B. Macro / market regimes (VN)

Suggested buckets (refine with data):

| Regime | Proxy (example) |
|--------|-----------------|
| Bull breadth expansion | VNINDEX above 200DMA & median stock RS>0 |
| Correction / bear | VNINDEX below 200DMA or dist lens CORRECTION_RISK |
| Narrow VIN-led | 2025 H1 VIC mega-move window — **label VIN distortion** |
| COVID shock | 2020 Q1–Q2 |
| Rate / credit stress | Operator-defined SBV episodes if available |

### 4C. Walk-forward / OOS

| Phase | Train | Validate | Test |
|-------|-------|----------|------|
| W1 | 2012–2017 | 2018–2019 | 2020–2022 |
| W2 | 2012–2019 | 2020–2021 | 2022–2024 |
| W3 | 2012–2022 | 2023 | 2024–2026 |

**Forbidden:** Optimizing tier cutoffs on 2012–2026 full sample then reporting same sample.

### 4D. Fragile-regime subsample

When `regime_label` contains `fragile_uptrend_narrow_leadership`, repeat tier spreads vs normal regime.

---

## 5. Portfolio constructions (stock-picking tests)

Define **primary** strategies the operator cares about:

| Strategy ID | Description |
|-------------|-------------|
| **S1 Tier ladder** | Long Tier 1 equal-weight, rebalance weekly; variants Tier 1+2, Tier 1 only top 10 by score |
| **S2 Score quintile** | Q5 vs Q1 among liquid names |
| **S3 Fund-backed overlay** | Tier 1–3 ∩ fund tag vs emerging-only |
| **S4 Risk overlay** | Long high score **excluding** caution_proxy vs including |
| **S5 Reject avoidance** | Universe minus `important_rejects` logic names |
| **S6 Changes momentum** | Buy `new_tier12`, sell `dropped_tier12` at rebalance |
| **S7 Component ablation** | Full score vs zeroing context / risk / each MF group |

**Metrics per strategy:** CAGR, vol, Sharpe, Sortino, max DD, hit rate, avg excess vs VNINDEX, turnover, capacity (ADV participation).

**“Improved performance” pass criteria (propose, operator approves):**

Example (you may tighten):

- OOS test window: Tier 1 excess return > 0 vs EW liquid **and** vs random N, **p < 0.05** bootstrap
- Monotonicity: Q5 > Q3 > Q1 median 20d return in ≥70% of years
- Risk: Tier 1 max DD not worse than EW by >2pp unless return lift >3pp annualized
- **Component:** removing risk penalty **hurts** OOS Sharpe (proves penalty adds value)
- **Failure:** If edge only in 2025 VIN window → flag **VIN distortion**, require ex-VIN pass

---

## 6. Statistical & reporting standards

- **Bootstrap** confidence intervals on spreads (block bootstrap by month).
- **Multiple testing:** Benjamini–Hochberg or holdout for threshold tuning.
- **IC / rank correlation** time series with t-stat.
- **Calibration tables** (like `distribution_days_probability_table.csv`) for: score decile → P(forward ret < 0), P(max DD > 5%).
- **Turnover-adjusted** returns mandatory.
- Publish **`metric_full`, `metric_ex_vin`, `metric_vin_only`** for any aggregate where VIN matters.

Deliverables:

1. `docs/research/institutional_accumulation/BACKTEST_DESIGN_v1.md` (your design)
2. `data/research/institutional_accumulation/backtest_manifest.json` (runs, dates, hashes)
3. CSV/Parquet: `forward_outcomes_panel.parquet`, `tier_strategy_equity_curves.csv`, `component_ablation_oos.csv`, `yearly_validation.csv`
4. HTML summary mirroring operator sections with **PASS/FAIL** badges per metric group
5. **Threshold tuning protocol** — only on train, report test once

---

## 7. Implementation guidance (for Cursor — do not code in ChatGPT unless asked)

**Reuse:**

| Module | Use |
|--------|-----|
| `src/scans/institutional_accumulation/indicators.py` | Feature parity with production |
| `src/scans/institutional_accumulation/scoring.py` | Same formulas |
| `src/scans/institutional_accumulation/pipeline.py` | Reference only — batch historical needs loop per date |
| `src/market/distribution_risk_lens/outcomes.py` | Pattern for forward returns + max DD |
| `pp_backtest/` | Fill timing conventions |

**New (suggested):**

```
scripts/research/institutional_accumulation_backtest/
  run_panel.py          # historical daily/weekly scores 2012+
  run_portfolios.py     # S1–S7 equity curves
  run_ablation.py       # component tests
  run_yearly_report.py  # tables for ChatGPT review
```

**Performance:** Vietnam ~1.5k tickers × ~3.5k days — vectorize; consider parquet panel cache `data/research/institutional_accumulation/panel_scores.parquet`.

**Tests:** `tests/test_institutional_accumulation_backtest_no_lookahead.py` — assert no bar after `scan_date` in features.

---

## 8. Known limitations (must address in plan)

1. **Fund priors lookahead** if using 2026 lists on 2012 symbols — Phase 1 OHLCV-only mandatory.
2. **Survivorship** in `data/stocks/` directory.
3. **VNINDEX cap-weight** vs stock-level RS — disclosure in conclusions.
4. **Static regime_label** from priors — may not vary historically; propose VNINDEX-based regime reconstruction.
5. **Operator explain text** — not independently validated; underlying rules only.
6. **Distribution Risk Lens** (market) is separate — cite only as cross-check, not duplicate work.
7. **April 2026 priors** — any test using them on history is **labeled synthetic context**, not empirical fund disclosure.

---

## 9. What NOT to do

- Do not claim “proven” without OOS pass criteria met.
- Do not optimize weights on full sample without walk-forward.
- Do not conflate index distribution lens with stock `distribution_risk_flag`.
- Do not change A3/S3/OMS/`final_action` in this project phase.
- Do not use LLM-generated labels as features.
- Do not ignore ex-VIN when 2025–2026 results drive conclusions.

---

## 10. Reference files (repo paths)

```
src/scans/institutional_accumulation/
  config.py scoring.py indicators.py pipeline.py context.py
  operator_summary.py operator_summary_html.py
  operator_lists.py operator_diagnostics.py operator_explain.py operator_changes.py
docs/trading/INSTITUTIONAL_ACCUMULATION_SCAN.md
docs/trading/INSTITUTIONAL_ACCUMULATION_OPERATOR_OUTPUTS.md
docs/research/VIN_EMA_CLOUD_BASELINE.md
data/smart_money/priors/apr2026_default_priors.json
outputs/scans/institutional_accumulation_{date}.csv
outputs/scans/institutional_accumulation_operator_summary_{date}.json
outputs/scans/institutional_accumulation_operator_summary_latest.html
scripts/reporting/build_institutional_accumulation_scan_chatgpt_zip.py
src/market/distribution_risk_lens/   # template for outcomes/buckets only
```

---

## 11. Your reply format (required)

```markdown
## Executive summary (≤12 bullets)

## Scope confirmation
- IN / OUT of backtest
- Primary operator question answered

## Hypothesis map
(Table: metric/section → test type → pass criteria)

## Data & universe plan
(2012+, PIT rules, survivorship, FireAnt SSOT)

## Methodology
- Signal timing (T close → T+1 open)
- Horizons & outcomes
- Benchmarks
- Costs

## Period / OOS design
(Years, regimes, walk-forward table)

## Portfolio strategies S1–S7
(Definitions + expected diagnostics)

## Component & ablation plan
(Weights, tiers, flags, penalties)

## Smart Money / fund context phases
(Phase 1 OHLCV-only vs monthly PIT)

## Output artifacts & schema
(file paths, columns)

## Pass/fail gates for "improved stock picking"
(numeric thresholds — propose defaults)

## Implementation backlog for Cursor
(P0/P1/P2, file-level, est. runtime)

## Risks & failure modes
(VIN, survivorship, lookahead, thin years)

## Open questions for operator
(max 8)
```

---

## 12. Operator context (why this matters)

The operator uses the HTML to **prioritize research** on fund-backed names, emerging flow, and to **avoid** distribution/VIN traps (e.g. POW-style rejects). They need evidence that:

- **Tier 1** names outperform **Reject** on a risk-adjusted basis OOS,
- **Risk penalty** and **distribution_risk_flag** identify future laggards,
- **Emerging** list adds value beyond fund tags,
- **Warnings** (no Tier 1, outside_fund skew) carry information,
- Results hold **outside** 2025 Vingroup narrative windows.

If the backtest **fails**, your plan must specify **what to downgrade** (display-only vs remove penalty) — still without touching production trading until promotion.

---

*End of prompt — version 2026-05-27*
