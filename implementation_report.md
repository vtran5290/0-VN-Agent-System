# IA Operator HTML — Full-History Evidence Update

## Status

Completed. Operator dashboard upgraded from P3.2 evidence strings to **full-history v0.2** SSOT (`ia_dashboard_evidence_config.json`). Regenerated `institutional_accumulation_operator_summary_latest.html` from scan `2026-05-29`. Pytest `-k institutional_accumulation`: **124 passed**.

**RESEARCH_ONLY_NOT_PRODUCTION** — no scoring, tiers, `final_action`, OMS, DNSE, sizing, A3/S3, or Phase36 changes.

## What changed

| Area | Detail |
|------|--------|
| SSOT | `data/research/institutional_accumulation_full_history/ia_dashboard_evidence_config.json` — 0 `PORTFOLIO_PROMISING`, NO-GO promotion |
| Labels | `INCONCLUSIVE_NOT_BUY_SIGNAL`, `HEAT_RISK_MANUAL_REVIEW`, `RISK_CONTROL_SUPPORTED`, `RISK_CLEAN_RESEARCH_ONLY`, `AVOID_OR_MANUAL_REVIEW`, `DISPLAY_ONLY` |
| HTML | 19 sections (+ `how-to-read`); full-history banner, queues, not-promote list, validation report link |
| Code | `operator_explain.py`, `operator_diagnostics.py`, `operator_summary.py`, `operator_summary_html.py` |
| Tests | `tests/test_institutional_accumulation_operator_evidence.py` (16 tests) + fixture config |
| Pack | `scripts/research/institutional_accumulation_backtest/build_operator_html_evidence_review_pack.py` |

## Safety line (exact)

> This dashboard does not set final_action, OMS orders, DNSE routing, sizing, or live execution.

## Primary artifact

`outputs/scans/institutional_accumulation_operator_summary_latest.html`

## Commands run

```powershell
.\.venv\Scripts\python.exe -m pytest tests -k "institutional_accumulation" -q
# Regenerate operator outputs from existing scan CSV (no rescoring):
.\.venv\Scripts\python.exe -c "… write_all_operator_outputs …"
.\.venv\Scripts\python.exe -m scripts.research.institutional_accumulation_backtest.build_operator_html_evidence_review_pack --pack-date 20260529
```

## Review pack

`outputs/review_packages/institutional_accumulation_operator_html_evidence_update_20260529.zip`

---

# P3 Portfolio Simulation Implementation Report

## Status

Completed. P3 research-only non-overlapping weekly portfolio simulation implemented, regenerated on full outcomes panel (`215,638` rows, `1,562` tickers, `467` rebalance weeks), tests passed (`48`), HTML and review pack built.

**RESEARCH_ONLY_NOT_PRODUCTION** — no production trading logic changed.

## What was built

- `p2_variants.py` — `P3_VARIANT_MAP`, `get_p3_variant_mask()` (reuses P2 masks + liquid-universe baseline).
- `p3_portfolio.py` — weekly holding-period returns (T+1 entry → next scan close), equity curves, costs/turnover, benchmarks, splits, acceptance labels.
- `p3_reporting.py` — HTML report with safety banners.
- CLI: `run_p3_portfolio.py`, `run_p3_html_report.py`, `build_p3_review_pack.py` (contamination guards).
- `tests/test_institutional_accumulation_p3_portfolio.py` — non-overlap, no 60d compounding, mask alignment, pack guards.

## Data source

| Field | Value |
|-------|-------|
| Source | `forward_outcomes_panel.parquet` |
| Rows | `215,638` |
| Tickers | `1,562` |
| Scan weeks | `467` (median gap ~7 days) |
| Price data | `data/fireant_ssot/ta_ohlcv_panel.parquet` (primary), CSV fallback |
| Benchmark | VNINDEX OHLCV via `data_loader` |
| Method | REST/SSOT OHLCV — **not** overlapping `ret_20d`/`ret_60d` for equity compounding |

## Commands run

```powershell
.\.venv\Scripts\python.exe -m scripts.research.institutional_accumulation_backtest.run_p3_portfolio
.\.venv\Scripts\python.exe -m scripts.research.institutional_accumulation_backtest.run_p3_html_report
.\.venv\Scripts\python.exe -m pytest tests -k "institutional_accumulation_backtest or institutional_accumulation_p1 or institutional_accumulation_p2 or institutional_accumulation_p3" -q
.\.venv\Scripts\python.exe -m scripts.research.institutional_accumulation_backtest.build_p3_review_pack --pack-date 20260528
```

## P2 → P3 pass/fail (honest)

P2 labeled **PROMISING_RESEARCH_VARIANT** for `V6_CONTROLLED_ACCUMULATION`, `V4_NO_DISTRIBUTION_RISK`, `V9_V6_REGIME_GATED` on overlapping forward-return diagnostics.

**P3 portfolio simulation does not confirm investability.** All five P3 portfolios received **`BLOCKED_BY_DATA`** at default config (`full_sample`, `top_n=20`, `score_desc`, base cost) because **average weekly holdings &lt; 10** (sparse valid price paths / thin variant universes per week). No variant earned **`PORTFOLIO_PROMISING`**.

### Headline metrics (`full_sample`, `top_n=20`, `score_desc`, base cost)

| portfolio_id | label | CAGR | max_dd | excess_vs_vnindex | excess_vs_ew_universe | avg_holdings | avg_turnover |
|--------------|-------|------|--------|-------------------|-------------------------|--------------|--------------|
| P3_V0_LIQUID_UNIVERSE_BASELINE | BLOCKED_BY_DATA | -6.0% | -50.9% | -117.8% | -11.5% | 4.9 | 0.15 |
| P3_V4_NO_DISTRIBUTION_RISK | BLOCKED_BY_DATA | -3.6% | -42.9% | -103.0% | +3.2% | 4.6 | 0.17 |
| P3_V6_CONTROLLED_ACCUMULATION | BLOCKED_BY_DATA | -1.0% | -30.9% | -84.1% | +22.2% | 3.2 | 0.21 |
| P3_V9_V6_REGIME_GATED | BLOCKED_BY_DATA | -2.1% | -35.2% | -92.9% | +13.4% | 3.0 | 0.20 |
| P3_V4B_DECILE_6_8_NO_DISTRIBUTION_RISK | BLOCKED_BY_DATA | -3.6% | -42.0% | -103.1% | +3.1% | 3.1 | 0.21 |

**Interpretation (FACTS):** V6 shows **better drawdown** than V0 liquid baseline (-31% vs -51%) and **positive excess vs equal-weight liquid universe** (+22%), but **large negative excess vs VNINDEX** (benchmark cumulative +75% over sample vs negative portfolio cumulative). Sparse holdings block formal promotion labels.

## Best / rejected (P3 labels)

- **Best risk profile (not promoted):** `P3_V6_CONTROLLED_ACCUMULATION` — shallowest max drawdown among variants; still fails holdings gate and VNINDEX excess test.
- **Rejected for portfolio use:** all variants for production/OMS — none `PORTFOLIO_PROMISING`; all `BLOCKED_BY_DATA` at default evaluation.

## Turnover and capacity

- Weekly turnover generally **0.13–0.34** (below 0.80 threshold when portfolios fill).
- Capacity flags mostly **OK** on median ADV; binding constraint is **fill rate** (names with valid entry/exit prices), not ADV alone.

## Outputs

| File | Path |
|------|------|
| Equity curves | `data/research/institutional_accumulation/p3_portfolio_equity_curves.csv` |
| Metrics | `data/research/institutional_accumulation/p3_portfolio_metrics.csv` |
| Turnover/capacity | `data/research/institutional_accumulation/p3_turnover_capacity.csv` |
| Yearly | `data/research/institutional_accumulation/p3_yearly_returns.csv` |
| Regime | `data/research/institutional_accumulation/p3_regime_returns.csv` |
| Diagnostic summary | `data/research/institutional_accumulation/p3_diagnostic_summary.csv` |
| HTML | `reports/research/institutional_accumulation/p3_portfolio_simulation.html` |

## Review pack

`outputs/review_packages/institutional_accumulation_p3_portfolio_review_pack_20260528.zip`

## Tests

`48 passed` — see `test_log.txt`.

## Limitations

- Weekly rebalance; equal-weight; no sizing, OMS, DNSE, or `final_action`.
- Entry `entry_price_open_t1` from panel; exit = close on next scan date (documented).
- VNINDEX cap-weight benchmark may be Vingroup-skewed 2025–2026.
- P2 overlapping-return edge **does not** survive as investable weekly portfolio alpha vs VNINDEX.

## Confirmation

No changes to A3/S3/OMS/production scan/DNSE/live paths. Research-only.
