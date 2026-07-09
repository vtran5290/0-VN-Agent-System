# S20 Price-Magnitude Gate-Zero Screen

**Date:** 2026-07-09
**Pre-reg:** `knowledge/backtests/2026-07-08_s20_pricemag_prereg.md`
**Baseline pool:** A3_RS+S2@1.4× OOS 2020-2026
**OOS positions:** 2375

## Locked thresholds

| Candidate | Threshold |
|-----------|-----------|
| PM-A | max single-day return ≥ 3.0× ATR14 (trigger day) |
| PM-B | max single-day return ≥ 8% |
| PM-C | max single-day return ≥ 5.0× holding-period avg daily return (denom min 2d) |

## Trigger rates and verdicts

| Candidate | Triggered | Rate | Median fire day | Verdict |
|-----------|-----------|------|-----------------|---------|
| PM-A | 111/2375 | 4.7% | 117 | **TOO RARE** |
| PM-B | 675/2375 | 28.4% | 33 | **ACCEPTABLE** |
| PM-C | 1061/2375 | 44.7% | 2 | **ACCEPTABLE** |

## Year breakdown (entry year)

### PM-A
| Year | Triggered | Total | Rate |
|------|-----------|-------|------|
| 2020 | 26 | 350 | 7.4% |
| 2021 | 8 | 374 | 2.1% |
| 2022 | 1 | 150 | 0.7% |
| 2023 | 14 | 186 | 7.5% |
| 2024 | 48 | 483 | 9.9% |
| 2025 | 14 | 556 | 2.5% |
| 2026 | 0 | 276 | 0.0% |

### PM-B
| Year | Triggered | Total | Rate |
|------|-----------|-------|------|
| 2020 | 112 | 350 | 32.0% |
| 2021 | 94 | 374 | 25.1% |
| 2022 | 40 | 150 | 26.7% |
| 2023 | 52 | 186 | 28.0% |
| 2024 | 162 | 483 | 33.5% |
| 2025 | 162 | 556 | 29.1% |
| 2026 | 53 | 276 | 19.2% |

### PM-C
| Year | Triggered | Total | Rate |
|------|-----------|-------|------|
| 2020 | 306 | 350 | 87.4% |
| 2021 | 138 | 374 | 36.9% |
| 2022 | 7 | 150 | 4.7% |
| 2023 | 62 | 186 | 33.3% |
| 2024 | 238 | 483 | 49.3% |
| 2025 | 260 | 556 | 46.8% |
| 2026 | 50 | 276 | 18.1% |

## Overall recommendation

**PM-B ACCEPTABLE — proceed to full OOS exit-class harness for PM-B**

### Per-candidate notes
- **PM-A** (4.7%): Threshold too strict; reassess before full run.
- **PM-B** (28.4%): Proceed to full OOS exit-class harness.
- **PM-C** (44.7%): Proceed to full OOS exit-class harness.
