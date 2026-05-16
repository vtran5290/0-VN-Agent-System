# Phase 1A — Implementation Audit
**Date:** 2026-05-16  
**Script audited:** `pp_backtest/portfolio_optimization_research.py`

---

## Finding 1 — CONFIRMED BUG: `max_position_pct` unused in equal-weight sizing

**Location:** `_run_one_sizing_experiment()` lines 695–698

```python
if sizing_method == "equal_weight":
    positions = params.get("max_open_positions", max_positions)
    equity, n_filled = _build_equity_v2(
        sub, max_positions=positions, rank_mode=rank_mode,
        sizing_mode="equal", gross_exposure=1.0,   # ← max_position_pct never passed
    )
```

The `max_position_pct` value is received as a parameter and stored, but never passed to the equity builder. This means every equal-weight config in the prior grid used the same implicit weight = `1/max_open_positions` regardless of the `max_position_pct` column in the output CSV.

**Impact on prior results:** The prior sizing grid labelled experiments as `A_A3_pct0.050_pos20` through `A_A3_pct0.250_pos20` — all 7 pct variants at the same pos=20 produced **identical metrics** (as seen in the output: same CAGR/Sharpe/MAR). This confirms the bug: the pct label was decorative. The prior results for equal-weight are still valid as a `max_pos` grid, but `max_position_pct` was never actually tested.

**Required fix:**
```python
base_w = min(1.0 / max(positions, 1), params.get("max_position_pct", 1.0))
# Pass as per-trade weight cap; total exposure = base_w * active_positions
```

**No `max_total_exposure` parameter exists anywhere in the engine.** All experiments implicitly assumed gross exposure = 1.0.

---

## Finding 2 — PARTIAL BUG: Rank-based weight normalization can exceed 1.0

**Location:** `_run_rank_based_sizing()` lines 822–828

```python
if mode in ("top_heavy", "sqrt"):
    total = sum(raw_ws)
    if total > 0:
        scale = min(1.0, len(queued) / max_positions)
        raw_ws = [w / total * scale for w in raw_ws]
        raw_ws = [min(w, max_position_pct) for w in raw_ws]  # ← cap AFTER normalize
```

The normalization sets sum to `scale ≤ 1.0`, then applies a per-position cap. If any weights are clipped, the remaining weights are NOT redistributed, so the batch total can be less than `scale` (cash leak) but never more than 1.0 in this path.

However for `linear` mode (lines 787–796):
```python
if mode == "linear":
    w = base * (1 + 0.5 * (rank_pct - 0.5) * 2)  # base ± base/2
return min(w, max_position_pct)
```
Linear weights are **not normalized across the batch** — they are computed independently per position and then capped. If many high-rank positions enter on the same day, sum of weights can exceed 1.0.

Example: 20 positions enter, all rank_pct ≈ 0.9, base=0.05.  
`w = 0.05 * (1 + 0.5*(0.9-0.5)*2) = 0.05 * 1.4 = 0.07` per position.  
20 positions × 0.07 = **1.40 gross exposure** — implicit 1.4× leverage.

In practice most days have few simultaneous entries, but on strong up-days with many signals this can create unintended leverage. The prior linear rank result (CAGR=20.40%) may include unmodelled leverage.

**Required fix:** After computing all weights in a batch, renormalize if sum exceeds `max_total_exposure`.

---

## Finding 3 — OK (by design): Risk-per-trade has no stop-exit simulation

**Location:** `_run_risk_per_trade_sizing()` lines 839–917

Risk-per-trade sizing computes position weight as `weight = min(risk_pct / stop_distance, max_position_pct)` but uses pre-computed `net_return` from the trade ledger (which uses TP/trail exits, not stop exits). There is no stop-exit simulation. This is consistent but is **INVALID_FOR_PRODUCTION** as noted in the Phase 1D spec:

- Stop is used to SIZE the position but never actually EXECUTED.
- A trade sized for a 7% stop loss but exited by TP/trail at 250 bars has very different risk than assumed.
- The high CAGR (59.80%) results from large position sizes on a strategy that rarely stops out (because stops are never triggered in the sim). This significantly overstates production returns.

**Classification: INVALID_FOR_PRODUCTION.** Phase 1D must implement actual stop execution.

---

## Finding 4 — OK BUT INCOMPLETE: Walk-forward uses pre-built ledger (correct) but no per-fold parameter re-estimation

**Location:** `run_walk_forward()` lines 1449–1482

After the fix in the last session, walk-forward uses a pre-built trade ledger sliced by entry date. This is correct for avoiding full re-simulation per fold and is appropriate for signal quality validation.

**Limitation:** Bucket/Kelly parameters are not re-estimated from the training window per fold. This is documented in implementation_notes.md. It means walk-forward results are only valid for equal-weight and fixed rank-based sizing, not for Kelly/bucket methods.

The Kelly stub at line 1479 (`kelly_weight = 0.05`) confirms this was always a placeholder.

---

## Summary Table

| Area | Status | Production Impact |
|------|--------|-------------------|
| Equal-weight `max_position_pct` | CONFIRMED BUG | Prior pct-grid results are invalid as pct tests; valid as pos-grid only |
| Rank-based linear normalization | PARTIAL BUG | Prior linear CAGR=20.40% may include implicit leverage up to ~1.4× |
| Risk-per-trade stop execution | BY DESIGN — INVALID_FOR_PRODUCTION | Prior 59.80% CAGR is overstated; stops never execute |
| Walk-forward parameter leak | BY DESIGN — INCOMPLETE | Kelly/bucket WF results would be invalid; equal-weight WF is OK |

---

## Prior result validity after audit

| Prior result | Still valid? | Notes |
|-------------|-------------|-------|
| A3 baseline (equal pos=20) | YES | max_position_pct=5% = 1/20, equivalent |
| Equal-weight pos-grid (5/10/15/20/30) | YES | Tested max_pos correctly |
| Equal-weight pct-grid (5-25%) | NO | pct parameter was ignored; all identical |
| Linear rank (CAGR=20.40%) | PARTIALLY | Result is real but may include leverage; must retest with normalization fix |
| Pullback scale-in (MAR=0.66/0.72) | YES | No sizing bug; uses blended entry price |
| Convergence experiments | YES | Use equal-weight baseline; sizing bug does not apply |
| Walk-forward (82/125 folds) | YES | Uses equal-weight; parameter leak only affects Kelly |
