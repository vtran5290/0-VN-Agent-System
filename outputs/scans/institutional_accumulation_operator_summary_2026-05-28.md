# Institutional Accumulation — Operator Summary

**Scan date:** 2026-05-28  
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
| Emerging (universe) | 24 |
| Top-tier fund-backed | 4 |
| Unknown sector (Tier 1–3) | 9/50 |

## B. What to look at first

### 1. Top fund-backed candidates (Tier 1–3)

- **VCB** (Tier 2, score 48.4, MF 60, risk 42, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Grouped money flow supportive
  - **Also:** bucket=consensus_core; OBV/PVT supportive; context score elevated
  - **Risk:** Moderate risk penalty (42)
  - **Note:** Tier 2 — use full scan row for CMF/OBV detail.
- **GAS** (Tier 3, score 41.4, MF 54, risk 55, sector `Phân phối khí đốt`) — `fund_commentary_mention`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** bucket=fund_commentary_mention; OBV/PVT supportive; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (55)
  - **Note:** Size as research only until risk penalty improves.
- **ACB** (Tier 3, score 39.9, MF 54, risk 55, sector `Ngân hàng`) — `fund_commentary_mention`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** bucket=fund_commentary_mention; CMF block strong; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (55)
  - **Note:** Size as research only until risk penalty improves.
- **CTG** (Tier 3, score 38.4, MF 35, risk 0, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Tier held up mainly by context, not flow confirmation; weekly CMF still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Investigate whether context is masking weak CMF/participation.

### 2. Top emerging candidates (no fund tag)

- **MSB** (Tier 2, score 64.5, MF 90, risk 20, sector `Ngân hàng`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; OBV/PVT supportive; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **HHP** (Tier 2, score 57.6, MF 74, risk 0, sector `Giấy`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; OBV/PVT supportive; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **VPL** (Tier 2, score 55.7, MF 73, risk 0, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; OBV/PVT supportive; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **NAF** (Tier 2, score 53.7, MF 56, risk 0, sector `Bia`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **MIG** (Tier 2, score 51.3, MF 67, risk 27, sector `Bảo hiểm tổng hợp`) — `outside_fund_disclosure`
  - **Why:** Emerging (no fund tag); flow/risk pass emerging gate
  - **Also:** CMF block strong; context score elevated; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **PSI** (Tier 2, score 50.9, MF 63, risk 27, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Emerging (no fund tag); flow/risk pass emerging gate
  - **Also:** CMF block strong; context score elevated; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **TLD** (Tier 2, score 49.0, MF 56, risk 0, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **DL1** (Tier 2, score 48.9, MF 62, risk 18, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** OBV/PVT supportive; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.

### 3. Important rejects (fund-linked, flow failed)

- **GMD** (Reject, score 30.6, MF 41, risk 40, sector `Dịch vụ vận tải`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; CMF block strong; context score elevated
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** risk penalty elevated; distribution risk flag
- **HPG** (Reject, score 24.8, MF 26, risk 40, sector `Khai thác quặng sắt và sản xuất thép`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; risk penalty elevated; distribution risk flag
- **MWG** (Reject, score 24.2, MF 18, risk 25, sector `Bán lẻ tổng hợp`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; distribution risk flag
- **MBB** (Reject, score 23.5, MF 21, risk 40, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; risk penalty elevated; distribution risk flag
- **BVH** (Reject, score 35.4, MF 51, risk 40, sector `Bảo hiểm nhân thọ`) — `selective_fund_bet`
  - **Why:** Scan tier driven by mixed flow/context/risk profile
  - **Also:** bucket=selective_fund_bet; CMF block strong; context score elevated
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Reject — use full scan row for CMF/OBV detail.
  - **Failed because:** risk penalty elevated; distribution risk flag
- **TCB** (Reject, score 34.5, MF 39, risk 15, sector `Ngân hàng`) — `consensus_second_ring`
  - **Why:** Fund-linked, but grouped money flow not confirming
  - **Also:** bucket=consensus_second_ring; CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Reject — use full scan row for CMF/OBV detail.
  - **Failed because:** weak grouped money flow
- **POW** (Reject, score 34.2, MF 40, risk 67, sector `Sản xuất và cung cấp điện truyền thống`) — `fund_commentary_mention`
  - **Why:** Fund-linked, but grouped money flow not confirming
  - **Also:** bucket=fund_commentary_mention; CMF block strong; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (67)
  - **Note:** Size as research only until risk penalty improves.
  - **Failed because:** weekly CMF still weak; risk penalty elevated; distribution risk flag
- **BID** (Reject, score 32.2, MF 41, risk 67, sector `Ngân hàng`) — `fund_commentary_mention`
  - **Why:** Fund-linked, but grouped money flow not confirming
  - **Also:** bucket=fund_commentary_mention; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; High risk penalty (67)
  - **Note:** Size as research only until risk penalty improves.
  - **Failed because:** weekly CMF still weak; risk penalty elevated; distribution risk flag

### 4. Elevated risk / distortion / distribution (Tier 1–3; matches caution-proxy %)

- **CTR** (Tier 3, score 38.5, MF 59, risk 67, sector `Xây dựng, xây lắp`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** CMF block strong; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; High risk penalty (67)
  - **Note:** Size as research only until risk penalty improves.
- **GAS** (Tier 3, score 41.4, MF 54, risk 55, sector `Phân phối khí đốt`) — `fund_commentary_mention`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** bucket=fund_commentary_mention; OBV/PVT supportive; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (55)
  - **Note:** Size as research only until risk penalty improves.
- **ACB** (Tier 3, score 39.9, MF 54, risk 55, sector `Ngân hàng`) — `fund_commentary_mention`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** bucket=fund_commentary_mention; CMF block strong; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (55)
  - **Note:** Size as research only until risk penalty improves.
- **DHA** (Tier 3, score 38.7, MF 48, risk 52, sector `Xây dựng, xây lắp`) — `outside_fund_disclosure`
  - **Why:** Scan tier driven by mixed flow/context/risk profile
  - **Also:** context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; High risk penalty (52)
  - **Note:** Size as research only until risk penalty improves.
- **HCM** (Tier 3, score 38.2, MF 49, risk 52, sector `Công ty chứng khoán`) — `outside_fund_disclosure`
  - **Why:** Scan tier driven by mixed flow/context/risk profile
  - **Also:** CMF block strong; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; High risk penalty (52)
  - **Note:** Size as research only until risk penalty improves.
- **IDJ** (Tier 3, score 42.0, MF 46, risk 45, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Scan tier driven by mixed flow/context/risk profile
  - **Also:** context score elevated; weekly CMF still weak
  - **Risk:** Moderate risk penalty (45)
  - **Note:** Size as research only until risk penalty improves.
- **DXS** (Tier 2, score 46.2, MF 50, risk 25, sector `Các công ty đầu cơ và phát triển bất động sản`) — `outside_fund_disclosure`
  - **Why:** Emerging (no fund tag); flow/risk pass emerging gate
  - **Also:** context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **KDC** (Tier 2, score 47.2, MF 62, risk 25, sector `Sản phẩm thực phẩm`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated
  - **Risk:** Distribution-day count elevated
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.

## C. Bucket mix

**Denominator:** All Tier 1–3 names in scan (n=50)

| Bucket | Count | % | Definition |
| --- | ---: | ---: | --- |
| fund_backed | 4 | 8.0% | has_fund_disclosure_tag among Tier 1–3 |
| emerging | 24 | 48.0% | emerging_accumulation_candidate among Tier 1–3 |
| vin_distortion_flagged | 0 | 0.0% | vingroup_distortion_flag=True among Tier 1–3 (scan boolean) |
| caution_proxy | 13 | 26.0% | vin_flag OR distribution_risk_flag OR score_risk_penalty>=45 (matches section 4 list) |
| outside_fund_disclosure | 46 | 92.0% | fund_context_bucket=outside_fund_disclosure among Tier 1–3 |

**Unknown sector in displayed look-first lists:** 5/26 (19.2%)
_(16 names enriched from `data/master/sector_map.csv` for display only.)_

## D. Changes since previous scan

_Previous scan date: 2026-05-27_

- **New Tier 1–2:** KDC, MIG, OGC, POM
- **Dropped Tier 1–2:** APS, PET, QNS, SSB
- **Tier change:** APS Tier 2 → Tier 3, Δ-1.2
- **Tier change:** BSR Tier 3 → Reject, Δ-5.7
- **Tier change:** BVB Tier 3 → Reject, Δ-2.3
- **Tier change:** CTR Reject → Tier 3, Δ+1.4
- **Tier change:** DHA Reject → Tier 3, Δ+3.4
- **Tier change:** FCN Tier 3 → Reject, Δ-3.9
- **Tier change:** HCM Reject → Tier 3, Δ+3.6
- **Tier change:** KDC Tier 3 → Tier 2, Δ+6.0
- **Tier change:** MBS Reject → Tier 3, Δ+0.2
- **Tier change:** MIG Tier 3 → Tier 2, Δ+12.5
- **Tier change:** MZG Reject → Tier 3, Δ+0.9
- **Tier change:** OGC Reject → Tier 2, Δ+11.1
- **Score up:** LEC Δ+19.0 → Reject
- **Score up:** FUEIP100 Δ+14.5 → Reject
- **Score up:** MIG Δ+12.5 → Tier 2
- **Score up:** MBT Δ+11.3 → Reject
- **Score up:** OGC Δ+11.1 → Tier 2
- **Score down:** SSB Δ-13.4 → Tier 3
- **Score down:** PHC Δ-11.9 → Reject
- **Score down:** FIC Δ-11.0 → Reject
- **Score down:** UNI Δ-10.7 → Reject
- **Score down:** DXG Δ-10.1 → Reject

## E. Workflow warnings (priority order)

- [P1 Structural] Top tier is 92% outside_fund_disclosure (46/50) — cross-check emerging vs April fund priors.
- [P2 Data] Unknown sector in displayed look-first lists: 5/26 — interpret sector/theme bullets cautiously.
- [P3 Market] No Tier 1 names — narrow/fragile regime; prioritize Tier 2 focus + near-miss.
- [P4 Caution] Emerging universe has several elevated risk_penalty names — vet before prioritizing.
- [P4 Caution] caution-proxy (section 4 rule): 13/50 Tier 1–3 names (26%) — includes high risk_penalty, not only vin_distortion_flag.

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