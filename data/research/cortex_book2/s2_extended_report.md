# S2 Threshold Extension Report — 1.5x and 1.6x

**Generated:** 2026-07-08
**Pre-reg:** knowledge/backtests/2026-07-08_s2_extended_prereg.md
**New baseline (S2@1.4x recomputed):** OOS MAR = 2.5292 (expected ~2.5447; reproducibility OK)
**G1a gate (binding):** >= 2.5892
**G1b gate (advisory floor):** >= 1.2646

---

## Results

| Threshold | OOS MAR | Delta vs S2@1.4x | sub-A MAR | sub-B MAR | N_OOS | Verdict |
|-----------|---------|------------------|-----------|-----------|-------|---------|
| 1.4x (baseline) | 2.5292 | — | — | — | 2380 | BASELINE |
| 1.5x | 1.6201 | -0.9090 | 2.8746 | 0.9276 | 2179 | CONDITIONAL-ADVANCE |
| 1.6x | 1.4762 | -1.0530 | 2.9348 | 0.3742 | 1997 | CONDITIONAL-ADVANCE |

---

## Gate Details

### vol_1_5x (1.5x)
- G1a (relative, binding): FAIL (1.6201 vs threshold 2.5892)
- G1b (absolute floor, advisory): PASS (1.6201 vs threshold 1.2646)

### vol_1_6x (1.6x)
- G1a (relative, binding): FAIL (1.4762 vs threshold 2.5892)
- G1b (absolute floor, advisory): PASS (1.4762 vs threshold 1.2646)

---

## Interpretation — Monotonic Trend Confirmation Table

| Metric | S2@1.2x | S2@1.3x | S2@1.4x (baseline) | S2@1.5x | S2@1.6x |
|--------|---------|---------|---------------------|---------|---------|
| OOS MAR | 2.3608 | 2.4804 | 2.5292 | 1.6201 | 1.4762 |
| sub-B MAR | — | 1.191 | — | 0.9276 | 0.3742 |

**Monotonic trend REVERSES at 1.5x.** OOS MAR drops -0.909 from baseline at 1.5x, continues deteriorating at 1.6x (-1.053).

## Mechanism

The reversal is driven by sub-B (2023-2026 choppy regime) collapse:
- S2@1.3x sub-B: 1.191 (regime-agnostic, confirmed CALIBRATED)
- S2@1.5x sub-B: 0.9276 (−22%)
- S2@1.6x sub-B: 0.3742 (−69% from S2@1.3x sub-B)

Sub-A (2020-2022 bull) actually remains strong (2.87 and 2.93) — the stricter filter
works well in trending markets. But in the choppy 2023-2026 regime, volume surges >=1.5x
are too rare and over-constrain the signal pool, removing regime-agnostic signals that
S2@1.4x and S2@1.3x retained.

**Structural conclusion:** S2@1.4x is the confirmed peak of the monotonic volume-filter
improvement curve. The regime-agnostic edge that made S2 the PRIMARY FILTER (sub-B 1.191
vs S1 sub-B 0.546) is degraded at thresholds above 1.4x.

## Program Verdict

**Both candidates: CONDITIONAL-ADVANCE** — above advisory G1b floor but below binding G1a gate.
**No ADVANCE candidates. Program goal (OOS MAR > 2.5447) not achieved via S2 threshold extension.**

S2@1.4x remains the A3+S2 benchmark threshold. No update to CALIBRATED operating threshold (1.3x).

## Confirmed Knowledge

1. S2 optimal volume threshold: 1.4x (maximum monotonic improvement; higher thresholds degrade sub-B)
2. Regime-agnostic character of S2 is fragile above 1.4x (choppy regime cannot sustain 1.5x signal frequency)
3. The gap to OOS MAR > 2.5447 is NOT closeable via S2 threshold manipulation

## Next Research Direction

Per brain beliefs:
- S20 gate zero: BORDERLINE (78.8%). Dual-track pre-reg required (count-only leg immune to band capping).
- PA-008/PA-009: both PASS/VIABLE. Exit mechanism improvements on A3+S2 are structurally viable.
- S18 reframe: timing overlay hypothesis open; needs new pre-reg.

`RESEARCH_ONLY_NOT_PRODUCTION`
