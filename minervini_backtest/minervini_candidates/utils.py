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
# Tier A2: loosen earnings_yoy level slightly vs Tier S (only this knob)
EARNINGS_YOY_MIN_A2 = 15.0

MIN_BARS_FOR_TECH = 21  # need 20 prior closes + today for high20 and ma20
TRADING_DAYS_3M = 63  # ~3 months for RS
TRADING_DAYS_6M = 126  # ~6 months for RS_6M
RS_TOP_QUANTILE = 0.80  # pass if RS_3M > 0 or in top 20%


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

    # Earnings accel: 2-step when accel_confidence=high, else 1-step
    if REQUIRE_EARNINGS_ACCEL:
        accel_conf = str(row.get("accel_confidence", "") or "").strip().lower()
        if accel_conf == "high":
            accel = row.get("earnings_accel_2step_flag")
            if accel is None or pd.isna(accel):
                reasons.append("missing earnings_accel_2step_flag")
            else:
                try:
                    if int(accel) != 1:
                        reasons.append("earnings_accel_2step=False")
                except (TypeError, ValueError):
                    reasons.append("earnings_accel_2step=False")
        else:
            accel = row.get("earnings_qoq_accel_flag")
            if accel is None or pd.isna(accel):
                reasons.append("missing earnings_accel_flag")
            else:
                try:
                    if int(accel) != 1:
                        reasons.append("earnings_accel=False")
                except (TypeError, ValueError):
                    reasons.append("earnings_accel=False")
        # Profit guard
        profit_pos = row.get("profit_positive")
        if profit_pos is not None and not pd.isna(profit_pos):
            try:
                if int(profit_pos) != 1:
                    reasons.append("profit_positive=False")
            except (TypeError, ValueError):
                reasons.append("profit_positive=False")

    # margin_yoy_min = 0 if available (use gross_margin_yoy)
    margin = _safe_float(row.get("gross_margin_yoy"))
    if margin is not None and margin < MARGIN_YOY_MIN:
        reasons.append(f"gross_margin_yoy<{MARGIN_YOY_MIN}")

    # eps_yoy optional: do not add to reasons for fail, only record NA if missing
    pass_ = len(reasons) == 0
    return pass_, reasons


def fa_gate_with_reasons_tier(row: pd.Series, tier_mark: str = "S") -> Tuple[bool, List[str], str]:
    """
    Evaluate FA gate by Mark tier.

    Tier S: current Mark-tight gate (unchanged; backwards compatible).
    Tier A2: identical to Tier S except earnings_yoy floor is slightly loosened
             (EARNINGS_YOY_MIN_A2) while keeping acceleration 2-step, profit_positive,
             and other constraints the same.
    Tier A4: identical to Tier S except debt_to_equity is demoted from a hard fail
             to a soft quality flag. This keeps Mark's core growth/acceleration gates
             intact while relaxing a balance-sheet quality screen that may be too harsh
             for breadth on VN leaders.
    """
    tm = (tier_mark or "S").upper()
    # Tier S: reuse existing behavior exactly
    base_pass, base_reasons = fa_gate_with_reasons(row)
    if tm == "S":
        return base_pass, base_reasons, "S"
    if tm == "A2":
        reasons = list(base_reasons)
        earnings = _safe_float(row.get("earnings_yoy"))
        if earnings is not None and earnings >= EARNINGS_YOY_MIN_A2:
            # Remove strict earnings_yoy reason (earnings_yoy<20.0) for A2 tier
            reasons = [r for r in reasons if not r.startswith("earnings_yoy<")]
        return len(reasons) == 0, reasons, "A2"
    if tm == "A3":
        # Tier A3: keep Mark core gates (sales, earnings_yoy, accel 2-step, profit_positive)
        # but demote ROE/debt/margin from hard gate to quality flags.
        reasons = []
        for r in base_reasons:
            if r.startswith("roe<") or r.startswith("debt_to_equity>") or r.startswith("gross_margin_yoy<"):
                continue
            reasons.append(r)
        return len(reasons) == 0, reasons, "A3"
    if tm == "A4":
        # Tier A4: soften only debt_to_equity; keep ROE and gross margin quality checks.
        reasons = [r for r in base_reasons if not r.startswith("debt_to_equity>")]
        return len(reasons) == 0, reasons, "A4"
    # Fallback: treat unknown tier_mark as S
    return base_pass, base_reasons, "S"


def debug_fa_gate_snapshot(
    fa_latest: pd.DataFrame,
    universe: list[str],
    tier_mark_S: str = "S",
    tier_mark_A2: str = "A2",
) -> pd.DataFrame:
    """
    Build a snapshot DataFrame comparing FA gate Tier S vs Tier A2 for each symbol.

    Columns:
      - symbol
      - pass_S, pass_A2
      - earnings_metric_name, earnings_value
      - floor_S, floor_A2
      - fail_reasons_S, fail_reasons_A2
      - flag_only_earnings_floor: True if S fails only due to earnings_yoy floor but A2 passes.
    """
    rows: list[dict[str, Any]] = []
    uni = set(s.upper() for s in universe)
    for _, row in fa_latest.iterrows():
        sym = str(row["symbol"]).upper()
        if uni and sym not in uni:
            continue
        pass_S, reasons_S, _ = fa_gate_with_reasons_tier(row, tier_mark=tier_mark_S)
        pass_A2, reasons_A2, _ = fa_gate_with_reasons_tier(row, tier_mark=tier_mark_A2)
        earnings_val = _safe_float(row.get("earnings_yoy"))
        earnings_metric_name = "earnings_yoy"
        floor_S = EARNINGS_YOY_MIN
        floor_A2 = EARNINGS_YOY_MIN_A2
        # flag_only_earnings_floor: S fails, A2 passes, and all S reasons are earnings_yoy floor
        only_earnings = (
            (not pass_S)
            and pass_A2
            and reasons_S
            and all(r.startswith("earnings_yoy<") for r in reasons_S)
        )
        rows.append(
            {
                "symbol": sym,
                "pass_S": bool(pass_S),
                "pass_A2": bool(pass_A2),
                "earnings_metric_name": earnings_metric_name,
                "earnings_value": earnings_val,
                "floor_S": float(floor_S),
                "floor_A2": float(floor_A2),
                "fail_reasons_S": "; ".join(reasons_S) if reasons_S else "",
                "fail_reasons_A2": "; ".join(reasons_A2) if reasons_A2 else "",
                "flag_only_earnings_floor": bool(only_earnings),
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# E8 FA core gate + scoring (Mark-style, broader Tier A)
# ---------------------------------------------------------------------------

def fa_core_gate_e8(row: pd.Series) -> bool:
    """
    E8 core FA gate (minimal, Mark-style):
      - profit_positive == 1 (if available)
      - sales_yoy >= 15
      - earnings_yoy >= 15
    No ROE/debt/margin/accel hard kill here; those go into score.
    """
    sales = _safe_float(row.get("sales_yoy"))
    earnings = _safe_float(row.get("earnings_yoy"))
    if sales is None or earnings is None:
        return False
    if sales < 15.0 or earnings < 15.0:
        return False
    profit_pos = row.get("profit_positive")
    if profit_pos is not None and not pd.isna(profit_pos):
        try:
            if int(profit_pos) != 1:
                return False
        except (TypeError, ValueError):
            return False
    return True


def fa_score_e8(row: pd.Series, rs_6m_pct: float | None) -> float:
    """
    E8 FA+RS score in [0,100] (Mark-inspired):
      - earnings accel strength (2-step > 1-step)
      - sales strength
      - RS_6m percentile
      - margin_yoy (gross_margin_yoy)
      - debt_to_equity (lower is better)
    """
    score = 0.0

    # Earnings acceleration
    accel_conf = str(row.get("accel_confidence", "") or "").strip().lower()
    accel_2 = row.get("earnings_accel_2step_flag")
    accel_1 = row.get("earnings_qoq_accel_flag")
    try:
        accel_2_ok = int(accel_2) == 1
    except Exception:
        accel_2_ok = False
    try:
        accel_1_ok = int(accel_1) == 1
    except Exception:
        accel_1_ok = False
    if accel_conf == "high" and accel_2_ok:
        score += 30.0
    elif accel_1_ok:
        score += 15.0

    # Sales strength
    sales = _safe_float(row.get("sales_yoy")) or 0.0
    if sales >= 30.0:
        score += 15.0
    elif sales >= 20.0:
        score += 10.0
    elif sales >= 15.0:
        score += 5.0

    # RS_6m percentile (0-100) -> up to 40 points
    if rs_6m_pct is not None:
        try:
            rs_val = float(rs_6m_pct)
            if np.isfinite(rs_val) and rs_val >= 0:
                score += min(max(rs_val, 0.0), 100.0) * 0.4  # 0..40
        except Exception:
            pass

    # Margin YoY (gross_margin_yoy)
    margin = _safe_float(row.get("gross_margin_yoy"))
    if margin is not None:
        if margin >= 5.0:
            score += 10.0
        elif margin >= 0.0:
            score += 5.0

    # Debt-to-equity quality
    dte = _safe_float(row.get("debt_to_equity"))
    if dte is not None:
        if dte <= 0.5:
            score += 5.0
        elif dte <= 1.0:
            score += 3.0
        elif dte <= 1.5:
            score += 1.0

    return float(min(score, 100.0))


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


def compute_rs_3m(
    price_data: Dict[str, pd.DataFrame],
    asof: pd.Timestamp,
    index_symbol: str = "VNINDEX",
) -> Tuple[Dict[str, float], float | None]:
    """
    RS_3M = ret_stock_63d - ret_index_63d (63 trading days).
    Returns (symbol -> rs_3m), and index return for that period (or None).
    """
    return _compute_rs(price_data, asof, index_symbol, TRADING_DAYS_3M)


def compute_rs_6m(
    price_data: Dict[str, pd.DataFrame],
    asof: pd.Timestamp,
    index_symbol: str = "VNINDEX",
) -> Tuple[Dict[str, float], float | None]:
    """
    RS_6M = ret_stock_126d - ret_index_126d (126 trading days).
    Returns (symbol -> rs_6m), and index return for that period (or None).
    """
    return _compute_rs(price_data, asof, index_symbol, TRADING_DAYS_6M)


def _compute_rs(
    price_data: Dict[str, pd.DataFrame],
    asof: pd.Timestamp,
    index_symbol: str,
    trading_days: int,
) -> Tuple[Dict[str, float], float | None]:
    out: Dict[str, float] = {}
    idx_df = price_data.get(index_symbol)
    if idx_df is None or idx_df.empty:
        return out, None
    idx_df = idx_df[idx_df["date"] <= asof].sort_values("date").tail(trading_days + 1)
    if len(idx_df) < trading_days + 1:
        return out, None
    ret_index = (idx_df["close"].iloc[-1] / idx_df["close"].iloc[0]) - 1.0
    for sym, px in price_data.items():
        if sym == index_symbol:
            continue
        if px is None or px.empty:
            out[sym] = np.nan
            continue
        px = px[px["date"] <= asof].sort_values("date").tail(trading_days + 1)
        if len(px) < trading_days + 1:
            out[sym] = np.nan
            continue
        ret_stock = (px["close"].iloc[-1] / px["close"].iloc[0]) - 1.0
        out[sym] = float(ret_stock - ret_index)
    return out, float(ret_index)


def rs_percentile_in_universe(rs_map: Dict[str, float], symbols: List[str]) -> Dict[str, float]:
    """
    Percentile (0-100) within universe: 100 = strongest RS, 0 = weakest.
    Only finite values are ranked; NaN stays NaN.
    """
    vals = pd.Series({s: rs_map.get(s, np.nan) for s in symbols})
    valid = vals.dropna()
    if len(valid) < 2:
        return {s: (100.0 if np.isfinite(vals.get(s, np.nan)) else np.nan) for s in symbols}
    # rank(pct=True): 0-1, 1 = max; * 100 -> 0-100, 100 = best
    pct = vals.rank(pct=True, method="average", ascending=True, na_option="keep") * 100.0
    out: Dict[str, float] = {}
    for s in symbols:
        v = pct.get(s, np.nan)
        out[s] = float(v) if np.isfinite(v) else np.nan
    return out


def run_candidate_screen(
    fa_latest: pd.DataFrame,
    price_data: Dict[str, pd.DataFrame],
    asof: pd.Timestamp,
    index_symbol: str = "VNINDEX",
    tier_mark: str = "S",
) -> pd.DataFrame:
    """
    For each symbol: FA gate, tech (breakout + MA), RS_3M gate.
    Candidate = PASS_FA and (breakout or MA) and pass_rs (RS_3M > 0 or top 20%).
    Adds rs_3m_pct, rs_6m_pct (percentile 0-100 in universe; 100 = strongest).
    """
    rs_3m_map, _ = compute_rs_3m(price_data, asof, index_symbol)
    rs_6m_map, _ = compute_rs_6m(price_data, asof, index_symbol)
    symbols = fa_latest["symbol"].tolist()
    rs_3m_pct_map = rs_percentile_in_universe(rs_3m_map, symbols)
    rs_6m_pct_map = rs_percentile_in_universe(rs_6m_map, symbols)
    valid_rs = [v for v in rs_3m_map.values() if np.isfinite(v)]
    p80 = float(np.percentile(valid_rs, RS_TOP_QUANTILE * 100)) if len(valid_rs) >= 5 else 0.0

    rows: List[Dict[str, Any]] = []
    for _, row in fa_latest.iterrows():
        sym = row["symbol"]
        fa_pass, fa_fail_reasons, fa_tier_mark = fa_gate_with_reasons_tier(row, tier_mark=tier_mark)
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

        rs_3m = rs_3m_map.get(sym, np.nan)
        rs_6m = rs_6m_map.get(sym, np.nan)
        rs_3m_pct = rs_3m_pct_map.get(sym, np.nan)
        rs_6m_pct = rs_6m_pct_map.get(sym, np.nan)
        pass_rs = bool(np.isfinite(rs_3m) and (rs_3m > 0 or rs_3m >= p80))

        # Tier A: FA pass AND tag non-empty (FA+Breakout/FA+MA/FA+Both). Tier W (Option W1): FA pass AND NOT tier_A.
        # Tag only when FA pass AND tech signal (Phase 2 logic unchanged).
        has_tech = tech_breakout or tech_ma
        is_tier_a = fa_pass and has_tech
        is_tier_w = fa_pass and not is_tier_a
        if is_tier_a:
            tier = "A"
            if tech_both:
                tag = "FA+Both"
            elif tech_breakout:
                tag = "FA+Breakout"
            else:
                tag = "FA+MA"
        elif is_tier_w:
            tier = "W"
            tag = "FA"
        else:
            tier = ""
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
            "rs_3m": rs_3m,
            "rs_6m": rs_6m,
            "rs_3m_pct": rs_3m_pct,
            "rs_6m_pct": rs_6m_pct,
            "pass_rs": pass_rs,
            "tier": tier,
            "tag": tag,
            "tech_fail_reason": tech_fail_reason,
            "tier_mark": fa_tier_mark,
        })

    return pd.DataFrame(rows)


def load_fa_latest_per_symbol_asof(fa_df: pd.DataFrame, asof: pd.Timestamp) -> pd.DataFrame:
    """
    From full FA DataFrame (symbol, report_date, ...), keep rows with report_date <= asof
    and take the latest report_date per symbol. For historical hit-rate: FA snapshot at asof.
    """
    if fa_df.empty or "report_date" not in fa_df.columns or "symbol" not in fa_df.columns:
        return pd.DataFrame()
    df = fa_df[fa_df["report_date"] <= asof].copy()
    if df.empty:
        return pd.DataFrame()
    df = df.sort_values(["symbol", "report_date"]).reset_index(drop=True)
    return df.groupby("symbol", as_index=False).last()


def get_quarter_end_trading_dates(
    price_data: Dict[str, pd.DataFrame],
    bench_symbol: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> List[pd.Timestamp]:
    """
    Quarter-end trading dates between start and end from benchmark price series.
    Uses last trading day of each quarter (Q1=Mar, Q2=Jun, Q3=Sep, Q4=Dec) present in data.
    """
    bench = price_data.get(bench_symbol)
    if bench is None or bench.empty or "date" not in bench.columns:
        return []
    dates = pd.to_datetime(bench["date"]).drop_duplicates().sort_values()
    dates = dates[(dates >= start) & (dates <= end)]
    if dates.empty:
        return []
    df = pd.DataFrame({"date": dates})
    df["year"] = df["date"].dt.year
    df["quarter"] = df["date"].dt.quarter
    qends = df.groupby(["year", "quarter"], as_index=False)["date"].max()
    out = sorted(qends["date"].tolist())
    return [pd.Timestamp(d) for d in out]


def get_month_end_trading_dates(
    price_data: Dict[str, pd.DataFrame],
    bench_symbol: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> List[pd.Timestamp]:
    """
    Month-end trading dates between start and end from benchmark price series.
    Last trading day of each month present in data.
    """
    bench = price_data.get(bench_symbol)
    if bench is None or bench.empty or "date" not in bench.columns:
        return []
    dates = pd.to_datetime(bench["date"]).drop_duplicates().sort_values()
    dates = dates[(dates >= start) & (dates <= end)]
    if dates.empty:
        return []
    df = pd.DataFrame({"date": dates})
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    mends = df.groupby(["year", "month"], as_index=False)["date"].max()
    out = sorted(mends["date"].tolist())
    return [pd.Timestamp(d) for d in out]


def forward_return_at_asof(
    px: pd.DataFrame,
    asof: pd.Timestamp,
    forward_days: int,
) -> Tuple[float | None, bool]:
    """
    Forward total return: close(asof+forward_days) / close(asof) - 1.
    Uses trading days (not calendar). Returns (ret, ok); ok=False if insufficient data.
    """
    if px is None or px.empty or "date" not in px.columns or "close" not in px.columns:
        return None, False
    px = px.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    on_or_before = px[px["date"] <= asof]
    if on_or_before.empty:
        return None, False
    close_asof = float(on_or_before["close"].iloc[-1])
    after = px[px["date"] > asof].head(forward_days)
    if len(after) < forward_days:
        return None, False
    close_end = float(after["close"].iloc[-1])
    ret = (close_end / close_asof) - 1.0
    return ret, True
