"""Simulated paper broker with JSON persistence."""
from __future__ import annotations

import json
import uuid
from src.trading.util.timeutil import utc_now_iso
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.trading.brokers.base import BaseBroker
from src.trading.brokers.hard_caps import HardCapPolicy
from src.trading.config import TradingConfig
from src.trading.models import BrokerOrder, OrderSide, OrderState, Position


class PaperBroker(BaseBroker):
    def __init__(
        self,
        config: TradingConfig,
        state_path: Optional[Path] = None,
        hard_cap_policy: Optional[HardCapPolicy] = None,
        **broker_kwargs: Any,
    ):
        super().__init__(hard_cap_policy or HardCapPolicy.disabled(), **broker_kwargs)
        self.config = config
        self.state_path = state_path or config.paper_broker_state_path
        self._state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        if self.state_path.exists():
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        return {
            "logged_in": False,
            "cash_vnd": self.config.initial_cash_vnd,
            "positions": {},
            "orders": {},
        }

    def _save_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(self._state, indent=2), encoding="utf-8")

    def _append_audit(self, event: Dict[str, Any]) -> None:
        self.config.ensure_dirs()
        line = json.dumps({**event, "ts": utc_now_iso()})
        with open(self.config.audit_log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def login(self) -> Dict[str, Any]:
        self._state["logged_in"] = True
        self._save_state()
        return {"broker": "paper", "status": "ok", "account_id": "PAPER-001"}

    def get_account(self) -> Dict[str, Any]:
        return {
            "account_id": "PAPER-001",
            "broker": "paper",
            "nav_vnd": self._nav(),
            "cash_vnd": self._state["cash_vnd"],
        }

    def get_sub_accounts(self) -> List[Dict[str, Any]]:
        return [{"sub_account_id": "PAPER-001", "type": "cash"}]

    def get_cash_balance(self) -> Dict[str, Any]:
        return {"cash_vnd": float(self._state["cash_vnd"]), "currency": "VND"}

    def get_positions(self) -> List[Dict[str, Any]]:
        out = []
        for sym, pos in self._state.get("positions", {}).items():
            qty = int(pos["quantity"])
            avg = float(pos["avg_price"])
            out.append(
                {
                    "symbol": sym,
                    "quantity": qty,
                    "avg_price": avg,
                    "market_value_vnd": qty * avg,
                }
            )
        return out

    def _nav(self) -> float:
        cash = float(self._state["cash_vnd"])
        pos_val = sum(
            int(p["quantity"]) * float(p["avg_price"])
            for p in self._state.get("positions", {}).values()
        )
        return cash + pos_val

    def get_trade_capacity(self, symbol: str, price: float, side: str) -> Dict[str, Any]:
        if price <= 0:
            return {"max_quantity": 0, "reason": "invalid_price"}
        side_u = side.upper()
        if side_u == OrderSide.BUY.value:
            max_qty = int(self._state["cash_vnd"] // price)
            return {"max_quantity": max_qty, "side": side_u, "symbol": symbol}
        pos = self._state.get("positions", {}).get(symbol, {})
        qty = int(pos.get("quantity", 0))
        return {"max_quantity": qty, "side": side_u, "symbol": symbol}

    def _place_order_impl(self, order: Dict[str, Any]) -> BrokerOrder:
        """Immediate full fill at limit price (single attempt)."""
        symbol = order["symbol"].upper()
        side = order["side"].upper()
        qty = int(order["quantity"])
        price = float(order["price"])
        idem = order.get("idempotency_key", "")
        now = utc_now_iso()
        order_id = f"PAPER-{uuid.uuid4().hex[:12]}"

        if side == OrderSide.BUY.value:
            cost = qty * price
            if cost > self._state["cash_vnd"]:
                bo = BrokerOrder(
                    idempotency_key=idem,
                    broker_order_id=order_id,
                    symbol=symbol,
                    side=side,
                    quantity=qty,
                    price=price,
                    state=OrderState.BROKER_REJECTED,
                    created_at=now,
                    updated_at=now,
                )
                self._state["orders"][order_id] = bo.to_dict()
                self._save_state()
                self._append_audit({"event": "broker_rejected", "order": bo.to_dict()})
                return bo
            self._state["cash_vnd"] -= cost
            pos = self._state["positions"].setdefault(
                symbol, {"quantity": 0, "avg_price": 0.0}
            )
            old_qty = int(pos["quantity"])
            new_qty = old_qty + qty
            if new_qty > 0:
                pos["avg_price"] = (
                    old_qty * float(pos["avg_price"]) + qty * price
                ) / new_qty
            pos["quantity"] = new_qty
        elif side == OrderSide.SELL.value:
            pos = self._state["positions"].get(symbol)
            if not pos or int(pos["quantity"]) < qty:
                bo = BrokerOrder(
                    idempotency_key=idem,
                    broker_order_id=order_id,
                    symbol=symbol,
                    side=side,
                    quantity=qty,
                    price=price,
                    state=OrderState.BROKER_REJECTED,
                    created_at=now,
                    updated_at=now,
                )
                self._state["orders"][order_id] = bo.to_dict()
                self._save_state()
                self._append_audit({"event": "broker_rejected", "order": bo.to_dict()})
                return bo
            pos["quantity"] = int(pos["quantity"]) - qty
            if int(pos["quantity"]) == 0:
                del self._state["positions"][symbol]
            self._state["cash_vnd"] += qty * price
        else:
            raise ValueError(f"Invalid side: {side}")

        bo = BrokerOrder(
            idempotency_key=idem,
            broker_order_id=order_id,
            symbol=symbol,
            side=side,
            quantity=qty,
            price=price,
            state=OrderState.FILLED,
            filled_quantity=qty,
            created_at=now,
            updated_at=now,
        )
        self._state["orders"][order_id] = bo.to_dict()
        self._save_state()
        self._append_audit({"event": "filled", "order": bo.to_dict()})
        return bo

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        od = self._state.get("orders", {}).get(order_id)
        if not od:
            return {"status": "not_found", "order_id": order_id}
        if od.get("state") == OrderState.FILLED.value:
            return {"status": "cannot_cancel_filled", "order_id": order_id}
        od["state"] = OrderState.CANCELLED.value
        self._save_state()
        return {"status": "cancelled", "order_id": order_id}

    def get_order_list(self) -> List[Dict[str, Any]]:
        return list(self._state.get("orders", {}).values())

    def get_order_detail(self, order_id: str) -> Dict[str, Any]:
        od = self._state.get("orders", {}).get(order_id)
        if not od:
            return {"error": "not_found", "order_id": order_id}
        return od

    def get_fills(self) -> List[Dict[str, Any]]:
        return [o for o in self._state.get("orders", {}).values() if o.get("state") == OrderState.FILLED.value]

    def get_open_orders(self) -> List[Dict[str, Any]]:
        return super().get_open_orders()

    def to_portfolio_positions(self) -> List[Position]:
        return [
            Position(
                symbol=sym,
                quantity=int(p["quantity"]),
                avg_price=float(p["avg_price"]),
                market_value_vnd=int(p["quantity"]) * float(p["avg_price"]),
            )
            for sym, p in self._state.get("positions", {}).items()
            if int(p["quantity"]) > 0
        ]
