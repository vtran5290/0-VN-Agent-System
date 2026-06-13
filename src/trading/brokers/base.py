"""Broker abstraction for Vietnam equities."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from src.trading.brokers.hard_caps import HardCapPolicy, enforce_submission_guards
from src.trading.models import BrokerOrder


class BaseBroker(ABC):
    def __init__(
        self,
        hard_cap_policy: Optional[HardCapPolicy] = None,
        *,
        submissions_today_fn: Optional[Any] = None,
        kill_switch: Optional[Dict[str, Any]] = None,
        check_halt_file: bool = False,
    ):
        self.hard_cap_policy = hard_cap_policy or HardCapPolicy.disabled()
        self._submissions_today_fn = submissions_today_fn
        self._kill_switch = kill_switch
        self._check_halt_file = check_halt_file

    def set_kill_switch(self, kill_switch: Optional[Dict[str, Any]]) -> None:
        self._kill_switch = kill_switch

    def _enforce_submission_guards(self, order: Dict[str, Any]) -> None:
        submissions = 0
        if self._submissions_today_fn is not None:
            submissions = int(self._submissions_today_fn())
        enforce_submission_guards(
            order,
            hard_cap_policy=self.hard_cap_policy,
            submissions_today=submissions,
            kill_switch=self._kill_switch,
            check_halt_file=self._check_halt_file,
        )

    def place_order(self, order: Dict[str, Any]) -> BrokerOrder:
        """Submit order with last-mile guards, then delegate to broker implementation."""
        self._enforce_submission_guards(order)
        return self._place_order_impl(order)

    @abstractmethod
    def _place_order_impl(self, order: Dict[str, Any]) -> BrokerOrder:
        """Broker-specific order submission (single attempt; no retry loop)."""

    @abstractmethod
    def login(self) -> Dict[str, Any]:
        """Authenticate with broker. Returns account metadata."""

    @abstractmethod
    def get_account(self) -> Dict[str, Any]:
        """Primary account info."""

    @abstractmethod
    def get_sub_accounts(self) -> List[Dict[str, Any]]:
        """Sub-accounts if supported."""

    @abstractmethod
    def get_cash_balance(self) -> Dict[str, Any]:
        """Cash balance in VND."""

    @abstractmethod
    def get_positions(self) -> List[Dict[str, Any]]:
        """Open positions."""

    @abstractmethod
    def get_trade_capacity(self, symbol: str, price: float, side: str) -> Dict[str, Any]:
        """Max quantity affordable at price."""

    @abstractmethod
    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel open order."""

    @abstractmethod
    def get_order_list(self) -> List[Dict[str, Any]]:
        """List orders."""

    @abstractmethod
    def get_order_detail(self, order_id: str) -> Dict[str, Any]:
        """Order detail by broker id."""

    def get_cash(self) -> Dict[str, Any]:
        return self.get_cash_balance()

    def get_open_orders(self) -> List[Dict[str, Any]]:
        return [
            o for o in self.get_order_list()
            if o.get("state") not in ("FILLED", "CANCELLED")
        ]

    def get_fills(self) -> List[Dict[str, Any]]:
        return []

    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        return self.get_order_detail(order_id)
