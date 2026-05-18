# Phase36 Order Intent Validation

**Date:** 2026-05-17  
**Scan:** `phase36_daily_scan_sample.csv` (as_of 2026-05-15)  
**Module:** `src/trading/live/order_intent.py`

---

## Checks

| Requirement | Result |
|-------------|--------|
| `a3_rank_score` not in `ACTION_MAP` | **PASS** |
| `a3_rank_score` cannot create `BUY_T1` via map | **PASS** |
| `PAPER_S3_SHADOW` not in `ACTION_MAP` | **PASS** |
| S3-only row → paper intent, no live BUY | **PASS** |
| A3+S3 dual-active → `BUY_T1` only (not shadow swallow) | **PASS** |
| `final_action` remains production action source | **PASS** |

---

## ACTION_MAP keys (production mapping)

`NEW_T1`, `NEW_T1_MANUAL_REVIEW_BREADTH`, `ADD_T2`, `WAIT_PB`, `HOLD_T1_ONLY`, `NO_T2_BREADTH`, `SKIP_*`, `WATCH_ONLY`, `TP1_PARTIAL`, `TRAIL_EXIT`, `MAX_HOLD_EXIT`

**Not present:** `a3_rank_score`, `PAPER_S3_SHADOW`, `PAPER_S3_RESEARCH_MONITOR`

---

## Live scan day intents (2026-05-15)

| Intent action | Role |
|---------------|------|
| `BUY_T1_MANUAL_REVIEW` | VPB — from `final_action=NEW_T1_MANUAL_REVIEW_BREADTH` |
| `PAPER_S3_SHADOW` | S3-only rows (22 rows), `quantity_estimate=0` |
| `WATCH_ONLY` / `WATCH_*` | Non-tradeable A3 monitor states |
| `WATCH_S3_RESEARCH_ONLY` | S3 research classification |

No `BUY_T2` or `ADD_T2` on this scan date (no `ADD_T2` in CSV).

### VPB (only production buy candidate)

- Action: `BUY_T1_MANUAL_REVIEW`
- `quantity_estimate`: 6050
- `value_VND`: 166,700,000
- Driven by `final_action`, not `a3_rank_score`

### S3 paper shadow

- 22 rows with `PAPER_S3_SHADOW`
- All `quantity_estimate = 0`, `value_VND = 0`
- `s3_no_real_order_flag` enforced in shadow row builder

---

## Synthetic regression (isolated)

| Scenario | Intent actions |
|----------|----------------|
| Dual-active (A3+S3, `final_action=NEW_T1`) | `{BUY_T1}` only |
| S3-only (`a3_active=False`, `PAPER_S3_SHADOW`) | `{PAPER_S3_SHADOW}` only |

---

## Conclusion

Phase36 did **not** change order-intent generation. Rank fields are not routable to live/DNSE actions. S3 remains non-tradeable except paper-tier intents with zero quantity.
