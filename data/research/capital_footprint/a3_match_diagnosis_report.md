# A3 Match Diagnosis Report

**Date:** 2026-05-30
**Status:** DIAGNOSIS COMPLETE — No production change. Research only.

---

## Question

Why does the Capital Footprint / A3 join produce only 4.2% match rate (9,012 of 215,638 A3 rows)?

---

## Facts

### Data Sources

| Panel | Rows | Symbols | Dates |
|---|---|---|---|
| A3 (institutional_accumulation panel_scores.parquet) | 215,638 | 1,562 | 468 (weekly, mostly Fridays) |
| CF Phase 2 panel (min_adv50=1e8 VND) | 376,331 | 366 | 2,071 (daily trading days) |
| CF full OHLCV (no filter) | 1,279,143 | 1,564 | all trading days |

### Match Breakdown

| Stage | Rows Lost | Rows Remaining | % of A3 total |
|---|---|---|---|
| A3 total | — | 215,638 | 100.0% |
| Non-CF symbol (adv50 filter excludes from CF) | 172,518 | 43,120 | 20.0% |
| CF symbol, date OUTSIDE CF date range for that symbol | 12,377 | 30,743 | 14.3% |
| CF symbol, date in range, but row filtered (per-day adv50 gap) | 21,731 | 9,012 | 4.2% |
| **Matched** | — | **9,012** | **4.2%** |

---

## Root Cause

**The 4.2% match rate is structural, not a bug.**

Three compounding filters reduce the match:

### 1. Universe Mismatch — 80.0% loss

CF research panel applies `adv50_vnd >= 100mn VND` per row. This limits CF to **366 liquid symbols**.
A3 scans the **full 1,562-symbol market** weekly, including stocks that rarely pass the 100mn VND daily threshold.

- A3 rows where symbol is NOT in CF: **172,518 (80.0%)**
- These stocks are too illiquid for the CF panel but valid A3 scan candidates.

### 2. Symbol Active Window Mismatch — 5.7% additional loss

Of 366 CF symbols, each symbol only appears in CF during periods when it passes the adv50 filter. A stock like BCG passed the CF threshold only during Oct–Nov 2023 (24 rows). But A3 scanned BCG continuously before and after that window.

- A3 rows with CF symbol, date before/after CF window for that symbol: **12,377**
- These are periods when the stock was scanned by A3 but was too illiquid for CF at the time.

### 3. Per-Row Adv50 Sparsity — 10.1% additional loss

Even within a CF symbol's active window, individual trading days can fall below the threshold. CF keeps rows only when `adv50_vnd >= 1e8` on that exact day. Some A3 Friday scans land on days when the symbol's 50-day ADV dropped below the threshold.

- A3 rows with CF symbol, date in range, specific (symbol, date) absent from CF: **21,731**

---

## Key Finding

All 189 A3 scan dates (Fridays) are present in CF's date set — there is **no date format or timezone mismatch**. No schema errors. No join logic bugs.

The issue is purely that:
- **A3 covers the full market** (1,562 symbols, including small-cap and low-liquidity stocks)
- **CF covers only the liquid subset** (366 symbols passing 100mn VND daily ADV threshold)

---

## Interpretation

| Question | Answer |
|---|---|
| Is this a bug? | **NO** — the join is correct |
| Is the low match rate fixable? | Partially — see options below |
| Are the 9,012 matched rows representative? | **NO** — they represent only the liquid end of A3 signals |
| Can we conclude about A3+CF synergy? | **NOT YET** — sample too small and biased toward high-liquidity stocks |

---

## Options to Improve Match Rate

| Option | Expected Match Rate | Tradeoff |
|---|---|---|
| Current: CF min_adv50=1e8 | 4.2% | Best CF quality, worst A3 coverage |
| CF min_adv50=0 (no filter) | ~20% (symbol-level ceiling) | Worse CF features for illiquid stocks |
| CF min_adv50=0, join only on symbol (latest CF label per symbol) | ~20% | Temporal mismatch — CF label may lag scan |
| Re-run CF panel with same universe as A3 (1,562 symbols) | ~50%+ | CF features unreliable for illiquid universe |
| Annotate A3 scan with CF label when symbol is liquid | ~4–20% depending on filter | Best for production: annotate only when CF coverage is solid |

---

## Verdict

**Phase 3 A3 testing with current CF panel is INCONCLUSIVE.**

- Sample size (9,012 rows) is insufficient for robust conclusions about A3+CF synergy.
- The matched subset is biased: only liquid A3 stocks that also appear in CF on the exact scan date.
- The dry-up T2 confirmation had only 25 rows — too few for any conclusion.

**Recommendation:**
1. Accept that A3/CF join at 4.2% match is structurally limited.
2. Do NOT rebuild CF panel with 0 filter just for A3 — CF quality degrades on illiquid stocks.
3. For Phase 3 annotation: add CF `phase_label` as a non-binding field in daily scan output for symbols already in CF scope, without forcing A3 join.

---

## Next Steps

| Action | Priority | Owner |
|---|---|---|
| Accept 4.2% as structural ceiling with current CF scope | Research | Operator |
| If A3+CF is important: rebuild A3 panel with same universe as CF (366 liquid symbols) | Future | Engineering |
| Annotate daily scan with CF label for CF-scope stocks only | Phase 3 plan | Engineering |

---

*Diagnosis date: 2026-05-30*
*CF panel params: min_adv50_vnd=1e8, include_fa=False*
*A3 panel: data/research/institutional_accumulation/panel_scores.parquet*
