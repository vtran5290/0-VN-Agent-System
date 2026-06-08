# Institutional Accumulation Scan

**Scan date:** 2026-06-05  
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
| Unknown | 5 | 28.9 |
| Các công ty đầu cơ và phát triển bất động sản | 3 | 25.52 |
| Công ty chứng khoán | 2 | 29.64 |
| Ngân hàng | 2 | 33.82 |
| Sản phẩm thực phẩm | 2 | 29.09 |
| Xây dựng, xây lắp | 2 | 25.48 |
| Bia | 1 | 40.48 |
| Bảo hiểm tổng hợp | 1 | 39.52 |
| Dịch vụ vận tải | 1 | 27.65 |
| Giấy | 1 | 37.7 |
| Khai thác quặng sắt và sản xuất thép | 1 | 25.7 |

## Top candidates (Tier 1)

_No Tier 1 names at current thresholds._

## Early accumulation (Tier 2)

| ticker | institutional_accumulation_score | score_money_flow | score_price_structure | smart_money_tag | cmf20_daily | rs_vs_vnindex_20 | vingroup_distortion_flag | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MSB | 59.94 | 72.80 | 79.26 | outside_fund_disclosure,ex_vingroup_quality | 0.49 | 0.16 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| TCI | 56.55 | 60.19 | 84.29 | outside_fund_disclosure,ex_vingroup_quality | 0.11 | 0.14 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| KSF | 55.47 | 81.23 | 65.59 | outside_fund_disclosure,ex_vingroup_quality | 0.18 | 0.15 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; context=56; Elevated weekly distribution weeks (3/6); Inconsistent CMF daily vs weekly |
| KDC | 54.95 | 67.07 | 69.22 | outside_fund_disclosure,ex_vingroup_quality | 0.32 | 0.11 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| TVN | 54.95 | 73.98 | 81.56 | outside_fund_disclosure,ex_vingroup_quality | 0.43 | 0.30 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Moderately extended 21.6%; One-bar speculative spike risk |
| OCB | 53.60 | 74.45 | 71.51 | outside_fund_disclosure,ex_vingroup_quality | 0.23 | 0.14 | False | tier=Tier 2; CMF daily positive; OBV above MA20; ADL bearish divergence vs price; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (4/25); ADL diverging bearishly from price |
| KOS | 50.26 | 62.97 | 66.60 | outside_fund_disclosure,ex_vingroup_quality | 0.23 | 0.04 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (4/25) |
| VPL | 49.93 | 65.61 | 73.87 | outside_fund_disclosure,vingroup_distortion_risk | 0.33 | 0.03 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=24 |
| HQC | 49.26 | 54.29 | 66.25 | outside_fund_disclosure,ex_vingroup_quality | -0.09 | 0.12 | False | tier=Tier 2; OBV above MA20; Up-volume dominates (20d); Turnover acceleration vs 50d baseline; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| PSI | 48.87 | 55.56 | 78.56 | outside_fund_disclosure,ex_vingroup_quality | 0.22 | 0.09 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Inconsistent CMF daily vs weekly; ADL diverging bearishly from price |
| HNM | 48.71 | 52.58 | 66.60 | outside_fund_disclosure,ex_vingroup_quality | 0.30 | 0.08 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| C69 | 48.22 | 59.28 | 66.04 | outside_fund_disclosure,ex_vingroup_quality | 0.08 | 0.20 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; One-bar speculative spike risk |
| VND | 47.88 | 58.13 | 56.12 | outside_fund_disclosure,ex_vingroup_quality | -0.13 | 0.11 | False | tier=Tier 2; OBV above MA20; Up-volume dominates (20d); More HV up-days than down-days; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| F88 | 47.77 | 67.74 | 63.81 | outside_fund_disclosure,ex_vingroup_quality | -0.11 | 0.07 | False | tier=Tier 2; OBV above MA20; Up-volume dominates (20d); More HV up-days than down-days; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (5/25); Elevated weekly distribution weeks (3/6) |
| DL1 | 46.69 | 45.39 | 69.14 | outside_fund_disclosure,ex_vingroup_quality | 0.13 | 0.10 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| VVS | 46.43 | 57.51 | 74.62 | outside_fund_disclosure,ex_vingroup_quality | 0.08 | 0.12 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; High distribution-day count (6/25) |
| TLD | 46.40 | 54.03 | 64.96 | outside_fund_disclosure,ex_vingroup_quality | 0.43 | 0.04 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (4/25) |
| MST | 46.37 | 45.31 | 68.10 | outside_fund_disclosure,ex_vingroup_quality | 0.28 | 0.09 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| NAF | 46.32 | 53.98 | 70.47 | outside_fund_disclosure,ex_vingroup_quality | 0.34 | 0.10 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (5/25) |
| MIG | 46.24 | 62.12 | 60.28 | outside_fund_disclosure,ex_vingroup_quality | 0.31 | 0.05 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Volatility contraction + supportive CMF; context=56; Elevated distribution days (4/25); Inconsistent CMF daily vs weekly |

## Mixed / review (Tier 3, top 10)

| ticker | institutional_accumulation_score | score_money_flow | score_price_structure | smart_money_tag | cmf20_daily | rs_vs_vnindex_20 | vingroup_distortion_flag | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| THD | 52.65 | 78.54 | 84.29 | outside_fund_disclosure,ex_vingroup_quality | — | 3.60 | False | tier=Tier 3; CMF weekly positive; OBV above MA20; ADL bearish divergence vs price; RS vs VNINDEX 20d positive; Holds MA50; context=56; Extended 141.5% above MA20/50; ADL diverging bearishly from price |
| ACB | 52.59 | 75.36 | 74.53 | fund_commentary_mention,ex_vingroup_quality,policy_liquidity_sensitive | 0.25 | 0.19 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; ADL bearish divergence vs price; RS vs VNINDEX 20d positive; Holds MA50; context=66; High distribution-day count (6/25); ADL diverging bearishly from price |
| DRI | 46.14 | 41.04 | 79.93 | outside_fund_disclosure,ex_vingroup_quality | 0.07 | 0.08 | False | tier=Tier 3; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Inconsistent CMF daily vs weekly |
| VCB | 45.78 | 55.64 | 61.13 | consensus_core,ex_vingroup_quality,ftse_beneficiary_candidate,policy_liquidity_sensitive | 0.08 | 0.07 | False | tier=Tier 3; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=88; High distribution-day count (7/25); Inconsistent CMF daily vs weekly |
| PET | 45.60 | 42.96 | 77.13 | outside_fund_disclosure,ex_vingroup_quality | 0.00 | 0.07 | False | tier=Tier 3; OBV above MA20; Up-volume dominates (20d); More HV up-days than down-days; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (4/25) |
| QNS | 44.94 | 48.88 | 58.15 | outside_fund_disclosure,ex_vingroup_quality | 0.31 | 0.05 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| MBS | 44.81 | 47.99 | 65.76 | outside_fund_disclosure,ex_vingroup_quality | 0.08 | 0.06 | False | tier=Tier 3; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA20; context=56; Inconsistent CMF daily vs weekly |
| ABB | 44.76 | 44.90 | 71.47 | outside_fund_disclosure,ex_vingroup_quality | -0.05 | 0.09 | False | tier=Tier 3; OBV above MA20; ADL bearish divergence vs price; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=56; ADL diverging bearishly from price |
| BVB | 43.35 | 52.34 | 54.64 | outside_fund_disclosure,ex_vingroup_quality | 0.22 | 0.02 | False | tier=Tier 3; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Inconsistent CMF daily vs weekly |
| TTA | 42.96 | 57.96 | 53.06 | outside_fund_disclosure,ex_vingroup_quality | 0.42 | 0.02 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA20; context=56; Elevated distribution days (5/25) |

## Emerging accumulation (outside fund disclosure tags)

_Names with Tier 1–3 + constructive money flow but **no** consensus/commentary/selective fund tag — possible accumulation not visible in top holdings._

**Count:** 22 (showing top 15)
| ticker | institutional_accumulation_score | score_money_flow |
| --- | --- | --- |
| MSB | 59.94 | 72.80 |
| TCI | 56.55 | 60.19 |
| KSF | 55.47 | 81.23 |
| KDC | 54.95 | 67.07 |
| OCB | 53.60 | 74.45 |
| KOS | 50.26 | 62.97 |
| VPL | 49.93 | 65.61 |
| HQC | 49.26 | 54.29 |
| PSI | 48.87 | 55.56 |
| HNM | 48.71 | 52.58 |
| C69 | 48.22 | 59.28 |
| VND | 47.88 | 58.13 |
| TLD | 46.40 | 54.03 |
| NAF | 46.32 | 53.98 |
| MIG | 46.24 | 62.12 |

## Fund-context names in scan (any tier)

**Count:** 23 (core / second_ring / commentary / selective)
| ticker | institutional_accumulation_score | score_money_flow |
| --- | --- | --- |
| ACB | 52.59 | 75.36 |
| VCB | 45.78 | 55.64 |
| FPT | 41.39 | 49.64 |
| BVH | 41.12 | 44.54 |
| GAS | 38.04 | 39.16 |
| GMD | 37.08 | 32.25 |
| GVR | 33.31 | 32.33 |
| POW | 30.81 | 25.67 |
| STB | 30.12 | 30.88 |
| BID | 29.72 | 23.83 |
| MBB | 28.66 | 19.61 |
| PNJ | 28.58 | 32.27 |
| NLG | 27.34 | 27.37 |
| CTG | 26.80 | 15.56 |
| MWG | 24.60 | 25.03 |
| SSI | 24.38 | 19.07 |
| HPG | 23.38 | 16.69 |
| VHM | 23.24 | 29.18 |
| TCB | 22.84 | 19.80 |
| VNM | 20.67 | 25.39 |

## Validation spot-checks

- **consensus_MBB:** tier=Reject score=28.7 money=20 vin_flag=False
- **consensus_CTG:** tier=Reject score=26.8 money=16 vin_flag=False
- **consensus_MWG:** tier=Reject score=24.6 money=25 vin_flag=False
- **consensus_HPG:** tier=Reject score=23.4 money=17 vin_flag=False
- **consensus_GMD:** tier=Reject score=37.1 money=32 vin_flag=False
- **vin_VIC:** tier=Reject score=26.7 vin_distortion=False cmf_d=0.09108893656053636 cmf_w=0.07702626836532414
- **vin_VHM:** tier=Reject score=23.2 vin_distortion=False cmf_d=-0.09971116329105828 cmf_w=0.06429262410004344

## Caveats

- Metrics are OHLCV-derived from repo CSVs; refresh `data/stocks` before relying on dates.
- RS vs sector index not computed (VNINDEX only).
- Vingroup names flagged; cap-weight VNINDEX may be skewed 2025–2026.
- Smart Money tags are priors, not buy signals.

---
*End of scan report.*