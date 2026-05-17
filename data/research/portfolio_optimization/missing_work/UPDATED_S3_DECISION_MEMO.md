# S3 Upgrade — Classification Decision Memo

Date: 2026-05-16 | Supersedes: S3_UPGRADE_DECISION_MEMO.md
Author: Claude Code (Sonnet 4.6)

---

## Decision Summary

**S3 EMA21/55 is upgraded from RESEARCH_ONLY to PAPER_TRADE_SHADOW.**

Enabling condition: max_hold = 60 bars (not 250).  
No real capital. No DNSE route. No live order intent.

---

## Classification Table

| Candidate | Class | MAR | Role | Capital |
|-----------|-------|-----|------|---------|
| A3 DP-First (EMA20/100) | PRODUCTION_CANDIDATE | 0.416 | Primary production strategy | YES |
| PTS shadow | PAPER_TRADE_SHADOW | 0.343 | Aggressive shadow, default OFF | PAPER ONLY |
| S3 max_hold=250 | REJECTED / RESEARCH_ONLY | -0.011 | Stale config — do not use for shadow | NONE |
| **S3 max_hold=60** | **PAPER_TRADE_SHADOW** | **0.377** | **S3 paper shadow** | **PAPER ONLY** |
| S3 GK5+max60+top100 | PARALLEL_PAPER_RESEARCH | 0.449 | Research monitor only | PAPER ONLY |

---

## What Changed From Prior Research

Previous best S3 (all configs including best DP config): MAR=0.190. Classified RESEARCH_ONLY.

New finding: S3 with max_hold=60 → MAR=0.377. Gate (0.30) passed.

The single change: **max_hold 250 → 60 bars.** Everything else unchanged.
- TP1: 18% (same)
- Trail: 3.5×ATR14 (same)
- Universe: full (same, no VIN3 exclusion for S3)
- Regime gate: VNINDEX EMA20>EMA100 (same)

Why max_hold=60 works: S3 uses EMA21/55 (fast cycle). Positions held past 60 bars hold
through the full reversal of the faster signal. 60 bars ≈ 3 trading months = natural
horizon for a 55-bar EMA signal.

---

## A3 Is Unchanged

A3 DP-First production config is not modified:
- EMA20/100, ex-VIN3, T1=50%, T2 on ≥4% pullback within 30 bars
- TP1=18%, trail=2.5×ATR14, max_hold=250
- Breadth advisory only — VNINDEX bear is the only hard T1 block
- Regime gate: VNINDEX EMA20>EMA100

---

## S3 as A3 Lead Indicator (Priority Ranking)

A3 trades with a prior S3 signal within 5 bars have MAR delta +0.083 vs A3 without S3.

**Rule:** When multiple A3 signals fire on the same day, rank those with `a3_s3_lead_5d=True`
first. This is a ranking rule only. A3 is never blocked because S3 was absent.

---

## S3 Hard Rules (DO NOT VIOLATE)

| Rule | Value |
|------|-------|
| S3 max_hold for shadow | **60 bars** — not 250, not 90, not 180 |
| S3 real capital | **NEVER** until explicit future approval |
| S3 DNSE route | **NEVER** |
| S3 live order intent | **NEVER** |
| S3 + A3 combined P&L | **NEVER** — track separately |
| S3 blocking A3 T1 | **NEVER** — S3 is ranking, not gating |

---

## Tests That Failed (Rejected Configs)

| Config | Best MAR | Reason rejected |
|--------|----------|----------------|
| Scout before A3 | 0.176 | Below 0.30 gate, adds complexity |
| Breadth regime filters | 0.147 | Below 0.30 gate |
| GK standalone (no max60) | 0.229 | Below 0.30 gate |
| S3 max_hold=250 | -0.011 | Negative MAR, rejected |
| S3 combined with A3 book | 0.264 | Worse than A3 alone (0.416) |

---

## Upgrade Path to Production

S3 requires ALL of the following before any production discussion:
1. 12 months of live paper trade data with max_hold=60 config
2. Live paper MAR ≥ 0.35 over the 12-month period
3. No 12-month rolling MaxDD exceeding -25%
4. 2022-equivalent bear year: better than -18% (current backtest worst year)
5. Explicit operator decision after reviewing live paper results

No timeline. No automatic upgrade. Evidence-driven only.

---

## Year-by-Year Stability (S3 max_hold=60)

| Year | Return |
|------|--------|
| 2015 | -7.0% |
| 2016 | -4.7% |
| 2017 | +27.9% |
| 2018 | -9.5% |
| 2019 | +3.3% |
| 2020 | +14.7% |
| 2021 | +67.7% |
| 2022 | **-18.0%** |
| 2023 | +6.6% |
| 2024 | +5.0% |
| 2025 | +45.3% |

S3 is offensive: strong in 2021, 2025. Weak in 2022, 2015, 2016.
A3 comparison 2022: -7.9% (much better drawdown control).
Do not use S3 as a bear-market hedge or defensive position.
