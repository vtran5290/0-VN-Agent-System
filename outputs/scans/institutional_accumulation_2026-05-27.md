# Institutional Accumulation Scan

**Scan date:** 2026-05-27  
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
| Unknown | 5 | 27.21 |
| Ngân hàng | 4 | 35.84 |
| Các công ty đầu cơ và phát triển bất động sản | 3 | 25.9 |
| Bia | 1 | 41.49 |
| Bán lẻ tổng hợp | 1 | 27.97 |
| Công ty chứng khoán | 1 | 30.6 |
| Giấy | 1 | 42.14 |
| Khai thác quặng sắt và sản xuất thép | 1 | 30.94 |
| Sản phẩm thực phẩm | 1 | 28.65 |
| Xây dựng, xây lắp | 1 | 26.43 |

## Top candidates (Tier 1)

_No Tier 1 names at current thresholds._

## Early accumulation (Tier 2)

| ticker | institutional_accumulation_score | score_money_flow | score_price_structure | smart_money_tag | cmf20_daily | rs_vs_vnindex_20 | vingroup_distortion_flag | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MSB | 63.65 | 87.30 | 84.29 | outside_fund_disclosure,ex_vingroup_quality | 0.47 | 0.18 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Moderately extended 19.1% |
| TVN | 59.52 | 82.75 | 84.29 | outside_fund_disclosure,ex_vingroup_quality | 0.60 | 0.42 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Extended 35.3% above MA20/50 |
| HHP | 58.29 | 74.88 | 70.55 | outside_fund_disclosure,ex_vingroup_quality | 0.34 | 0.16 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| VPL | 56.50 | 75.62 | 83.73 | outside_fund_disclosure,vingroup_distortion_risk | 0.30 | 0.11 | False | tier=Tier 2; CMF daily positive; OBV above MA20; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=24 |
| SSB | 52.98 | 62.85 | 67.93 | outside_fund_disclosure,ex_vingroup_quality | 0.59 | 0.06 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| NAF | 52.25 | 56.74 | 73.61 | outside_fund_disclosure,ex_vingroup_quality | 0.32 | 0.05 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| VCB | 51.84 | 64.09 | 57.03 | consensus_core,ex_vingroup_quality,ftse_beneficiary_candidate,policy_liquidity_sensitive | 0.07 | 0.05 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=88; Inconsistent CMF daily vs weekly; ADL diverging bearishly from price |
| DL1 | 51.22 | 68.67 | 64.04 | outside_fund_disclosure,ex_vingroup_quality | 0.11 | 0.14 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; One-bar speculative spike risk |
| C69 | 48.81 | 51.34 | 68.65 | outside_fund_disclosure,ex_vingroup_quality | 0.16 | 0.10 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| PDR | 48.81 | 66.22 | 63.89 | outside_fund_disclosure,ex_vingroup_quality | 0.22 | 0.04 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Inconsistent CMF daily vs weekly; ADL diverging bearishly from price |
| QNS | 48.74 | 55.57 | 71.22 | outside_fund_disclosure,ex_vingroup_quality | 0.46 | 0.09 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; ADL diverging bearishly from price |
| LPB | 48.22 | 54.53 | 70.79 | outside_fund_disclosure,ex_vingroup_quality | 0.05 | 0.15 | False | tier=Tier 2; OBV above MA20; Up-volume dominates (20d); More HV up-days than down-days; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (4/25) |
| VPI | 48.19 | 60.32 | 54.25 | outside_fund_disclosure,ex_vingroup_quality | 0.19 | 0.03 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| PSI | 47.73 | 60.02 | 68.44 | outside_fund_disclosure,ex_vingroup_quality | 0.32 | 0.05 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Inconsistent CMF daily vs weekly; ADL diverging bearishly from price |
| APS | 47.05 | 59.79 | 66.31 | outside_fund_disclosure,ex_vingroup_quality | 0.30 | 0.16 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Inconsistent CMF daily vs weekly; ADL diverging bearishly from price |
| DXS | 47.01 | 52.90 | 75.54 | outside_fund_disclosure,ex_vingroup_quality | 0.05 | 0.09 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (4/25); Inconsistent CMF daily vs weekly |
| VND | 46.94 | 67.47 | 54.36 | outside_fund_disclosure,ex_vingroup_quality | -0.11 | 0.08 | False | tier=Tier 2; OBV above MA20; Up-volume dominates (20d); More HV up-days than down-days; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (5/25) |
| PET | 46.86 | 54.27 | 74.85 | outside_fund_disclosure,ex_vingroup_quality | 0.01 | 0.06 | False | tier=Tier 2; OBV above MA20; ADL bearish divergence vs price; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (4/25); ADL diverging bearishly from price |
| TLD | 46.50 | 55.29 | 55.03 | outside_fund_disclosure,ex_vingroup_quality | 0.39 | 0.01 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |

## Mixed / review (Tier 3, top 10)

| ticker | institutional_accumulation_score | score_money_flow | score_price_structure | smart_money_tag | cmf20_daily | rs_vs_vnindex_20 | vingroup_distortion_flag | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| IDJ | 44.61 | 50.98 | 69.55 | outside_fund_disclosure,ex_vingroup_quality | 0.34 | 0.17 | False | tier=Tier 3; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Inconsistent CMF daily vs weekly; ADL diverging bearishly from price |
| DCL | 44.59 | 64.03 | 36.35 | outside_fund_disclosure,ex_vingroup_quality | 0.30 | 0.00 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Volatility contraction + supportive CMF; context=56 |
| HII | 43.88 | 46.47 | 66.22 | outside_fund_disclosure,ex_vingroup_quality | — | 0.12 | False | tier=Tier 3; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (4/25) |
| VC3 | 43.51 | 55.56 | 44.00 | outside_fund_disclosure,ex_vingroup_quality | 0.63 | -0.02 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; Up-volume dominates (20d); Volatility contraction + supportive CMF; context=56 |
| OCB | 43.44 | 52.67 | 63.08 | outside_fund_disclosure,ex_vingroup_quality | 0.17 | 0.04 | False | tier=Tier 3; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Inconsistent CMF daily vs weekly; ADL diverging bearishly from price |
| PCH | 43.43 | 42.69 | 61.16 | outside_fund_disclosure,ex_vingroup_quality | 0.07 | -0.01 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; More HV up-days than down-days; Holds MA50; Volatility contraction + supportive CMF; context=56 |
| CDC | 43.38 | 45.16 | 57.63 | outside_fund_disclosure,ex_vingroup_quality | 0.54 | 0.08 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA20; context=56 |
| POM | 43.26 | 58.04 | 70.00 | outside_fund_disclosure,ex_vingroup_quality | — | 0.16 | False | tier=Tier 3; ADL bearish divergence vs price; Up-volume dominates (20d); More HV up-days than down-days; RS vs VNINDEX 20d positive; Holds MA50; context=56; Moderately extended 15.0%; ADL diverging bearishly from price |
| PHR | 42.45 | 45.90 | 61.89 | outside_fund_disclosure,ex_vingroup_quality | 0.04 | 0.10 | False | tier=Tier 3; ADL bearish divergence vs price; Up-volume dominates (20d); More HV up-days than down-days; RS vs VNINDEX 20d positive; Holds MA50; context=56; ADL diverging bearishly from price |
| ACB | 42.07 | 53.98 | 65.99 | fund_commentary_mention,ex_vingroup_quality,policy_liquidity_sensitive | 0.10 | 0.07 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; ADL bearish divergence vs price; RS vs VNINDEX 20d positive; Holds MA50; context=66; High distribution-day count (9/25); ADL diverging bearishly from price |

## Emerging accumulation (outside fund disclosure tags)

_Names with Tier 1–3 + constructive money flow but **no** consensus/commentary/selective fund tag — possible accumulation not visible in top holdings._

**Count:** 25 (showing top 15)
| ticker | institutional_accumulation_score | score_money_flow |
| --- | --- | --- |
| MSB | 63.65 | 87.30 |
| HHP | 58.29 | 74.88 |
| VPL | 56.50 | 75.62 |
| SSB | 52.98 | 62.85 |
| NAF | 52.25 | 56.74 |
| DL1 | 51.22 | 68.67 |
| C69 | 48.81 | 51.34 |
| PDR | 48.81 | 66.22 |
| QNS | 48.74 | 55.57 |
| LPB | 48.22 | 54.53 |
| VPI | 48.19 | 60.32 |
| PSI | 47.73 | 60.02 |
| APS | 47.05 | 59.79 |
| DXS | 47.01 | 52.90 |
| VND | 46.94 | 67.47 |

## Fund-context names in scan (any tier)

**Count:** 23 (core / second_ring / commentary / selective)
| ticker | institutional_accumulation_score | score_money_flow |
| --- | --- | --- |
| VCB | 51.84 | 64.09 |
| ACB | 42.07 | 53.98 |
| CTG | 40.84 | 37.69 |
| GAS | 40.79 | 59.30 |
| STB | 36.94 | 30.31 |
| BVH | 35.43 | 51.14 |
| BID | 33.95 | 42.67 |
| POW | 33.09 | 41.32 |
| TCB | 32.35 | 37.35 |
| GMD | 32.32 | 43.39 |
| FPT | 32.17 | 46.25 |
| SSI | 28.98 | 26.87 |
| VHM | 28.88 | 29.57 |
| GVR | 27.97 | 33.14 |
| VNM | 26.85 | 33.68 |
| MSN | 26.50 | 34.13 |
| HPG | 25.19 | 26.71 |
| MWG | 24.44 | 18.43 |
| MBB | 23.77 | 22.47 |
| PNJ | 20.38 | 27.63 |

## Validation spot-checks

- **consensus_MBB:** tier=Reject score=23.8 money=22 vin_flag=False
- **consensus_CTG:** tier=Tier 3 score=40.8 money=38 vin_flag=False
- **consensus_MWG:** tier=Reject score=24.4 money=18 vin_flag=False
- **consensus_HPG:** tier=Reject score=25.2 money=27 vin_flag=False
- **consensus_GMD:** tier=Reject score=32.3 money=43 vin_flag=False
- **vin_VIC:** tier=Reject score=23.7 vin_distortion=False cmf_d=0.11479616701882982 cmf_w=0.044162400693808244
- **vin_VHM:** tier=Reject score=28.9 vin_distortion=False cmf_d=0.032193881406318625 cmf_w=0.031596213097591294

## Caveats

- Metrics are OHLCV-derived from repo CSVs; refresh `data/stocks` before relying on dates.
- RS vs sector index not computed (VNINDEX only).
- Vingroup names flagged; cap-weight VNINDEX may be skewed 2025–2026.
- Smart Money tags are priors, not buy signals.

---
*End of scan report.*