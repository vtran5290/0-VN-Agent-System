# Institutional Accumulation Scan

**Scan date:** 2026-05-26  
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
| Unknown | 5 | 27.25 |
| Các công ty đầu cơ và phát triển bất động sản | 4 | 26.44 |
| Ngân hàng | 3 | 34.44 |
| Bia | 1 | 38.69 |
| Bán lẻ tổng hợp | 1 | 27.84 |
| Dược phẩm | 1 | 36.15 |
| Giấy | 1 | 42.5 |
| Khai thác quặng sắt và sản xuất thép | 1 | 30.25 |
| Sản phẩm thực phẩm | 1 | 28.68 |
| Xây dựng, xây lắp | 1 | 26.5 |

## Top candidates (Tier 1)

_No Tier 1 names at current thresholds._

## Early accumulation (Tier 2)

| ticker | institutional_accumulation_score | score_money_flow | score_price_structure | smart_money_tag | cmf20_daily | rs_vs_vnindex_20 | vingroup_distortion_flag | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MSB | 61.79 | 82.45 | 84.20 | outside_fund_disclosure,ex_vingroup_quality | 0.45 | 0.16 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Moderately extended 17.0% |
| VPL | 58.17 | 77.09 | 87.70 | outside_fund_disclosure,vingroup_distortion_risk | 0.27 | 0.14 | False | tier=Tier 2; CMF daily positive; OBV above MA20; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=24 |
| VCB | 58.16 | 75.48 | 48.69 | consensus_core,ex_vingroup_quality,ftse_beneficiary_candidate,policy_liquidity_sensitive | -0.00 | 0.02 | False | tier=Tier 2; OBV above MA20; Up-volume dominates (20d); More HV up-days than down-days; RS vs VNINDEX 20d positive; Holds MA50; context=88 |
| HHP | 58.03 | 74.21 | 70.54 | outside_fund_disclosure,ex_vingroup_quality | 0.36 | 0.18 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| TVN | 56.25 | 80.45 | 84.29 | outside_fund_disclosure,ex_vingroup_quality | 0.56 | 0.42 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Extended 34.1% above MA20/50; Elevated distribution days (4/25) |
| QNS | 50.55 | 60.36 | 71.19 | outside_fund_disclosure,ex_vingroup_quality | 0.44 | 0.09 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; ADL diverging bearishly from price |
| DCL | 50.35 | 69.50 | 49.51 | outside_fund_disclosure,ex_vingroup_quality | 0.33 | 0.02 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA20; context=56 |
| C69 | 50.10 | 53.45 | 70.40 | outside_fund_disclosure,ex_vingroup_quality | 0.14 | 0.11 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| DL1 | 50.10 | 67.45 | 61.67 | outside_fund_disclosure,ex_vingroup_quality | 0.09 | 0.12 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; One-bar speculative spike risk |
| NAF | 49.95 | 51.05 | 73.10 | outside_fund_disclosure,ex_vingroup_quality | 0.27 | 0.02 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| PSI | 49.47 | 60.58 | 73.88 | outside_fund_disclosure,ex_vingroup_quality | 0.33 | 0.07 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Inconsistent CMF daily vs weekly; ADL diverging bearishly from price |
| PDR | 49.26 | 65.37 | 66.63 | outside_fund_disclosure,ex_vingroup_quality | 0.25 | 0.05 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Inconsistent CMF daily vs weekly; ADL diverging bearishly from price |
| VC3 | 48.47 | 60.87 | 54.50 | outside_fund_disclosure,ex_vingroup_quality | 0.67 | -0.01 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; Holds MA50; Volatility contraction + supportive CMF; context=56 |
| DXS | 48.35 | 61.29 | 74.64 | outside_fund_disclosure,ex_vingroup_quality | 0.08 | 0.14 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (5/25); Inconsistent CMF daily vs weekly |
| LPB | 48.01 | 53.29 | 70.00 | outside_fund_disclosure,ex_vingroup_quality | 0.09 | 0.16 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Inconsistent CMF daily vs weekly |
| VPI | 47.63 | 62.60 | 49.15 | outside_fund_disclosure,ex_vingroup_quality | 0.22 | 0.02 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| IDJ | 46.79 | 54.02 | 73.23 | outside_fund_disclosure,ex_vingroup_quality | 0.35 | 0.17 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Inconsistent CMF daily vs weekly; ADL diverging bearishly from price |
| TLD | 46.30 | 54.06 | 55.98 | outside_fund_disclosure,ex_vingroup_quality | 0.39 | 0.01 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| PET | 46.23 | 55.16 | 77.10 | outside_fund_disclosure,ex_vingroup_quality | 0.04 | 0.10 | False | tier=Tier 2; OBV above MA20; ADL bearish divergence vs price; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (5/25); ADL diverging bearishly from price |

## Mixed / review (Tier 3, top 10)

| ticker | institutional_accumulation_score | score_money_flow | score_price_structure | smart_money_tag | cmf20_daily | rs_vs_vnindex_20 | vingroup_distortion_flag | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| APS | 45.56 | 60.95 | 68.01 | outside_fund_disclosure,ex_vingroup_quality | 0.32 | 0.16 | False | tier=Tier 3; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (4/25); Inconsistent CMF daily vs weekly |
| GAS | 45.29 | 63.88 | 55.49 | fund_commentary_mention,ex_vingroup_quality,infrastructure_domestic_demand_aligned | -0.00 | 0.06 | False | tier=Tier 3; OBV above MA20; Up-volume dominates (20d); More HV up-days than down-days; RS vs VNINDEX 20d positive; Holds MA50; context=66; High distribution-day count (8/25) |
| VND | 45.25 | 60.98 | 57.12 | outside_fund_disclosure,ex_vingroup_quality | -0.07 | 0.11 | False | tier=Tier 3; Up-volume dominates (20d); More HV up-days than down-days; Turnover acceleration vs 50d baseline; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (5/25) |
| DRI | 44.97 | 45.63 | 62.69 | outside_fund_disclosure,ex_vingroup_quality | 0.02 | 0.07 | False | tier=Tier 3; OBV above MA20; Up-volume dominates (20d); More HV up-days than down-days; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| PHR | 44.61 | 50.95 | 62.74 | outside_fund_disclosure,ex_vingroup_quality | 0.04 | 0.11 | False | tier=Tier 3; OBV above MA20; ADL bearish divergence vs price; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=56; ADL diverging bearishly from price |
| VIX | 44.51 | 51.20 | 67.78 | outside_fund_disclosure,ex_vingroup_quality | -0.01 | 0.10 | False | tier=Tier 3; OBV above MA20; Up-volume dominates (20d); Turnover acceleration vs 50d baseline; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (5/25) |
| HII | 44.19 | 48.17 | 65.02 | outside_fund_disclosure,ex_vingroup_quality | — | 0.12 | False | tier=Tier 3; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (4/25) |
| SSB | 44.15 | 54.06 | 56.87 | outside_fund_disclosure,ex_vingroup_quality | 0.52 | 0.04 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (4/25) |
| L40 | 43.82 | 50.85 | 58.33 | outside_fund_disclosure,ex_vingroup_quality | 0.41 | 0.05 | False | tier=Tier 3; CMF daily positive; CMF daily/weekly conflict; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=56; Inconsistent CMF daily vs weekly |
| CTR | 43.74 | 66.04 | 60.28 | outside_fund_disclosure,ex_vingroup_quality | 0.48 | 0.04 | False | tier=Tier 3; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (5/25); Inconsistent CMF daily vs weekly |

## Emerging accumulation (outside fund disclosure tags)

_Names with Tier 1–3 + constructive money flow but **no** consensus/commentary/selective fund tag — possible accumulation not visible in top holdings._

**Count:** 27 (showing top 15)
| ticker | institutional_accumulation_score | score_money_flow |
| --- | --- | --- |
| MSB | 61.79 | 82.45 |
| VPL | 58.17 | 77.09 |
| HHP | 58.03 | 74.21 |
| QNS | 50.55 | 60.36 |
| DCL | 50.35 | 69.50 |
| C69 | 50.10 | 53.45 |
| DL1 | 50.10 | 67.45 |
| NAF | 49.95 | 51.05 |
| PSI | 49.47 | 60.58 |
| PDR | 49.26 | 65.37 |
| VC3 | 48.47 | 60.87 |
| LPB | 48.01 | 53.29 |
| VPI | 47.63 | 62.60 |
| IDJ | 46.79 | 54.02 |
| TLD | 46.30 | 54.06 |

## Fund-context names in scan (any tier)

**Count:** 23 (core / second_ring / commentary / selective)
| ticker | institutional_accumulation_score | score_money_flow |
| --- | --- | --- |
| VCB | 58.16 | 75.48 |
| GAS | 45.29 | 63.88 |
| CTG | 38.13 | 37.89 |
| STB | 37.97 | 31.93 |
| ACB | 36.77 | 45.64 |
| TCB | 35.68 | 38.56 |
| GVR | 35.61 | 38.93 |
| FPT | 35.53 | 51.47 |
| BVH | 35.28 | 48.76 |
| GMD | 35.20 | 47.21 |
| BID | 34.25 | 43.06 |
| POW | 31.60 | 40.73 |
| VNM | 29.29 | 35.93 |
| SSI | 28.07 | 27.02 |
| MSN | 27.00 | 31.14 |
| VHM | 26.59 | 33.15 |
| HPG | 25.28 | 26.96 |
| MBB | 24.67 | 24.81 |
| MWG | 24.30 | 18.06 |
| NLG | 20.16 | 17.27 |

## Validation spot-checks

- **consensus_MBB:** tier=Reject score=24.7 money=25 vin_flag=False
- **consensus_CTG:** tier=Tier 3 score=38.1 money=38 vin_flag=False
- **consensus_MWG:** tier=Reject score=24.3 money=18 vin_flag=False
- **consensus_HPG:** tier=Reject score=25.3 money=27 vin_flag=False
- **consensus_GMD:** tier=Reject score=35.2 money=47 vin_flag=False
- **vin_VIC:** tier=Reject score=24.5 vin_distortion=False cmf_d=0.07673589077830957 cmf_w=0.04096068592294866
- **vin_VHM:** tier=Reject score=26.6 vin_distortion=False cmf_d=0.04288837008981866 cmf_w=0.04534525103143513

## Caveats

- Metrics are OHLCV-derived from repo CSVs; refresh `data/stocks` before relying on dates.
- RS vs sector index not computed (VNINDEX only).
- Vingroup names flagged; cap-weight VNINDEX may be skewed 2025–2026.
- Smart Money tags are priors, not buy signals.

---
*End of scan report.*