"""Broker-layer hard caps — last-resort backstop independent of signal logic."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, FrozenSet, Optional, Set

logger = logging.getLogger(__name__)

_LIMIT_ORDER_TYPES = frozenset({"LO", "LIMIT"})
_MARKET_ORDER_TYPES = frozenset({"ATO", "ATC", "MP", "MARKET", "MKT"})


class HardCapViolationError(RuntimeError):
    """Raised when a broker-layer hard cap is breached."""


class HaltSignalError(RuntimeError):
    """Raised when HALT_LIVE or kill-switch blocks submission."""


class MisconfigurationError(RuntimeError):
    """Raised when live-mode safety prerequisites are not met."""


@dataclass(frozen=True)
class HardCapPolicy:
    """Broker-scoped submission limits. Use disabled() for paper simulation."""

    enabled: bool = True
    max_order_value_vnd: float = 50_000_000.0
    max_submissions_per_day: int = 3
    allowed_symbols: FrozenSet[str] = field(default_factory=frozenset)

    @classmethod
    def disabled(cls) -> "HardCapPolicy":
        return cls(enabled=False)

    @classmethod
    def from_config_dict(cls, raw: Optional[Dict[str, Any]]) -> "HardCapPolicy":
        if not raw:
            return cls()
        symbols = raw.get("allowed_symbols") or []
        policy = cls(
            enabled=bool(raw.get("enabled", True)),
            max_order_value_vnd=float(raw.get("max_order_value_vnd", 50_000_000)),
            max_submissions_per_day=int(raw.get("max_submissions_per_day", 3)),
            allowed_symbols=frozenset(str(s).upper() for s in symbols),
        )
        policy.log_startup_warnings()
        return policy

    def log_startup_warnings(self) -> None:
        if self.enabled and not self.allowed_symbols:
            logger.warning(
                "HardCapPolicy: allowed_symbols is empty — symbol restriction "
                "is not enforced. Populate config/trading.yaml broker_hard_caps "
                "before Stage 3."
            )

    @staticmethod
    def _order_type(order: Dict[str, Any]) -> str:
        raw = order.get("order_type") or order.get("type") or "LO"
        return str(raw).upper()

    def _check_price_and_order_type(self, order: Dict[str, Any]) -> None:
        """Adapter layer accepts limit orders (LO) with price > 0 only."""
        order_type = self._order_type(order)
        price = float(order.get("price", 0))

        if order_type in _MARKET_ORDER_TYPES or order_type not in _LIMIT_ORDER_TYPES:
            raise HardCapViolationError(
                "Market/ATO/ATC orders not permitted at adapter layer — "
                "use limit orders only"
            )
        if price <= 0:
            raise HardCapViolationError("Limit order with price=0 is invalid")

    def enforce(self, order: Dict[str, Any], *, submissions_today: int) -> None:
        if not self.enabled:
            return
        self._check_price_and_order_type(order)
        symbol = str(order.get("symbol", "")).upper()
        qty = int(order.get("quantity", 0))
        price = float(order.get("price", 0))
        order_value = qty * price

        if self.allowed_symbols and symbol not in self.allowed_symbols:
            raise HardCapViolationError(
                f"Symbol {symbol} not in broker allowed_symbols whitelist"
            )
        if order_value > self.max_order_value_vnd:
            raise HardCapViolationError(
                f"Order value {order_value:,.0f} VND exceeds broker max "
                f"{self.max_order_value_vnd:,.0f} VND"
            )
        if submissions_today >= self.max_submissions_per_day:
            raise HardCapViolationError(
                f"Daily broker submission cap reached ({self.max_submissions_per_day})"
            )


def check_halt_live_file(repo_root: Optional[Any] = None) -> Optional[str]:
    """Return halt reason if HALT_LIVE file exists at repo root, else None."""
    from pathlib import Path

    from src.trading.config import REPO_ROOT

    root = Path(repo_root) if repo_root is not None else REPO_ROOT
    halt = root / "HALT_LIVE"
    if halt.exists():
        return halt.read_text(encoding="utf-8").strip() or "HALT_LIVE file present"
    return None


def check_kill_switch_status(kill_switch: Optional[Dict[str, Any]]) -> Optional[str]:
    if kill_switch and kill_switch.get("status") == "BLOCK":
        reasons = kill_switch.get("reasons") or []
        return "; ".join(reasons) if reasons else "kill_switch BLOCK"
    return None


def enforce_submission_guards(
    order: Dict[str, Any],
    *,
    hard_cap_policy: HardCapPolicy,
    submissions_today: int,
    kill_switch: Optional[Dict[str, Any]] = None,
    check_halt_file: bool = True,
) -> None:
    """Last-mile guards immediately before broker submission."""
    if check_halt_file:
        halt_reason = check_halt_live_file()
        if halt_reason:
            raise HaltSignalError(f"HALT_LIVE: {halt_reason}")
    ks_reason = check_kill_switch_status(kill_switch)
    if ks_reason:
        raise HaltSignalError(f"kill_switch: {ks_reason}")
    hard_cap_policy.enforce(order, submissions_today=submissions_today)


def today_utc() -> str:
    return date.today().isoformat()
