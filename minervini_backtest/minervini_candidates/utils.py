"""
Utilities for Minervini candidate filter.
FA gate (Mark-tight + earnings accel), price feature computation, technical signals.
Reuses exact definitions from Phase 2: breakout_20d, ma5_gt_ma10_gt_ma20.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd


# FA gate thresholds (Mark-tight + earnings acceleration)
SALES_YOY_MIN = 15.0
ROE_MIN = 15.0
EARNINGS_YOY_MIN = 20.0
DEBT_TO_EQUITY_MAX = 1.5
MARGIN_YOY_MIN = 0.0
REQUIRE_EARNINGS_ACCEL = True
EPS_YOY_MIN_OPTIONAL = 20.0  # optional; do not fail if missing

MIN_BARS_FOR_TECH = 21  # need 20 prior closes + today for high20 and ma20


def _safe_float(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    try:
        f = float(value)
        return None if np.isnan(f) else f
    except (TypeError, ValueError):
        return None


def load_fa_latest_per_symbol(fa_csv: Path) -> pd.DataFrame:
    """
    Load FA CSV and keep only the latest report_date row per symbol.
    Also ensures report_date is datetime and symbol is string.
    """
    df = pd.read_csv(fa_csv)
    if "symbol" not in df.columns or "report_date" not in df.columns:
        raise ValueError("FA CSV must contain 'symbol' and 'report_date'.")
    df["report_date"] = pd.to_datetime(df["report_date"])
    df["symbol"] = df["symbol"].astype(str).str.strip().str.upper()
    df = df.sort_values(["symbol", "report_date"]).reset_index(drop=True)
    latest = df.groupby("symbol", as_index=False).last()
    return latest


def fa_gate_with_reasons(row: pd.Series) -> Tuple[bool, List[str]]:
    """
    Evaluate FA gate (Mark-tight + earnings accel). Returns (pass, fail_reasons).
    Does not modify existing FA computation; implements same thresholds for screening.
    """
    reasons: List[str] = []

    # Required
    sales = _safe_float(row.get("sales_yoy"))
    if sales is None:
        reasons.append("missing sales_yoy")
    elif sales < SALES_YOY_MIN:
        reasons.append(f"sales_yoy<{SALES_YOY_MIN}")

    roe = _safe_float(row.get("roe"))
    if roe is None:
        reasons.append("missing roe")
    elif roe < ROE_MIN:
        reasons.append(f"roe<{ROE_MIN}")

    earnings = _safe_float(row.get("earnings_yoy"))
    if earnings is None:
        reasons.append("missing earnings_yoy")
    elif earnings < EARNINGS_YOY_MIN:
        reasons.append(f"earnings_yoy<{EARNINGS_YOY_MIN}")

    dte = _safe_float(row.get("debt_to_equity"))
    if dte is None:
        reasons.append("missing debt_to_equity")
    elif dte > DEBT_TO_EQUITY_MAX:
        reasons.append(f"debt_to_equity>{DEBT_TO_EQUITY_MAX}")

    if REQUIRE_EARNINGS_ACCEL:
        accel = row.get("earnings_qoq_accel_flag")
        if accel is None or pd.isna(accel):
            reasons.append("missing earnings_accel_flag")
        else:
            try:
                if int(accel) != 1:
                    reasons.append("earnings_accel=False")
            except (TypeError, ValueError):
                reasons.append("earnings_accel=False")

    # margin_yoy_min = 0 if available (use gross_margin_yoy)
    margin = _safe_float(row.get("gross_margin_yoy"))
    if margin is not None and margin < MARGIN_YOY_MIN:
        reasons.append(f"gross_margin_yoy<{MARGIN_YOY_MIN}")

    # eps_yoy optional: do not add to reasons for fail, only record NA if missing
    pass_ = len(reasons) == 0
    return pass_, reasons


def load_price_data(price_dir: Path) -> Dict[str, pd.DataFrame]:
    """Load all CSV in price_dir. Each file: symbol.csv with date, open, high, low, close, volume."""
    price_dir = Path(price_dir)
    if not price_dir.exists():
        return {}
    out: Dict[str, pd.DataFrame] = {}
    for fp in price_dir.glob("*.csv"):
        sym = fp.stem.upper()
        try:
            df = pd.read_csv(fp)
            cols = {c: c.lower() for c in df.columns}
            for cap in ["Date", "Open", "High", "Low", "Close", "Volume"]:
                if cap in df.columns and cap.lower() not in df.columns:
                    df = df.rename(columns={cap: cap.lower()})
            for c in ["date", "open", "high", "low", "close", "volume"]:
                if c not in df.columns:
                    break
            else:
                df["date"] = pd.to_datetime(df["date"])
                df = df.sort_values("date").drop_duplicates(subset=["date"], keep="last")
                out[sym] = df
        except Exception:
            continue
    return out


def get_asof_date(price_data: Dict[str, pd.DataFrame], prefer_symbol: str = "VNINDEX") -> pd.Timestamp | None:
    """Latest common trading date from prefer_symbol or any series."""
    if prefer_symbol in price_data and not price_data[prefer_symbol].empty:
        return price_data[prefer_symbol]["date"].max()
    for df in price_data.values():
        if df is not None and not df.empty:
            return df["date"].max()
    return None


def price_features_at_asof(px: pd.DataFrame, asof: pd.Timestamp) -> Dict[str, float] | None:
    """
    Compute at asof: close, high20 (max close prior 20 days), ma5/10/20, vol_med20, adv20 (VND).
    high20 uses prior 20 trading days only (excl. today), matching breakout_20d definition.
    Returns None and reason via exception or insufficient history.
    """
    px = px[px["date"] <= asof].sort_values("date").tail(MIN_BARS_FOR_TECH)
    if len(px) < MIN_BARS_FOR_TECH:
        return None

    close = px["close"].astype(float)
    volume = px["volume"].astype(float)

    # Prior 20 days max (excl. today): rolling(20).max().shift(1) on last row
    high20_prev = close.rolling(20, min_periods=20).max().shift(1).iloc[-1]
    close_today = close.iloc[-1]
    ma5 = close.rolling(5, min_periods=5).mean().iloc[-1]
    ma10 = close.rolling(10, min_periods=10).mean().iloc[-1]
    ma20 = close.rolling(20, min_periods=20).mean().iloc[-1]
    vol_med20 = volume.rolling(20, min_periods=20).median().iloc[-1]
    adv20 = (close * volume).rolling(20, min_periods=20).mean().iloc[-1]

    return {
        "close": float(close_today),
        "high20": float(high20_prev),
        "ma5": float(ma5),
        "ma10": float(ma10),
        "ma20": float(ma20),
        "vol_med20": float(vol_med20),
        "volume": float(volume.iloc[-1]),
        "liquidity_adv20": float(adv20),
    }


def breakout_20d_at_asof(px: pd.DataFrame, asof: pd.Timestamp) -> bool:
    """
    Exact Phase 2 definition: close_today > max(close over prior 20 trading days).
    """
    feat = price_features_at_asof(px, asof)
    if feat is None:
        return False
    return feat["close"] > feat["high20"]


def ma_stacked_at_asof(px: pd.DataFrame, asof: pd.Timestamp) -> bool:
    """
    Exact Phase 2 definition: ma5 > ma10 > ma20 (ma5_gt_ma10_gt_ma20).
    """
    feat = price_features_at_asof(px, asof)
    if feat is None:
        return False
    return feat["ma5"] > feat["ma10"] and feat["ma10"] > feat["ma20"]


def run_candidate_screen(
    fa_latest: pd.DataFrame,
    price_data: Dict[str, pd.DataFrame],
    asof: pd.Timestamp,
) -> pd.DataFrame:
    """
    For each symbol in fa_latest: evaluate FA gate, then tech (breakout + MA).
    Returns one row per symbol with all required output columns.
    """
    rows: List[Dict[str, Any]] = []
    for _, row in fa_latest.iterrows():
        sym = row["symbol"]
        fa_pass, fa_fail_reasons = fa_gate_with_reasons(row)
        fa_fail_str = "; ".join(fa_fail_reasons) if fa_fail_reasons else ""

        px = price_data.get(sym)
        tech_fail_reason = ""
        if px is None or px.empty:
            tech_breakout = False
            tech_ma = False
            tech_both = False
            close = ma5 = ma10 = ma20 = high20 = np.nan
            liquidity_adv20 = volume = vol_med20 = np.nan
            tech_fail_reason = "no_price_data"
        else:
            feat = price_features_at_asof(px, asof)
            if feat is None:
                tech_breakout = False
                tech_ma = False
                tech_both = False
                close = ma5 = ma10 = ma20 = high20 = np.nan
                liquidity_adv20 = volume = vol_med20 = np.nan
                tech_fail_reason = "TECH_FAIL_INSUFFICIENT_HISTORY"
            else:
                close = feat["close"]
                high20 = feat["high20"]
                ma5, ma10, ma20 = feat["ma5"], feat["ma10"], feat["ma20"]
                volume = feat["volume"]
                vol_med20 = feat["vol_med20"]
                liquidity_adv20 = feat["liquidity_adv20"]
                tech_breakout = close > high20
                tech_ma = ma5 > ma10 and ma10 > ma20
                tech_both = tech_breakout and tech_ma
                tech_fail_reason = ""

        # Candidate: PASS_FA and (breakout or MA)
        is_candidate = fa_pass and (tech_breakout or tech_ma)
        if not is_candidate and not fa_pass and fa_fail_reasons:
            pass
        if is_candidate:
            if tech_both:
                tag = "FA+Both"
            elif tech_breakout:
                tag = "FA+Breakout"
            else:
                tag = "FA+MA"
        else:
            tag = ""

        # earnings_accel_flag: from CSV or computed
        earnings_accel_flag = row.get("earnings_qoq_accel_flag")
        if earnings_accel_flag is None or pd.isna(earnings_accel_flag):
            earnings_accel_flag = ""
        else:
            try:
                earnings_accel_flag = int(earnings_accel_flag)
            except (TypeError, ValueError):
                earnings_accel_flag = ""

        rows.append({
            "asof_date": asof.strftime("%Y-%m-%d"),
            "symbol": sym,
            "fa_pass": fa_pass,
            "fa_fail_reasons": fa_fail_str,
            "sales_yoy": _safe_float(row.get("sales_yoy")),
            "earnings_yoy": _safe_float(row.get("earnings_yoy")),
            "roe": _safe_float(row.get("roe")),
            "debt_to_equity": _safe_float(row.get("debt_to_equity")),
            "margin_yoy": _safe_float(row.get("gross_margin_yoy")),
            "eps_yoy": _safe_float(row.get("eps_yoy")),
            "earnings_accel_flag": earnings_accel_flag,
            "tech_breakout_20d": tech_breakout,
            "tech_ma_stacked": tech_ma,
            "tech_both": tech_both,
            "close": close,
            "ma5": ma5,
            "ma10": ma10,
            "ma20": ma20,
            "high20": high20,
            "liquidity_adv20": liquidity_adv20,
            "volume": volume,
            "vol_med20": vol_med20,
            "tag": tag,
            "tech_fail_reason": tech_fail_reason,
        })

    return pd.DataFrame(rows)
