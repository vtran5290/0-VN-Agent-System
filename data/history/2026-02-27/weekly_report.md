# Weekly Macro/Policy/Decision Packet — 2026-02-27

**Data confidence:** High | missing: None
**Market level source:** VNINDEX | **DistDays proxy:** VN30
## Global Macro + Fed
- FACTS (levels):
  - UST 2Y: 3.42
  - UST 10Y: 4.02
  - DXY: 117.9917
  - CPI YoY: None
  - NFP: 158627.0
- WHAT CHANGED (WoW):
  - UST 2Y Δ: 0.0
  - UST 10Y Δ: 0.0
  - DXY Δ: 0.0
- INTERPRETATION: TBD when data is filled.

## Vietnam Policy + Liquidity
- FACTS (levels):
  - OMO net: 171395
  - Interbank ON: 8.5
  - Credit growth YoY: 15
  - USD/VND: 23864
- WHAT CHANGED (WoW):
  - OMO net Δ: None
  - Interbank ON Δ: None
  - Credit growth YoY Δ: None
- TRANSMISSION (template): rates → credit → FX → sentiment (fill next).

## Vietnam Policy
- FACTS:
  - 2026-02-01 | Policy referenced in manager commentary | Several fund manager commentaries referenced domestic policy themes and SOE-related measures; details vary by report.

## Research Intake This Week
### Macro
  - Funds broadly maintain risk-on posture in narrative.
  - No numeric macro datapoints extracted in this pack (left null).


## Sectors & Companies (Earnings / Broker Notes)
- FACTS:
  - None reported this week.

- MARKET (levels): vnindex_level=7600.0, vn30_level=2061.75, distribution_days_rolling_20=6 (proxy: VN30)
- **Distribution (LB=25, refined):** VN30=6, HNX=4, UPCOM=5 → Composite=High (leader=VN30)
- **Action bias:** No new buys; only manage risk/exits; raise cash into strength.
- Breadth: VN30 trend_ok(>MA20)=True | HNX close=262.82, trend_ok(>MA20)=True | UPCOM close=129.75, trend_ok(>MA20)=True
- WHAT CHANGED (WoW):
  - VNIndex Δ: 0.0, Dist days Δ: None

## Regime Engine
- Regime: STATE B
- Regime shift: None
- Inputs: global_liquidity=tight, vn_liquidity=easing
- **Suggested Regime (advisory):** C (from dist composite, breadth, MA trend)
- **Current Regime:** B
- **Mismatch:** Yes

## Probability + Allocation
- P(Fed cut within 3m): 0.4
- P(VN tightening within 1m): 0.2
- P(VNIndex breakout within 1m): 0.55
- Allocation: {'gross_exposure': 0.55, 'cash_weight': 0.45, 'constraints': {'max_single_position': 0.12, 'max_sector_weight': 0.3, 'max_portfolio_drawdown': 0.08, 'default_stop_loss': 0.07}, 'gross_exposure_override': 0.4, 'cash_weight_override': 0.6, 'override_reason': 'DistDays>=6 → High risk → cap gross exposure', 'no_new_buys': True}
- Override: gross=0.4, cash=0.6 — DistDays>=6 → High risk → cap gross exposure
- **no_new_buys: True** — only manage risk / exits / trims.

## Portfolio Structure (Hybrid)
- Core allowed: False
- Bucket allocation: {'core': 0.0, 'swing': 0.4, 'cash': 0.6, 'note': 'Core disabled due to regime/risk'}

## Decision Layer
- Top 3 actions:
  1) Only manage risk / exits / trims; no new buys (DistDays>=6 → High).
  2) Trim weak names; raise cash per override. Core disabled.
  3) Watchlist: monitor leaders only; no adds unless pocket pivot + dist-days drop.
- Top 3 risks:
  1) Regime B mismatch: global tight can override VN easing quickly (external shock sensitivity).
  2) Data gaps → narrative bias (probabilities become unreliable).
  3) Market fragility elevated (distribution days risk=High) → higher failure rate of breakouts.
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
- No backtest records available.

## Watchlist Updates
- Top candidates (by total score):
  - MBB: total=3.5 (F=4, T=3, R=4) | placeholder
  - SSI: total=3.0 (F=3, T=3, R=3) | placeholder

## Execution & Monitoring
- Market risk flag (dist days): {'distribution_days_rolling_20': 6, 'distribution_days': {'vn30': 6, 'hnx': 4, 'upcom': 5}, 'dist_risk_composite': 'High', 'dist_proxy_symbol': 'VN30', 'risk_flag': 'High', 'force_reduce_gross': True}

## Execution — Sell/Trim Signals (MVP)
- MBB: HOLD | No violation (tier=3)
- SSI: TRIM / TIGHTEN STOP | Day-1 close below key MA (tier=2)

## Portfolio Health
- **% positions below MA20:** 50.0% (1/2)
- **% positions with sell/trim active:** 50.0% (1/2)
- **Avg R multiple (open):** — (add r_multiple in tech_status)
- **Risk concentration by sector:**
  - Banking: 50.0% (1)
  - Securities: 50.0% (1)

## Council Process Status
- council_output status: stale_meeting_id
- mechanically_executable: True
- chair_decision logged: True
- Next step: run council prompts and save `data/decision/council_output.json`, then re-run weekly.

## Signals to monitor next week
- Update: UST 2Y/10Y, DXY, CPI/NFP surprises
- VN: OMO net, interbank ON, credit growth trend, USD/VND
- Market: distribution days rolling-20, breadth, failed breakouts

## If X happens → do Y
- If regime shifts to STATE C (tight+tight) → reduce gross, raise cash, tighten stops.
- If distribution days cluster + failed breakout → cut laggards, only hold leaders.
- If policy tailwind + earnings confirm for a sector → overweight with risk limits.