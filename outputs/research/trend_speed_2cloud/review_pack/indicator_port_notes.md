# Pine → Python — v2

## Speed reset (fixed v2)
Pine sequence on cross bar:
1. `speed := c - o`
2. `speed := speed + c - o`

Python v2: `speed[i] = 2 * (RMA(close,10) - RMA(open,10))` on cross; else `speed[i-1] + co`.

## T2 gate evaluation
- Pullback detection unchanged (low ≤ T1_entry×0.96 within 30 bars after T1 entry).
- Gate features read at **T2 fill bar** only (causal).
- If pullback occurs but gate/breadth blocks → **T1-only** `blended_net_return = t1_net` (exact).

## Anti-lookahead
- Signal-bar features for entry filters; fill-bar features for T2 gates.
- Rolling ranks: trailing 252 bars, min 60.
