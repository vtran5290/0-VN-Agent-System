# Institutional Accumulation Scan

**Scan date:** 2026-05-21  
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
| Unknown | 4 | 26.38 |
| Ngân hàng | 3 | 30.28 |
| Xây dựng, xây lắp | 3 | 25.66 |
| Công ty chứng khoán | 1 | 25.79 |
| Dược phẩm | 1 | 34.55 |
| Giấy | 1 | 37.62 |
| Hóa chất cơ bản - Sản phẩm nhựa, cao su, hóa chất | 1 | 32.48 |
| Khai thác quặng sắt và sản xuất thép | 1 | 24.69 |
| Sản phẩm thực phẩm | 1 | 27.59 |
| Thăm dò và sản xuất dầu khí | 1 | 46.18 |

## Top candidates (Tier 1)

_No Tier 1 names at current thresholds._

## Early accumulation (Tier 2)

| ticker | institutional_accumulation_score | score_money_flow | score_price_structure | smart_money_tag | cmf20_daily | rs_vs_vnindex_20 | vingroup_distortion_flag | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MSB | 63.70 | 88.38 | 82.98 | outside_fund_disclosure,ex_vingroup_quality | 0.37 | 0.13 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Moderately extended 17.3% |
| VPL | 53.78 | 76.87 | 72.32 | outside_fund_disclosure,vingroup_distortion_risk | 0.24 | 0.06 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=24 |
| HHP | 53.75 | 74.68 | 64.89 | outside_fund_disclosure,ex_vingroup_quality | 0.31 | 0.15 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; One-bar speculative spike risk |
| BSR | 52.35 | 70.44 | 78.22 | outside_fund_disclosure,ex_vingroup_quality | 0.08 | 0.14 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (5/25); ADL diverging bearishly from price |
| VCB | 51.36 | 66.91 | 51.47 | consensus_core,ex_vingroup_quality,ftse_beneficiary_candidate,policy_liquidity_sensitive | 0.05 | 0.05 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=88; Inconsistent CMF daily vs weekly; ADL diverging bearishly from price |
| LPB | 50.34 | 56.63 | 73.78 | outside_fund_disclosure,ex_vingroup_quality | 0.07 | 0.12 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Inconsistent CMF daily vs weekly |
| DL1 | 49.98 | 67.28 | 72.90 | outside_fund_disclosure,ex_vingroup_quality | 0.13 | 0.14 | False | tier=Tier 2; CMF daily positive; OBV above MA20; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=56; Moderately extended 15.5%; One-bar speculative spike risk |
| L40 | 49.96 | 58.91 | 62.47 | outside_fund_disclosure,ex_vingroup_quality | 0.48 | 0.08 | False | tier=Tier 2; CMF daily positive; OBV above MA20; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| PCH | 49.46 | 52.33 | 69.63 | outside_fund_disclosure,ex_vingroup_quality | 0.22 | 0.03 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| PSI | 49.24 | 69.94 | 60.35 | outside_fund_disclosure,ex_vingroup_quality | 0.34 | 0.02 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Inconsistent CMF daily vs weekly; ADL diverging bearishly from price |
| QNS | 49.05 | 63.55 | 61.50 | outside_fund_disclosure,ex_vingroup_quality | 0.35 | 0.04 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; ADL diverging bearishly from price |
| CDC | 48.70 | 55.72 | 62.29 | outside_fund_disclosure,ex_vingroup_quality | 0.58 | 0.11 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| TVN | 48.67 | 57.50 | 68.37 | outside_fund_disclosure,ex_vingroup_quality | 0.22 | 0.07 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (4/25) |
| VIX | 48.62 | 62.77 | 61.03 | outside_fund_disclosure,ex_vingroup_quality | -0.00 | 0.07 | False | tier=Tier 2; OBV above MA20; Up-volume dominates (20d); More HV up-days than down-days; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (4/25) |
| DCL | 47.93 | 57.90 | 56.61 | outside_fund_disclosure,ex_vingroup_quality | 0.43 | 0.03 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA20; context=56 |
| HII | 47.27 | 59.03 | 61.28 | outside_fund_disclosure,ex_vingroup_quality | — | 0.08 | False | tier=Tier 2; Up-volume dominates (20d); Turnover acceleration vs 50d baseline; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (4/25) |
| CTR | 46.83 | 67.72 | 63.35 | outside_fund_disclosure,ex_vingroup_quality | 0.43 | 0.06 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (4/25); Inconsistent CMF daily vs weekly |

## Mixed / review (Tier 3, top 10)

| ticker | institutional_accumulation_score | score_money_flow | score_price_structure | smart_money_tag | cmf20_daily | rs_vs_vnindex_20 | vingroup_distortion_flag | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PVP | 47.42 | 60.94 | 80.36 | outside_fund_disclosure,ex_vingroup_quality | 0.23 | 0.17 | False | tier=Tier 3; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (5/25); Inconsistent CMF daily vs weekly |
| APS | 45.96 | 68.96 | 64.28 | outside_fund_disclosure,ex_vingroup_quality | 0.38 | 0.08 | False | tier=Tier 3; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (5/25); Inconsistent CMF daily vs weekly |
| TCO | 45.72 | 54.06 | 68.22 | outside_fund_disclosure,ex_vingroup_quality | 0.31 | 0.10 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (5/25) |
| PHR | 45.45 | 61.15 | 66.19 | outside_fund_disclosure,ex_vingroup_quality | 0.07 | 0.09 | False | tier=Tier 3; CMF daily positive; OBV above MA20; ADL bearish divergence vs price; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (5/25); ADL diverging bearishly from price |
| VPI | 45.45 | 61.97 | 42.24 | outside_fund_disclosure,ex_vingroup_quality | 0.12 | -0.05 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; OBV above MA20; Holds MA50; Volatility contraction + supportive CMF; context=56 |
| DXS | 45.44 | 59.25 | 68.74 | outside_fund_disclosure,ex_vingroup_quality | 0.03 | 0.07 | False | tier=Tier 3; OBV above MA20; Up-volume dominates (20d); More HV up-days than down-days; RS vs VNINDEX 20d positive; Holds MA50; context=56; High distribution-day count (6/25) |
| PIV | 45.08 | 56.76 | 47.95 | outside_fund_disclosure,ex_vingroup_quality | 0.37 | -0.01 | False | tier=Tier 3; CMF daily positive; OBV above MA20; Up-volume dominates (20d); Holds MA50; Volatility contraction + supportive CMF; context=56 |
| IDJ | 45.06 | 60.24 | 67.19 | outside_fund_disclosure,ex_vingroup_quality | 0.32 | 0.09 | False | tier=Tier 3; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (4/25); Inconsistent CMF daily vs weekly |
| OIL | 44.78 | 65.91 | 49.91 | outside_fund_disclosure,ex_vingroup_quality | 0.15 | 0.03 | False | tier=Tier 3; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (4/25); Inconsistent CMF daily vs weekly |
| NAF | 44.63 | 48.82 | 65.69 | outside_fund_disclosure,ex_vingroup_quality | 0.23 | -0.01 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; OBV above MA20; Holds MA50; Volatility contraction + supportive CMF; context=56; Elevated distribution days (4/25) |

## Emerging accumulation (outside fund disclosure tags)

_Names with Tier 1–3 + constructive money flow but **no** consensus/commentary/selective fund tag — possible accumulation not visible in top holdings._

**Count:** 34 (showing top 15)
| ticker | institutional_accumulation_score | score_money_flow |
| --- | --- | --- |
| MSB | 63.70 | 88.38 |
| VPL | 53.78 | 76.87 |
| HHP | 53.75 | 74.68 |
| LPB | 50.34 | 56.63 |
| L40 | 49.96 | 58.91 |
| PCH | 49.46 | 52.33 |
| PSI | 49.24 | 69.94 |
| QNS | 49.05 | 63.55 |
| CDC | 48.70 | 55.72 |
| TVN | 48.67 | 57.50 |
| VIX | 48.62 | 62.77 |
| DCL | 47.93 | 57.90 |
| HII | 47.27 | 59.03 |
| TCO | 45.72 | 54.06 |
| VPI | 45.45 | 61.97 |

## Fund-context names in scan (any tier)

**Count:** 23 (core / second_ring / commentary / selective)
| ticker | institutional_accumulation_score | score_money_flow |
| --- | --- | --- |
| VCB | 51.36 | 66.91 |
| GAS | 41.89 | 61.03 |
| STB | 41.24 | 34.23 |
| GVR | 41.02 | 55.18 |
| CTG | 40.91 | 49.56 |
| BID | 39.41 | 55.96 |
| GMD | 34.43 | 41.95 |
| VHM | 34.06 | 38.87 |
| POW | 33.56 | 52.57 |
| BVH | 31.66 | 39.69 |
| TCB | 30.78 | 41.11 |
| FPT | 30.08 | 43.97 |
| HPG | 27.84 | 26.41 |
| MWG | 26.48 | 23.78 |
| ACB | 25.66 | 38.07 |
| MSN | 24.75 | 29.88 |
| MBB | 24.46 | 24.80 |
| SSI | 22.68 | 24.22 |
| VNM | 22.05 | 28.87 |
| PNJ | 17.94 | 21.20 |

## Validation spot-checks

- **consensus_MBB:** tier=Reject score=24.5 money=25 vin_flag=False
- **consensus_CTG:** tier=Tier 3 score=40.9 money=50 vin_flag=False
- **consensus_MWG:** tier=Reject score=26.5 money=24 vin_flag=False
- **consensus_HPG:** tier=Reject score=27.8 money=26 vin_flag=False
- **consensus_GMD:** tier=Reject score=34.4 money=42 vin_flag=False
- **vin_VIC:** tier=Reject score=34.2 vin_distortion=False cmf_d=0.10279848818469287 cmf_w=0.0796443202461418
- **vin_VHM:** tier=Reject score=34.1 vin_distortion=False cmf_d=0.033293577007447894 cmf_w=0.11041170634495696

## Caveats

- Metrics are OHLCV-derived from repo CSVs; refresh `data/stocks` before relying on dates.
- RS vs sector index not computed (VNINDEX only).
- Vingroup names flagged; cap-weight VNINDEX may be skewed 2025–2026.
- Smart Money tags are priors, not buy signals.

---
*End of scan report.*