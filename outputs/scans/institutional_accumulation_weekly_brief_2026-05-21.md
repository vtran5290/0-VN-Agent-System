# Institutional Accumulation Weekly Brief — Research Only

**As-of:** 2026-05-21 | **Methodology:** v1.1 | **Rows scored:** 1562  
**Regime:** `fragile_uptrend_narrow_leadership` (source: `data/smart_money/priors/apr2026_default_priors.json`, month **2026-04**)  
**Universe:** `full_liquid_universe` — all liquid `data/stocks/*.csv`; fund lists are **context tags only**.

> **Safety:** Research ranking / prioritization only. Does **not** set `final_action`, orders, OMS, sizing, or execution.

**Primary outputs:** `outputs/scans/institutional_accumulation_2026-05-21.csv`, `.json`, `institutional_accumulation_operator_summary_2026-05-21.html`

---

## Global Macro + Fed (brief)

**FACTS** (from `data/decision/weekly_report.md`, as-of **2026-05-17** — not re-fetched for this scan):

- UST 2Y **4.0%**, 10Y **4.47%** (FRED, value_date 2026-05-14)
- DXY reconstructed **97.92** (FRED H.10, 2026-05-08); legacy WoW Δ **-0.20**
- US CPI YoY **3.81%** (ref month 2026-04)
- NFP change **+115k** persons (2026-04-01)

**INTERPRETATION**

- Mild UST softening + softer DXY WoW is **neutral-to-supportive** for EM risk appetite, but data are **4–9 days stale** vs scan date 2026-05-21.
- For accumulation work, treat global block as **background**; scan OHLCV is local CSV through **2026-05-21**.

---

## Vietnam Policy + Liquidity (brief)

**FACTS** (same weekly packet, 2026-05-17):

- OMO net **+4000** (SBV scrape); WoW Δ **-6000** (less injection vs prior week)
- Interbank ON **6.05%**; WoW Δ **+1.81pp**
- Credit growth YoY **12.5%**; WoW Δ **+0.4pp**
- SBV reference USD/VND **25,131**

**INTERPRETATION**

- Liquidity tone: **mixed** — OMO net positive but down WoW; short rate up → not a clear “easy liquidity” impulse for broad risk-on.
- Transmission sketch: **rates up short-end → bank NIM pressure / cautious credit → FX stable → equity flow still selective** (fits fragile narrow leadership tag).

---

## Market internals (scan-derived)

**FACTS**

| Tier | Count |
|------|------:|
| Tier 1 | 0 |
| Tier 2 | 18 |
| Tier 3 | 33 |
| Reject | 1511 |
| Emerging (universe) | 28 |

- **Tier 1–2 by sector (top):** Unknown **5**, construction-related **3**, transport **2**, chemicals **2**, plus single names in securities, paper, real estate (see `sector_summary.tier12_count_by_sector` in JSON).
- **Emerging top 5:** TCI (56.9), DRI (55.8), HHP (55.8), VPI (53.0), PIV (50.7) — all **outside_fund_disclosure**, Tier 2.
- **Vingroup:** `vingroup_distortion_flag` count **0** this run; **3** VIN-watch names in caution-proxy via **risk ≥ 45** (VIC, VHM, VRE/VPL class).
- **VNINDEX caveat:** Cap-weighted index health may be **Vingroup-skewed** in 2025–2026; prefer breadth-style checks for broad-market conclusions (`docs/research/VIN_EMA_CLOUD_BASELINE.md`).
- **Breadth proxy in scan validation:** not a native field; **Unknown** — would need separate breadth job.

**INTERPRETATION**

- Market internals = **narrow flow leadership**: no Tier 1; Tier 2 stack is **non-fund emerging** names with strong grouped MF.
- April fund **consensus banks** (MBB, MWG, HPG) remain **Reject** or weak Tier 3 — **fund narrative ≠ flow confirmation** at this OHLCV slice.

---

## Sectors & Companies (accumulation lens)

### FACTS table

| ticker | tier | score | score_money_flow | fund_context_bucket | emerging | vingroup_distortion |
|--------|------|------:|-----------------:|---------------------|----------|---------------------|
| MBB | Reject | 23.0 | 21 | consensus_core | false | false |
| CTG | Tier 3 | 40.9 | 50 | consensus_core | false | false |
| MWG | Reject | 31.8 | 27 | consensus_core | false | false |
| HPG | Reject | 28.0 | 23 | consensus_core | false | false |
| GMD | Reject | 37.3 | 46 | consensus_core | false | false |
| VCB | Tier 3 | 39.5 | 42 | consensus_core | false | false |
| STB | Tier 3 | 46.2 | 42 | consensus_second_ring | false | false |
| VHM | Tier 3 | 40.5 | 48 | consensus_second_ring | false | false |
| VIC | Tier 3 | 40.4 | 56 | outside_fund_disclosure | false | false |
| TCI | Tier 2 | 56.9 | 78 | outside_fund_disclosure | true | false |
| DRI | Tier 2 | 55.8 | 66 | outside_fund_disclosure | true | false |
| HHP | Tier 2 | 55.8 | 74 | outside_fund_disclosure | true | false |
| VPI | Tier 2 | 53.0 | 81 | outside_fund_disclosure | true | false |
| BSR | Tier 2 | 52.4 | 70 | outside_fund_disclosure | false | false |

*Full universe: `outputs/scans/institutional_accumulation_2026-05-21.csv`; top 80: `*_top80.csv`.*

### INTERPRETATION

- **Consensus vs flow:** April core/ring names score on **context** but **weak/fragile CMF** on banks (MBB/MWG/HPG Reject); CTG/VCB/STB Tier 3 are **context-floor** names, not clean accumulation.
- **Emerging vs fund priors:** Top flow is **outside April disclosure lists** (TCI, DRI, HHP, VPI) — research queue should **not** assume fund holdings drive the scan leaderboard.
- **VIN:** VIC has decent MF but **high risk penalty**; distortion flag off — treat as **caution**, not structural VIN distortion signal.

---

## Decision layer (research only)

### Top 3 research actions

1. **Forensic pass on Tier 2 emerging leaders** (TCI, DRI, HHP, VPI): confirm catalyst, liquidity, and whether flow persists vs April fund themes.
2. **Bank flow repair watch** on MBB/CTG/MWG: weekly CMF + grouped MF must improve before upgrading from Reject/Tier 3 context floor.
3. **Reconcile VIC/VHM** with risk-proxy caution: no `vingroup_distortion_flag`, but risk ≥ 50 — cap-weight narrative risk separate from scan flag.

### Top 3 methodology risks

1. **Sector Unknown concentration** (5/18 Tier 1–2 labeled Unknown) — sector theme stats unreliable.
2. **Zero Tier 1** under fragile floors — operators may misread as “broken scan” vs intentional strict gate.
3. **Stale macro block** if brief read without checking `weekly_report.md` date (2026-05-17 vs scan 2026-05-21).

### Watchlist updates (symbols only)

**Add / elevate monitoring** (from scan; not buy signals): `TCI`, `DRI`, `HHP`, `VPI`, `BSR`, `CTG` (tier change vs prior scan)

**Maintain distress watch:** `MBB`, `MWG`, `HPG`, `GMD`

*Existing `config/watchlist.txt` holdings overlap: STB, BID, VCB, CTG — scan shows STB/CTG/VCB Tier 3 context-led; align human notes.*

---

## Validation & data integrity

| Check | Result |
|-------|--------|
| `execution_leakage_check` | **ok** |
| `money_flow_redundancy` | **ok** (no pair ≥ 0.9) |
| `price_unit_mode` | **thousand_vnd** (1562 rows) |
| OHLCV source | Local CSV, sliced through **2026-05-21** |
| Fund context | April priors fallback (no `smart_money_2026-05.json` in repo) |

**Limitations:** No sector RS vs index; no pocket pivot; no live FireAnt pull in this brief; macro/policy bullets from **weekly packet 2026-05-17**.

---

## Signals to monitor next week

- **MBB / MWG weekly CMF** turning positive with OBV slope > 0 (consensus repair signal).
- **TCI / VPI** staying Tier 2 with MF ≥ 55 and risk ≤ 25 (emerging quality persistence).
- **New Tier 1–2 entrants** vs 2026-04-30 baseline (14 names joined Tier 1–2 per diff JSON).
- **VIC risk_penalty** and extension — if risk drops below 45, caution-proxy may clear without distortion flag.
- **Sector map coverage** — Unknown share in Tier 1–2 falling after data refresh.

---

## If X happens → do Y (research steps only)

| If | Then (research) |
|----|-----------------|
| MBB or MWG crosses **Tier 3 fragile floor** with MF ≥ 48 and weekly CMF > 0.05 | Re-run scan; document upgrade path for consensus-core narrative |
| Any Tier 2 emerging name gains **≥6 distribution days** | Downgrade to watch-only; remove from priority queue |
| **Tier 1 count &gt; 0** on next run | Re-assess regime tag; compare to `fragile_uptrend` priors — may signal broadening |
| VIC `vingroup_distortion_flag` turns **true** | Re-read diagnosis string; separate from cap-weight index commentary |
| Emerging count drops sharply after OHLCV refresh | Check for stale `data/stocks` bars (many files end ~2026-05-15) before changing methodology |

---

*End weekly brief — institutional accumulation scan only.*
