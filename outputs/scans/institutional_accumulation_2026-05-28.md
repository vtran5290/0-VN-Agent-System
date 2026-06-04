# Institutional Accumulation Scan

**Scan date:** 2026-05-28  
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
| Unknown | 6 | 27.81 |
| Các công ty đầu cơ và phát triển bất động sản | 3 | 25.44 |
| Ngân hàng | 3 | 33.37 |
| Bia | 1 | 40.95 |
| Bảo hiểm tổng hợp | 1 | 33.85 |
| Công ty chứng khoán | 1 | 31.52 |
| Giấy | 1 | 42.24 |
| Khai thác quặng sắt và sản xuất thép | 1 | 30.57 |
| Sản phẩm thực phẩm | 1 | 27.9 |
| Xây dựng, xây lắp | 1 | 26.48 |

## Top candidates (Tier 1)

_No Tier 1 names at current thresholds._

## Early accumulation (Tier 2)

| ticker | institutional_accumulation_score | score_money_flow | score_price_structure | smart_money_tag | cmf20_daily | rs_vs_vnindex_20 | vingroup_distortion_flag | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MSB | 64.53 | 89.61 | 84.29 | outside_fund_disclosure,ex_vingroup_quality | 0.51 | 0.21 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Moderately extended 19.2% |
| TVN | 59.96 | 83.89 | 84.29 | outside_fund_disclosure,ex_vingroup_quality | 0.56 | 0.41 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Extended 34.3% above MA20/50 |
| HHP | 57.63 | 73.52 | 70.03 | outside_fund_disclosure,ex_vingroup_quality | 0.31 | 0.16 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| VPL | 55.71 | 73.35 | 83.99 | outside_fund_disclosure,vingroup_distortion_risk | 0.28 | 0.10 | False | tier=Tier 2; CMF daily positive; OBV above MA20; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=24 |
| NAF | 53.74 | 56.38 | 79.41 | outside_fund_disclosure,ex_vingroup_quality | 0.37 | 0.07 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| MIG | 51.29 | 67.18 | 71.42 | outside_fund_disclosure,ex_vingroup_quality | 0.23 | 0.06 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (4/25); Inconsistent CMF daily vs weekly |
| PSI | 50.87 | 63.04 | 75.55 | outside_fund_disclosure,ex_vingroup_quality | 0.35 | 0.11 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Inconsistent CMF daily vs weekly; ADL diverging bearishly from price |
| TLD | 48.95 | 55.82 | 63.08 | outside_fund_disclosure,ex_vingroup_quality | 0.35 | 0.02 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| DL1 | 48.89 | 62.09 | 64.62 | outside_fund_disclosure,ex_vingroup_quality | 0.11 | 0.16 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; One-bar speculative spike risk |
| VND | 48.74 | 69.46 | 58.09 | outside_fund_disclosure,ex_vingroup_quality | -0.18 | 0.12 | False | tier=Tier 2; OBV above MA20; Up-volume dominates (20d); More HV up-days than down-days; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (5/25) |
| VCB | 48.41 | 60.04 | 58.83 | consensus_core,ex_vingroup_quality,ftse_beneficiary_candidate,policy_liquidity_sensitive | 0.08 | 0.06 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=88; Elevated distribution days (4/25); Inconsistent CMF daily vs weekly |
| VPI | 48.24 | 55.84 | 60.52 | outside_fund_disclosure,ex_vingroup_quality | 0.17 | 0.02 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| LPB | 47.89 | 47.33 | 70.79 | outside_fund_disclosure,ex_vingroup_quality | 0.02 | 0.17 | False | tier=Tier 2; OBV above MA20; Up-volume dominates (20d); More HV up-days than down-days; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| OGC | 47.87 | 60.32 | 68.52 | outside_fund_disclosure,ex_vingroup_quality | 0.35 | 0.14 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; ADL bearish divergence vs price; RS vs VNINDEX 20d positive; Holds MA50; context=56; Inconsistent CMF daily vs weekly; ADL diverging bearishly from price |
| PDR | 47.81 | 69.19 | 56.30 | outside_fund_disclosure,ex_vingroup_quality | 0.14 | 0.03 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (4/25); Inconsistent CMF daily vs weekly |
| C69 | 47.70 | 54.68 | 70.42 | outside_fund_disclosure,ex_vingroup_quality | 0.16 | 0.14 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; One-bar speculative spike risk |
| KDC | 47.18 | 61.81 | 62.88 | outside_fund_disclosure,ex_vingroup_quality | 0.48 | 0.22 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (5/25) |
| POM | 46.81 | 58.97 | 70.00 | outside_fund_disclosure,ex_vingroup_quality | — | 0.21 | False | tier=Tier 2; ADL bearish divergence vs price; Up-volume dominates (20d); More HV up-days than down-days; RS vs VNINDEX 20d positive; Holds MA50; context=56; ADL diverging bearishly from price; One-bar speculative spike risk |
| DXS | 46.22 | 49.59 | 76.05 | outside_fund_disclosure,ex_vingroup_quality | 0.02 | 0.07 | False | tier=Tier 2; Up-volume dominates (20d); More HV up-days than down-days; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (5/25) |

## Mixed / review (Tier 3, top 10)

| ticker | institutional_accumulation_score | score_money_flow | score_price_structure | smart_money_tag | cmf20_daily | rs_vs_vnindex_20 | vingroup_distortion_flag | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| APS | 45.89 | 57.43 | 65.39 | outside_fund_disclosure,ex_vingroup_quality | 0.27 | 0.16 | False | tier=Tier 3; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Inconsistent CMF daily vs weekly; ADL diverging bearishly from price |
| DCL | 45.45 | 60.59 | 44.07 | outside_fund_disclosure,ex_vingroup_quality | 0.31 | 0.03 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Volatility contraction + supportive CMF; context=56 |
| MST | 45.41 | 53.23 | 62.51 | outside_fund_disclosure,ex_vingroup_quality | 0.25 | 0.02 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA20; context=56; Elevated distribution days (4/25) |
| PCH | 45.13 | 43.21 | 66.55 | outside_fund_disclosure,ex_vingroup_quality | 0.12 | 0.02 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| PET | 44.40 | 55.27 | 61.86 | outside_fund_disclosure,ex_vingroup_quality | -0.02 | 0.05 | False | tier=Tier 3; OBV above MA20; Up-volume dominates (20d); More HV up-days than down-days; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (5/25) |
| PHR | 44.35 | 47.55 | 57.86 | outside_fund_disclosure,ex_vingroup_quality | -0.02 | 0.10 | False | tier=Tier 3; Up-volume dominates (20d); More HV up-days than down-days; Turnover acceleration vs 50d baseline; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| QNS | 42.92 | 52.75 | 62.82 | outside_fund_disclosure,ex_vingroup_quality | 0.45 | 0.09 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (4/25); ADL diverging bearishly from price |
| VC3 | 42.48 | 50.94 | 46.59 | outside_fund_disclosure,ex_vingroup_quality | 0.61 | -0.01 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; Volatility contraction + supportive CMF; context=56 |
| OCB | 42.39 | 53.53 | 58.19 | outside_fund_disclosure,ex_vingroup_quality | 0.14 | 0.05 | False | tier=Tier 3; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Inconsistent CMF daily vs weekly; ADL diverging bearishly from price |
| TCI | 42.19 | 40.35 | 68.50 | outside_fund_disclosure,ex_vingroup_quality | 0.00 | 0.10 | False | tier=Tier 3; CMF weekly positive; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (4/25) |

## Emerging accumulation (outside fund disclosure tags)

_Names with Tier 1–3 + constructive money flow but **no** consensus/commentary/selective fund tag — possible accumulation not visible in top holdings._

**Count:** 24 (showing top 15)
| ticker | institutional_accumulation_score | score_money_flow |
| --- | --- | --- |
| MSB | 64.53 | 89.61 |
| HHP | 57.63 | 73.52 |
| VPL | 55.71 | 73.35 |
| NAF | 53.74 | 56.38 |
| MIG | 51.29 | 67.18 |
| PSI | 50.87 | 63.04 |
| TLD | 48.95 | 55.82 |
| DL1 | 48.89 | 62.09 |
| VND | 48.74 | 69.46 |
| VPI | 48.24 | 55.84 |
| OGC | 47.87 | 60.32 |
| PDR | 47.81 | 69.19 |
| C69 | 47.70 | 54.68 |
| KDC | 47.18 | 61.81 |
| DXS | 46.22 | 49.59 |

## Fund-context names in scan (any tier)

**Count:** 23 (core / second_ring / commentary / selective)
| ticker | institutional_accumulation_score | score_money_flow |
| --- | --- | --- |
| VCB | 48.41 | 60.04 |
| GAS | 41.44 | 53.62 |
| ACB | 39.89 | 53.87 |
| CTG | 38.44 | 35.48 |
| BVH | 35.35 | 50.94 |
| TCB | 34.48 | 39.34 |
| POW | 34.21 | 40.00 |
| BID | 32.21 | 41.32 |
| VHM | 31.39 | 39.46 |
| GMD | 30.55 | 40.99 |
| GVR | 29.80 | 31.79 |
| FPT | 29.53 | 43.89 |
| STB | 28.79 | 27.58 |
| MSN | 25.51 | 31.84 |
| PNJ | 25.44 | 36.55 |
| HPG | 24.76 | 25.57 |
| SSI | 24.66 | 25.96 |
| MWG | 24.22 | 17.85 |
| VNM | 23.82 | 30.31 |
| NLG | 23.63 | 19.27 |

## Validation spot-checks

- **consensus_MBB:** tier=Reject score=23.5 money=21 vin_flag=False
- **consensus_CTG:** tier=Tier 3 score=38.4 money=35 vin_flag=False
- **consensus_MWG:** tier=Reject score=24.2 money=18 vin_flag=False
- **consensus_HPG:** tier=Reject score=24.8 money=26 vin_flag=False
- **consensus_GMD:** tier=Reject score=30.6 money=41 vin_flag=False
- **vin_VIC:** tier=Reject score=24.4 vin_distortion=False cmf_d=0.05548819446954442 cmf_w=0.042021394306274364
- **vin_VHM:** tier=Reject score=31.4 vin_distortion=False cmf_d=0.02896292116492522 cmf_w=0.07657347811113514

## Caveats

- Metrics are OHLCV-derived from repo CSVs; refresh `data/stocks` before relying on dates.
- RS vs sector index not computed (VNINDEX only).
- Vingroup names flagged; cap-weight VNINDEX may be skewed 2025–2026.
- Smart Money tags are priors, not buy signals.

---
*End of scan report.*