# Institutional Accumulation — Operator Summary

**Scan date:** 2026-07-09  
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
| Tier 3 | 33 |
| Reject | 1508 |
| Emerging (universe) | 27 |
| Top-tier fund-backed | 2 |
| Unknown sector (Tier 1–3) | 8/54 |

## B. What to look at first

### 1. Top fund-backed candidates (Tier 1–3)

- **GMD** (Tier 3, score 42.6, MF 55, risk 40, sector `Dịch vụ vận tải`) — `consensus_core`
  - **Why:** Scan tier driven by mixed flow/context/risk profile
  - **Also:** bucket=consensus_core; context score elevated
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Tier 3 — use full scan row for CMF/OBV detail.
- **TCB** (Tier 3, score 39.2, MF 42, risk 55, sector `Ngân hàng`) — `consensus_second_ring`
  - **Why:** Tier held up mainly by context, not flow confirmation; weekly CMF still weak
  - **Also:** bucket=consensus_second_ring; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; High risk penalty (55)
  - **Note:** Investigate whether context is masking weak CMF/participation.

### 2. Top emerging candidates (no fund tag)

- **SSB** (Tier 2, score 58.4, MF 76, risk 0, sector `Ngân hàng`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; OBV/PVT supportive; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **PSI** (Tier 2, score 57.9, MF 80, risk 20, sector `Securities`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **NAB** (Tier 2, score 57.0, MF 80, risk 15, sector `Ngân hàng`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **MSB** (Tier 2, score 56.0, MF 63, risk 0, sector `Ngân hàng`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **ABB** (Tier 2, score 55.2, MF 65, risk 0, sector `Ngân hàng`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **CSM** (Tier 2, score 55.0, MF 74, risk 30, sector `Rubber`) — `outside_fund_disclosure`
  - **Why:** Emerging (no fund tag); flow/risk pass emerging gate
  - **Also:** CMF block strong; context score elevated
  - **Risk:** Moderate risk penalty (30)
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **TVC** (Tier 2, score 53.9, MF 64, risk 0, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** OBV/PVT supportive; context score elevated; weekly CMF still weak
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **HDB** (Tier 2, score 52.6, MF 69, risk 0, sector `Ngân hàng`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.

### 3. Important rejects (fund-linked, flow failed)

- **MBB** (Reject, score 36.8, MF 43, risk 40, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Consensus-core name below accumulation tier thresholds
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weekly CMF still weak; risk penalty elevated; distribution risk flag
- **VCB** (Reject, score 33.4, MF 40, risk 40, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; risk penalty elevated; distribution risk flag
- **MWG** (Reject, score 32.3, MF 33, risk 52, sector `Bán lẻ tổng hợp`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; High risk penalty (52)
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; risk penalty elevated; distribution risk flag
- **CTG** (Reject, score 31.5, MF 34, risk 40, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; risk penalty elevated; distribution risk flag
- **HPG** (Reject, score 23.0, MF 20, risk 40, sector `Khai thác quặng sắt và sản xuất thép`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; risk penalty elevated; distribution risk flag
- **POW** (Reject, score 37.9, MF 50, risk 67, sector `Sản xuất và cung cấp điện truyền thống`) — `fund_commentary_mention`
  - **Why:** Scan tier driven by mixed flow/context/risk profile
  - **Also:** bucket=fund_commentary_mention; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; High risk penalty (67)
  - **Note:** Size as research only until risk penalty improves.
  - **Failed because:** weekly CMF still weak; risk penalty elevated; distribution risk flag
- **STB** (Reject, score 34.4, MF 43, risk 40, sector `Ngân hàng`) — `consensus_second_ring`
  - **Why:** Scan tier driven by mixed flow/context/risk profile
  - **Also:** bucket=consensus_second_ring; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Reject — use full scan row for CMF/OBV detail.
  - **Failed because:** weekly CMF still weak; risk penalty elevated; distribution risk flag
- **VHM** (Reject, score 29.1, MF 41, risk 55, sector `Các công ty đầu cơ và phát triển bất động sản`) — `consensus_second_ring`
  - **Why:** VIN-linked name: elevated risk penalty; distortion flag not active at this as-of
  - **Also:** bucket=consensus_second_ring; context score thin; daily CMF missing
  - **Risk:** Distribution-day count elevated; High risk penalty (55); VIN name in caution via risk, not distortion flag
  - **Note:** Size as research only until risk penalty improves.
  - **Failed because:** daily CMF missing; risk penalty elevated; distribution risk flag

### 4. Elevated risk / distortion / distribution (Tier 1–3; matches caution-proxy %)

- **NVB** (Tier 3, score 43.4, MF 61, risk 68, sector `Ngân hàng`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** CMF block strong; context score elevated
  - **Risk:** High risk penalty (68)
  - **Note:** Size as research only until risk penalty improves.
- **HSL** (Tier 3, score 47.8, MF 73, risk 60, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** CMF block strong; OBV/PVT supportive; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (60)
  - **Note:** Size as research only until risk penalty improves.
- **VGR** (Tier 3, score 46.8, MF 72, risk 58, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** OBV/PVT supportive; context score elevated; daily CMF missing
  - **Risk:** Distribution-day count elevated; High risk penalty (58)
  - **Note:** Size as research only until risk penalty improves.
- **HVN** (Tier 3, score 40.8, MF 49, risk 55, sector `Hàng không chở khách`) — `outside_fund_disclosure`
  - **Why:** Scan tier driven by mixed flow/context/risk profile
  - **Also:** context score elevated; daily CMF missing
  - **Risk:** Distribution-day count elevated; High risk penalty (55)
  - **Note:** Size as research only until risk penalty improves.
- **TCB** (Tier 3, score 39.2, MF 42, risk 55, sector `Ngân hàng`) — `consensus_second_ring`
  - **Why:** Tier held up mainly by context, not flow confirmation; weekly CMF still weak
  - **Also:** bucket=consensus_second_ring; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; High risk penalty (55)
  - **Note:** Investigate whether context is masking weak CMF/participation.
- **VDS** (Tier 3, score 44.7, MF 60, risk 52, sector `Công ty chứng khoán`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** CMF block strong; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; High risk penalty (52)
  - **Note:** Size as research only until risk penalty improves.
- **BMP** (Tier 3, score 46.2, MF 61, risk 52, sector `Hóa chất cơ bản - Sản phẩm nhựa, cao su, hóa chất`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** CMF block strong; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; High risk penalty (52)
  - **Note:** Size as research only until risk penalty improves.
- **TCX** (Tier 3, score 40.1, MF 59, risk 52, sector `Securities`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; High risk penalty (52)
  - **Note:** Size as research only until risk penalty improves.

## C. Bucket mix

**Denominator:** All Tier 1–3 names in scan (n=54)

| Bucket | Count | % | Definition |
| --- | ---: | ---: | --- |
| fund_backed | 2 | 3.7% | has_fund_disclosure_tag among Tier 1–3 |
| emerging | 27 | 50.0% | emerging_accumulation_candidate among Tier 1–3 |
| vin_distortion_flagged | 0 | 0.0% | vingroup_distortion_flag=True among Tier 1–3 (scan boolean) |
| caution_proxy | 25 | 46.3% | vin_flag OR distribution_risk_flag OR score_risk_penalty>=45 (matches section 4 list) |
| outside_fund_disclosure | 52 | 96.3% | fund_context_bucket=outside_fund_disclosure among Tier 1–3 |

**Unknown sector in displayed look-first lists:** 3/25 (12.0%)
_(56 names enriched from `data/master/sector_map.csv` for display only.)_

## D. Changes since previous scan

_Previous scan date: 2026-07-08_

_No meaningful tier or score changes vs previous scan._

## E. Workflow warnings (priority order)

- [P1 Structural] Top tier is 96% outside_fund_disclosure (52/54) — cross-check emerging vs April fund priors.
- [P2 Data] Unknown sector in displayed look-first lists: 3/25 — interpret sector/theme bullets cautiously.
- [P3 Market] No Tier 1 names — narrow/fragile regime; prioritize Tier 2 focus + near-miss.
- [P4 Caution] Emerging universe has several elevated risk_penalty names — vet before prioritizing.
- [P4 Caution] caution-proxy (section 4 rule): 25/54 Tier 1–3 names (46%) — includes high risk_penalty, not only vin_distortion_flag.

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