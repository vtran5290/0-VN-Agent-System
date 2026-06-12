# Institutional Accumulation — Operator Summary

**Scan date:** 2026-06-12  
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
| Tier 2 | 22 |
| Tier 3 | 41 |
| Reject | 1499 |
| Emerging (universe) | 25 |
| Top-tier fund-backed | 4 |
| Unknown sector (Tier 1–3) | 14/63 |

## B. What to look at first

### 1. Top fund-backed candidates (Tier 1–3)

- **ACB** (Tier 2, score 56.6, MF 81, risk 30, sector `Ngân hàng`) — `fund_commentary_mention`
  - **Why:** Grouped money flow supportive
  - **Also:** bucket=fund_commentary_mention; CMF block strong; OBV/PVT supportive
  - **Risk:** Moderate risk penalty (30)
  - **Note:** Tier 2 — use full scan row for CMF/OBV detail.
- **VCB** (Tier 3, score 41.9, MF 44, risk 52, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Tier held up mainly by context, not flow confirmation; weekly CMF still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; High risk penalty (52)
  - **Note:** Investigate whether context is masking weak CMF/participation.
- **FPT** (Tier 3, score 39.1, MF 39, risk 15, sector `Công nghệ phần mềm`) — `fund_commentary_mention`
  - **Why:** Tier held up mainly by context, not flow confirmation; weekly CMF still weak
  - **Also:** bucket=fund_commentary_mention; context score elevated; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Investigate whether context is masking weak CMF/participation.
- **BVH** (Tier 3, score 39.0, MF 46, risk 40, sector `Bảo hiểm nhân thọ`) — `selective_fund_bet`
  - **Why:** Tier held up mainly by context, not flow confirmation; weekly CMF still weak
  - **Also:** bucket=selective_fund_bet; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Investigate whether context is masking weak CMF/participation.

### 2. Top emerging candidates (no fund tag)

- **MSB** (Tier 2, score 55.9, MF 69, risk 0, sector `Ngân hàng`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **HHP** (Tier 2, score 55.1, MF 60, risk 0, sector `Giấy`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **ABB** (Tier 2, score 54.4, MF 60, risk 0, sector `Ngân hàng`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **SBG** (Tier 2, score 54.0, MF 68, risk 18, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **HNM** (Tier 2, score 53.9, MF 62, risk 0, sector `Sản phẩm thực phẩm`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **BVB** (Tier 2, score 52.9, MF 62, risk 12, sector `Ngân hàng`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** context score elevated; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **AMS** (Tier 2, score 52.7, MF 71, risk 15, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **TVN** (Tier 2, score 51.2, MF 63, risk 25, sector `Khai thác quặng sắt và sản xuất thép`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; OBV/PVT supportive; context score elevated
  - **Risk:** Distribution-day count elevated
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.

### 3. Important rejects (fund-linked, flow failed)

- **GMD** (Reject, score 32.6, MF 32, risk 52, sector `Dịch vụ vận tải`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; daily/weekly CMF conflict
  - **Risk:** Distribution-day count elevated; High risk penalty (52)
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; daily/weekly CMF conflict; risk penalty elevated; distribution risk flag
- **MWG** (Reject, score 28.9, MF 25, risk 40, sector `Bán lẻ tổng hợp`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; risk penalty elevated; distribution risk flag
- **MBB** (Reject, score 28.8, MF 24, risk 40, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; risk penalty elevated; distribution risk flag
- **CTG** (Reject, score 23.0, MF 15, risk 40, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; risk penalty elevated; distribution risk flag
- **HPG** (Reject, score 22.8, MF 15, risk 40, sector `Khai thác quặng sắt và sản xuất thép`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; risk penalty elevated; distribution risk flag
- **STB** (Reject, score 33.8, MF 29, risk 40, sector `Ngân hàng`) — `consensus_second_ring`
  - **Why:** Fund-linked, but grouped money flow not confirming
  - **Also:** bucket=consensus_second_ring; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Reject — use full scan row for CMF/OBV detail.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; risk penalty elevated; distribution risk flag
- **GAS** (Reject, score 31.2, MF 26, risk 25, sector `Phân phối khí đốt`) — `fund_commentary_mention`
  - **Why:** Fund-linked, but grouped money flow not confirming
  - **Also:** bucket=fund_commentary_mention; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated
  - **Note:** Reject — use full scan row for CMF/OBV detail.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; distribution risk flag
- **POW** (Reject, score 30.9, MF 23, risk 25, sector `Sản xuất và cung cấp điện truyền thống`) — `fund_commentary_mention`
  - **Why:** Fund-linked, but grouped money flow not confirming
  - **Also:** bucket=fund_commentary_mention; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated
  - **Note:** Reject — use full scan row for CMF/OBV detail.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; distribution risk flag

### 4. Elevated risk / distortion / distribution (Tier 1–3; matches caution-proxy %)

- **THD** (Tier 3, score 52.6, MF 78, risk 68, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** CMF block strong; OBV/PVT supportive; context score elevated
  - **Risk:** High risk penalty (68)
  - **Note:** Size as research only until risk penalty improves.
- **BAF** (Tier 3, score 39.0, MF 53, risk 62, sector `Sản phẩm thực phẩm`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** CMF block strong; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (62)
  - **Note:** Size as research only until risk penalty improves.
- **VAB** (Tier 3, score 39.5, MF 56, risk 58, sector `Ngân hàng`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; High risk penalty (58)
  - **Note:** Size as research only until risk penalty improves.
- **BIC** (Tier 3, score 38.6, MF 53, risk 55, sector `Bảo hiểm tổng hợp`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** CMF block strong; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; High risk penalty (55)
  - **Note:** Size as research only until risk penalty improves.
- **VCB** (Tier 3, score 41.9, MF 44, risk 52, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Tier held up mainly by context, not flow confirmation; weekly CMF still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; High risk penalty (52)
  - **Note:** Investigate whether context is masking weak CMF/participation.
- **PC1** (Tier 3, score 38.2, MF 48, risk 52, sector `Xây dựng, xây lắp`) — `outside_fund_disclosure`
  - **Why:** Scan tier driven by mixed flow/context/risk profile
  - **Also:** CMF block strong; OBV/PVT supportive; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (52)
  - **Note:** Size as research only until risk penalty improves.
- **AGG** (Tier 3, score 47.7, MF 64, risk 47, sector `Các công ty đầu cơ và phát triển bất động sản`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** CMF block strong; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (47)
  - **Note:** Size as research only until risk penalty improves.
- **NVB** (Tier 3, score 44.6, MF 55, risk 45, sector `Ngân hàng`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** context score elevated; weekly CMF still weak
  - **Risk:** Moderate risk penalty (45)
  - **Note:** Size as research only until risk penalty improves.

## C. Bucket mix

**Denominator:** All Tier 1–3 names in scan (n=63)

| Bucket | Count | % | Definition |
| --- | ---: | ---: | --- |
| fund_backed | 4 | 6.3% | has_fund_disclosure_tag among Tier 1–3 |
| emerging | 25 | 39.7% | emerging_accumulation_candidate among Tier 1–3 |
| vin_distortion_flagged | 0 | 0.0% | vingroup_distortion_flag=True among Tier 1–3 (scan boolean) |
| caution_proxy | 21 | 33.3% | vin_flag OR distribution_risk_flag OR score_risk_penalty>=45 (matches section 4 list) |
| outside_fund_disclosure | 59 | 93.7% | fund_context_bucket=outside_fund_disclosure among Tier 1–3 |

**Unknown sector in displayed look-first lists:** 3/27 (11.1%)
_(16 names enriched from `data/master/sector_map.csv` for display only.)_

## D. Changes since previous scan

_Previous scan date: 2026-06-10_

- **New Tier 1–2:** BVB, HSL, SBG, TVN, UNI
- **Dropped Tier 1–2:** KOS, NVB, PSI, VND, VPL
- **Tier change:** AAA Reject → Tier 3, Δ+13.7
- **Tier change:** AGG Reject → Tier 3, Δ+16.9
- **Tier change:** BAF Reject → Tier 3, Δ+8.1
- **Tier change:** BIC Reject → Tier 3, Δ+2.4
- **Tier change:** BMI Reject → Tier 3, Δ+4.8
- **Tier change:** BVB Reject → Tier 2, Δ+15.0
- **Tier change:** BVH Reject → Tier 3, Δ+3.2
- **Tier change:** CMG Tier 3 → Reject, Δ-1.2
- **Tier change:** CRE Reject → Tier 3, Δ+3.2
- **Tier change:** CTF Tier 3 → Reject, Δ-2.5
- **Tier change:** CTR Tier 3 → Reject, Δ-4.8
- **Tier change:** FPT Reject → Tier 3, Δ+3.3
- **Score up:** AGG Δ+16.9 → Tier 3
- **Score up:** BBT Δ+16.7 → Reject
- **Score up:** LDG Δ+16.6 → Reject
- **Score up:** BVB Δ+15.0 → Tier 2
- **Score up:** PIS Δ+14.9 → Reject
- **Score down:** CMN Δ-15.3 → Reject
- **Score down:** MEL Δ-14.2 → Reject
- **Score down:** LCM Δ-12.4 → Reject
- **Score down:** HMH Δ-11.5 → Reject
- **Score down:** BSQ Δ-11.3 → Reject

## E. Workflow warnings (priority order)

- [P1 Structural] Top tier is 94% outside_fund_disclosure (59/63) — cross-check emerging vs April fund priors.
- [P2 Data] Unknown sector in displayed look-first lists: 3/27 — interpret sector/theme bullets cautiously.
- [P3 Market] No Tier 1 names — narrow/fragile regime; prioritize Tier 2 focus + near-miss.
- [P4 Caution] Emerging universe has several elevated risk_penalty names — vet before prioritizing.
- [P4 Caution] caution-proxy (section 4 rule): 21/63 Tier 1–3 names (33%) — includes high risk_penalty, not only vin_distortion_flag.

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