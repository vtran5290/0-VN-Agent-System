# Institutional Accumulation Scan

**Scan date:** 2026-06-12  
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
| Unknown | 6 | 29.93 |
| Ngân hàng | 5 | 35.78 |
| Sản phẩm thực phẩm | 3 | 30.8 |
| Các công ty đầu cơ và phát triển bất động sản | 2 | 27.76 |
| Xây dựng, xây lắp | 2 | 27.44 |
| Bảo hiểm tổng hợp | 1 | 42.3 |
| Công ty chứng khoán | 1 | 27.22 |
| Giấy | 1 | 44.45 |
| Khai thác quặng sắt và sản xuất thép | 1 | 27.53 |

## Top candidates (Tier 1)

_No Tier 1 names at current thresholds._

## Early accumulation (Tier 2)

| ticker | institutional_accumulation_score | score_money_flow | score_price_structure | smart_money_tag | cmf20_daily | rs_vs_vnindex_20 | vingroup_distortion_flag | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ACB | 56.62 | 81.37 | 66.50 | fund_commentary_mention,ex_vingroup_quality,policy_liquidity_sensitive | 0.17 | 0.20 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; ADL bearish divergence vs price; RS vs VNINDEX 20d positive; Holds MA50; context=66; Elevated distribution days (4/25); ADL diverging bearishly from price |
| HSL | 56.56 | 77.57 | 80.71 | outside_fund_disclosure,ex_vingroup_quality | — | 0.46 | False | tier=Tier 2; Up-volume dominates (20d); More HV up-days than down-days; Turnover acceleration vs 50d baseline; RS vs VNINDEX 20d positive; Holds MA50; context=56; Extended 33.8% above MA20/50 |
| MSB | 55.93 | 69.07 | 70.00 | outside_fund_disclosure,ex_vingroup_quality | 0.46 | 0.15 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| HHP | 55.12 | 59.94 | 79.50 | outside_fund_disclosure,ex_vingroup_quality | 0.28 | 0.08 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| ABB | 54.35 | 60.25 | 76.34 | outside_fund_disclosure,ex_vingroup_quality | 0.13 | 0.17 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| SBG | 54.02 | 67.61 | 75.47 | outside_fund_disclosure,ex_vingroup_quality | 0.39 | 0.19 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; One-bar speculative spike risk |
| HNM | 53.85 | 61.80 | 72.46 | outside_fund_disclosure,ex_vingroup_quality | 0.35 | 0.20 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| DST | 53.75 | 73.90 | 75.69 | outside_fund_disclosure,ex_vingroup_quality | — | 1.51 | False | tier=Tier 2; OBV above MA20; Up-volume dominates (20d); More HV up-days than down-days; RS vs VNINDEX 20d positive; Holds MA50; context=56; Extended 67.4% above MA20/50 |
| BVB | 52.87 | 61.67 | 75.99 | outside_fund_disclosure,ex_vingroup_quality | 0.31 | 0.09 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Inconsistent CMF daily vs weekly |
| AMS | 52.74 | 70.57 | 65.14 | outside_fund_disclosure,ex_vingroup_quality | 0.50 | 0.07 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; context=56; Elevated distribution days (4/25) |
| OCB | 51.50 | 73.48 | 71.08 | outside_fund_disclosure,ex_vingroup_quality | 0.17 | 0.17 | False | tier=Tier 2; CMF daily positive; OBV above MA20; ADL bearish divergence vs price; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (5/25); ADL diverging bearishly from price |
| TVN | 51.19 | 62.92 | 75.71 | outside_fund_disclosure,ex_vingroup_quality | 0.42 | 0.23 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (5/25) |
| MST | 51.16 | 53.56 | 74.03 | outside_fund_disclosure,ex_vingroup_quality | 0.42 | 0.22 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| VC3 | 49.88 | 49.01 | 75.62 | outside_fund_disclosure,ex_vingroup_quality | 0.70 | 0.08 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| TCI | 48.46 | 55.43 | 80.70 | outside_fund_disclosure,ex_vingroup_quality | 0.04 | 0.13 | False | tier=Tier 2; CMF weekly positive; OBV above MA20; Turnover acceleration vs 50d baseline; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (4/25); One-bar speculative spike risk |
| MIG | 48.28 | 57.45 | 73.87 | outside_fund_disclosure,ex_vingroup_quality | 0.38 | 0.11 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA20; context=56; Elevated distribution days (4/25); Inconsistent CMF daily vs weekly |
| UNI | 48.03 | 81.22 | 40.74 | outside_fund_disclosure,ex_vingroup_quality | — | -0.01 | False | tier=Tier 2; OBV above MA20; Up-volume dominates (20d); Turnover acceleration vs 50d baseline; context=56; Elevated distribution days (4/25); Elevated weekly distribution weeks (3/6) |
| C69 | 47.77 | 56.21 | 66.90 | outside_fund_disclosure,ex_vingroup_quality | 0.12 | 0.12 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (4/25) |
| DL1 | 47.72 | 52.40 | 63.30 | outside_fund_disclosure,ex_vingroup_quality | 0.03 | 0.05 | False | tier=Tier 2; OBV above MA20; Up-volume dominates (20d); More HV up-days than down-days; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| HQC | 47.47 | 59.19 | 61.79 | outside_fund_disclosure,ex_vingroup_quality | 0.03 | 0.14 | False | tier=Tier 2; OBV above MA20; ADL bearish divergence vs price; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=56; ADL diverging bearishly from price |

## Mixed / review (Tier 3, top 10)

| ticker | institutional_accumulation_score | score_money_flow | score_price_structure | smart_money_tag | cmf20_daily | rs_vs_vnindex_20 | vingroup_distortion_flag | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| THD | 52.63 | 78.49 | 84.29 | outside_fund_disclosure,ex_vingroup_quality | — | 2.04 | False | tier=Tier 3; CMF weekly positive; OBV above MA20; ADL bearish divergence vs price; RS vs VNINDEX 20d positive; Holds MA50; context=56; Extended 129.7% above MA20/50; ADL diverging bearishly from price |
| AGG | 47.73 | 64.28 | 74.07 | outside_fund_disclosure,ex_vingroup_quality | 0.73 | 0.11 | False | tier=Tier 3; CMF daily positive; OBV above MA20; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (5/25); High weekly distribution weeks (4/6) |
| PSI | 45.55 | 51.88 | 71.69 | outside_fund_disclosure,ex_vingroup_quality | 0.21 | 0.10 | False | tier=Tier 3; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Inconsistent CMF daily vs weekly; ADL diverging bearishly from price |
| VIW | 45.52 | 66.65 | 60.13 | outside_fund_disclosure,ex_vingroup_quality | 0.10 | 0.14 | False | tier=Tier 3; CMF daily positive; OBV above MA20; ADL bearish divergence vs price; RS vs VNINDEX 20d positive; Holds MA20; context=56; Elevated distribution days (4/25); Elevated weekly distribution weeks (3/6) |
| VJC | 45.36 | 47.51 | 84.39 | outside_fund_disclosure,ex_vingroup_quality | 0.28 | 0.12 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; High distribution-day count (6/25) |
| TPB | 45.22 | 60.82 | 57.24 | outside_fund_disclosure,ex_vingroup_quality | -0.03 | 0.11 | False | tier=Tier 3; OBV above MA20; Up-volume dominates (20d); More HV up-days than down-days; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (5/25) |
| VPL | 44.92 | 57.24 | 67.30 | outside_fund_disclosure,vingroup_distortion_risk | 0.36 | 0.05 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Volatility contraction + supportive CMF; context=24 |
| DLG | 44.79 | 55.55 | 57.14 | outside_fund_disclosure,ex_vingroup_quality | -0.00 | 0.09 | False | tier=Tier 3; OBV above MA20; Up-volume dominates (20d); More HV up-days than down-days; RS vs VNINDEX 20d positive; Holds MA20; context=56; Elevated distribution days (4/25) |
| NVB | 44.63 | 55.37 | 73.97 | outside_fund_disclosure,ex_vingroup_quality | 0.17 | 0.25 | False | tier=Tier 3; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Inconsistent CMF daily vs weekly; ADL diverging bearishly from price |
| VVS | 44.15 | 50.85 | 66.95 | outside_fund_disclosure,ex_vingroup_quality | 0.12 | 0.14 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Volatility contraction + supportive CMF; context=56; Elevated distribution days (5/25) |

## Emerging accumulation (outside fund disclosure tags)

_Names with Tier 1–3 + constructive money flow but **no** consensus/commentary/selective fund tag — possible accumulation not visible in top holdings._

**Count:** 25 (showing top 15)
| ticker | institutional_accumulation_score | score_money_flow |
| --- | --- | --- |
| MSB | 55.93 | 69.07 |
| HHP | 55.12 | 59.94 |
| ABB | 54.35 | 60.25 |
| SBG | 54.02 | 67.61 |
| HNM | 53.85 | 61.80 |
| BVB | 52.87 | 61.67 |
| AMS | 52.74 | 70.57 |
| TVN | 51.19 | 62.92 |
| MST | 51.16 | 53.56 |
| VC3 | 49.88 | 49.01 |
| MIG | 48.28 | 57.45 |
| UNI | 48.03 | 81.22 |
| C69 | 47.77 | 56.21 |
| DL1 | 47.72 | 52.40 |
| HQC | 47.47 | 59.19 |

## Fund-context names in scan (any tier)

**Count:** 23 (core / second_ring / commentary / selective)
| ticker | institutional_accumulation_score | score_money_flow |
| --- | --- | --- |
| ACB | 56.62 | 81.37 |
| VCB | 41.85 | 44.44 |
| FPT | 39.06 | 38.69 |
| BVH | 39.04 | 45.95 |
| STB | 33.77 | 29.08 |
| GMD | 32.56 | 32.41 |
| GAS | 31.24 | 26.09 |
| POW | 30.87 | 22.79 |
| MWG | 28.88 | 25.31 |
| MBB | 28.75 | 24.10 |
| KDH | 28.24 | 27.22 |
| GVR | 27.55 | 25.62 |
| VNM | 25.35 | 24.03 |
| PNJ | 25.29 | 24.05 |
| BID | 24.89 | 19.50 |
| NLG | 24.33 | 29.66 |
| CTG | 22.97 | 14.67 |
| HPG | 22.75 | 15.03 |
| VHM | 22.69 | 29.40 |
| TCB | 22.10 | 19.24 |

## Validation spot-checks

- **consensus_MBB:** tier=Reject score=28.8 money=24 vin_flag=False
- **consensus_CTG:** tier=Reject score=23.0 money=15 vin_flag=False
- **consensus_MWG:** tier=Reject score=28.9 money=25 vin_flag=False
- **consensus_HPG:** tier=Reject score=22.8 money=15 vin_flag=False
- **consensus_GMD:** tier=Reject score=32.6 money=32 vin_flag=False
- **vin_VIC:** tier=Reject score=17.7 vin_distortion=False cmf_d=-0.046479364675297646 cmf_w=0.09133129865469591
- **vin_VHM:** tier=Reject score=22.7 vin_distortion=False cmf_d=-0.1446493845462637 cmf_w=0.08022156838012838

## Caveats

- Metrics are OHLCV-derived from repo CSVs; refresh `data/stocks` before relying on dates.
- RS vs sector index not computed (VNINDEX only).
- Vingroup names flagged; cap-weight VNINDEX may be skewed 2025–2026.
- Smart Money tags are priors, not buy signals.

---
*End of scan report.*