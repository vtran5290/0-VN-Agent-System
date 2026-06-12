# Institutional Accumulation Scan

**Scan date:** 2026-06-10  
**Role:** Research ranking only — not execution.  
**Context:** fallback:apr2026_default_priors.json | regime: `fragile_uptrend_narrow_leadership`  
**Universe:** full_liquid_universe — fund lists are priors only  
**Data:** local_csv:data/stocks | benchmark: VNINDEX | method: OHLCV-derived; no lookahead slice

## Regime context (Smart Money prior)

- narrow_breadth
- weak_foreign_flow
- low_liquidity_dispersion
- oil_geopolitics_inflation

## Sector summary

| Sector | Tier 1–2 count | Avg score (universe) |
| --- | ---: | ---: |
| Ngân hàng | 5 | 34.23 |
| Unknown | 5 | 29.14 |
| Các công ty đầu cơ và phát triển bất động sản | 3 | 26.53 |
| Sản phẩm thực phẩm | 3 | 28.79 |
| Công ty chứng khoán | 2 | 27.52 |
| Xây dựng, xây lắp | 2 | 26.47 |
| Bảo hiểm tổng hợp | 1 | 40.22 |
| Giấy | 1 | 40.81 |

## Top candidates (Tier 1)

_No Tier 1 names at current thresholds._

## Early accumulation (Tier 2)

| ticker | institutional_accumulation_score | score_money_flow | score_price_structure | smart_money_tag | cmf20_daily | rs_vs_vnindex_20 | vingroup_distortion_flag | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MSB | 59.67 | 68.41 | 84.27 | outside_fund_disclosure,ex_vingroup_quality | 0.51 | 0.12 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| AMS | 57.63 | 76.13 | 75.06 | outside_fund_disclosure,ex_vingroup_quality | 0.50 | 0.08 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (4/25) |
| DST | 56.77 | 75.51 | 84.29 | outside_fund_disclosure,ex_vingroup_quality | — | 2.30 | False | tier=Tier 2; CMF weekly positive; OBV above MA20; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=56; Extended 90.6% above MA20/50 |
| DL1 | 55.59 | 59.95 | 81.18 | outside_fund_disclosure,ex_vingroup_quality | 0.16 | 0.15 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| ABB | 54.99 | 61.10 | 77.46 | outside_fund_disclosure,ex_vingroup_quality | 0.15 | 0.16 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| ACB | 54.54 | 80.16 | 66.42 | fund_commentary_mention,ex_vingroup_quality,policy_liquidity_sensitive | 0.30 | 0.23 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; ADL bearish divergence vs price; RS vs VNINDEX 20d positive; Holds MA50; context=66; Elevated distribution days (5/25); ADL diverging bearishly from price |
| OCB | 53.79 | 77.03 | 68.73 | outside_fund_disclosure,ex_vingroup_quality | 0.27 | 0.17 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (4/25); ADL diverging bearishly from price |
| MST | 52.31 | 53.08 | 78.80 | outside_fund_disclosure,ex_vingroup_quality | 0.38 | 0.14 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| TCI | 52.30 | 58.46 | 80.03 | outside_fund_disclosure,ex_vingroup_quality | 0.03 | 0.12 | False | tier=Tier 2; CMF weekly positive; Turnover acceleration vs 50d baseline; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (4/25) |
| HHP | 51.57 | 54.55 | 74.14 | outside_fund_disclosure,ex_vingroup_quality | 0.32 | 0.06 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| VND | 50.27 | 61.90 | 59.54 | outside_fund_disclosure,ex_vingroup_quality | -0.11 | 0.11 | False | tier=Tier 2; OBV above MA20; Up-volume dominates (20d); More HV up-days than down-days; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| KDC | 50.02 | 59.40 | 62.04 | outside_fund_disclosure,ex_vingroup_quality | 0.24 | 0.09 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| HNM | 49.26 | 55.35 | 64.83 | outside_fund_disclosure,ex_vingroup_quality | 0.24 | 0.16 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| KOS | 49.26 | 61.94 | 64.46 | outside_fund_disclosure,ex_vingroup_quality | 0.45 | 0.04 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA20; context=56; Elevated distribution days (4/25) |
| MIG | 49.20 | 61.64 | 71.47 | outside_fund_disclosure,ex_vingroup_quality | 0.36 | 0.07 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA20; context=56; Elevated distribution days (4/25); Inconsistent CMF daily vs weekly |
| VPL | 48.92 | 63.38 | 73.27 | outside_fund_disclosure,vingroup_distortion_risk | 0.34 | 0.05 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=24 |
| VC3 | 48.79 | 50.23 | 70.08 | outside_fund_disclosure,ex_vingroup_quality | 0.71 | 0.05 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| PSI | 48.20 | 53.63 | 78.78 | outside_fund_disclosure,ex_vingroup_quality | 0.22 | 0.08 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Inconsistent CMF daily vs weekly; ADL diverging bearishly from price |
| NVB | 48.04 | 59.56 | 70.17 | outside_fund_disclosure,ex_vingroup_quality | 0.20 | 0.22 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Inconsistent CMF daily vs weekly; ADL diverging bearishly from price |
| HQC | 47.62 | 58.97 | 62.61 | outside_fund_disclosure,ex_vingroup_quality | 0.01 | 0.15 | False | tier=Tier 2; OBV above MA20; ADL bearish divergence vs price; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=56; ADL diverging bearishly from price |

## Mixed / review (Tier 3, top 10)

| ticker | institutional_accumulation_score | score_money_flow | score_price_structure | smart_money_tag | cmf20_daily | rs_vs_vnindex_20 | vingroup_distortion_flag | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| THD | 52.65 | 78.54 | 84.29 | outside_fund_disclosure,ex_vingroup_quality | — | 2.49 | False | tier=Tier 3; CMF weekly positive; OBV above MA20; ADL bearish divergence vs price; RS vs VNINDEX 20d positive; Holds MA50; context=56; Extended 136.7% above MA20/50; ADL diverging bearishly from price |
| IDJ | 49.59 | 64.37 | 82.30 | outside_fund_disclosure,ex_vingroup_quality | 0.45 | 0.25 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Extended 26.1% above MA20/50; ADL diverging bearishly from price |
| TVN | 45.14 | 62.49 | 70.68 | outside_fund_disclosure,ex_vingroup_quality | 0.48 | 0.28 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Moderately extended 19.3%; Elevated distribution days (4/25) |
| VNE | 45.06 | 68.97 | 54.20 | outside_fund_disclosure,ex_vingroup_quality | — | 0.08 | False | tier=Tier 3; OBV above MA20; Up-volume dominates (20d); More HV up-days than down-days; RS vs VNINDEX 20d positive; Holds MA20; context=56; High distribution-day count (7/25) |
| TTA | 44.81 | 63.81 | 60.28 | outside_fund_disclosure,ex_vingroup_quality | 0.41 | 0.04 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA20; context=56; High distribution-day count (6/25) |
| VJC | 44.53 | 46.74 | 82.48 | outside_fund_disclosure,ex_vingroup_quality | 0.24 | 0.10 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; High distribution-day count (6/25) |
| DLG | 43.93 | 55.39 | 75.42 | outside_fund_disclosure,ex_vingroup_quality | 0.11 | 0.14 | False | tier=Tier 3; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (5/25); Inconsistent CMF daily vs weekly |
| UNI | 43.84 | 74.47 | 34.92 | outside_fund_disclosure,ex_vingroup_quality | — | -0.03 | False | tier=Tier 3; Up-volume dominates (20d); Turnover acceleration vs 50d baseline; context=56; Elevated distribution days (4/25); Elevated weekly distribution weeks (3/6) |
| VVS | 43.69 | 58.04 | 64.12 | outside_fund_disclosure,ex_vingroup_quality | 0.10 | 0.09 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA20; context=56; High distribution-day count (6/25) |
| VCB | 43.56 | 48.87 | 62.38 | consensus_core,ex_vingroup_quality,ftse_beneficiary_candidate,policy_liquidity_sensitive | 0.11 | 0.08 | False | tier=Tier 3; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=88; High distribution-day count (8/25); Inconsistent CMF daily vs weekly |

## Emerging accumulation (outside fund disclosure tags)

_Names with Tier 1–3 + constructive money flow but **no** consensus/commentary/selective fund tag — possible accumulation not visible in top holdings._

**Count:** 22 (showing top 15)
| ticker | institutional_accumulation_score | score_money_flow |
| --- | --- | --- |
| MSB | 59.67 | 68.41 |
| AMS | 57.63 | 76.13 |
| DL1 | 55.59 | 59.95 |
| ABB | 54.99 | 61.10 |
| OCB | 53.79 | 77.03 |
| MST | 52.31 | 53.08 |
| TCI | 52.30 | 58.46 |
| HHP | 51.57 | 54.55 |
| VND | 50.27 | 61.90 |
| KDC | 50.02 | 59.40 |
| HNM | 49.26 | 55.35 |
| KOS | 49.26 | 61.94 |
| MIG | 49.20 | 61.64 |
| VPL | 48.92 | 63.38 |
| VC3 | 48.79 | 50.23 |

## Fund-context names in scan (any tier)

**Count:** 23 (core / second_ring / commentary / selective)
| ticker | institutional_accumulation_score | score_money_flow |
| --- | --- | --- |
| ACB | 54.54 | 80.16 |
| VCB | 43.56 | 48.87 |
| GAS | 36.80 | 30.11 |
| BVH | 35.82 | 42.73 |
| FPT | 35.75 | 39.03 |
| NLG | 33.50 | 31.18 |
| VHM | 32.35 | 31.25 |
| POW | 31.48 | 23.24 |
| STB | 30.77 | 31.21 |
| KDH | 30.38 | 27.03 |
| PNJ | 29.49 | 31.42 |
| MBB | 27.59 | 20.63 |
| GMD | 27.01 | 30.77 |
| BID | 26.89 | 19.84 |
| MWG | 26.05 | 25.58 |
| CTG | 24.79 | 14.57 |
| VNM | 22.53 | 22.21 |
| HPG | 22.07 | 13.24 |
| SSI | 21.28 | 20.07 |
| TCB | 20.97 | 19.13 |

## Validation spot-checks

- **consensus_MBB:** tier=Reject score=27.6 money=21 vin_flag=False
- **consensus_CTG:** tier=Reject score=24.8 money=15 vin_flag=False
- **consensus_MWG:** tier=Reject score=26.1 money=26 vin_flag=False
- **consensus_HPG:** tier=Reject score=22.1 money=13 vin_flag=False
- **consensus_GMD:** tier=Reject score=27.0 money=31 vin_flag=False
- **vin_VIC:** tier=Reject score=20.5 vin_distortion=False cmf_d=-0.016688956634012497 cmf_w=0.0975530878800061
- **vin_VHM:** tier=Reject score=32.4 vin_distortion=False cmf_d=0.008323659407715506 cmf_w=0.10283052803324166

## Caveats

- Metrics are OHLCV-derived from repo CSVs; refresh `data/stocks` before relying on dates.
- RS vs sector index not computed (VNINDEX only).
- Vingroup names flagged; cap-weight VNINDEX may be skewed 2025–2026.
- Smart Money tags are priors, not buy signals.

---
*End of scan report.*