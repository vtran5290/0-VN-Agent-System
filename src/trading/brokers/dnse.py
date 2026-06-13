"""DNSE broker — Stage 2 read-only shadow (EntradeX / api.dnse.com.vn).

Read-only client: REST paths align with ``vnstock.connector.dnse.Trade`` against
``https://api.dnse.com.vn``. We call the same endpoints directly (no vnstock import
at runtime) to avoid stdout noise and trading-token side effects from the Trade
class print statements.

Stage 3 write path (place_order / cancel_order) remains NotImplementedError.

VN market mechanics (documented only — enforcement in Stage 3):
  - Price ceiling/floor: ±7% HOSE daily limit; orders outside range are rejected.
  - Board lot: 100 shares minimum per order on HOSE round-lot board.
  - Settlement: T+2.5 — bought shares not sellable for 2.5 trading days; sale
    proceeds not available for 2.5 days.
  - ATO/ATC: ATO only 9:00–9:15, ATC only 14:30–14:45; outside those windows
    only LO (limit) orders are accepted by the broker.

Async fills: DNSE order_list / deals_list are poll-based. No async callback /
status-poll loop exists in OMS yet — required before Stage 3 live submission.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

import requests

from src.trading.brokers.base import BaseBroker
from src.trading.brokers.hard_caps import HardCapPolicy
from src.trading.config import TradingConfig
from src.trading.models import BrokerOrder, OrderState

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.dnse.com.vn"


class LiveTradingDisabledError(RuntimeError):
    """Raised when live DNSE order placement is not permitted."""


class DNSEAuthError(RuntimeError):
    """Raised when DNSE authentication fails."""


def _mask_user(user: str) -> str:
    if not user:
        return "***"
    if len(user) <= 2:
        return "***"
    return user[:2] + "***"


def _first_numeric(row: Dict[str, Any], keys: List[str], default: float = 0.0) -> float:
    for key in keys:
        if key in row and row[key] is not None:
            try:
                return float(row[key])
            except (TypeError, ValueError):
                continue
    return default


def _first_str(row: Dict[str, Any], keys: List[str], default: str = "") -> str:
    for key in keys:
        val = row.get(key)
        if val is not None and str(val).strip():
            return str(val)
    return default


class _DnseReadApi:
    """Minimal read-only HTTP client (vnstock Trade-compatible endpoints)."""

    def __init__(self) -> None:
        self.token: Optional[str] = None
        self.sub_account: Optional[str] = None

    def login(self, username: str, password: str) -> None:
        url = f"{_BASE_URL}/auth-service/login"
        payload = json.dumps({"username": username, "password": password})
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, headers=headers, data=payload, timeout=30)
        if response.status_code != 200:
            raise DNSEAuthError(f"DNSE login failed (HTTP {response.status_code})")
        token = response.json().get("token")
        if not token:
            raise DNSEAuthError("DNSE login failed: no token in response")
        self.token = token

    def _auth_headers(self) -> Dict[str, str]:
        if not self.token:
            raise DNSEAuthError("DNSE not logged in")
        return {"Authorization": f"Bearer {self.token}"}

    def resolve_sub_account(self, override: Optional[str] = None) -> str:
        if override:
            self.sub_account = override
            return override
        if self.sub_account:
            return self.sub_account
        url = f"{_BASE_URL}/order-service/accounts"
        response = requests.get(url, headers=self._auth_headers(), timeout=30)
        if response.status_code != 200:
            raise RuntimeError(f"DNSE sub-accounts fetch failed (HTTP {response.status_code})")
        accounts = response.json().get("accounts") or []
        if not accounts:
            raise RuntimeError("DNSE sub-accounts list empty")
        acct_no = str(
            accounts[0].get("accountNo")
            or accounts[0].get("account_no")
            or accounts[0].get("id")
            or ""
        )
        if not acct_no:
            raise RuntimeError("DNSE sub-account number not found in response")
        self.sub_account = acct_no
        return acct_no

    def fetch_balance_row(self, sub_account: str) -> Dict[str, Any]:
        url = f"{_BASE_URL}/order-service/account-balances/{sub_account}"
        response = requests.get(url, headers=self._auth_headers(), timeout=30)
        if response.status_code != 200:
            raise RuntimeError(f"DNSE balance fetch failed (HTTP {response.status_code})")
        data = response.json()
        if isinstance(data, dict):
            return data
        if isinstance(data, list) and data:
            return data[0] if isinstance(data[0], dict) else {}
        return {}

    def fetch_deals(self, sub_account: str) -> List[Dict[str, Any]]:
        url = f"{_BASE_URL}/deal-service/deals?accountNo={sub_account}"
        response = requests.get(url, headers=self._auth_headers(), timeout=30)
        if response.status_code != 200:
            raise RuntimeError(f"DNSE deals fetch failed (HTTP {response.status_code})")
        payload = response.json()
        deals = payload.get("data") if isinstance(payload, dict) else payload
        return list(deals or [])

    def fetch_orders(self, sub_account: str) -> List[Dict[str, Any]]:
        url = f"{_BASE_URL}/order-service/v2/orders?accountNo={sub_account}"
        response = requests.get(url, headers=self._auth_headers(), timeout=30)
        if response.status_code != 200:
            raise RuntimeError(f"DNSE order list fetch failed (HTTP {response.status_code})")
        payload = response.json()
        orders = payload.get("orders") if isinstance(payload, dict) else payload
        return list(orders or [])


class DNSEBroker(BaseBroker):
    """DNSE read-only broker adapter for Stage 2 shadow."""

    is_read_only: bool = True

    def __init__(
        self,
        config: TradingConfig,
        hard_cap_policy: Optional[HardCapPolicy] = None,
        *,
        api_client: Optional[_DnseReadApi] = None,
        **broker_kwargs: Any,
    ):
        super().__init__(
            hard_cap_policy or config.broker_hard_cap_policy(),
            check_halt_file=True,
            **broker_kwargs,
        )
        self.config = config
        self._api = api_client or _DnseReadApi()
        self._logged_in = False
        self._sub_account: Optional[str] = None
        self._balance_cache: Dict[str, Any] = {}

    @property
    def read_only(self) -> bool:
        return self.is_read_only

    def _credentials(self) -> tuple[str, str]:
        user = os.environ.get("DNSE_USERNAME", "").strip()
        password = os.environ.get("DNSE_PASSWORD", "").strip()
        if not user or not password:
            raise DNSEAuthError("DNSE_USERNAME and DNSE_PASSWORD must be set in environment")
        return user, password

    def _sub_account_no(self) -> str:
        override = os.environ.get("DNSE_SUB_ACCOUNT", "").strip() or None
        if self._sub_account:
            return self._sub_account
        self._sub_account = self._api.resolve_sub_account(override)
        return self._sub_account

    def login(self) -> Dict[str, Any]:
        user, password = self._credentials()
        logger.info("DNSE login attempted for user=%s", _mask_user(user))
        self._api.login(user, password)
        self._sub_account = self._api.resolve_sub_account(
            os.environ.get("DNSE_SUB_ACCOUNT", "").strip() or None
        )
        self._logged_in = True
        return {
            "broker": "dnse",
            "status": "ok",
            "read_only": True,
            "sub_account": self._sub_account,
        }

    def get_balances(self) -> Dict[str, Any]:
        """Read-only balance snapshot (shadow / operator use)."""
        row = self._fetch_balance_row()
        return {
            "cash_available_vnd": _first_numeric(
                row, ["availableCash", "cashAvailable", "cash", "availableAmount"]
            ),
            "total_portfolio_value_vnd": _first_numeric(
                row,
                ["netAssetValue", "totalAsset", "nav", "totalPortfolioValue", "equity"],
            ),
            "margin_used_vnd": _first_numeric(
                row, ["marginDebt", "marginUsed", "usedMargin", "loanAmount"]
            ),
            "raw_status": "ok",
        }

    def _fetch_balance_row(self) -> Dict[str, Any]:
        if not self._logged_in:
            self.login()
        sub = self._sub_account_no()
        self._balance_cache = self._api.fetch_balance_row(sub)
        return self._balance_cache

    def get_account(self) -> Dict[str, Any]:
        bal = self.get_balances()
        return {
            "broker": "dnse",
            "account_id": self._sub_account_no(),
            "nav_vnd": bal["total_portfolio_value_vnd"],
            "cash_vnd": bal["cash_available_vnd"],
            "read_only": True,
        }

    def get_sub_accounts(self) -> List[Dict[str, Any]]:
        if not self._logged_in:
            self.login()
        sub = self._sub_account_no()
        return [{"sub_account_id": sub, "type": "stock"}]

    def get_cash_balance(self) -> Dict[str, Any]:
        bal = self.get_balances()
        return {"cash_vnd": bal["cash_available_vnd"], "currency": "VND"}

    def get_positions(self) -> List[Dict[str, Any]]:
        if not self._logged_in:
            self.login()
        sub = self._sub_account_no()
        deals = self._api.fetch_deals(sub)
        out: List[Dict[str, Any]] = []
        for deal in deals:
            symbol = _first_str(deal, ["symbol", "stockSymbol", "ticker"]).upper()
            qty = int(_first_numeric(deal, ["openQuantity", "quantity", "qty", "currentQty"]))
            if qty <= 0 or not symbol:
                continue
            avg_cost = _first_numeric(deal, ["averageCost", "avgCost", "costPrice", "breakEvenPrice"])
            current_price = _first_numeric(deal, ["marketPrice", "currentPrice", "lastPrice", "price"])
            unrealized = _first_numeric(
                deal, ["unrealizedProfit", "unrealizedPnl", "pnl", "profit"]
            )
            out.append(
                {
                    "symbol": symbol,
                    "qty": qty,
                    "quantity": qty,
                    "avg_cost_vnd": avg_cost,
                    "avg_price": avg_cost,
                    "current_price_vnd": current_price,
                    "unrealized_pnl_vnd": unrealized,
                    "market_value_vnd": qty * current_price if current_price > 0 else 0.0,
                }
            )
        return out

    def get_open_orders(self) -> List[Dict[str, Any]]:
        if not self._logged_in:
            self.login()
        sub = self._sub_account_no()
        orders = self._api.fetch_orders(sub)
        open_statuses = {"new", "pending", "partiallyfilled", "partially_filled", "open", "queued"}
        out: List[Dict[str, Any]] = []
        for order in orders:
            status = _first_str(order, ["orderStatus", "status", "state"]).lower()
            if status in ("filled", "cancelled", "canceled", "rejected", "expired"):
                continue
            if status and status not in open_statuses and status not in ("", "working"):
                continue
            side_raw = _first_str(order, ["side", "orderSide"]).upper()
            side = "BUY" if side_raw in ("B", "BUY", "1") else "SELL"
            out.append(
                {
                    "order_id": _first_str(order, ["id", "orderId", "order_id"]),
                    "symbol": _first_str(order, ["symbol", "stockSymbol"]).upper(),
                    "side": side,
                    "qty": int(_first_numeric(order, ["quantity", "qty", "orderQty"])),
                    "price": _first_numeric(order, ["price", "orderPrice", "limitPrice"]),
                    "order_type": _first_str(order, ["orderType", "type"], "LO"),
                    "status": status or "open",
                    "created_at": _first_str(order, ["createdDate", "createdAt", "orderTime"]),
                }
            )
        return out

    def get_trade_capacity(self, symbol: str, price: float, side: str) -> Dict[str, Any]:
        return {"max_quantity": 0, "status": "read_only", "symbol": symbol}

    def _place_order_impl(self, order: Dict[str, Any]) -> BrokerOrder:
        self._require_live_gate()
        raise NotImplementedError(
            "DNSE place_order not implemented — Stage 2 is read-only shadow only."
        )

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        raise NotImplementedError("DNSE cancel_order not implemented — Stage 2 read-only only.")

    def get_order_list(self) -> List[Dict[str, Any]]:
        return [
            {
                "order_id": o["order_id"],
                "symbol": o["symbol"],
                "side": o["side"],
                "quantity": o["qty"],
                "price": o["price"],
                "state": o["status"].upper(),
            }
            for o in self.get_open_orders()
        ]

    def get_order_detail(self, order_id: str) -> Dict[str, Any]:
        for o in self.get_open_orders():
            if o["order_id"] == order_id:
                return o
        return {"error": "not_found", "order_id": order_id}

    def _require_live_gate(self) -> None:
        if not self.config.live_dnse_orders_allowed():
            raise LiveTradingDisabledError(
                "DNSE live orders disabled. Require LIVE_TRADING=true, "
                "DRY_RUN=false, CONFIRM_LIVE_BROKER=DNSE, BROKER=dnse, "
                "max_order_value_vnd > 0"
            )
