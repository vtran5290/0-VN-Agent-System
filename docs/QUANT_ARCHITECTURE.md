# Quant Trading System — Architecture Blueprint

**Status:** Design phase — local paper-trading validated, live deployment pending.  
**Data sovereignty:** All alpha computation runs locally. External MCPs used only for macro context and chart display.

---

## 1. MCP Ecosystem Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Claude Code (Orchestrator)                │
└─────┬───────────────┬───────────────┬──────────────┬────────────┘
      │               │               │              │
      ▼               ▼               ▼              ▼
┌──────────┐  ┌────────────┐  ┌────────────┐  ┌──────────────┐
│  LOCAL   │  │  FRED MCP  │  │TradingView │  │ Broker MCP   │
│  QUANT   │  │  (macro)   │  │   (charts) │  │ (future)     │
│  ENGINE  │  │            │  │            │  │              │
│ 4 tools  │  │ yield curve│  │ live prices│  │ order mgmt   │
│ (stdio)  │  │ CPI/PPI    │  │ indicators │  │ VPS broker   │
└──────────┘  └────────────┘  └────────────┘  └──────────────┘
      │
      └── reads SSOT locally (no network, no token bloat)
          data/fireant_ssot/*.parquet
          data/master/sector_map.csv
```

**Token cost principle:** The local engine does all math and returns < 400-char summaries. 
External MCPs are called only when Claude needs live data that isn't in the SSOT.

---

## 2. Local Quant Engine — Tool Reference

| Tool | Purpose | Returns |
|------|---------|---------|
| `screen_technical_setups(ticker)` | Wyckoff phase, pocket pivot, tight closes, volume dry-up | Phase + signals string |
| `run_isolated_backtest(strategy, params)` | Walk-forward IS estimate for 3 strategies | Stats summary |
| `evaluate_fundamental_moat(ticker)` | Rev CAGR, EPS stability, gross margin | Moat verdict |
| `enforce_portfolio_constraints(ticker, size%)` | Hard risk limit checker | APPROVED or BLOCKED |

### Strategies available in `run_isolated_backtest`

| Strategy name | Signal | Horizon |
|--------------|--------|---------|
| `mean_reversion_252d` | Inverse 1-year laggards (v3 validated: OOS IC +0.24, ICIR 1.25) | 200–250d |
| `ma_crossover` | MA50 > MA200 alignment breakout | 60–100d |
| `breakout_52w` | Distance from 52-week high | 25–50d |

---

## 3. Portfolio Management Layer (Phase 2)

### 3a. State File Schema

`data/trading/paper_broker_state.json`:
```json
{
  "equity_vnd": 1000000000,
  "cash_vnd": 400000000,
  "nav_history": [
    {"date": "2026-05-01", "nav": 980000000}
  ],
  "positions": {
    "HPG": {
      "qty": 1000,
      "avg_cost_vnd": 24500000,
      "weight_pct": 4.5,
      "entry_date": "2026-04-15",
      "strategy": "mean_reversion_252d",
      "stop_loss_pct": 8.0
    }
  },
  "drawdown_peak_vnd": 1050000000,
  "max_drawdown_pct": -5.2,
  "regime": "Accumulation"
}
```

### 3b. Portfolio Risk Controls (enforced by Council Enforcer tool)

| Rule | Limit | Rationale |
|------|-------|-----------|
| Max single position | 8% of equity | Single-stock blowup protection |
| Max sector concentration | 30% of equity | Sector rotation risk |
| Max total positions | 20 | Concentration vs diversification |
| Max market impact | 5% of ADV50 | Slippage / liquidity protection |
| Max drawdown trigger | −15% portfolio | Auto-shutdown threshold |
| Regime gate | No new longs in Expansion | v3 finding: IC fails in bull regime |

### 3c. Drawdown Monitoring

The portfolio engine tracks:
- **Peak NAV** — updated daily when NAV > peak
- **Current drawdown** — `(NAV / peak - 1) × 100`
- **Max drawdown** — rolling worst from peak
- **Position-level drawdown** — individual position vs avg cost

**Auto-shutdown rule:** If portfolio drawdown < −15%, the agent stops placing new orders and alerts Claude for manual review.

---

## 4. Automated Trading Agent — Orchestration Loop

The agent runs as a scheduled Claude Code sub-agent (or cron task). It follows this deterministic decision tree on each cycle:

```
START
  │
  ├─1─ [FRED MCP] get_macro_regime()
  │     → Yield curve slope, CPI momentum, USD strength
  │     → Map to: RISK_ON / RISK_OFF / NEUTRAL
  │
  ├─2─ [LOCAL QUANT] Determine VNIndex regime
  │     → Expansion / Accumulation / Warning / Contraction
  │     → If Expansion + RISK_OFF → SKIP (no new longs)
  │
  ├─3─ [LOCAL QUANT] screen_technical_setups(candidates)
  │     → Candidates = ADV50 ≥ 2B + in allowed regime
  │     → Filter: PocketPivot OR TightCloses + VolDryUp
  │
  ├─4─ [LOCAL QUANT] evaluate_fundamental_moat(filtered)
  │     → Only consider Strong or Moderate moat
  │
  ├─5─ [LOCAL QUANT] run_isolated_backtest("mean_reversion_252d", params)
  │     → Rank filtered candidates by score
  │     → Take top N within position limits
  │
  ├─6─ [LOCAL QUANT] enforce_portfolio_constraints(ticker, proposed_size)
  │     → BLOCKED → skip to next candidate
  │     → APPROVED → proceed to order
  │
  ├─7─ [BROKER MCP] place_order(ticker, qty, limit_price)
  │     → Limit order at last close + 0.5% (avoid chasing)
  │     → Set stop-loss at entry − 8%
  │
  └─8─ Write state → paper_broker_state.json
       Log order → data/trading/orders/
       Update NAV and drawdown metrics
```

### Agent Cadence

| Trigger | Action |
|---------|--------|
| Daily 09:00 (market open) | Full scan → new entry candidates |
| Daily 15:00 (market close) | Mark-to-market positions, check stops |
| Weekly Sunday | Regime re-evaluation, rebalance if quarterly |
| Any time drawdown < −8% on a position | Alert Claude, review stop |

---

## 5. Broker MCP (Phase 3 — Future)

The broker layer will be a thin stdio MCP wrapping the VPS Securities API (or paper broker stub). It will expose:

| Tool | Function |
|------|----------|
| `get_account_balance()` | Real-time equity and cash |
| `place_limit_order(ticker, side, qty, price)` | Submit order with T+2 settlement |
| `get_open_orders()` | List pending orders |
| `cancel_order(order_id)` | Cancel pending order |
| `get_positions()` | Mark-to-market position list |

**Security model:**
- Broker MCP runs as a separate process with narrow API key scope (no withdrawal)
- All orders require the Council Enforcer approval first (tool call is logged)
- Max order value hard-coded in broker MCP config (second line of defense)

---

## 6. Data Flow Diagram

```
External (controlled, pull-only)          Local (SSOT, zero egress)
─────────────────────────────────         ──────────────────────────────
FireAnt API → scripts/fetch_*.py ────►  data/fireant_ssot/*.parquet
                                                    │
FRED API → [fred-mcp-server] ──────────────────────┤ (macro context only)
                                                    │
TradingView → [tradingview-mcp] ────────────────────┤ (chart display only)
                                                    │
                                         mcp_quant_engine.py
                                                    │
                                         ┌──────────▼──────────┐
                                         │  Claude Code Agent   │
                                         │  (orchestrates all)  │
                                         └──────────────────────┘
                                                    │
                                         data/trading/
                                           paper_broker_state.json
                                           orders/*.json
                                           reports/*.md
```

---

## 7. Governance & Risk Checklist

Before enabling live trading (not paper):

- [ ] OOS IC ≥ 0.25 maintained for ≥ 6 rolling months
- [ ] Paper trading Sharpe > 0.5 over ≥ 3 months  
- [ ] Council Enforcer tool tested against ≥ 50 edge cases
- [ ] Broker MCP tested in sandbox with ≥ 30 paper orders
- [ ] Auto-shutdown at −15% drawdown confirmed in simulation
- [ ] Manual kill switch documented and tested
- [ ] Regulatory check: VPS/DNSE API ToS reviewed for algo trading
