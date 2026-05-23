# Institutional Accumulation Scan — Weekly Research Brief
**As-of: 2026-04-30 | Methodology: v1.1 | Scan rows: 1,564**  
**Regime: `fragile_uptrend_narrow_leadership` (source: `data/smart_money/priors/apr2026_default_priors.json`)**  
**Universe policy: `full_liquid_universe` | Research ranking only — does not set final_action**

---

## Global Macro + Fed (brief)

FACTS (from regime priors; no live macro data in repo as of scan date):
- Regime priors cite: `oil_geopolitics_inflation`, `weak_foreign_flow`, `narrow_breadth`, `low_liquidity_dispersion`
- Catalysts cited in priors: `Q1_earnings_strength`, `FTSE_secondary_EM_upgrade`
- Fed/DM rate trajectory as of April 2026: **Unknown from local repo** — confirm via SSBV/Fed minutes external feed

INTERPRETATION:
- The `fragile_uptrend_narrow_leadership` regime tag implies risk-on is not broad. If DM rates are elevated, foreign flow into VN equities remains constrained.
- FTSE secondary EM upgrade catalyst is a potential re-rating trigger for banks and large-cap names (MBB, CTG, VCB) — but flow data as of 2026-04-30 does not yet show that re-rating materializing in CMF/OBV signals.
- Confirm/deny: VN-Index level and 20-bar breadth indicator not available from local OHLCV without computing cross-stock advance/decline. Unknown from this scan run alone.

---

## Vietnam Policy + Liquidity (brief)

FACTS (from regime priors; OMO/interbank data not in scan outputs):
- `apr2026_default_priors.json:risk_flags`: `weak_foreign_flow`, `low_liquidity_dispersion`
- Credit/FX/OMO actual data for April 2026: **Unknown** — not available in `data/smart_money/priors/`

INTERPRETATION:
- Policy `policy_liquidity_sensitive` theme names (MBB, CTG, VCB, TCB, STB, BID, ACB) are all Reject or Tier 3 in this scan. If interbank rates remained elevated into April-end, this is consistent with the weak CMF readings on bank names.
- Transmission chain: OMO tightness → higher interbank → credit cost → bank NIM compression → equity valuation drag. Consistent with scan showing VCB CMF = −0.133 (negative daily CMF), CTG MF = 25.

---

## Market Internals (scan-derived)

FACTS:
- **Tier distribution**: Tier 1 = 0 | Tier 2 = 13 | Tier 3 = 35 | Reject = 1,516
- **Max score in full universe**: 57.4 (TOS, transport) — well below Tier 1 floor of 72
- **Emerging accumulation**: 36 candidates outside fund disclosure; top 5 below
- **VIN distortion flags**: 2 (VIC, VHM)
- **Breadth proxy**: Not directly computed in this scan. VNINDEX cap-weight index is distorted by Vingroup (VIC, VHM, VRE combined ~25–30% weight). VN-Index headline may overstate breadth.

**Top sectors in Tier 2:**
| Sector | Tier 2 count | Sample tickers |
|---|---|---|
| Real estate (BDS) | 4 | NRC, SJS, KSF, VPI |
| Unknown (sector map gap) | 4 | TNT, DSH, PIV, SJS† |
| Transport (Dịch vụ vận tải) | 1 | TOS |
| Pharma (Dược phẩm) | 1 | DVM |
| Aviation | 1 | VJC |
| Chemicals/plastics | 2 | PCH, BFC |
† SJS appears in both real estate and Unknown — sector map inconsistency.

**Vingroup distortion note:**
- VNINDEX is cap-weight; VIC rallied +47.8% vs VNINDEX 20d (RS_vs_VNINDEX_20d). This distorts headline index returns.
- Both VIC and VHM are in Tier 3 with VIN distortion flag applied (+22 risk penalty, −26 context deduction in fragile regime).
- VIC: price-led CMF only; extension 34.8% above MA20/50; weekly CMF = −0.011 (negative). Tier 3 only due to high MF=63.41 from participation/up-volume signals — not persistent multi-horizon flow.
- VHM: extension 28.8%; weekly CMF = 0.015 (barely positive, below VIN_CMF_WEEKLY_WEAK threshold of 0.03).

**Top 5 emerging accumulation candidates (outside fund disclosure, Tier 2+):**
| Ticker | Tier | Score | MF | Sector | Risk | Note |
|---|---|---|---|---|---|---|
| TOS | Tier 2 | 57.4 | 72.0 | Transport | 0.0 | Strong CMF daily+weekly; OBV above MA20; clean risk |
| DVM | Tier 2 | 53.8 | 75.65 | Pharma | 0.0 | CMF=0.261/0.143; all groups positive; risk-free |
| NRC | Tier 2 | 53.45 | 72.4 | Real estate | 0.0 | CMF strong; participation=100 (up-vol dominated) |
| TNT | Tier 2 | 53.29 | 69.86 | Unknown | 40.0 | ⚠ 7/25 distribution days; elevated risk |
| HNG | Tier 2 | 52.22 | 69.61 | Food | 27.0 | ⚠ CMF daily/weekly conflict; ADL bearish divergence |

---

## Sectors & Companies (accumulation lens)

### FACTS table — required names

| Ticker | Tier | Score | MF | fund_context_bucket | emerging | VIN distortion |
|--------|------|-------|----|---------------------|----------|---------------|
| MBB | Reject | 26.95 | 24.20 | consensus_core | No | No |
| CTG | Reject | 32.47 | 25.34 | consensus_core | No | No |
| MWG | Tier 3 | 45.04 | 49.24 | consensus_core | No | No |
| HPG | Tier 3 | 42.10 | 44.73 | consensus_core | No | No |
| GMD | Reject | 30.08 | 30.62 | consensus_core | No | No |
| VIC | Tier 3 | 39.58 | 63.41 | outside_fund_disclosure | **Yes** | **Yes** |
| VHM | Tier 3 | 42.50 | 65.59 | consensus_second_ring | No | **Yes** |
| VCB | Tier 3 | 44.55 | 57.13 | consensus_core | No | No |
| STB | Reject | 36.41 | 32.14 | consensus_second_ring | No | No |
| PNJ | — | — | — | fund_commentary_mention | — | — |
| TCB | — | — | — | fund_commentary_mention | — | — |
| BVH | — | — | — | selective_fund_bet | — | — |

*PNJ/TCB/BVH appear in priors but not in top80 or emerging outputs — likely Reject; exact scores unavailable without full CSV search.*

### Top 10 by score (from top80):

| Rank | Ticker | Tier | Score | MF | bucket | emerging |
|------|--------|------|-------|----|--------|----------|
| 1 | TOS | Tier 2 | 57.4 | 72.0 | outside | Yes |
| 2 | DVM | Tier 2 | 53.8 | 75.65 | outside | Yes |
| 3 | NRC | Tier 2 | 53.45 | 72.4 | outside | Yes |
| 4 | TNT | Tier 2 | 53.29 | 69.86 | outside | Yes |
| 5 | HNG | Tier 2 | 52.22 | 69.61 | outside | Yes |
| 6 | NVL | Tier 3 | 51.76 | 73.92 | outside | Yes |
| 7 | BFC | Tier 2 | 51.44 | 56.12 | outside | Yes |
| 8 | DSH | Tier 2 | 50.79 | 65.69 | outside | Yes |
| 9 | SJS | Tier 2 | 50.79 | 71.02 | outside | Yes |
| 10 | VJC | Tier 2 | 50.18 | 55.65 | outside | Yes |

### INTERPRETATION:

1. **Consensus vs emerging tension is extreme in this tape.** The top 13 Tier 2 names are all `outside_fund_disclosure`. Consensus-core and second-ring names (MBB, CTG, GMD, STB) are all Reject with flow scores 24–32. This signals that fund-consensed names are NOT being accumulated in April 2026 on a money-flow basis. Either funds are holding flat (not adding) or distribution is occurring. This is the clearest risk message from the scan.

2. **VIN distortion and emerging divergence within Vingroup.** VIC is simultaneously in Tier 3, flagged as VIN-distorted, *and* emerging=True. This combination is unusual: the flow (MF=63.41) is driven by up-volume and CMF daily, but weekly CMF is negative (−0.011) — a day-trader footprint, not institutional accumulation. Operators should treat VIC's emerging flag with extra skepticism.

3. **Banks absent despite FTSE catalyst.** MBB (CMF_d=0.048), CTG (CMF_d: weak), VCB (CMF_d=−0.133). The FTSE secondary EM upgrade catalyst (cited in priors) is not yet visible in money-flow signals as of April 30. If FTSE announcement timing precedes accumulation, expect banks to be the highest-conviction catch-up when flow confirms.

4. **Real estate dominates Tier 2/emerging.** NRC, SJS, KSF, VPI, NVL = 5 of top-25 emerging names are real estate sector. This diverges from the macro consensus (regime cites weak foreign flow, not real-estate-positive). Possible explanation: domestic liquidity rotation into real estate ahead of policy rate cuts. Treat as unconfirmed hypothesis — no fundamental data in scan to support.

---

## Decision Layer (research only)

### Top 3 research actions

1. **Deepen diligence on TOS and DVM** — the two cleanest Tier 2 emerging names (risk=0, multi-group flow positive). TOS (transport) has all four MF groups positive (CMF=90.8, participation=91.1). DVM (pharma) has MF=75.65 with strong CMF daily/weekly. Neither is in any fund disclosure list. Confirm: check fundamental catalysts, float, and whether this is genuine accumulation or sector rotation artefact.

2. **Monitor MBB/CTG for tier change trigger** — These are the highest-conviction fundamental names (consensus_core, FTSE beneficiary, policy_liquidity_sensitive) currently Reject. If weekly CMF turns positive and score crosses 38 (Tier 3 fragile floor), upgrade watch status. Watch: `cmf20_weekly` turning from negative to positive with `obv_slope_20` inflection.

3. **Validate real estate emerging cluster** (NRC, SJS, KSF, VPI, NVL) — 5 Tier 2-3 names from real estate have strong flow but limited sector context. Run fundamental screen on each for: debt restructuring risk, policy rate sensitivity, liquidity depth beyond ADV50. DSH and PIV have `sector=Unknown` — cross-reference against sector map for correct classification.

### Top 3 methodology risks

1. **Emerging list is permissive** — TNT (risk=40, 7/25 dist days), KSF (risk=40, 9/25 dist days), PVP (risk=87) qualify as emerging candidates despite substantial risk penalties. P1 fix pending (add `emerging_max_risk_penalty = 30`). Until fix is deployed, hand-screen any emerging name with `score_risk_penalty ≥ 30`.

2. **E1VFVN30 ETF in emerging Tier 3** — An VNINDEX-tracking ETF should not appear as an accumulation candidate. This is a code gap, not a data issue. Filter manually until P1-4 is deployed.

3. **Sector map coverage gap** — 4 Tier 2 names have `sector=Unknown`. Without sector coverage, the sector concentration check (`_sector_summary`) misses these names, potentially under-counting real estate or other sector clusters in risk assessment.

### Watchlist additions (symbols only, from scan output)

Add to human watchlist for next monitoring cycle:
- TOS (emerging Tier 2, clean flow, transport)
- DVM (emerging Tier 2, clean flow, pharma)
- NRC (emerging Tier 2, real estate, strong CMF)
- VJC (emerging Tier 2, aviation, volatility contraction flag)
- MWG (Tier 3 consensus_core, fragile floor, watch for flow recovery)
- VCB (Tier 3 consensus_core, holds MA20, watch for CMF turn)
- MBB (Reject, watch for CMF inflection — FTSE catalyst)

---

## Validation & Data Integrity

FACTS:
- `execution_leakage_check: ok = true` — no final_action, OMS, DNSE, orders in outputs
- `workflow_role: research_ranking_only` confirmed in scan JSON
- `money_flow_redundancy: status = "ok"` (from validation block in scan JSON)
- `price_unit_mode`: 100% of rows = `thousand_vnd`, `value_scale_factor = 1000.0` — no anomalies
- `unit_warning` column: empty for all sampled rows
- No lookahead: `confirm_no_lookahead(MBB, scan_date) = True`, `confirm_no_lookahead(VIC, scan_date) = True`
- Context source: `fallback:apr2026_default_priors.json` (monthly smart_money JSON for 2026-04 not found)

Limitations (unchanged from v1.1):
- **No anchored VWAP** — not implemented; not in outputs
- **No pocket pivot** — not implemented
- **No sector RS** — sector benchmark series not added; `sector_rs` column omitted
- **VIN baseline**: dual universe (full + ex-VIN) aggregate statistics not computed in single-name scan; VIN distortion flagged at name level only
- **VNINDEX proxy**: cap-weight index; may be Vingroup-skewed in 2025–2026 period, inflating RS readings for VIC/VHM

---

## Signals to Monitor Next Week

- **MBB `cmf20_weekly`**: Currently weak/negative. Any turn to positive > 0.05 with sustained `obv_slope_20 > 0` would be first tier-upgrade signal for the highest-conviction consensus name.
- **VIC weekly CMF confirmation**: Currently −0.011 (negative weekly CMF with positive daily). If weekly CMF turns positive and extension reduces below 25%, VIN distortion flag would drop — re-evaluate.
- **TOS price/volume integrity**: Leading emerging Tier 2 with risk=0. Watch for distribution days accumulating or weekly CMF deterioration that would pull it below Tier 2.
- **Emerging real estate cluster** (NRC, SJS, KSF, VPI): If rate cut signal comes from SBV, expect flow into real estate to accelerate — these names would be the early signal.
- **FTSE secondary EM announcement timing**: If upgrade announced in May, watch CTG/MBB/VCB for immediate CMF response in first 1–2 weeks post-announcement.

---

## If X Happens → Do Y (research steps only)

| Condition | Research action |
|---|---|
| MBB score crosses 38 (fragile T3 floor) | Re-run scan with `--as-of <date>`; check if CMF daily > 0 AND weekly > 0 simultaneously; update watchlist status |
| VIC weekly CMF turns > 0.05 for 2 consecutive weeks | Re-run VIN distortion check; if diagnosis drops to < 3 reasons, VIN flag clears; reassess Tier position without distortion penalty |
| Any Tier 2 emerging name shows distribution_days ≥ 6 in next scan | Downgrade to watchlist only; do not add to research priority list |
| TOS or DVM drops from Tier 2 to Tier 3 | Re-examine CMF trajectory; if MF drops below 50, remove from watchlist |
| Sector "Unknown" names (TNT, DSH, PIV, SJS) gain sector classification | Re-run sector concentration check; adjust real estate count in Tier 2 |
| E1VFVN30 appears again in emerging (pre-P1-4 fix) | Manually exclude; it is an index ETF, not an accumulation candidate |
| P1 fixes deployed (emerging_max_risk_penalty, ETF filter) | Re-run scan to get clean emerging list; compare emerging count before/after (expect ~5–8 names removed) |

---

*Sources: `outputs/scans/institutional_accumulation_2026-04-30.json`, `outputs/scans/institutional_accumulation_2026-04-30_top80.csv`, `outputs/scans/emerging_accumulation_2026-04-30.csv`, `data/smart_money/priors/apr2026_default_priors.json`. No live API data used.*
