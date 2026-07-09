# S20 Price-Magnitude Gate-Zero Screen Results

**Date:** 2026-07-08
**Pre-reg:** `knowledge/backtests/2026-07-08_s20_pricemag_prereg.md`
**Baseline pool:** A3_RS+S2@1.4× OOS 2020-2026
**OOS positions (raw):** 2375
**Valid positions analyzed:** 2375

## Locked thresholds (pre-registered before screen)

| Candidate | Threshold |
|-----------|-----------|
| PM-A | max single-day return ≥ 3.0× ATR14 (on trigger day) |
| PM-B | max single-day return ≥ 8% |
| PM-C | max single-day return ≥ 5.0× holding-period avg daily return |

## Trigger rates and verdicts

| Candidate | Triggered | Rate | Verdict |
|-----------|-----------|------|---------|
| PM-A | 111/2375 | 4.7% | **too rare** |
| PM-B | 675/2375 | 28.4% | **proceed** |
| PM-C | 1285/2375 | 54.1% | **borderline** |

## Gate-zero verdict rules (from pre-reg)

| Trigger rate | Verdict |
|---|---|
| < 20% | too rare — reassess threshold |
| 20%–50% | proceed — full OOS harness |
| 50%–70% | borderline — parameter sensitivity required |
| > 70% | over-fires — do not run full OOS |

## Max single-day return distribution (valid positions)

| Bin | Count |
|-----|-------|
| ≥ 8% | 675 |
| 5%–8% | 1604 |
| 3%–5% | 70 |
| < 3% | 26 |

## Overall recommendation

**Proceed to full OOS harness for candidate(s) in proceed/borderline range**

### Per-candidate notes
- **PM-A** (4.7%): Too rare — threshold too strict; reassess before full run.
- **PM-B** (28.4%): Acceptable trigger rate — proceed to full OOS exit-class harness.
- **PM-C** (54.1%): Borderline — include ±1 threshold step sensitivity before full run.
