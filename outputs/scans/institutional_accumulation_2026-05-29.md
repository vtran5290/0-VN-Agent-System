# Institutional Accumulation Scan

**Scan date:** 2026-05-29  
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
| Unknown | 4 | 27.25 |
| Các công ty đầu cơ và phát triển bất động sản | 2 | 24.67 |
| Bia | 1 | 41.18 |
| Bảo hiểm tổng hợp | 1 | 34.23 |
| Giấy | 1 | 40.78 |
| Khai thác quặng sắt và sản xuất thép | 1 | 30.93 |
| Ngân hàng | 1 | 32.0 |
| Sản phẩm thực phẩm | 1 | 27.12 |
| Xây dựng, xây lắp | 1 | 26.14 |

## Top candidates (Tier 1)

_No Tier 1 names at current thresholds._

## Early accumulation (Tier 2)

| ticker | institutional_accumulation_score | score_money_flow | score_price_structure | smart_money_tag | cmf20_daily | rs_vs_vnindex_20 | vingroup_distortion_flag | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MSB | 64.61 | 89.82 | 84.29 | outside_fund_disclosure,ex_vingroup_quality | 0.57 | 0.22 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Moderately extended 20.0% |
| TVN | 59.30 | 84.20 | 81.49 | outside_fund_disclosure,ex_vingroup_quality | 0.52 | 0.35 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Extended 28.9% above MA20/50 |
| HHP | 57.23 | 71.28 | 71.66 | outside_fund_disclosure,ex_vingroup_quality | 0.27 | 0.11 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| VPL | 56.28 | 73.07 | 86.42 | outside_fund_disclosure,vingroup_distortion_risk | 0.32 | 0.09 | False | tier=Tier 2; CMF daily positive; OBV above MA20; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=24 |
| NAF | 54.88 | 58.20 | 81.01 | outside_fund_disclosure,ex_vingroup_quality | 0.44 | 0.08 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| KSF | 52.48 | 80.59 | 56.33 | outside_fund_disclosure,ex_vingroup_quality | 0.18 | 0.01 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (5/25) |
| MIG | 52.08 | 71.26 | 68.72 | outside_fund_disclosure,ex_vingroup_quality | 0.25 | 0.05 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (4/25); Inconsistent CMF daily vs weekly |
| PSI | 49.49 | 62.63 | 71.17 | outside_fund_disclosure,ex_vingroup_quality | 0.28 | 0.07 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Inconsistent CMF daily vs weekly; ADL diverging bearishly from price |
| KDC | 48.67 | 67.20 | 60.92 | outside_fund_disclosure,ex_vingroup_quality | 0.38 | 0.14 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (5/25) |
| DL1 | 47.55 | 54.69 | 69.89 | outside_fund_disclosure,ex_vingroup_quality | 0.13 | 0.17 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; One-bar speculative spike risk |
| C69 | 47.54 | 54.53 | 70.08 | outside_fund_disclosure,ex_vingroup_quality | 0.12 | 0.13 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; One-bar speculative spike risk |
| VPI | 46.74 | 54.51 | 56.94 | outside_fund_disclosure,ex_vingroup_quality | 0.13 | 0.01 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| TLD | 46.26 | 51.78 | 58.95 | outside_fund_disclosure,ex_vingroup_quality | 0.32 | 0.01 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |

## Mixed / review (Tier 3, top 10)

| ticker | institutional_accumulation_score | score_money_flow | score_price_structure | smart_money_tag | cmf20_daily | rs_vs_vnindex_20 | vingroup_distortion_flag | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VCB | 46.92 | 60.00 | 59.29 | consensus_core,ex_vingroup_quality,ftse_beneficiary_candidate,policy_liquidity_sensitive | 0.08 | 0.03 | False | tier=Tier 3; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=88; Elevated distribution days (5/25); Inconsistent CMF daily vs weekly |
| OGC | 45.76 | 59.70 | 61.85 | outside_fund_disclosure,ex_vingroup_quality | 0.23 | 0.08 | False | tier=Tier 3; CMF daily positive; CMF daily/weekly conflict; ADL bearish divergence vs price; RS vs VNINDEX 20d positive; Holds MA50; context=56; Inconsistent CMF daily vs weekly; ADL diverging bearishly from price |
| MST | 44.67 | 49.59 | 56.23 | outside_fund_disclosure,ex_vingroup_quality | 0.26 | 0.01 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA20; context=56 |
| PCH | 44.38 | 43.16 | 63.91 | outside_fund_disclosure,ex_vingroup_quality | 0.11 | 0.00 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| VND | 43.77 | 66.69 | 44.09 | outside_fund_disclosure,ex_vingroup_quality | -0.22 | 0.04 | False | tier=Tier 3; OBV above MA20; Up-volume dominates (20d); More HV up-days than down-days; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (5/25) |
| POM | 42.45 | 61.76 | 62.06 | outside_fund_disclosure,ex_vingroup_quality | — | 0.23 | False | tier=Tier 3; ADL bearish divergence vs price; Up-volume dominates (20d); More HV up-days than down-days; RS vs VNINDEX 20d positive; Holds MA50; context=56; Moderately extended 16.8%; ADL diverging bearishly from price |
| PET | 42.04 | 52.26 | 66.08 | outside_fund_disclosure,ex_vingroup_quality | 0.00 | 0.05 | False | tier=Tier 3; OBV above MA20; ADL bearish divergence vs price; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (5/25); ADL diverging bearishly from price |
| CDC | 41.43 | 42.93 | 53.70 | outside_fund_disclosure,ex_vingroup_quality | 0.57 | 0.10 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; Up-volume dominates (20d); RS vs VNINDEX 20d positive; context=56 |
| OCB | 41.43 | 60.00 | 45.96 | outside_fund_disclosure,ex_vingroup_quality | 0.09 | 0.02 | False | tier=Tier 3; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (4/25); Inconsistent CMF daily vs weekly |
| TCI | 41.15 | 38.62 | 67.13 | outside_fund_disclosure,ex_vingroup_quality | 0.02 | 0.09 | False | tier=Tier 3; CMF weekly positive; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (4/25) |

## Emerging accumulation (outside fund disclosure tags)

_Names with Tier 1–3 + constructive money flow but **no** consensus/commentary/selective fund tag — possible accumulation not visible in top holdings._

**Count:** 20 (showing top 15)
| ticker | institutional_accumulation_score | score_money_flow |
| --- | --- | --- |
| MSB | 64.61 | 89.82 |
| HHP | 57.23 | 71.28 |
| VPL | 56.28 | 73.07 |
| NAF | 54.88 | 58.20 |
| KSF | 52.48 | 80.59 |
| MIG | 52.08 | 71.26 |
| PSI | 49.49 | 62.63 |
| KDC | 48.67 | 67.20 |
| DL1 | 47.55 | 54.69 |
| C69 | 47.54 | 54.53 |
| VPI | 46.74 | 54.51 |
| TLD | 46.26 | 51.78 |
| OGC | 45.76 | 59.70 |
| MST | 44.67 | 49.59 |
| VND | 43.77 | 66.69 |

## Fund-context names in scan (any tier)

**Count:** 23 (core / second_ring / commentary / selective)
| ticker | institutional_accumulation_score | score_money_flow |
| --- | --- | --- |
| VCB | 46.92 | 60.00 |
| ACB | 41.05 | 58.61 |
| GAS | 40.32 | 55.62 |
| TCB | 38.38 | 39.94 |
| BVH | 34.18 | 47.54 |
| CTG | 34.09 | 32.35 |
| POW | 34.02 | 37.50 |
| VHM | 33.82 | 43.91 |
| BID | 30.66 | 35.20 |
| GMD | 29.49 | 39.61 |
| GVR | 27.59 | 31.80 |
| HPG | 27.57 | 24.48 |
| PNJ | 27.43 | 35.79 |
| FPT | 26.41 | 36.52 |
| STB | 25.87 | 21.46 |
| MSN | 24.21 | 30.87 |
| SSI | 23.72 | 25.61 |
| VNM | 23.16 | 28.81 |
| MBB | 23.15 | 21.06 |
| NLG | 21.77 | 19.49 |

## Validation spot-checks

- **consensus_MBB:** tier=Reject score=23.1 money=21 vin_flag=False
- **consensus_CTG:** tier=Reject score=34.1 money=32 vin_flag=False
- **consensus_MWG:** tier=Reject score=21.6 money=17 vin_flag=False
- **consensus_HPG:** tier=Reject score=27.6 money=24 vin_flag=False
- **consensus_GMD:** tier=Reject score=29.5 money=40 vin_flag=False
- **vin_VIC:** tier=Reject score=25.5 vin_distortion=False cmf_d=0.12711298773059485 cmf_w=0.04253805087187159
- **vin_VHM:** tier=Reject score=33.8 vin_distortion=False cmf_d=0.04317532428150248 cmf_w=0.06544179663452289

## Caveats

- Metrics are OHLCV-derived from repo CSVs; refresh `data/stocks` before relying on dates.
- RS vs sector index not computed (VNINDEX only).
- Vingroup names flagged; cap-weight VNINDEX may be skewed 2025–2026.
- Smart Money tags are priors, not buy signals.

---
*End of scan report.*