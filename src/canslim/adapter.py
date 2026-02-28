"""
adapter.py
==========
Chuyển đổi data thô từ FireAnt -> CanslimInputs để đưa vào rules engine.
Đây là lớp "keo" giữa data layer và decision layer.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import pandas as pd

from .rules import CanslimInputs
from .primary_trend import compute_primary_trend, get_primary_state
from .fireant_fetcher import (
    fetch_ohlcv,
    fetch_multi_quarters,
    compute_rs_ratings,
)

logger = logging.getLogger(__name__)


def _detect_tactical_market_status(
    index_symbol: str = "VNINDEX",
    end_date: Optional[str] = None,
    lookback_days: int = 120,
) -> str:
    """
    Legacy tactical market regime detector (simple O'Neil-style FTD + DD rules).

    This is the Tier-2 engine (fast tactical layer). Tier-1 primary trend
    gating is applied in build_batch_inputs() before this status is used.
    """
    if end_date is None:
        end_date = datetime.today().strftime("%Y-%m-%d")

    start = (
        datetime.strptime(end_date, "%Y-%m-%d") - pd.Timedelta(days=lookback_days)
    ).strftime("%Y-%m-%d")

    df = fetch_ohlcv(index_symbol, start, end_date, resolution="D")
    if df.empty or len(df) < 20:
        return "unknown"

    df = df.copy()
    df["ma50"] = df["close"].rolling(50).mean()
    df["ma200"] = df["close"].rolling(200, min_periods=100).mean()
    df["pct_chg"] = df["close"].pct_change()

    latest = df.iloc[-1]
    close = latest["close"]
    ma50 = latest["ma50"]
    ma200 = latest["ma200"] if not pd.isna(latest["ma200"]) else close

    # Distribution days: ngày index giảm ≥ 0.2% với volume cao hơn ngày trước
    last20 = df.iloc[-20:].copy()
    last20["vol_prev"] = last20["volume"].shift(1)
    dist_days = (
        (last20["pct_chg"] <= -0.002)
        & (last20["volume"] > last20["vol_prev"])
    ).sum()

    # Follow-through day: trong 25 ngày gần nhất, có ngày tăng ≥ 2% với volume cao
    last25 = df.iloc[-25:]
    ftd_candidate = last25[
        (last25["pct_chg"] >= 0.02)
        & (last25["volume"] > last25["volume"].shift(1))
    ]
    has_ftd = len(ftd_candidate) > 0

    # Regime rules
    if close < ma50 * 0.95 or dist_days >= 6:
        return "downtrend"
    elif close < ma50 or dist_days >= 4:
        return "correction"
    elif has_ftd and dist_days <= 2 and close > ma50:
        return "confirmed_uptrend"
    elif close > ma50 and dist_days <= 3:
        return "uptrend_under_pressure"
    else:
        return "correction"


def _detect_primary_state(
    index_symbol: str,
    date: str,
    breadth_symbols: list[str],
    lookback_days: int = 260,
) -> str:
    """
    Tier-1 primary trend detector using MA + breadth (independent of tactical FTD engine).

    - Uses index_symbol (VNINDEX or VN30) for price / MA.
    - Uses breadth_symbols (e.g., VN30 universe or screen universe) for % above MA50.
    """
    start = (
        datetime.strptime(date, "%Y-%m-%d") - pd.Timedelta(days=lookback_days)
    ).strftime("%Y-%m-%d")

    index_df = fetch_ohlcv(index_symbol, start, date, resolution="D")
    if index_df.empty:
        return "NEUTRAL"

    constituent_prices: dict[str, pd.DataFrame] = {}
    for sym in breadth_symbols:
        try:
            df_sym = fetch_ohlcv(sym, start, date, resolution="D")
        except Exception as e:
            logger.error(f"OHLCV fetch failed for breadth symbol {sym}: {e}")
            continue
        if df_sym.empty:
            continue
        constituent_prices[sym] = df_sym[["date", "close"]].copy()

    primary_df = compute_primary_trend(index_df, constituent_prices)
    return get_primary_state(primary_df, date)


# ---------------------------------------------------------------------------
# Volume average (dùng median để tránh outlier VN)
# ---------------------------------------------------------------------------
def compute_avg_volume(df_daily: pd.DataFrame, window: int = 20) -> float:
    """Dùng median 20 ngày thay vì mean — phù hợp với thanh khoản VN."""
    if len(df_daily) < window:
        return df_daily["volume"].median()
    return df_daily["volume"].iloc[-window - 1: -1].median()


# ---------------------------------------------------------------------------
# Pivot detection (simple: high của base)
# ---------------------------------------------------------------------------
def detect_pivot(df_weekly: pd.DataFrame, base_weeks: int = 6) -> Optional[float]:
    """
    Pivot đơn giản: high của n tuần gần nhất (base period).
    Production: thay bằng cup-with-handle detector từ technicals.py.
    """
    if len(df_weekly) < base_weeks:
        return None
    recent = df_weekly.iloc[-base_weeks:]
    return float(recent["high"].max())


# ---------------------------------------------------------------------------
# Main adapter
# ---------------------------------------------------------------------------
@dataclass
class AdapterContext:
    """Context cần thiết để build CanslimInputs cho 1 symbol tại 1 thời điểm."""
    symbol: str
    date: str                                # "YYYY-MM-DD" — ngày đánh giá
    rs_universe_ratings: Optional[pd.Series] = None  # pre-computed RS để tránh gọi lại nhiều lần
    market_status: Optional[str] = None      # pre-computed market regime
    # Position context (None nếu chưa có vị thế)
    entry_price: Optional[float] = None
    entry_date: Optional[str] = None
    leader_stock: Optional[bool] = None


def build_canslim_inputs(ctx: AdapterContext) -> Optional[CanslimInputs]:
    """
    Fetch data và build CanslimInputs hoàn chỉnh từ FireAnt.

    Returns None nếu data không đủ.
    """
    # --- OHLCV ---
    try:
        df_daily = fetch_ohlcv(
            ctx.symbol,
            start=_date_offset(ctx.date, -300),
            end=ctx.date,
            resolution="D",
        )
        df_weekly = fetch_ohlcv(
            ctx.symbol,
            start=_date_offset(ctx.date, -400),
            end=ctx.date,
            resolution="W",
        )
    except Exception as e:
        logger.error(f"OHLCV fetch failed for {ctx.symbol}: {e}")
        return None

    if df_daily.empty or len(df_daily) < 20:
        logger.warning(f"{ctx.symbol}: insufficient OHLCV data")
        return None

    # --- Price & Volume ---
    current_price = float(df_daily.iloc[-1]["close"])
    avg_vol = compute_avg_volume(df_daily, window=20)
    today_vol = float(df_daily.iloc[-1]["volume"])
    breakout_volume_ratio = today_vol / avg_vol if avg_vol > 0 else None

    # --- Pivot ---
    pivot = detect_pivot(df_weekly, base_weeks=8) if not df_weekly.empty else None

    # --- Fundamentals ---
    try:
        fund_df = fetch_multi_quarters(ctx.symbol, n_quarters=6)
    except Exception as e:
        logger.error(f"Fundamentals fetch failed for {ctx.symbol}: {e}")
        fund_df = pd.DataFrame()

    q_eps_yoy = None
    q_sales_yoy = None
    sales_accel = None

    if not fund_df.empty:
        # Lấy quý gần nhất có đủ YoY
        latest = fund_df.dropna(subset=["eps_yoy", "revenue_yoy"])
        if not latest.empty:
            last_row = latest.iloc[-1]
            q_eps_yoy = float(last_row["eps_yoy"])
            q_sales_yoy = float(last_row["revenue_yoy"])
            sales_accel = bool(last_row.get("revenue_accel", False))

    # --- RS Rating ---
    rs_rating = None
    if ctx.rs_universe_ratings is not None and ctx.symbol in ctx.rs_universe_ratings:
        rs_rating = int(ctx.rs_universe_ratings[ctx.symbol])

    # --- Position context ---
    gain_from_entry = None
    drawdown_from_entry = None
    weeks_since_entry = None

    if ctx.entry_price and ctx.entry_date:
        gain = (current_price - ctx.entry_price) / ctx.entry_price
        gain_from_entry = gain
        drawdown_from_entry = gain  # âm nếu lỗ

        entry_dt = datetime.strptime(ctx.entry_date, "%Y-%m-%d")
        current_dt = datetime.strptime(ctx.date, "%Y-%m-%d")
        weeks_since_entry = (current_dt - entry_dt).days / 7.0

    # --- Market status ---
    market_status = ctx.market_status  # pre-computed ở pipeline level

    return CanslimInputs(
        # Fundamentals
        q_eps_yoy=q_eps_yoy,
        q_sales_yoy=q_sales_yoy,
        sales_accel=sales_accel,
        margin_yoy=None,  # optional: thêm nếu parse được gross margin từ FireAnt
        # Leadership
        rs_rating=rs_rating,
        # Trade context
        price=current_price,
        pivot=pivot,
        breakout_volume_ratio=breakout_volume_ratio,
        # Position context
        entry_price=ctx.entry_price,
        days_since_entry=int(weeks_since_entry * 7) if weeks_since_entry else None,
        weeks_since_entry=weeks_since_entry,
        gain_from_entry=gain_from_entry,
        drawdown_from_entry=drawdown_from_entry,
        max_gain_since_entry=None,  # tracking riêng trong backtest engine
        # Market
        market_status=market_status,
        leader_stock=ctx.leader_stock,
    )


# ---------------------------------------------------------------------------
# Pipeline helper: build inputs cho nhiều symbols cùng lúc
# ---------------------------------------------------------------------------
def build_batch_inputs(
    symbols: list[str],
    date: str,
    rs_universe_symbols: Optional[list[str]] = None,
    index_symbol: str = "VNINDEX",
    positions: Optional[dict] = None,  # {symbol: {"entry_price": x, "entry_date": y}}
) -> dict[str, Optional[CanslimInputs]]:
    """
    Build CanslimInputs cho cả list symbols.
    Pre-compute market_status và RS ratings một lần để tránh duplicate calls.

    positions: dict vị thế đang giữ, nếu có.
    """
    logger.info(f"[Pipeline] Date={date}, symbols={len(symbols)}")

    # 1. Market regime (Tier-1 primary + Tier-2 tactical)
    logger.info("Computing market regime (Tier-1 primary + Tier-2 tactical)...")

    breadth_universe = rs_universe_symbols or symbols
    primary_state = _detect_primary_state(
        index_symbol=index_symbol,
        date=date,
        breadth_symbols=breadth_universe,
    )
    tactical_status = _detect_tactical_market_status(index_symbol, end_date=date)

    if primary_state == "DOWN":
        market_status = "downtrend"
    elif primary_state == "NEUTRAL":
        market_status = "correction"
    else:  # primary_state == "UP"
        market_status = tactical_status

    logger.info(f"Primary state: {primary_state}, tactical: {tactical_status}, combined: {market_status}")

    # 2. RS ratings (compute 1 lần cho cả universe)
    rs_ratings = None
    if rs_universe_symbols:
        logger.info(f"Computing RS ratings for {len(rs_universe_symbols)} symbols...")
        rs_ratings = compute_rs_ratings(rs_universe_symbols, end_date=date)

    # 3. Build inputs per symbol
    results = {}
    for sym in symbols:
        pos = (positions or {}).get(sym, {})
        ctx = AdapterContext(
            symbol=sym,
            date=date,
            rs_universe_ratings=rs_ratings,
            market_status=market_status,
            entry_price=pos.get("entry_price"),
            entry_date=pos.get("entry_date"),
            leader_stock=pos.get("leader_stock"),
        )
        results[sym] = build_canslim_inputs(ctx)

    return results


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------
def _date_offset(date_str: str, days: int) -> str:
    """Tính ngày offset từ date_str."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return (dt + pd.Timedelta(days=days)).strftime("%Y-%m-%d")

