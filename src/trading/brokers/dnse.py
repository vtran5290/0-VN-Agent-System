"""DNSE broker placeholder — no real orders until live integration phase."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.trading.brokers.base import BaseBroker
from src.trading.config import TradingConfig
from src.trading.models import BrokerOrder, OrderState


class LiveTradingDisabledError(RuntimeError):
    """Raised when live DNSE order placement is not permitted."""


class DNSEBroker(BaseBroker):
    """
    Placeholder for DNSE / DSE LightSpeed API.
    Future: integrate vnstock.connector.dnse.Trade or direct REST.
    """

    def __init__(self, config: TradingConfig):
        self.config = config
        self._logged_in = False

    def _get_trade_client(self) -> Any:
        """Hook for future vnstock DNSE Trade client."""
        raise NotImplementedError(
            "DNSE live client not implemented. "
            "Future: vnstock.connector.dnse.Trade"
        )

    def _require_live_gate(self) -> None:
        if not self.config.live_dnse_orders_allowed():
            raise LiveTradingDisabledError(
                "DNSE live orders disabled. Require LIVE_TRADING=true, "
                "DRY_RUN=false, CONFIRM_LIVE_BROKER=DNSE, BROKER=dnse, "
                "max_order_value_vnd > 0"
            )

    def login(self) -> Dict[str, Any]:
        self._logged_in = True
        return {
            "broker": "dnse",
            "status": "placeholder",
            "message": "Read-only placeholder; credentials not connected",
        }

    def get_account(self) -> Dict[str, Any]:
        return {"broker": "dnse", "status": "placeholder", "account_id": None}

    def get_sub_accounts(self) -> List[Dict[str, Any]]:
        return []

    def get_cash_balance(self) -> Dict[str, Any]:
        return {"cash_vnd": 0.0, "currency": "VND", "status": "placeholder"}

    def get_positions(self) -> List[Dict[str, Any]]:
        return []

    def get_trade_capacity(self, symbol: str, price: float, side: str) -> Dict[str, Any]:
        return {"max_quantity": 0, "status": "placeholder", "symbol": symbol}

    def place_order(self, order: Dict[str, Any]) -> BrokerOrder:
        self._require_live_gate()
        # Even with gate passed, v1 does not place real orders
        raise NotImplementedError(
            "DNSE place_order not implemented in v1. "
            "Integrate vnstock.connector.dnse.Trade when ready."
        )

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        self._require_live_gate()
        raise NotImplementedError("DNSE cancel_order not implemented in v1")

    def get_order_list(self) -> List[Dict[str, Any]]:
        return []

    def get_order_detail(self, order_id: str) -> Dict[str, Any]:
        return {"error": "placeholder", "order_id": order_id}
