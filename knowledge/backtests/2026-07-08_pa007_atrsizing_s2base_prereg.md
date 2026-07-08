# Pre-Registration: PA-007 v2 — ATR Sizing Overlay on A3_RS+S2@1.4× Base
# PA Status: RUN COMPLETE — FAIL (G5 2021 capture); OPUS-GATE pending for sizing-class S2-base first run
# Council authority: Opus REDIRECT + Fable GAP resolved — 2026-07-08-2300_PA007_BaselineMismatch_Council.md
# Baseline: A3_RS+S2@1.4× (OOS MAR 2.5233, MaxDD −5.57%, 2020-2026)
# Class: SIZING — overlay_class = sizing
# Prior result (inadmissible): C2_atr10 OOS MAR 2.2571 on A3_RS standalone (1.7844) — different universe
# Date: 2026-07-08
#
# THIS IS A PRE-REGISTRATION DOCUMENT.
# Gates must be locked BEFORE Cursor runs the harness.
# No gate changes after data is seen.
# Activation requires: (1) user sign-off here; (2) harness run; (3) Trigger #5 dual-judge; (4) config enabled:true.

---

## User sign-off (required before any run)
```
USER SIGN-OFF: [x] APPROVED — PA-007 v2 (2026-07-08, user)
Date: 2026-07-08
Signed: user (Cursor session)
```
Prior sign-off (2026-07-05) was for A3_RS standalone run. Does NOT carry to this pre-reg.

---

## Belief / protocol amendment statement (LOCKED)

"Sizing A3_RS+S2@1.4× positions inversely proportional to each stock's recent 10-day ATR (constant vol-equivalent position sizing) will produce better risk-adjusted returns than flat 1/20 position cap sizing on the S2-filtered universe, because it normalizes position risk across high- and low-volatility entries without changing the entry/exit/filter logic."

PA type: SIZING OVERLAY — does NOT modify entry criteria, exit criteria, S2 filter, or regime logic. Only affects position size after a signal passes S2.

---

## Architecture constraints (carry-forward from v1 — unchanged)

1. **Cap precedence:** 1/20 position cap binds AFTER ATR-scaled weight. `pos_size = min(1/20, k / ATR_10d)`. Cap is the floor, not the numerator.
2. **Entry/exit frozen:** PA-007 v2 modifies ONLY position size. No change to A3_RS entry, S2 filter, exit signals, or C1 regime gating.
3. **No over-penalization of high-vol winners:** ATR-scaling must not systematically reduce exposure to high-ATR S2-surviving stocks. HIGH-RISK: S2 selects for high-vol-surge days which may correlate with above-average ATR — see ATR distribution check requirement below.
4. **±7% band fill-realism:** VN ±7% daily price band. High-ATR stocks may under-fill. Fill fraction check required.
5. **Independent test:** PA-007 v2 tested on A3_RS+S2@1.4× in isolation. PA-008/PA-009 are already CLOSED-NEGATIVE.

---

## New requirement: ATR distribution check (council-mandated, tier-b distribution-shift)

Before gate run, produce:
- ATR_10d distribution for S2-surviving signals (those passing S2@1.4× filter)
- ATR_10d distribution for full A3_RS signals (all signals, including filtered-out)
- Comparison: mean, median, 75th percentile ATR for both sets
- If S2-surviving ATR is systematically higher (mean >20% above full-universe mean): flag [ATR-UNDERSIZING-RISK] and include a compensated-k variant (k calibrated on S2-filtered IS data only, not full IS)

This check must appear in the harness output before gate verdicts are issued.

---

## Baseline configuration (LOCKED — must match harness baseline exactly)

```yaml
baseline_configuration: A3_RS+S2@1.4x
baseline_oos_mar: 2.5233
baseline_oos_maxdd: -0.0557
baseline_oos_cagr: 0.1405
baseline_sub_a_mar: 4.4083
baseline_sub_b_mar: 1.1312
baseline_window: 2020-2026
n_oos_trades: 2383
k_calibration_source: "S2-filtered IS data ONLY (not standalone IS)"
sizing_headroom_declared: "1/20 cap is the binding constraint; ATR sizing compresses below cap for high-ATR stocks"
k_atr20: 0.02300000
k_atr10: 0.02600000
n_is_s2_pairs: 1762
```

k must be derived from the S2-filtered IS universe such that median position size = 1/20 flat cap. Do NOT reuse k=0.028 from standalone IS calibration — the signal distribution differs.

---

## Gate parameters (LOCK before run — fill [●] after IS calibration, before OOS run)

```
overlay_class: sizing
baseline_configuration: A3_RS+S2@1.4x

G1a (relative): OOS MAR >= 2.5233 × 0.90 = 2.2710
G1b (absolute MaxDD): OOS MaxDD >= -0.0557 × 1.05 = -0.0585 (must not worsen by >5pp)
G1c (CAGR floor): OOS CAGR > 0%
G1d_a (sub-A floor): OOS sub-A MAR > 0
G1d_b (sub-B floor): OOS sub-B MAR > 0
G2 (fill-realism): realized fill fraction for high-ATR S2 signals >= 80% of model intention
G3 (turnover): turnover increase vs. A3_RS+S2@1.4× flat-cap <= 20%
G5 (2021 high-vol capture): high-vol winner P&L contribution in 2021 sub-period >= 85% of A3_RS+S2 flat-cap baseline
      NOTE: G5 threshold reduced to 85% (from 90%) for the S2 universe — by-construction all surviving signals are high-vol; 90% would require near-perfect recapture which is structurally harder. Council authority: Fable GAP resolved.

Standing guardrails:
- If both baseline AND candidate OOS MAR are negative → maximum status CONDITIONAL-ADVANCE
- Borderline rule: G1a margin < 0.02 MAR units → CONDITIONAL-ADVANCE; confirmation run required
- Negative OOS MAR cap: if candidate OOS MAR < 0 → PARKED regardless of relative gate
```

---

## Candidate parameters

| Candidate | ATR window | k (to be calibrated) | Description |
|-----------|-----------|---------------------|-------------|
| C2_atr10_s2 | 10 trading days | 0.02600000 | Re-run of v1 C2 on S2-filtered universe |
| C1_atr20_s2 | 20 trading days | 0.02300000 | Re-run of v1 C1 on S2-filtered universe (previously failed G5 at standalone — failed G5 again on S2) |

Note: C1_atr20 failed G5 on standalone at 77.9%. On the S2 universe (all signals high-vol), the 2021 capture dynamics may differ. Include both candidates.

---

## Multi-episode stress gate (sizing-class requirement)

Test must report results across >= 2 distinct regime sub-windows:
- sub-A (bull regime periods): OOS sub-A MAR > 0
- sub-B (choppy/bear-adjacent): OOS sub-B MAR > 0
Use same sub-window definitions as A3_RS+S2@1.4× baseline (sub-A = 4.4083, sub-B = 1.1312).

---

## Attribution slices required (alongside gate verdicts)

- Year attribution: 2020, 2021, 2022, 2023, 2024, 2025 — flag any year where PA-007 v2 materially loses vs. A3_RS+S2 flat-cap
- ATR distribution comparison: S2-surviving vs. full A3_RS (per council mandate above)
- High-ATR stock P&L contribution before/after sizing

---

## Config flag

```yaml
pa007_atrsizing_v2:
  enabled: false    # HARD DEFAULT — do not enable without user sign-off + harness + Trigger #5
  atr_window: "[●]"  # lock after test
  candidate: "[●]"   # lock after test
  baseline_configuration: A3_RS+S2@1.4x
  cap_override: false
```

---

## Files to create (Cursor, after user sign-off)

1. `pp_backtest/cortex_pa007_atrsizing_v2.py` — harness on A3_RS+S2@1.4× base
2. `data/research/cortex_pa007_s2base/baseline_config.json` — baseline locked values
3. ATR distribution report inline in harness output

---

## Run results (2026-07-08)

| Candidate | OOS MAR | MaxDD | G1a | G1b | G2 | G3 | G5 2021 | Verdict |
|-----------|---------|-------|-----|-----|----|----|---------|---------|
| C1_atr20_s2 | 2.3296 | −5.57% | PASS | PASS | PASS | PASS | FAIL (25.8%) | FAIL |
| C2_atr10_s2 | 2.3081 | −5.72% | PASS | PASS | PASS | PASS | FAIL (25.5%) | FAIL |

ATR distribution: S2/full atr10 ratio 1.033 — no [ATR-UNDERSIZING-RISK].
Kill driver: G5 2021 high-vol P&L capture (~25% vs 85% floor).
Artifact: `data/research/cortex_pa007_s2base/pa007_atrsizing_v2_meta.json`

---

## References
- Prior pre-reg (standalone): `knowledge/backtests/2026-07-05_schwager_pa007_atrsizing_prereg.md`
- Prior gates addendum: `knowledge/backtests/2026-07-05_pa007_atrsizing_gates_addendum.md`
- Council: `D:\V\00. Command Center\05_AI_Handoffs\2026-07-08-2300_PA007_BaselineMismatch_Council.md`
- Framework edits required: `D:\V\.claude\rules\verification-harness.md` (Cursor task)
- Baseline source: `D:\V\0. VN Agent System\data/research/cortex_pa009_exit_class/baseline_maxdd.json`
