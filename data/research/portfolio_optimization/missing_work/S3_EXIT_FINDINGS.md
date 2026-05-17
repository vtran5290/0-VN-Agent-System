# S3 Exit Optimization — Findings

## Top 15 configurations by MAR

| Variant | TP% | Trail | MaxHold | Cloud Loss | No-Progress | N | MAR | CAGR | MaxDD | TP1 Rate | Avg Hold |
|---------|-----|-------|---------|------------|-------------|---|-----|------|-------|----------|----------|
| max_hold | 18% | 3.5× | 60 | — | — | 11632 | 0.377 | 7.9% | -21.0% | 19.4% | 55b |
| cloud_loss | 18% | 3.5× | 250 | 2b | — | 11632 | 0.264 | 6.2% | -23.4% | 19.9% | 28b |
| cloud_loss | 18% | 3.5× | 250 | 3b | — | 11632 | 0.204 | 5.0% | -24.8% | 24.5% | 32b |
| tp_trail | 12% | 2.0× | 250 | — | — | 11632 | 0.092 | 2.8% | -30.7% | 72.5% | 110b |
| tp_trail | 12% | 3.0× | 250 | — | — | 11632 | 0.090 | 2.3% | -25.6% | 71.2% | 120b |
| max_hold | 18% | 3.5× | 90 | — | — | 11632 | 0.075 | 2.7% | -35.6% | 32.1% | 76b |
| tp_trail | 10% | 3.0× | 250 | — | — | 11632 | 0.070 | 2.3% | -33.3% | 74.8% | 110b |
| tp_trail | 15% | 2.5× | 250 | — | — | 11632 | 0.065 | 2.1% | -32.6% | 66.9% | 128b |
| tp_trail | 10% | 2.5× | 250 | — | — | 11632 | 0.062 | 2.2% | -36.1% | 75.5% | 105b |
| tp_trail | 15% | 2.0× | 250 | — | — | 11632 | 0.058 | 2.1% | -35.9% | 67.6% | 123b |
| max_hold | 18% | 3.5× | 180 | — | — | 11632 | 0.056 | 2.1% | -37.3% | 52.9% | 122b |
| tp_trail | 18% | 2.0× | 250 | — | — | 11632 | 0.047 | 1.7% | -36.3% | 62.6% | 135b |
| tp_trail | 12% | 2.5× | 250 | — | — | 11632 | 0.029 | 1.1% | -37.1% | 71.8% | 115b |
| tp_trail | 15% | 3.0× | 250 | — | — | 11632 | 0.028 | 1.0% | -36.5% | 66.2% | 133b |
| tp_trail | 12% | 3.5× | 250 | — | — | 11632 | 0.020 | 0.8% | -37.5% | 70.5% | 125b |

## Best exit config

- TP: 18%, Trail: 3.5×ATR14, MaxHold: 60 bars
- MAR: 0.377, CAGR: 7.9%, MaxDD: -21.0%

## Key Finding

**max_hold = 60 bars is the single most important S3 parameter.**

S3 baseline (250-bar hold): MAR=-0.011. Simply capping at 60 bars: MAR=0.377.
This alone clears the PAPER_TRADE_SHADOW gate (0.30).

Why: S3 uses EMA21/55 (fast cycle). Holding 250 bars means riding the full reversal
of a faster signal. Positions that have not resolved within 60 bars are dead weight.
The 250-bar max_hold was designed for A3 (EMA20/100), not S3.

Cloud-loss exit (2 bars below EMA55): MAR=0.264 — better than baseline but worse than
max60. Tighter exits reduce MAR because they cut winners short in choppy markets.

No-progress exits (cut if no +5% in 20 bars): MAR=0.010 — harmful.

## Combined with liquidity filter

max_hold=60 + top-100 ADV symbols: MAR=0.324, CAGR=11.58%, MaxDD=-35.74%, n=4,227.
Higher CAGR but worse MaxDD — not recommended as the primary config.
max_hold=60 alone (full universe, n=11,632) has better MAR (0.377) and lower MaxDD (-21%).

## Implementation note

S3 paper-trade shadow must use max_hold=60. The TP1 and trail parameters are unchanged
from the S3 config (TP=18%, trail=3.5×ATR14). Only the max_hold changes.
