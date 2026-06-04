# ChatGPT Prompt — Distribution Risk Lens: Work Done + Optimize Correction Prediction

**Paste this entire file into a new ChatGPT chat.**  
Optionally attach: `distribution_risk_daily_scan_chatgpt_YYYYMMDD.zip` or repo files listed below.

---

## Your role

You are a **senior quant researcher + Vietnam markets specialist**. The operator already built **Distribution Risk Lens v1.2** in production (context-only, no OMS). Your job:

1. **Understand what exists** (method, data, outputs, integrations).
2. **Propose concrete upgrades** to **predict market corrections / drawdowns** more usefully for a discretionary Vietnam equity operator.
3. **Do not** recommend changing `final_action`, A3/S3 rules, OMS, or live capital without explicit operator approval.

**Safety invariant (non-negotiable):**

> Distribution Risk Lens is **market context only** and does **not** change `final_action`.

---

## 1. What was built (work done summary)

### Core module: `src/market/distribution_risk_lens/`

| File | Purpose |
|------|---------|
| `definitions.py` | Distribution day flags (down day + volume; variants strict 0.5%, heavy vol, etc.) |
| `features.py` | Rolling dist counts 5/10/20/25/50d, EMA position flags |
| `index_views.py` | Three series: `vnindex_raw`, `ex_vin_proxy`, `vin_group` (VIC,VHM,VRE; VPL if ≥252 bars) |
| `outcomes.py` | Forward returns + **max drawdown** over 5/10/25/75/100d; correction hit flags 3/5/10/15% |
| `buckets.py` | Historical probability tables by bucket (dist_count_10d/25d/50d) |
| `warnings.py` | Deterministic states: NORMAL → CAUTION → CORRECTION_RISK / DISTRIBUTION_CLUSTER / DOWNTREND_WARNING |
| `events.py` | Event-study exports |
| `pipeline.py` | End-to-end run → SSOT artifacts |

**CLI:** `python -m scripts.research.run_distribution_risk_lens`  
**Refresh in reports:** `refresh_distribution_risk_for_reports()` in `src/trading/reports/distribution_risk_card.py`

### SSOT outputs (`data/research/market_risk/`)

| File | Content |
|------|---------|
| `distribution_risk_latest.json` | Snapshot: warning states, dist counts, probabilities, lifts, freshness, VIN comparison |
| `distribution_days_probability_table.csv` | Aggregated bucket stats (median/mean fwd ret, p_ret_neg, p_max_dd at 3/5/10/15%) |
| `distribution_days_forward_returns.csv` | Per-day features + forward outcomes (full history ~2012+) |
| `distribution_days_event_study.csv` | Filtered event rows |
| `distribution_days_warning_backtest.csv` | Warning state history |
| `distribution_days_yearly_validation.csv` | Yearly stability checks |
| `distribution_risk_threshold_explainer.html` | Standalone visual: end-return vs max-DD semantics |

### Integrations (read-only context card)

- **`data/decision/daily_scan.md`** — section after breadth; auto-refresh on write
- **`src/trading/reports/cloud_daily_report.py`** — Section G (MARKET CONTEXT tag + ctx-safety)
- **`src/report/weekly.py`** — optional section when `--render`
- **Tests:** `tests/test_distribution_*.py`, `tests/test_cloud_daily_report_distribution_risk.py`

### Related but separate: RS Correction Lens v1.1

- `src/market/rs_correction_lens/` — relative strength vs VNINDEX from correction anchor (15/5 default)
- **Not** the same as distribution lens; complementary for leader rotation
- Do not merge into distribution methodology without explicit design

### UX / disclosure patches (done)

- ex-VIN labelled **derived proxy**, NOT native index
- Per-view freshness (`is_stale_for_as_of`) → `NEEDS_REVIEW` if stale
- Threshold explainer HTML (0% vs 5% vs max-DD confusion addressed for operators)
- Report UX style guide: `docs/reporting/REPORT_UX_STYLE_GUIDE.md`

---

## 2. Methodology (FACTS)

### Distribution day (default `base`)

- Close down ≥ **0.2%** vs prior close **and** volume > prior day volume
- Variants tested in research: strict 0.5% drop, heavy volume 1.1×, ADV20 volume, close-in-range filter

### Rolling counts → warning state (on `dist_count_25d` + EMA)

| dist_count_25d | Typical state |
|----------------|---------------|
| ≤1 | NORMAL |
| 2–3 | CAUTION |
| ≥4 + below EMA20 or low breadth | CORRECTION_RISK |
| ≥4 | DISTRIBUTION_CLUSTER |
| ≥5 + below EMA50 | DOWNTREND_WARNING |

### Index views

| View | Type | Notes |
|------|------|-------|
| `vnindex_raw` | Native VNINDEX OHLCV | FireAnt / CSV SSOT |
| `ex_vin_proxy` | **Derived** cap-weight decomposition | Primary operator view; NOT exchange index |
| `vin_group` | Equal-weight VIC,VHM,VRE basket | Research; VPL excluded if <252 bars |

**VIN baseline:** `docs/research/VIN_EMA_CLOUD_BASELINE.md` — dual full vs ex-VIN; cap-weight VNINDEX may be VIN-skewed 2025–2026.

### Probability engine

- Historical **event study**: all past days matching current bucket (e.g. `ex_vin_proxy` + `dist_count_25d >= 5`)
- Horizons: **5, 10, 25, 75, 100** trading days
- Metrics published in JSON:
  - `p_ret_neg_{H}d` — P(forward close-to-close return < 0)
  - `p_correction_5pct_25d` — P(**max drawdown** ≤ −5% within 25d), NOT end return
  - `p_correction_10pct_75d` — P(max DD ≤ −10% within 75d)
- Also in CSV: `p_max_dd_le_neg3pct`, `_neg5pct`, `_neg10pct`, `_neg15pct` by horizon
- **Lift vs base_rate** and **confidence** (HIGH/MEDIUM/LOW from sample size)

### Critical semantic distinction (operators often confuse)

| Question | Metric | Example (ex-VIN, dist≥5, 25d, n≈1832) |
|----------|--------|--------------------------------------|
| Đóng cửa sau 25 phiên **âm**? | `p_ret_neg_25d` | **41.6%** |
| **Chạm −5%** trên đường trong 25 phiên? | `p_correction_5pct_25d` / max_dd | **42.1%** |
| Đóng cửa **≤ −5%**? | Not default on card; ~**14.5%** from forward_returns |
| Đóng cửa **≤ −10%**? | ~**4.9%** (25d) | |

**Full threshold ladder (ex-VIN, dist≥5, 25d)** — computed from `distribution_days_forward_returns.csv`:

| Mức | P(đóng cửa ≤) | P(chạm max DD ≤) |
|-----|---------------|------------------|
| 0% | 41.6% | ~100%* |
| 2% | 27.9% | 83.6% |
| 5% | 14.5% | 42.1% |
| 8% | 8.3% | 23.8% |
| 10% | 4.9% | 17.6% |

\*Max DD ≤0% ≈ always true over 25d (any intraperiod dip); use ≥2% for path risk.

---

## 3. Current snapshot (as-of **2026-05-26** — update when refreshing)

**Source:** `data/research/market_risk/distribution_risk_latest.json`  
**Method:** `distribution_risk_lens_v1.2`  
**VNINDEX:** ~1884 (26/5), slight dip from 1886 (25/5)

| View | dist 10/25/50 | Warning |
|------|---------------|---------|
| vnindex_raw | 3 / **5** / 9 | DISTRIBUTION_CLUSTER |
| ex_vin_proxy | 3 / **5** / 8 | DISTRIBUTION_CLUSTER |
| vin_group | 3 / 5 / 7 | DOWNTREND_WARNING |

**Primary (ex-VIN) probabilities (dist≥5 bucket):**

| Metric | P | Base | Lift |
|--------|---|------|------|
| p_ret_neg_25d | 41.6% | 39.0% | +2.6pp |
| p_correction_5pct_25d | 42.1% | 40.5% | +1.6pp |
| p_correction_10pct_75d | 47.7% | 44.3% | +3.4pp |

Raw vs ex-VIN **aligned** on DISTRIBUTION_CLUSTER (no warning disagreement).

---

## 4. Known limitations (honest)

1. **ex-VIN is a proxy** — decomposition methodology, not HOSE index; drawdown probs may use synthetic high/low from close when needed.
2. **Bucket matching is marginal** — lift vs base often only **1–3pp** at dist≥5; signal is weak for precise timing.
3. **Distribution days ≠ O'Neil only** — simplified vol/down rule; not full FTD/DDay institutional definition.
4. **No intraday** in lens — daily close only; session recovery invisible except via future filters in analyst notes.
5. **Vietnam 2025–2026** — Vingroup mega-move can distort cap-weight VNINDEX; prefer ex-VIN + breadth.
6. **Card shows sparse thresholds** — only 5% (25d) and 10% (75d) on operator card; full 0–10% ladder exists in data but not in daily UI.
7. **Stationary bucket** — does not condition on regime (bull/bear), breadth zone, or RS leaders.

---

## 5. What the operator wants you to optimize

**Goal:** Better **prediction / framing of market corrections** for Vietnam (VNINDEX or ex-VIN), usable next to Phase36 `final_action` (defense breadth, manual T1) — **context only**.

### Priority questions for your proposal

1. **Threshold surface:** Should daily card expose full **0–10% ladder** (end return AND max DD) for 25d? Best UX?
2. **Better buckets:** Condition on `dist_count_25d` + **breadth** + **EMA stack** + **prior 20d return**? Hierarchical calibration?
3. **Correction definition:** Optimize for **max DD** vs **end return** vs **both** — which should drive "correction warning"?
4. **VIN handling:** Separate published track for `vin_group` vs forcing ex-VIN primary?
5. **Out-of-sample:** Walk-forward / yearly validation (`distribution_days_yearly_validation.csv`) — where does bucket fail?
6. **Combine lenses:** Distribution cluster + RS correction leaders + distribution risk — joint score without touching `final_action`?
7. **Alternative labels:** Replace or augment DISTRIBUTION_CLUSTER with probability-of-−5% / −10% directly?
8. **FireAnt data:** Any fields missing (breadth, industry rotation) worth adding to features?

### Output format (your reply)

```markdown
## Executive summary (≤10 bullets)

## What to keep from v1.2

## Proposed v1.3 methodology
- Feature changes
- Bucket / calibration changes
- New outputs (JSON schema sketch)
- UI / report changes (daily_scan + cloud Section G)

## Backtest / validation plan
- Metrics (Brier, calibration, hit rate for −5% max DD in 25d)
- OOS protocol

## P0 / P1 / P2 implementation tasks (file-level)

## Risks & what NOT to do

## Open questions for operator
```

---

## 6. Repo paths (for code-aware suggestions)

```
src/market/distribution_risk_lens/
src/trading/reports/distribution_risk_card.py
scripts/research/run_distribution_risk_lens.py
data/research/market_risk/distribution_risk_latest.json
data/research/market_risk/distribution_days_forward_returns.csv
data/research/market_risk/distribution_days_probability_table.csv
data/research/market_risk/distribution_risk_threshold_explainer.html
docs/research/VIN_EMA_CLOUD_BASELINE.md
docs/reporting/REPORT_UX_STYLE_GUIDE.md
tests/test_distribution_risk_lens.py
tests/test_distribution_days.py
```

**Regenerate:**

```powershell
.\.venv\Scripts\python.exe -m scripts.research.run_distribution_risk_lens
.\.venv\Scripts\python.exe scripts\reporting\daily_scan_report.py
.\.venv\Scripts\python.exe -m src.trading.cli cloud-daily-report
.\.venv\Scripts\python.exe -m scripts.reporting.build_distribution_risk_daily_scan_chatgpt_zip
```

---

## 7. Constraints (do not violate)

- FireAnt-first for Vietnam OHLCV; disclose proxies.
- Facts vs interpretation separated in any operator-facing copy.
- Lens **must not** modify `final_action`, position sizing, or OMS.
- No live capital / auto-trade recommendations.
- Preserve SSOT file pattern under `data/research/market_risk/`.
- Prefer extending `distribution_risk_lens` over parallel duplicate modules.

---

## 8. Companion context (optional reads)

- QA review prompt (older snapshot): `docs/trading/CHATGPT_DISTRIBUTION_RISK_DAILY_SCAN_REVIEW_PROMPT.md`
- RS lens (separate): `docs/trading/CHATGPT_RS_CORRECTION_DAILY_SCAN_REVIEW_PROMPT.md`
- Operator explainer visual: open `data/research/market_risk/distribution_risk_threshold_explainer.html` in browser

---

_End of prompt — optimize correction prediction for Vietnam operator stack._
