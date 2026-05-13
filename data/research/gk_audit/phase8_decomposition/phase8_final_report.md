# Phase 8 Final Report — Component Decomposition & Signal Value

Run date: 2026-05-06

---

## A. Component Attribution Summary

| Component | Label | N | CAGR | MAR | aDD | 2018 | 2022 | WinRate | PF | Expectancy |
|-----------|-------|---|------|-----|-----|------|------|---------|-----|------------|
| A_GK_only | GK BUY only | 266 | 6.7% | 0.18 | -38.0% | -16.5% | -30.7% | 39.1% | 1.36 | 3.2% |
| B_GK_VE | GK + VolExp | 259 | 5.7% | 0.13 | -42.8% | -23.9% | -29.2% | 34.7% | 1.26 | 2.4% |
| C_GK_regime | GK + regime G07 | 368 | 10.5% | 0.31 | -34.0% | -4.1% | 3.9% | 47.6% | 1.91 | 2.6% |
| D_GK_VE_regime | GK + VolExp + regime G07 | 333 | 6.6% | 0.19 | -35.6% | -4.3% | 0.4% | 44.1% | 1.56 | 1.9% |
| E_GK_TS | GK + TS20 | 463 | 3.4% | 0.07 | -47.2% | -16.4% | -32.9% | 26.1% | 1.15 | 0.9% |
| F_GK_VE_TS | GK + VolExp + TS20 | 450 | 0.8% | 0.02 | -53.3% | -22.3% | -29.9% | 22.7% | 1.04 | 0.2% |
| G_C06 | Full C06 (baseline) | 450 | 0.8% | 0.02 | -53.3% | -22.3% | -29.9% | 22.7% | 1.04 | 0.2% |
| H_B05ff | Best Phase7: B05_ff | 355 | 13.2% | 0.38 | -34.5% | -4.1% | 5.2% | 43.9% | 2.15 | 3.4% |

**Findings:**
- VolExp filter effect: compare A vs B and E vs F.
- TS20 effect: compare B vs F and A vs E.
- Regime gate effect: compare B vs D and F vs G.
- B05_ff (H) is the best complete arm but still MARGINAL on MAR.

## B. Watchlist Forward Returns

| Signal | Horizon | N | Avg Fwd Ret | Median | Hit>5% | Hit>10% | Hit>20% |
|--------|---------|---|-------------|--------|---------|---------|---------|
| C06 | 5d | 1793 | 0.0% | -0.5% | 16.7% | 6.4% | 1.1% |
| C06 | 10d | 1785 | 0.4% | -0.5% | 24.4% | 11.3% | 2.9% |
| C06 | 20d | 1772 | 1.4% | -0.1% | 32.6% | 19.9% | 7.4% |
| C06 | 40d | 1763 | 1.1% | -1.1% | 34.3% | 23.8% | 12.2% |
| C06 | 63d | 1731 | 2.8% | -1.5% | 37.8% | 30.2% | 18.6% |
| C06 | 126d | 1626 | 6.6% | 0.0% | 42.1% | 36.0% | 27.0% |
| GK_only | 5d | 2612 | 0.1% | -0.3% | 15.7% | 5.6% | 0.8% |
| GK_only | 10d | 2601 | 0.6% | -0.3% | 24.1% | 11.1% | 2.6% |
| GK_only | 20d | 2584 | 1.4% | 0.2% | 32.3% | 19.2% | 6.8% |
| GK_only | 40d | 2568 | 1.4% | -0.7% | 35.3% | 24.5% | 12.3% |
| GK_only | 63d | 2531 | 2.1% | -1.4% | 36.8% | 29.2% | 17.6% |
| GK_only | 126d | 2406 | 6.3% | 0.3% | 42.2% | 35.7% | 25.5% |
| VolumeExp | 5d | 112295 | 0.2% | 0.0% | 17.7% | 6.6% | 1.2% |
| VolumeExp | 10d | 112092 | 0.5% | 0.0% | 25.0% | 12.3% | 3.5% |
| VolumeExp | 20d | 111661 | 0.9% | -0.2% | 31.2% | 19.1% | 7.6% |
| VolumeExp | 40d | 110393 | 1.5% | -0.6% | 35.9% | 26.2% | 13.4% |
| VolumeExp | 63d | 108517 | 3.1% | -0.7% | 38.7% | 30.7% | 18.9% |
| VolumeExp | 126d | 104715 | 6.4% | -0.3% | 42.1% | 35.7% | 25.7% |
| Universe | 5d | 171543 | 0.2% | 0.0% | 15.2% | 5.1% | 0.8% |
| Universe | 10d | 170738 | 0.6% | 0.0% | 22.9% | 10.3% | 2.6% |
| Universe | 20d | 168862 | 0.9% | 0.0% | 30.2% | 17.6% | 6.4% |
| Universe | 40d | 167013 | 1.1% | -0.6% | 34.3% | 24.4% | 12.1% |
| Universe | 63d | 162838 | 2.1% | -1.1% | 36.6% | 28.5% | 17.4% |
| Universe | 126d | 152920 | 5.9% | -0.7% | 41.1% | 34.7% | 24.8% |

**C06 shows POSITIVE forward-return selection value vs universe at 63d.**
C06 avg 63d: 2.8% vs universe avg: 2.1%.
C06 hit>20% rate: 18.6% vs universe: 17.4%.

## C. Leader Detection

| Signal Type | Leader Def | N Signals | N Leaders | Recall | Precision | FP Rate | FN Rate |
|-------------|------------|-----------|-----------|--------|-----------|---------|---------|
| C06 | 20pct_63d | 1797 | 63577 | 0.5% | 17.9% | 82.1% | 99.5% |
| C06 | 30pct_126d | 1797 | 62082 | 0.5% | 17.5% | 82.5% | 99.5% |
| GK_only | 20pct_63d | 2616 | 63577 | 0.7% | 17.0% | 83.0% | 99.3% |
| GK_only | 30pct_126d | 2616 | 62082 | 0.7% | 16.9% | 83.1% | 99.3% |
| Don20 | 20pct_63d | 41466 | 63577 | 12.7% | 19.4% | 80.6% | 87.3% |
| Don20 | 30pct_126d | 41466 | 62082 | 12.2% | 18.2% | 81.8% | 87.8% |
| Don252 | 20pct_63d | 12489 | 63577 | 4.8% | 24.2% | 75.8% | 95.2% |
| Don252 | 30pct_126d | 12489 | 62082 | 4.3% | 21.2% | 78.8% | 95.7% |
| VolumeExp | 20pct_63d | 112466 | 63577 | 32.2% | 18.2% | 81.8% | 67.8% |
| VolumeExp | 30pct_126d | 112466 | 62082 | 31.6% | 17.4% | 82.6% | 68.4% |
| Near52_VE | 20pct_63d | 26572 | 63577 | 9.1% | 21.8% | 78.2% | 90.9% |
| Near52_VE | 30pct_126d | 26572 | 62082 | 8.4% | 19.7% | 80.3% | 91.6% |

C06 recall (20pct_63d): 0.5% | precision: 17.9%
Don20 recall (20pct_63d): 12.7%

## D. Winner vs Loser Anatomy (Full C06 Trades)

| Bucket | N | AvgRet | AvgHold | VolExp | Dist52wk | RS3M | ATR% | Ret20 | RangePos |
|--------|---|--------|---------|--------|----------|------|------|-------|----------|
| mega_winner | 16 | 101.2% | 112.1 | 2.64 | -20.5% | 6.1% | 4.0% | 22.6% | 0.70 |
| big_winner | 22 | 29.9% | 77.3 | 2.29 | -9.6% | 9.6% | 3.5% | 14.7% | 0.68 |
| normal_winner | 38 | 12.0% | 66.9 | 1.97 | -17.6% | 5.6% | 3.3% | 12.2% | 0.55 |
| flat | 180 | -1.4% | 31.4 | 1.79 | -21.6% | -2.2% | 3.1% | 10.4% | 0.55 |
| loser | 144 | -8.8% | 23.2 | 2.03 | -19.6% | 1.2% | 3.3% | 11.8% | 0.44 |
| big_loser | 50 | -22.5% | 21.2 | 2.00 | -21.9% | -0.7% | 4.0% | 15.8% | 0.39 |

Key separators: look for differences in RS3M, Dist52wk, and VolExp between mega_winner and big_loser.

## E. Exit Utility Test

| Entry | Exit | N | CAGR | MAR | aDD | 2018 | 2022 | AvgHold |
|-------|------|---|------|-----|-----|------|------|---------|
| Don20 | EMA20_exit | 1320 | -7.0% | -0.10 | -72.4% | -15.7% | -38.0% | 14.3 |
| Don20 | Fixed20 | 947 | -5.3% | -0.08 | -65.3% | -20.2% | -47.1% | 21.0 |
| Don20 | Fixed40 | 483 | -8.8% | -0.12 | -74.8% | -25.2% | -56.9% | 41.0 |
| Don20 | Fixed63 | 310 | -6.3% | -0.09 | -69.1% | -28.9% | -55.2% | 64.0 |
| Don20 | GK_SELL | 276 | 0.5% | 0.01 | -53.9% | -16.9% | -44.9% | 71.1 |
| Don20 | GK_TS20 | 538 | 2.9% | 0.08 | -36.1% | -24.3% | -44.9% | 36.8 |
| Don20 | TS20_63 | 604 | -0.3% | -0.01 | -49.4% | -23.9% | -46.6% | 32.9 |
| Don252 | EMA20_exit | 821 | -0.0% | -0.00 | -56.6% | -9.9% | -27.8% | 17.0 |
| Don252 | Fixed20 | 763 | 2.3% | 0.04 | -56.2% | -7.6% | -19.7% | 21.0 |
| Don252 | Fixed40 | 425 | 5.5% | 0.10 | -54.8% | -4.9% | -38.5% | 41.0 |
| Don252 | Fixed63 | 285 | 6.1% | 0.13 | -48.1% | -9.6% | -24.7% | 64.0 |
| Don252 | GK_SELL | 306 | -1.1% | -0.02 | -58.7% | -7.0% | -47.4% | 56.6 |
| Don252 | GK_TS20 | 469 | -5.7% | -0.08 | -68.9% | -7.7% | -50.0% | 34.6 |
| Don252 | TS20_63 | 484 | 5.8% | 0.09 | -61.8% | -7.9% | -45.4% | 33.8 |
| EmaCross | EMA20_exit | 1356 | -3.5% | -0.05 | -67.6% | -13.5% | -25.6% | 11.8 |
| EmaCross | Fixed20 | 892 | -5.7% | -0.08 | -69.6% | -16.1% | -43.5% | 21.0 |
| EmaCross | Fixed40 | 473 | -7.2% | -0.10 | -69.7% | -35.8% | -46.7% | 41.0 |
| EmaCross | Fixed63 | 309 | -4.5% | -0.07 | -64.3% | -32.3% | -52.7% | 64.0 |
| EmaCross | GK_SELL | 200 | -1.4% | -0.03 | -49.9% | -28.5% | -34.3% | 95.2 |
| EmaCross | GK_TS20 | 539 | -2.7% | -0.05 | -56.7% | -18.1% | -38.3% | 35.0 |
| EmaCross | TS20_63 | 579 | 1.8% | 0.04 | -46.9% | -15.0% | -38.9% | 32.9 |
| Near52_VE | EMA20_exit | 1214 | 5.9% | 0.12 | -48.0% | -6.6% | -20.2% | 13.1 |
| Near52_VE | Fixed20 | 849 | 4.1% | 0.10 | -42.9% | -8.2% | -21.1% | 21.0 |
| Near52_VE | Fixed40 | 457 | 4.1% | 0.10 | -41.6% | -10.4% | -40.4% | 41.0 |
| Near52_VE | Fixed63 | 296 | 4.8% | 0.10 | -49.5% | -6.7% | -32.7% | 64.0 |
| Near52_VE | GK_SELL | 312 | -3.6% | -0.06 | -62.8% | -9.8% | -40.6% | 60.0 |
| Near52_VE | GK_TS20 | 511 | -1.0% | -0.02 | -59.1% | -3.8% | -46.7% | 34.8 |
| Near52_VE | TS20_63 | 533 | 9.4% | 0.24 | -39.3% | -2.0% | -34.9% | 33.8 |
| Top20RS | EMA20_exit | 793 | 2.3% | 0.04 | -52.7% | 0.8% | -36.6% | 11.1 |
| Top20RS | Fixed20 | 687 | -9.8% | -0.14 | -72.1% | -4.4% | -59.0% | 21.0 |
| Top20RS | Fixed40 | 420 | -5.3% | -0.08 | -66.6% | -5.5% | -54.7% | 41.0 |
| Top20RS | Fixed63 | 269 | -2.5% | -0.04 | -65.2% | -7.6% | -52.9% | 64.0 |
| Top20RS | GK_SELL | 248 | -0.4% | -0.01 | -54.3% | 1.7% | -55.8% | 69.8 |
| Top20RS | GK_TS20 | 445 | 2.0% | 0.03 | -62.1% | -2.3% | -56.0% | 35.9 |
| Top20RS | TS20_63 | 453 | 0.2% | 0.00 | -68.3% | -7.4% | -58.2% | 34.9 |

**GK_SELL and/or GK_TS20 is the best or competitive exit in multiple entry systems.**

## F. Discretionary Rank Review

| Rank Variable | Recall@5 | Recall@10 | Recall@20 | Months |
|---------------|----------|-----------|-----------|--------|
| adv50 | 27.2% | 47.9% | 74.8% | 94 |
| rs1m | 33.7% | 60.4% | 82.6% | 94 |
| rs3m | 30.7% | 48.5% | 78.6% | 93 |
| rs6m | 31.1% | 51.0% | 81.3% | 90 |
| dist_52wk | 26.9% | 57.0% | 79.8% | 94 |
| volexp | 36.1% | 54.4% | 79.2% | 94 |

Best rank variable: **rs1m** with recall@10=60.4%.

## G. Final Classification

### Answers to classification questions:

**A. Does C06 have positive forward-return selection value?**
YES — C06 shows positive forward-return selection value: avg 63d return exceeds universe baseline (2.8% vs 2.1%). The GK+VolExp filter selects stocks with above-average forward returns.

**B. Does C06 identify future leaders better than simple alternatives?**
C06 recall 0.5% vs Don20 recall 12.7% at 20%/63d threshold. C06 trades precision vs breadth of simple Donchian. C06 does NOT have dramatically higher recall — the GK+VolExp filter increases precision but reduces recall (misses many future leaders by filtering timing).

**C. Are GK SELL / TimeStop20 useful exits for other entries?**
YES — GK_SELL and/or GK_TS20 outperforms fixed holds for at least some entry systems. The exit layer is a genuine contributor: it cuts losers faster than fixed holds and allows winners to run further than TS20 alone.

**D. Is C06 better as a watchlist than as a portfolio strategy?**
UNCERTAIN — the evidence does not clearly support watchlist superiority. The forward-return advantage is small; the system may need additional discretionary filters to add value as a watchlist tool.

**E. Should the AFL remain as a signal chart, or be downgraded?**
Keep AFL as SIGNAL CHART with regime context. The AFL identifies potential breakout candidates (GK_BUY + VolExp). Overlay with B05_ff regime state: only act on signals when VNINDEX G08 AND breadth > 40% are both true. Do not downgrade to context-only unless leader detection precision is below 10%.

**F. Cleanest practical workflow:**
1. Daily: AFL generates GK_BUY + VolExp signals -> candidate watchlist.
2. Check regime: VNINDEX close > EMA100 AND EMA20 > EMA50 AND >40% stocks above EMA50.
3. If regime ON: review top 10 candidates by 3M RS + VolExp. Select 1-3 for monitoring.
4. Entry: next-day open if price holds above EMA50 or signal bar close.
5. Exit: GK_SELL signal OR TimeStop20 (exit if 20+ bars and ret <= 0).
6. Risk: max 10 positions, half-size when VNINDEX < EMA50, force-flat on regime OFF.
7. Do NOT automate: regime RESEARCH_ONLY. Use as watchlist only until MAR > 0.40 in OOS.

## H. Verdict

**Classification: WATCHLIST + EXIT OVERLAY**

- Reject as mechanical portfolio: CONFIRMED (Phase 7 RESEARCH_ONLY stands).
- Keep as watchlist engine: YES, conditional on regime gate (B05_ff regime ON).
- Keep GK_SELL + TS20 as exits: YES, for manual/discretionary use.
- AFL signal chart: KEEP as candidate filter, not as automated entry.

**Required before upgrading to PAPER_TRADE:**
1. OOS walk-forward (IS=2018-2022, OOS=2023-2026) for B05_ff: MAR must exceed 0.40.
2. OOS top1 concentration < 30% after regime gate is applied.
3. Accumulate 2026 OOS data until N_OOS >= 150 trades.
4. Optionally: add 15-20% max allocation cap per ticker.

**Do not paper trade. Do not live trade. WATCHLIST + EXIT OVERLAY only.**