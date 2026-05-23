# Institutional Accumulation — Operator Summary

**Scan date:** 2026-05-21  
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
| Tier 2 | 17 |
| Tier 3 | 37 |
| Reject | 1508 |
| Emerging (universe) | 34 |
| Top-tier fund-backed | 6 |
| Unknown sector (Tier 1–3) | 10/54 |

## B. What to look at first

### 1. Top fund-backed candidates (Tier 1–3)

- **VCB** (Tier 2, score 51.4, MF 67, risk 27, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Grouped money flow supportive
  - **Also:** bucket=consensus_core; OBV/PVT supportive; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Tier 2 — use full scan row for CMF/OBV detail.
- **GAS** (Tier 3, score 41.9, MF 61, risk 55, sector `Phân phối khí đốt`) — `fund_commentary_mention`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** bucket=fund_commentary_mention; OBV/PVT supportive; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (55)
  - **Note:** Size as research only until risk penalty improves.
- **STB** (Tier 3, score 41.2, MF 34, risk 15, sector `Ngân hàng`) — `consensus_second_ring`
  - **Why:** Tier held up mainly by context, not flow confirmation; weekly CMF still weak
  - **Also:** bucket=consensus_second_ring; context score elevated; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Investigate whether context is masking weak CMF/participation.
- **GVR** (Tier 3, score 41.0, MF 55, risk 42, sector `Hóa chất cơ bản - Sản phẩm nhựa, cao su, hóa chất`) — `selective_fund_bet`
  - **Why:** Grouped money flow supportive
  - **Also:** bucket=selective_fund_bet; context score elevated; weekly CMF still weak
  - **Risk:** Moderate risk penalty (42)
  - **Note:** Tier 3 — use full scan row for CMF/OBV detail.
- **CTG** (Tier 3, score 40.9, MF 50, risk 15, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Scan tier driven by mixed flow/context/risk profile
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Tier 3 — use full scan row for CMF/OBV detail.
- **BID** (Tier 3, score 39.4, MF 56, risk 55, sector `Ngân hàng`) — `fund_commentary_mention`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** bucket=fund_commentary_mention; CMF block strong; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (55)
  - **Note:** Size as research only until risk penalty improves.

### 2. Top emerging candidates (no fund tag)

- **MSB** (Tier 2, score 63.7, MF 88, risk 20, sector `Ngân hàng`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; OBV/PVT supportive; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **VPL** (Tier 2, score 53.8, MF 77, risk 0, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; OBV/PVT supportive
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **HHP** (Tier 2, score 53.8, MF 75, risk 18, sector `Giấy`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; OBV/PVT supportive; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **LPB** (Tier 2, score 50.3, MF 57, risk 12, sector `Ngân hàng`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **L40** (Tier 2, score 50.0, MF 59, risk 0, sector `Xây dựng, xây lắp`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **PCH** (Tier 2, score 49.5, MF 52, risk 0, sector `Hóa chất cơ bản - Sản phẩm nhựa, cao su, hóa chất`) — `outside_fund_disclosure`
  - **Why:** Emerging (no fund tag); flow/risk pass emerging gate
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **PSI** (Tier 2, score 49.2, MF 70, risk 27, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Emerging (no fund tag); flow/risk pass emerging gate
  - **Also:** CMF block strong; context score elevated; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **QNS** (Tier 2, score 49.0, MF 64, risk 15, sector `Sản phẩm thực phẩm`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.

### 3. Important rejects (fund-linked, flow failed)

- **GMD** (Reject, score 34.4, MF 42, risk 25, sector `Dịch vụ vận tải`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated
  - **Risk:** Distribution-day count elevated
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** distribution risk flag
- **HPG** (Reject, score 27.8, MF 26, risk 25, sector `Khai thác quặng sắt và sản xuất thép`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; distribution risk flag
- **MWG** (Reject, score 26.5, MF 24, risk 25, sector `Bán lẻ tổng hợp`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; distribution risk flag
- **MBB** (Reject, score 24.5, MF 25, risk 40, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; risk penalty elevated; distribution risk flag
- **VHM** (Reject, score 34.1, MF 39, risk 45, sector `Các công ty đầu cơ và phát triển bất động sản`) — `consensus_second_ring`
  - **Why:** VIN-linked name: elevated risk penalty; distortion flag not active at this as-of
  - **Also:** bucket=consensus_second_ring; context score thin
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (45); VIN name in caution via risk, not distortion flag
  - **Note:** Size as research only until risk penalty improves.
  - **Failed because:** weak grouped money flow; risk penalty elevated; distribution risk flag
- **POW** (Reject, score 33.6, MF 53, risk 52, sector `Sản xuất và cung cấp điện truyền thống`) — `fund_commentary_mention`
  - **Why:** Scan tier driven by mixed flow/context/risk profile
  - **Also:** bucket=fund_commentary_mention; CMF block strong; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (52)
  - **Note:** Size as research only until risk penalty improves.
  - **Failed because:** weekly CMF still weak; risk penalty elevated; distribution risk flag
- **BVH** (Reject, score 31.7, MF 40, risk 40, sector `Bảo hiểm nhân thọ`) — `selective_fund_bet`
  - **Why:** Fund-linked, but grouped money flow not confirming
  - **Also:** bucket=selective_fund_bet; CMF block strong; context score elevated
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Reject — use full scan row for CMF/OBV detail.
  - **Failed because:** weak grouped money flow; risk penalty elevated; distribution risk flag
- **TCB** (Reject, score 30.8, MF 41, risk 37, sector `Ngân hàng`) — `consensus_second_ring`
  - **Why:** Fund-linked, but grouped money flow not confirming
  - **Also:** bucket=consensus_second_ring; context score elevated; daily/weekly CMF conflict
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (37)
  - **Note:** Reject — use full scan row for CMF/OBV detail.
  - **Failed because:** daily/weekly CMF conflict; risk penalty elevated; distribution risk flag

### 4. Elevated risk / distortion / distribution (Tier 1–3; matches caution-proxy %)

- **BID** (Tier 3, score 39.4, MF 56, risk 55, sector `Ngân hàng`) — `fund_commentary_mention`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** bucket=fund_commentary_mention; CMF block strong; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (55)
  - **Note:** Size as research only until risk penalty improves.
- **GAS** (Tier 3, score 41.9, MF 61, risk 55, sector `Phân phối khí đốt`) — `fund_commentary_mention`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** bucket=fund_commentary_mention; OBV/PVT supportive; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (55)
  - **Note:** Size as research only until risk penalty improves.
- **PVP** (Tier 3, score 47.4, MF 61, risk 52, sector `Dịch vụ vận tải`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** CMF block strong; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; High risk penalty (52)
  - **Note:** Size as research only until risk penalty improves.
- **APS** (Tier 3, score 46.0, MF 69, risk 52, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** CMF block strong; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; High risk penalty (52)
  - **Note:** Size as research only until risk penalty improves.
- **PLX** (Tier 3, score 41.4, MF 60, risk 40, sector `Thăm dò và sản xuất dầu khí`) — `outside_fund_disclosure`
  - **Why:** Grouped money flow supportive
  - **Also:** CMF block strong; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Tier 3 — use full scan row for CMF/OBV detail.
- **BSR** (Tier 2, score 52.4, MF 70, risk 40, sector `Thăm dò và sản xuất dầu khí`) — `outside_fund_disclosure`
  - **Why:** Grouped money flow supportive
  - **Also:** CMF block strong; context score elevated
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** High-priority forensic review: strong flow without fund tag.
- **DXS** (Tier 3, score 45.4, MF 59, risk 40, sector `Các công ty đầu cơ và phát triển bất động sản`) — `outside_fund_disclosure`
  - **Why:** Grouped money flow supportive
  - **Also:** context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Tier 3 — use full scan row for CMF/OBV detail.
- **PHR** (Tier 3, score 45.5, MF 61, risk 40, sector `Hóa chất cơ bản - Sản phẩm nhựa, cao su, hóa chất`) — `outside_fund_disclosure`
  - **Why:** Grouped money flow supportive
  - **Also:** CMF block strong; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Tier 3 — use full scan row for CMF/OBV detail.

## C. Bucket mix

**Denominator:** All Tier 1–3 names in scan (n=54)

| Bucket | Count | % | Definition |
| --- | ---: | ---: | --- |
| fund_backed | 6 | 11.1% | has_fund_disclosure_tag among Tier 1–3 |
| emerging | 34 | 63.0% | emerging_accumulation_candidate among Tier 1–3 |
| vin_distortion_flagged | 0 | 0.0% | vingroup_distortion_flag=True among Tier 1–3 (scan boolean) |
| caution_proxy | 12 | 22.2% | vin_flag OR distribution_risk_flag OR score_risk_penalty>=45 (matches section 4 list) |
| outside_fund_disclosure | 48 | 88.9% | fund_context_bucket=outside_fund_disclosure among Tier 1–3 |

**Unknown sector in displayed look-first lists:** 3/28 (10.7%)
_(16 names enriched from `data/master/sector_map.csv` for display only.)_

## D. Changes since previous scan

_Previous scan date: 2026-05-22_

- **New Tier 1–2:** BSR, CDC, HII, VIX
- **Dropped Tier 1–2:** C69, IDJ, NAF
- **Tier change:** BID Reject → Tier 3, Δ+3.5
- **Tier change:** BSR Tier 3 → Tier 2, Δ+5.8
- **Tier change:** C69 Tier 2 → Tier 3, Δ-7.8
- **Tier change:** CDC Tier 3 → Tier 2, Δ+4.1
- **Tier change:** FOX Tier 3 → Reject, Δ-2.3
- **Tier change:** HCM Reject → Tier 3, Δ+3.4
- **Tier change:** HII Tier 3 → Tier 2, Δ+1.9
- **Tier change:** IDJ Tier 2 → Tier 3, Δ-4.0
- **Tier change:** MST Tier 3 → Reject, Δ-3.7
- **Tier change:** NAF Tier 2 → Tier 3, Δ-3.3
- **Tier change:** PDR Reject → Tier 3, Δ+3.5
- **Tier change:** PVT Reject → Tier 3, Δ+2.7
- **Score up:** VSM Δ+13.8 → Reject
- **Score up:** L45 Δ+12.6 → Reject
- **Score up:** PXT Δ+12.6 → Reject
- **Score up:** SP2 Δ+11.7 → Reject
- **Score up:** DP2 Δ+11.1 → Reject
- **Score down:** CMN Δ-14.2 → Reject
- **Score down:** CEN Δ-14.0 → Reject
- **Score down:** BHC Δ-14.0 → Reject
- **Score down:** IPA Δ-13.4 → Reject
- **Score down:** S12 Δ-13.2 → Reject

## E. Workflow warnings (priority order)

- [P1 Structural] Top tier is 89% outside_fund_disclosure (48/54) — cross-check emerging vs April fund priors.
- [P2 Data] Unknown sector in displayed look-first lists: 3/28 — interpret sector/theme bullets cautiously.
- [P3 Market] No Tier 1 names — narrow/fragile regime; prioritize Tier 2 focus + near-miss.
- [P4 Caution] Emerging universe has several elevated risk_penalty names — vet before prioritizing.
- [P4 Caution] caution-proxy (section 4 rule): 12/54 Tier 1–3 names (22%) — includes high risk_penalty, not only vin_distortion_flag.

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