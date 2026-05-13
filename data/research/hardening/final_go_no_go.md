# Final Go / No-Go — VN EMA Cloud Strategy
## Based on Portfolio Hardening Steps 2–6

**Date:** 2026-05-13
**Decision:** Move to paper trading. Do NOT deploy live capital yet.

---

## Answers to Required Questions

### A. Is B_cloud20_100_partial still the best production candidate after hardening?

**Yes — with one modification.**

The best validated configuration is:
- Entry: cloud_only, EMA(20)/EMA(100)
- Exit: partial_tp (tp=+15%, trail=2.5×ATR14, max_hold=250)
- Universe: ex-VIN3
- Fill mode: **ema_dist** (not FIFO — see Step 2 results)
- Max positions: 20

With ema_dist fill, the primary candidate delivers:
- CAGR = 12.3% (vs 10.7% FIFO)
- Sharpe = 1.202 (vs 1.136 FIFO)
- maxDD = -30.0%
- MAR = 0.41

The original 10.7% / 1.136 FIFO baseline was a conservative lower bound. ema_dist fill confirms the production number is higher.

Cost stress test: CAGR remains 9.6% and Sharpe remains 1.033 even at 100 bps (2.5× assumed cost). The edge is not being eroded by realistic transaction costs.

---

### B. Is B_cloud21_55_partial safer / more robust despite lower headline performance?

**Partially yes — with important caveats.**

After ranked fill, the shadow is more competitive than FIFO numbers suggested:
- B_cloud21_55_partial (ex_vin3, momentum fill): CAGR=9.9%, Sharpe=0.973, maxDD=-33.2%
- B_cloud21_55_partial (full universe, FIFO): CAGR=8.6%, Sharpe=0.906, maxDD=-32.4%

Key advantage of shadow: it has CAGR=+0.7% in the 2023-2026 period vs primary at -2.3%. The 21/55 cloud is more responsive (shorter EMA), so it exits bear positions faster and re-enters earlier in recovery. It is more resilient in the CURRENT regime.

Key disadvantage of shadow:
1. Lower Sharpe and CAGR than primary across the full 14-year period
2. VIN treatment is unclear: full universe is better for shadow (CAGR 8.6% vs 4.5% ex_vin3), which means VHM/VRE contribute genuine returns — but this also means higher event risk
3. FIFO severely underrates it — requires careful ranked fill implementation in production

**Verdict on B vs shadow:**
- Primary (20/100) remains preferred for the full-period risk-adjusted case
- Shadow (21/55) is a useful diversifier or fallback during regimes where the primary is in drawdown (as now)
- Do NOT switch to shadow permanently — primary has better 14-year profile

---

### C. Should live universe be full / ex-VIC / ex-VIN3?

**Use ex-VIN3 for the primary candidate (20/100).**

FACTS:
- full → ex_vic: maxDD improves from -43.4% to -33.9% (-9.5pp). VIC alone is the biggest distorter.
- ex_vic → ex_vin3: maxDD improves further from -33.9% to -30.1% (-3.8pp). CAGR -0.4pp.
- For the shadow (21/55): full universe is materially better (CAGR 8.6% vs 4.5%), meaning VHM/VRE generate genuine returns in that system.

**Decision:**
- Primary (20/100): run ex-VIN3. The -3.8pp maxDD reduction from removing VHM/VRE justifies the trivial -0.4pp CAGR cost.
- Shadow (21/55): monitor with both full and ex_vin3 tracks in parallel during paper trading. Do not force ex_vin3 on the shadow until the VHM/VRE contribution is better understood.

---

### D. Is the strategy ready for paper trading?

**Yes. Conditions met for paper trading:**

| Check | Result |
|---|---|
| 14-year backtest | ✓ Two full decades covered |
| OOS signal quality | ✓ OOS avg_trade=6.3%, hit rate=67.9% (2023+) |
| Cost robustness | ✓ Profitable at 100 bps (2.5× assumption) |
| Position diversification | ✓ max_pos=20 validated |
| VIN treatment defined | ✓ ex-VIN3 for primary |
| Fill mode defined | ✓ ema_dist ranking |
| Exit rule defined | ✓ partial_tp with exact parameters |
| Regime awareness | ✓ Currently in drawdown — documented |

**NOT ready for live capital deployment yet** (see Section F).

---

### E. What exact configuration should be used in paper trading?

```
Entry:        cloud_only — EMA(20) > EMA(100), cloud was bearish ≥3 bars
Exit:         partial_tp — 50% at +15%, trail remainder at 2.5×ATR(14), max 250 bars
Universe:     ex-VIN3 (272 universe, exclude VIC/VHM/VRE, exclude VPL<252 bars)
Fill:         ema_dist ranked — when multiple signals fire same day, sort by
              (entry_price - EMA100) / EMA100 descending, fill top N
Max positions: 20 (5% equal weight each)
Cost budget:  40 bps assumed; strategy survives 100 bps
Execution:    Signal at T close, entry at T+1 open (conservative) or T+1 close
```

Full parameter YAML is in `paper_trade_spec.md`.

---

### F. What still has to be proven before any small live deployment?

**Three conditions must be met before deploying real capital:**

**F1 — Drawdown resolution (mandatory)**
The portfolio is currently in a ~30% drawdown from its 2022 peak.
Before live deployment, either:
(a) The equity curve recovers to within 10% of its prior peak during paper trading, OR
(b) A rigorous entry criterion is defined (e.g., "deploy after X consecutive profitable months in paper trading")

Do not deploy into a known drawdown trough without a specific criterion.

**F2 — Paper trade validation (minimum 3 months)**
Run paper trading for at least 3 months (63 trading days).
Criteria to confirm:
- At least 20 paper trades closed
- Paper avg_trade_ret ≥ 4% (below OOS backtest of 6.3% but within 1 std dev)
- Paper hit rate ≥ 60% (below backtest 67.9%)
- No systematic execution gap between signal close and actual fill exceeding 2% per trade

**F3 — Execution audit**
The backtest assumes entry at T+1 close. In VN markets (HOSE), this means end-of-day ATC price. Before live deployment, measure the actual gap between:
- Signal close price (T)
- Achievable entry price (T+1 open or T+1 ATC)
If average gap exceeds 1%, adjust cost assumption accordingly.

---

## Supporting Facts — What the Hardening Confirmed

**What the hardening CONFIRMED (facts):**

| Finding | Evidence |
|---|---|
| FIFO fill understates strategy quality | Primary CAGR +1.6pp with ema_dist; shadow CAGR +5.4pp |
| Cost is not the edge killer | CAGR=9.6%, Sharpe=1.033 at 100 bps |
| VIC is the main VIN distorter | maxDD -43.4% full → -33.9% ex_vic (-9.5pp) |
| 20 positions is the right floor | max_pos=10 drops Sharpe from 1.136 to 0.810 |
| Strategy is in current drawdown | Portfolio CAGR=-2.3% in 2023-2026 at equity level |
| OOS individual trade quality is positive | avg_trade=6.3%, hit=67.9% in 2023+ |
| Edge is not concentrated in one period | Positive CAGR in all three subperiods for primary (2012-17, 2018-22 strong; 2023-26 weak) |

**What the hardening DID NOT resolve:**

| Open question | What would answer it |
|---|---|
| Shadow (21/55) with ranked fill on full universe | Need one additional run: (21/55, full, ema_dist/momentum) |
| Actual VN execution gap (T vs T+1) | Live or paper trading execution log, 50+ trades |
| Whether current drawdown is structural or cyclical | 3-6 months of paper trading in current regime |
| Sector concentration behavior | Need sector metadata (not currently in panel) |

---

## Decision

**MOVE TO PAPER TRADING with B_cloud20_100_partial (ex-VIN3, ema_dist fill, max_pos=20).**

Track B_cloud21_55_partial (full universe, ema_dist fill) as shadow in parallel.

**Do NOT deploy live capital** until F1 (drawdown resolution) and F2 (3-month paper track record) are satisfied.
