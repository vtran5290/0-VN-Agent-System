# Broker Adapter Guide

Canonical brokers: [`src/trading/brokers/`](../../src/trading/brokers/)

| Adapter | Status |
|---------|--------|
| `PaperBroker` | Working — simulated fills |
| `DNSEBroker` | Placeholder — read-only; live orders blocked |

## Before submit

1. Pre-submit re-risk (cash, kill switch, reconciliation)
2. `get_trade_capacity(symbol, price, side)` — reject if `max_quantity < requested`
3. Triple gate for DNSE live (future)

## Credentials

Use `.env` only (never commit). See `.env.example` for `DNSE_*` placeholders.
