# Pre-Registration: S15 — FIP Quality Momentum Filter
# Belief ID: S15
# Status: SOURCED → Lane A pre-registration
# Date: 2026-07-05
# Prepared by: Claude CLI
# Source: Gray & Vogel, Quantitative Momentum (2016), Ch.6 ("The Path Matters")
#   Academic basis: Da, Gurun & Warachka (2014) "Frog-in-Pan" — 1927-2014 US data
#   FIP = sign(past_return) × (%-negative_days − %-positive_days)
#   Top 10% momentum → rank by FIP → top half (lower FIP = smoother path) CAGR 17.14% vs bottom half 13.02%
#
# VN pre-check result (2026-07-05): EXPRESSIBLE. std(FIP) = 0.064 on A3_RS+S1 OOS pool.
# Pre-check file: data/research/cortex_book7/s15_fip_precheck.md
#
# THIS IS A PRE-REGISTRATION DOCUMENT.
# Gates must be locked BEFORE Cursor writes or runs the harness.
# No gate changes after data is seen.

---

## Belief statement (LOCKED)

"Among S1+A3_RS momentum candidates, those with smoother continuous price formation paths
(lower FIP score = fewer sign changes in daily returns over the 252-day lookback) produce
higher forward OOS MAR than those with spike-driven or erratic paths (higher FIP = lottery
momentum). Ranking by FIP and selecting the top half (lower FIP) improves the S1 baseline."

VN operationalization:
- Universe: all A3_RS+S1 OOS signal days (N ≈ 1732 baseline)
- For each (ticker, signal_date): compute FIP over the prior LOOKBACK=252 trading days
  FIP = sign(ret_252d) × (pct_negative_days − pct_positive_days)
  Note: since A3_RS+S1 candidates have positive momentum (positive ret_252d), sign=+1 always,
  so FIP = pct_negative_days − pct_positive_days  (more negative = smoother = better)
- Rank: sort by FIP ascending (most negative = smoothest path = top quality)
- Filter: keep bottom P50 of FIP (top half by quality = smoothest paths)
- Forward returns: same as S1 baseline (next N-day MAR per A3_RS definition)

---

## Gate parameters (LOCKED before harness runs)

| Gate | Threshold | Rationale |
|------|-----------|-----------|
| G1a (primary) | OOS MAR ≥ 1.844 | 3.3% improvement over S1 baseline (1.7844); consistent with S18 level |
| G1b (floor) | OOS MAR ≥ 0.516 | Absolute floor (G1B_FLOOR constant in common.py) |
| G2 (mechanism) | FIP_top_MAR > FIP_bottom_MAR | Quality (smooth) half outperforms lottery (jumpy) half; primary mechanism check |
| G3 (N floor) | N_OOS ≥ 30 | Minimum OOS trade count for statistical reliability |
| N_OOS estimate | ~866 (half of 1732 baseline) | Top-half split; verify actual count in harness output |

**Negative-OOS cap (standing guardrail):** if both candidate and baseline OOS MAR are negative,
maximum status is CONDITIONAL-ADVANCE — never full ADVANCE regardless of relative improvement.

**Borderline-pass rule:** if G1a pass margin < 0.020 (hairline), treat as CONDITIONAL-ADVANCE
pending a separate pre-registered confirmation test before any operational promotion.

---

## Sub-window validation (required)

Report OOS MAR separately for:
- Sub-A: 2020–2022 (IS-adjacent, trending/COVID-rally regime)
- Sub-B: 2023–2026 (OOS-far, choppy/post-COVID regime)

If sub-B MAR < sub-A MAR by factor >2×: flag REGIME-SPLIT. Not a gate failure but a required
observation for operational context. Prior sub-B collapse signals (S17, S18): same pattern
observed — note whether S15 follows or diverges.

---

## Harness design notes

1. **FIP computation window:** 252 prior trading days from signal_date. Exclude stocks with
   < 252 days of OHLCV data from FIP computation that day.

2. **Split method:** on each signal_date independently rank all A3_RS+S1 candidates by FIP
   ascending; keep bottom 50% (smooth path). Do NOT use a pre-computed universal percentile —
   rank within the day's candidate pool.

3. **Interaction check (post-hoc, for notes only):** if G1a PASS, also report: FIP_top MAR
   for S1-filtered-only subset (to check whether S15 adds value beyond S1 alone or just
   re-selects the S1 pool).

4. **Expected N_OOS:** since the FIP filter keeps half the S1 pool, N_OOS ≈ 866. If actual
   N_OOS < 200 after data availability filter, flag [THIN-N] but do not abort.

5. **Script name (new):** `pp_backtest/cortex_book7_s15_fip_harness.py`

---

## Output files

| File | Description |
|------|-------------|
| `knowledge/backtests/s15_harness_results.md` | Gate verdicts, IS/OOS split, sub-window, G2 mechanism check |
| `data/research/cortex_book7/s15_fip_harness_meta.json` | Machine-readable results |
| `knowledge/backtests/2026-07-05_schwager_s15_fip_gates_addendum.md` | IS thresholds locked before OOS eval |

---

## Expansion gate context

S15 ADVANCE would provide the 3rd CALIBRATED belief required for Mechanism Gate unlock:
- ≥10 SOURCED: ✓ (satisfied)
- ≥3 CALIBRATED (excl. C1/C2/C3): S1 ✓, S2 ✓, S15 → would be 3/3 ✓
- Falsification pathway: ✓ (S19 INVALIDATED [S1-context], 2026-07-05 council)

ADVANCE verdict here unlocks Mechanism Gate. Do NOT apply gate-change or extraction unlock
without user approval even if ADVANCE is confirmed — present to user first.
