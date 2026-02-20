# Weekly Macro/Policy/Decision Packet — 2026-02-20

## Global Macro + Fed
- FACTS (levels):
  - UST 2Y: None
  - UST 10Y: None
  - DXY: None
  - CPI YoY: None
  - NFP: None
- WHAT CHANGED (WoW):
  - UST 2Y Δ: None
  - UST 10Y Δ: None
  - DXY Δ: None
- INTERPRETATION: TBD when data is filled.

## Vietnam Policy + Liquidity
- FACTS (levels):
  - OMO net: None
  - Interbank ON: None
  - Credit growth YoY: None
  - USD/VND: None
- WHAT CHANGED (WoW):
  - OMO net Δ: None
  - Interbank ON Δ: None
  - Credit growth YoY Δ: None
- TRANSMISSION (template): rates → credit → FX → sentiment (fill next).

## Vietnam Policy
- FACTS:
  - None | Policy item 1 | Unknown (fill later)
- INTERPRETATION (template):
  - Transmission: rates → credit → FX → sentiment
  - Likely winners/losers: (fill once facts confirmed)

## Sectors & Companies (Earnings / Broker Notes)
- FACTS:
  - MBB | 2025Q4 | Unknown (fill later)
  - Vietcap | PC1 | Unknown (fill later)
- INTERPRETATION (template):
  - Earnings momentum / revision risk: (fill)
  - Catalysts / risks: (fill)

- MARKET (levels): vnindex_level, distribution_days_rolling_20 — see raw inputs.
- WHAT CHANGED (WoW):
  - VNIndex Δ: None, Dist days Δ: None

## Regime Engine
- Regime: STATE B
- Regime shift: None
- Inputs: global_liquidity=tight, vn_liquidity=easing

## Probability + Allocation
- P(Fed cut within 3m): 0.4
- P(VN tightening within 1m): 0.2
- P(VNIndex breakout within 1m): 0.55
- Allocation: {'gross_exposure': 0.55, 'cash_weight': 0.45, 'constraints': {'max_single_position': 0.12, 'max_sector_weight': 0.3, 'max_portfolio_drawdown': 0.08, 'default_stop_loss': 0.07}}

## Decision Layer
- Top 3 actions:
  1) Maintain mid exposure per band (gross=0.55, cash=0.45).
  2) Favor leaders with earnings clarity; avoid adding to laggards/high-beta breakouts without confirmation.
  3) Scale exposure only if breakout attempts succeed AND distribution-day risk is not rising.
- Top 3 risks:
  1) Regime B mismatch: global tight can override VN easing quickly (external shock sensitivity).
  2) Data gaps → narrative bias (probabilities become unreliable).
  3) Sudden liquidity shock (global or VN) causing gap-down risk.
- Watchlist updates (regime-fit + risk posture):
  - Posture: Selective / Leader-only
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

## Watchlist Updates
- Top candidates (by total score):
  - MBB: total=3.5 (F=4, T=3, R=4) | placeholder
  - SSI: total=3.0 (F=3, T=3, R=3) | placeholder

## Execution & Monitoring
- Market risk flag (dist days): {'distribution_days_rolling_20': None, 'risk_flag': 'Unknown', 'force_reduce_gross': False}

## Execution — Sell/Trim Signals (MVP)
- MBB: HOLD | No violation (tier=3)
- SSI: TRIM / TIGHTEN STOP | Day-1 close below key MA (tier=2)

## Signals to monitor next week
- Update: UST 2Y/10Y, DXY, CPI/NFP surprises
- VN: OMO net, interbank ON, credit growth trend, USD/VND
- Market: distribution days rolling-20, breadth, failed breakouts

## If X happens → do Y
- If regime shifts to STATE C (tight+tight) → reduce gross, raise cash, tighten stops.
- If distribution days cluster + failed breakout → cut laggards, only hold leaders.
- If policy tailwind + earnings confirm for a sector → overweight with risk limits.