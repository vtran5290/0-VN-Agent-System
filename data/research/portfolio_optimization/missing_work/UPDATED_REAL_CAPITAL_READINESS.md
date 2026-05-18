# Real Capital Readiness (Updated 2026-05-17 — Phase35+36)

Strategy: A3 DP-First | Classification: PRODUCTION_CANDIDATE

---

## Status: NOT READY FOR REAL CAPITAL

Blockers remain:
1. **Gate 1** — A3 paper trade not started (3-month minimum required)
2. **Gate 2** — Live data pipeline daily schedule not confirmed
3. **Gates 6-7** — Execution system position limits and exit alerts not implemented

---

## Gate Summary

| Gate | Description | Status |
|------|-------------|--------|
| Gate 1: Paper duration | A3 DP paper trade ≥ 3 months, ≥10 trades, MAR ≥ 0.30 | **NOT MET — NOT STARTED** |
| Gate 2: Live pipeline | Daily fetch runs, panel value confirmed, VNINDEX fresh | **NOT VERIFIED** |
| Gate 3: Liquidity formula | ADV50 corrected (Phase 3.1) | **VERIFIED** |
| Gate 4: Regime gate | VNINDEX EMA20>EMA100 logic confirmed | **VERIFIED** |
| Gate 5: Breadth monitoring | pct_cloud_bull_a3 computed daily | **VERIFIED LOGIC, NOT LIVE** |
| Gate 6: Position limits | Max 20 slots, ADV cap enforced in code | **NOT CONFIGURED** |
| Gate 7: Exit alerts | TP1, trail, max_hold triggers implemented | **NOT LIVE** |
| Gate 8: GK10 overlay | Optional, off by default | **VERIFIED (OPTIONAL)** |
| Gate 9: PTS mode | OFF by default, paper-only if on | **VERIFIED OFF** |
| Gate 10: S3 shadow | S3_max60 paper shadow started | **NOT STARTED** |
| Gate 11: S3 combo paper | S3 combo (TP=10%) paper gate started | **NOT STARTED** |

Ready when Gates 1–7 all checked. No timeline. Evidence-driven.

---

## S3 Shadow Status (Phase35)

S3 max60 is **PAPER_TRADE_SHADOW only** — no real capital, no live orders, no DNSE. S3 max250 is **rejected**. GK5+top100 is **PAPER_S3_RESEARCH_MONITOR** only. This does NOT affect A3 real capital gates.

S3 is **not** a production candidate. Any future discussion requires live paper evidence first.

S3 shadow evidence gate (separate from A3) requires:
1. 12 months live paper data (max_hold=60)
2. Live MAR ≥ 0.35
3. MaxDD ≤ -25% rolling 12M
4. Bear year ≥ -18%
5. Explicit operator decision

S3 shadow readiness is tracked separately and does not count toward A3 real capital gates.

---

## A3 Reference Performance

| Portfolio | MAR | CAGR | MaxDD |
|-----------|-----|------|-------|
| 5B VND / 10% ADV | 0.416 | 5.81% | -13.99% |

Backtest 2012-2026. Corrected ADV50 (Phase 3.1).

---

## S3 Shadow Reference Performance

| Config | MAR | CAGR | MaxDD | Notes |
|--------|-----|------|-------|-------|
| S3_max60 | 0.377 | 7.92% | -20.99% | PAPER_TRADE_SHADOW |
| S3_GK5_max60_top100 | 0.449 | 12.90% | -28.73% | Research monitor |
| S3_best_dp (max_hold=250) | 0.190 | 4.65% | -24.47% | REJECTED |
