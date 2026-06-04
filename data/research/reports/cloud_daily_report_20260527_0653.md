# Cloud Daily Report — 2026-05-27 06:53 UTC

**Mode:** PRE-LUNCH PREVIEW | **VNINDEX:** BULL | **Breadth:** NORMAL | **T1:** OK | **T2:** OK | **NAV:** 5.27bn VND | **Positions:** data\raw\current_positions_derived.json

> PREVIEW ONLY | AUTO ORDER OFF | IF_CLOSE_NOW
> Intraday preview only. final_action=INTRADAY_PREVIEW. would_be_final_action is planning only.

> Daily scan is source of truth. AFL is visual only.

## Warnings
- Data starts 2012-01-03 (after 2012); shorter history flagged
- missing_quote_count=101
- distribution_risk_lens: NEEDS_REVIEW: stale index view; probabilities may be caveated.

## B. Decision Summary

### ACTION NOW
- Review 1 A3 NEW_T1 candidate(s) for manual checklist
- Review would-be A3 candidate(s) if close now; wait for EOD confirmation. (CTR)

### WATCH / PREPARE
- 2 would-be NEW_T1 if close now
- S3 paper setups: 0
- T2 candidates (ADD_T2 + WAIT_PB): 0

### DO NOT DO
- Do not trade S3 as live capital
- Do not use intraday preview as order source
- Do not base orders on AFL visuals

## C. A3 Action Board

### Group 1: New T1 Candidates
| Symbol | Action | Rank | Close | PB | TP1 | Trail | Note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FPT | NEW_T1 | — | 100.00 | 96.00 | 118.00 | — |  |

*Signal confirmed at today's close; planned fill is next session open. Entry levels are pending until the next-open fill price is known.*

## G. Market Context
- VNINDEX regime: BULL
- A3 breadth: 0.4500
- Breadth zone: NORMAL
- T1 permission: OK
- T2 permission: OK
- Sector L4 stress: 1
- Liquidity warnings: 1

### VNINDEX Distribution Risk Lens
- Primary view: **ex_vin_proxy**
- Lens report status: **NEEDS_REVIEW**
#### Index view freshness
| View | Last data date | Requested as-of | Stale |
| --- | --- | --- | --- |
| vnindex_raw | 2026-05-26 | 2099-01-01 | YES |
| ex_vin_proxy | 2026-05-26 | 2099-01-01 | YES |
| vin_group | 2026-05-26 | 2099-01-01 | YES |

NEEDS_REVIEW: stale index view; probabilities may be caveated.
#### v1.3 breadth staleness (read-only)
- Breadth status: **OK**
- Breadth as-of: **2026-05-26**
- Index as-of: **2099-01-01**
- Breadth lag (sessions): **1**
- _Research context only; not used for final_action, OMS, A3/S3, or position sizing._
- VNINDEX raw: **DISTRIBUTION_CLUSTER** (dist 10/25/50: 3/5/9)
- ex-VIN proxy: **DISTRIBUTION_CLUSTER** (dist 10/25/50: 3/5/8)
- VIN distortion flag: **False**
- VIN group warning: **DOWNTREND_WARNING**
- Distribution Risk Lens is market context only and does not change final_action.
- **ex-VIN proxy is derived and is NOT a native exchange index.**
- _NOT true ex-VIN index; see vnindex_low_dist_ex_vin.py methodology_
- _ex-VIN proxy drawdown/correction probabilities are close-based; high/low are synthetic from close when native OHLC is unavailable._
- P(25D return < 0) ex-VIN: **41.6% (base 39.0%)**
- P(-5% correction within 25D) ex-VIN: **42.1% (base 40.5%)**
- P(-10% correction within 75D) ex-VIN: **47.7% (base 44.3%)**
- Comparison: Raw and ex-VIN proxy broadly aligned on distribution warning.


### RS vs VNINDEX (correction leg)

| Metric | Value |
| --- | --- |
| Anchor date | 2026-05-15 (close 1921.6) |
| End date | 2026-05-26 (close 1884.18) |
| VNINDEX return | -1.95% |
| Drawdown from peak | -1.95% |
| Detection | config_override |
| Universe n | 272 |
| Outperform (RS>0) | 148 |
| Leaders (RS≥+3%) | 63 |

**Definitions:** `RS leg` = stock return − VNINDEX return over correction anchor→end. `RS20 before/after` = 20d RS vs VNINDEX at anchor date vs end date; `Δ RS20` = after − before (pp). `Close (anchor→end)` = kVND close on anchor bar → end bar. Hold/T1/S3/A3 columns crosswalk Phase36 `final_action` (display only).

#### Top leaders (RS≥+3%)
| Symbol | Close (anchor→end) | Ret leg | RS leg | RS20 before | RS20 after | Δ RS20 | Impr | Hold | final_action | T1 | S3 lead | A3/S3 cloud |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NVB | 10.6→11.9 | +12.26% | +14.21% | -14.41% | +9.45% | +23.86% | Y | — | — | — | — | —/— |
| C69 | 15.9→17.8 | +11.95% | +13.90% | -10.67% | +11.21% | +21.88% | Y | — | — | — | — | —/— |
| PC1 | 17.85→19.9 | +11.48% | +13.43% | -43.19% | -18.17% | +25.02% | Y | Y | not_in_scan | — | — | —/— |
| ILS | 24.4→27.0 | +10.66% | +12.60% | +26.59% | +22.55% | -4.04% | — | — | — | — | — | —/— |
| PET | 47.0→52.0 | +10.64% | +12.59% | -11.31% | +10.49% | +21.80% | Y | — | — | — | — | —/— |
| VND | 16.45→18.1 | +10.03% | +11.98% | -10.59% | +10.65% | +21.24% | Y | — | — | — | — | —/— |
| VVS | 105.0→115.2 | +9.71% | +11.66% | -21.59% | -8.28% | +13.31% | Y | — | — | — | — | —/— |
| POM | 4.3→4.7 | +9.30% | +11.25% | -0.72% | +13.90% | +14.62% | Y | — | — | — | — | —/— |
| VPL | 88.4→95.7 | +8.26% | +10.21% | +2.28% | +13.87% | +11.59% | Y | — | — | — | — | —/— |
| CTR | 84.9→90.5 | +6.60% | +8.54% | -10.63% | +4.49% | +15.12% | Y | — | — | — | — | —/— |
| ACB | 23.3→24.8 | +6.44% | +8.39% | -11.14% | +4.79% | +15.93% | Y | — | — | — | — | —/— |
| VAB | 10.2→10.85 | +6.37% | +8.32% | -10.14% | +5.11% | +15.25% | Y | — | — | — | — | —/— |
| NNC | 45.05→47.8 | +6.10% | +8.05% | -14.27% | +8.52% | +22.79% | Y | — | — | — | — | —/— |
| VCB | 60.7→64.4 | +6.10% | +8.04% | -5.86% | +1.81% | +7.67% | Y | Y | not_in_scan | — | — | —/— |
| HSG | 12.1→12.8 | +5.79% | +7.73% | -34.44% | -19.21% | +15.23% | Y | Y | not_in_scan | — | — | —/— |

#### RS improving + positive RS
| Symbol | Close (anchor→end) | Ret leg | RS leg | RS20 before | RS20 after | Δ RS20 | Impr | Hold | final_action | T1 | S3 lead | A3/S3 cloud |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NVB | 10.6→11.9 | +12.26% | +14.21% | -14.41% | +9.45% | +23.86% | Y | — | — | — | — | —/— |
| C69 | 15.9→17.8 | +11.95% | +13.90% | -10.67% | +11.21% | +21.88% | Y | — | — | — | — | —/— |
| PC1 | 17.85→19.9 | +11.48% | +13.43% | -43.19% | -18.17% | +25.02% | Y | Y | not_in_scan | — | — | —/— |
| PET | 47.0→52.0 | +10.64% | +12.59% | -11.31% | +10.49% | +21.80% | Y | — | — | — | — | —/— |
| VND | 16.45→18.1 | +10.03% | +11.98% | -10.59% | +10.65% | +21.24% | Y | — | — | — | — | —/— |
| VVS | 105.0→115.2 | +9.71% | +11.66% | -21.59% | -8.28% | +13.31% | Y | — | — | — | — | —/— |
| POM | 4.3→4.7 | +9.30% | +11.25% | -0.72% | +13.90% | +14.62% | Y | — | — | — | — | —/— |
| VPL | 88.4→95.7 | +8.26% | +10.21% | +2.28% | +13.87% | +11.59% | Y | — | — | — | — | —/— |
| CTR | 84.9→90.5 | +6.60% | +8.54% | -10.63% | +4.49% | +15.12% | Y | — | — | — | — | —/— |
| ACB | 23.3→24.8 | +6.44% | +8.39% | -11.14% | +4.79% | +15.93% | Y | — | — | — | — | —/— |
| VAB | 10.2→10.85 | +6.37% | +8.32% | -10.14% | +5.11% | +15.25% | Y | — | — | — | — | —/— |
| NNC | 45.05→47.8 | +6.10% | +8.05% | -14.27% | +8.52% | +22.79% | Y | — | — | — | — | —/— |
| VCB | 60.7→64.4 | +6.10% | +8.04% | -5.86% | +1.81% | +7.67% | Y | Y | not_in_scan | — | — | —/— |
| HSG | 12.1→12.8 | +5.79% | +7.73% | -34.44% | -19.21% | +15.23% | Y | Y | not_in_scan | — | — | —/— |
| SSB | 16.5→17.45 | +5.76% | +7.70% | -11.16% | +3.75% | +14.91% | Y | — | — | — | — | —/— |

#### Defensive flat (ret −1%…+2%, RS≥+1%)
| Symbol | Close (anchor→end) | Ret leg | RS leg | RS20 before | RS20 after | Δ RS20 | Impr | Hold | final_action | T1 | S3 lead | A3/S3 cloud |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ABB | 15.2→15.5 | +1.97% | +3.92% | -4.11% | +3.29% | +7.40% | Y | — | — | — | — | —/— |
| BIC | 23.15→23.6 | +1.94% | +3.89% | -9.92% | -1.37% | +8.55% | Y | — | — | — | — | —/— |
| EVF | 13.65→13.9 | +1.83% | +3.78% | -9.66% | +7.01% | +16.67% | Y | — | — | — | — | —/— |
| NKG | 13.8→14.05 | +1.81% | +3.76% | -16.53% | -3.84% | +12.69% | Y | — | — | — | — | —/— |
| PAT | 66.6→67.8 | +1.80% | +3.75% | -16.99% | -1.76% | +15.23% | Y | — | — | — | — | —/— |
| MIG | 17.3→17.6 | +1.73% | +3.68% | -16.20% | -1.30% | +14.90% | Y | — | — | — | — | —/— |
| VGT | 11.7→11.9 | +1.71% | +3.66% | -14.62% | -1.57% | +13.05% | Y | — | — | — | — | —/— |
| CTF | 17.9→18.2 | +1.68% | +3.62% | -9.32% | -0.19% | +9.13% | Y | — | — | — | — | —/— |
| PAN | 32.95→33.5 | +1.67% | +3.62% | -3.12% | +4.44% | +7.56% | Y | — | — | — | — | —/— |
| CTS | 28.05→28.5 | +1.60% | +3.55% | -8.22% | +6.00% | +14.22% | Y | — | — | — | — | —/— |
| FUEVN100 | 26.44→26.85 | +1.55% | +3.50% | -4.41% | +0.97% | +5.38% | Y | — | — | — | — | —/— |
| BID | 42.95→43.6 | +1.51% | +3.46% | -1.91% | +4.07% | +5.98% | Y | Y | not_in_scan | — | — | —/— |
| BSI | 35.0→35.5 | +1.43% | +3.38% | -13.88% | +0.69% | +14.57% | Y | — | — | — | — | —/— |
| BWE | 43.8→44.4 | +1.37% | +3.32% | -7.76% | +1.33% | +9.09% | Y | — | — | — | — | —/— |
| PAC | 22.05→22.35 | +1.36% | +3.31% | -18.59% | -4.19% | +14.40% | Y | — | — | — | — | —/— |

#### Weakest RS
| Symbol | Close (anchor→end) | Ret leg | RS leg | RS20 before | RS20 after | Δ RS20 | Impr | Hold | final_action | T1 | S3 lead | A3/S3 cloud |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TCX | 51.2→43.35 | -15.33% | -13.38% | -10.70% | -14.73% | -4.03% | — | Y | not_in_scan | — | — | —/— |
| HPA | 38.45→33.55 | -12.74% | -10.80% | -7.30% | -11.27% | -3.97% | — | — | — | — | — | —/— |
| REE | 60.3→52.8 | -12.44% | -10.49% | -16.72% | -15.85% | +0.87% | — | — | — | — | — | —/— |
| PVP | 19.85→17.4 | -12.34% | -10.40% | +28.21% | -3.80% | -32.01% | — | — | — | — | — | —/— |
| BMP | 157.2→139.9 | -11.01% | -9.06% | +1.48% | -6.59% | -8.07% | — | — | — | — | — | —/— |
| GEE | 121.0→107.8 | -10.91% | -8.96% | -46.17% | -40.14% | +6.03% | Y | — | — | — | — | —/— |
| PVD | 33.7→30.15 | -10.53% | -8.59% | -6.87% | -5.48% | +1.39% | Y | — | — | — | — | —/— |
| BSR | 31.75→28.5 | -10.24% | -8.29% | +12.50% | +13.26% | +0.76% | — | — | — | — | — | —/— |
| NVL | 17.3→15.55 | -10.12% | -8.17% | -7.05% | -19.75% | -12.70% | — | — | — | — | — | —/— |
| FTS | 26.65→24.1 | -9.57% | -7.62% | -12.87% | -9.80% | +3.07% | Y | — | — | — | — | —/— |
| BFC | 62.7→57.0 | -9.09% | -7.14% | -0.67% | -11.95% | -11.28% | — | — | — | — | — | —/— |
| HPG | 26.55→24.25 | -8.66% | -6.72% | -15.22% | -13.51% | +1.71% | Y | — | — | — | — | —/— |
| PIV | 8.1→7.4 | -8.64% | -6.69% | +7.49% | -2.07% | -9.56% | — | — | — | — | — | —/— |
| VIW | 26.7→24.4 | -8.61% | -6.67% | -34.26% | -38.49% | -4.23% | — | — | — | — | — | —/— |
| HID | 4.65→4.26 | -8.39% | -6.44% | -15.03% | -13.08% | +1.95% | Y | — | — | — | — | —/— |

> Cap-weight VNINDEX may be Vingroup-skewed in 2025–2026. Flag VIN names separately; do not treat VPL as broad-market proof.

## RS C3 Context (RS line acceleration)

**FACTS** (context only; does not change final_action)

> **OOS3 regime active:** C3 IC near zero in 2024+. Use as sort/display only — hard filter not operative.

_Data as of: 2026-05-25_

| Symbol | C3 Rating | C3 Zone | #Top50 | T2 Context | Late Chase | final_action | EMA dist% |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AAA | 54 | NEUTRAL | #1 | — | — | SKIP_LIQUIDITY | — |
| SSI | 54 | NEUTRAL | #2 | — | — | WATCH_ONLY | — |
| FPT | 52 | NEUTRAL | #3 | — | — | NEW_T1 | — |

_RS C3 is review-ranking context only and does not set or override final_action. IC near zero in OOS3 2024+. Use as sort/prioritization display only._

**SSOT:** `data/research/rs_rating/rs_rating_daily.parquet` · **classification:** REVIEW_RANKING_ONLY


## H. Delta vs Previous
- New: FPT
- Removed: CTR, VCB