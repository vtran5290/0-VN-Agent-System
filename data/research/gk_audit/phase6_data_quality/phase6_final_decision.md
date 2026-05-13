# Phase 6 Final Decision Report

Generated: 2026-05-04

---

## A. Did Adjusted Data Materially Change C06?

| Metric | Raw | Adjusted | Change |
|--------|-----|----------|--------|
| CAGR | 22.0% | 26.5% | +4.5 ppts |
| MAR | 0.73 | 1.02 | +0.29 |
| Active MaxDD | -27.3% | -26.7% | +0.6 ppts |
| ex-top3 CAGR | 12.5% | 12.6% | +0.1 ppts |
| top1 ticker | 19.5% | 26.6% | +7.1 ppts |
| CA watchlist PnL | 40.1% | 14.2% | -25.9 ppts |
| 2024 return | +2.1% | +6.7% | +4.6 ppts |

**CAGR change on adjusted data: +4.5 ppts (adjusted is BETTER than raw)**
Threshold: drop > 5 ppts = contamination flag.
Verdict: NOT CONTAMINATED — CA adjustment improved performance, not degraded it.

**Interpretation:** The 2024-01-30 CA cluster (VIC -50%, MCH -50%, L40 -67%) was distorting GK
signals negatively in raw data. Backward-adjusted prices remove these distortions. CA-watchlist
contribution to full-period PnL dropped from 40.1% to 14.2% after adjustment — the raw-data edge
was NOT driven by CA events, but CA data was noisy enough to hurt returns.

---

## B. Is the OOS Top-1 Winner (L40) Legitimate?

L40 OOS trade: 2025-09-03 → 2025-12-02, open entry 35.80 → open exit 90.00 = +150.5% raw

**Finding: L40's return is LEGITIMATE but represents EXTREME concentration risk.**

- CA event (L40 -66.8%) occurred on 2024-01-30 — 16+ months before trade entry
- The Sep-Dec 2025 trade was entered at clean post-CA market prices
- L40 had a genuine speculative breakout: price went from 35 → 90 (exit) → 117 (peak 2025-10-17)
- No CA event occurred during the 90-day holding period
- However: 1 trade = 63.1% of OOS PnL (raw), 47.8% on adjusted basis — not a system edge

On adjusted data, L40's return is preserved (adjustment only affects pre-2024-01-30 prices).
The OOS trade itself is unaffected by the CA adjustment.

See oos_top1_ticker_review.md for full analysis.

---

## C. Does C06 Survive Excluding L40 / CA Tickers?

| OOS Test | N | MAR | aDD | top1_pct | Verdict |
|----------|---|-----|-----|----------|---------|
| E1 raw full OOS | 78 | 0.87 | -23.0% | 50.1% | ref |
| E2 raw excl L40 | 79 | 0.47 | -25.5% | 51.7% | MARGINAL |
| E3 raw excl top3 (L40,NVL,SMC) | 79 | 0.34 | -26.7% | 69.3% | FAIL |
| E4 raw excl CA watchlist | 80 | 0.30 | -25.5% | 99.7% | FAIL |
| E5 adj full OOS | 78 | 1.62 | -25.1% | 47.8% | ref |
| E6 adj excl L40 | 80 | 0.73 | -27.5% | 84.1% | PASS MAR, FAIL top1 |
| E7 adj excl CA watchlist | 78 | 0.89 | -25.0% | 90.4% | PASS MAR, FAIL top1 |

**Key finding:** After excluding L40 on raw data (E2), top1 = 51.7% (NVL now leads with 31.3% of PnL).
The concentration problem is NOT specific to L40 — the OOS sample is too small for diversified edge.

On adjusted data excluding L40 (E6), MAR = 0.73 passes, but top1 = 84.1% still fails concentration.
After CA adjustment, a different non-CA ticker drives OOS results.

**Conclusion:** C06 has marginal OOS edge when L40 is excluded (MAR 0.47 raw, 0.73 adj), but the
top1-ticker criterion (< 30%) fails in every scenario tested. The system's OOS "success" is
concentrated in 1-2 high-return trades in a small 78-trade sample, not distributed systematic edge.

---

## D. Does C06 Survive 2018/2022?

**TESTED — 2018-2022 data fetched from FireAnt API (259/272 symbols with history).**

Full panel: 2018-01-02 to 2026-04-29, 271 symbols, 510K rows.

### D1. C06 Full Backtest 2018-2026

| Metric | Value |
|--------|-------|
| N trades | 450 |
| CAGR | 0.5% |
| MAR | 0.01 |
| Active MaxDD | -53.3% |
| top1 ticker | 330.9% (negative total PnL, 1 winner skews) |

**Yearly returns:**

| Year | C06 Return | Context |
|------|-----------|---------|
| 2018 | -22.3% | VNINDEX -30% bear |
| 2019 | -12.8% | — |
| 2020 | +40.7% | COVID crash + recovery |
| 2021 | +21.2% | Bull market |
| 2022 | -29.9% | VNINDEX -35% bear |
| 2023 | -16.5% | (residual from 2022 drawdown) |
| 2024 | +3.9% | |
| 2025 | +51.8% | |
| 2026 | -7.0% | |

**Bear period isolation:**
- 2018 (bear): CAGR -18.6%, aDD -24.2% → **FAIL**
- 2020 (COVID): CAGR +42.6%, aDD -8.2% → PASS (recovery beneficiary)
- 2022 (bear): CAGR -27.2%, aDD -20.3% → **FAIL**

### D2. Walk-Forward: IS=2018-2022, OOS=2023-2026

| Metric | Value |
|--------|-------|
| OOS N trades | 182 |
| OOS CAGR | 6.0% |
| OOS MAR | 0.16 |
| OOS active MaxDD | -37.7% |
| OOS top1 ticker | 95.1% (L40) |

**OOS top-5 contributors:** L40 (95%), VGI (90%), SMC (53%), CEO (41%), MCH (39%)

**Verdict: FAIL** — C06 trained on 2018-2022 produces MAR=0.16 in OOS (2023-2026). The 2018 and
2022 bear markets inflict large losses that the 2019/2021 gains cannot recover. The SZ06 half-size
regime filter reduces exposure but does not prevent sustained drawdowns when GK signals fire into
downtrending stocks during broad market selloffs.

**Key insight:** The 2023-2026 backtest period (used in Phases 1-5) was a bull-recovery period.
It started after the 2022 bottom, giving C06 ideal conditions. C06 is a momentum system — it
performs when stocks trend up and GK signals lead sustained breakouts. In bear markets, breakouts
fail and the system suffers repeated small entries that quickly stop out, accumulating fees and
slippage losses.

**Conclusion:** C06 requires a regime filter stronger than SZ06 (half-size when VNINDEX < EMA50)
to survive bear markets. The full 2018-2026 CAGR of 0.5% with aDD -53.3% confirms the system
is NOT suitable for live deployment without significant bear-market protection.

---

## E. TimeStop20 Robustness on Adjusted Data

| Window | Raw MAR | Adjusted MAR | Change |
|--------|---------|--------------|--------|
| 15b, 0% threshold | 0.43 | 1.04 | +0.61 |
| 20b, 0% threshold | 0.73 | 1.02 | +0.29 |
| 25b, 0% threshold | 0.75 | 0.92 | +0.17 |
| 30b, 0% threshold | 0.52 | 1.28 | +0.76 |

**TimeStop robustness on adjusted data: ROBUST — all bar windows pass MAR > 0.55**

The 15-bar fragility identified in Phase 5 (raw MAR=0.43) disappears entirely on adjusted data
(adj MAR=1.04). The CA distortions from the 2024-01-30 cluster were creating spurious signals
that particularly hurt short-hold trades. On clean adjusted prices, the exit timing is more robust.

---

## F. Final Decision

**VERDICT: RESEARCH_ONLY**

Checklist:
  ✅ Adjusted-data C06 MAR >= 0.50: 1.02
  ✅ CA contamination check (CAGR drop < 5 ppts): adjusted CAGR is +4.5 ppts BETTER
  ✅ CA watchlist PnL contribution < 30%: 14.2% (on adjusted data)
  ✅ TimeStop robust on adjusted data (all bar windows): YES
  ❌ OOS top1 ticker contribution < 30%: 47.8% (adj full OOS), 50.1% (raw)
  ❌ OOS ex-L40 top1 ticker < 30%: 84.1% (adj), 51.7% (raw) — next winner takes over
  ❌ 2018 bear year return > -20%: -22.3% (FAIL)
  ❌ 2022 bear year return > -20%: -29.9% (FAIL)
  ❌ Full 2018-2026 MAR acceptable: 0.01 (FAIL — near breakeven over 8+ years)

**Primary reason for RESEARCH_ONLY:** C06 fails both bear market years decisively.
Full 2018-2026 backtest: CAGR 0.5%, active MaxDD -53.3%. The system is profitable only
in the 2023-2026 bull-recovery window. This is a STRUCTURAL problem, not a data quality issue.

**Secondary reason:** OOS concentration — top1 >= 47% in all OOS scenarios.

Resolved (no longer blockers):
- CA data contamination: CLEARED (adj CAGR improved)
- TimeStop fragility at 15b: CLEARED (adj MAR=1.04)

---

## G. Required Actions Before Paper Trade

1. **Bear market regime filter (BLOCKER)** — C06 loses -22% in 2018 and -30% in 2022.
   SZ06 (half-size when VNINDEX < EMA50) is insufficient. Required: a stronger regime gate
   that moves to FLAT (0 position) or very small (0.25x) in sustained bear markets.
   Options to research (Phase 7):
   - VNINDEX 52-week low regime: no new entries when VNINDEX is within X% of 52wk low
   - Trend filter: no entries when VNINDEX EMA20 < EMA50 AND VNINDEX < prior-month close
   - Kill switch: stop all entries when 3-month rolling loss exceeds 10%

2. **OOS concentration (BLOCKER)** — wait until OOS N >= 150 trades before re-evaluating.
   With N=78 over ~1.5 years (2025-2026), the sample is not large enough to confirm diversified edge.
   Re-assess after 2026 Q4 data is available.

3. **Official CA data** — obtain HOSE/HNX corporate action announcements for CA-watchlist
   tickers and verify backward-adjustment factors match official records. Not a blocker since
   CA contamination check passed, but important before live deployment.

4. **Live signal validation** — run GK signal generator (Python) for 3 months without capital,
   comparing output against AmiBroker AFL chart. Validate entry/exit timing at bar t+1 open.

---

## H. Top 3 Risks Remaining

1. **Bear market performance is structurally bad**: C06 loses 22-30% in both 2018 and 2022.
   The system is a momentum strategy with no structural protection against multi-month bear markets.
   SZ06 (half-size) is not sufficient. This is NOT fixable by parameter tuning — it requires a
   fundamentally different regime gate or a separate bear-market overlay.

2. **OOS concentration not resolved**: Even with CA-clean adjusted data, the top-1 ticker
   contributes 47-95% of OOS PnL in every scenario tested. With 78 trades over 1.5 OOS years,
   the sample is too small to confirm diversified edge. Wait for N >= 150 OOS trades.

3. **Bull-period overfitting risk**: All Phase 1-5 optimization was done on 2023-2026, which
   is a post-bottom recovery period. C06's full 2018-2026 CAGR of 0.5% vs 22% on 2023-2026 alone
   shows the system is highly regime-dependent. Parameters tuned on the bull recovery may not
   generalize to the next bear cycle.
