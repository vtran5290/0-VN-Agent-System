"""Order manager — proposals through risk to broker (or dry-run)."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Set, Tuple

from src.trading.brokers.base import BaseBroker
from src.trading.brokers.dnse import DNSEBroker
from src.trading.brokers.hard_caps import (
    HardCapViolationError,
    HaltSignalError,
    MisconfigurationError,
)
from src.trading.brokers.paper import PaperBroker
from src.trading.config import LiveTradingConfig, TradingConfig
from src.trading.live.data_health import load_data_health_status
from src.trading.models import (
    ManagedOrder,
    OrderProposal,
    OrderState,
    PortfolioState,
    Position,
    RiskDecision,
    RiskVerdict,
    load_proposals,
    proposals_path,
    save_proposals,
    trade_intent_key,
)
from src.trading.live.sizing_constraints import log_adv_participation_advisory
from src.trading.oms.idempotency import IdempotencyStore
from src.trading.oms.order_journal import (
    DuplicateOrderError,
    JournalStatus,
    OrphanOrderError,
    OrderJournal,
)
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


def _live_execution_mode(config: TradingConfig) -> bool:
    mode = getattr(config, "mode", "paper")
    return mode in ("live_manual", "live_auto")


def _require_journal_for_live_hard_caps(
    config: TradingConfig,
    policy: Any,
    journal: Optional[OrderJournal],
) -> None:
    if policy.enabled and _live_execution_mode(config) and journal is None:
        raise MisconfigurationError(
            "HardCapPolicy requires an initialized order journal in live mode — "
            "journal=None disables the daily cap"
        )


def get_broker(
    config: TradingConfig,
    journal: Optional[OrderJournal] = None,
    kill_switch: Optional[Dict[str, Any]] = None,
) -> BaseBroker:
    policy = config.broker_hard_cap_policy()
    _require_journal_for_live_hard_caps(config, policy, journal)
    submissions_fn = None
    if journal is not None:
        submissions_fn = journal.count_submissions_today
    broker_kwargs: Dict[str, Any] = {
        "submissions_today_fn": submissions_fn,
        "kill_switch": kill_switch,
    }
    if config.broker.lower() == "dnse":
        policy.log_startup_warnings()
        return DNSEBroker(
            config,
            hard_cap_policy=policy,
            check_halt_file=True,
            **broker_kwargs,
        )
    return PaperBroker(config, **broker_kwargs)


def _wire_broker_journal(broker: BaseBroker, journal: OrderJournal) -> None:
    broker._submissions_today_fn = journal.count_submissions_today  # noqa: SLF001


def portfolio_from_broker(broker: BaseBroker, asof_date: str) -> PortfolioState:
    cash = broker.get_cash_balance().get("cash_vnd", 0.0)
    positions = []
    for p in broker.get_positions():
        positions.append(
            Position(
                symbol=p["symbol"],
                quantity=int(p["quantity"]),
                avg_price=float(p["avg_price"]),
                market_value_vnd=float(p.get("market_value_vnd", 0)),
            )
        )
    nav = broker.get_account().get("nav_vnd", cash + sum(x.market_value_vnd for x in positions))
    open_orders = [
        o for o in broker.get_order_list()
        if o.get("state") not in (OrderState.FILLED.value, OrderState.CANCELLED.value)
    ]
    return PortfolioState(
        asof_date=asof_date,
        cash_vnd=float(cash),
        nav_vnd=float(nav),
        positions=positions,
        open_orders=open_orders,
        new_positions_today=0,
        daily_orders=0,
        open_slots=len(positions),
    )


class OrderManager:
    def __init__(self, config: TradingConfig, broker: Optional[BaseBroker] = None):
        self.config = config
        self.config.ensure_dirs()
        self.journal = OrderJournal(config.order_journal_path)
        self._recovery_orphans = self.journal.run_startup_recovery(
            config.order_recovery_report_path
        )
        policy = config.broker_hard_cap_policy()
        if broker is None:
            self.broker = get_broker(config, journal=self.journal)
        else:
            self.broker = broker
            if policy.enabled and _live_execution_mode(config):
                if self.broker._submissions_today_fn is None:  # noqa: SLF001
                    _wire_broker_journal(self.broker, self.journal)
        self.broker.login()
        self.risk = RiskEngine(config)
        self.store = IdempotencyStore(config.orders_dir)

    @property
    def recovery_orphans(self) -> List[Any]:
        """PENDING/SUBMITTED journal rows flagged at startup for operator review."""
        return self._recovery_orphans

    def close(self) -> None:
        self.journal.close()

    def __del__(self) -> None:
        try:
            self.journal.close()
        except Exception:
            pass

    def _audit(self, event: str, payload: dict) -> None:
        line = json.dumps({"event": event, "ts": utc_now_iso(), **payload})
        with open(self.config.audit_log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def check_trade_intent_blocked(
        self,
        proposal: OrderProposal,
        live: Optional[LiveTradingConfig],
        exclude_idempotency_key: Optional[str] = None,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Return (blocked, blocking_key, blocking_state)."""
        if live and live.allow_same_day_same_symbol_side:
            return False, None, None
        key = trade_intent_key(
            proposal.signal.strategy,
            proposal.signal.asof_date,
            proposal.signal.symbol,
            proposal.signal.side,
        )
        for mo in self.load_all_orders():
            if exclude_idempotency_key and mo.idempotency_key == exclude_idempotency_key:
                continue
            if mo.trade_intent_key != key:
                continue
            if mo.state in _ACTIVE_STATES:
                return True, key, mo.state.value
            if mo.state == OrderState.REJECTED_BY_RISK:
                continue
        return False, None, None

    def risk_review_proposals(
        self,
        asof_date: str,
        extra: Optional[Dict[str, Any]] = None,
        live_config: Optional[LiveTradingConfig] = None,
    ) -> List[ManagedOrder]:
        path = proposals_path(self.config.data_root, asof_date)
        proposals = load_proposals(path)
        if live_config and proposals:
            from src.trading.risk.batch_context import BatchRiskReviewer
            reviewer = BatchRiskReviewer(live_config, self)
            return reviewer.risk_review_batch(asof_date, proposals, extra)

        portfolio = portfolio_from_broker(self.broker, asof_date)
        pending = list(self.store.list_keys())
        results: List[ManagedOrder] = []

        for prop in proposals:
            prop.adv50_vnd = prop.adv50_vnd or 0.0
            prop.nav_vnd = portfolio.nav_vnd
            if self.store.exists(prop.idempotency_key):
                existing = self.store.load(prop.idempotency_key)
                if existing:
                    results.append(existing)
                continue

            mo = ManagedOrder(proposal=prop, state=OrderState.PENDING_SIGNAL)
            self._audit("proposed", {"idempotency_key": prop.idempotency_key, "symbol": prop.signal.symbol})

            blocked, bkey, bstate = self.check_trade_intent_blocked(prop, live_config)
            if blocked:
                verdict = RiskVerdict(
                    passed=False,
                    reasons=[f"Active trade intent exists: {bkey} ({bstate})"],
                    rule_ids=["trade_intent_lock"],
                    decision=RiskDecision.BLOCK,
                )
                mo.state = transition(mo.state, OrderState.REJECTED_BY_RISK)
                mo.risk_verdict = verdict
                prop.risk_verdict = verdict
            else:
                ctx = RiskContext(portfolio=portfolio, pending_idempotency_keys=pending)
                verdict = self.risk.evaluate(prop, ctx, live_config=live_config, extra=extra or {})
                prop.risk_verdict = verdict
                mo.risk_verdict = verdict
                if verdict.decision == RiskDecision.PASS:
                    mo.state = transition(mo.state, OrderState.APPROVED_BY_RISK)
                    mo.state = transition(mo.state, OrderState.ORDER_READY)
                else:
                    mo.state = transition(mo.state, OrderState.REJECTED_BY_RISK)

            mo.updated_at = utc_now_iso()
            self.store.save(mo)
            pending.append(prop.idempotency_key)
            results.append(mo)

        save_proposals(path, proposals)
        return results

    def _pre_submit_risk(
        self,
        mo: ManagedOrder,
        live_config: Optional[LiveTradingConfig],
        extra: Dict[str, Any],
    ) -> bool:
        portfolio = portfolio_from_broker(self.broker, mo.proposal.signal.asof_date)
        ctx = RiskContext(portfolio=portfolio, pending_idempotency_keys=[])
        verdict = self.risk.evaluate(mo.proposal, ctx, live_config=live_config, extra=extra)
        if verdict.decision != RiskDecision.PASS:
            return False
        blocked, bkey, bstate = self.check_trade_intent_blocked(
            mo.proposal, live_config, exclude_idempotency_key=mo.idempotency_key
        )
        if blocked:
            self._audit(
                "pre_submit_duplicate_trade_intent_rejected",
                {
                    "idempotency_key": mo.idempotency_key,
                    "blocking_key": bkey,
                    "blocking_state": bstate,
                },
            )
            return False
        sig = mo.proposal.signal
        cap = self.broker.get_trade_capacity(sig.symbol, sig.intended_price, sig.side)
        if int(cap.get("max_quantity", 0)) < sig.quantity:
            self._audit(
                "broker_capacity_rejected",
                {"idempotency_key": mo.idempotency_key, "max_quantity": cap.get("max_quantity")},
            )
            return False
        return True

    def _apply_paper_ledger_fill(self, mo: ManagedOrder, paper_ledger: Any) -> None:
        sig = mo.proposal.signal
        action = sig.metadata.get("action", "")
        if action.startswith("SELL") or sig.side.upper() == "SELL":
            pass
        paper_ledger.apply_fill_from_order(
            action=action or ("SELL_EXIT" if sig.side.upper() == "SELL" else "BUY_T1"),
            symbol=sig.symbol,
            asof_date=sig.asof_date,
            fill_price=sig.intended_price,
            quantity=sig.quantity,
            value_vnd=mo.proposal.order_value_vnd,
            breadth_zone=sig.metadata.get("breadth_zone", ""),
            sector_l4=sig.metadata.get("sector_l4", ""),
        )

    def execute_approved(
        self,
        asof_date: str,
        live_config: Optional[LiveTradingConfig] = None,
        extra: Optional[Dict[str, Any]] = None,
        paper_ledger: Optional[Any] = None,
    ) -> List[ManagedOrder]:
        extra = extra or {}
        if live_config:
            from src.trading.monitoring.kill_switch import load_kill_switch
            extra.setdefault("data_health", load_data_health_status(live_config))
            extra.setdefault("kill_switch", load_kill_switch(live_config))
            rs_path = live_config.reconciliation_status_path
            if rs_path.exists() and "reconciliation" not in extra:
                extra["reconciliation"] = json.loads(rs_path.read_text(encoding="utf-8"))

        ks = extra.get("kill_switch", {})
        if ks.get("status") == "BLOCK":
            self._audit("execute_blocked_kill_switch", {"asof": asof_date})
            return []

        if hasattr(self.broker, "set_kill_switch"):
            self.broker.set_kill_switch(ks)

        recon = extra.get("reconciliation", {})
        mode = live_config.mode if live_config else "dry_run"
        if live_config and mode in ("live_manual", "live_auto") and recon.get("BLOCK_NEW_ORDERS"):
            self._audit(
                "execute_blocked_reconciliation",
                {
                    "asof": asof_date,
                    "message": (
                        "Reconciliation failure in live mode — halting cycle. "
                        "Resolve manually or revert to paper mode."
                    ),
                },
            )
            return []
        if live_config and live_config.require_reconciliation_clean and recon.get("BLOCK_NEW_ORDERS"):
            self._audit("execute_blocked_reconciliation", {"asof": asof_date})
            return []

        paper_mode = mode == "paper"
        dry_run_mode = mode == "dry_run" or (not paper_mode and self.config.dry_run)

        if paper_mode:
            self.config.broker = "paper"
            self.config.live_trading = True
            self.config.dry_run = False
            if not isinstance(self.broker, PaperBroker):
                self.broker = get_broker(
                    self.config,
                    journal=self.journal,
                    kill_switch=extra.get("kill_switch"),
                )
                self.broker.login()

        proposals = load_proposals(proposals_path(self.config.data_root, asof_date))
        executed: List[ManagedOrder] = []
        paper_fills = 0

        for prop in proposals:
            mo = self.store.load(prop.idempotency_key)
            if not mo or mo.state != OrderState.ORDER_READY:
                continue
            if not mo.risk_verdict or mo.risk_verdict.decision != RiskDecision.PASS:
                continue

            if live_config and live_config.mode == "live_auto" and not live_config.live_auto_allowed():
                mo.state = OrderState.ERROR_REQUIRES_MANUAL_REVIEW
                mo.error_message = "live_auto disabled"
                self.store.save(mo)
                executed.append(mo)
                continue

            if dry_run_mode and not paper_mode:
                self._audit(
                    "dry_run_submit",
                    {"idempotency_key": mo.idempotency_key, "payload": prop.to_dict()},
                )
                executed.append(mo)
                continue

            if not self._pre_submit_risk(mo, live_config, extra):
                try:
                    mo.state = transition(mo.state, OrderState.REJECTED_AT_EXECUTION)
                except Exception:
                    mo.state = OrderState.REJECTED_AT_EXECUTION
                self._audit("execution_risk_rejected", {"idempotency_key": mo.idempotency_key})
                self.store.save(mo)
                executed.append(mo)
                continue

            if self.config.broker.lower() == "dnse":
                mo.state = OrderState.ERROR_REQUIRES_MANUAL_REVIEW
                mo.error_message = "DNSE broker not implemented for live orders"
                self.store.save(mo)
                executed.append(mo)
                continue

            sig = prop.signal
            log_adv_participation_advisory(
                sig.symbol,
                sig.quantity,
                mo.proposal.adv50_vnd,
                sig.intended_price,
            )
            order_req = {
                "symbol": sig.symbol,
                "side": sig.side,
                "quantity": sig.quantity,
                "price": sig.intended_price,
                "idempotency_key": mo.idempotency_key,
            }
            try:
                self.journal.write_pending(
                    mo.idempotency_key,
                    symbol=sig.symbol,
                    action=sig.side,
                    qty=sig.quantity,
                    price=sig.intended_price,
                )
                mo.state = transition(mo.state, OrderState.ORDER_SUBMITTED)
                bo = self.broker.place_order(order_req)
                self.journal.mark_submitted(
                    mo.idempotency_key,
                    bo.broker_order_id,
                    raw_response=bo.to_dict(),
                )
                mo.broker_order_id = bo.broker_order_id
                if bo.state == OrderState.FILLED:
                    mo.state = transition(mo.state, OrderState.FILLED)
                    self.journal.mark_filled(mo.idempotency_key, raw_response=bo.to_dict())
                    if paper_mode and paper_ledger is not None:
                        self._apply_paper_ledger_fill(mo, paper_ledger)
                        paper_fills += 1
                elif bo.state == OrderState.BROKER_REJECTED:
                    mo.state = transition(mo.state, OrderState.BROKER_REJECTED)
                    self.journal.mark_rejected(mo.idempotency_key, raw_response=bo.to_dict())
                self._audit(
                    "paper_filled" if paper_mode else "submitted",
                    {"idempotency_key": mo.idempotency_key, "broker_order_id": bo.broker_order_id},
                )
            except (DuplicateOrderError, OrphanOrderError) as e:
                mo.state = OrderState.ERROR_REQUIRES_MANUAL_REVIEW
                mo.error_message = str(e)
                self._audit(
                    "journal_duplicate_or_orphan",
                    {"idempotency_key": mo.idempotency_key, "error": str(e)},
                )
            except (HardCapViolationError, HaltSignalError) as e:
                try:
                    mo.state = transition(mo.state, OrderState.REJECTED_AT_EXECUTION)
                except Exception:
                    mo.state = OrderState.REJECTED_AT_EXECUTION
                mo.error_message = str(e)
                entry = self.journal.get(mo.idempotency_key)
                if entry and entry.status == JournalStatus.PENDING:
                    self.journal.mark_rejected(mo.idempotency_key, raw_response={"error": str(e)})
                self._audit(
                    "broker_guard_rejected",
                    {"idempotency_key": mo.idempotency_key, "error": str(e)},
                )
            except Exception as e:
                mo.state = OrderState.ERROR_REQUIRES_MANUAL_REVIEW
                mo.error_message = str(e)
                entry = self.journal.get(mo.idempotency_key)
                if entry and entry.status == JournalStatus.PENDING:
                    self.journal.mark_rejected(mo.idempotency_key, raw_response={"error": str(e)})
                self._audit("error", {"idempotency_key": mo.idempotency_key, "error": str(e)})

            mo.updated_at = utc_now_iso()
            self.store.save(mo)
            executed.append(mo)

        if live_config and paper_mode:
            extra["_paper_fills"] = paper_fills
        return executed

    def load_all_orders(self) -> List[ManagedOrder]:
        orders = []
        for p in self.config.orders_dir.glob("*.json"):
            try:
                orders.append(ManagedOrder.from_dict(json.loads(p.read_text(encoding="utf-8"))))
            except (json.JSONDecodeError, KeyError):
                continue
        return orders
