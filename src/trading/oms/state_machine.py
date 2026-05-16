"""Order state machine with validated transitions."""
from __future__ import annotations

from src.trading.models import OrderState


class InvalidStateTransition(Exception):
    pass


_ALLOWED: dict[OrderState, set[OrderState]] = {
    OrderState.PENDING_SIGNAL: {
        OrderState.APPROVED_BY_RISK,
        OrderState.REJECTED_BY_RISK,
    },
    OrderState.APPROVED_BY_RISK: {OrderState.ORDER_READY},
    OrderState.ORDER_READY: {
        OrderState.ORDER_SUBMITTED,
        OrderState.BROKER_REJECTED,
        OrderState.REJECTED_AT_EXECUTION,
        OrderState.ERROR_REQUIRES_MANUAL_REVIEW,
        OrderState.CANCEL_REQUESTED,
    },
    OrderState.ORDER_SUBMITTED: {
        OrderState.PARTIALLY_FILLED,
        OrderState.FILLED,
        OrderState.BROKER_REJECTED,
        OrderState.CANCEL_REQUESTED,
        OrderState.ERROR_REQUIRES_MANUAL_REVIEW,
    },
    OrderState.PARTIALLY_FILLED: {
        OrderState.FILLED,
        OrderState.CANCEL_REQUESTED,
        OrderState.ERROR_REQUIRES_MANUAL_REVIEW,
    },
    OrderState.CANCEL_REQUESTED: {
        OrderState.CANCELLED,
        OrderState.ERROR_REQUIRES_MANUAL_REVIEW,
    },
    OrderState.REJECTED_BY_RISK: set(),
    OrderState.REJECTED_AT_EXECUTION: set(),
    OrderState.FILLED: set(),
    OrderState.CANCELLED: set(),
    OrderState.BROKER_REJECTED: set(),
    OrderState.ERROR_REQUIRES_MANUAL_REVIEW: set(),
}


def transition(current: OrderState, new: OrderState) -> OrderState:
    allowed = _ALLOWED.get(current, set())
    if new not in allowed:
        raise InvalidStateTransition(f"Cannot transition {current.value} -> {new.value}")
    return new
