# ChatGPT Design Prompt — Sector L4 Cloud × Stock Cloud Causality (2012→now)

**Role:** Thinking brain / research architect — **NOT** implementer.  
**Downstream:** Cursor or Claude Code implements from your spec.  
**Repo:** VN Agent System (Vietnam equities, FireAnt-first)

---

Copy everything **below the line** into a **new ChatGPT conversation**. Attach this file plus (if available) the zip from `scripts/reporting/build_sector_rotation_chatgpt_zip.py` or the sector L4 research pack under `data/research/portfolio_optimization/missing_work/`.

---

## Your mission

Design a **rigorous, implementable research program** (tests + outputs + pass/fail gates) to answer:

> **Khi ngành cấp L4 “cloud turn positive”, đó là chỉ báo hữu ích để lọc cổ trong ngành — hay chủ yếu là 1–2 mã lớn/liquidity kéo ngành, rồi các mã còn lại “đi theo”?**

Produce **test specifications** that a coding agent can implement without guessing. Include **alternative theses** you invent beyond the three below.

---

## Core theses to test (minimum — extend with your own)

| ID | Thesis (plain language) | If true, operator would… |
|----|-------------------------|-------------------------|
| **T1 — Sector filter** | L4 cloud turn **leads** many stocks in that L4 within 5–20 sessions; sector breadth rising **adds value** vs stock-only cloud | Use **sector L4 breadth** as a **filter** before picking names in that sector |
| **T2 — Leader drag** | One **leader** (cap/ADV/return) turns cloud first; sector L4 flips **because of** that name; rest of sector is **lagging follow-through** | Weight **leader identity** more than sector flag; sector turn alone is **weak** for laggards |
| **T3 — Coincident breadth** | Sector and stocks turn together; **no lead**; sector signal is **redundant** with median stock cloud | Do **not** add sector layer; stock-level cloud is enough |
| **T4 — False sector** | Sector metric is noisy (mapping errors, mixed L4); **spurious** correlation | Fix mapping / use L3 or cap-bucket instead |
| **T5 — Regime gated** | Sector filter only works when **VNINDEX bull** + **market breadth** defense/normal | Gate sector filter on macro (see market overlays) |

**You must propose at least 2 additional theses (T6, T7, …)** — e.g. foreign-flow days, VIN-policy windows, bank-sector special case, small-cap catch-up within L4, etc.

---

## Definitions (bind to repo — do not redefine casually)

### Sector L4
- **Grain:** `sector_l4` finest label in `sector_l4_map_coverage.csv` (from FireAnt industry map + overrides).
- **Coverage:** ~273 symbols mapped; ~71 `Unknown` — tests must report **coverage sensitivity** (exclude Unknown vs include).

### Cloud (A3 production definition)
- **Stock cloud:** EMA20/100 `cloud_bull` per symbol (see `pp_backtest/ema_levels/indicators.py` → `ema_cloud`).
- **Sector L4 cloud breadth:** For each `(date, sector_l4)`,  
  `l4_breadth = mean(cloud_bull_20_100)` over all mapped symbols in that L4 on that date.  
  (Already computed in `sector_l4_daily_metrics.csv` / `portfolio_optimization_final_steps.py` step sector.)

### Sector L4 “turn positive” (define precisely for tests)
Specify **one primary** definition in your spec, plus **robustness variants**:

| Variant | Suggested rule |
|---------|----------------|
| **Primary** | `l4_breadth` crosses above **40%** from below (hysteresis: back below **35%** to reset) |
| Alt A | L4 **cap-weight** cloud (weight by ADV50) vs **equal-weight** breadth |
| Alt B | L4 **median** stock cloud flip (≥50% of names bull) vs mean breadth |
| Alt C | First day `l4_breadth` ≥ 40% after ≥20 sessions below 30% |

### Stock events (for T1/T2)
- **Stock cloud turn:** same cloud definition, symbol-level.
- **A3 entry signal (optional linkage):** `cloud_only_entry` bar from `pp_backtest/ema_levels/entry.py` — use only if test needs “production-like” entries, not just cloud flips.

---

## Market overlays (required in design)

Run **parallel tracks** — do not only use VNINDEX cap-weight.

| Track | Data | Purpose |
|-------|------|---------|
| **M0 — Market breadth** | `regime_decomposition_breadth.csv` or recompute from panel | Defense/normal context |
| **M1 — VNINDEX full** | `ta_vnindex.parquet`, `VNINDEX.csv` | Regime: EMA20 > EMA100 bull flag |
| **M2 — VNINDEX ex-VIN proxy** | `vnindex_ex_vin_daily_series.csv`, `vnindex_low_dist_ex_vin.py` | Broad market **without Vingroup return distortion** |
| **M3 — VIN group only** | `VIC`, `VHM`, `VRE` (+ `VPL` if ≥252 bars) | Sector moves driven by VIN names |
| **M4 — VIN distortion flag** | Per `docs/research/VIN_EMA_CLOUD_BASELINE.md` | Tag 2025–2026 windows where conclusions may be VIN-skewed |

**Mandatory reporting:** For any headline result, show **full universe vs ex-VIN** where sample size allows (tables: `metric_full`, `metric_ex_vin`, `note_on_distortion`).

---

## Data SSOT (implementer will use)

| Asset | Path |
|-------|------|
| OHLCV panel | `data/research/ema_cloud/ohlcv_panel_ext2012.parquet` |
| Sector map | `data/research/portfolio_optimization/missing_work/sector_l4_map_coverage.csv` |
| L4 daily metrics (if fresh enough) | `data/research/portfolio_optimization/missing_work/sector_l4_daily_metrics.csv` |
| Prior L4 stress tests | `data/research/portfolio_optimization/missing_work/sector_l4_stress_rule_tests.csv` |
| Prior findings | `data/research/portfolio_optimization/missing_work/SECTOR_L4_FINAL_FINDINGS.md` |
| A3 trade ledger (for P&L tests) | `pp_backtest/.../phase25a_dp_trade_ledger.csv` (verify path in repo) |
| VIN baseline | `docs/research/VIN_EMA_CLOUD_BASELINE.md` |

**Source discipline:** FireAnt / repo panel only unless endpoint documented. State **native vs derived** for ex-VIN index.

**Date range:** **2012-01-01 → latest panel date** (report last date in every table).

**Liquidity filter (default):** Align with Phase36 A3 universe rules (ADV50, min bars) — document exclusions (`VPL` <252 bars, etc.).

---

## Statistical / econometric tests to specify (implementer-ready)

For each test, your output must include: **hypothesis**, **inputs**, **procedure**, **outputs (CSV columns)**, **primary metric**, **pass/fail threshold**, **known pitfalls**.

### Block A — Lead/lag & Granger causality
- For each `sector_l4` with ≥N symbols and ≥T years:
  - Does **L4 breadth change** Granger-cause **median stock return** in L4 (h=5,10,20)?
  - Does **leader stock return** Granger-cause **L4 breadth** (T2)?
  - **Cross-section:** On sector-turn days, distribution of **stock cloud turns** in same L4 over next 1–10 sessions (histogram vs random days).

### Block B — Information added (filter value)
- **Baseline:** Stock-level cloud turn → forward return (20/60/120d), hit rate, MAR on A3 ledger subset.
- **Overlay:** Only take stock turns when **L4 breadth ≥ X%** or **L4 just turned positive**.
- Report **delta**: `Δhit_rate`, `Δmean_return`, `ΔMAR`, `ΔmaxDD` vs baseline.
- **Stratify** by M1 bull/bear, M0 defense/normal, M2 ex-VIN regime.

### Block C — Leader vs sector (T2 deep dive)
Per L4, identify **leader** per day or per event:
- Candidate leader rules: top **ADV50**, top **market cap proxy** (if available), top **1d/5d return**, or **first stock to flip cloud** in L4.
- Measure: % of sector turns where **leader flipped ≥k days before** L4 breadth cross vs **same day** vs **after**.
- **Spillover:** After leader turn, do **non-leaders** in L4 outperform **non-L4** controls matched by ADV/beta?

### Block D — Sector concentration & false discovery
- Multiple testing correction across **~40+ L4 sectors**.
- **Placebo:** Randomly shuffle symbols across L4 labels (preserve marginals) — does “sector effect” vanish?
- **Unknown sector bucket:** Show results with/without `sector_l4=Unknown`.

### Block E — Link to production (optional, second phase)
- Replay **sector_l4_stress** style rules on A3 ledger with new gates from Block B winners only.
- Compare to existing `no_entry_if_l4_breadth<40%` (see `sector_l4_stress_rule_tests.csv`).

---

## Required deliverables from you (ChatGPT)

Produce a single markdown doc: **`SECTOR_L4_CLOUD_CAUSALITY_TEST_PLAN.md`** with:

### 1. Executive summary (1 page)
- Which theses are worth implementing first (P0/P1/P2).
- What would **falsify** using sector L4 in production dashboard.

### 2. Test catalog table

| test_id | thesis | priority | inputs | method | outputs | pass criterion | fail action |
|---------|--------|----------|--------|--------|---------|----------------|-------------|

Minimum **15 tests** across Blocks A–E.

### 3. Implementation spec for coding agent
- Suggested module layout: `scripts/research/sector_l4_causality/`  
- CLI entry: `python -m scripts.research.sector_l4_causality.run_all --start 2012-01-01 --end latest`  
- Output dir: `data/research/sector_l4_causality/`  
- Runtime / memory notes (panel 742k rows, 272 symbols).  
- Reuse: `ema_cloud`, `load_panel`, sector map loader from `portfolio_optimization_final_steps.py` — **no duplicate FireAnt client**.

### 4. Output artifacts (filenames fixed)
Examples you must list explicitly:
- `sector_l4_turn_events.csv`
- `sector_stock_lead_lag_summary.csv`
- `granger_sector_to_stock_by_l4.csv`
- `filter_value_ablation.csv` (with/without sector gate)
- `leader_vs_sector_classification.csv`
- `regime_stratified_full_vs_ex_vin.csv`
- `SECTOR_L4_CAUSALITY_FINDINGS.md` (facts only + interpretation separated)

### 5. Visualization spec (optional P1)
- Heatmap: sector × year, % time in L4 bull regime.
- Event study charts: L4 turn t=0, cumulative return leaders vs followers.

### 6. Operator translation (Vietnamese-friendly appendix)
- 5 bullets: “Nếu kết quả X → làm Y trong daily scan / cloud report”.
- Explicitly state: **sector L4 in Phase36 today = dashboard warning only** (`sector_l4_stress_flag`); your plan must say **adopt / shadow / reject** for production.

---

## Constraints (non-negotiable)

1. **Facts vs interpretation** — separate in findings template.  
2. **No hallucinated data** — if field missing, `Unknown` + list file to add.  
3. **VIN:** dual-report **full** and **ex-VIN** on important aggregates; flag VIN distortion 2025–2026.  
4. **Do not** claim sector ETF = native index unless FireAnt native index documented.  
5. Tests must be **computable on laptop** (no HFT, no tick data required for P0).  
6. Prefer **simple, auditable** methods first; fancy ML only in P2 with justification.  
7. Align cloud definitions with **existing A3** (20/100), not a third cloud unless as robustness.

---

## Questions you must answer in your plan

1. **Optimal L4 breadth threshold** for “sector healthy” — 30/40/50%? Hysteresis?  
2. **Equal-weight vs cap-weight** sector breadth — which matches Vietnam rotation reality?  
3. Is **first-stock-to-flip** or **max-ADV leader** better for T2?  
4. Does sector filter add value **after** controlling for **market breadth** and **VNINDEX bull**?  
5. Which L4 sectors are **too small** (n<5) to include?  
6. **2012–2019** vs **2020–2026** stability — structural break tests?  
7. Should **ex-VIN** test use **stock universe ex-VIN** or only **index overlay ex-VIN**?

---

## Anti-patterns (reject these)

- Using **cap-weight VNINDEX** alone as “market health” for 2025–2026 conclusions.  
- Treating **correlation** as **causation** without lead/lag or event study.  
- One **global** regression without sector-level heterogeneity.  
- Ignoring **71 Unknown** sector mappings.  
- Recommending **hard production block** on sector L4 without MAR delta on A3 ledger (prior stress tests barely moved MAR — see `SECTOR_L4_FINAL_FINDINGS.md`).

---

## Reference: what repo already concluded (do not ignore)

From `SECTOR_L4_FINAL_FINDINGS.md` (2026-05-16):
- L4 breadth entry filters at 30/40/50%: **small MAR lift** vs no cap; blocked many trades.  
- **Decision then:** `SHADOW_RISK_CONTROL` — dashboard warning, **not** hard entry block.  
- **max_N_per_l4** concentration rules hurt badly.

Your new plan should say whether **causality evidence** could upgrade this to **filter**, **ranking feature**, or stay **warning only**.

---

## Output format reminder

```markdown
# SECTOR_L4_CLOUD_CAUSALITY_TEST_PLAN
## 1. Executive summary
## 2. Thesis registry (T1…Tn)
## 3. Test catalog (table)
## 4. Implementation spec (modules, CLI, reuse map)
## 5. Output schema (CSV column defs)
## 6. Pass/fail gates for adoption
## 7. FACTS vs INTERPRETATION template for final report
## 8. Appendix: operator Vietnamese summary
```

**Do not write Python code** unless pseudo-code for clarity. The implementer is Cursor/Claude.

---

_End of prompt — attach repo paths or zip when available._
