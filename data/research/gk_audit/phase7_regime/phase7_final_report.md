# Phase 7 Final Report — Market Regime Framework

Run date: 2026-05-05

---

## A. Facts

**Phase 6 baseline (2018-2026, C06 + SZ06 only):**
- CAGR: 0.5%  MAR: 0.01  aDD: -53.3%
- 2018: -22.3%  2022: -29.9%  N: 450
- SZ06 (half-size when VNINDEX < EMA50) is insufficient to protect against sustained bear markets.

**Evaluation thresholds:**
- Required: 2018 > -15%, 2022 > -15%, aDD > -30%, CAGR > 8%, MAR > 0.40, N >= 80
- Strong:   2018 > -10%, 2022 > -10%, aDD > -25%, CAGR > 10%, MAR > 0.50, top1 < 30%

**Key finding**: No arm met all required criteria. **Verdict: RESEARCH_ONLY.**
However, Phase 7 definitively identified what works: force-flat + hysteresis/breadth
reduces 2018 losses from -22% to -3% and 2022 losses from -30% to near zero or positive.
The remaining gap to CANDIDATE is the active MaxDD criterion (-30% threshold) and MAR (0.40).

---

## B. Best Stop-New-Entries Regime (Groups 1/5/6 stop-new-entries)

| Arm                  | CAGR    | MAR   | aDD     | 2018    | 2022    |     N | Verdict            |
|----------------------|---------|-------|---------|---------|---------|-------|----------------------|
| C06_SZ06_ONLY        | 0.5%    | 0.01  | -53.3%  | -22.3%  | -29.9%  |   450 | FAIL               |
| G09                  | 5.0%    | 0.14  | -36.7%  | -14.6%  | -15.4%  |   323 | FAIL               |
| G08                  | 5.8%    | 0.12  | -46.4%  | -13.3%  | -31.9%  |   304 | FAIL               |
| G12                  | 5.4%    | 0.11  | -47.3%  | -13.3%  | -31.9%  |   299 | FAIL               |
| G05                  | 4.9%    | 0.09  | -51.5%  | -12.3%  | -33.4%  |   318 | FAIL               |

**Best stop-new-entries gate: G09** (drawdown from 252d high < 15%).
- CAGR=5.0%, MAR=0.14, aDD=-36.7%, 2018=-14.6%, 2022=-15.4%
- Stop-new-entries is insufficient: existing positions continue to fall in bear markets.
- All G01-G12 stop-new-entries arms FAIL the required criteria.

**Why stop-new-entries fails:** When regime turns OFF, existing positions held through the
downturn continue losing. The gate only stops new losses from new entries. For sustained bear
markets (2018: 12 months, 2022: 12 months), the open positions from pre-bear entries absorb
the full drawdown before GK_SELL or TStop20 fires.

---

## C. Best Force-Flat Regime (Group 2)

| Arm                  | CAGR    | MAR   | aDD     | 2018    | 2022    |     N | Verdict            |
|----------------------|---------|-------|---------|---------|---------|-------|----------------------|
| C06_SZ06_ONLY        | 0.5%    | 0.01  | -53.3%  | -22.3%  | -29.9%  |   450 | FAIL               |
| F07                  | 8.3%    | 0.23  | -35.5%  | -4.3%   | 0.4%    |   386 | FAIL               |
| F01                  | 9.4%    | 0.22  | -41.9%  | -5.0%   | 3.9%    |   466 | FAIL               |
| F09                  | 6.3%    | 0.16  | -38.6%  | -9.9%   | -9.9%   |   328 | FAIL               |
| F08                  | 7.6%    | 0.15  | -51.0%  | -8.0%   | -17.1%  |   358 | FAIL               |
| F12                  | 7.1%    | 0.14  | -52.1%  | -8.0%   | -17.1%  |   349 | FAIL               |

**Best force-flat gate: F07** (exit all when VNINDEX EMA20 < EMA50 OR close < EMA50).
- Bear year performance dramatically improved vs stop-new-entries.
- F01 (close > EMA50) achieves CAGR=9.4% with 2022=+3.9%, but aDD=-41.9% fails.
- F07 (close > EMA50 AND EMA20 > EMA50): better aDD at -35.5% but still fails threshold.
- All standalone force-flat arms fail: the single-day regime switch causes whipsaw exits.

---

## D. Best Hysteresis Rule (Group 3 — force-flat + confirmation delay)

| Arm                  | CAGR    | MAR   | aDD     | 2018    | 2022    |     N | Verdict            |
|----------------------|---------|-------|---------|---------|---------|-------|----------------------|
| F07_H2 (G07+5d)      | 11.3%   | 0.36  | -31.7%  | -3.0%   | -1.9%   |   328 | MARGINAL           |
| F07_H3 (G07+10d)     | 8.7%    | 0.33  | -26.8%  | -3.1%   | 1.3%    |   257 | MARGINAL           |
| F09_H5 (G09+ret20>0) | 10.0%   | 0.29  | -34.1%  | -2.1%   | -4.0%   |   345 | MARGINAL           |
| F07_H5 (G07+ret20>0) | 8.4%    | 0.23  | -37.2%  | -4.7%   | -3.4%   |   372 | FAIL               |
| F07_H1 (G07+3d)      | 7.1%    | 0.16  | -43.8%  | -4.2%   | -1.2%   |   366 | FAIL               |

**Key finding: Hysteresis (5+ consecutive regime-ON days before re-entry) is the single most
effective improvement.** It prevents whipsaw exits and reduces false re-entries.

- **F07_H2** (G07 + require 5 consecutive days ON): CAGR=11.3%, aDD=-31.7%, 2018=-3.0%, 2022=-1.9%
  - Misses CANDIDATE by aDD (−31.7% vs threshold −30.0%) and MAR (0.36 vs 0.40)
- **F07_H3** (G07 + require 10 consecutive days ON): CAGR=8.7%, aDD=-26.8%, 2018=-3.1%, 2022=+1.3%
  - Passes aDD and bear years; misses MAR (0.33 vs 0.40) and CAGR is borderline
  - Trade-off: fewer trades (N=257) due to stricter re-entry gate

**Best hysteresis arm: F07_H2** (by MAR), **F07_H3** (by aDD safety).

---

## E. Best Two-Layer Regime (Group 4)

| Arm                  | CAGR    | MAR   | aDD     | 2018    | 2022    |     N | Verdict            |
|----------------------|---------|-------|---------|---------|---------|-------|----------------------|
| R04 (risk-on only)   | 8.3%    | 0.23  | -35.5%  | -4.3%   | 0.4%    |   386 | FAIL               |
| R03                  | 7.3%    | 0.14  | -52.4%  | -7.7%   | -18.7%  |   341 | FAIL               |
| R02                  | 0.9%    | 0.02  | -52.6%  | -7.5%   | -15.4%  |   400 | FAIL               |
| R01 (3-state sizing) | -3.0%   | -0.06 | -50.5%  | -15.2%  | -21.2%  |   340 | FAIL               |

**R04** (risk-on = G07, otherwise force-flat) = same as F07 — identical logic and results.
Three-state sizing (R01/R02: half-size in neutral zone) underperforms vs binary force-flat.
The neutral zone (VNINDEX between EMA50 and EMA100) allows entries that turn into bear losses.

---

## F. Breadth Filters — Key Insight (Group 5)

| Arm                  | CAGR    | MAR   | aDD     | 2018    | 2022    |     N | Verdict            |
|----------------------|---------|-------|---------|---------|---------|-------|----------------------|
| B05_ff (G08+B01 ff)  | 13.2%   | 0.38  | -34.5%  | -4.1%   | 5.2%    |   355 | MARGINAL           |
| B04_ff (rising brd)  | 12.2%   | 0.30  | -40.8%  | -1.7%   | 2.2%    |   669 | FAIL               |
| B01_ff (>40% EMA50)  | 8.4%    | 0.21  | -40.4%  | -3.3%   | 1.4%    |   447 | FAIL               |
| B02_ff (>50% EMA50)  | 7.0%    | 0.19  | -35.8%  | -1.9%   | 1.6%    |   353 | FAIL               |
| B03_ff (>40% EMA100) | 4.5%    | 0.09  | -52.3%  | -3.1%   | 6.9%    |   371 | FAIL               |

**B05_ff is the best single arm overall:** CAGR=13.2%, MAR=0.38, aDD=-34.5%, 2018=-4.1%, 2022=+5.2%.

B05_ff = VNINDEX close > EMA100 AND EMA20 > EMA50 (G08) PLUS > 40% of universe above EMA50 (B01), force-flat.

- Bear years handled: 2022=+5.2% (the broad market breadth correctly identified the 2022 bear).
- 2020 COVID: still captured (broad market breadth recovered quickly in April-June 2020).
- **Remaining gap:** aDD=-34.5% fails the -30% threshold. MAR=0.38 fails the 0.40 threshold.

**Why breadth adds value over pure VNINDEX gates:** The VNINDEX can be supported by a few
large-cap stocks while the broader market is weak. Breadth (% of universe above EMA50) detects
when the broad market has deteriorated — a better signal for system entry risk.

---

## G. Sector Filters (Group 6)

Sector filters (S01-S04 on G08 base) all FAIL: aDD remains -45% to -51%, and 2022 losses
of -29% to -32% are not meaningfully reduced. Adding a sector breadth condition on top of G08
does not add sufficient protection because G08 already handles the macro regime.
Sector filters add value only at the stock-selection level, not the regime level.

---

## H. 2018/2022 Bear Market Review — Best Arms

| Arm          | 2018    | 2022   | aDD     | MAR  | CAGR   |
|--------------|---------|--------|---------|------|--------|
| B04_ff       | -1.7%   | +2.2%  | -40.8%  | 0.30 | 12.2%  |
| B02_ff       | -1.9%   | +1.6%  | -35.8%  | 0.19 | 7.0%   |
| F09_H5       | -2.1%   | -4.0%  | -34.1%  | 0.29 | 10.0%  |
| F07_H2/H4    | -3.0%   | -1.9%  | -31.7%  | 0.36 | 11.3%  |
| F07_H3       | -3.1%   | +1.3%  | -26.8%  | 0.33 | 8.7%   |
| B05_ff       | -4.1%   | +5.2%  | -34.5%  | 0.38 | 13.2%  |
| Baseline     | -22.3%  | -29.9% | -53.3%  | 0.01 | 0.5%   |

The force-flat + hysteresis approach reduces 2018 losses from -22.3% to -1.7% to -4.1%
and 2022 losses from -29.9% to near zero or positive across the best arms.

The remaining active MaxDD reflects 2019 active underperformance: when VNINDEX recovered
after 2018 bear, regime-gated systems in cash missed the early recovery — generating
negative active returns vs the benchmark. This is structural in all force-flat approaches.

---

## I. OOS Concentration (2025+ OOS period)

OOS concentration analysis was not re-run for all 57 arms (too expensive). Key points:
- The OOS top-1 concentration problem (L40 = 50-95% of OOS PnL) is a SAMPLE SIZE issue.
- With N=78 OOS trades over 1.5 years (2025-2026), any high-return single stock dominates.
- Regime gates do not reduce OOS concentration — they may worsen it (fewer trades → same winners).
- Concentration is not resolvable by regime gating; requires accumulating more OOS time.

Recommendation: Re-run OOS walk-forward (IS=2018-2022, OOS=2023-2026) for B05_ff and F07_H2
to check whether the regime gate changes the OOS trade distribution.

---

## J. Production / Paper-Trade Decision

**VERDICT: RESEARCH_ONLY**

No arm met all required criteria. The closest candidates:

| Arm        | 2018  | 2022  | aDD    | CAGR  | MAR  | Gap to CANDIDATE                   |
|------------|-------|-------|--------|-------|------|------------------------------------|
| B05_ff     | -4.1% | +5.2% | -34.5% | 13.2% | 0.38 | aDD -4.5 ppts, MAR -0.02 short     |
| F07_H2     | -3.0% | -1.9% | -31.7% | 11.3% | 0.36 | aDD -1.7 ppts, MAR -0.04 short     |
| F07_H3     | -3.1% | +1.3% | -26.8% | 8.7%  | 0.33 | MAR -0.07 short (aDD passes)       |

**Phase 7 materially advances the research despite RESEARCH_ONLY verdict:**
- Bear year 2018: improved from -22.3% to -3.0% (best arms)
- Bear year 2022: improved from -29.9% to +5.2% (best arm B05_ff)
- Full-period CAGR: improved from 0.5% to 8.7-13.2%
- The system is viable in principle; the remaining gap is refinement, not fundamental design

**Required before upgrading to CANDIDATE:**
1. B05_ff or F07_H2 must pass OOS walk-forward test (IS=2018-2022, OOS=2023-2026)
2. OOS top1 concentration must be checked on regime-gated system
3. Active MaxDD gap (-30% threshold): either adjust the gate parameters or accept that
   the -34.5% of B05_ff is the best achievable with this system design

---

## K. Top 3 Risks

1. **Active MaxDD vs VNINDEX benchmark**: Force-flat systems underperform when in cash
   during market recoveries. The active MaxDD penalty comes from being flat when the market
   rallies (especially 2019, early 2020, post-2022 recovery). This is structural for any
   force-flat regime gate. The solution would require faster re-entry (less hysteresis)
   which increases whipsaw risk.

2. **2019 residual drawdown**: After the 2018 bear market, C06 with regime gates sat in
   cash while VNINDEX recovered, creating a sustained active drawdown through 2019 (-12.8%
   in baseline). The hysteresis (5-10 days) further delays re-entry. This contributes to
   the active MaxDD being worse than -30% for most arms.

3. **OOS concentration not resolved**: The 2025-2026 OOS period shows L40 dominating all
   variant results. Regime gates do not diversify the winning trades. The OOS concentration
   problem requires accumulating more OOS time or testing a position-size cap per ticker.

---

## L. Next Research Questions

1. **OOS walk-forward for B05_ff and F07_H2**: Run IS=2018-2022, OOS=2023-2026 on both.
   Does the regime gate improve OOS MAR from 0.16? Does L40 still dominate?

2. **Active MaxDD optimization**: The -30% aDD threshold is the binding constraint.
   Test whether a position-level stop (e.g. -12% hard stop per trade in addition to TS20)
   reduces the active drawdown without significantly hurting CAGR.

3. **Faster re-entry**: Test H1 (3 consecutive days) with a softer gate (G09: drawdown < 15%)
   for B05_ff. This may preserve more of the 2019 and post-2022 recovery without increasing
   2018/2022 losses.

4. **Top1 ticker cap**: Test a maximum 15-20% allocation cap per ticker (currently uncapped).
   If L40 is capped at 15%, does the OOS concentration problem improve?

5. **Phase 8 focus**: Combine B05_ff with a per-trade position cap and re-run OOS
   walk-forward. If OOS MAR > 0.40 and top1 < 30%, upgrade to CONDITIONAL_PAPER_TRADE.
