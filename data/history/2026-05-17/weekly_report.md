# Weekly Macro/Policy/Decision Packet — as-of 2026-05-17
_Report age: 2 day(s); market snapshot date: 2026-05-17_

**Data confidence:** High | missing: — | not_due_yet: — | warnings: report_asof_weekend_but_dxy_same_calendar_day_suspicious
**Market level source:** VNINDEX | **DistDays proxy:** VN30
## Global Macro + Fed
- FACTS (levels) + source tag:
  - UST 2Y: 4.0 — FRED DGS2, **value_date**=2026-05-14 (fred_dgs_daily_observation; not labeled as broker session close)
  - UST 10Y: 4.47 — FRED DGS10, **value_date**=2026-05-14 (fred_dgs_daily_observation)
  - **DXY reconstructed (FRED H.10, ICE-style):** 97.9231 (value_date=2026-05-08)
  - **DXY third-party proxy (Yahoo DX-Y.NYB):** None (value_date=2026-05-17) — cross-check, not licensed ICE; source=Yahoo Finance DX-Y.NYB
  - **DXY ICE official (env/manual only):** None (value_date=None)
  - **Legacy `global.dxy` (WoW driver):** 97.9231 — reconstructed if available, else third-party
  - **USD broad (FRED DTWEXBGS):** 118.0392 (value_date=2026-05-08)
  - CPI YoY: 3.81 — source=bls, **reference_month**=2026-04, value_date=2026-04
  - Nonfarm payroll **MoM change (persons):** 115000 (PAYEMS level date=2026-04-01)
  - Nonfarm payroll **level (thousands):** 158736.0 (prior level date=2026-03-01)
  - Legacy field `nfp` (intentionally null): None
- WHAT CHANGED (WoW):
  - UST 2Y Δ: 0.2400000000000002
  - UST 10Y Δ: 0.20000000000000018
  - Primary DXY Δ (legacy `dxy`): -0.1968999999999994
  - USD broad (DTWEXBGS) Δ: None
  - Payroll MoM Δ persons: None
- INTERPRETATION: TBD when data is filled.
  - _Note:_ `ust_2y` value_date (2026-05-14) is **before** report as-of (2026-05-17).
  - _Note:_ `ust_10y` value_date (2026-05-14) is **before** report as-of (2026-05-17).
  - _Note:_ `usd_broad_index_fred` value_date (2026-05-08) is **before** report as-of (2026-05-17).
  - _Note:_ `nonfarm_payroll_level_thousands` value_date (2026-04-01) is **before** report as-of (2026-05-17).
  - _Note:_ `nonfarm_payroll_change_persons` value_date (2026-04-01) is **before** report as-of (2026-05-17).
  - _Note:_ `dxy_reconstructed` value_date (2026-05-08) is **before** report as-of (2026-05-17).

## Vietnam Policy + Liquidity
- FACTS (levels):
  - OMO net: 4000 (verification=parsed, source=sbv, detail=SBV nghiệp vụ thị trường mở (HTML scrape))
  - Interbank ON: 6.05
  - Credit growth YoY: 12.5
  - **SBV reference USD/VND:** 25131
- WHAT CHANGED (WoW):
  - OMO net Δ: -6000
  - Interbank ON Δ: 1.8099999999999996
  - Credit growth YoY Δ: 0.40000000000000036
- TRANSMISSION (template): rates → credit → FX → sentiment (fill next).

## Vietnam Policy
- FACTS:
  - None reported this week.

## Research Intake This Week
### Company
  regime=B global_liquidity=tight vn_liquidity=easing (regime_state.json asof 2026-05-10)
  allocation gross_exposure=0.55 cash_weight=0.45 (allocation_plan.json asof 2026-05-10)
  vnindex_level=1915.37 dist_days_20=3 dist_risk=Elevated (weekly_report.md asof 2026-05-10)
  scan_asof=2026-05-15 (panel date); scan_generated=2026-05-16
  Research engine = A3_DP EMA-cloud daily scan (B_cloud20_100, B_cloud21_55, C_GK_regime strategies).
  No published IC time series in repo — ic_estimates left null.
  Top signals 2026-05-16 (all skipped — B_cloud20_100 book full 20/20):
  BMP +5.3%, PVS +4.2%, QNS +4.0%, TCB +2.6%, SHI +1.9%, GSP +1.2%, KOS +1.1%, KSV +0.6%
  B_cloud21_55 has 20 free slots; fills today: ILS, TRC, VIX, QNS, ASM.
  C_GK_regime fills: PHR, NDN, TRC.
  Convergence (2+ strategies today): QNS (B20100+B2155), TRC (B2155+CGK).
  Near-entry preferred_pullback_zone (A3): HPG ideal_pullback -4.5% vs signal; VPB, KSV, MWG, VJC.
  Order pipeline (A3_DP): HPG BUY T1, price 24500, qty 6804, requires_manual_review=true, breadth_zone=defense.


## Sectors & Companies (Earnings / Broker Notes)
- FACTS:
  - None reported this week.

- MARKET (levels): vnindex_level=1921.6, vn30_level=2050.58, distribution_days_rolling_20=3 (proxy: VN30)
- **Distribution (LB=25, refined):** VN30=3, HNX=3, UPCOM=4 → Composite=Elevated (leader=VN30)
- Breadth: VN30 trend_ok(>MA20)=False | HNX close=257.42, trend_ok(>MA20)=True | UPCOM close=126.61, trend_ok(>MA20)=False
- WHAT CHANGED (WoW):
  - VNIndex Δ: 225.3599999999999, Dist days Δ: -1

## Regime Engine
- Regime: STATE B
- Regime shift: None
- Inputs: global_liquidity=tight, vn_liquidity=easing
- **Suggested Regime (advisory):** B (from dist composite, breadth, MA trend)
- **Current Regime:** B
- **Mismatch:** No

## Probability + Allocation
- P(Fed cut within 3m): 0.35000000000000003
- P(VN tightening within 1m): 0.25
- P(VNIndex breakout within 1m): 0.5
- Allocation: {'gross_exposure': 0.55, 'cash_weight': 0.45, 'constraints': {'max_single_position': 0.12, 'max_sector_weight': 0.3, 'max_portfolio_drawdown': 0.08, 'default_stop_loss': 0.07}}

## VNINDEX downtrend probability (v2)
- **FACTS:** source=FireAnt VNINDEX (index OHLCV), method=`scripts/run_vnindex_downtrend_v2.py`, values=shrinkage-adjusted analog probabilities (not broker/regime-engine outputs).
- Model as-of: 2026-05-17 | mode=T10 | regime band: Yellow
- **P(confirmed downtrend 20d):** 9.9% (k=10, adjusted)
- **P(outcome_B / MA50 breach proxy):** 44.7% (k=10, adjusted)
- **P(trend_break 20d):** 41.9% (k=10, adjusted)
- **INTERPRETATION:** Confirmed downtrend = structural 20d breakdown analog; outcome_B = close below MA50 proxy. Low sample → wide CI (see reports/latest/vnindex_downtrend_probability_v2.md).

## Portfolio Structure (Hybrid)
- Core allowed: True
- Bucket allocation: {'core': 0.33, 'swing': 0.22, 'cash': 0.45, 'note': 'Core enabled'}

## Current book (Excel-derived)
- **FACTS:** Positions below come from `data/raw/current_positions_derived.json` (ingested from `D:\V\1. Current Trade Sys\CP\Port Analysis\Analysis - FQuery - 20260519v1.xlsx`) — not a FireAnt or broker statement; qty = shares from Open!X; avg_cost = abs(Open!W).
- **Open positions:** 14
  - **BID:** qty 18000, avg cost 42.091 VND/sh | sector/tag: Ngân hàng
  - **DPR:** qty 9200, avg cost 43.175 VND/sh | sector/tag: Rubber
  - **DXG:** qty 40000, avg cost 14.608 VND/sh | sector/tag: BDS
  - **GVR:** qty 19000, avg cost 36.958 VND/sh | sector/tag: Rubber
  - **HCM:** qty 20000, avg cost 28.337 VND/sh | sector/tag: CTCK
  - **HDB:** qty 16000, avg cost 27.329 VND/sh | sector/tag: Ngân hàng
  - **MSB:** qty 25000, avg cost 13.200 VND/sh | sector/tag: Ngân hàng
  - **NVL:** qty 30000, avg cost 16.916 VND/sh | sector/tag: BDS
  - **PDR:** qty 25000, avg cost 16.580 VND/sh | sector/tag: BDS
  - **PHR:** qty 7500, avg cost 66.446 VND/sh | sector/tag: Rubber
  - **PVS:** qty 10000, avg cost 41.230 VND/sh | sector/tag: Energy / DTC
  - **STB:** qty 10000, avg cost 68.950 VND/sh | sector/tag: Ngân hàng
  - **TCX:** qty 2500, avg cost 51.577 VND/sh | sector/tag: CTCK
  - **VPB:** qty 3500, avg cost 28.528 VND/sh | sector/tag: Ngân hàng

## Decision Layer
- Top 3 actions:
  1) Maintain mid exposure per band (gross=0.55, cash=0.45).
  2) No new buys unless confirmed pocket pivot / reclaim; trim weak names.
  3) Scale exposure only if breakout attempts succeed AND distribution-day risk is not rising.
- Top 3 risks:
  1) Regime B mismatch: global tight can override VN easing quickly (external shock sensitivity).
  2) Data gaps → narrative bias (probabilities become unreliable).
  3) Market fragility elevated (distribution days risk=Elevated) → higher failure rate of breakouts.
- Watchlist updates (regime-fit + risk posture):
  - Posture: Defensive / Reduce new buys
  - Tickers: SSI, VCI, SHS, TCX, MBB, STB, SHB, DCM, PVD, PC1, DXG, VSC, GMD, MWG
  - MVP: no per-ticker scoring yet. Add technical/fundamental signals later.
  - SSI: regime_fit=B, total_score=None
  - VCI: regime_fit=B, total_score=None
  - SHS: regime_fit=B, total_score=None
  - TCX: regime_fit=B, total_score=None
  - MBB: regime_fit=B, total_score=None
  - STB: regime_fit=B, total_score=None
  - SHB: regime_fit=B, total_score=None
  - DCM: regime_fit=B, total_score=None
  - PVD: regime_fit=B, total_score=None
  - PC1: regime_fit=B, total_score=None
  - DXG: regime_fit=B, total_score=None
  - VSC: regime_fit=B, total_score=None
  - GMD: regime_fit=B, total_score=None
  - MWG: regime_fit=B, total_score=None

### Backtest edge (knowledge)
- No backtest records available. Add backtest knowledge (e.g. data/raw/backtest_*.json or knowledge layer) to populate.

## Watchlist Updates
- Top candidates (by total score):
  - MBB: total=3.5 (F=4, T=3, R=4) | placeholder
  - SSI: total=3.0 (F=3, T=3, R=3) | placeholder

## Execution & Monitoring
- Market risk flag (dist days): {'distribution_days_rolling_20': 3, 'distribution_days': {'vn30': 3, 'hnx': 3, 'upcom': 4}, 'dist_risk_composite': 'Elevated', 'dist_proxy_symbol': 'VN30', 'risk_flag': 'Elevated', 'force_reduce_gross': False}
- Hormuz energy shock layer: ENERGY_SHOCK_LOW | mode=headline | vn_inflation=low | vn_supply=low | checklist=0/6(unknown)

## Execution — Sell/Trim Signals (MVP)
- STB: HOLD | No violation (tier=None)
- HDB: HOLD | No violation (tier=1)
- MSB: HOLD | No violation (tier=1)
- BID: HOLD | No violation (tier=None)
- VPB: HOLD | No violation (tier=1)
- HCM: HOLD | No violation (tier=1)
- TCX: HOLD | No violation (tier=None)
- DXG: HOLD | No violation (tier=None)
- PDR: HOLD | No violation (tier=None)
- NVL: SELL / EXIT | Day-2 confirmation breach (tier=1)
- GVR: HOLD | No violation (tier=1)
- PHR: HOLD | No violation (tier=None)
- DPR: HOLD | No violation (tier=None)
- PVS: HOLD | No violation (tier=1)

## Portfolio Health
- **% positions below MA20:** 7.1% (1/14)
- **% positions with sell/trim active:** 7.1% (1/14)
- **Avg R multiple (open):** — (add r_multiple in tech_status)
- **Risk concentration by sector:**
  - Banking: 35.7% (5)
  - Rubber: 21.4% (3)
  - —: 14.3% (2)
  - Real estate: 14.3% (2)
  - Securities: 7.1% (1)
  - Oil & Gas: 7.1% (1)

## Council Process Status
- council_output status: stale_meeting_id
- mechanically_executable: True
- chair_decision logged: True
- Next step: run council prompts and save `data/decision/council_output.json`, then re-run weekly.

## Open questions
- WoW Vietnam liquidity
- Dist days trend
- Council execution

## Signals to monitor next week
- Update: UST 2Y/10Y (FRED observation dates), **DXY reconstructed** / third-party proxy, USD broad (DTWEXBGS), CPI (BLS ref month), payroll **MoM change**
- VN: OMO net (SBV/TBNN fallback provenance), interbank ON, credit growth trend, SBV reference USD/VND
- Market: distribution days rolling-20, breadth, failed breakouts

## If X happens → do Y
- If regime shifts to STATE C (tight+tight) → reduce gross, raise cash, tighten stops.
- If distribution days cluster + failed breakout → cut laggards, only hold leaders.
- If policy tailwind + earnings confirm for a sector → overweight with risk limits.