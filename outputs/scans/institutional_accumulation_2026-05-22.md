# Institutional Accumulation Scan

**Scan date:** 2026-05-22  
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
| Unknown | 4 | 26.69 |
| Ngân hàng | 3 | 30.29 |
| Xây dựng, xây lắp | 3 | 27.12 |
| Bia | 1 | 40.32 |
| Dược phẩm | 1 | 38.34 |
| Giấy | 1 | 39.37 |
| Hóa chất cơ bản - Sản phẩm nhựa, cao su, hóa chất | 1 | 32.89 |
| Khai thác quặng sắt và sản xuất thép | 1 | 26.73 |
| Sản phẩm thực phẩm | 1 | 27.5 |

## Top candidates (Tier 1)

_No Tier 1 names at current thresholds._

## Early accumulation (Tier 2)

| ticker | institutional_accumulation_score | score_money_flow | score_price_structure | smart_money_tag | cmf20_daily | rs_vs_vnindex_20 | vingroup_distortion_flag | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MSB | 61.13 | 87.73 | 83.27 | outside_fund_disclosure,ex_vingroup_quality | 0.42 | 0.13 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Moderately extended 16.2%; Elevated distribution days (4/25) |
| HHP | 57.40 | 75.46 | 66.58 | outside_fund_disclosure,ex_vingroup_quality | 0.32 | 0.13 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| VPL | 54.96 | 77.29 | 75.97 | outside_fund_disclosure,vingroup_distortion_risk | 0.28 | 0.09 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=24 |
| TVN | 54.33 | 72.64 | 79.45 | outside_fund_disclosure,ex_vingroup_quality | 0.47 | 0.24 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Moderately extended 23.1%; Elevated distribution days (4/25) |
| DCL | 53.11 | 66.43 | 63.51 | outside_fund_disclosure,ex_vingroup_quality | 0.46 | 0.06 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA20; context=56 |
| L40 | 52.18 | 60.55 | 68.18 | outside_fund_disclosure,ex_vingroup_quality | 0.48 | 0.10 | False | tier=Tier 2; CMF daily positive; OBV above MA20; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| VCB | 51.80 | 66.88 | 53.08 | consensus_core,ex_vingroup_quality,ftse_beneficiary_candidate,policy_liquidity_sensitive | 0.06 | 0.04 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=88; Inconsistent CMF daily vs weekly; ADL diverging bearishly from price |
| PCH | 51.63 | 56.03 | 72.35 | outside_fund_disclosure,ex_vingroup_quality | 0.26 | 0.04 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| C69 | 51.13 | 64.43 | 69.46 | outside_fund_disclosure,ex_vingroup_quality | 0.25 | 0.12 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; One-bar speculative spike risk |
| DL1 | 50.46 | 68.03 | 73.59 | outside_fund_disclosure,ex_vingroup_quality | 0.21 | 0.17 | False | tier=Tier 2; CMF daily positive; OBV above MA20; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=56; Moderately extended 17.2%; One-bar speculative spike risk |
| QNS | 50.38 | 63.19 | 66.72 | outside_fund_disclosure,ex_vingroup_quality | 0.39 | 0.07 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; ADL diverging bearishly from price |
| LPB | 50.05 | 55.79 | 73.87 | outside_fund_disclosure,ex_vingroup_quality | 0.08 | 0.11 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Inconsistent CMF daily vs weekly |
| IDJ | 49.07 | 60.47 | 72.62 | outside_fund_disclosure,ex_vingroup_quality | 0.36 | 0.13 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Inconsistent CMF daily vs weekly; ADL diverging bearishly from price |
| PSI | 48.73 | 69.49 | 59.17 | outside_fund_disclosure,ex_vingroup_quality | 0.33 | 0.02 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Inconsistent CMF daily vs weekly; ADL diverging bearishly from price |
| NAF | 47.97 | 53.19 | 71.71 | outside_fund_disclosure,ex_vingroup_quality | 0.28 | 0.01 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (4/25) |
| CTR | 47.20 | 68.42 | 63.74 | outside_fund_disclosure,ex_vingroup_quality | 0.49 | 0.06 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (4/25); Inconsistent CMF daily vs weekly |

## Mixed / review (Tier 3, top 10)

| ticker | institutional_accumulation_score | score_money_flow | score_price_structure | smart_money_tag | cmf20_daily | rs_vs_vnindex_20 | vingroup_distortion_flag | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BSR | 46.60 | 65.60 | 72.81 | outside_fund_disclosure,ex_vingroup_quality | 0.06 | 0.11 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; High distribution-day count (6/25); ADL diverging bearishly from price |
| DXS | 46.26 | 60.94 | 76.23 | outside_fund_disclosure,ex_vingroup_quality | 0.08 | 0.11 | False | tier=Tier 3; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; High distribution-day count (6/25); Inconsistent CMF daily vs weekly |
| APS | 45.99 | 67.93 | 65.76 | outside_fund_disclosure,ex_vingroup_quality | 0.36 | 0.09 | False | tier=Tier 3; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (5/25); Inconsistent CMF daily vs weekly |
| TLD | 45.80 | 55.70 | 51.99 | outside_fund_disclosure,ex_vingroup_quality | 0.37 | -0.01 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; OBV above MA20; Holds MA50; context=56 |
| POM | 45.64 | 53.79 | 84.29 | outside_fund_disclosure,ex_vingroup_quality | — | 0.15 | False | tier=Tier 3; ADL bearish divergence vs price; Up-volume dominates (20d); More HV up-days than down-days; RS vs VNINDEX 20d positive; Holds MA50; context=56; Moderately extended 19.4%; ADL diverging bearishly from price |
| HII | 45.35 | 52.01 | 63.93 | outside_fund_disclosure,ex_vingroup_quality | — | 0.09 | False | tier=Tier 3; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (4/25) |
| CDC | 44.61 | 52.13 | 62.86 | outside_fund_disclosure,ex_vingroup_quality | 0.61 | 0.17 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; One-bar speculative spike risk |
| VIX | 44.00 | 59.15 | 55.14 | outside_fund_disclosure,ex_vingroup_quality | -0.01 | 0.06 | False | tier=Tier 3; OBV above MA20; Up-volume dominates (20d); More HV up-days than down-days; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (5/25) |
| OIL | 43.92 | 65.55 | 47.31 | outside_fund_disclosure,ex_vingroup_quality | 0.14 | 0.02 | False | tier=Tier 3; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (4/25); Inconsistent CMF daily vs weekly |
| VC3 | 43.51 | 57.09 | 41.92 | outside_fund_disclosure,ex_vingroup_quality | 0.68 | -0.04 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; Up-volume dominates (20d); Volatility contraction + supportive CMF; context=56 |

## Emerging accumulation (outside fund disclosure tags)

_Names with Tier 1–3 + constructive money flow but **no** consensus/commentary/selective fund tag — possible accumulation not visible in top holdings._

**Count:** 34 (showing top 15)
| ticker | institutional_accumulation_score | score_money_flow |
| --- | --- | --- |
| HHP | 57.40 | 75.46 |
| VPL | 54.96 | 77.29 |
| DCL | 53.11 | 66.43 |
| L40 | 52.18 | 60.55 |
| PCH | 51.63 | 56.03 |
| C69 | 51.13 | 64.43 |
| QNS | 50.38 | 63.19 |
| LPB | 50.05 | 55.79 |
| IDJ | 49.07 | 60.47 |
| PSI | 48.73 | 69.49 |
| NAF | 47.97 | 53.19 |
| TLD | 45.80 | 55.70 |
| HII | 45.35 | 52.01 |
| CDC | 44.61 | 52.13 |
| VIX | 44.00 | 59.15 |

## Fund-context names in scan (any tier)

**Count:** 23 (core / second_ring / commentary / selective)
| ticker | institutional_accumulation_score | score_money_flow |
| --- | --- | --- |
| VCB | 51.80 | 66.88 |
| GAS | 41.34 | 61.82 |
| CTG | 39.44 | 49.05 |
| STB | 38.71 | 33.63 |
| GVR | 38.68 | 54.28 |
| BID | 35.94 | 53.91 |
| BVH | 35.32 | 44.18 |
| GMD | 33.02 | 47.79 |
| FPT | 32.38 | 48.98 |
| POW | 29.80 | 43.37 |
| TCB | 28.69 | 35.34 |
| MWG | 28.08 | 23.79 |
| VHM | 27.52 | 34.67 |
| VNM | 26.75 | 36.61 |
| HPG | 25.70 | 21.52 |
| ACB | 24.97 | 35.53 |
| SSI | 24.32 | 28.52 |
| MBB | 24.13 | 23.91 |
| MSN | 23.57 | 32.32 |
| NLG | 19.42 | 15.93 |

## Validation spot-checks

- **consensus_MBB:** tier=Reject score=24.1 money=24 vin_flag=False
- **consensus_CTG:** tier=Tier 3 score=39.4 money=49 vin_flag=False
- **consensus_MWG:** tier=Reject score=28.1 money=24 vin_flag=False
- **consensus_HPG:** tier=Reject score=25.7 money=22 vin_flag=False
- **consensus_GMD:** tier=Reject score=33.0 money=48 vin_flag=False
- **vin_VIC:** tier=Reject score=33.5 vin_distortion=False cmf_d=0.15856490660761807 cmf_w=0.0877216769708619
- **vin_VHM:** tier=Reject score=27.5 vin_distortion=False cmf_d=0.06219657951641325 cmf_w=0.07646745361481748

## Caveats

- Metrics are OHLCV-derived from repo CSVs; refresh `data/stocks` before relying on dates.
- RS vs sector index not computed (VNINDEX only).
- Vingroup names flagged; cap-weight VNINDEX may be skewed 2025–2026.
- Smart Money tags are priors, not buy signals.

---
*End of scan report.*