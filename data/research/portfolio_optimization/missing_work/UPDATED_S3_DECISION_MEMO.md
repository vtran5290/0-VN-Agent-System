# Updated S3 Decision Memo — Phase35

Generated: 2026-05-17
Supersedes: S3_UPGRADE_DECISION_MEMO.md, FINAL_DECISION_MEMO_CLEAN.md (S3 section only)

---

## S3 Classification Table (Phase35)

| Config | Classification | MAR | Role | Capital |
|--------|---------------|-----|------|---------|
| S3 EMA21/55 max_hold=250 | **REJECTED** | -0.011 | Never use as shadow config | NONE |
| S3 EMA21/55 max_hold=60 | **PAPER_TRADE_SHADOW** | 0.377 | Paper shadow tracking | PAPER ONLY |
| S3 GK5 + max60 + top100 | **PARALLEL_PAPER_RESEARCH** | 0.449* | Research monitor | NONE |
| S3 combo TP10/mom20/breadth35 | **PRODUCTION_CANDIDATE_PENDING_PAPER** | 0.640 | Paper gate in progress | PAPER ONLY |

*MAR=0.449 unverified — no persisted CSV. Requires s3_combined_test.py re-run.

---

## Non-Negotiables

1. **A3 DP-first is the ONLY real-capital candidate.** Nothing in this memo changes A3 production logic.
2. **S3 gets no real capital, no DNSE routing, no live orders — in any config.**
3. **S3 max_hold=250 is rejected and must never be used as a shadow config.**
4. **S3 max_hold=60 is the correct shadow config** (TP=18%, trail=3.5×ATR14, max_hold=60).
5. **S3 does not gate A3.** S3 lead-5d improves A3 ranking only — A3 signal fires regardless.
6. **S3 requires 12 months live paper evidence before any production discussion.**

---

## S3 max_hold=60 — PAPER_TRADE_SHADOW

Config:
- Universe: full 272-symbol
- EMA: 21/55
- Entry: cloud breakout (EMA21 > EMA55, price above both, min 3 bear bars before)
- TP1: +18%
- Trail: 3.5×ATR14
- max_hold: **60 bars** (HARD RULE — never change to 250)
- Regime gate: VNINDEX EMA20 > EMA100
- Breadth/GK filters: NOT applied for base shadow

Results: MAR=0.377, CAGR=7.9%, MaxDD=-21.0%, 2022=-18.0%

**Risk:** S3 is offensive. In bear years it significantly underperforms A3. Do not treat as a hedge.

---

## S3 Lead-5d → A3 Ranking Only

- `a3_s3_lead_5d = True` if S3 fired ≤5 bars before A3 on same symbol
- `a3_priority_boost_from_s3 = True` when lead-5d confirmed
- A3 is ranked higher — it is NEVER blocked when `a3_s3_lead_5d = False`
- A3 production rules unchanged

Phase36 extension: lead_11_20 bucket (MAR=0.464) and lead_21_30 (MAR=0.455) provide finer
ranking via `s3_lead_age_bars`. Additive to `a3_s3_lead_5d`, not a replacement.

---

## S3 GK5 + max60 + top100 — PARALLEL_PAPER_RESEARCH

No capital. Track as `PAPER_S3_RESEARCH_MONITOR` in daily scan.
Confirm MAR ≥ 0.40 via `pp_backtest/s3_combined_test.py` before any reclassification.

---

## S3 Combo TP10/mom20/breadth35 — PRODUCTION_CANDIDATE_PENDING_PAPER

MAR=0.640 (confirmed 2026-05-17). Paper gate: 30 decisions / 10 exits / 90 days.
Capacity: ~5B VND. Ledger: `src/trading/live/s3_combo_paper_ledger.py`.

---

## S3 max_hold=250 — REJECTED

MAR=-0.011. Label in scan as `REJECTED_CONFIG`. Do not shadow or track.

---

## What Has NOT Changed

- A3 EMA20/100 DP-First production logic, entry, sizing, routing
- A3 universe (ex-VIN3), T1=50%, T2=50% pullback, TP1=+18%, trail=2.5×ATR14, max_hold=250
- Breadth does not hard-block A3 T1; VNINDEX bear is the only hard block
- Sector L4: dashboard warning only; PTS: paper shadow only; AFL: visual only
