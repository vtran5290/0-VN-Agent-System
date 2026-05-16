"""Core domain models for the trading pipeline."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.trading.util.timeutil import utc_now_iso


class OrderState(str, Enum):
    PENDING_SIGNAL = "PENDING_SIGNAL"
    APPROVED_BY_RISK = "APPROVED_BY_RISK"
    REJECTED_BY_RISK = "REJECTED_BY_RISK"
    ORDER_READY = "ORDER_READY"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"
    BROKER_REJECTED = "BROKER_REJECTED"
    REJECTED_AT_EXECUTION = "REJECTED_AT_EXECUTION"
    ERROR_REQUIRES_MANUAL_REVIEW = "ERROR_REQUIRES_MANUAL_REVIEW"


class RiskDecision(str, Enum):
    PASS = "PASS"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    BLOCK = "BLOCK"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


def idempotency_key(
    strategy: str,
    asof_date: str,
    symbol: str,
    side: str,
    intended_price: float,
    quantity: int,
) -> str:
    return f"{strategy}|{asof_date}|{symbol}|{side}|{intended_price:.2f}|{quantity}"


def trade_intent_key(strategy: str, asof_date: str, symbol: str, side: str) -> str:
    return f"{strategy}|{asof_date}|{symbol}|{side}"


@dataclass
class Signal:
    strategy: str
    symbol: str
    side: str
    asof_date: str
    intended_price: float
    quantity: int
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Signal":
        return cls(
            strategy=d["strategy"],
            symbol=d["symbol"],
            side=d["side"],
            asof_date=d["asof_date"],
            intended_price=float(d["intended_price"]),
            quantity=int(d["quantity"]),
            reason=d.get("reason", ""),
            metadata=d.get("metadata", {}),
        )


@dataclass
class OrderProposal:
    signal: Signal
    adv50_vnd: float = 0.0
    nav_vnd: float = 0.0
    market_value_vnd: float = 0.0
    risk_verdict: Optional["RiskVerdict"] = None

    @property
    def order_value_vnd(self) -> float:
        return self.signal.intended_price * self.signal.quantity

    @property
    def idempotency_key(self) -> str:
        s = self.signal
        return idempotency_key(
            s.strategy, s.asof_date, s.symbol, s.side, s.intended_price, s.quantity
        )

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "signal": self.signal.to_dict(),
            "adv50_vnd": self.adv50_vnd,
            "nav_vnd": self.nav_vnd,
            "market_value_vnd": self.market_value_vnd,
            "idempotency_key": self.idempotency_key,
        }
        if self.risk_verdict is not None:
            d["risk_verdict"] = self.risk_verdict.to_dict()
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "OrderProposal":
        rv = None
        if d.get("risk_verdict"):
            rv = RiskVerdict.from_dict(d["risk_verdict"])
        return cls(
            signal=Signal.from_dict(d["signal"]),
            adv50_vnd=float(d.get("adv50_vnd", 0)),
            nav_vnd=float(d.get("nav_vnd", 0)),
            market_value_vnd=float(d.get("market_value_vnd", 0)),
            risk_verdict=rv,
        )


@dataclass
class RiskVerdict:
    passed: bool
    reasons: List[str] = field(default_factory=list)
    rule_ids: List[str] = field(default_factory=list)
    decision: RiskDecision = RiskDecision.PASS

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "reasons": self.reasons,
            "rule_ids": self.rule_ids,
            "decision": self.decision.value,
            "status": self.decision.value if self.decision != RiskDecision.PASS else ("PASS" if self.passed else "FAIL"),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RiskVerdict":
        dec = d.get("decision", "PASS")
        try:
            decision = RiskDecision(dec)
        except ValueError:
            decision = RiskDecision.PASS if d.get("passed") else RiskDecision.BLOCK
        return cls(
            passed=bool(d.get("passed", decision == RiskDecision.PASS)),
            reasons=list(d.get("reasons", [])),
            rule_ids=list(d.get("rule_ids", [])),
            decision=decision,
        )


@dataclass
class Position:
    symbol: str
    quantity: int
    avg_price: float
    market_value_vnd: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Position":
        return cls(
            symbol=d["symbol"],
            quantity=int(d["quantity"]),
            avg_price=float(d["avg_price"]),
            market_value_vnd=float(d.get("market_value_vnd", 0)),
        )


@dataclass
class PortfolioState:
    asof_date: str
    cash_vnd: float
    nav_vnd: float
    positions: List[Position] = field(default_factory=list)
    open_orders: List[Dict[str, Any]] = field(default_factory=list)
    new_positions_today: int = 0
    daily_orders: int = 0
    open_slots: int = 0

    def position_map(self) -> Dict[str, Position]:
        return {p.symbol: p for p in self.positions}

    def total_exposure_vnd(self) -> float:
        return sum(p.market_value_vnd for p in self.positions)


@dataclass
class BrokerOrder:
    idempotency_key: str
    broker_order_id: str
    symbol: str
    side: str
    quantity: int
    price: float
    state: OrderState
    filled_quantity: int = 0
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["state"] = self.state.value
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BrokerOrder":
        return cls(
            idempotency_key=d["idempotency_key"],
            broker_order_id=d["broker_order_id"],
            symbol=d["symbol"],
            side=d["side"],
            quantity=int(d["quantity"]),
            price=float(d["price"]),
            state=OrderState(d["state"]),
            filled_quantity=int(d.get("filled_quantity", 0)),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
        )


@dataclass
class ManagedOrder:
    """OMS-tracked order with full lifecycle."""
    proposal: OrderProposal
    state: OrderState = OrderState.PENDING_SIGNAL
    broker_order_id: Optional[str] = None
    risk_verdict: Optional[RiskVerdict] = None
    error_message: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    @property
    def idempotency_key(self) -> str:
        return self.proposal.idempotency_key

    @property
    def trade_intent_key(self) -> str:
        s = self.proposal.signal
        return trade_intent_key(s.strategy, s.asof_date, s.symbol, s.side)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "idempotency_key": self.idempotency_key,
            "proposal": self.proposal.to_dict(),
            "state": self.state.value,
            "broker_order_id": self.broker_order_id,
            "risk_verdict": self.risk_verdict.to_dict() if self.risk_verdict else None,
            "error_message": self.error_message,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ManagedOrder":
        rv = None
        if d.get("risk_verdict"):
            rv = RiskVerdict.from_dict(d["risk_verdict"])
        return cls(
            proposal=OrderProposal.from_dict(d["proposal"]),
            state=OrderState(d["state"]),
            broker_order_id=d.get("broker_order_id"),
            risk_verdict=rv,
            error_message=d.get("error_message", ""),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
        )


def save_proposals(path: Path, proposals: List[OrderProposal]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "asof_date": proposals[0].signal.asof_date if proposals else "",
        "generated_at": utc_now_iso(),
        "proposals": [p.to_dict() for p in proposals],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_proposals(path: Path) -> List[OrderProposal]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [OrderProposal.from_dict(p) for p in data.get("proposals", [])]


def proposals_path(cfg_data_root: Path, asof_date: str) -> Path:
    return cfg_data_root / "order_proposals" / f"order_proposals_{asof_date}.json"
