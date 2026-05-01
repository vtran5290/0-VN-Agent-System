from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import math


@dataclass
class FaFilterConfig:
    eps_yoy_min: float | None = None
    sales_yoy_min: float | None = None
    roe_min: float | None = None
    debt_to_equity_max: float | None = None
    margin_yoy_min: float | None = None
    require_eps_accel: bool = False
    # Earnings-based filters (using net_profit as EPS proxy when shares series missing)
    earnings_yoy_min: float | None = None
    require_earnings_accel: bool = False
    # Berkshire-style: minimum gross margin (decimal, e.g. 0.20 = 20%)
    gross_margin_min: float | None = None


def _safe_float(value: Any) -> float | None:
    """Convert to float, returning None on None/NaN/parse failure."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f):
        return None
    return f


def _accel_flag(value: Any) -> bool | None:
    """
    Normalize acceleration flag.

    Returns:
      - True  -> positive flag (e.g. 1)
      - False -> explicit non-flag (e.g. 0)
      - None  -> missing/NaN/unparseable -> treat as "no information"
    """
    f = _safe_float(value)
    if f is None:
        return None
    try:
        return bool(int(f))
    except (TypeError, ValueError):
        return None


def fa_pass(row: Any, cfg: FaFilterConfig) -> bool:
    """
    Lightweight FA pass rule for cohort construction.

    Expected row fields (some may be missing, in which case that filter is skipped):
      - eps_yoy
      - eps_qoq_accel_flag (bool or 0/1)
      - sales_yoy
      - roe
      - gross_margin_yoy
      - debt_to_equity

    All configured thresholds must be satisfied for the row to pass.
    Missing / NaN values for a given factor cause that factor to be skipped
    rather than treated as automatic failure.
    """
    # EPS YoY
    if cfg.eps_yoy_min is not None:
        v = _safe_float(getattr(row, "eps_yoy", None))
        if v is not None and v < cfg.eps_yoy_min:
            return False

    # Earnings YoY (from net_profit, used as EPS proxy when shares series missing)
    if cfg.earnings_yoy_min is not None:
        v = _safe_float(getattr(row, "earnings_yoy", None))
        if v is not None and v < cfg.earnings_yoy_min:
            return False

    # EPS acceleration flag
    if cfg.require_eps_accel:
        flag = _accel_flag(getattr(row, "eps_qoq_accel_flag", None))
        if flag is False:
            return False

    # Earnings acceleration: 2-step when accel_confidence=high, else 1-step (Mark-style upgrade)
    if cfg.require_earnings_accel:
        accel_conf = getattr(row, "accel_confidence", None)
        two_step = _accel_flag(getattr(row, "earnings_accel_2step_flag", None))
        one_step = _accel_flag(getattr(row, "earnings_qoq_accel_flag", None))
        if accel_conf == "high":
            if two_step is False:
                return False
        else:
            if one_step is False:
                return False
        # Profit guard: current quarter profit > 0 (avoid accel from negative base)
        profit_pos = getattr(row, "profit_positive", None)
        if profit_pos is not None:
            try:
                if int(profit_pos) != 1:
                    return False
            except (TypeError, ValueError):
                return False

    # Sales YoY
    if cfg.sales_yoy_min is not None:
        v = _safe_float(getattr(row, "sales_yoy", None))
        if v is not None and v < cfg.sales_yoy_min:
            return False

    # ROE
    if cfg.roe_min is not None:
        v = _safe_float(getattr(row, "roe", None))
        if v is not None and v < cfg.roe_min:
            return False

    # Margin YoY
    if cfg.margin_yoy_min is not None:
        v = _safe_float(getattr(row, "gross_margin_yoy", None))
        if v is not None and v < cfg.margin_yoy_min:
            return False

    # Debt / Equity
    if cfg.debt_to_equity_max is not None:
        v = _safe_float(getattr(row, "debt_to_equity", None))
        if v is not None and v > cfg.debt_to_equity_max:
            return False

    # Gross margin (level) — Berkshire moat / pricing power
    if cfg.gross_margin_min is not None:
        v = _safe_float(getattr(row, "gross_margin", None))
        if v is not None and v < cfg.gross_margin_min:
            return False

    return True

