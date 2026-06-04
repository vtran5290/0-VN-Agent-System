# Institutional Accumulation — Operator Summary

**Scan date:** 2026-05-29  
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
| Tier 2 | 13 |
| Tier 3 | 29 |
| Reject | 1520 |
| Emerging (universe) | 20 |
| Top-tier fund-backed | 4 |
| Unknown sector (Tier 1–3) | 8/42 |

## B. What to look at first

### 1. Top fund-backed candidates (Tier 1–3)

- **VCB** (Tier 3, score 46.9, MF 60, risk 52, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** bucket=consensus_core; OBV/PVT supportive; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (52)
  - **Note:** Size as research only until risk penalty improves.
- **ACB** (Tier 3, score 41.0, MF 59, risk 55, sector `Ngân hàng`) — `fund_commentary_mention`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** bucket=fund_commentary_mention; CMF block strong; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (55)
  - **Note:** Size as research only until risk penalty improves.
- **GAS** (Tier 3, score 40.3, MF 56, risk 67, sector `Phân phối khí đốt`) — `fund_commentary_mention`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** bucket=fund_commentary_mention; OBV/PVT supportive; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (67)
  - **Note:** Size as research only until risk penalty improves.
- **TCB** (Tier 3, score 38.4, MF 40, risk 15, sector `Ngân hàng`) — `consensus_second_ring`
  - **Why:** Tier held up mainly by context, not flow confirmation
  - **Also:** bucket=consensus_second_ring; CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Investigate whether context is masking weak CMF/participation.

### 2. Top emerging candidates (no fund tag)

- **MSB** (Tier 2, score 64.6, MF 90, risk 20, sector `Ngân hàng`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; OBV/PVT supportive; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **HHP** (Tier 2, score 57.2, MF 71, risk 0, sector `Giấy`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; OBV/PVT supportive; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **VPL** (Tier 2, score 56.3, MF 73, risk 0, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; OBV/PVT supportive
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **NAF** (Tier 2, score 54.9, MF 58, risk 0, sector `Bia`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **KSF** (Tier 2, score 52.5, MF 81, risk 25, sector `Các công ty đầu cơ và phát triển bất động sản`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; OBV/PVT supportive; context score elevated
  - **Risk:** Distribution-day count elevated
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **MIG** (Tier 2, score 52.1, MF 71, risk 27, sector `Bảo hiểm tổng hợp`) — `outside_fund_disclosure`
  - **Why:** Emerging (no fund tag); flow/risk pass emerging gate
  - **Also:** CMF block strong; context score elevated; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **PSI** (Tier 2, score 49.5, MF 63, risk 27, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Emerging (no fund tag); flow/risk pass emerging gate
  - **Also:** CMF block strong; context score elevated; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **KDC** (Tier 2, score 48.7, MF 67, risk 25, sector `Sản phẩm thực phẩm`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated
  - **Risk:** Distribution-day count elevated
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.

### 3. Important rejects (fund-linked, flow failed)

- **CTG** (Reject, score 34.1, MF 32, risk 15, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak
- **GMD** (Reject, score 29.5, MF 40, risk 40, sector `Dịch vụ vận tải`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; CMF block strong; context score elevated
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; risk penalty elevated; distribution risk flag
- **HPG** (Reject, score 27.6, MF 24, risk 40, sector `Khai thác quặng sắt và sản xuất thép`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; risk penalty elevated; distribution risk flag
- **MBB** (Reject, score 23.1, MF 21, risk 40, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; risk penalty elevated; distribution risk flag
- **MWG** (Reject, score 21.6, MF 17, risk 40, sector `Bán lẻ tổng hợp`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; risk penalty elevated; distribution risk flag
- **BVH** (Reject, score 34.2, MF 48, risk 40, sector `Bảo hiểm nhân thọ`) — `selective_fund_bet`
  - **Why:** Scan tier driven by mixed flow/context/risk profile
  - **Also:** bucket=selective_fund_bet; CMF block strong; context score elevated
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Reject — use full scan row for CMF/OBV detail.
  - **Failed because:** risk penalty elevated; distribution risk flag
- **POW** (Reject, score 34.0, MF 38, risk 67, sector `Sản xuất và cung cấp điện truyền thống`) — `fund_commentary_mention`
  - **Why:** Fund-linked, but grouped money flow not confirming
  - **Also:** bucket=fund_commentary_mention; CMF block strong; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (67)
  - **Note:** Size as research only until risk penalty improves.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; risk penalty elevated; distribution risk flag
- **VHM** (Reject, score 33.8, MF 44, risk 60, sector `Các công ty đầu cơ và phát triển bất động sản`) — `consensus_second_ring`
  - **Why:** VIN-linked name: elevated risk penalty; distortion flag not active at this as-of
  - **Also:** bucket=consensus_second_ring; CMF block strong; context score thin
  - **Risk:** Distribution-day count elevated; High risk penalty (60); VIN name in caution via risk, not distortion flag
  - **Note:** Size as research only until risk penalty improves.
  - **Failed because:** risk penalty elevated; distribution risk flag

### 4. Elevated risk / distortion / distribution (Tier 1–3; matches caution-proxy %)

- **GAS** (Tier 3, score 40.3, MF 56, risk 67, sector `Phân phối khí đốt`) — `fund_commentary_mention`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** bucket=fund_commentary_mention; OBV/PVT supportive; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (67)
  - **Note:** Size as research only until risk penalty improves.
- **IDJ** (Tier 3, score 38.6, MF 42, risk 65, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Scan tier driven by mixed flow/context/risk profile
  - **Also:** context score elevated; weekly CMF still weak
  - **Risk:** High risk penalty (65)
  - **Note:** Size as research only until risk penalty improves.
- **ACB** (Tier 3, score 41.0, MF 59, risk 55, sector `Ngân hàng`) — `fund_commentary_mention`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** bucket=fund_commentary_mention; CMF block strong; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (55)
  - **Note:** Size as research only until risk penalty improves.
- **POM** (Tier 3, score 42.5, MF 62, risk 53, sector `Steel`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** context score elevated; daily CMF missing
  - **Risk:** High risk penalty (53)
  - **Note:** Size as research only until risk penalty improves.
- **VCB** (Tier 3, score 46.9, MF 60, risk 52, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** bucket=consensus_core; OBV/PVT supportive; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (52)
  - **Note:** Size as research only until risk penalty improves.
- **APS** (Tier 3, score 40.5, MF 48, risk 45, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Scan tier driven by mixed flow/context/risk profile
  - **Also:** context score elevated; weekly CMF still weak
  - **Risk:** Moderate risk penalty (45)
  - **Note:** Size as research only until risk penalty improves.
- **VNE** (Tier 3, score 39.2, MF 65, risk 40, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Grouped money flow supportive
  - **Also:** context score elevated; daily CMF missing
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Tier 3 — use full scan row for CMF/OBV detail.
- **PET** (Tier 3, score 42.0, MF 52, risk 40, sector `Bán lẻ tổng hợp`) — `outside_fund_disclosure`
  - **Why:** Scan tier driven by mixed flow/context/risk profile
  - **Also:** CMF block strong; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Tier 3 — use full scan row for CMF/OBV detail.

## C. Bucket mix

**Denominator:** All Tier 1–3 names in scan (n=42)

| Bucket | Count | % | Definition |
| --- | ---: | ---: | --- |
| fund_backed | 4 | 9.5% | has_fund_disclosure_tag among Tier 1–3 |
| emerging | 20 | 47.6% | emerging_accumulation_candidate among Tier 1–3 |
| vin_distortion_flagged | 0 | 0.0% | vingroup_distortion_flag=True among Tier 1–3 (scan boolean) |
| caution_proxy | 12 | 28.6% | vin_flag OR distribution_risk_flag OR score_risk_penalty>=45 (matches section 4 list) |
| outside_fund_disclosure | 38 | 90.5% | fund_context_bucket=outside_fund_disclosure among Tier 1–3 |

**Unknown sector in displayed look-first lists:** 5/25 (20.0%)
_(16 names enriched from `data/master/sector_map.csv` for display only.)_

## D. Changes since previous scan

_Previous scan date: 2026-05-28_

- **New Tier 1–2:** KSF
- **Dropped Tier 1–2:** DXS, LPB, OGC, PDR, POM, VCB, VND
- **Tier change:** CTF Tier 3 → Reject, Δ-3.1
- **Tier change:** CTG Tier 3 → Reject, Δ-4.3
- **Tier change:** CTR Tier 3 → Reject, Δ-0.7
- **Tier change:** DHA Tier 3 → Reject, Δ-6.0
- **Tier change:** DXS Tier 2 → Reject, Δ-8.3
- **Tier change:** HCM Tier 3 → Reject, Δ-2.1
- **Tier change:** HII Tier 3 → Reject, Δ-6.8
- **Tier change:** KSF Reject → Tier 2, Δ+15.4
- **Tier change:** LPB Tier 2 → Tier 3, Δ-9.0
- **Tier change:** MBS Tier 3 → Reject, Δ-2.5
- **Tier change:** MZG Tier 3 → Reject, Δ-6.0
- **Tier change:** NDN Tier 3 → Reject, Δ-1.3
- **Score up:** VHE Δ+18.2 → Reject
- **Score up:** KSF Δ+15.4 → Tier 2
- **Score up:** FIC Δ+15.0 → Reject
- **Score up:** VE8 Δ+14.2 → Reject
- **Score up:** BVG Δ+13.1 → Reject
- **Score down:** SGH Δ-16.1 → Reject
- **Score down:** VIT Δ-15.2 → Reject
- **Score down:** SZL Δ-14.1 → Reject
- **Score down:** CRV Δ-11.6 → Reject
- **Score down:** CTP Δ-11.5 → Reject

## E. Workflow warnings (priority order)

- [P1 Structural] Top tier is 90% outside_fund_disclosure (38/42) — cross-check emerging vs April fund priors.
- [P2 Data] Unknown sector in displayed look-first lists: 5/25 — interpret sector/theme bullets cautiously.
- [P3 Market] No Tier 1 names — narrow/fragile regime; prioritize Tier 2 focus + near-miss.
- [P4 Caution] Emerging universe has several elevated risk_penalty names — vet before prioritizing.
- [P4 Caution] caution-proxy (section 4 rule): 12/42 Tier 1–3 names (29%) — includes high risk_penalty, not only vin_distortion_flag.

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