"""Batch-aware risk review with simulated portfolio updates."""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

import pandas as pd

from src.trading.config import LiveTradingConfig, TradingConfig
from src.trading.models import (
    ManagedOrder,
    OrderProposal,
    OrderSide,
    OrderState,
    PortfolioState,
    Position,
    RiskDecision,
    RiskVerdict,
)
from src.trading.oms.idempotency import IdempotencyStore
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.trading.oms.order_manager import OrderManager

from src.trading.oms.order_manager import portfolio_from_broker
from src.trading.oms.state_machine import transition
from src.trading.risk.engine import RiskContext, RiskEngine
from src.trading.util.timeutil import utc_now_iso


def _sort_proposals(proposals: List[OrderProposal]) -> List[OrderProposal]:
    return sorted(
        proposals,
        key=lambda p: (p.signal.symbol, p.signal.metadata.get("tier", ""), p.signal.side),
    )


def apply_verdict_to_sim(portfolio: PortfolioState, proposal: OrderProposal, verdict: RiskVerdict) -> None:
    if verdict.decision == RiskDecision.BLOCK:
        return
    if verdict.decision == RiskDecision.MANUAL_REVIEW:
        return  # do not consume cash until approved
    sig = proposal.signal
    val = proposal.order_value_vnd
    portfolio.daily_orders += 1
    if sig.side.upper() == OrderSide.BUY.value:
        portfolio.cash_vnd -= val
        pm = portfolio.position_map()
        existing = pm.get(sig.symbol)
        if existing:
            new_qty = existing.quantity + sig.quantity
            new_mv = existing.market_value_vnd + val
            existing.quantity = new_qty
            existing.market_value_vnd = new_mv
            existing.avg_price = new_mv / new_qty if new_qty else existing.avg_price
        else:
            portfolio.positions.append(
                Position(
                    symbol=sig.symbol,
                    quantity=sig.quantity,
                    avg_price=sig.intended_price,
                    market_value_vnd=val,
                )
            )
            portfolio.new_positions_today += 1
    elif sig.side.upper() == OrderSide.SELL.value:
        portfolio.cash_vnd += val
        pm = portfolio.position_map()
        if sig.symbol in pm:
            p = pm[sig.symbol]
            p.quantity = max(0, p.quantity - sig.quantity)
            p.market_value_vnd = max(0.0, p.market_value_vnd - val)


class BatchRiskReviewer:
    def __init__(self, config: LiveTradingConfig, om: "OrderManager"):
        self.config = config
        self.om = om
        self.engine = RiskEngine(config)

    def risk_review_batch(
        self,
        asof_date: str,
        proposals: List[OrderProposal],
        extra_ctx: Optional[Dict[str, Any]] = None,
    ) -> List[ManagedOrder]:
        extra_ctx = extra_ctx or {}
        base_portfolio = portfolio_from_broker(self.om.broker, asof_date)
        base_portfolio.open_slots = len(base_portfolio.positions)
        sim = copy.deepcopy(base_portfolio)
        pending = list(self.om.store.list_keys())
        results: List[ManagedOrder] = []
        risk_rows: List[Dict[str, Any]] = []

        for prop in _sort_proposals(proposals):
            prop.nav_vnd = sim.nav_vnd
            if self.om.store.exists(prop.idempotency_key):
                existing = self.om.store.load(prop.idempotency_key)
                if existing:
                    results.append(existing)
                continue

            mo = ManagedOrder(proposal=prop, state=OrderState.PENDING_SIGNAL)
            ctx = RiskContext(
                portfolio=sim,
                pending_idempotency_keys=pending,
            )
            verdict = self.engine.evaluate(prop, ctx, live_config=self.config, extra=extra_ctx)
            prop.risk_verdict = verdict
            mo.risk_verdict = verdict

            if verdict.decision == RiskDecision.PASS:
                mo.state = transition(mo.state, OrderState.APPROVED_BY_RISK)
                mo.state = transition(mo.state, OrderState.ORDER_READY)
                apply_verdict_to_sim(sim, prop, verdict)
            elif verdict.decision == RiskDecision.MANUAL_REVIEW:
                mo.state = transition(mo.state, OrderState.APPROVED_BY_RISK)
                mo.error_message = "manual_review_required"
            else:
                mo.state = transition(mo.state, OrderState.REJECTED_BY_RISK)

            mo.updated_at = utc_now_iso()
            self.om.store.save(mo)
            pending.append(prop.idempotency_key)
            results.append(mo)
            risk_rows.append({
                "idempotency_key": prop.idempotency_key,
                "symbol": prop.signal.symbol,
                "decision": verdict.decision.value,
                "reasons": "; ".join(verdict.reasons),
                "rule_ids": "|".join(verdict.rule_ids),
            })

        if risk_rows:
            path = self.config.risk_check_path(asof_date)
            path.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(risk_rows).to_csv(path, index=False)
        return results
