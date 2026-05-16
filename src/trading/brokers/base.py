"""Broker abstraction for Vietnam equities."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List  # noqa: F401 — List used by stubs

from src.trading.models import BrokerOrder


class BaseBroker(ABC):
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
    def place_order(self, order: Dict[str, Any]) -> BrokerOrder:
        """Submit order. Single attempt; no retry loop."""

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
