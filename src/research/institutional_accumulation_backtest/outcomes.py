from __future__ import annotations

import numpy as np
import pandas as pd


HORIZONS = (5, 10, 20, 60, 120)


def _forward_return(prices: np.ndarray, i: int, h: int) -> float | None:
    j = i + h
    if j >= len(prices):
        return None
    if prices[i] <= 0:
        return None
    return float(prices[j] / prices[i] - 1.0)


def _forward_max_dd(prices: np.ndarray, i: int, h: int) -> float | None:
    j = i + h
    if j >= len(prices):
        return None
    window = prices[i : j + 1]
    peak = window[0]
    mdd = 0.0
    for px in window[1:]:
        peak = max(peak, px)
        mdd = min(mdd, px / peak - 1.0)
    return float(mdd)


def _forward_mfe(prices: np.ndarray, i: int, h: int) -> float | None:
    j = i + h
    if j >= len(prices):
        return None
    base = prices[i]
    if base <= 0:
        return None
    return float(np.max(prices[i + 1 : j + 1]) / base - 1.0)


def compute_forward_outcomes(panel: pd.DataFrame, prices_by_ticker: dict[str, pd.DataFrame], bench: pd.DataFrame) -> pd.DataFrame:
    bench = bench.copy().sort_values("date")
    bench["date"] = pd.to_datetime(bench["date"], errors="coerce").dt.normalize()
    bench = bench.dropna(subset=["date"])
    bench_map = {pd.Timestamp(d).normalize(): i for i, d in enumerate(bench["date"])}
    bench_open = bench["open"].astype(float).to_numpy()
    bench_close = bench["close"].astype(float).to_numpy()
    rows: list[dict] = []

    for ticker, g in panel.groupby("ticker"):
        px = prices_by_ticker.get(ticker)
        if px is None or px.empty:
            continue
        px = px.copy().sort_values("date")
        px_dates = pd.to_datetime(px["date"], errors="coerce").dt.normalize()
        idx_by_date = {pd.Timestamp(d).normalize(): i for i, d in enumerate(px_dates)}
        open_arr = px["open"].astype(float).to_numpy()
        close_arr = px["close"].astype(float).to_numpy()

        for _, r in g.iterrows():
            dt = pd.Timestamp(r["scan_date"]).normalize()
            i = idx_by_date.get(dt)
            bi = bench_map.get(dt)
            out = dict(r)
            if i is None or bi is None or i + 1 >= len(open_arr) or bi + 1 >= len(bench_open):
                for h in HORIZONS:
                    out[f"ret_{h}d"] = None
                    out[f"vnindex_ret_{h}d"] = None
                    out[f"excess_ret_{h}d_vs_vnindex"] = None
                out["entry_date"] = None
                out["entry_price_open_t1"] = None
                out["entry_price_close_t"] = None
                rows.append(out)
                continue

            out["entry_date"] = str(px_dates.iloc[i + 1].date())
            out["entry_price_open_t1"] = float(open_arr[i + 1])
            out["entry_price_close_t"] = float(close_arr[i])

            for h in HORIZONS:
                stock_ret = _forward_return(open_arr, i + 1, h)
                bench_ret = _forward_return(bench_open, bi + 1, h)
                out[f"ret_{h}d"] = stock_ret
                out[f"vnindex_ret_{h}d"] = bench_ret
                out[f"excess_ret_{h}d_vs_vnindex"] = (
                    None if stock_ret is None or bench_ret is None else float(stock_ret - bench_ret)
                )
                out[f"exit_date_{h}d"] = (
                    str(px_dates.iloc[i + 1 + h].date()) if i + 1 + h < len(px_dates) else None
                )
            out["max_dd_20d"] = _forward_max_dd(open_arr, i + 1, 20)
            out["max_dd_60d"] = _forward_max_dd(open_arr, i + 1, 60)
            out["max_favorable_excursion_20d"] = _forward_mfe(open_arr, i + 1, 20)
            out["max_favorable_excursion_60d"] = _forward_mfe(open_arr, i + 1, 60)
            out["hit_dd_minus_5pct_60d"] = (
                None if out["max_dd_60d"] is None else bool(out["max_dd_60d"] <= -0.05)
            )
            out["hit_dd_minus_10pct_60d"] = (
                None if out["max_dd_60d"] is None else bool(out["max_dd_60d"] <= -0.10)
            )
            rows.append(out)
    return pd.DataFrame(rows)
