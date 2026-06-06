# Stock DNA Research Module — Implementation Report
Date: 2026-06-06
STOCK_DNA_RESEARCH_ONLY — NOT FOR PRODUCTION USE

---

## Executive Summary

| Item | Value |
|------|-------|
| Symbols analyzed | 412 |
| Touch events detected | see stock_dna_line_scores.csv |
| MEDIUM+ confidence profiles | 241 |
| Shuffled-null benchmark passed | True |
| V1 proxy lift (A3-like T2, NOT proven A3 improvement) | 2.7% |
| Best variant | V1 A3-like T2 proxy (NOT proven A3 improvement — a3_true_ledger_used=False) |
| **Recommended production status** | **RESEARCH_ANNOTATION_ONLY** |

---

## Council Decision

**APPROVE_WITH_MODIFICATIONS** (2026-06-04)
V1 scope: 4 lines (EMA20, EMA50, SMA100, SMA150), walk-forward, shuffled-null, regime-split.
Variants implemented: V1 (T2 annotation), V4 (danger line annotation).
Variants deferred: V2 (pullback depth), V3 (extension warning), V5 (ranking).

---

## Files Changed

### New module
- `src/trading/research/stock_dna/__init__.py`
- `src/trading/research/stock_dna/schema.py`
- `src/trading/research/stock_dna/features.py`
- `src/trading/research/stock_dna/events.py`
- `src/trading/research/stock_dna/scoring.py`
- `src/trading/research/stock_dna/profiles.py`
- `src/trading/research/stock_dna/overlay.py`
- `src/trading/research/stock_dna/reporting.py`

### New scripts
- `scripts/research/run_stock_dna_discovery.py`
- `scripts/research/run_stock_dna_a3_overlay_backtest.py`
- `scripts/reporting/build_stock_dna_report.py`
- `scripts/research/package_stock_dna_review.py`

### New tests
- `tests/research/test_stock_dna_no_lookahead.py`
- `tests/research/test_stock_dna_events.py`
- `tests/research/test_stock_dna_profiles.py`
- `tests/research/test_stock_dna_safety.py`
- `tests/research/test_stock_dna_output.py`

### No production files modified
- `src/trading/oms/` — NOT MODIFIED
- `data/decision/` — NOT WRITTEN
- `data/scan/` — NOT WRITTEN
- A3 final_action logic — NOT MODIFIED

---

## Output Files
- data\research\stock_dna\stock_dna_a3_overlay_by_year.csv
- data\research\stock_dna\stock_dna_a3_overlay_metrics.csv
- data\research\stock_dna\stock_dna_annotation_ledger_sample.csv
- data\research\stock_dna\stock_dna_implementation_report.md
- data\research\stock_dna\stock_dna_line_scores.csv
- data\research\stock_dna\stock_dna_null_benchmark.json
- data\research\stock_dna\stock_dna_oos_lift.json
- data\research\stock_dna\stock_dna_open_questions.md
- data\research\stock_dna\stock_dna_research_report.html
- data\research\stock_dna\stock_dna_superperformer_screen.csv
- data\research\stock_dna\stock_dna_superperformer_screen.md
- data\research\stock_dna\stock_dna_symbol_profiles.csv
- data\research\stock_dna\stock_dna_symbol_profiles.json
- data\research\stock_dna\stock_dna_trade_level_overlay.csv
- data\research\stock_dna\stock_dna_trade_level_overlay_full.csv
- data\research\stock_dna\stock_dna_trade_level_overlay_sample.csv

---

## Assumptions
- FACT: ta_ohlcv_panel.parquet is the SSOT for OHLCV data.
- ASSUMPTION: Close prices are corporate-action adjusted (if not, SMA100/SMA150 comparisons across events may be biased).
- ASSUMPTION: 5bn VND ADV20 liquidity floor is appropriate for the analysis period.
- ASSUMPTION: 3-year minimum history before walk-forward OOS year is sufficient for SMA150 warmup.

---

## Risks / Open Issues
- VIN return distortion: all VIN scores should be treated as INTERPRETATION not FACT.
- Walk-forward OOS years with few liquid symbols (pre-2018) may produce noisy results.
- Shuffled-null benchmark: if z_score < 2 for most lines, DNA is noise for those lines.
- See stock_dna_open_questions.md for full list.

---

## Errors During Run
_None reported._

---

## Next Action for ChatGPT
Review stock_dna_symbol_profiles.csv for face validity.
Verify shuffled-null result in stock_dna_null_benchmark.json.
Approve or redirect RESEARCH_ANNOTATION_ONLY status before any operator-facing integration.
