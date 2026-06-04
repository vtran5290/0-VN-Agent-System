# Institutional Accumulation — Operator Summary

**Scan date:** 2026-05-26  
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
| Tier 3 | 31 |
| Reject | 1512 |
| Emerging (universe) | 27 |
| Top-tier fund-backed | 3 |
| Unknown sector (Tier 1–3) | 9/50 |

## B. What to look at first

### 1. Top fund-backed candidates (Tier 1–3)

- **VCB** (Tier 2, score 58.2, MF 75, risk 0, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Grouped money flow supportive
  - **Also:** bucket=consensus_core; OBV/PVT supportive; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Tier 2 — use full scan row for CMF/OBV detail.
- **GAS** (Tier 3, score 45.3, MF 64, risk 40, sector `Phân phối khí đốt`) — `fund_commentary_mention`
  - **Why:** Grouped money flow supportive
  - **Also:** bucket=fund_commentary_mention; OBV/PVT supportive; context score elevated
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Tier 3 — use full scan row for CMF/OBV detail.
- **CTG** (Tier 3, score 38.1, MF 38, risk 15, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Tier held up mainly by context, not flow confirmation; weekly CMF still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Investigate whether context is masking weak CMF/participation.

### 2. Top emerging candidates (no fund tag)

- **MSB** (Tier 2, score 61.8, MF 82, risk 20, sector `Ngân hàng`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; OBV/PVT supportive; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **VPL** (Tier 2, score 58.2, MF 77, risk 0, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; OBV/PVT supportive
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **HHP** (Tier 2, score 58.0, MF 74, risk 0, sector `Giấy`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; OBV/PVT supportive; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **QNS** (Tier 2, score 50.5, MF 60, risk 15, sector `Sản phẩm thực phẩm`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **DCL** (Tier 2, score 50.4, MF 70, risk 0, sector `Dược phẩm`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **C69** (Tier 2, score 50.1, MF 53, risk 0, sector `Xây dựng, xây lắp`) — `outside_fund_disclosure`
  - **Why:** Emerging (no fund tag); flow/risk pass emerging gate
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **DL1** (Tier 2, score 50.1, MF 67, risk 18, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** OBV/PVT supportive; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **NAF** (Tier 2, score 50.0, MF 51, risk 0, sector `Bia`) — `outside_fund_disclosure`
  - **Why:** Emerging (no fund tag); flow/risk pass emerging gate
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.

### 3. Important rejects (fund-linked, flow failed)

- **GMD** (Reject, score 35.2, MF 47, risk 40, sector `Dịch vụ vận tải`) — `consensus_core`
  - **Why:** Consensus-core name below accumulation tier thresholds
  - **Also:** bucket=consensus_core; CMF block strong; context score elevated
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** risk penalty elevated; distribution risk flag
- **HPG** (Reject, score 25.3, MF 27, risk 40, sector `Khai thác quặng sắt và sản xuất thép`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; risk penalty elevated; distribution risk flag
- **MBB** (Reject, score 24.7, MF 25, risk 40, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; risk penalty elevated; distribution risk flag
- **MWG** (Reject, score 24.3, MF 18, risk 25, sector `Bán lẻ tổng hợp`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; distribution risk flag
- **STB** (Reject, score 38.0, MF 32, risk 15, sector `Ngân hàng`) — `consensus_second_ring`
  - **Why:** Fund-linked, but grouped money flow not confirming
  - **Also:** bucket=consensus_second_ring; context score elevated; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Reject — use full scan row for CMF/OBV detail.
  - **Failed because:** weak grouped money flow; weekly CMF still weak
- **ACB** (Reject, score 36.8, MF 46, risk 55, sector `Ngân hàng`) — `fund_commentary_mention`
  - **Why:** Scan tier driven by mixed flow/context/risk profile
  - **Also:** bucket=fund_commentary_mention; CMF block strong; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (55)
  - **Note:** Size as research only until risk penalty improves.
  - **Failed because:** risk penalty elevated; distribution risk flag
- **TCB** (Reject, score 35.7, MF 39, risk 15, sector `Ngân hàng`) — `consensus_second_ring`
  - **Why:** Fund-linked, but grouped money flow not confirming
  - **Also:** bucket=consensus_second_ring; CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Reject — use full scan row for CMF/OBV detail.
  - **Failed because:** weak grouped money flow
- **GVR** (Reject, score 35.6, MF 39, risk 52, sector `Hóa chất cơ bản - Sản phẩm nhựa, cao su, hóa chất`) — `selective_fund_bet`
  - **Why:** Fund-linked, but grouped money flow not confirming
  - **Also:** bucket=selective_fund_bet; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; High risk penalty (52)
  - **Note:** Size as research only until risk penalty improves.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; risk penalty elevated; distribution risk flag

### 4. Elevated risk / distortion / distribution (Tier 1–3; matches caution-proxy %)

- **BSR** (Tier 3, score 42.2, MF 56, risk 55, sector `Thăm dò và sản xuất dầu khí`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (55)
  - **Note:** Size as research only until risk penalty improves.
- **POM** (Tier 3, score 43.6, MF 57, risk 53, sector `Steel`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** context score elevated; daily CMF missing
  - **Risk:** High risk penalty (53)
  - **Note:** Size as research only until risk penalty improves.
- **CTR** (Tier 3, score 43.7, MF 66, risk 52, sector `Xây dựng, xây lắp`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** CMF block strong; OBV/PVT supportive; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (52)
  - **Note:** Size as research only until risk penalty improves.
- **TVN** (Tier 2, score 56.2, MF 80, risk 50, sector `Khai thác quặng sắt và sản xuất thép`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** CMF block strong; context score elevated
  - **Risk:** High risk penalty (50)
  - **Note:** High-priority forensic review: strong flow without fund tag.
- **PET** (Tier 2, score 46.2, MF 55, risk 40, sector `Bán lẻ tổng hợp`) — `outside_fund_disclosure`
  - **Why:** Grouped money flow supportive
  - **Also:** CMF block strong; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** High-priority forensic review: strong flow without fund tag.
- **GAS** (Tier 3, score 45.3, MF 64, risk 40, sector `Phân phối khí đốt`) — `fund_commentary_mention`
  - **Why:** Grouped money flow supportive
  - **Also:** bucket=fund_commentary_mention; OBV/PVT supportive; context score elevated
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Tier 3 — use full scan row for CMF/OBV detail.
- **DXS** (Tier 2, score 48.4, MF 61, risk 37, sector `Các công ty đầu cơ và phát triển bất động sản`) — `outside_fund_disclosure`
  - **Why:** Grouped money flow supportive
  - **Also:** CMF block strong; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (37)
  - **Note:** High-priority forensic review: strong flow without fund tag.
- **VIX** (Tier 3, score 44.5, MF 51, risk 25, sector `Công ty chứng khoán`) — `outside_fund_disclosure`
  - **Why:** Emerging (no fund tag); flow/risk pass emerging gate
  - **Also:** context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated
  - **Note:** Tier 3 — use full scan row for CMF/OBV detail.

## C. Bucket mix

**Denominator:** All Tier 1–3 names in scan (n=50)

| Bucket | Count | % | Definition |
| --- | ---: | ---: | --- |
| fund_backed | 3 | 6.0% | has_fund_disclosure_tag among Tier 1–3 |
| emerging | 27 | 54.0% | emerging_accumulation_candidate among Tier 1–3 |
| vin_distortion_flagged | 0 | 0.0% | vingroup_distortion_flag=True among Tier 1–3 (scan boolean) |
| caution_proxy | 11 | 22.0% | vin_flag OR distribution_risk_flag OR score_risk_penalty>=45 (matches section 4 list) |
| outside_fund_disclosure | 47 | 94.0% | fund_context_bucket=outside_fund_disclosure among Tier 1–3 |

**Unknown sector in displayed look-first lists:** 2/26 (7.7%)
_(16 names enriched from `data/master/sector_map.csv` for display only.)_

## D. Changes since previous scan

_Previous scan date: 2026-05-22_

- **New Tier 1–2:** DXS, PDR, PET, TLD, VC3, VPI
- **Dropped Tier 1–2:** CTR, L40, PCH
- **Tier change:** CTF Reject → Tier 3, Δ+3.5
- **Tier change:** CTR Tier 2 → Tier 3, Δ-3.5
- **Tier change:** DBD Tier 3 → Reject, Δ-7.5
- **Tier change:** DXS Tier 3 → Tier 2, Δ+2.1
- **Tier change:** FOX Tier 3 → Reject, Δ-5.0
- **Tier change:** GEX Tier 3 → Reject, Δ-0.8
- **Tier change:** GVR Tier 3 → Reject, Δ-3.1
- **Tier change:** HNG Tier 3 → Reject, Δ-7.9
- **Tier change:** KDC Reject → Tier 3, Δ+4.5
- **Tier change:** L40 Tier 2 → Tier 3, Δ-8.4
- **Tier change:** MBS Reject → Tier 3, Δ+11.7
- **Tier change:** MST Tier 3 → Reject, Δ-5.7
- **Score up:** VAB Δ+20.5 → Tier 3
- **Score up:** VSM Δ+19.0 → Reject
- **Score up:** SMA Δ+15.6 → Reject
- **Score up:** LIG Δ+15.4 → Reject
- **Score up:** NVB Δ+15.1 → Reject
- **Score down:** VHE Δ-22.6 → Reject
- **Score down:** SJS Δ-15.5 → Reject
- **Score down:** TGP Δ-15.2 → Reject
- **Score down:** SZG Δ-14.5 → Reject
- **Score down:** SBB Δ-11.8 → Reject

## E. Workflow warnings (priority order)

- [P1 Structural] Top tier is 94% outside_fund_disclosure (47/50) — cross-check emerging vs April fund priors.
- [P3 Market] No Tier 1 names — narrow/fragile regime; prioritize Tier 2 focus + near-miss.
- [P4 Caution] Emerging universe has several elevated risk_penalty names — vet before prioritizing.
- [P4 Caution] caution-proxy (section 4 rule): 11/50 Tier 1–3 names (22%) — includes high risk_penalty, not only vin_distortion_flag.

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