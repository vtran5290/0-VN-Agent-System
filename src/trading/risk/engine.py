"""Risk engine — approve/reject every proposed order."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.trading.config import LiveTradingConfig, TradingConfig
from src.trading.models import OrderProposal, PortfolioState, RiskDecision, RiskVerdict
from src.trading.risk import live_rules as LR
from src.trading.risk import rules as R


@dataclass
class RiskContext:
    portfolio: PortfolioState
    pending_idempotency_keys: List[str] = field(default_factory=list)
    active_trade_intent_keys: List[str] = field(default_factory=list)


class RiskEngine:
    def __init__(self, config: TradingConfig):
        self.config = config

    def evaluate(
        self,
        proposal: OrderProposal,
        ctx: RiskContext,
        live_config: Optional[LiveTradingConfig] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> RiskVerdict:
        extra = extra or {}
        cfg = live_config or self.config
        checks = [
            R.check_max_order_value(proposal, self.config),
            R.check_min_adv50(proposal, self.config),
            R.check_max_order_pct_adv50(proposal, self.config),
            R.check_max_position_pct_nav(proposal, ctx.portfolio, self.config),
            R.check_max_total_exposure(proposal, ctx.portfolio, self.config),
            R.check_max_daily_new_positions(proposal, ctx.portfolio, self.config),
            R.check_no_margin(proposal, ctx.portfolio, self.config),
            R.check_no_duplicate_open_orders(
                proposal, ctx.portfolio, ctx.pending_idempotency_keys
            ),
            R.check_stale_market_data(proposal, self.config),
        ]

        manual_review = False
        reasons_mr: List[str] = []
        rule_ids_mr: List[str] = []
        if isinstance(cfg, LiveTradingConfig):
            live_checks = [
                LR.check_max_daily_orders(ctx.portfolio, cfg),
                LR.check_max_slots(proposal, ctx.portfolio, cfg),
                LR.check_data_health(extra, cfg),
                LR.check_kill_switch(extra, cfg),
                LR.check_reconciliation(extra, cfg),
                LR.check_regime_bull(proposal, cfg),
                LR.check_breadth_manual_review(proposal),
                LR.check_pts_s3_block(proposal, cfg),
            ]
            for item in live_checks:
                ok, rule_id, msg, dec = item
                if not ok and msg:
                    if dec == RiskDecision.MANUAL_REVIEW:
                        manual_review = True
                        reasons_mr = [msg]
                        rule_ids_mr = [rule_id]
                    else:
                        checks.append((False, rule_id, msg))

        reasons: List[str] = []
        rule_ids: List[str] = []
        for passed, rule_id, msg in checks:
            if not passed and msg:
                reasons.append(msg)
                rule_ids.append(rule_id)

        if manual_review and not reasons:
            return RiskVerdict(
                passed=False,
                reasons=reasons_mr,
                rule_ids=rule_ids_mr,
                decision=RiskDecision.MANUAL_REVIEW,
            )
        if reasons:
            return RiskVerdict(
                passed=False,
                reasons=reasons,
                rule_ids=rule_ids,
                decision=RiskDecision.BLOCK,
            )
        return RiskVerdict(passed=True, reasons=[], rule_ids=[], decision=RiskDecision.PASS)
