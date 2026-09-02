# Pre-Registration: S14 — Minervini MA Stack (Trend Template) Filter
# Belief ID: S14
# Status: SOURCED → Lane A pre-registration
# Date: 2026-07-05
# Prepared by: Claude CLI
# Source: Minervini, Trade Like a Stock Market Wizard (2013), Ch.5 ("Trading with the Trend")
#   8 Trend Template criteria — criteria #1-6 are the new elements vs S1 (which covers #7/#8)
#   MA stack: price > 50d SMA > 150d SMA > 200d SMA, 200d SMA trending up ≥1 month
#   Plus: current price ≥30% above 52-week low
#
# VN pre-check result (2026-07-05): EXPRESSIBLE. 0.9% pass all 8 criteria → 67 OOS signals.
# Pre-check file: data/research/cortex_book6/s14_trend_template_precheck.md
#
# THIS IS A PRE-REGISTRATION DOCUMENT.
# Gates must be locked BEFORE Cursor writes or runs the harness.
# No gate changes after data is seen.

---

## Belief statement (LOCKED)

"Requiring a full Minervini MA stack confirmation (price > 50d SMA > 150d SMA > 200d SMA,
200d SMA trending up ≥1 month, price ≥30% above 52-week low) as an additional pre-filter on
A3_RS+S1 candidates selects confirmed Stage 2 stocks and produces higher forward OOS MAR than
the S1+A3_RS baseline without the MA stack requirement."

VN operationalization:
- Universe: all A3_RS+S1 OOS signal days (N ≈ 1732 baseline)
- For each (ticker, signal_date): apply all 8 Trend Template criteria (definitions below)
- Keep only signals where ALL 8 criteria are satisfied
- Forward returns: same as S1 baseline (next N-day MAR per A3_RS definition)

### Trend Template criteria (all 8 must be satisfied, LOCKED)
1. Current price > 150d SMA AND > 200d SMA
2. 150d SMA > 200d SMA
3. 200d SMA trending up ≥1 month (200d SMA[today] > 200d SMA[21 trading days ago])
4. 50d SMA > 150d SMA AND > 200d SMA
5. Current price > 50d SMA
6. Current price ≥ 30% above 52-week low
7. Current price within 25% of 52-week high (S1 overlap — already in pool by S1 definition)
8. RS Rating ≥ 70 (A3_RS screen — already satisfied by A3_RS selection)

Note: criteria 7 and 8 are satisfied by the A3_RS+S1 pre-filter. Criteria 1-6 are the new constraints.
The 0.9% pass rate reflects the additional filtering from criteria 1-6 on the S1 pool.

---

## Gate parameters (LOCKED before harness runs)

| Gate | Threshold | Rationale |
|------|-----------|-----------|
| G1a (primary) | OOS MAR ≥ 1.850 | 3.7% improvement over S1 baseline (1.7844); strict gate appropriate for a highly concentrated filter |
| G1b (floor) | OOS MAR ≥ 0.516 | Absolute floor (G1B_FLOOR constant in common.py) |
| G2 (mechanism) | MA_stack_MAR > non_stack_MAR | Stage 2 pool (MA pass) outperforms excluded pool (MA fail); G2 checks selection quality |
| G3 (N floor) | N_OOS ≥ 30 | Minimum OOS trade count; N=67 from pre-check — above floor but thin |
| N_OOS actual | 67 (from pre-check) | THIN — note in results; borderline-pass rule applies if G1a pass margin < 0.020 |

**Thin-N warning:** N=67 is above the G3 floor but is thin for statistical confidence. If G1a passes
by a narrow margin (< 0.020 above threshold), require a separate pre-registered confirmation test
before promoting to CALIBRATED. This is not automatic — present to user.

**Negative-OOS cap:** if both candidate and baseline OOS MAR are negative, maximum status is
CONDITIONAL-ADVANCE — never full ADVANCE.

---

## Sub-window validation (required)

Report OOS MAR separately for:
- Sub-A: 2020–2022 (IS-adjacent, trending regime)
- Sub-B: 2023–2026 (OOS-far, choppy regime)

CAUTION: with N=67 total, sub-window N will be approximately 30-40 (sub-A) and 20-30 (sub-B).
Sub-B may fall below MIN_N_OOS=30. If sub-B N < 30: flag [SUB-B-THIN] and report without
treating as a gate pass/fail condition.

---

## Harness design notes

1. **MA history requirement:** 200d SMA requires ≥200 trading days of OHLCV. Exclude stocks with
   < 200 days of history from signal consideration. This may reduce N_OOS below 67.

2. **200d SMA trend check:** compute SMA200[today] vs SMA200[21 trading days ago]. If SMA200 data
   is unavailable 21 days prior (new listing), exclude from criterion 3.

3. **G2 control group:** compute MAR for signals that pass A3_RS+S1 but FAIL at least one MA stack
   criterion. This is the "removed" pool. Report both pools.

4. **Script name (new):** `pp_backtest/cortex_book6_s14_ma_stack_harness.py`

---

## Output files

| File | Description |
|------|-------------|
| `knowledge/backtests/s14_harness_results.md` | Gate verdicts, IS/OOS split, sub-window, G2 mechanism check |
| `data/research/cortex_book6/s14_ma_stack_harness_meta.json` | Machine-readable results |
| `knowledge/backtests/2026-07-05_schwager_s14_ma_stack_gates_addendum.md` | IS thresholds locked before OOS eval |

---

## Expansion gate context

S14 ADVANCE would also provide the 3rd CALIBRATED belief (same as S15 — whichever runs first
and ADVANCES unlocks the Mechanism Gate). See S15 pre-reg for expansion gate detail.
If S15 runs first and ADVANCES: S14 harness is still worth running but Mechanism Gate unlock
should be attributed to S15.
