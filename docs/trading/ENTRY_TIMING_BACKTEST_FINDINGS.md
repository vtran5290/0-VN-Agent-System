# Entry Timing Backtest Findings

**As-of:** 2026-05-19  
**Status:** B0 baseline documented; B3 NOT_TESTABLE_WITH_CURRENT_DATA

---

## Variants Defined

### B0 — Baseline: Signal at close T, fill at open T+1

- **Status:** PRODUCTION BASELINE — unchanged.
- Signal: `cloud_only_entry(close[T], EMA20[T], EMA100[T], cloud_was_bear)` = True at bar T.
- Fill: `open[T+1]`.
- This is what `entry.py:5` documents and what the backtest has always measured.

Entry gap cost (signal close → next open):
- Mean ~+0.X% (positive = morning gap-up after signal, makes fill slightly worse than signal close)
- See `data/research/cloud_timing/entry_gap_analysis.csv` for actual values after running `scripts/research/a3_signal_timing_audit.py`

### B1 — Close/ATC fill: Signal at close T, fill at close T

- **Status:** RESEARCH ONLY — NOT production.
- Label: `close_confirmed_atc_fill`
- Warning: **Optimistic.** Signal requires the final close price, which is only known after ATC matching (15:00 HCM). An ATC order submitted based on pre-ATC data would not know the final close with certainty.
- To run: compare B0 returns to returns using `close[T]` as fill instead of `open[T+1]`.
- Expected finding: B1 will appear better than B0 because it avoids the positive morning gap cost.
- This is an upper-bound estimate, not a realizable strategy without ATC infrastructure.

### B2 — Next-day close proxy

- **Status:** RESEARCH — testable with current EOD data.
- Label: `next_close_proxy`
- Compares fill at `close[T+1]` vs `open[T+1]`.
- Useful if operator consistently can't fill at open (circuit breaks, illiquidity at open).
- Expected: slightly worse than B0 for trending markets (missed early move), slightly better for mean-reverting opens.

### B3 — Intraday provisional signal, pre-lunch fill

- **Status:** NOT_TESTABLE_WITH_CURRENT_DATA
- Required data: pre-ATC / pre-lunch intraday snapshots by symbol and date.
- Current data: EOD OHLCV only; no historical intraday partial-close snapshots.
- If such data were available: simulate provisional close at 11:30 HCM (pre-lunch), re-run cloud engine, identify which symbols would have signaled, compare fill at 11:30 vs EOD open[T+1].
- This test cannot be run without the historical intraday data.

### B4 — ATC trigger threshold diagnostic

- **Status:** IMPLEMENTED as helper.
- Label: `atc_trigger_diagnostic`
- See `scripts/research/a3_pre_atc_trigger.py` and `data/research/cloud_timing/a3_pre_atc_trigger_levels.csv`.
- For each symbol: computes minimum close price that would trigger A3 signal given prior EMA values.
- Not a true entry variant — it's a price-monitoring tool for the pre-ATC session.
- Operator uses this to watch "is symbol X close to trigger?" before 14:45 HCM.

---

## Entry Gap Analysis

Run `python scripts/research/a3_signal_timing_audit.py` to generate `data/research/cloud_timing/entry_gap_analysis.csv`.

Fields:
- `symbol`, `date`: signal bar
- `close`: signal-bar close (what B1 would fill at)
- `next_open`: next-bar open (what B0 fills at)
- `next_open_gap_pct`: `(next_open / close - 1) * 100` — positive means gap up (B0 fills worse)

---

## Metrics to Compare (Run from backtest outputs)

| Metric | B0 | B1 | B2 | B3 | B4 |
|---|---|---|---|---|---|
| CAGR | — | — | — | N/A | N/A |
| MaxDD | — | — | — | N/A | N/A |
| MAR | — | — | — | N/A | N/A |
| Hit rate | — | — | — | N/A | N/A |
| Mean trade return | — | — | — | N/A | N/A |
| Mean entry gap cost | see CSV | 0 by def | see CSV | N/A | N/A |

*Populate from backtest runner after data collection.*

---

## Bad / Bull Year Decomposition

Key years to report:
- 2018: bear market test
- 2022: bear market test
- 2020–2021: COVID bull run
- 2025: recent bull run

VN market data quality:
- Pre-2018: thin liquidity, use with caution
- 2018–current: reliable OHLCV for major symbols

---

## Conclusion

B0 remains the production baseline. B1 is an optimistic upper bound. B2 is a conservative proxy. B3 requires historical intraday data not currently in the system. B4 is a pre-ATC monitoring diagnostic, not a tradeable variant.

**No strategy change recommended based on these findings.** The primary fix was the scan-layer bug (latest-bar signal missed), not the entry timing rule.
