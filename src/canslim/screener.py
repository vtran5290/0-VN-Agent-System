"""
screener.py
===========
Orchestrate toàn bộ pipeline:
    1. Fetch universe symbols
    2. Compute market regime + RS ratings
    3. Build CanslimInputs cho từng symbol
    4. Chạy pre-buy check
    5. Output watchlist ranked by RS + EPS tier
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from .fireant_fetcher import fetch_all_symbols
from .adapter import build_batch_inputs
from .rules import canslim_pre_buy_check, EpsTier, canslim_position_management

logger = logging.getLogger(__name__)


def _load_symbols_from_file(path: str) -> list[str]:
    """Load universe symbols từ file text (mỗi dòng 1 mã)."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Symbols file not found: {p}")
    raw = p.read_text(encoding="utf-8").splitlines()
    symbols = [line.strip().upper() for line in raw if line.strip() and not line.strip().startswith("#")]
    return symbols


def run_daily_screen(
    date: Optional[str] = None,
    exchange: str = "HOSE",
    custom_symbols: Optional[list[str]] = None,
    symbols_path: Optional[str] = None,
    min_rs: int = 80,
    positions: Optional[dict] = None,
    strict: bool = True,
    keep_all_rows: bool = True,
) -> pd.DataFrame:
    """
    Chạy CANSLIM screener cho 1 ngày.

    Args:
        date: "YYYY-MM-DD", mặc định hôm nay
        exchange: "HOSE" | "HNX" | "UPCOM"
        custom_symbols: nếu có, dùng list này thay vì fetch toàn bộ sàn
        min_rs: ngưỡng RS tối thiểu để đưa vào watchlist
        positions: dict vị thế đang giữ

    Returns:
        DataFrame kết quả, sorted theo RS desc + EPS tier
    """
    if date is None:
        date = datetime.today().strftime("%Y-%m-%d")

    logger.info(f"=== CANSLIM Daily Screen | {date} | {exchange} ===")

    # 1. Universe
    if custom_symbols:
        symbols = [str(s).strip().upper() for s in custom_symbols if str(s).strip()]
    elif symbols_path:
        logger.info(f"Loading symbols from file: {symbols_path}")
        symbols = _load_symbols_from_file(symbols_path)
        logger.info(f"Universe from file: {len(symbols)} symbols")
    else:
        logger.info("Fetching symbol universe from FireAnt...")
        symbols = fetch_all_symbols(exchange)
        logger.info(f"Universe: {len(symbols)} symbols")

    if not symbols:
        logger.error("No symbols to screen!")
        return pd.DataFrame()

    # 2. Build inputs (includes market regime + RS computation)
    inputs_map = build_batch_inputs(
        symbols=symbols,
        date=date,
        rs_universe_symbols=symbols,
        positions=positions or {},
    )

    # 3. Run pre-buy check
    rows = []
    for sym, inputs in inputs_map.items():
        sym = str(sym).strip().upper()

        # Luôn ghi 1 dòng / symbol để tránh "mù" data
        if inputs is None:
            rows.append({
                "symbol": sym,
                "date": date,
                "allow_buy": False,
                "size_suggestion": "no_buy",
                "eps_tier": "C_MISSING",
                "eps_yoy_pct": None,
                "sales_ok": None,
                "sales_yoy_pct": None,
                "rs_rating": None,
                "buy_zone": None,
                "volume_ok": None,
                "market_status": None,
                "price": None,
                "pivot": None,
                "strict_mode": strict,
                "reasons": "DATA_MISSING",
            })
            continue

        result = canslim_pre_buy_check(inputs, rs_min=min_rs, strict=strict)
        rs = inputs.rs_rating

        # Nếu keep_all_rows=False, có thể drop RS<min_rs để tạo watchlist “sạch”
        if not keep_all_rows and rs is not None and rs < min_rs:
            continue

        rows.append({
            "symbol": sym,
            "date": date,
            "allow_buy": result["allow_buy"],
            "size_suggestion": result["size_suggestion"],
            "eps_tier": result["eps_tier"],
            "eps_yoy_pct": f"{inputs.q_eps_yoy*100:.1f}%" if inputs.q_eps_yoy is not None else None,
            "sales_ok": result["sales_ok"],
            "sales_yoy_pct": f"{inputs.q_sales_yoy*100:.1f}%" if inputs.q_sales_yoy is not None else None,
            "rs_rating": rs,
            "buy_zone": result["buy_zone"],
            "volume_ok": result["volume_ok"],
            "market_status": result["market_status"],
            "price": inputs.price,
            "pivot": inputs.pivot,
            "strict_mode": strict,
            "reasons": "; ".join(result["reasons"]) if result["reasons"] else "OK",
        })

    if not rows:
        logger.info("No symbols passed RS filter")
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    # Sort: allow_buy first, then RS desc, then EPS tier
    eps_order = {
        EpsTier.ELITE.value: 0,
        EpsTier.PREFERRED.value: 1,
        EpsTier.MIN_PASS.value: 2,
        EpsTier.FAIL.value: 3,
        None: 4,
    }
    df["_eps_order"] = df["eps_tier"].map(eps_order)
    df = df.sort_values(
        ["allow_buy", "rs_rating", "_eps_order"],
        ascending=[False, False, True],
    ).drop(columns=["_eps_order"]).reset_index(drop=True)

    logger.info(f"Screener done: {len(df)} candidates, {df['allow_buy'].sum()} allow_buy")
    return df


def run_position_monitor(
    positions: dict,  # {symbol: {"entry_price": x, "entry_date": "YYYY-MM-DD"}}
    date: Optional[str] = None,
) -> pd.DataFrame:
    """
    Monitor vị thế đang giữ: stop + profit signals.
    """
    if date is None:
        date = datetime.today().strftime("%Y-%m-%d")

    symbols = list(positions.keys())
    inputs_map = build_batch_inputs(
        symbols=symbols,
        date=date,
        rs_universe_symbols=None,  # không cần RS cho position management
        positions=positions,
    )

    rows = []
    for sym, inputs in inputs_map.items():
        if inputs is None:
            continue
        result = canslim_position_management(inputs)
        rows.append({
            "symbol": sym,
            "action": result["action"],
            "reason": result["reason"],
            "gain_pct": f"{result['gain']*100:.1f}%" if result.get("gain") else None,
            "weeks_held": result.get("weeks"),
            "entry_price": positions[sym].get("entry_price"),
            "current_price": inputs.price,
        })

    return pd.DataFrame(rows) if rows else pd.DataFrame()

