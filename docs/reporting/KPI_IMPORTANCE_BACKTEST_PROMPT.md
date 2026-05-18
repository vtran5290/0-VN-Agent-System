# KPI importance backtest (research prompt)

**Objective:** Rank weekly KPIs by historical association with Vietnam equity outcomes to set `importance_tier` in `metric_registry.py` (Core / Secondary / Appendix).

## Dependent variables

- VNINDEX forward return: 1W, 1M, 3M
- VNINDEX max drawdown: 1M, 3M
- Distribution cluster probability (dist days ≥ threshold)
- Breakout success rate (define from existing research outputs)

## Candidate features

Global: UST2Y/10Y level & Δ, DXY level & Δ, USDCNH, Brent, VIX, Fed cut prob 3M/6M  
VN liquidity: interbank ON, OMO stock, OMO net 7D/20D, credit growth YoY, USD/VND ref & premium  
Market: turnover, breadth (% above MA20), dist days 20, foreign flow, P/E, P/B  
A3: pct_cloud_bull_a3, breadth_zone

## Methods

1. Pearson / Spearman correlation (levels and changes)  
2. Rank IC by week  
3. Lead/lag (1–4 weeks)  
4. Regime-conditioned (STATE A–E or cloud bull/bear)  
5. Simple walk-forward: top features by |IC| stability

## Output table

| feature | horizon | IC | sign | stable? | recommended_tier |

## Implementation note

Script stub: `scripts/research/kpi_importance_backtest.py` (create when panel history CSV/parquet is wired). Do not block weekly HTML on this research.
