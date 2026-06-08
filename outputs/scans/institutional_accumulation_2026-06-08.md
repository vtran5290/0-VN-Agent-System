# Institutional Accumulation Scan

**Scan date:** 2026-06-08  
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
| Các công ty đầu cơ và phát triển bất động sản | 3 | 25.31 |
| Ngân hàng | 2 | 32.67 |
| Sản phẩm thực phẩm | 2 | 28.48 |
| Unknown | 2 | 29.55 |
| Bảo hiểm tổng hợp | 1 | 41.9 |
| Công ty chứng khoán | 1 | 26.68 |
| Giấy | 1 | 38.17 |
| Xây dựng, xây lắp | 1 | 25.28 |

## Top candidates (Tier 1)

_No Tier 1 names at current thresholds._

## Early accumulation (Tier 2)

| ticker | institutional_accumulation_score | score_money_flow | score_price_structure | smart_money_tag | cmf20_daily | rs_vs_vnindex_20 | vingroup_distortion_flag | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MSB | 60.19 | 74.25 | 78.19 | outside_fund_disclosure,ex_vingroup_quality | 0.51 | 0.11 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| TCI | 58.19 | 64.49 | 84.29 | outside_fund_disclosure,ex_vingroup_quality | 0.16 | 0.15 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| KDC | 53.88 | 66.39 | 66.33 | outside_fund_disclosure,ex_vingroup_quality | 0.29 | 0.11 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| KSF | 53.49 | 81.37 | 58.32 | outside_fund_disclosure,ex_vingroup_quality | 0.19 | 0.08 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; context=56; Elevated weekly distribution weeks (3/6); Inconsistent CMF daily vs weekly |
| KOS | 52.36 | 64.60 | 71.91 | outside_fund_disclosure,ex_vingroup_quality | 0.28 | 0.05 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (4/25) |
| HNM | 52.17 | 58.77 | 70.55 | outside_fund_disclosure,ex_vingroup_quality | 0.28 | 0.13 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| VPL | 50.53 | 65.50 | 76.16 | outside_fund_disclosure,vingroup_distortion_risk | 0.37 | 0.06 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=24 |
| PSI | 49.53 | 56.24 | 80.00 | outside_fund_disclosure,ex_vingroup_quality | 0.26 | 0.10 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Inconsistent CMF daily vs weekly; ADL diverging bearishly from price |
| MIG | 49.52 | 61.18 | 73.26 | outside_fund_disclosure,ex_vingroup_quality | 0.35 | 0.08 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA20; context=56; Elevated distribution days (4/25); Inconsistent CMF daily vs weekly |
| OCB | 49.26 | 71.94 | 63.44 | outside_fund_disclosure,ex_vingroup_quality | 0.10 | 0.08 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (5/25); Inconsistent CMF daily vs weekly |
| MST | 49.09 | 51.39 | 69.59 | outside_fund_disclosure,ex_vingroup_quality | 0.30 | 0.10 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| HHP | 47.38 | 48.90 | 66.85 | outside_fund_disclosure,ex_vingroup_quality | 0.29 | 0.07 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| HQC | 46.52 | 55.18 | 70.69 | outside_fund_disclosure,ex_vingroup_quality | 0.12 | 0.18 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Inconsistent CMF daily vs weekly; ADL diverging bearishly from price |

## Mixed / review (Tier 3, top 10)

| ticker | institutional_accumulation_score | score_money_flow | score_price_structure | smart_money_tag | cmf20_daily | rs_vs_vnindex_20 | vingroup_distortion_flag | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| THD | 53.44 | 80.62 | 84.29 | outside_fund_disclosure,ex_vingroup_quality | — | 3.18 | False | tier=Tier 3; CMF weekly positive; OBV above MA20; ADL bearish divergence vs price; RS vs VNINDEX 20d positive; Holds MA50; context=56; Extended 155.0% above MA20/50; ADL diverging bearishly from price |
| TVN | 51.00 | 71.25 | 79.73 | outside_fund_disclosure,ex_vingroup_quality | 0.47 | 0.24 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Moderately extended 18.7%; Elevated distribution days (4/25) |
| ACB | 50.70 | 75.78 | 67.23 | fund_commentary_mention,ex_vingroup_quality,policy_liquidity_sensitive | 0.23 | 0.17 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; ADL bearish divergence vs price; RS vs VNINDEX 20d positive; Holds MA50; context=66; High distribution-day count (7/25); ADL diverging bearishly from price |
| QNS | 45.95 | 48.47 | 62.33 | outside_fund_disclosure,ex_vingroup_quality | 0.30 | 0.06 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| UNI | 45.53 | 65.07 | 53.72 | outside_fund_disclosure,ex_vingroup_quality | — | 0.07 | False | tier=Tier 3; Up-volume dominates (20d); Turnover acceleration vs 50d baseline; RS vs VNINDEX 20d positive; context=56; Elevated distribution days (4/25); Elevated weekly distribution weeks (3/6) |
| DRI | 45.24 | 41.86 | 75.61 | outside_fund_disclosure,ex_vingroup_quality | 0.09 | 0.07 | False | tier=Tier 3; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Inconsistent CMF daily vs weekly |
| NAF | 45.14 | 47.84 | 74.58 | outside_fund_disclosure,ex_vingroup_quality | 0.33 | 0.10 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (5/25) |
| VNE | 44.69 | 75.85 | 43.54 | outside_fund_disclosure,ex_vingroup_quality | — | 0.01 | False | tier=Tier 3; OBV above MA20; Up-volume dominates (20d); More HV up-days than down-days; RS vs VNINDEX 20d positive; context=56; High distribution-day count (8/25) |
| ABB | 44.56 | 47.21 | 74.51 | outside_fund_disclosure,ex_vingroup_quality | -0.00 | 0.11 | False | tier=Tier 3; CMF weekly positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Inconsistent CMF daily vs weekly; ADL diverging bearishly from price |
| VND | 44.41 | 56.55 | 54.42 | outside_fund_disclosure,ex_vingroup_quality | -0.15 | 0.08 | False | tier=Tier 3; OBV above MA20; Up-volume dominates (20d); More HV up-days than down-days; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (4/25) |

## Emerging accumulation (outside fund disclosure tags)

_Names with Tier 1–3 + constructive money flow but **no** consensus/commentary/selective fund tag — possible accumulation not visible in top holdings._

**Count:** 18 (showing top 15)
| ticker | institutional_accumulation_score | score_money_flow |
| --- | --- | --- |
| MSB | 60.19 | 74.25 |
| TCI | 58.19 | 64.49 |
| KDC | 53.88 | 66.39 |
| KSF | 53.49 | 81.37 |
| KOS | 52.36 | 64.60 |
| HNM | 52.17 | 58.77 |
| VPL | 50.53 | 65.50 |
| PSI | 49.53 | 56.24 |
| MIG | 49.52 | 61.18 |
| MST | 49.09 | 51.39 |
| HHP | 47.38 | 48.90 |
| HQC | 46.52 | 55.18 |
| QNS | 45.95 | 48.47 |
| UNI | 45.53 | 65.07 |
| VND | 44.41 | 56.55 |

## Fund-context names in scan (any tier)

**Count:** 23 (core / second_ring / commentary / selective)
| ticker | institutional_accumulation_score | score_money_flow |
| --- | --- | --- |
| ACB | 50.70 | 75.78 |
| VCB | 44.21 | 51.35 |
| FPT | 39.02 | 47.81 |
| GAS | 38.08 | 35.58 |
| BVH | 36.34 | 38.70 |
| GMD | 34.57 | 31.62 |
| POW | 32.32 | 24.30 |
| STB | 30.97 | 30.06 |
| PNJ | 28.84 | 31.89 |
| KDH | 28.70 | 21.88 |
| MBB | 28.34 | 18.25 |
| NLG | 27.22 | 26.84 |
| CTG | 25.38 | 16.66 |
| BID | 25.35 | 23.27 |
| MWG | 24.86 | 24.57 |
| GVR | 24.01 | 25.85 |
| VHM | 23.50 | 30.03 |
| TCB | 22.43 | 19.77 |
| HPG | 22.13 | 13.40 |
| VNM | 20.72 | 22.42 |

## Validation spot-checks

- **consensus_MBB:** tier=Reject score=28.3 money=18 vin_flag=False
- **consensus_CTG:** tier=Reject score=25.4 money=17 vin_flag=False
- **consensus_MWG:** tier=Reject score=24.9 money=25 vin_flag=False
- **consensus_HPG:** tier=Reject score=22.1 money=13 vin_flag=False
- **consensus_GMD:** tier=Reject score=34.6 money=32 vin_flag=False
- **vin_VIC:** tier=Reject score=26.1 vin_distortion=False cmf_d=0.0681666200236524 cmf_w=0.09449144298743511
- **vin_VHM:** tier=Reject score=23.5 vin_distortion=False cmf_d=-0.0447651292551244 cmf_w=0.10203902888231953

## Caveats

- Metrics are OHLCV-derived from repo CSVs; refresh `data/stocks` before relying on dates.
- RS vs sector index not computed (VNINDEX only).
- Vingroup names flagged; cap-weight VNINDEX may be skewed 2025–2026.
- Smart Money tags are priors, not buy signals.

---
*End of scan report.*