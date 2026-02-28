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

    # Earnings acceleration flag
    if cfg.require_earnings_accel:
        flag = _accel_flag(getattr(row, "earnings_qoq_accel_flag", None))
        if flag is False:
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

    return True

