# Institutional Accumulation — Operator Summary

**Scan date:** 2026-05-22  
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
| Tier 2 | 16 |
| Tier 3 | 37 |
| Reject | 1509 |
| Emerging (universe) | 34 |
| Top-tier fund-backed | 5 |
| Unknown sector (Tier 1–3) | 10/53 |

## B. What to look at first

### 1. Top fund-backed candidates (Tier 1–3)

- **VCB** (Tier 2, score 51.8, MF 67, risk 27, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Grouped money flow supportive
  - **Also:** bucket=consensus_core; OBV/PVT supportive; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Tier 2 — use full scan row for CMF/OBV detail.
- **GAS** (Tier 3, score 41.3, MF 62, risk 55, sector `Phân phối khí đốt`) — `fund_commentary_mention`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** bucket=fund_commentary_mention; OBV/PVT supportive; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (55)
  - **Note:** Size as research only until risk penalty improves.
- **CTG** (Tier 3, score 39.4, MF 49, risk 15, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Scan tier driven by mixed flow/context/risk profile
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Tier 3 — use full scan row for CMF/OBV detail.
- **STB** (Tier 3, score 38.7, MF 34, risk 15, sector `Ngân hàng`) — `consensus_second_ring`
  - **Why:** Tier held up mainly by context, not flow confirmation; weekly CMF still weak
  - **Also:** bucket=consensus_second_ring; context score elevated; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Investigate whether context is masking weak CMF/participation.
- **GVR** (Tier 3, score 38.7, MF 54, risk 52, sector `Hóa chất cơ bản - Sản phẩm nhựa, cao su, hóa chất`) — `selective_fund_bet`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** bucket=selective_fund_bet; CMF block strong; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (52)
  - **Note:** Size as research only until risk penalty improves.

### 2. Top emerging candidates (no fund tag)

- **HHP** (Tier 2, score 57.4, MF 75, risk 0, sector `Giấy`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; OBV/PVT supportive; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **VPL** (Tier 2, score 55.0, MF 77, risk 0, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; OBV/PVT supportive
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **DCL** (Tier 2, score 53.1, MF 66, risk 0, sector `Dược phẩm`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **L40** (Tier 2, score 52.2, MF 61, risk 0, sector `Xây dựng, xây lắp`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **PCH** (Tier 2, score 51.6, MF 56, risk 0, sector `Hóa chất cơ bản - Sản phẩm nhựa, cao su, hóa chất`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **C69** (Tier 2, score 51.1, MF 64, risk 18, sector `Xây dựng, xây lắp`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **QNS** (Tier 2, score 50.4, MF 63, risk 15, sector `Sản phẩm thực phẩm`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **LPB** (Tier 2, score 50.0, MF 56, risk 12, sector `Ngân hàng`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.

### 3. Important rejects (fund-linked, flow failed)

- **GMD** (Reject, score 33.0, MF 48, risk 40, sector `Dịch vụ vận tải`) — `consensus_core`
  - **Why:** Consensus-core name below accumulation tier thresholds
  - **Also:** bucket=consensus_core; CMF block strong; context score elevated
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** risk penalty elevated; distribution risk flag
- **MWG** (Reject, score 28.1, MF 24, risk 15, sector `Bán lẻ tổng hợp`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak
- **HPG** (Reject, score 25.7, MF 22, risk 25, sector `Khai thác quặng sắt và sản xuất thép`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; distribution risk flag
- **MBB** (Reject, score 24.1, MF 24, risk 40, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; risk penalty elevated; distribution risk flag
- **BID** (Reject, score 35.9, MF 54, risk 67, sector `Ngân hàng`) — `fund_commentary_mention`
  - **Why:** Scan tier driven by mixed flow/context/risk profile
  - **Also:** bucket=fund_commentary_mention; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; High risk penalty (67)
  - **Note:** Size as research only until risk penalty improves.
  - **Failed because:** weekly CMF still weak; risk penalty elevated; distribution risk flag
- **BVH** (Reject, score 35.3, MF 44, risk 40, sector `Bảo hiểm nhân thọ`) — `selective_fund_bet`
  - **Why:** Scan tier driven by mixed flow/context/risk profile
  - **Also:** bucket=selective_fund_bet; CMF block strong; context score elevated
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Reject — use full scan row for CMF/OBV detail.
  - **Failed because:** risk penalty elevated; distribution risk flag
- **FPT** (Reject, score 32.4, MF 49, risk 40, sector `Công nghệ phần mềm`) — `fund_commentary_mention`
  - **Why:** Scan tier driven by mixed flow/context/risk profile
  - **Also:** bucket=fund_commentary_mention; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Reject — use full scan row for CMF/OBV detail.
  - **Failed because:** weekly CMF still weak; risk penalty elevated; distribution risk flag
- **POW** (Reject, score 29.8, MF 43, risk 67, sector `Sản xuất và cung cấp điện truyền thống`) — `fund_commentary_mention`
  - **Why:** Scan tier driven by mixed flow/context/risk profile
  - **Also:** bucket=fund_commentary_mention; CMF block strong; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (67)
  - **Note:** Size as research only until risk penalty improves.
  - **Failed because:** weekly CMF still weak; risk penalty elevated; distribution risk flag

### 4. Elevated risk / distortion / distribution (Tier 1–3; matches caution-proxy %)

- **PVP** (Tier 3, score 39.3, MF 53, risk 67, sector `Dịch vụ vận tải`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; High risk penalty (67)
  - **Note:** Size as research only until risk penalty improves.
- **BSR** (Tier 3, score 46.6, MF 66, risk 55, sector `Thăm dò và sản xuất dầu khí`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** CMF block strong; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (55)
  - **Note:** Size as research only until risk penalty improves.
- **GAS** (Tier 3, score 41.3, MF 62, risk 55, sector `Phân phối khí đốt`) — `fund_commentary_mention`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** bucket=fund_commentary_mention; OBV/PVT supportive; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (55)
  - **Note:** Size as research only until risk penalty improves.
- **POM** (Tier 3, score 45.6, MF 54, risk 53, sector `Steel`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** context score elevated; daily CMF missing
  - **Risk:** High risk penalty (53)
  - **Note:** Size as research only until risk penalty improves.
- **DXS** (Tier 3, score 46.3, MF 61, risk 52, sector `Các công ty đầu cơ và phát triển bất động sản`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; High risk penalty (52)
  - **Note:** Size as research only until risk penalty improves.
- **APS** (Tier 3, score 46.0, MF 68, risk 52, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** CMF block strong; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; High risk penalty (52)
  - **Note:** Size as research only until risk penalty improves.
- **GVR** (Tier 3, score 38.7, MF 54, risk 52, sector `Hóa chất cơ bản - Sản phẩm nhựa, cao su, hóa chất`) — `selective_fund_bet`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** bucket=selective_fund_bet; CMF block strong; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (52)
  - **Note:** Size as research only until risk penalty improves.
- **PLX** (Tier 3, score 40.2, MF 59, risk 40, sector `Thăm dò và sản xuất dầu khí`) — `outside_fund_disclosure`
  - **Why:** Grouped money flow supportive
  - **Also:** context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Tier 3 — use full scan row for CMF/OBV detail.

## C. Bucket mix

**Denominator:** All Tier 1–3 names in scan (n=53)

| Bucket | Count | % | Definition |
| --- | ---: | ---: | --- |
| fund_backed | 5 | 9.4% | has_fund_disclosure_tag among Tier 1–3 |
| emerging | 34 | 64.2% | emerging_accumulation_candidate among Tier 1–3 |
| vin_distortion_flagged | 0 | 0.0% | vingroup_distortion_flag=True among Tier 1–3 (scan boolean) |
| caution_proxy | 14 | 26.4% | vin_flag OR distribution_risk_flag OR score_risk_penalty>=45 (matches section 4 list) |
| outside_fund_disclosure | 48 | 90.6% | fund_context_bucket=outside_fund_disclosure among Tier 1–3 |

**Unknown sector in displayed look-first lists:** 2/27 (7.4%)
_(16 names enriched from `data/master/sector_map.csv` for display only.)_

## D. Changes since previous scan

_Previous scan date: 2026-05-21_

- **New Tier 1–2:** C69, IDJ, NAF
- **Dropped Tier 1–2:** BSR, CDC, HII, VIX
- **Tier change:** BID Tier 3 → Reject, Δ-3.5
- **Tier change:** BSR Tier 2 → Tier 3, Δ-5.8
- **Tier change:** C69 Tier 3 → Tier 2, Δ+7.8
- **Tier change:** CDC Tier 2 → Tier 3, Δ-4.1
- **Tier change:** FOX Reject → Tier 3, Δ+2.3
- **Tier change:** HCM Tier 3 → Reject, Δ-3.4
- **Tier change:** HII Tier 2 → Tier 3, Δ-1.9
- **Tier change:** IDJ Tier 3 → Tier 2, Δ+4.0
- **Tier change:** MST Reject → Tier 3, Δ+3.7
- **Tier change:** NAF Tier 3 → Tier 2, Δ+3.3
- **Tier change:** PDR Tier 3 → Reject, Δ-3.5
- **Tier change:** PVT Tier 3 → Reject, Δ-2.7
- **Score up:** CMN Δ+14.2 → Reject
- **Score up:** CEN Δ+14.0 → Reject
- **Score up:** BHC Δ+14.0 → Reject
- **Score up:** IPA Δ+13.4 → Reject
- **Score up:** S12 Δ+13.2 → Reject
- **Score down:** VSM Δ-13.8 → Reject
- **Score down:** L45 Δ-12.6 → Reject
- **Score down:** PXT Δ-12.6 → Reject
- **Score down:** SP2 Δ-11.7 → Reject
- **Score down:** DP2 Δ-11.1 → Reject

## E. Workflow warnings (priority order)

- [P1 Structural] Top tier is 91% outside_fund_disclosure (48/53) — cross-check emerging vs April fund priors.
- [P3 Market] No Tier 1 names — narrow/fragile regime; prioritize Tier 2 focus + near-miss.
- [P4 Caution] Emerging universe has several elevated risk_penalty names — vet before prioritizing.
- [P4 Caution] caution-proxy (section 4 rule): 14/53 Tier 1–3 names (26%) — includes high risk_penalty, not only vin_distortion_flag.

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