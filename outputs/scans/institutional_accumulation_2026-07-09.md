# Institutional Accumulation Scan

**Scan date:** 2026-07-09  
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
| Ngân hàng | 6 | 37.18 |
| Unknown | 6 | 27.26 |
| Công ty chứng khoán | 2 | 36.74 |
| Các công ty đầu cơ và phát triển bất động sản | 1 | 23.1 |
| Giấy | 1 | 35.61 |
| Hóa chất cơ bản - Sản phẩm nhựa, cao su, hóa chất | 1 | 24.32 |
| Phân phối khí đốt | 1 | 35.34 |
| Sản phẩm thực phẩm | 1 | 29.39 |
| Sản xuất và cung cấp điện truyền thống | 1 | 27.6 |
| Xây dựng, xây lắp | 1 | 26.3 |

## Top candidates (Tier 1)

_No Tier 1 names at current thresholds._

## Early accumulation (Tier 2)

| ticker | institutional_accumulation_score | score_money_flow | score_price_structure | smart_money_tag | cmf20_daily | rs_vs_vnindex_20 | vingroup_distortion_flag | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SSB | 58.40 | 75.75 | 69.77 | outside_fund_disclosure,ex_vingroup_quality | 0.70 | 0.12 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| PSI | 57.89 | 79.59 | 74.15 | outside_fund_disclosure,ex_vingroup_quality | 0.16 | 0.15 | False | tier=Tier 2; CMF daily positive; OBV above MA20; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=56; Moderately extended 18.0% |
| NAB | 56.99 | 80.49 | 66.89 | outside_fund_disclosure,ex_vingroup_quality | 0.44 | 0.10 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (4/25) |
| MSB | 55.97 | 63.14 | 78.21 | outside_fund_disclosure,ex_vingroup_quality | 0.35 | 0.08 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| ABB | 55.20 | 64.62 | 73.45 | outside_fund_disclosure,ex_vingroup_quality | 0.44 | 0.13 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| CSM | 54.98 | 73.81 | 77.34 | outside_fund_disclosure,ex_vingroup_quality | 0.56 | 0.12 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (4/25); ADL diverging bearishly from price |
| TVC | 53.89 | 64.36 | 69.12 | outside_fund_disclosure,ex_vingroup_quality | -0.19 | 0.09 | False | tier=Tier 2; OBV above MA20; Up-volume dominates (20d); More HV up-days than down-days; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| ABW | 53.52 | 78.08 | 74.89 | outside_fund_disclosure,ex_vingroup_quality | 0.15 | 0.22 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Moderately extended 18.7%; Elevated distribution days (5/25) |
| HDB | 52.64 | 69.00 | 58.35 | outside_fund_disclosure,ex_vingroup_quality | 0.23 | 0.05 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| CAP | 51.65 | 56.20 | 72.18 | outside_fund_disclosure,ex_vingroup_quality | 0.28 | 0.09 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| SBS | 51.02 | 65.97 | 65.24 | outside_fund_disclosure,ex_vingroup_quality | 0.31 | 0.15 | False | tier=Tier 2; CMF daily positive; OBV above MA20; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (4/25) |
| HHP | 50.60 | 60.74 | 62.28 | outside_fund_disclosure,ex_vingroup_quality | 0.37 | -0.01 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; Holds MA50; Volatility contraction + supportive CMF; context=56 |
| DSE | 49.63 | 63.79 | 54.65 | outside_fund_disclosure,ex_vingroup_quality | 0.19 | 0.07 | False | tier=Tier 2; CMF daily positive; OBV above MA20; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| C69 | 49.39 | 62.30 | 78.71 | outside_fund_disclosure,ex_vingroup_quality | 0.30 | 0.13 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; High distribution-day count (6/25) |
| HNG | 49.24 | 64.92 | 58.60 | outside_fund_disclosure,ex_vingroup_quality | 0.48 | -0.00 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; Holds MA20; Volatility contraction + supportive CMF; context=56; Inconsistent CMF daily vs weekly |
| NRC | 49.23 | 58.90 | 70.18 | outside_fund_disclosure,ex_vingroup_quality | 0.17 | 0.15 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; One-bar speculative spike risk |
| BWE | 48.85 | 64.29 | 51.20 | outside_fund_disclosure,ex_vingroup_quality | 0.29 | -0.00 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; Holds MA50; context=56 |
| TRC | 47.57 | 65.55 | 59.23 | outside_fund_disclosure,ex_vingroup_quality | — | 0.05 | False | tier=Tier 2; CMF weekly positive; OBV above MA20; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (5/25) |
| TTA | 47.17 | 66.48 | 50.82 | outside_fund_disclosure,ex_vingroup_quality | 0.52 | 0.05 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (4/25) |
| BVB | 46.43 | 58.25 | 50.77 | outside_fund_disclosure,ex_vingroup_quality | 0.07 | 0.05 | False | tier=Tier 2; CMF daily positive; OBV above MA20; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=56 |

## Mixed / review (Tier 3, top 10)

| ticker | institutional_accumulation_score | score_money_flow | score_price_structure | smart_money_tag | cmf20_daily | rs_vs_vnindex_20 | vingroup_distortion_flag | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BVS | 51.70 | 72.63 | 78.64 | outside_fund_disclosure,ex_vingroup_quality | 0.47 | 0.26 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Moderately extended 22.9%; Elevated distribution days (4/25) |
| HSL | 47.77 | 72.87 | 70.00 | outside_fund_disclosure,ex_vingroup_quality | — | 0.36 | False | tier=Tier 3; OBV above MA20; Up-volume dominates (20d); Turnover acceleration vs 50d baseline; RS vs VNINDEX 20d positive; Holds MA50; context=56; Extended 31.4% above MA20/50; Elevated distribution days (5/25) |
| VGR | 46.75 | 71.59 | 66.94 | outside_fund_disclosure,ex_vingroup_quality | — | 0.20 | False | tier=Tier 3; OBV above MA20; ADL bearish divergence vs price; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (5/25); ADL diverging bearishly from price |
| BMP | 46.21 | 61.03 | 75.93 | outside_fund_disclosure,ex_vingroup_quality | 0.35 | 0.10 | False | tier=Tier 3; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (5/25); Inconsistent CMF daily vs weekly |
| TVS | 45.92 | 62.60 | 57.32 | outside_fund_disclosure,ex_vingroup_quality | — | 0.09 | False | tier=Tier 3; CMF weekly positive; OBV above MA20; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (5/25) |
| MCH | 45.55 | 60.88 | 59.49 | outside_fund_disclosure,ex_vingroup_quality | 0.43 | 0.04 | False | tier=Tier 3; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (4/25); Inconsistent CMF daily vs weekly |
| TPB | 45.36 | 64.23 | 54.26 | outside_fund_disclosure,ex_vingroup_quality | 0.19 | -0.00 | False | tier=Tier 3; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; Holds MA50; Volatility contraction + supportive CMF; context=56; Elevated distribution days (4/25); Inconsistent CMF daily vs weekly |
| AAS | 45.06 | 63.03 | 60.54 | outside_fund_disclosure,ex_vingroup_quality | 0.36 | 0.05 | False | tier=Tier 3; CMF daily positive; CMF daily/weekly conflict; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (5/25); Inconsistent CMF daily vs weekly |
| VDS | 44.68 | 59.95 | 71.91 | outside_fund_disclosure,ex_vingroup_quality | 0.39 | 0.16 | False | tier=Tier 3; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (5/25); Inconsistent CMF daily vs weekly |
| VPX | 44.24 | 68.25 | 59.07 | outside_fund_disclosure,ex_vingroup_quality | 0.41 | 0.05 | False | tier=Tier 3; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; High distribution-day count (8/25); Inconsistent CMF daily vs weekly |

## Emerging accumulation (outside fund disclosure tags)

_Names with Tier 1–3 + constructive money flow but **no** consensus/commentary/selective fund tag — possible accumulation not visible in top holdings._

**Count:** 27 (showing top 15)
| ticker | institutional_accumulation_score | score_money_flow |
| --- | --- | --- |
| SSB | 58.40 | 75.75 |
| PSI | 57.89 | 79.59 |
| NAB | 56.99 | 80.49 |
| MSB | 55.97 | 63.14 |
| ABB | 55.20 | 64.62 |
| CSM | 54.98 | 73.81 |
| TVC | 53.89 | 64.36 |
| HDB | 52.64 | 69.00 |
| CAP | 51.65 | 56.20 |
| SBS | 51.02 | 65.97 |
| HHP | 50.60 | 60.74 |
| DSE | 49.63 | 63.79 |
| HNG | 49.24 | 64.92 |
| NRC | 49.23 | 58.90 |
| BWE | 48.85 | 64.29 |

## Fund-context names in scan (any tier)

**Count:** 23 (core / second_ring / commentary / selective)
| ticker | institutional_accumulation_score | score_money_flow |
| --- | --- | --- |
| GMD | 42.58 | 54.59 |
| TCB | 39.22 | 42.20 |
| POW | 37.89 | 50.50 |
| MBB | 36.84 | 43.18 |
| STB | 34.36 | 42.71 |
| VCB | 33.44 | 39.73 |
| MWG | 32.31 | 33.18 |
| CTG | 31.48 | 33.99 |
| VHM | 29.14 | 40.94 |
| NLG | 27.81 | 39.72 |
| ACB | 25.98 | 32.69 |
| SSI | 25.61 | 34.50 |
| FPT | 25.03 | 25.59 |
| HPG | 23.03 | 20.29 |
| PNJ | 22.73 | 28.75 |
| GAS | 21.83 | 17.76 |
| BID | 21.65 | 24.05 |
| VNM | 21.46 | 27.30 |
| MSN | 19.60 | 21.41 |
| BVH | 18.88 | 18.68 |

## Validation spot-checks

- **consensus_MBB:** tier=Reject score=36.8 money=43 vin_flag=False
- **consensus_CTG:** tier=Reject score=31.5 money=34 vin_flag=False
- **consensus_MWG:** tier=Reject score=32.3 money=33 vin_flag=False
- **consensus_HPG:** tier=Reject score=23.0 money=20 vin_flag=False
- **consensus_GMD:** tier=Tier 3 score=42.6 money=55 vin_flag=False
- **vin_VIC:** tier=Reject score=36.4 vin_distortion=False cmf_d=0.22258839052378585 cmf_w=0.13822836845340875
- **vin_VHM:** tier=Reject score=29.1 vin_distortion=False cmf_d=nan cmf_w=0.1828661691684344

## Caveats

- Metrics are OHLCV-derived from repo CSVs; refresh `data/stocks` before relying on dates.
- RS vs sector index not computed (VNINDEX only).
- Vingroup names flagged; cap-weight VNINDEX may be skewed 2025–2026.
- Smart Money tags are priors, not buy signals.

---
*End of scan report.*