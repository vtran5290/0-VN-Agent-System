# Institutional Accumulation — Operator Summary

**Scan date:** 2026-06-05  
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
| Tier 2 | 21 |
| Tier 3 | 29 |
| Reject | 1512 |
| Emerging (universe) | 22 |
| Top-tier fund-backed | 5 |
| Unknown sector (Tier 1–3) | 11/50 |

## B. What to look at first

### 1. Top fund-backed candidates (Tier 1–3)

- **ACB** (Tier 3, score 52.6, MF 75, risk 55, sector `Ngân hàng`) — `fund_commentary_mention`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** bucket=fund_commentary_mention; CMF block strong; OBV/PVT supportive
  - **Risk:** Distribution-day count elevated; High risk penalty (55)
  - **Note:** Size as research only until risk penalty improves.
- **VCB** (Tier 3, score 45.8, MF 56, risk 52, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** bucket=consensus_core; OBV/PVT supportive; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (52)
  - **Note:** Size as research only until risk penalty improves.
- **FPT** (Tier 3, score 41.4, MF 50, risk 40, sector `Công nghệ phần mềm`) — `fund_commentary_mention`
  - **Why:** Scan tier driven by mixed flow/context/risk profile
  - **Also:** bucket=fund_commentary_mention; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Tier 3 — use full scan row for CMF/OBV detail.
- **BVH** (Tier 3, score 41.1, MF 45, risk 55, sector `Bảo hiểm nhân thọ`) — `selective_fund_bet`
  - **Why:** Tier held up mainly by context, not flow confirmation
  - **Also:** bucket=selective_fund_bet; CMF block strong; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (55)
  - **Note:** Investigate whether context is masking weak CMF/participation.
- **GAS** (Tier 3, score 38.0, MF 39, risk 52, sector `Phân phối khí đốt`) — `fund_commentary_mention`
  - **Why:** Tier held up mainly by context, not flow confirmation; weekly CMF still weak
  - **Also:** bucket=fund_commentary_mention; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; High risk penalty (52)
  - **Note:** Investigate whether context is masking weak CMF/participation.

### 2. Top emerging candidates (no fund tag)

- **MSB** (Tier 2, score 59.9, MF 73, risk 0, sector `Ngân hàng`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; OBV/PVT supportive; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **TCI** (Tier 2, score 56.5, MF 60, risk 0, sector `Công ty chứng khoán`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **KSF** (Tier 2, score 55.5, MF 81, risk 24, sector `Các công ty đầu cơ và phát triển bất động sản`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** OBV/PVT supportive; context score elevated; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **KDC** (Tier 2, score 55.0, MF 67, risk 0, sector `Sản phẩm thực phẩm`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; OBV/PVT supportive; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **OCB** (Tier 2, score 53.6, MF 74, risk 30, sector `Ngân hàng`) — `outside_fund_disclosure`
  - **Why:** Emerging (no fund tag); flow/risk pass emerging gate
  - **Also:** CMF block strong; context score elevated; weekly CMF still weak
  - **Risk:** Moderate risk penalty (30)
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **KOS** (Tier 2, score 50.3, MF 63, risk 15, sector `Các công ty đầu cơ và phát triển bất động sản`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **VPL** (Tier 2, score 49.9, MF 66, risk 0, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; OBV/PVT supportive
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **HQC** (Tier 2, score 49.3, MF 54, risk 0, sector `Các công ty đầu cơ và phát triển bất động sản`) — `outside_fund_disclosure`
  - **Why:** Emerging (no fund tag); flow/risk pass emerging gate
  - **Also:** context score elevated; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.

### 3. Important rejects (fund-linked, flow failed)

- **GMD** (Reject, score 37.1, MF 32, risk 27, sector `Dịch vụ vận tải`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; daily/weekly CMF conflict
  - **Risk:** No major structural risk flag
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; daily/weekly CMF conflict
- **MBB** (Reject, score 28.7, MF 20, risk 40, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; risk penalty elevated; distribution risk flag
- **CTG** (Reject, score 26.8, MF 16, risk 15, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak
- **MWG** (Reject, score 24.6, MF 25, risk 40, sector `Bán lẻ tổng hợp`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; risk penalty elevated; distribution risk flag
- **HPG** (Reject, score 23.4, MF 17, risk 40, sector `Khai thác quặng sắt và sản xuất thép`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; risk penalty elevated; distribution risk flag
- **GVR** (Reject, score 33.3, MF 32, risk 25, sector `Hóa chất cơ bản - Sản phẩm nhựa, cao su, hóa chất`) — `selective_fund_bet`
  - **Why:** Fund-linked, but grouped money flow not confirming
  - **Also:** bucket=selective_fund_bet; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated
  - **Note:** Reject — use full scan row for CMF/OBV detail.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; distribution risk flag
- **POW** (Reject, score 30.8, MF 26, risk 15, sector `Sản xuất và cung cấp điện truyền thống`) — `fund_commentary_mention`
  - **Why:** Fund-linked, but grouped money flow not confirming
  - **Also:** bucket=fund_commentary_mention; context score elevated; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Reject — use full scan row for CMF/OBV detail.
  - **Failed because:** weak grouped money flow; weekly CMF still weak
- **STB** (Reject, score 30.1, MF 31, risk 40, sector `Ngân hàng`) — `consensus_second_ring`
  - **Why:** Fund-linked, but grouped money flow not confirming
  - **Also:** bucket=consensus_second_ring; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Reject — use full scan row for CMF/OBV detail.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; risk penalty elevated; distribution risk flag

### 4. Elevated risk / distortion / distribution (Tier 1–3; matches caution-proxy %)

- **THD** (Tier 3, score 52.6, MF 79, risk 68, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** CMF block strong; OBV/PVT supportive; context score elevated
  - **Risk:** High risk penalty (68)
  - **Note:** Size as research only until risk penalty improves.
- **ACB** (Tier 3, score 52.6, MF 75, risk 55, sector `Ngân hàng`) — `fund_commentary_mention`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** bucket=fund_commentary_mention; CMF block strong; OBV/PVT supportive
  - **Risk:** Distribution-day count elevated; High risk penalty (55)
  - **Note:** Size as research only until risk penalty improves.
- **BVH** (Tier 3, score 41.1, MF 45, risk 55, sector `Bảo hiểm nhân thọ`) — `selective_fund_bet`
  - **Why:** Tier held up mainly by context, not flow confirmation
  - **Also:** bucket=selective_fund_bet; CMF block strong; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (55)
  - **Note:** Investigate whether context is masking weak CMF/participation.
- **BIC** (Tier 3, score 39.3, MF 55, risk 55, sector `Bảo hiểm tổng hợp`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** CMF block strong; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; High risk penalty (55)
  - **Note:** Size as research only until risk penalty improves.
- **GAS** (Tier 3, score 38.0, MF 39, risk 52, sector `Phân phối khí đốt`) — `fund_commentary_mention`
  - **Why:** Tier held up mainly by context, not flow confirmation; weekly CMF still weak
  - **Also:** bucket=fund_commentary_mention; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; High risk penalty (52)
  - **Note:** Investigate whether context is masking weak CMF/participation.
- **VAB** (Tier 3, score 42.2, MF 61, risk 52, sector `Ngân hàng`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** CMF block strong; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; High risk penalty (52)
  - **Note:** Size as research only until risk penalty improves.
- **VCB** (Tier 3, score 45.8, MF 56, risk 52, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** bucket=consensus_core; OBV/PVT supportive; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (52)
  - **Note:** Size as research only until risk penalty improves.
- **VNE** (Tier 3, score 40.1, MF 71, risk 40, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Grouped money flow supportive
  - **Also:** OBV/PVT supportive; context score elevated; daily CMF missing
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Tier 3 — use full scan row for CMF/OBV detail.

## C. Bucket mix

**Denominator:** All Tier 1–3 names in scan (n=50)

| Bucket | Count | % | Definition |
| --- | ---: | ---: | --- |
| fund_backed | 5 | 10.0% | has_fund_disclosure_tag among Tier 1–3 |
| emerging | 22 | 44.0% | emerging_accumulation_candidate among Tier 1–3 |
| vin_distortion_flagged | 0 | 0.0% | vingroup_distortion_flag=True among Tier 1–3 (scan boolean) |
| caution_proxy | 15 | 30.0% | vin_flag OR distribution_risk_flag OR score_risk_penalty>=45 (matches section 4 list) |
| outside_fund_disclosure | 45 | 90.0% | fund_context_bucket=outside_fund_disclosure among Tier 1–3 |

**Unknown sector in displayed look-first lists:** 3/25 (12.0%)
_(16 names enriched from `data/master/sector_map.csv` for display only.)_

## D. Changes since previous scan

_Previous scan date: 2026-06-02_

- **New Tier 1–2:** F88, HNM, HQC, KOS, MST, OCB, TCI, VND, VVS
- **Dropped Tier 1–2:** VPI
- **Tier change:** ABB Reject → Tier 3, Δ+11.4
- **Tier change:** APS Tier 3 → Reject, Δ-9.2
- **Tier change:** BIC Reject → Tier 3, Δ+8.4
- **Tier change:** BVB Reject → Tier 3, Δ+12.9
- **Tier change:** BVH Reject → Tier 3, Δ+6.9
- **Tier change:** CDC Tier 3 → Reject, Δ-8.7
- **Tier change:** CMG Reject → Tier 3, Δ+11.5
- **Tier change:** DBD Reject → Tier 3, Δ+4.0
- **Tier change:** F88 Reject → Tier 2, Δ+13.4
- **Tier change:** FOX Reject → Tier 3, Δ+7.3
- **Tier change:** FPT Reject → Tier 3, Δ+15.0
- **Tier change:** HBC Tier 3 → Reject, Δ-5.3
- **Score up:** HQC Δ+29.1 → Tier 2
- **Score up:** DAH Δ+22.5 → Reject
- **Score up:** SVN Δ+20.7 → Reject
- **Score up:** XHC Δ+20.0 → Reject
- **Score up:** MCG Δ+19.1 → Reject
- **Score down:** SMA Δ-23.0 → Reject
- **Score down:** CTX Δ-15.8 → Reject
- **Score down:** TCB Δ-15.5 → Reject
- **Score down:** LPB Δ-15.4 → Reject
- **Score down:** DQC Δ-14.5 → Reject

## E. Workflow warnings (priority order)

- [P1 Structural] Top tier is 90% outside_fund_disclosure (45/50) — cross-check emerging vs April fund priors.
- [P2 Data] Unknown sector in displayed look-first lists: 3/25 — interpret sector/theme bullets cautiously.
- [P3 Market] No Tier 1 names — narrow/fragile regime; prioritize Tier 2 focus + near-miss.
- [P4 Caution] Emerging universe has several elevated risk_penalty names — vet before prioritizing.
- [P4 Caution] caution-proxy (section 4 rule): 15/50 Tier 1–3 names (30%) — includes high risk_penalty, not only vin_distortion_flag.

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