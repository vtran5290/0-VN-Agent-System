# S3 Order Intent Rules (Phase35)

Date: 2026-05-16 | Classification: PAPER_TRADE_SHADOW

---

## S3 max_hold=60 — Allowed Intent

| Intent type | Allowed? | Notes |
|-------------|----------|-------|
| Paper trade entry (manual log) | YES | Log to s3_shadow_paper_trades.csv |
| Paper trade exit (manual log) | YES | Log exit reason and P&L |
| DNSE order | **NEVER** | Hard rule — not now, not before "approval" |
| Live order (any broker) | **NEVER** | Hard rule |
| Real capital allocation | **NEVER** | Until explicit future approval gate |
| Combined A3+S3 P&L reporting | **NEVER** | Track separately always |

---

## Order-Intent Field in Scan Output

`strategy_classification` field controls routing:

| strategy_classification | Order intent | Execution |
|------------------------|-------------|-----------|
| A3_PRODUCTION | LIVE_ORDER_INTENT | DNSE route allowed (after real capital approval) |
| PTS_SHADOW | PAPER_INTENT_ONLY | No live order |
| S3_PAPER_SHADOW | **PAPER_S3_SHADOW_INTENT_ONLY** | No live order. No DNSE. |
| S3_RESEARCH_ONLY | NO_INTENT | Watchlist display only |
| WATCH_ONLY | NO_INTENT | Display only |
| SKIP | NO_INTENT | Not shown |

---

## Code Enforcement (Scan Layer)

Any code generating order objects MUST check `strategy_classification` before routing:

```python
if row["strategy_classification"] == "S3_PAPER_SHADOW":
    # paper log only — never route to broker
    log_s3_shadow_paper(row)
    return  # do NOT fall through to order router

if row["strategy_classification"] == "A3_PRODUCTION":
    # only after real capital approval gate is confirmed
    if REAL_CAPITAL_APPROVED:
        route_to_dnse(row)
    else:
        log_paper(row)
```

---

## What Changes from Phase34

Phase34: S3 had `strategy_classification = S3_RESEARCH_ONLY` — no paper tracking, no position size.

Phase35: S3_max60 has `strategy_classification = S3_PAPER_SHADOW`:
- Paper position size = same slot formula as A3 (for tracking comparison only)
- Logged to `data/trading/live/s3_shadow_paper_trades.csv`
- `final_action` for S3 shadow: NEW_S3_SHADOW | S3_SHADOW_HOLD | S3_SHADOW_EXIT | WATCH_ONLY
- max_hold hard limit = 60 bars enforced in scan and in paper ledger

S3_best_dp (old max_hold=250 config) remains `S3_RESEARCH_ONLY` — no change to that path.

---

## A3 Priority Rule (S3 as Lead Indicator)

Field: `a3_s3_lead_5d` in scan output.

When `a3_s3_lead_5d = True`: S3 signal fired within 5 bars before this A3 signal.

**Operator rule:** On days with multiple NEW_T1 or NEW_T1_MANUAL_REVIEW_BREADTH signals, sort by:
1. `a3_s3_lead_5d = True` first
2. Then by ADV50 descending

This is a **ranking rule only**. A3 is never blocked because `a3_s3_lead_5d = False`.
