# Pre-Registration: PA-007 — ATR-Adjusted Position Sizing Overlay
# PA Status: TESTED — PASS (C2_atr10) / FAIL C1_atr20 (G5 only) — 2026-07-05
# Harness: cortex_pa007_atrsizing.py — OOS MAR C2=2.2571, baseline 1.7844; all 6 gates PASS (C2)
# C1_atr20: OOS MAR 2.5792 — G5 FAIL (2021 high-vol capture 77.9% vs 90% floor)
# Sub-B: C2 0.8571 vs flat 0.547 (ATR sizing DOES NOT collapse sub-B — contrast with S6 Kelly)
# Candidate to advance: C2_atr10 (k_val=0.028000, 10-day ATR window)
# NEXT: Trigger #5 dual-judge (opus + ChatGPT, independent) REQUIRED before config enabled:true
# [SECTOR-MAP-GAP] advisory: sector attribution naming mismatch — re-run with canonical names if needed
# ✅ User sign-off received: 2026-07-05 ("approved" — Claude Cowork session, higher council review)
# Date: 2026-07-05
# Council authority: ChatGPT APPROVE (advisory) + opus APPROVE + fable GAP resolved
# Source: Woodriff, Hedge Fund Market Wizards (2012) — "volatility adjustment [sizing to constant vol
#   equivalent] worked extremely well for the entire history of the program"
# VN application: replace flat 1/20 position cap with ATR-scaled weight; size inversely proportional
#   to recent 20-day ATR to maintain constant vol-equivalent risk across A3_RS positions
#
# THIS IS A PRE-REGISTRATION DOCUMENT.
# Gates must be locked BEFORE Cursor runs the harness.
# No gate changes after data is seen.
# Activation requires: (1) user sign-off here; (2) Trigger #5 dual-judge on first run; (3) config flag enabled:false.

---

## User sign-off (required before any run)
```
USER SIGN-OFF: [✓] RECEIVED — 2026-07-05
Date: 2026-07-05
Signed: User (Claude Cowork session — "approved" — higher council review)
```
Sign-off confirmed at top of file. Harness may proceed.

---

## Belief / protocol amendment statement (LOCKED)

"Sizing A3_RS positions inversely proportional to each stock's recent 20-day ATR (constant vol-equivalent position sizing) will produce better risk-adjusted returns than flat 1/20 position cap sizing, because it normalizes position risk across high- and low-volatility entries without changing the entry/exit signal logic."

PA type: SIZING OVERLAY — does NOT modify entry criteria, exit criteria, or signal logic. Only affects position size after signal fires.

---

## Architecture constraints (HARD RULES — do not override)

1. **Cap precedence:** The 1/20 position cap (20-stock maximum) binds AFTER the ATR-scaled weight is computed. Never let vol-scaling push a single position above 1/20 of portfolio. Formula: `pos_size = min(1/20, k / ATR_20d)` where k is a scaling constant. Cap is the floor, not the numerator.
2. **Entry/exit frozen:** PA-007 modifies ONLY position size. No change to A3_RS entry signals, exit signals, or regime gating. C1 bear-regime block is upstream — PA-007 operates only within C1-permitted (bull) periods.
3. **No over-penalization of high-vol winners:** ATR-scaling must not systematically reduce exposure to high-volatility stocks that are genuine momentum leaders. This is why the 2021 capture check is required (2021 VN bull run featured high-vol outperformers). If high-vol winners lose more than 10% of their expected P&L contribution after scaling → attribution investigation required.
4. **±7% band fill-realism:** VN ±7% daily price band caps fill precision. High-ATR stocks may systematically under-fill vs. model's intended vol-equivalent size. Add fill-realism check (realized fill fraction vs. model fill): if high-ATR stocks have realized fill < 80% of model intention on average → add a fill-adjusted-MAR variant to the gate.
5. **Independent test first:** PA-007 must be tested in isolation (PA-007 only, PA-008 off) before any combined run. Do not conflate PA-007 and PA-008 effects.

---

## Lane A test design (activate ONLY after user sign-off)

### Candidate parameters (k=2)

| Candidate | Signal condition | ATR window | Description |
|-----------|-----------------|-----------|-------------|
| C1_atr20 | A3_RS signal fires; size = min(1/20, k/ATR_20d) | 20 trading days | Standard Woodriff volatility normalization |
| C2_atr10 | A3_RS signal fires; size = min(1/20, k/ATR_10d) | 10 trading days | Shorter window; more responsive to recent vol |

Scaling constant k: computed from IS data to set median position size equal to the existing 1/20 flat cap. Lock before OOS run. Do NOT adjust after seeing OOS results.

### Baseline
- A3_RS standalone frozen baseline OOS MAR: per current knowledge.md calibrated value (check knowledge.md § Calibrated Beliefs before running — do not use a stale baseline)

### Test universe
- All A3_RS OOS signal periods (same IS/OOS split as existing calibrated signals)
- Do NOT re-optimize IS period to fit ATR scaling

### Gate parameters (LOCK before run, AFTER user sign-off)

```
G1a (relative): OOS MAR ≥ baseline × 1.05 (5% relative improvement — conservative; sizing overlay)
G1b (absolute): OOS MAR ≥ 0.516 (standard absolute floor)
G2 (MaxDD): OOS MaxDD ≤ frozen-baseline MaxDD × 1.10 (no more than 10% worse drawdown)
G3 (fill-realism): realized fill fraction for high-ATR stocks ≥ 80% of model intention on average
G4 (turnover): turnover increase vs. flat-cap baseline ≤ 20% (sizing changes alone should not churn)
G5 (2021 capture): high-vol winner P&L contribution in 2021 sub-period ≥ 90% of flat-cap baseline
Standing guardrail: if both baseline AND candidate OOS MAR are negative → CONDITIONAL-ADVANCE only
Borderline rule: G1a margin < 0.02 MAR units → CONDITIONAL-ADVANCE; requires confirmation run before activation
Window scoping: all gate thresholds calibrated on same OOS window as candidate; no cross-window reuse
```

### Attribution slices required (output alongside gate verdicts)
- Sector attribution: which sectors gain/lose MAR from vol-sizing?
- Year attribution: 2019, 2020, 2021, 2022, 2023, 2024, 2025 (flag any year where PA-007 materially loses vs. baseline)
- High-vol vs. low-vol split: do high-vol stocks systematically lose expected contribution?

---

## Interaction test (after standalone PA-007 passes)

**PA-007 × PA-008 combined test:**
- Gate: OOS MAR ≥ max(PA-007-alone OOS MAR, PA-008-alone OOS MAR) × 1.02 (2% marginal floor for second overlay)
- Additional check: turnover does not compound beyond 25% above baseline

**PA-007 × C1:**
- C1 is upstream; PA-007 applies within C1-permitted periods only. No interaction test needed.

**PA-007 × S17 (if S17 CALIBRATED by then):**
- S17 is a signal filter (entry); PA-007 is sizing. If both active: S17 filters which signals fire; PA-007 sizes the ones that pass. Sequential, not conflicting. No interaction gate needed.

---

## Config flag

```yaml
# A3_RS system config
pa007_atrsizing:
  enabled: false    # HARD DEFAULT — do not enable without user sign-off + Trigger #5 dual-judge
  atr_window: 20    # trading days
  candidate: C1_atr20  # lock after test
  cap_override: false   # 1/20 cap always binds last; ATR-scaled weight cannot exceed it
```

---

## Files to create (Cursor, after user sign-off)

1. `pp_backtest/cortex_pa007_atrsizing.py` — harness script
2. `knowledge/backtests/2026-07-05_pa007_atrsizing_gates_addendum.md` — gates addendum after IS calibration
3. `pp_backtest/attribution/pa007_sector_year_attribution.py` — attribution slices

---

## References
- Source: Woodriff, Hedge Fund Market Wizards (2012) — pattern-extracted from E:\Calibre-books\...\Hedge Fund Market Wizards\
- Council: 2026-07-05-2100_SchwagerPACandidates_Council.md
- Verification gates: verification-harness.md § VN Agent System → promotion gate design
- PA lifecycle: sources.md → PA candidate ledger (once sources.md PENDING_WRITE is applied)
