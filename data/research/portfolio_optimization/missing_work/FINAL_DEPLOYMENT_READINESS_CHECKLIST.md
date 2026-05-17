# Final Deployment Readiness Checklist

Date: 2026-05-16 | Strategy: A3 DP-First | Classification: PRODUCTION_CANDIDATE

---

## Pre-Deployment Gates

### Gate 1: Paper Trade Duration (REQUIRED, NOT MET)

- [ ] A3 DP paper trade running continuously for ≥ 3 months
- [ ] At least 10 completed trades (T1 entered AND exited)
- [ ] Running MAR on paper trades ≥ 0.30

Current status: **Paper trade not started. This gate blocks real capital deployment.**

---

### Gate 2: Live Data Pipeline (REQUIRED, NOT VERIFIED)

- [ ] `python scripts/run_weekly_full_fetch.py` runs cleanly on scheduled basis
- [ ] Panel parquet files update daily (HOSE/HNX prices, volume, value)
- [ ] panel["value"] column confirmed populated (not just close×vol fallback)
- [ ] VNINDEX data available daily for regime gate computation
- [ ] Phase34 scan runs without errors on fresh data

Current status: Pipeline exists. Daily schedule not confirmed.

---

### Gate 3: Liquidity Formula (VERIFIED — Phase 3.1)

- [x] ADV50 formula confirmed: `panel["value"].rolling(50).mean()`
- [x] Unit confirmed: VND (not kVND). Phase 3.1 ratio check passed.
- [x] AFL formula confirmed: `MA(C * V * 1000, 50)` — close_kVND × volume × 1000 = VND
- [x] Never use `close × volume` without `× 1000` (Phase 3.1 bug fix)

---

### Gate 4: Regime Gate (VERIFIED)

- [x] VNINDEX EMA20 > EMA100 = bull regime (only hard T1 block)
- [x] VNINDEX EMA20 < EMA100 = bear regime → no new T1 entries
- [x] Gate computed from VNINDEX close data (not individual stocks)
- [ ] Live confirmation: regime gate correctly reflects current VNINDEX EMA state

---

### Gate 5: Breadth Monitoring (VERIFIED LOGIC, NOT LIVE)

- [x] Breadth = pct_cloud_bull_a3 = fraction of A3 universe in EMA20/100 bull cloud
- [x] Defense (<35%): T1 allowed with operator review. T2 blocked.
- [x] Caution (35-40%): T1 allowed. T2 reduced.
- [x] Normal (≥40%): T1 and T2 both allowed.
- [ ] Breadth computed and displayed daily in dashboard

---

### Gate 6: Position Limits (REQUIRED, NOT CONFIGURED)

- [x] Max 20 concurrent slots (20 positions)
- [x] T1 = 50% of slot (T2 = 50% on pullback)
- [x] ADV cap: effective_T1 = min(T1_target, adv50_VND × 10%)
- [ ] Execution system enforces position count limit
- [ ] Execution system enforces 5-bar minimum hold (T+3 settlement)

---

### Gate 7: Exit Rules (VERIFIED LOGIC, NOT LIVE)

- [x] TP1: sell 50% of position when close ≥ ep1 × 1.18
- [x] Trail: exit remaining when close < (peak − 2.5×ATR14)
- [x] Max hold: exit at 250 bars regardless of P&L
- [x] Min sell lock: no exits within 5 bars of entry
- [ ] Exit triggers implemented in execution system or tracked manually with daily alerts

---

### Gate 8: GK10 Overlay (OPTIONAL — NOT REQUIRED FOR DEPLOYMENT)

- [x] GK10 signal: Garman-Klass buy within 10 days of A3 breakout
- [x] Effect: slot × 1.25 if GK10 active
- [ ] GK10 overlay tested on 3+ months of paper trades separately
- Note: GK10 can be OFF (gk_mult=1.0) without affecting deployment readiness

---

### Gate 9: PTS Mode (VERIFIED OFF — NO REAL CAPITAL)

- [x] PTS mode = OFF by default (Param "PTS Shadow ON" = 0)
- [x] PTS classified PAPER_TRADE_SHADOW (MAR=0.343 < DP MAR=0.416)
- [x] No real capital in PTS mode
- [ ] PTS shadow paper trade running separately (optional)

---

### Gate 10: S3 Shadow (UPDATED 2026-05-16)

- [x] S3_best_dp (max_hold=250) REJECTED — MAR=0.190, do not use
- [x] S3_max60 classified PAPER_TRADE_SHADOW — MAR=0.377, max_hold=60 bars
- [x] S3 paper shadow: no real capital, no DNSE route, no live order intent
- [x] S3 shadow AFL created: Cloud_Strategy_S3_21_55_PAPER_SHADOW_MAX60.afl
- [ ] S3 shadow paper ledger active (s3_shadow_paper_trades.csv)
- [x] S3 and A3 P&L tracked separately — never combined

---

## Capital Deployment Decision

**Status as of 2026-05-16: NOT READY FOR REAL CAPITAL**

Blockers:
1. Paper trade not started (Gate 1 — 3 months minimum)
2. Live data pipeline schedule not confirmed (Gate 2)
3. Execution system position limits and exit alerts not implemented (Gates 6-7)

Ready when Gates 1-7 are all checked.

---

## Reference Performance (Backtest 2012–2026)

| Portfolio | MAR | CAGR | MaxDD |
|-----------|-----|------|-------|
| 5B VND / 10% ADV | 0.416 | 5.81% | -13.99% |

Backtest uses corrected ADV50 (Phase 3.1). Period: 2012-01-01 to 2026-05-16.
Walk-forward validation (2023-2026 out-of-sample) pending as future work.
