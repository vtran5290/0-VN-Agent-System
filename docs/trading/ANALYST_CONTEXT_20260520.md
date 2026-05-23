# Analyst Context — 2026-05-20 (for ChatGPT reviewer)

**Purpose:** Sanity-check qualitative conclusions against packaged data.  
**Not SSOT** — research notes only.

**EMA method (authoritative for this package):** Full `VNINDEX.csv` history → `ewm(span, adjust=False)` for EMA10/20/50, then last 10 rows exported to `outputs/VNINDEX_recent_5d.csv`.  
Do **not** recompute EMA on the 10-row tail only (that yields different distances).

---

## FACTS — VNINDEX session 2026-05-20 (FireAnt EOD, native)

Source: `outputs/VNINDEX_recent_5d.csv` (matches `minervini_backtest/data/raw/VNINDEX.csv`).

| Field | 2026-05-19 | 2026-05-20 |
|-------|------------|------------|
| Close | 1912.93 | 1913.23 |
| Return | −0.78% | +0.02% |
| Range / prev close | 1.49% | 3.15% |
| Volume / 20d avg (`vol_ratio`) | 1.26× | **1.46×** |
| Close in range (`close_loc`) | 0.30 | **0.898** |
| Low | — | 1859 (−2.8% vs prior close) |
| % vs EMA10 / 20 / 50 | +0.43% / +2.02% / +5.03% | **+0.36% / +1.84% / +4.84%** |
| Above EMA10 / 20 / 50 | 1 / 1 / 1 | **1 / 1 / 1** (Yes / Yes / Yes) |
| Distribution day (O'Neil rule) | Yes | No |
| dist_count_10d / 25d (lens) | — | 3 / 4 |

---

## FACTS — Distribution lens as-of 2026-05-20

See `outputs/distribution_risk_latest.json`.

- **Primary view:** ex_vin_proxy → CAUTION
- **ex-VIN `last_data_date`:** 2026-05-19 vs **requested** 2026-05-20 → `is_stale_for_as_of: true`
- **Lens `report_status`:** NEEDS_REVIEW (`PRIMARY_VIEW_STALE`)
- **VNINDEX raw:** DISTRIBUTION_CLUSTER

---

## FACTS — Historical analogues (reproducibility)

Primary file in zip: `outputs/distribution_days_forward_returns_2024plus.csv` (subset from 2024).  
Bucket summary: `outputs/analyst_historical_buckets_20260520.csv`.

| Filter label | n | 10d mean fwd | 10d P(neg) |
|--------------|---|--------------|------------|
| prior_down_then_strong_close_above_ema10_20 | 21 | +1.79% | 28.6% |
| day_after_dist_strong_close_above_ema20_50 | 108 | +0.64% | 41.7% |
| above_ema10_20_50_dist10_2_3 | 690 | +0.68% | 38.4% |

20/5 matches **above EMA10/20/50** + strong close → use rows 2–3; not the strict “prior down” row unless 19/5 down filter applied separately.

---

## INTERPRETATION (non-SSOT)

1. Recovery candle on 20/5 (wide range, close near high, vol ~1.46×).
2. Still above EMA10/20/50 on **full-history** EMA — short-term cushion thin (+0.36% above EMA10).
3. Distribution cluster persists — context caution, not cleared by one session.
4. ex-VIN lens data stale vs 20/5 — use freshness table; do not treat ex-VIN probs as fully current.
