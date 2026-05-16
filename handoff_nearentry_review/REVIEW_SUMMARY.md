# Near-Entry Window Optimisation — Batch Review Summary

**Date:** 2026-05-15  
**Repo:** VN Agent System — Vietnam equities EMA-cloud strategy  
**Reviewer requested by:** VTran  

---

## What this batch did

This batch completed a bounded validation of the daily scan near-entry watchlist windows for two
strategies. The goal was to replace the legacy symmetric `±7%` filter with asymmetric, per-strategy
validated thresholds — and to determine whether hard-cap filtering or quality labelling is the
better operational approach.

---

## Context: the strategies being patched

| Label | File code | Signal | Rank | Universe | Config |
|-------|-----------|--------|------|----------|--------|
| **A3 PRIMARY** | `B_cloud20_100` | EMA 20/100 cloud turn | `ema_dist` | ex-VIN3 (excl VIC/VHM/VRE/VPL) | tp=18%, trail=2.5× |
| **S3 SHADOW** | `B_cloud21_55` | EMA 21/55 cloud turn | `mom20` | full universe | tp=18%, trail=3.5× |
| **C_GK** | `C_GK_regime` | Gaussian-Kernel + G07 regime gate | `ema_dist_55` | full | legacy |

Near-entry watchlist = symbols where the last cloud-turn signal in the prior 30 bars is within
`X%` of today's close and the position is not already open.

---

## Steps completed in this batch

### Step 1 — OOS Gate (`run_oos_gate.py`)
- Subperiod stability check: 2012–2017, 2018–2022, 2023–2026.
- **A3 PRIMARY** — PASS on all periods with OOS capture ≥50%.
- **S3 SHADOW** — FRAGILE PASS: wins 3/3 periods, strong DD improvement, but thin margins.
  Advances to Step 3 **conditionally** with active monitoring.
- Fixed: G/B contradiction in summary (G said "keep ex_vin3"; B said S3 advances — now consistent).
- Output: `data/research/optimization/oos_gate_summary.md`

### Step 2 — Sizing overlays (`run_sizing_optimization.py`)
- Sizing grid: `{equal, inv_atr, conv_mom60, inv_atr_conv_mom60}` × `max_positions {10,12,16,20,24}`
  × `gross_exposure {0.70, 0.85, 1.00}`.
- Anchor baseline: `equal / max_positions=20 / gross=1.00`.
- **Finding**: `inv_atr` is WORSE than `equal` for A3 (Sharpe 1.117 vs 1.182). Main driver of
  improvement is `max_positions=24` (+0.054 Sharpe vs 20). Sizing mode adds only marginal lift.
- A3 best: Sh=1.241 (+0.059 vs anchor), DD=-27.3% → **PASS**
- S3 best: Sh=1.146 (+0.109 vs anchor), DD=-27.2% → **PASS**
- Output: `data/research/optimization/sizing_summary.md`

### Step 3 — Same-exit near-entry analysis (`run_nearentry_opt.py`)
- Method: For each historical trade, simulate delayed entry at T+k bars at actual close. Hold
  exit value fixed (same-exit simplification). Report return and hit-rate by drift bucket.
- **Limitation found**: same-exit is BIASED — it overestimates downside returns (pullback entries
  look better than they are) and underestimates upside returns (chase entries look worse).
  This reversed the initial ">+14% = hard reject" conclusion.
- Output: `data/research/optimization/nearentry_summary.md`

### Step 4 — Realistic exit replay (`run_nearentry_realistic.py`)
- Corrected method: re-run `_exit_partial_tp_v2` with `start=T+k`, `entry_price=P_k`.
  TP1 reprices to `P_k*(1+tp_pct)`, so the exit simulation is fully correct for each delayed entry.
- **Critical finding**: entries above `+14%` from signal are **NOT bad**. They are
  momentum-confirmed: A3 shows 10.38% mean net vs 6.61% baseline; S3 shows 11.63% vs 6.35%.
  These entries outperform because strong movers tend to continue and hit the repriced TP1.
- Same-exit bias direction confirmed opposite of intuition: same-exit OVERESTIMATES downside
  returns by 1–9pp and UNDERESTIMATES upside returns by 2–10pp.
- Output: `data/research/optimization/realistic_near_entry_validation.csv` (210,998 rows, 26 MB —
  500-row sample included in this zip as `realistic_near_entry_validation_sample500.csv`)

### Step 5 — 3-mode comparison (`daily_scan_near_entry_comparison.csv`)
Three filter modes evaluated on the realistic replay data:

| Mode | Description | A3 mean_net | A3 % included | A3 excluded mean |
|------|-------------|-------------|----------------|------------------|
| A | `abs(pct_vs) ≤ 7%` (legacy) | 6.22% | 81.3% | 7.75% |
| B | `[-10%,+8%]` hard filter | 6.30% | 86.8% | 7.89% |
| C | Labels only, block `<-DN` only | 6.36% | 96.3% | 10.39% |

**Mode B EXCLUDES the best entries.** The excluded bucket in Mode B (mostly `>+14%`) has
mean 7.89% for A3 and 11.63% for S3. Filtering these out hurts total opportunity.

**Mode C is the correct operational approach**: apply only a downside floor (reject damaged/
deep-pullback entries), label everything else by quality, let the operator decide on stretched
and momentum-confirmed entries.

### Step 6 — Code review (`near_entry_scan_review.md`)
Documented the filter locations in `daily_three_strategy_scan.py`, C_GK isolation rationale,
and the exact patch specification.

### Step 7 — Patch applied (`daily_three_strategy_scan.py`)
See patch details below.

---

## Thresholds validated

| Strategy | Downside floor | Upside label boundary | Approach |
|----------|---------------|----------------------|----------|
| A3 (B_cloud20_100) | -10% hard floor | +8% (acceptable→stretched) | Mode C, no upside cap |
| S3 (B_cloud21_55) | -6% hard floor | +8% (acceptable→stretched) | Mode C, no upside cap |
| C_GK | ±7% symmetric | — | **Unchanged** — no asymmetric validation |

**C_GK NOT changed**: different signal family (GK channel + regime gate), no drift-bucket
analysis was done for it. It keeps `CGK_NEAR_ENTRY_PCT = 0.07`.

---

## Quality labels

### A3 (B_cloud20_100) — `_near_entry_label_b20100(pct_vs)`
| Band | Label | Interpretation |
|------|-------|----------------|
| `< -10%` | `deep_pullback` | BLOCKED by floor — not shown |
| `[-10%, -2%)` | `ideal_pullback` | Best risk/reward entry zone |
| `[-2%, +8%]` | `acceptable` | Standard near-entry |
| `(+8%, +14%]` | `stretched` | Elevated entry; still profitable |
| `> +14%` | `momentum_confirmed` | Outperforms baseline — do NOT block |

### S3 (B_cloud21_55) — `_near_entry_label_b2155(pct_vs)`
| Band | Label | Interpretation |
|------|-------|----------------|
| `< -6%` | `damaged` | BLOCKED by floor |
| `[-6%, -2%)` | `ideal` | Best entry zone for S3 |
| `[-2%, +8%]` | `acceptable` | Standard |
| `(+8%, +14%]` | `stretched` | Proceed with smaller size |
| `> +14%` | `momentum_confirmed` | Outperforms baseline — include |

---

## Files changed

| File | Change type | Status |
|------|-------------|--------|
| `pp_backtest/daily_three_strategy_scan.py` | Patched | ✅ Done |
| `pp_backtest/run_oos_gate.py` | Modified (G/B fix) | ✅ Done |
| `pp_backtest/run_sizing_optimization.py` | Rewritten | ✅ Done |
| `pp_backtest/run_nearentry_opt.py` | Created | ✅ Done |
| `pp_backtest/run_nearentry_realistic.py` | Created | ✅ Done |
| `data/research/optimization/oos_gate_summary.md` | Regenerated | ✅ Done |
| `data/research/optimization/sizing_summary.md` | Created | ✅ Done |
| `data/research/optimization/near_entry_scan_review.md` | Created | ✅ Done |
| `data/research/optimization/nearentry_summary.md` | Created | ✅ Done |
| `data/research/optimization/near_entry_final_recommendation.md` | Created | ✅ Done |
| `data/research/optimization/daily_scan_near_entry_comparison.csv` | Created | ✅ Done |
| `data/research/optimization/realistic_near_entry_validation.csv` | Created (26 MB) | ✅ Done |

---

## Key changes to `daily_three_strategy_scan.py`

### Constants block (replaces `NEAR_ENTRY_PCT = 0.07`)
```python
NEAR_ENTRY_B20100_UP = 0.08   # A3: acceptable→stretched boundary
NEAR_ENTRY_B20100_DN = 0.10   # A3: hard downside floor
NEAR_ENTRY_B2155_UP  = 0.08   # S3: same upside boundary
NEAR_ENTRY_B2155_DN  = 0.06   # S3: tighter downside floor
CGK_NEAR_ENTRY_PCT   = 0.07   # C_GK: unchanged
```

### New functions added
- `_near_entry_band_str(up, dn)` — parameterized header string (was single-value)
- `_near_entry_label_b20100(pct_vs)` — A3 quality label
- `_near_entry_label_b2155(pct_vs)` — S3 quality label

### `scan_cloud_strategy()` signature change
```python
# New keyword-only params:
near_entry_up: float = 0.07,
near_entry_dn: float = 0.07,
label_fn: Callable[[float], str] | None = None,
```

### Filter logic change (line ~376)
```python
# OLD: abs(pct_vs) <= NEAR_ENTRY_PCT  (symmetric, hard cap)
# NEW: pct_vs >= -near_entry_dn  (downside floor only — Mode C)
```

### Output column rename
`"label"` (was `"holding"/"pullback"`) → `"entry_window_label"` (quality category string)

### `scan_c_gk()` — NO changes to filter logic
Filter still uses `abs(pct_vs) <= CGK_NEAR_ENTRY_PCT` (symmetric ±7%). Column still `"label"`.

---

## Review questions for the other AI

1. **Filter asymmetry**: Is `pct_vs >= -near_entry_dn` (downside floor only, no upside cap) the
   correct interpretation of Mode C? Or should there be a hard upside reject at some level?

2. **Momentum_confirmed label**: Given A3 `>+14%` = 10.4% mean vs 6.6% baseline, is it
   appropriate to show these in the watchlist without any warning? Should there be a flag or note?

3. **S3 "damaged" label**: S3 `<-6%` entries were 4.13% mean vs 6.35% baseline, hit 63.7% vs
   65.4%. The floor blocks them. Is -6% the right cut, or should it be -4% or -8%?

4. **`slow_today * 0.97` guard**: This independent slow-EMA floor still applies in Mode C. Does
   it interact badly with `deep_pullback` entries for A3 (which has floor at -10%)? Could a
   stock be -9% vs signal but also below `slow * 0.97`?

5. **C_GK isolation**: Is the "no asymmetric validation for C_GK" policy appropriate, or should
   a similar realistic-replay analysis be run for the GK signal family?

---

*End of REVIEW_SUMMARY.md*
