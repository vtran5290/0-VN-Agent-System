# Intraday preview scan (pre-lunch)

- Generated: 2026-05-18T10:45:58.587506+07:00
- Mode: **pre-lunch** (preview only — no auto orders)
- `auto_order_allowed`: **False** (always)

## A. Data integrity

- Source: FireAnt (`historical_quotes_partial_daily`)
- Capability available: **True**
- Panel EOD as-of: **2026-05-18**
- Session phase: **MORNING_CONTINUOUS**
- Stale symbols: none
- Missing quotes: none

## B. Intraday A3 preview (IF_CLOSE_NOW)

### would_be `TP1_PARTIAL` (2)

| symbol   |   close_kVND |   a3_rank_score | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:-------------------------|:------------------------|
| TCO      |         15.5 |           2.829 | MANUAL_REVIEW_REQUIRED   | OK                      |
| VHM      |        158   |           0.168 | MANUAL_REVIEW_REQUIRED   | OK                      |

### would_be `TRAIL_EXIT` (32)

| symbol   |   close_kVND |   a3_rank_score | intraday_action_status   | intraday_data_quality   |
|:---------|-------------:|----------------:|:-------------------------|:------------------------|
| EIB      |        21.85 |           2.913 | MANUAL_REVIEW_REQUIRED   | OK                      |
| VCG      |        21.6  |           2.885 | MANUAL_REVIEW_REQUIRED   | OK                      |
| HHS      |        13    |           0.999 | MANUAL_REVIEW_REQUIRED   | OK                      |
| VGI      |        89.2  |           0.973 | MANUAL_REVIEW_REQUIRED   | OK                      |
| MSN      |        77.5  |           0.969 | MANUAL_REVIEW_REQUIRED   | OK                      |
| MZG      |        12.9  |           0.961 | MANUAL_REVIEW_REQUIRED   | OK                      |
| NVL      |        17.3  |           0.96  | MANUAL_REVIEW_REQUIRED   | OK                      |
| HUT      |        15.9  |           0.933 | MANUAL_REVIEW_REQUIRED   | OK                      |
| MCH      |       133    |           0.932 | MANUAL_REVIEW_REQUIRED   | OK                      |
| PPC      |         9.81 |           0.929 | MANUAL_REVIEW_REQUIRED   | OK                      |
| VHC      |        60    |           0.917 | MANUAL_REVIEW_REQUIRED   | OK                      |
| MWG      |        82    |           0.89  | MANUAL_REVIEW_REQUIRED   | OK                      |
| DGW      |        42.4  |           0.882 | MANUAL_REVIEW_REQUIRED   | OK                      |
| HNM      |         7.5  |           0.863 | MANUAL_REVIEW_REQUIRED   | OK                      |
| REE      |        60.3  |           0.859 | MANUAL_REVIEW_REQUIRED   | OK                      |

## C. S3 paper-shadow preview

- S3 remains **PAPER_SHADOW / NO REAL CAPITAL**
- `PAPER_S3_SHADOW` count: **0**

## D. Volume projection warning

- Projected volume is **not** used for official ADV50 (EOD history only).
## E. Operator action

- **Manual review only** — do not route to OMS without EOD scan confirmation.

### Top manual-review candidates

| symbol   | would_be_final_action   |   a3_rank_score | intraday_action_status   |
|:---------|:------------------------|----------------:|:-------------------------|
| EIB      | TRAIL_EXIT              |           2.913 | MANUAL_REVIEW_REQUIRED   |
| VCG      | TRAIL_EXIT              |           2.885 | MANUAL_REVIEW_REQUIRED   |
| TCO      | TP1_PARTIAL             |           2.829 | MANUAL_REVIEW_REQUIRED   |
| HHS      | TRAIL_EXIT              |           0.999 | MANUAL_REVIEW_REQUIRED   |
| VGI      | TRAIL_EXIT              |           0.973 | MANUAL_REVIEW_REQUIRED   |
| MSN      | TRAIL_EXIT              |           0.969 | MANUAL_REVIEW_REQUIRED   |
| MZG      | TRAIL_EXIT              |           0.961 | MANUAL_REVIEW_REQUIRED   |
| NVL      | TRAIL_EXIT              |           0.96  | MANUAL_REVIEW_REQUIRED   |
| HUT      | TRAIL_EXIT              |           0.933 | MANUAL_REVIEW_REQUIRED   |
| MCH      | TRAIL_EXIT              |           0.932 | MANUAL_REVIEW_REQUIRED   |

## F. Risk warnings

- Intraday data may be delayed vs exchange tape.
- Breadth/regime from last EOD decomposition unless refreshed.
- Do not confuse `would_be_final_action` with tradeable `final_action`.
