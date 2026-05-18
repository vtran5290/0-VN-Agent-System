"""Batch-aware risk review with simulated portfolio updates."""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

from src.trading.config import LiveTradingConfig
from src.trading.models import (
    ManagedOrder,
    OrderProposal,
    OrderSide,
    OrderState,
    PortfolioState,
    Position,
    RiskDecision,
    RiskVerdict,
    trade_intent_key,
)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.trading.oms.order_manager import OrderManager

from src.trading.oms.order_manager import portfolio_from_broker
from src.trading.oms.state_machine import transition
from src.trading.risk.engine import RiskContext, RiskEngine
from src.trading.util.timeutil import utc_now_iso

_ACTIVE_STATES = {
    OrderState.APPROVED_BY_RISK,
    OrderState.ORDER_READY,
    OrderState.ORDER_SUBMITTED,
    OrderState.PARTIALLY_FILLED,
    OrderState.FILLED,
}


def _proposal_order(proposals: List[OrderProposal]) -> List[OrderProposal]:
    """Preserve input order (intent_sequence from scan adapter). No alphabetical sort."""
    return sorted(
        proposals,
        key=lambda p: int(p.signal.metadata.get("intent_sequence", 0)),
    )


def apply_verdict_to_sim(portfolio: PortfolioState, proposal: OrderProposal, verdict: RiskVerdict) -> None:
    if verdict.decision == RiskDecision.BLOCK:
        return
    if verdict.decision == RiskDecision.MANUAL_REVIEW:
        return
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

    def _batch_trade_intent_blocked(
        self,
        proposal: OrderProposal,
        batch_approved_keys: Set[str],
    ) -> Optional[str]:
        if self.config.allow_same_day_same_symbol_side:
            return None
        key = trade_intent_key(
            proposal.signal.strategy,
            proposal.signal.asof_date,
            proposal.signal.symbol,
            proposal.signal.side,
        )
        if key in batch_approved_keys:
            return f"duplicate_trade_intent_batch: {key}"
        blocked, _, _ = self.om.check_trade_intent_blocked(proposal, self.config)
        if blocked:
            return blocked
        return None

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
        batch_approved_keys: Set[str] = set()

        for prop in _proposal_order(proposals):
            prop.nav_vnd = sim.nav_vnd
            if self.om.store.exists(prop.idempotency_key):
                existing = self.om.store.load(prop.idempotency_key)
                if existing:
                    results.append(existing)
                continue

            mo = ManagedOrder(proposal=prop, state=OrderState.PENDING_SIGNAL)
            blocked_msg = self._batch_trade_intent_blocked(prop, batch_approved_keys)
            if blocked_msg:
                from src.trading.models import RiskVerdict
                verdict = RiskVerdict(
                    passed=False,
                    reasons=[blocked_msg],
                    rule_ids=["duplicate_trade_intent_batch"],
                    decision=RiskDecision.BLOCK,
                )
                prop.risk_verdict = verdict
                mo.risk_verdict = verdict
                mo.state = transition(mo.state, OrderState.REJECTED_BY_RISK)
            else:
                ctx = RiskContext(portfolio=sim, pending_idempotency_keys=pending)
                verdict = self.engine.evaluate(prop, ctx, live_config=self.config, extra=extra_ctx)
                prop.risk_verdict = verdict
                mo.risk_verdict = verdict
                if verdict.decision == RiskDecision.PASS:
                    mo.state = transition(mo.state, OrderState.APPROVED_BY_RISK)
                    mo.state = transition(mo.state, OrderState.ORDER_READY)
                    apply_verdict_to_sim(sim, prop, verdict)
                    batch_approved_keys.add(
                        trade_intent_key(
                            prop.signal.strategy,
                            prop.signal.asof_date,
                            prop.signal.symbol,
                            prop.signal.side,
                        )
                    )
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
                "decision": mo.risk_verdict.decision.value if mo.risk_verdict else "",
                "reasons": "; ".join(mo.risk_verdict.reasons) if mo.risk_verdict else "",
                "rule_ids": "|".join(mo.risk_verdict.rule_ids) if mo.risk_verdict else "",
            })

        if risk_rows:
            path = self.config.risk_check_path(asof_date)
            path.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(risk_rows).to_csv(path, index=False)
        return results
