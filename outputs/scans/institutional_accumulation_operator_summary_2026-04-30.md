# Institutional Accumulation — Operator Summary

**Scan date:** 2026-04-30  
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
| Tier 3 | 34 |
| Reject | 1515 |
| Emerging (universe) | 24 |
| Top-tier fund-backed | 5 |
| Unknown sector (Tier 1–3) | 8/47 |

## B. What to look at first

### 1. Top fund-backed candidates (Tier 1–3)

- **MWG** (Tier 3, score 45.0, MF 49, risk 0, sector `Bán lẻ tổng hợp`) — `consensus_core`
  - **Why:** Scan tier driven by mixed flow/context/risk profile
  - **Also:** bucket=consensus_core; CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Tier 3 — use full scan row for CMF/OBV detail.
- **VCB** (Tier 3, score 44.5, MF 57, risk 0, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Grouped money flow supportive
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Tier 3 — use full scan row for CMF/OBV detail.
- **VHM** (Tier 3, score 42.5, MF 66, risk 57, sector `Các công ty đầu cơ và phát triển bất động sản`) — `consensus_second_ring`
  - **Why:** VIN distortion: strong RS without robust multi-horizon flow
  - **Also:** bucket=consensus_second_ring; CMF block strong; context score thin
  - **Risk:** Vingroup distortion flag active; High risk penalty (57)
  - **Note:** Do not treat as clean accumulation until multi-horizon flow confirms.
- **HPG** (Tier 3, score 42.1, MF 45, risk 0, sector `Khai thác quặng sắt và sản xuất thép`) — `consensus_core`
  - **Why:** Tier held up mainly by context, not flow confirmation; weekly CMF still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Investigate whether context is masking weak CMF/participation.
- **TCB** (Tier 3, score 40.1, MF 55, risk 27, sector `Ngân hàng`) — `consensus_second_ring`
  - **Why:** Grouped money flow supportive
  - **Also:** bucket=consensus_second_ring; context score elevated; daily/weekly CMF conflict
  - **Risk:** No major structural risk flag
  - **Note:** Tier 3 — use full scan row for CMF/OBV detail.

### 2. Top emerging candidates (no fund tag)

- **TOS** (Tier 2, score 57.4, MF 72, risk 0, sector `Dịch vụ vận tải`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **DVM** (Tier 2, score 53.8, MF 76, risk 0, sector `Dược phẩm`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; OBV/PVT supportive; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **NRC** (Tier 2, score 53.5, MF 72, risk 0, sector `Các công ty đầu cơ và phát triển bất động sản`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **HNG** (Tier 2, score 52.2, MF 70, risk 27, sector `Sản phẩm thực phẩm`) — `outside_fund_disclosure`
  - **Why:** Emerging (no fund tag); flow/risk pass emerging gate
  - **Also:** CMF block strong; context score elevated; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **BFC** (Tier 2, score 51.4, MF 56, risk 15, sector `Hóa chất cơ bản - Sản phẩm nhựa, cao su, hóa chất`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **DSH** (Tier 2, score 50.8, MF 66, risk 12, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** OBV/PVT supportive; context score elevated; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **SJS** (Tier 2, score 50.8, MF 71, risk 25, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated
  - **Risk:** Distribution-day count elevated
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **VJC** (Tier 2, score 50.2, MF 56, risk 0, sector `Hàng không chở khách`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.

### 3. Important rejects (fund-linked, flow failed)

- **CTG** (Reject, score 32.5, MF 25, risk 0, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak
- **GMD** (Reject, score 30.1, MF 31, risk 52, sector `Dịch vụ vận tải`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; daily/weekly CMF conflict
  - **Risk:** Distribution-day count elevated; High risk penalty (52)
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; daily/weekly CMF conflict; risk penalty elevated; distribution risk flag
- **MBB** (Reject, score 26.9, MF 24, risk 40, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; risk penalty elevated; distribution risk flag
- **STB** (Reject, score 36.4, MF 32, risk 0, sector `Ngân hàng`) — `consensus_second_ring`
  - **Why:** Fund-linked, but grouped money flow not confirming
  - **Also:** bucket=consensus_second_ring; context score elevated; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Reject — use full scan row for CMF/OBV detail.
  - **Failed because:** weak grouped money flow; weekly CMF still weak
- **GVR** (Reject, score 31.8, MF 35, risk 27, sector `Hóa chất cơ bản - Sản phẩm nhựa, cao su, hóa chất`) — `selective_fund_bet`
  - **Why:** Fund-linked, but grouped money flow not confirming
  - **Also:** bucket=selective_fund_bet; context score elevated; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Reject — use full scan row for CMF/OBV detail.
  - **Failed because:** weak grouped money flow; weekly CMF still weak
- **MSN** (Reject, score 30.6, MF 37, risk 25, sector `Sản phẩm thực phẩm`) — `fund_commentary_mention`
  - **Why:** Fund-linked, but grouped money flow not confirming
  - **Also:** bucket=fund_commentary_mention; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated
  - **Note:** Reject — use full scan row for CMF/OBV detail.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; distribution risk flag
- **SSI** (Reject, score 28.3, MF 23, risk 0, sector `Công ty chứng khoán`) — `fund_commentary_mention`
  - **Why:** Fund-linked, but grouped money flow not confirming
  - **Also:** bucket=fund_commentary_mention; context score elevated; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Reject — use full scan row for CMF/OBV detail.
  - **Failed because:** weak grouped money flow; weekly CMF still weak
- **KDH** (Reject, score 24.4, MF 19, risk 0, sector `Các công ty đầu cơ và phát triển bất động sản`) — `selective_fund_bet`
  - **Why:** Fund-linked, but grouped money flow not confirming
  - **Also:** bucket=selective_fund_bet; context score elevated; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Reject — use full scan row for CMF/OBV detail.
  - **Failed because:** weak grouped money flow; weekly CMF still weak

### 4. Elevated risk / distortion / distribution (Tier 1–3; matches caution-proxy %)

- **PVP** (Tier 3, score 45.4, MF 72, risk 87, sector `Dịch vụ vận tải`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** CMF block strong; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; High risk penalty (87)
  - **Note:** Size as research only until risk penalty improves.
- **VIC** (Tier 3, score 39.6, MF 63, risk 69, sector `Các công ty đầu cơ và phát triển bất động sản`) — `outside_fund_disclosure`
  - **Why:** VIN distortion: strong RS without robust multi-horizon flow
  - **Also:** weekly CMF still weak
  - **Risk:** Vingroup distortion flag active; High risk penalty (69)
  - **Note:** Do not treat as clean accumulation until multi-horizon flow confirms.
- **F88** (Tier 3, score 44.1, MF 74, risk 67, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** CMF block strong; OBV/PVT supportive; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (67)
  - **Note:** Size as research only until risk penalty improves.
- **VBB** (Tier 3, score 40.5, MF 56, risk 65, sector `Ngân hàng`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** OBV/PVT supportive; context score elevated; daily/weekly CMF conflict
  - **Risk:** High risk penalty (65)
  - **Note:** Size as research only until risk penalty improves.
- **VHM** (Tier 3, score 42.5, MF 66, risk 57, sector `Các công ty đầu cơ và phát triển bất động sản`) — `consensus_second_ring`
  - **Why:** VIN distortion: strong RS without robust multi-horizon flow
  - **Also:** bucket=consensus_second_ring; CMF block strong; context score thin
  - **Risk:** Vingroup distortion flag active; High risk penalty (57)
  - **Note:** Do not treat as clean accumulation until multi-horizon flow confirms.
- **NVL** (Tier 3, score 51.8, MF 74, risk 50, sector `Các công ty đầu cơ và phát triển bất động sản`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** CMF block strong; OBV/PVT supportive; context score elevated
  - **Risk:** High risk penalty (50)
  - **Note:** Size as research only until risk penalty improves.
- **TCO** (Tier 3, score 38.8, MF 55, risk 50, sector `Dịch vụ vận tải`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** CMF block strong; context score elevated
  - **Risk:** High risk penalty (50)
  - **Note:** Size as research only until risk penalty improves.
- **HTN** (Tier 3, score 45.5, MF 63, risk 47, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** CMF block strong; OBV/PVT supportive; context score elevated
  - **Risk:** Moderate risk penalty (47)
  - **Note:** Size as research only until risk penalty improves.

## C. Bucket mix

**Denominator:** All Tier 1–3 names in scan (n=47)

| Bucket | Count | % | Definition |
| --- | ---: | ---: | --- |
| fund_backed | 5 | 10.6% | has_fund_disclosure_tag among Tier 1–3 |
| emerging | 24 | 51.1% | emerging_accumulation_candidate among Tier 1–3 |
| vin_distortion_flagged | 2 | 4.3% | vingroup_distortion_flag=True among Tier 1–3 (scan boolean) |
| caution_proxy | 13 | 27.7% | vin_flag OR distribution_risk_flag OR score_risk_penalty>=45 (matches section 4 list) |
| outside_fund_disclosure | 42 | 89.4% | fund_context_bucket=outside_fund_disclosure among Tier 1–3 |

_VIN watch (VIC/VHM/VRE/VPL) in **caution-proxy** list: 2 — may appear in section 4 without `vin_distortion_flagged` % moving._

**Unknown sector in displayed look-first lists:** 4/28 (14.3%)
_(16 names enriched from `data/master/sector_map.csv` for display only.)_

## D. Changes since previous scan

_Previous scan date: 2026-05-21_

- **New Tier 1–2:** BFC, DVM, HNG, KSF, NRC, PCH, SJS, TNT, VJC
- **Dropped Tier 1–2:** BSR, CDC, CTR, DL1, DRI, HHP, HII, L40, NDN, PHR, QNS, TCI, TCO, TVN
- **Tier change:** AAV Reject → Tier 3, Δ+16.8
- **Tier change:** APS Tier 3 → Reject, Δ-30.8
- **Tier change:** BAF Reject → Tier 3, Δ+19.3
- **Tier change:** BFC Reject → Tier 2, Δ+23.0
- **Tier change:** BIC Reject → Tier 3, Δ+27.5
- **Tier change:** BID Tier 3 → Reject, Δ-17.0
- **Tier change:** BIG Reject → Tier 3, Δ+23.4
- **Tier change:** BMP Reject → Tier 3, Δ+7.2
- **Tier change:** BSR Tier 2 → Reject, Δ-35.5
- **Tier change:** C69 Tier 3 → Reject, Δ-8.0
- **Tier change:** CDC Tier 2 → Tier 3, Δ-9.9
- **Tier change:** CRC Reject → Tier 3, Δ+17.4
- **Score up:** BIC Δ+27.5 → Tier 3
- **Score up:** NRC Δ+27.1 → Tier 2
- **Score up:** AG1 Δ+24.7 → Reject
- **Score up:** BIG Δ+23.4 → Tier 3
- **Score up:** BFC Δ+23.0 → Tier 2
- **Score down:** BSR Δ-35.5 → Reject
- **Score down:** APS Δ-30.8 → Reject
- **Score down:** QNS Δ-28.6 → Reject
- **Score down:** PHR Δ-27.8 → Reject
- **Score down:** SBB Δ-26.5 → Reject

## E. Workflow warnings (priority order)

- [P1 Structural] Top tier is 89% outside_fund_disclosure (42/47) — cross-check emerging vs April fund priors.
- [P2 Data] Unknown sector in displayed look-first lists: 4/28 — interpret sector/theme bullets cautiously.
- [P3 Market] No Tier 1 names — narrow/fragile regime; prioritize Tier 2 focus + near-miss.
- [P4 Caution] 2 names with vingroup_distortion_flag in Tier 1–3 — cap-weight narrative risk.

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