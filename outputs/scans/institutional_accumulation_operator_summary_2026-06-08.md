# Institutional Accumulation — Operator Summary

**Scan date:** 2026-06-08  
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
| Emerging (universe) | 18 |
| Top-tier fund-backed | 4 |
| Unknown sector (Tier 1–3) | 8/47 |

## B. What to look at first

### 1. Top fund-backed candidates (Tier 1–3)

- **ACB** (Tier 3, score 50.7, MF 76, risk 55, sector `Ngân hàng`) — `fund_commentary_mention`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** bucket=fund_commentary_mention; CMF block strong; OBV/PVT supportive
  - **Risk:** Distribution-day count elevated; High risk penalty (55)
  - **Note:** Size as research only until risk penalty improves.
- **VCB** (Tier 3, score 44.2, MF 51, risk 52, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** bucket=consensus_core; OBV/PVT supportive; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (52)
  - **Note:** Size as research only until risk penalty improves.
- **FPT** (Tier 3, score 39.0, MF 48, risk 40, sector `Công nghệ phần mềm`) — `fund_commentary_mention`
  - **Why:** Tier held up mainly by context, not flow confirmation; weekly CMF still weak
  - **Also:** bucket=fund_commentary_mention; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Investigate whether context is masking weak CMF/participation.
- **GAS** (Tier 3, score 38.1, MF 36, risk 52, sector `Phân phối khí đốt`) — `fund_commentary_mention`
  - **Why:** Tier held up mainly by context, not flow confirmation; weekly CMF still weak
  - **Also:** bucket=fund_commentary_mention; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; High risk penalty (52)
  - **Note:** Investigate whether context is masking weak CMF/participation.

### 2. Top emerging candidates (no fund tag)

- **MSB** (Tier 2, score 60.2, MF 74, risk 0, sector `Ngân hàng`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; OBV/PVT supportive; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **TCI** (Tier 2, score 58.2, MF 64, risk 0, sector `Công ty chứng khoán`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **KDC** (Tier 2, score 53.9, MF 66, risk 0, sector `Sản phẩm thực phẩm`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; OBV/PVT supportive; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **KSF** (Tier 2, score 53.5, MF 81, risk 24, sector `Các công ty đầu cơ và phát triển bất động sản`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** OBV/PVT supportive; context score elevated; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **KOS** (Tier 2, score 52.4, MF 65, risk 15, sector `Các công ty đầu cơ và phát triển bất động sản`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **HNM** (Tier 2, score 52.2, MF 59, risk 0, sector `Sản phẩm thực phẩm`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **VPL** (Tier 2, score 50.5, MF 66, risk 0, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **PSI** (Tier 2, score 49.5, MF 56, risk 27, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Emerging (no fund tag); flow/risk pass emerging gate
  - **Also:** context score elevated; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.

### 3. Important rejects (fund-linked, flow failed)

- **GMD** (Reject, score 34.6, MF 32, risk 37, sector `Dịch vụ vận tải`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; daily/weekly CMF conflict
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (37)
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; daily/weekly CMF conflict; risk penalty elevated; distribution risk flag
- **MBB** (Reject, score 28.3, MF 18, risk 40, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; risk penalty elevated; distribution risk flag
- **CTG** (Reject, score 25.4, MF 17, risk 25, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; distribution risk flag
- **MWG** (Reject, score 24.9, MF 25, risk 40, sector `Bán lẻ tổng hợp`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; risk penalty elevated; distribution risk flag
- **HPG** (Reject, score 22.1, MF 13, risk 40, sector `Khai thác quặng sắt và sản xuất thép`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; risk penalty elevated; distribution risk flag
- **BVH** (Reject, score 36.3, MF 39, risk 55, sector `Bảo hiểm nhân thọ`) — `selective_fund_bet`
  - **Why:** Fund-linked, but grouped money flow not confirming
  - **Also:** bucket=selective_fund_bet; CMF block strong; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (55)
  - **Note:** Size as research only until risk penalty improves.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; risk penalty elevated; distribution risk flag
- **POW** (Reject, score 32.3, MF 24, risk 15, sector `Sản xuất và cung cấp điện truyền thống`) — `fund_commentary_mention`
  - **Why:** Fund-linked, but grouped money flow not confirming
  - **Also:** bucket=fund_commentary_mention; context score elevated; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Reject — use full scan row for CMF/OBV detail.
  - **Failed because:** weak grouped money flow; weekly CMF still weak
- **STB** (Reject, score 31.0, MF 30, risk 40, sector `Ngân hàng`) — `consensus_second_ring`
  - **Why:** Fund-linked, but grouped money flow not confirming
  - **Also:** bucket=consensus_second_ring; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Reject — use full scan row for CMF/OBV detail.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; risk penalty elevated; distribution risk flag

### 4. Elevated risk / distortion / distribution (Tier 1–3; matches caution-proxy %)

- **THD** (Tier 3, score 53.4, MF 81, risk 68, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** CMF block strong; OBV/PVT supportive; context score elevated
  - **Risk:** High risk penalty (68)
  - **Note:** Size as research only until risk penalty improves.
- **ACB** (Tier 3, score 50.7, MF 76, risk 55, sector `Ngân hàng`) — `fund_commentary_mention`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** bucket=fund_commentary_mention; CMF block strong; OBV/PVT supportive
  - **Risk:** Distribution-day count elevated; High risk penalty (55)
  - **Note:** Size as research only until risk penalty improves.
- **TVN** (Tier 3, score 51.0, MF 71, risk 53, sector `Khai thác quặng sắt và sản xuất thép`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** CMF block strong; OBV/PVT supportive; context score elevated
  - **Risk:** High risk penalty (53)
  - **Note:** Size as research only until risk penalty improves.
- **GAS** (Tier 3, score 38.1, MF 36, risk 52, sector `Phân phối khí đốt`) — `fund_commentary_mention`
  - **Why:** Tier held up mainly by context, not flow confirmation; weekly CMF still weak
  - **Also:** bucket=fund_commentary_mention; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; High risk penalty (52)
  - **Note:** Investigate whether context is masking weak CMF/participation.
- **VCB** (Tier 3, score 44.2, MF 51, risk 52, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** bucket=consensus_core; OBV/PVT supportive; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (52)
  - **Note:** Size as research only until risk penalty improves.
- **PC1** (Tier 3, score 39.5, MF 54, risk 52, sector `Xây dựng, xây lắp`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** CMF block strong; OBV/PVT supportive; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (52)
  - **Note:** Size as research only until risk penalty improves.
- **DBD** (Tier 3, score 38.2, MF 52, risk 40, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Scan tier driven by mixed flow/context/risk profile
  - **Also:** CMF block strong; context score elevated
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Tier 3 — use full scan row for CMF/OBV detail.
- **TTA** (Tier 3, score 41.3, MF 61, risk 40, sector `Sản xuất và cung cấp điện truyền thống`) — `outside_fund_disclosure`
  - **Why:** Grouped money flow supportive
  - **Also:** CMF block strong; context score elevated
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Tier 3 — use full scan row for CMF/OBV detail.

## C. Bucket mix

**Denominator:** All Tier 1–3 names in scan (n=47)

| Bucket | Count | % | Definition |
| --- | ---: | ---: | --- |
| fund_backed | 4 | 8.5% | has_fund_disclosure_tag among Tier 1–3 |
| emerging | 18 | 38.3% | emerging_accumulation_candidate among Tier 1–3 |
| vin_distortion_flagged | 0 | 0.0% | vingroup_distortion_flag=True among Tier 1–3 (scan boolean) |
| caution_proxy | 19 | 40.4% | vin_flag OR distribution_risk_flag OR score_risk_penalty>=45 (matches section 4 list) |
| outside_fund_disclosure | 43 | 91.5% | fund_context_bucket=outside_fund_disclosure among Tier 1–3 |

**Unknown sector in displayed look-first lists:** 4/25 (16.0%)
_(16 names enriched from `data/master/sector_map.csv` for display only.)_

## D. Changes since previous scan

_Previous scan date: 2026-06-05_

- **New Tier 1–2:** —
- **Dropped Tier 1–2:** C69, DL1, F88, NAF, TLD, TVN, VND, VVS
- **Tier change:** BVB Tier 3 → Reject, Δ-6.7
- **Tier change:** BVH Tier 3 → Reject, Δ-4.8
- **Tier change:** C69 Tier 2 → Tier 3, Δ-4.2
- **Tier change:** DL1 Tier 2 → Tier 3, Δ-6.7
- **Tier change:** DLG Reject → Tier 3, Δ+6.6
- **Tier change:** F88 Tier 2 → Reject, Δ-19.7
- **Tier change:** FOX Tier 3 → Reject, Δ-10.2
- **Tier change:** MBS Tier 3 → Reject, Δ-6.9
- **Tier change:** MZG Reject → Tier 3, Δ+5.9
- **Tier change:** NAF Tier 2 → Tier 3, Δ-1.2
- **Tier change:** NDN Tier 3 → Reject, Δ-6.5
- **Tier change:** PC1 Reject → Tier 3, Δ+10.4
- **Score up:** LDP Δ+18.5 → Reject
- **Score up:** MCF Δ+15.5 → Reject
- **Score up:** TKU Δ+15.5 → Reject
- **Score up:** SAS Δ+15.0 → Reject
- **Score up:** CIG Δ+14.5 → Reject
- **Score down:** F88 Δ-19.7 → Reject
- **Score down:** NVT Δ-14.1 → Reject
- **Score down:** SIV Δ-11.9 → Reject
- **Score down:** MCG Δ-11.2 → Reject
- **Score down:** GEX Δ-10.9 → Reject

## E. Workflow warnings (priority order)

- [P1 Structural] Top tier is 92% outside_fund_disclosure (43/47) — cross-check emerging vs April fund priors.
- [P2 Data] Unknown sector in displayed look-first lists: 4/25 — interpret sector/theme bullets cautiously.
- [P3 Market] No Tier 1 names — narrow/fragile regime; prioritize Tier 2 focus + near-miss.
- [P4 Caution] Emerging universe has several elevated risk_penalty names — vet before prioritizing.
- [P4 Caution] caution-proxy (section 4 rule): 19/47 Tier 1–3 names (40%) — includes high risk_penalty, not only vin_distortion_flag.

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