# Institutional Accumulation Scan

**Scan date:** 2026-04-30  
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
| Unknown | 4 | 26.24 |
| Các công ty đầu cơ và phát triển bất động sản | 3 | 29.64 |
| Hóa chất cơ bản - Sản phẩm nhựa, cao su, hóa chất | 2 | 29.42 |
| Dược phẩm | 1 | 38.94 |
| Dịch vụ vận tải | 1 | 29.66 |
| Hàng không chở khách | 1 | 31.92 |
| Sản phẩm thực phẩm | 1 | 28.14 |

## Top candidates (Tier 1)

_No Tier 1 names at current thresholds._

## Early accumulation (Tier 2)

| ticker | institutional_accumulation_score | score_money_flow | score_price_structure | smart_money_tag | cmf20_daily | rs_vs_vnindex_20 | vingroup_distortion_flag | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TOS | 57.40 | 72.00 | 71.30 | outside_fund_disclosure,ex_vingroup_quality | 0.59 | 0.04 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| DVM | 53.80 | 75.65 | 53.47 | outside_fund_disclosure,ex_vingroup_quality | 0.26 | -0.01 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; Holds MA50; context=56 |
| NRC | 53.45 | 72.40 | 56.64 | outside_fund_disclosure,ex_vingroup_quality | 0.32 | 0.01 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| TNT | 53.29 | 69.86 | 82.38 | outside_fund_disclosure,ex_vingroup_quality | 0.81 | 0.17 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; High distribution-day count (7/25) |
| HNG | 52.22 | 69.61 | 71.47 | outside_fund_disclosure,ex_vingroup_quality | 0.61 | 0.07 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Inconsistent CMF daily vs weekly; ADL diverging bearishly from price |
| BFC | 51.44 | 56.12 | 80.12 | outside_fund_disclosure,ex_vingroup_quality | 0.43 | 0.12 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; ADL diverging bearishly from price |
| DSH | 50.79 | 65.69 | 63.09 | outside_fund_disclosure,ex_vingroup_quality | 0.08 | 0.04 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=56; Inconsistent CMF daily vs weekly |
| SJS | 50.79 | 71.02 | 63.28 | outside_fund_disclosure,ex_vingroup_quality | 0.33 | 0.07 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; Up-volume dominates (20d); RS vs VNINDEX 20d positive; Holds MA50; context=56; Elevated distribution days (5/25) |
| VJC | 50.18 | 55.65 | 67.67 | outside_fund_disclosure,ex_vingroup_quality | 0.42 | 0.05 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56 |
| PIV | 49.05 | 59.95 | 64.70 | outside_fund_disclosure,ex_vingroup_quality | 0.24 | 0.05 | False | tier=Tier 2; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Inconsistent CMF daily vs weekly |
| PCH | 46.32 | 62.28 | 53.49 | outside_fund_disclosure,ex_vingroup_quality | 0.16 | -0.02 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; Holds MA50; context=56; Elevated distribution days (4/25) |
| KSF | 46.31 | 67.76 | 60.30 | outside_fund_disclosure,ex_vingroup_quality | 0.08 | 0.02 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; High distribution-day count (9/25) |
| VPI | 46.18 | 61.99 | 44.79 | outside_fund_disclosure,ex_vingroup_quality | 0.09 | -0.04 | False | tier=Tier 2; CMF daily positive; CMF weekly positive; OBV above MA20; Holds MA50; context=56 |

## Mixed / review (Tier 3, top 10)

| ticker | institutional_accumulation_score | score_money_flow | score_price_structure | smart_money_tag | cmf20_daily | rs_vs_vnindex_20 | vingroup_distortion_flag | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NVL | 51.76 | 73.92 | 77.10 | outside_fund_disclosure,ex_vingroup_quality | 0.21 | 0.34 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Extended 42.7% above MA20/50; ADL diverging bearishly from price |
| HTN | 45.50 | 63.28 | 67.48 | outside_fund_disclosure,ex_vingroup_quality | 0.10 | 0.07 | False | tier=Tier 3; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Moderately extended 22.4%; Inconsistent CMF daily vs weekly |
| NAB | 45.37 | 67.49 | 41.31 | outside_fund_disclosure,ex_vingroup_quality | 0.22 | -0.03 | False | tier=Tier 3; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; Holds MA50; context=56; Inconsistent CMF daily vs weekly |
| PVP | 45.37 | 71.77 | 78.37 | outside_fund_disclosure,ex_vingroup_quality | 0.24 | 0.10 | False | tier=Tier 3; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; Moderately extended 15.3%; High distribution-day count (6/25) |
| MWG | 45.04 | 49.24 | 37.45 | consensus_core,ex_vingroup_quality,ftse_beneficiary_candidate,infrastructure_domestic_demand_aligned | 0.05 | -0.08 | False | tier=Tier 3; OBV above MA20; Up-volume dominates (20d); More HV up-days than down-days; Holds MA50; context=88 |
| MZG | 44.98 | 53.84 | 60.15 | outside_fund_disclosure,ex_vingroup_quality | 0.39 | -0.16 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; Up-volume dominates (20d); Holds MA50; Volatility contraction + supportive CMF; context=56; Elevated distribution days (4/25) |
| VCB | 44.55 | 57.13 | 25.00 | consensus_core,ex_vingroup_quality,ftse_beneficiary_candidate,policy_liquidity_sensitive | -0.13 | -0.08 | False | tier=Tier 3; OBV above MA20; Up-volume dominates (20d); More HV up-days than down-days; Holds MA20; context=88 |
| F88 | 44.13 | 73.97 | 59.51 | outside_fund_disclosure,ex_vingroup_quality | 0.10 | 0.11 | False | tier=Tier 3; CMF daily positive; CMF daily/weekly conflict; OBV above MA20; RS vs VNINDEX 20d positive; Holds MA50; context=56; High distribution-day count (6/25); Inconsistent CMF daily vs weekly |
| PTB | 44.13 | 57.56 | 43.47 | outside_fund_disclosure,ex_vingroup_quality | 0.33 | -0.10 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; OBV above MA20; Holds MA20; Volatility contraction + supportive CMF; context=56 |
| BAF | 43.45 | 56.17 | 42.94 | outside_fund_disclosure,ex_vingroup_quality | 0.23 | -0.07 | False | tier=Tier 3; CMF daily positive; CMF weekly positive; OBV above MA20; Holds MA50; Volatility contraction + supportive CMF; context=56 |

## Emerging accumulation (outside fund disclosure tags)

_Names with Tier 1–3 + constructive money flow but **no** consensus/commentary/selective fund tag — possible accumulation not visible in top holdings._

**Count:** 24 (showing top 15)
| ticker | institutional_accumulation_score | score_money_flow |
| --- | --- | --- |
| TOS | 57.40 | 72.00 |
| DVM | 53.80 | 75.65 |
| NRC | 53.45 | 72.40 |
| HNG | 52.22 | 69.61 |
| BFC | 51.44 | 56.12 |
| DSH | 50.79 | 65.69 |
| SJS | 50.79 | 71.02 |
| VJC | 50.18 | 55.65 |
| PIV | 49.05 | 59.95 |
| PCH | 46.32 | 62.28 |
| VPI | 46.18 | 61.99 |
| NAB | 45.37 | 67.49 |
| MZG | 44.98 | 53.84 |
| PTB | 44.13 | 57.56 |
| BAF | 43.45 | 56.17 |

## Fund-context names in scan (any tier)

**Count:** 23 (core / second_ring / commentary / selective)
| ticker | institutional_accumulation_score | score_money_flow |
| --- | --- | --- |
| MWG | 45.04 | 49.24 |
| VCB | 44.55 | 57.13 |
| VHM | 42.50 | 65.59 |
| HPG | 42.10 | 44.73 |
| TCB | 40.10 | 55.23 |
| STB | 36.41 | 32.14 |
| CTG | 32.47 | 25.34 |
| GVR | 31.83 | 34.91 |
| MSN | 30.55 | 37.09 |
| GMD | 30.08 | 30.62 |
| SSI | 28.28 | 23.17 |
| MBB | 26.95 | 24.20 |
| KDH | 24.43 | 18.55 |
| BVH | 22.74 | 21.88 |
| BID | 22.41 | 29.81 |
| ACB | 21.86 | 27.68 |
| VNM | 20.35 | 24.41 |
| PNJ | 19.85 | 26.24 |
| NLG | 19.68 | 15.26 |
| FPT | 19.43 | 18.29 |

## Validation spot-checks

- **consensus_MBB:** tier=Reject score=26.9 money=24 vin_flag=False
- **consensus_CTG:** tier=Reject score=32.5 money=25 vin_flag=False
- **consensus_MWG:** tier=Tier 3 score=45.0 money=49 vin_flag=False
- **consensus_HPG:** tier=Tier 3 score=42.1 money=45 vin_flag=False
- **consensus_GMD:** tier=Reject score=30.1 money=31 vin_flag=False
- **vin_VIC:** tier=Tier 3 score=39.6 vin_distortion=True cmf_d=0.18932754062066448 cmf_w=-0.011266519907447616
- **vin_VHM:** tier=Tier 3 score=42.5 vin_distortion=True cmf_d=nan cmf_w=0.015252361971737554

## Caveats

- Metrics are OHLCV-derived from repo CSVs; refresh `data/stocks` before relying on dates.
- RS vs sector index not computed (VNINDEX only).
- Vingroup names flagged; cap-weight VNINDEX may be skewed 2025–2026.
- Smart Money tags are priors, not buy signals.

---
*End of scan report.*