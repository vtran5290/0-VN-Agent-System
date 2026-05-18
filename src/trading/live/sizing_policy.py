"""Account-level execution sizing (not strategy signal sizing)."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple

import pandas as pd

from src.trading.config import LiveTradingConfig
from src.trading.live.paper_ledger import PaperLedger

POLICY_SCAN_STRICT = "scan_size_strict"
POLICY_CAP_TO_LIMITS = "cap_to_account_limits"
POLICY_CAP_TO_LIQUIDITY = "cap_to_liquidity"
POLICY_REJECT_OVER_CAP = "reject_if_scan_size_exceeds_cap"


def _account_sizing(config: LiveTradingConfig) -> Tuple[str, float]:
    acct = getattr(config, "paper_account", None)
    if acct is not None:
        return (
            str(getattr(acct, "sizing_policy", POLICY_SCAN_STRICT)),
            float(getattr(acct, "min_trade_value_VND", 0)),
        )
    return POLICY_SCAN_STRICT, 0.0


def cash_available_vnd(config: LiveTradingConfig, ledger: Optional[PaperLedger] = None) -> float:
    p = config.paper_broker_state_path
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return float(data.get("cash_vnd", config.initial_cash_vnd))
        except (json.JSONDecodeError, OSError):
            pass
    return float(config.initial_cash_vnd)


def _empty_attribution() -> Dict[str, bool]:
    return {
        "capped_by_max_order_value": False,
        "capped_by_cash": False,
        "capped_by_adv_liquidity": False,
        "capped_by_scan_value": False,
    }


def _cap_attribution(
    scan_value_vnd: float,
    max_order: float,
    cash: float,
    adv_cap: float,
    execution_value: float,
) -> Dict[str, bool]:
    if execution_value >= scan_value_vnd - 1:
        return _empty_attribution()
    attr = _empty_attribution()
    eps = 1.0
    candidates = [
        ("capped_by_max_order_value", max_order),
        ("capped_by_cash", cash),
        ("capped_by_adv_liquidity", adv_cap if adv_cap > 0 else float("inf")),
    ]
    for name, cap_val in candidates:
        if cap_val < scan_value_vnd - eps and abs(cap_val - execution_value) <= eps:
            attr[name] = True
    return attr


def apply_execution_sizing(
    config: LiveTradingConfig,
    scan_value_vnd: float,
    limit_price: float,
    side: str,
    row: pd.Series,
    *,
    ledger: Optional[PaperLedger] = None,
) -> Tuple[float, int, str, str, Dict[str, bool]]:
    """
    Return (execution_value_VND, qty, sizing_policy, sizing_adjustment_reason, cap_attribution).
    SELL paths should not use buy caps — caller handles qty via ledger.
    """
    policy, min_trade = _account_sizing(config)
    if side == "SELL":
        qty = int(scan_value_vnd / limit_price) if limit_price > 0 and scan_value_vnd > 0 else 0
        return scan_value_vnd, qty, policy, "", _empty_attribution()

    if policy == POLICY_SCAN_STRICT:
        qty = int(scan_value_vnd / limit_price) if limit_price > 0 else 0
        attr = _empty_attribution()
        attr["capped_by_scan_value"] = True
        return scan_value_vnd, qty, policy, "", attr

    cash = cash_available_vnd(config, ledger)
    adv_b = float(row.get("adv50_B_VND") or 0)
    adv_cap = adv_b * 1_000_000_000 * float(config.adv_participation)
    max_order = float(config.max_order_value_vnd)
    caps = [scan_value_vnd, max_order, cash]
    if adv_cap > 0:
        caps.append(adv_cap)
    execution_value = min(caps)
    attr = _cap_attribution(scan_value_vnd, max_order, cash, adv_cap, execution_value)

    if policy == POLICY_REJECT_OVER_CAP:
        if scan_value_vnd > max_order:
            return 0.0, 0, policy, "scan_size_exceeds_cap", attr
        qty = int(execution_value / limit_price) if limit_price > 0 else 0
        return execution_value, qty, policy, "", attr

    reason = ""
    if execution_value < scan_value_vnd - 1:
        if policy == POLICY_CAP_TO_LIQUIDITY:
            if attr["capped_by_adv_liquidity"]:
                reason = "liquidity_cap_hit"
            else:
                reason = "capped_to_liquidity"
        else:
            reason = "capped_to_account_limits"
    if min_trade > 0 and execution_value < min_trade:
        return 0.0, 0, policy, "below_min_trade_value", attr
    qty = int(execution_value / limit_price) if limit_price > 0 else 0
    if qty <= 0:
        return 0.0, 0, policy, "below_min_trade_value", attr
    return execution_value, qty, policy, reason, attr
