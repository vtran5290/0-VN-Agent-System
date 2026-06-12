# Institutional Accumulation — Operator Summary

**Scan date:** 2026-06-10  
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
| Tier 3 | 24 |
| Reject | 1516 |
| Emerging (universe) | 22 |
| Top-tier fund-backed | 2 |
| Unknown sector (Tier 1–3) | 11/46 |

## B. What to look at first

### 1. Top fund-backed candidates (Tier 1–3)

- **ACB** (Tier 2, score 54.5, MF 80, risk 40, sector `Ngân hàng`) — `fund_commentary_mention`
  - **Why:** Grouped money flow supportive
  - **Also:** bucket=fund_commentary_mention; CMF block strong; OBV/PVT supportive
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Tier 2 — use full scan row for CMF/OBV detail.
- **VCB** (Tier 3, score 43.6, MF 49, risk 52, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Scan tier driven by mixed flow/context/risk profile
  - **Also:** bucket=consensus_core; OBV/PVT supportive; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (52)
  - **Note:** Size as research only until risk penalty improves.

### 2. Top emerging candidates (no fund tag)

- **MSB** (Tier 2, score 59.7, MF 68, risk 0, sector `Ngân hàng`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **AMS** (Tier 2, score 57.6, MF 76, risk 15, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **DL1** (Tier 2, score 55.6, MF 60, risk 0, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **ABB** (Tier 2, score 55.0, MF 61, risk 0, sector `Ngân hàng`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **OCB** (Tier 2, score 53.8, MF 77, risk 30, sector `Ngân hàng`) — `outside_fund_disclosure`
  - **Why:** Emerging (no fund tag); flow/risk pass emerging gate
  - **Also:** CMF block strong; context score elevated
  - **Risk:** Moderate risk penalty (30)
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **MST** (Tier 2, score 52.3, MF 53, risk 0, sector `Xây dựng, xây lắp`) — `outside_fund_disclosure`
  - **Why:** Emerging (no fund tag); flow/risk pass emerging gate
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **TCI** (Tier 2, score 52.3, MF 58, risk 15, sector `Công ty chứng khoán`) — `outside_fund_disclosure`
  - **Why:** Emerging name with strong grouped flow and low risk
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.
- **HHP** (Tier 2, score 51.6, MF 55, risk 0, sector `Giấy`) — `outside_fund_disclosure`
  - **Why:** Emerging (no fund tag); flow/risk pass emerging gate
  - **Also:** CMF block strong; context score elevated
  - **Risk:** No major structural risk flag
  - **Note:** Validate catalyst and liquidity; no fund disclosure tag.

### 3. Important rejects (fund-linked, flow failed)

- **MBB** (Reject, score 27.6, MF 21, risk 40, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; risk penalty elevated; distribution risk flag
- **GMD** (Reject, score 27.0, MF 31, risk 52, sector `Dịch vụ vận tải`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; daily/weekly CMF conflict
  - **Risk:** Distribution-day count elevated; High risk penalty (52)
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; daily/weekly CMF conflict; risk penalty elevated; distribution risk flag
- **MWG** (Reject, score 26.1, MF 26, risk 40, sector `Bán lẻ tổng hợp`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; risk penalty elevated; distribution risk flag
- **CTG** (Reject, score 24.8, MF 15, risk 25, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; distribution risk flag
- **HPG** (Reject, score 22.1, MF 13, risk 40, sector `Khai thác quặng sắt và sản xuất thép`) — `consensus_core`
  - **Why:** Consensus-core, but grouped money flow still weak
  - **Also:** bucket=consensus_core; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Monitor as fund-core reject — check if flow repair is underway.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; risk penalty elevated; distribution risk flag
- **GAS** (Reject, score 36.8, MF 30, risk 25, sector `Phân phối khí đốt`) — `fund_commentary_mention`
  - **Why:** Fund-linked, but grouped money flow not confirming
  - **Also:** bucket=fund_commentary_mention; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated
  - **Note:** Reject — use full scan row for CMF/OBV detail.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; distribution risk flag
- **BVH** (Reject, score 35.8, MF 43, risk 40, sector `Bảo hiểm nhân thọ`) — `selective_fund_bet`
  - **Why:** Scan tier driven by mixed flow/context/risk profile
  - **Also:** bucket=selective_fund_bet; CMF block strong; context score elevated
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Reject — use full scan row for CMF/OBV detail.
  - **Failed because:** weekly CMF still weak; risk penalty elevated; distribution risk flag
- **FPT** (Reject, score 35.8, MF 39, risk 40, sector `Công nghệ phần mềm`) — `fund_commentary_mention`
  - **Why:** Fund-linked, but grouped money flow not confirming
  - **Also:** bucket=fund_commentary_mention; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; Moderate risk penalty (40)
  - **Note:** Reject — use full scan row for CMF/OBV detail.
  - **Failed because:** weak grouped money flow; weekly CMF still weak; risk penalty elevated; distribution risk flag

### 4. Elevated risk / distortion / distribution (Tier 1–3; matches caution-proxy %)

- **VIW** (Tier 3, score 38.2, MF 57, risk 87, sector `Xây dựng, xây lắp`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** OBV/PVT supportive; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (87)
  - **Note:** Size as research only until risk penalty improves.
- **APS** (Tier 3, score 39.1, MF 48, risk 70, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Scan tier driven by mixed flow/context/risk profile
  - **Also:** context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; High risk penalty (70)
  - **Note:** Size as research only until risk penalty improves.
- **THD** (Tier 3, score 52.6, MF 79, risk 68, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** CMF block strong; OBV/PVT supportive; context score elevated
  - **Risk:** High risk penalty (68)
  - **Note:** Size as research only until risk penalty improves.
- **TVN** (Tier 3, score 45.1, MF 62, risk 53, sector `Khai thác quặng sắt và sản xuất thép`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** CMF block strong; OBV/PVT supportive; context score elevated
  - **Risk:** High risk penalty (53)
  - **Note:** Size as research only until risk penalty improves.
- **VAB** (Tier 3, score 42.6, MF 62, risk 52, sector `Ngân hàng`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** CMF block strong; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; High risk penalty (52)
  - **Note:** Size as research only until risk penalty improves.
- **VCB** (Tier 3, score 43.6, MF 49, risk 52, sector `Ngân hàng`) — `consensus_core`
  - **Why:** Scan tier driven by mixed flow/context/risk profile
  - **Also:** bucket=consensus_core; OBV/PVT supportive; context score elevated
  - **Risk:** Distribution-day count elevated; High risk penalty (52)
  - **Note:** Size as research only until risk penalty improves.
- **DLG** (Tier 3, score 43.9, MF 55, risk 52, sector `Các công ty đầu cơ và phát triển bất động sản`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** CMF block strong; context score elevated; weekly CMF still weak
  - **Risk:** Distribution-day count elevated; High risk penalty (52)
  - **Note:** Size as research only until risk penalty improves.
- **IDJ** (Tier 3, score 49.6, MF 64, risk 50, sector `Unknown`) — `outside_fund_disclosure`
  - **Why:** Flow acceptable, but risk penalty too high for clean accumulation
  - **Also:** CMF block strong; context score elevated
  - **Risk:** High risk penalty (50)
  - **Note:** Size as research only until risk penalty improves.

## C. Bucket mix

**Denominator:** All Tier 1–3 names in scan (n=46)

| Bucket | Count | % | Definition |
| --- | ---: | ---: | --- |
| fund_backed | 2 | 4.3% | has_fund_disclosure_tag among Tier 1–3 |
| emerging | 22 | 47.8% | emerging_accumulation_candidate among Tier 1–3 |
| vin_distortion_flagged | 0 | 0.0% | vingroup_distortion_flag=True among Tier 1–3 (scan boolean) |
| caution_proxy | 16 | 34.8% | vin_flag OR distribution_risk_flag OR score_risk_penalty>=45 (matches section 4 list) |
| outside_fund_disclosure | 44 | 95.7% | fund_context_bucket=outside_fund_disclosure among Tier 1–3 |

**Unknown sector in displayed look-first lists:** 5/25 (20.0%)
_(16 names enriched from `data/master/sector_map.csv` for display only.)_

## D. Changes since previous scan

_Previous scan date: 2026-06-08_

- **New Tier 1–2:** ABB, ACB, AMS, C69, DL1, DST, NVB, QNS, VC3, VND
- **Dropped Tier 1–2:** KSF
- **Tier change:** ABB Tier 3 → Tier 2, Δ+10.4
- **Tier change:** ACB Tier 3 → Tier 2, Δ+3.8
- **Tier change:** AMS Reject → Tier 2, Δ+9.8
- **Tier change:** APS Reject → Tier 3, Δ+12.2
- **Tier change:** BIC Tier 3 → Reject, Δ-3.7
- **Tier change:** C69 Tier 3 → Tier 2, Δ+2.5
- **Tier change:** CTF Reject → Tier 3, Δ+5.6
- **Tier change:** CTR Reject → Tier 3, Δ+7.1
- **Tier change:** DBD Tier 3 → Reject, Δ-5.6
- **Tier change:** DCL Tier 3 → Reject, Δ-7.0
- **Tier change:** DL1 Tier 3 → Tier 2, Δ+15.6
- **Tier change:** DST Reject → Tier 2, Δ+10.5
- **Score up:** TS3 Δ+21.3 → Reject
- **Score up:** VW3 Δ+16.2 → Reject
- **Score up:** BKG Δ+16.0 → Reject
- **Score up:** DL1 Δ+15.6 → Tier 2
- **Score up:** KVC Δ+14.8 → Reject
- **Score down:** VTO Δ-16.6 → Reject
- **Score down:** KSF Δ-14.2 → Tier 3
- **Score down:** HKT Δ-13.8 → Reject
- **Score down:** GTS Δ-13.0 → Reject
- **Score down:** SSC Δ-12.3 → Reject

## E. Workflow warnings (priority order)

- [P1 Structural] Top tier is 96% outside_fund_disclosure (44/46) — cross-check emerging vs April fund priors.
- [P2 Data] Unknown sector in displayed look-first lists: 5/25 — interpret sector/theme bullets cautiously.
- [P3 Market] No Tier 1 names — narrow/fragile regime; prioritize Tier 2 focus + near-miss.
- [P4 Caution] Emerging universe has several elevated risk_penalty names — vet before prioritizing.
- [P4 Caution] caution-proxy (section 4 rule): 16/46 Tier 1–3 names (35%) — includes high risk_penalty, not only vin_distortion_flag.

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