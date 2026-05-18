# Intraday preview scan v3.1 — review note

## Review verdict

**APPROVED_FOR_OPERATOR_PREVIEW**

Independent review approved the intraday preview layer for operator planning only. It must **not** replace EOD Phase36 scan, route orders, or write intraday bars to EOD parquet.

## Remaining cleanup (completed)

- **P1:** `MISSING_INTRADAY_QUOTE` added to `DATA_QUALITY_VALUES` in `src/trading/intraday/schema.py` (runtime policy already used this value; enum now matches tests and policy).

## Tests

| Suite | Result |
|-------|--------|
| `tests/test_intraday_scan.py` | **27/27 passed** |
| Broader safety (`test_trading_order_intent`, `test_s3_phase35`, `test_phase36_daily_scan`, intraday) | Pre-existing failures in `test_s3_phase35` (import) and one `test_phase36_daily_scan` case (unrelated); intraday gate unchanged at 27 passed |

Archived output: `data/research/intraday/review/intraday_v3_1_test_output.txt`

## Operator contract (do not violate)

| Field | Meaning |
|-------|---------|
| `final_action` | Always **`INTRADAY_PREVIEW`** on intraday outputs |
| `would_be_final_action` | **IF_CLOSE_NOW** — what Phase36 would say if today closed at scan time |
| `auto_order_allowed` | **`False`** for every row |
| `manual_review_required` | Only for **quoted** rows with actionable preview signals |
| Unquoted symbols | `intraday_data_quality=MISSING_INTRADAY_QUOTE`, `intraday_action_status=STALE_DATA_NO_ACTION`, no manual review, not candidates |

## SSOT and routing

- **EOD Phase36 scan** remains SSOT for production order routing.
- **OMS** blocks intraday CSV paths via `scan_resolver._is_intraday_preview()`.
- **No live routing** from intraday CSV; preview does not change A3 production, S3 paper-shadow, or OMS production paths.

## Data boundaries

- VNINDEX overlay is **in-memory only**.
- No writes to `data/research/ema_cloud/ohlcv_panel_ext2012.parquet` or `data/fireant_ssot/ta_vnindex.parquet`.

## Maintainer status

Post–P1 enum patch: **ready for operator preview** per review verdict. Re-run `python -m src.trading.cli intraday-scan` during session for fresh `phase36_intraday_scan_latest.*` outputs.
