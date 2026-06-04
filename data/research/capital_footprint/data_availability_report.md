# Capital Footprint Research — Data Availability Report

**Date:** 2026-05-29
**Author:** Claude Code (automated audit)
**Purpose:** Document what data is available, what is missing, and what proxy features are used.

---

## FACTS | ASSUMPTIONS | RISKS | ACTIONS

---

## 1. Primary Data Sources

### 1.1 OHLCV Panel (REQUIRED — AVAILABLE)

| Property | Value |
|---|---|
| File | `data/fireant_ssot/ta_ohlcv_panel.parquet` |
| Rows | 1,279,304 |
| Symbols | 1,564 |
| Date range | 2017-05-18 to 2026-05-29 |
| Columns | symbol, date, open, high, low, close, volume, value |
| Price type | Adjusted (FireAnt adjusted close) |
| Value traded | VND (value column) |
| Status | **AVAILABLE** |

**Note:** Data starts 2017-05-18, not 2012. Feature backtest window is therefore 2018-2026 (after 6-month warmup). The spec requests 2012 start but this data does not exist in the repository. VNINDEX goes back to 2012 but ticker-level data only to 2017.

### 1.2 VNINDEX Daily Bars (REQUIRED — AVAILABLE)

| Property | Value |
|---|---|
| File | `data/fireant_ssot/ta_vnindex.parquet` |
| Rows | 3,590 |
| Date range | 2012-01-03 to 2026-05-29 |
| Columns | date, open, high, low, close, volume |
| Status | **AVAILABLE** |

### 1.3 Sector Classification (REQUIRED — PARTIAL)

| Property | Value |
|---|---|
| File | `data/master/sector_map.csv` |
| Symbols mapped | 115 (of 1,564 in OHLCV) |
| Columns | symbol, primary_sector, sub_sector, themes |
| ICB fallback | `fa_quarterly.parquet` has icbCode and icbName for 1,932 symbols |
| Status | **PARTIAL — ICB fallback used for unmatched symbols** |

**Proxy:** For symbols not in sector_map.csv, use `icbName` from FA quarterly data (available for 1,932 symbols). This covers ~90%+ of the tradeable universe.

### 1.4 Value Traded / Liquidity (REQUIRED — AVAILABLE)

| Property | Value |
|---|---|
| Source | `value` column in ta_ohlcv_panel.parquet |
| Unit | VND (Vietnamese Dong) |
| Coverage | Same as OHLCV panel |
| Status | **AVAILABLE** |

### 1.5 Market Regime Log (REQUIRED — AVAILABLE)

| Property | Value |
|---|---|
| File | `data/combined_regime_log_2012_now.csv` |
| Rows | 3,505 |
| Date range | 2012-02-06 to present |
| Key columns | market_status_combined, breadth_pct, allow_new_buys, ma50, ma200, distribution_count_20d |
| Status | **AVAILABLE** |

---

## 2. Optional Data Sources

### 2.1 Financial Statement Data (OPTIONAL — AVAILABLE)

| Property | Value |
|---|---|
| File | `data/fireant_ssot/fa_quarterly.parquet` |
| Rows | 53,395 |
| Symbols | 1,932 |
| Date range | 2016Q1 to 2026Q2 |
| Key columns | symbol, year, quarter, financialValues_TotalRevenue, financialValues_ProfitAfterTax, icbCode, icbName |
| Total columns | 877 (rich feature set) |
| Status | **AVAILABLE — with 45-day lookahead guard** |

**Lookahead guard:** All FA features use a 45-day publication lag. Quarter-end date + 45 days = availability date.

### 2.2 Existing A3 Institutional Accumulation Scores (SUPPLEMENTARY — AVAILABLE)

| Property | Value |
|---|---|
| File | `data/research/institutional_accumulation/panel_scores.parquet` |
| Rows | 215,638 |
| Date range | 2017-05-19 to 2026-05-27 |
| Key columns | institutional_accumulation_score, tier, cmf20_daily, rs_vs_vnindex_20/60, adl_slope_20, up_down_volume_ratio_20, distribution_days_25 |
| Status | **AVAILABLE — used as A3 baseline in enhancement tests** |

---

## 3. Unavailable Data (Skipped Cleanly)

### 3.1 Foreign Institutional Flow (NOT AVAILABLE)

| Property | Value |
|---|---|
| Status | **NOT AVAILABLE** |
| Reason | No dedicated foreign flow data in repository |
| Impact | Cannot compute foreign_net_value, foreign_flow_z, foreign_accumulation_flag |
| Proxy | Residual capital proxy: high value traded with no known foreign attribution = potential domestic large-money signal |
| Features skipped | foreign_net_value_1d/5d/20d/60d, foreign_flow_persistence, foreign_accumulation_flag, foreign_ownership_room_proxy |

### 3.2 Proprietary/Dealer Trading (NOT AVAILABLE)

| Property | Value |
|---|---|
| Status | **NOT AVAILABLE** |
| Reason | No proprietary trading data in repository |
| Features skipped | All proprietary-trading-specific features |

### 3.3 Margin Data (NOT AVAILABLE — PROXY USED)

| Property | Value |
|---|---|
| Status | **NOT AVAILABLE (direct)** |
| Proxy | Vietnam liquidity cycle via SBV OMS and credit growth (macro-level signal, not stock-level) |
| Features skipped | Stock-level margin_balance, margin_eligibility_flag |

### 3.4 Index / ETF Membership Data (NOT AVAILABLE)

| Property | Value |
|---|---|
| Status | **NOT AVAILABLE** |
| Reason | No historical ETF basket, FTSE candidate list, or rebalance date data in repository |
| Features skipped | index_member_flag, ftse_candidate_flag, etf_candidate_flag, rebalance_window_flag, index_flow_score |

### 3.5 Broker Research / Target Price Revisions (NOT AVAILABLE)

| Property | Value |
|---|---|
| Status | **NOT AVAILABLE** |
| Reason | No broker revision data with timestamps in repository |
| Features skipped | broker_upgrade_flag, target_price_revision_30d, eps_revision_30d, revision_score |

---

## 4. Data Coverage Summary

| Dataset | Required | Available | Coverage | Notes |
|---|---|---|---|---|
| Adjusted OHLCV daily bars | Yes | Yes | 2017-2026, 1,564 symbols | 2012 start not available |
| VNINDEX daily bars | Yes | Yes | 2012-2026 | Full |
| Sector mapping | Yes | Partial | 115 direct + ICB fallback ~90% | ICB proxy used |
| Value traded (liquidity) | Yes | Yes | Same as OHLCV | Built into OHLCV panel |
| Foreign buy/sell | Optional | No | — | Skipped cleanly |
| Margin data | Optional | Proxy only | Macro-level only | SBV credit growth |
| ETF/index membership | Optional | No | — | Skipped cleanly |
| Financial statements | Optional | Yes | 2016-2026, 1,932 symbols | 45-day lag guard |
| Broker revisions | Optional | No | — | Skipped cleanly |
| Market regime | Yes | Yes | 2012-2026 | Full from regime log |
| A3 institutional scores | Supplementary | Yes | 2017-2026 | Used for A3 enhancement |

---

## 5. Backtest Window

| Period | Role | Date Range |
|---|---|---|
| Warmup | Feature computation only | 2017-05-18 to 2017-12-31 |
| Train/Design | In-sample optimization | 2018-01-01 to 2019-12-31 |
| Validation | Out-of-sample validation | 2020-01-01 to 2022-12-31 |
| Out-of-Sample | Final OOS test | 2023-01-01 to 2026-05-29 |

**Note:** The spec requests 2012-2018 training. This is not possible with available OHLCV data starting 2017-05-18. The revised splits above are used.

---

## 6. Proxy Features Summary

| Proxy Feature | Intended Signal | Proxy Used | Quality |
|---|---|---|---|
| sector_primary | Sector identity | ICB name from FA quarterly | Medium (covers ~90%) |
| big_individual_footprint_proxy | Large domestic capital | High value + strong close + non-foreign residual | Low-Medium (cannot confirm account type) |
| margin_liquidity_proxy | Margin cycle | Macro SBV credit growth (not stock-level) | Low (market-wide only) |
| foreign_flow_residual | Foreign attribution | None (skipped) | N/A |

---

## 7. Open Issues

1. OHLCV data only from 2017-05-18 — cannot test 2012-2017 period as specified
2. Sector map covers only 115 symbols — ICB fallback adds coverage but may have classification inconsistencies
3. No foreign flow → big_individual_footprint_proxy cannot distinguish domestic vs foreign capital accurately
4. FA data quarterly frequency → fundamental features change slowly, limited predictive power at daily frequency

---

**Next action:** Proceed with feature engineering using available data. Mark skipped features as `NaN` with documentation.
