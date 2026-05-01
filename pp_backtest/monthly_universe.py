from __future__ import annotations

"""
pp_backtest/monthly_universe.py

Build a monthly point-in-time eligibility map for the Pocket Pivot backtest.

Eligibility per symbol, per month_start (first trading day of calendar month):
- listed_flag: symbol has at least 1 bar before month_start
- min_history_flag: at least `min_history_bars` trading bars before month_start
- adtv20 / adtv50: trailing average traded value over last 20/50 trading days
- active_flag: symbol has at least 1 bar on/after month_start (not delisted)
- eligible_flag: listed_flag & min_history_flag & liquidity_flag & active_flag

Outputs CSV with:
symbol, month_start, adtv20, adtv50, listed_flag, min_history_flag, active_flag, eligible_flag
"""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parent.parent
_PP = Path(__file__).resolve().parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_PP) not in sys.path:
    sys.path.insert(0, str(_PP))

try:
    from pp_backtest.data import fetch_ohlcv_fireant
    from pp_backtest.universe_liquidity import get_trading_calendar
    from pp_backtest.date_utils import detect_latest_raw_date
except ImportError:
    from data import fetch_ohlcv_fireant
    from universe_liquidity import get_trading_calendar
    from date_utils import detect_latest_raw_date


LIQ_THRESHOLD_ADTV20 = 2_000_000_000.0  # 2bn VND
LIQ_THRESHOLD_ADTV50 = 4_000_000_000.0  # 4bn VND
MIN_HISTORY_BARS = 100  # minimum daily bars before month_start


def _load_universe(path: Path) -> list[str]:
    txt = path.read_text(encoding="utf-8").strip().splitlines()
    return [ln.strip().upper() for ln in txt if ln.strip() and not ln.strip().startswith("#")]


@dataclass
class MonthlyUniverseConfig:
    universe_path: Path = _REPO / "config" / "universe_full_from_user.txt"
    start: str = "2012-01-01"
    end: str = "2026-02-21"
    min_history_bars: int = MIN_HISTORY_BARS
    liq_thr_adtv20: float = LIQ_THRESHOLD_ADTV20
    liq_thr_adtv50: float = LIQ_THRESHOLD_ADTV50


def _first_trading_day_of_month(calendar: pd.DatetimeIndex, year: int, month: int) -> pd.Timestamp | None:
    for d in calendar:
        if d.year == year and d.month == month:
            return d
    return None


def build_monthly_universe(cfg: MonthlyUniverseConfig, fetch: Callable[[str, str, str], pd.DataFrame]) -> pd.DataFrame:
    print(f"[monthly_universe] cfg.start={cfg.start} cfg.end={cfg.end}", flush=True)
    start_ts = pd.Timestamp(cfg.start)
    end_ts = pd.Timestamp(cfg.end)

    # Trading calendar from VN30 as proxy
    print("[monthly_universe] building trading calendar from VN30...", flush=True)
    calendar = get_trading_calendar(fetch, cfg.start, cfg.end)
    if calendar.empty:
        raise RuntimeError("Empty trading calendar from VN30.")
    print(
        f"[monthly_universe] calendar size={len(calendar)} "
        f"range={calendar.min()} -> {calendar.max()}",
        flush=True,
    )

    # Monthly month_start dates (first trading day of each month)
    months = []
    y, m = start_ts.year, start_ts.month
    while (y < end_ts.year) or (y == end_ts.year and m <= end_ts.month):
        ms = _first_trading_day_of_month(calendar, y, m)
        if ms is not None and start_ts <= ms <= end_ts:
            months.append(ms)
        # increment month
        if m == 12:
            y += 1
            m = 1
        else:
            m += 1

    if not months:
        raise RuntimeError("No month_start dates found in calendar range.")
    print(f"[monthly_universe] month_start count={len(months)} last={months[-1]}", flush=True)

    # Load candidate symbols
    symbols = _load_universe(cfg.universe_path)
    if not symbols:
        raise RuntimeError(f"No symbols loaded from {cfg.universe_path}")
    print(f"[monthly_universe] universe size={len(symbols)} from {cfg.universe_path}", flush=True)

    # Fetch daily data once per symbol over extended window
    lookback_start = (start_ts - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
    print(f"[monthly_universe] fetching daily data from {lookback_start} to {cfg.end}", flush=True)
    data_by_sym: dict[str, pd.DataFrame] = {}
    for idx, sym in enumerate(symbols, 1):
        try:
            df = fetch(sym, lookback_start, cfg.end)
        except Exception as e:
            if idx % 50 == 0:
                print(f"[monthly_universe] fetch failed for {sym}: {e}", flush=True)
            continue
        if df.empty or "date" not in df.columns:
            continue
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        df = df.sort_values("date").reset_index(drop=True)
        df["value"] = df["close"].astype(float) * df["volume"].astype(float)
        data_by_sym[sym] = df
        if idx % 50 == 0:
            print(f"[monthly_universe] fetched {len(data_by_sym)}/{len(symbols)} symbols", flush=True)
    print(f"[monthly_universe] total symbols with data={len(data_by_sym)}", flush=True)

    rows: list[dict] = []
    for mi, ms in enumerate(months, 1):
        cutoff = ms  # month_start
        if mi % 6 == 1:
            print(f"[monthly_universe] processing month {mi}/{len(months)} cutoff={cutoff}", flush=True)
        for sym, df in data_by_sym.items():
            hist = df[df["date"] < cutoff]
            future = df[df["date"] >= cutoff]

            listed_flag = not hist.empty
            min_history_flag = len(hist) >= cfg.min_history_bars
            active_flag = not future.empty

            # trailing 50 trading days for liquidity
            hist_tail = hist.tail(50)
            if hist_tail.empty:
                adtv20 = np.nan
                adtv50 = np.nan
            else:
                value = hist_tail["value"].astype(float)
                adtv50 = float(value.mean())
                last20 = hist_tail.tail(20)
                adtv20 = float(last20["value"].mean()) if not last20.empty else float("nan")

            liquidity_flag = bool(
                (adtv20 is not np.nan)
                and (adtv50 is not np.nan)
                and (adtv20 >= cfg.liq_thr_adtv20)
                and (adtv50 >= cfg.liq_thr_adtv50)
            )

            eligible_flag = bool(listed_flag and min_history_flag and active_flag and liquidity_flag)

            rows.append(
                {
                    "symbol": sym,
                    "month_start": ms,
                    "adtv20": adtv20,
                    "adtv50": adtv50,
                    "listed_flag": listed_flag,
                    "min_history_flag": min_history_flag,
                    "active_flag": active_flag,
                    "eligible_flag": eligible_flag,
                }
            )

    df_out = pd.DataFrame(rows)
    df_out["month_start"] = pd.to_datetime(df_out["month_start"]).dt.strftime("%Y-%m-%d")
    return df_out


def main(args: object | None = None) -> None:
    cfg = MonthlyUniverseConfig()
    if args and getattr(args, "start", None):
        cfg.start = args.start
    if args and getattr(args, "end", None):
        cfg.end = args.end
    else:
        detected = detect_latest_raw_date()
        if detected:
            cfg.end = detected
    if args and getattr(args, "universe", None):
        p = Path(args.universe)
        cfg.universe_path = p if p.is_absolute() else _REPO / p

    df = build_monthly_universe(cfg, fetch_ohlcv_fireant)
    out_path = _PP / "monthly_universe_eligibility.csv"
    df.to_csv(out_path, index=False)
    print(f"[monthly_universe] wrote {len(df)} rows to {out_path}")


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None, help="End date (YYYY-MM-DD); if omitted, auto-detect from data/stocks/*.csv")
    p.add_argument(
        "--universe",
        default="config/universe_full_from_user.txt",
        help="Universe symbols file (one symbol per line).",
    )
    args = p.parse_args()
    main(args=args)

