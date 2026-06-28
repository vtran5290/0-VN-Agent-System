# D1 Capitulation Sleeve — Gate Results

**Label:** RESEARCH_ONLY_NOT_PRODUCTION
**Sample size (unique N=3 events):** 402 — **OK**

## Best config
- N2_slip0.005_cb15_D
- MAR=0.2784, CAGR=0.0259, MaxDD=-0.0931, n_trades=838

## Unlock-day gap distribution (prior floor close -> unlock open)
- n=402, mean=-0.024040714632502118, median=-0.04262200324791504, p5=-0.09754779169413302, p95=0.06997649769157174

## A3 correlation
- annual=0.07948249173011455, daily=-0.004402846010774182 (n=3664)

## Kill criteria
- **K1:** PASS
- **K2:** PASS
- **K3:** PASS
- **K4:** PASS
- **K5:** PASS
- **K6:** PASS

## Sweep top 5 by MAR

          config_id  mar_full     cagr    max_dd  n_honest_trades  win_rate
N2_slip0.005_cb15_D  0.278416 0.025908 -0.093056              838  0.643198
N2_slip0.010_cb15_D  0.223032 0.021112 -0.094658              838  0.630072
N2_slip0.015_cb15_D  0.165434 0.016384 -0.099036              838  0.618138
N4_slip0.005_cb20_D  0.161864 0.004776 -0.029509               85  0.623529
N2_slip0.005_cb10_D  0.135031 0.010495 -0.077721              720  0.622222