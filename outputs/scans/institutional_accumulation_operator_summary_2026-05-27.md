# Institutional Accumulation — Operator Summary

**Scan date:** 2026-05-27  
**Role:** research_prioritization_only  
**Regime:** `fragile_uptrend_narrow_leadership` | **Context:** fallback:apr2026_default_priors.json

## What this file is / is not

- **For:** Human research / allocator monitoring after Smart Money monthly + full scan.
- **Not for:** Orders, final_action, sizing, OMS, or execution — use separate execution workflow.

## A. Regime & scan snapshot

| Metric | Value |
| --- | --- |
| Rows scored | 1562 |
| Tier 1 | 0 |
| Tier 2 | 19 |
| Tier 3 | 33 |
| Reject | 1510 |
| Emerging (universe) | 25 |
| Top-tier fund-backed | 4 |
| Unknown sector (Tier 1–3) | 9/52 |

## B. What to look at first

### 1. Top fund-backed candidates (Tier 1–3)

- **VCB** (Tier 2, score 51.8, MF 64, risk 27, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Grouped money flow supportive
  - **Also:** bucket=consensus_core; OBV/PVT supportive; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Tier 2 — use full scan row for CMF/OBV detail.
- **ACB** (Tier 3, score 42.1, MF 54, risk 55, sector `Ngân hàng`) — `fund_commentary_mention`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** bucket=fund_commentary_mention; CMF block strong; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (55)
  - **Note:** Size as research only until risk penalty improves.
- **CTG** (Tier 3, score 40.8, MF 38, risk 0, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Tier held up mainly by context, not flow confirmation; weekly CMF still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Investigate whether context is masking weak CMF/participation.
- **GAS** (Tier 3, score 40.8, MF 59, risk 40, sector `Phân phối khí đốt`) — `fund_commentary_mention`
  - **Why:** Grouped money flow supportive
  - **Also:** bucket=fund_commentary_mention; OBV/PVT supportive; context score elevated
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Tier 3 — use full scan row for CMF/OBV detail.

### 2. Top emerging candidates (no fund tag)

- **MSB** (Tier 2, score 63.6, MF 87, risk 20, sector `Ngân hàng`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; OBV/PVT supportive; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **HHP** (Tier 2, score 58.3, MF 75, risk 0, sector `Giấy`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; OBV/PVT supportive; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **VPL** (Tier 2, score 56.5, MF 76, risk 0, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; OBV/PVT supportive; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **SSB** (Tier 2, score 53.0, MF 63, risk 0, sector `Ngân hàng`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **NAF** (Tier 2, score 52.2, MF 57, risk 0, sector `Bia`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **DL1** (Tier 2, score 51.2, MF 69, risk 18, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** OBV/PVT supportive; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **C69** (Tier 2, score 48.8, MF 51, risk 0, sector `Xây dựng, xây lắp`) — `outside_fund_disclosure`
  - **Why:** Emerging (no fund tag); flow/risk pass emerging gate
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **PDR** (Tier 2, score 48.8, MF 66, risk 27, sector `Các công ty đầu cơ và phát triển bất động sản`) — `outside_fund_disclosure`
  - **Why:** Emerging (no fund tag); flow/risk pass emerging gate
  - **Also:** CMF block strong; context score elevated; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.

### 3. Important rejects (fund-linked, flow failed)

- **GMD** (Reject, score 32.3, MF 43, risk 40, sector `Dịch vụ vận tải`) — `consensus_core`
  - **Why:** Consensus-core name below accumulation tier thresholds
  - **Also:** bucket=consensus_core; CMF block strong; context score elevated
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** risk penalty elevated; distribution risk flag
- **HPG** (Reject, score 25.2, MF 27, risk 40, sector `Khai thác quặng sắt và sản xuất thép`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; risk penalty elevated; distribution risk flag
- **MWG** (Reject, score 24.4, MF 18, risk 25, sector `Bán lẻ tổng hợp`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; distribution risk flag
- **MBB** (Reject, score 23.8, MF 22, risk 40, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; risk penalty elevated; distribution risk flag
- **STB** (Reject, score 36.9, MF 30, risk 25, sector `Ngân hàng`) — `consensus_second_ring`
  - **Why:** Fund-linked, but grouped money flow not confirming
  - **Also:** bucket=consensus_second_ring; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated
  - **Note:** Reject — use full scan row for CMF/OBV detail.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; distribution risk flag
- **BVH** (Reject, score 35.4, MF 51, risk 40, sector `Bảo hiểm nhân thọ`) — `selective_fund_bet`
  - **Why:** Scan tier driven by mixed flow/context/risk profile
  - **Also:** bucket=selective_fund_bet; CMF block strong; context score elevated
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Reject — use full scan row for CMF/OBV detail.
  - **Failed because:** risk penalty elevated; distribution risk flag
- **BID** (Reject, score 34.0, MF 43, risk 52, sector `Ngân hàng`) — `fund_commentary_mention`
  - **Why:** Scan tier driven by mixed flow/context/risk profile
  - **Also:** bucket=fund_commentary_mention; CMF block strong; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (52)
  - **Note:** Size as research only until risk penalty improves.
  - **Failed because:** weekly CMF still weak; risk penalty elevated; distribution risk flag
- **POW** (Reject, score 33.1, MF 41, risk 67, sector `Sản xuất và cung cấp điện truyền thống`) — `fund_commentary_mention`
  - **Why:** Fund-linked, but grouped money flow not confirming
  - **Also:** bucket=fund_commentary_mention; CMF block strong; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (67)
  - **Note:** Size as research only until risk penalty improves.
  - **Failed because:** weekly CMF still weak; risk penalty elevated; distribution risk flag

### 4. Elevated risk / distortion / distribution (Tier 1–3; matches caution-proxy %)

- **ACB** (Tier 3, score 42.1, MF 54, risk 55, sector `Ngân hàng`) — `fund_commentary_mention`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** bucket=fund_commentary_mention; CMF block strong; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (55)
  - **Note:** Size as research only until risk penalty improves.
- **BSR** (Tier 3, score 38.8, MF 53, risk 55, sector `Thăm dò và sản xuất dầu khí`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (55)
  - **Note:** Size as research only until risk penalty improves.
- **POM** (Tier 3, score 43.3, MF 58, risk 53, sector `Steel`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** context score elevated; daily CMF missing
  - **Risk:** High risk penalty (53)
  - **Note:** Size as research only until risk penalty improves.
- **BVB** (Tier 3, score 39.6, MF 55, risk 52, sector `Ngân hàng`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** CMF block strong; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; High risk penalty (52)
  - **Note:** Size as research only until risk penalty improves.
- **VIX** (Tier 3, score 38.9, MF 47, risk 40, sector `Công ty chứng khoán`) — `outside_fund_disclosure`
  - **Why:** Scan tier driven by mixed flow/context/risk profile
  - **Also:** context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Tier 3 — use full scan row for CMF/OBV detail.
- **GAS** (Tier 3, score 40.8, MF 59, risk 40, sector `Phân phối khí đốt`) — `fund_commentary_mention`
  - **Why:** Grouped money flow supportive
  - **Also:** bucket=fund_commentary_mention; OBV/PVT supportive; context score elevated
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Tier 3 — use full scan row for CMF/OBV detail.
- **VND** (Tier 2, score 46.9, MF 67, risk 25, sector `Công ty chứng khoán`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** OBV/PVT supportive; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **MST** (Tier 3, score 39.9, MF 51, risk 25, sector `Xây dựng, xây lắp`) — `outside_fund_disclosure`
  - **Why:** Emerging (no fund tag); flow/risk pass emerging gate
  - **Also:** CMF block strong; context score elevated
  - **Risk:** Distribution-day count elevated
  - **Note:** Tier 3 — use full scan row for CMF/OBV detail.

## C. Bucket mix

**Denominator:** All Tier 1–3 names in scan (n=52)

| Bucket | Count | % | Definition |
| --- | ---: | ---: | --- |
| fund_backed | 4 | 7.7% | has_fund_disclosure_tag among Tier 1–3 |
| emerging | 25 | 48.1% | emerging_accumulation_candidate among Tier 1–3 |
| vin_distortion_flagged | 0 | 0.0% | vingroup_distortion_flag=True among Tier 1–3 (scan boolean) |
| caution_proxy | 11 | 21.2% | vin_flag OR distribution_risk_flag OR score_risk_penalty>=45 (matches section 4 list) |
| outside_fund_disclosure | 48 | 92.3% | fund_context_bucket=outside_fund_disclosure among Tier 1–3 |

**Unknown sector in displayed look-first lists:** 2/26 (7.7%)
_(16 names enriched from `data/master/sector_map.csv` for display only.)_

## D. Changes since previous scan

_Previous scan date: 2026-05-26_

- **New Tier 1–2:** APS, SSB, VND
- **Dropped Tier 1–2:** DCL, IDJ, VC3
- **Tier change:** ACB Reject → Tier 3, Δ+5.3
- **Tier change:** APS Tier 3 → Tier 2, Δ+1.5
- **Tier change:** BVB Reject → Tier 3, Δ+7.3
- **Tier change:** CTR Tier 3 → Reject, Δ-6.7
- **Tier change:** DCL Tier 2 → Tier 3, Δ-5.8
- **Tier change:** DPR Tier 3 → Reject, Δ-3.3
- **Tier change:** FCN Reject → Tier 3, Δ+3.9
- **Tier change:** IDJ Tier 2 → Tier 3, Δ-2.2
- **Tier change:** MBS Tier 3 → Reject, Δ-0.2
- **Tier change:** MIG Reject → Tier 3, Δ+9.1
- **Tier change:** MST Reject → Tier 3, Δ+4.1
- **Tier change:** MZG Tier 3 → Reject, Δ-1.9
- **Score up:** PAS Δ+19.7 → Reject
- **Score up:** AMS Δ+13.7 → Reject
- **Score up:** HTM Δ+12.2 → Reject
- **Score up:** SDG Δ+12.1 → Reject
- **Score up:** KIP Δ+11.5 → Reject
- **Score down:** DWS Δ-13.3 → Reject
- **Score down:** LIC Δ-12.5 → Reject
- **Score down:** HD6 Δ-12.4 → Reject
- **Score down:** LLM Δ-11.8 → Reject
- **Score down:** VIM Δ-10.1 → Reject

## E. Workflow warnings (priority order)

- [P1 Structural] Top tier is 92% outside_fund_disclosure (48/52) — cross-check emerging vs April fund priors.
- [P3 Market] No Tier 1 names — narrow/fragile regime; prioritize Tier 2 focus + near-miss.
- [P4 Caution] Emerging universe has several elevated risk_penalty names — vet before prioritizing.
- [P4 Caution] caution-proxy (section 4 rule): 11/52 Tier 1–3 names (21%) — includes high risk_penalty, not only vin_distortion_flag.

## File map

| File | Role |
| --- | --- |
| `institutional_accumulation_{date}.csv` | Full ranked universe |
| `institutional_accumulation_{date}.json` | Machine payload |
| `institutional_accumulation_{date}.md` | Detailed methodology report |
| `institutional_accumulation_operator_summary_{date}.html` | **Browser view** — start here |
| `institutional_accumulation_operator_summary_{date}.md` | Same summary, markdown |
| `institutional_accumulation_operator_summary_{date}.json` | Same summary, JSON |
| `data/decision/institutional_accumulation_compact.json` | Weekly/council compact |
| `emerging_accumulation_{date}.csv` | Emerging-only list |
| `institutional_accumulation_diff_{date}.json` | WoW tier/score diff |

---
*End operator summary.*