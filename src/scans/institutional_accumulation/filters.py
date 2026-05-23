from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd

from src.data_loader import load_ohlcv_csv

from .config import ETF_EXCLUSION_SECTORS, ETF_EXCLUSION_SYMBOLS

# Repo convention: FireAnt / data/stocks CSVs store close in thousand-VND (kVND).
PRICE_UNIT_KVND_MAX_MEDIAN = 500.0
VALUE_SCALE_KVND_TO_VND = 1000.0


def read_watchlist(path: Path) -> List[str]:
    if not path.is_file():
        return []
    out: List[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        t = line.strip().upper().split("#")[0].strip()
        if t:
            out.append(t)
    return out


def is_etf_or_open_fund(symbol: str, sector: str) -> bool:
    """Exclude ETF / open-fund vehicles from accumulation scan output."""
    if symbol.upper() in ETF_EXCLUSION_SYMBOLS:
        return True
    if sector in ETF_EXCLUSION_SECTORS:
        return True
    return False


def discover_symbols(stocks_dir: Path, watchlist: Optional[List[str]] = None) -> List[str]:
    if watchlist:
        return sorted({t.upper() for t in watchlist})
    if not stocks_dir.is_dir():
        return []
    skip = {"VNINDEX", "VN30", "HNXINDEX", "UPCOMINDEX"}
    return sorted(p.stem.upper() for p in stocks_dir.glob("*.csv") if p.stem.upper() not in skip)


def detect_price_value_units(df: pd.DataFrame) -> Tuple[str, float, Optional[str]]:
    """
    Explicit unit path for ADV / turnover (replaces implicit median heuristic only).

    Returns:
        price_unit_mode: 'thousand_vnd' | 'full_vnd' | 'unknown'
        value_scale_factor: multiply raw close*volume to full VND
        unit_warning: non-null if ambiguous
    """
    if df.empty or "close" not in df.columns:
        return "unknown", 1.0, "missing_close_column"
    med = float(df["close"].tail(60).median())
    if med <= 0 or not pd.notna(med):
        return "unknown", 1.0, "invalid_median_close"

    if med < PRICE_UNIT_KVND_MAX_MEDIAN:
        return "thousand_vnd", VALUE_SCALE_KVND_TO_VND, None
    if med >= 5000:
        return "full_vnd", 1.0, None
    return "unknown", 1.0, f"ambiguous_close_median_{med:.2f}_verify_units"


def _value_vnd_series(df: pd.DataFrame) -> Tuple[pd.Series, str, float, Optional[str]]:
    x = df.copy()
    if "value" not in x.columns and "close" in x.columns and "volume" in x.columns:
        x["value"] = x["close"] * x["volume"]
    mode, scale, warn = detect_price_value_units(x)
    val = x["value"].astype(float) * scale
    return val, mode, scale, warn


def liquidity_metrics(df: pd.DataFrame) -> dict:
    val, mode, scale, warn = _value_vnd_series(df)
    adv20 = val.tail(20).mean() if len(val) >= 20 else None
    adv50 = val.tail(50).mean() if len(val) >= 50 else None
    return {
        "adv20_value": float(adv20) if adv20 is not None and pd.notna(adv20) else None,
        "adv50_value": float(adv50) if adv50 is not None and pd.notna(adv50) else None,
        "n_bars": len(df),
        "price_unit_mode": mode,
        "value_scale_factor": scale,
        "unit_warning": warn,
    }


def passes_liquidity(
    liq: dict,
    *,
    min_history: int,
    min_adv20: float,
    min_adv50: float,
) -> tuple[bool, str]:
    if liq.get("n_bars", 0) < min_history:
        return False, "insufficient_history"
    a20 = liq.get("adv20_value")
    a50 = liq.get("adv50_value")
    if a20 is None or a20 < min_adv20:
        return False, "low_adv20"
    if a50 is None or a50 < min_adv50:
        return False, "low_adv50"
    return True, "ok"


def load_symbol_ohlcv(stocks_dir: Path, symbol: str) -> Optional[pd.DataFrame]:
    path = stocks_dir / f"{symbol}.csv"
    if not path.is_file():
        return None
    try:
        return load_ohlcv_csv(path)
    except (ValueError, OSError):
        return None


def resolve_benchmark_path(benchmark_dir: Path, ticker: str) -> Path:
    primary = benchmark_dir / f"{ticker}.csv"
    if primary.is_file():
        return primary
    repo = benchmark_dir.parent.parent
    fallback = repo / "minervini_backtest" / "data" / "raw" / f"{ticker}.csv"
    if fallback.is_file():
        return fallback
    stocks_fb = repo / "data" / "stocks" / f"{ticker}.csv"
    if stocks_fb.is_file():
        return stocks_fb
    raise FileNotFoundError(
        f"Benchmark {ticker} not found in {benchmark_dir}, minervini_backtest/data/raw, or data/stocks"
    )


def detect_scan_date(benchmark_path: Path, override: Optional[str] = None) -> str:
    if override:
        return override
    df = load_ohlcv_csv(benchmark_path)
    if df.empty:
        raise ValueError(f"Benchmark empty: {benchmark_path}")
    return pd.Timestamp(df["date"].max()).strftime("%Y-%m-%d")
