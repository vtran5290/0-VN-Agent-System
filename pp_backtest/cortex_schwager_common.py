"""Shared utilities for Schwager S17/S18/S19 harnesses."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests

from pp_backtest.cortex_book1_common import IS_WINDOW, OOS_WINDOW, PANEL_END, PANEL_START
from pp_backtest.cortex_book2_common import (
    OOS_SUB_WINDOW_A,
    OOS_SUB_WINDOW_B,
    apply_proximity_filter,
    build_signal_filter_map,
    count_oos_trades,
)
from pp_backtest.d1_capital_based_validation import _metrics_from_equity
from pp_backtest.d3_sector_rs_validation import (
    D4_CASH_YIELD,
    apply_size,
    load_sector_map,
    prepare_trades_with_size,
    run_capital_sim,
)
from pp_backtest.sprint2b_common import (
    SIZE_LAGGING_BASE,
    SIZE_LEADING_BASE,
    build_baseline_stack,
    slice_equity_years,
)
from src.data.fireant_client import RESTV2_BASE, _BROWSER_HEADERS, _load_token

REPO = Path(__file__).resolve().parents[1]
OUT_ROOT = REPO / "data" / "research" / "cortex_schwager"
BUY_SELL_CACHE = OUT_ROOT / "buy_sell_cache.parquet"

G1B_FLOOR = 0.516
S1_BASELINE_OOS_MAR = 1.7844
S1_BASELINE_N_OOS = 1732
MAR_TOLERANCE = 0.05
N_TOLERANCE = int(S1_BASELINE_N_OOS * 0.01)
S1_MIN_PROX = 0.85

S17_G1A = 1.850
S18_G1A = 1.844
S19_G1A = 1.820
G_CONTINUATION = 0.55  # S18 G2: OOS sector continuation floor
MIN_SECTOR_MEMBERS = 10
MIN_N_OOS = 30
VIN_SYMBOLS = {"VIC", "VHM", "VRE"}
FIREANT_DELAY = 0.12

IS_START = pd.Timestamp(f"{IS_WINDOW[0]}-01-01")
IS_END = pd.Timestamp(f"{IS_WINDOW[1]}-12-31")
OOS_START = pd.Timestamp(f"{OOS_WINDOW[0]}-01-01")
OOS_END = pd.Timestamp(f"{PANEL_END}")


def year_mask(series: pd.Series, window: tuple[int, int]) -> pd.Series:
    y0, y1 = window
    return (series.dt.year >= y0) & (series.dt.year <= y1)


def signal_date_col(trades: pd.DataFrame) -> pd.Series:
    t = trades.copy()
    if "signal_date" in t.columns:
        sd = pd.to_datetime(t["signal_date"]).dt.normalize()
    else:
        sd = pd.to_datetime(t["entry_date"]).dt.normalize() - pd.tseries.offsets.BDay(1)
    return sd


def run_filtered_sim(stack: dict[str, Any], trades: pd.DataFrame) -> tuple[pd.Series, dict[str, float], int]:
    """D3-sized capital sim on filtered trade subset."""
    if trades.empty:
        eq = pd.Series(dtype=float)
        return eq, {"mar": np.nan, "max_dd": np.nan, "cagr": np.nan}, 0
    sized = apply_size(trades, stack["sctx"], leading=SIZE_LEADING_BASE, lagging=SIZE_LAGGING_BASE)
    prep = prepare_trades_with_size(sized, "rs_score", "_size_mult")
    eq, _, _ = run_capital_sim(prep, stack["ctx"].gate, D4_CASH_YIELD)
    eq_oos = slice_equity_years(eq, OOS_WINDOW[0], OOS_WINDOW[1])
    m = _metrics_from_equity(eq_oos)
    n_oos = count_oos_trades(trades, OOS_WINDOW[0], OOS_WINDOW[1])
    return eq, m, n_oos


def sector_daily_returns(panel: pd.DataFrame, sector_map: dict[str, str]) -> pd.DataFrame:
    p = panel.copy()
    p["date"] = pd.to_datetime(p["date"]).dt.normalize()
    p["sector"] = p["symbol"].astype(str).map(sector_map).fillna("Unknown")
    p = p[p["sector"] != "Unknown"]
    p["ret"] = p.groupby("symbol")["close"].pct_change()
    p = p.dropna(subset=["ret"])
    counts = p.groupby("sector")["symbol"].nunique()
    valid = set(counts[counts >= MIN_SECTOR_MEMBERS].index)
    p = p[p["sector"].isin(valid)]
    return p.groupby(["date", "sector"], as_index=False)["ret"].mean()


def build_sector_triggers(sector_rets: pd.DataFrame, k: float, roll: int = 20) -> pd.DataFrame:
    """Upside sector trigger on day t: ret_t > k * rolling_std and ret_t > 0."""
    rows: list[dict[str, Any]] = []
    for sec, g in sector_rets.groupby("sector"):
        g = g.sort_values("date").set_index("date")
        std = g["ret"].rolling(roll, min_periods=15).std()
        trig = (g["ret"] > k * std) & (g["ret"] > 0)
        nxt = g["ret"].shift(-1)
        for dt in g.index[trig.fillna(False)]:
            rows.append(
                {
                    "date": dt,
                    "sector": sec,
                    "sector_ret": float(g.loc[dt, "ret"]),
                    "next_ret": float(nxt.loc[dt]) if pd.notna(nxt.loc[dt]) else np.nan,
                    "continued": bool(nxt.loc[dt] > 0) if pd.notna(nxt.loc[dt]) else False,
                }
            )
    return pd.DataFrame(rows)


def persistence_rate(triggers: pd.DataFrame, window: tuple[int, int]) -> tuple[float, int]:
    t = triggers.copy()
    t["date"] = pd.to_datetime(t["date"])
    t = t[year_mask(t["date"], window)]
    t = t.dropna(subset=["next_ret"])
    if t.empty:
        return np.nan, 0
    return float(t["continued"].mean()), len(t)


def filter_trades_s18(
    trades: pd.DataFrame,
    sector_map: dict[str, str],
    triggers: pd.DataFrame,
) -> pd.DataFrame:
    """Keep trades whose signal_date sector had an S18 trigger that day."""
    if triggers.empty:
        return trades.iloc[0:0].copy()
    trig_set = set(zip(pd.to_datetime(triggers["date"]).dt.normalize(), triggers["sector"]))
    t = trades.copy()
    t["_sig"] = signal_date_col(t)
    t["_sec"] = t["symbol"].astype(str).map(sector_map)
    mask = [((r["_sig"], r["_sec"]) in trig_set) for _, r in t.iterrows()]
    return t[mask].drop(columns=["_sig", "_sec"]).reset_index(drop=True)


def co_sector_keys(trades: pd.DataFrame, sector_map: dict[str, str], window: tuple[int, int]) -> set[tuple[pd.Timestamp, str]]:
    t = trades.copy()
    t["entry_date"] = pd.to_datetime(t["entry_date"]).dt.normalize()
    t = t[year_mask(t["entry_date"], window)]
    t["_sec"] = t["symbol"].astype(str).map(sector_map)
    keys: set[tuple[pd.Timestamp, str]] = set()
    for (ed, sec), grp in t.groupby(["entry_date", "_sec"]):
        if len(grp) >= 2 and sec and sec != "Unknown":
            keys.add((ed, sec))
    return keys


def filter_co_sector_trades(trades: pd.DataFrame, sector_map: dict[str, str], window: tuple[int, int]) -> pd.DataFrame:
    keys = co_sector_keys(trades, sector_map, window)
    if not keys:
        return trades.iloc[0:0].copy()
    t = trades.copy()
    t["entry_date"] = pd.to_datetime(t["entry_date"]).dt.normalize()
    t["_sec"] = t["symbol"].astype(str).map(sector_map)
    mask = [(r["entry_date"], r["_sec"]) in keys for _, r in t.iterrows()]
    return t[mask].drop(columns=["_sec"]).reset_index(drop=True)


def apply_s19_c1_leader(trades: pd.DataFrame, sector_map: dict[str, str]) -> pd.DataFrame:
    t = trades.copy()
    t["entry_date"] = pd.to_datetime(t["entry_date"]).dt.normalize()
    t["_sec"] = t["symbol"].astype(str).map(sector_map)
    keep_idx: list[int] = []
    for (_, _), grp in t.groupby(["entry_date", "_sec"]):
        if len(grp) < 2:
            keep_idx.extend(grp.index.tolist())
        else:
            keep_idx.append(grp.sort_values("rs_score", ascending=False).index[0])
    return t.loc[keep_idx].drop(columns=["_sec"]).reset_index(drop=True)


def apply_s19_c3_top_half(trades: pd.DataFrame, sector_map: dict[str, str]) -> pd.DataFrame:
    t = trades.copy()
    t["entry_date"] = pd.to_datetime(t["entry_date"]).dt.normalize()
    t["_sec"] = t["symbol"].astype(str).map(sector_map)
    keep_idx: list[int] = []
    for (_, _), grp in t.groupby(["entry_date", "_sec"]):
        if len(grp) < 2:
            keep_idx.extend(grp.index.tolist())
        else:
            n = max(1, len(grp) // 2)
            keep_idx.extend(grp.sort_values("rs_score", ascending=False).head(n).index.tolist())
    return t.loc[keep_idx].drop(columns=["_sec"]).reset_index(drop=True)


def apply_s19_c2_weight(trades: pd.DataFrame, sector_map: dict[str, str]) -> pd.DataFrame:
    t = trades.copy()
    t["entry_date"] = pd.to_datetime(t["entry_date"]).dt.normalize()
    t["_sec"] = t["symbol"].astype(str).map(sector_map)
    t["_s19w"] = 1.0
    for (_, _), grp in t.groupby(["entry_date", "_sec"]):
        if len(grp) < 2:
            continue
        leader = grp.sort_values("rs_score", ascending=False).index[0]
        for idx in grp.index:
            t.loc[idx, "_s19w"] = 2.0 if idx == leader else 0.5
    return t


def run_s19_c2_sim(stack: dict[str, Any], trades: pd.DataFrame) -> tuple[pd.Series, dict[str, float], int]:
    t = apply_s19_c2_weight(trades, stack["sector_map"])
    if t.empty:
        return pd.Series(dtype=float), {"mar": np.nan, "max_dd": np.nan, "cagr": np.nan}, 0
    sized = apply_size(t, stack["sctx"], leading=SIZE_LEADING_BASE, lagging=SIZE_LAGGING_BASE)
    sized["_combined"] = sized["_size_mult"].astype(float) * sized["_s19w"].astype(float)
    prep = prepare_trades_with_size(sized, "rs_score", "_combined")
    eq, _, _ = run_capital_sim(prep, stack["ctx"].gate, D4_CASH_YIELD)
    eq_oos = slice_equity_years(eq, OOS_WINDOW[0], OOS_WINDOW[1])
    m = _metrics_from_equity(eq_oos)
    n_oos = count_oos_trades(t, OOS_WINDOW[0], OOS_WINDOW[1])
    return eq, m, n_oos


def fetch_buy_sell_raw(symbol: str, start: str, end: str, headers: dict[str, str]) -> pd.DataFrame:
    url = f"{RESTV2_BASE}/symbols/{symbol}/historical-quotes"
    params = {"startDate": start, "endDate": end, "offset": 0, "limit": 5000}
    r = requests.get(url, headers=headers, params=params, timeout=60)
    if r.status_code != 200:
        return pd.DataFrame()
    data = r.json()
    if not isinstance(data, list):
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for item in data:
        d = item.get("date") or item.get("Date")
        bq, sq = item.get("buyQuantity"), item.get("sellQuantity")
        if not d or bq is None or sq is None:
            continue
        try:
            bq, sq = float(bq), float(sq)
        except (TypeError, ValueError):
            continue
        if bq <= 0 and sq <= 0:
            continue
        rows.append(
            {
                "symbol": symbol,
                "date": pd.Timestamp(str(d)[:10]).normalize(),
                "buy_quantity": bq,
                "sell_quantity": sq,
            }
        )
    return pd.DataFrame(rows)


def load_or_build_buy_sell_cache(symbols: list[str], start: str, end: str) -> pd.DataFrame:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    if BUY_SELL_CACHE.exists():
        cached = pd.read_parquet(BUY_SELL_CACHE)
        cached["date"] = pd.to_datetime(cached["date"]).dt.normalize()
        have = set(cached["symbol"].astype(str).unique())
        if set(symbols).issubset(have):
            sub = cached[
                (cached["symbol"].isin(symbols))
                & (cached["date"] >= start_ts)
                & (cached["date"] <= end_ts)
            ]
            if sub["symbol"].nunique() >= len(symbols) * 0.95:
                return sub
    token = _load_token(None)
    if not token:
        raise RuntimeError("FIREANT_TOKEN required for S17 harness")
    headers = {**_BROWSER_HEADERS, "Authorization": f"Bearer {token}"}
    parts: list[pd.DataFrame] = []
    if BUY_SELL_CACHE.exists():
        parts.append(pd.read_parquet(BUY_SELL_CACHE))
    for i, sym in enumerate(symbols):
        df = fetch_buy_sell_raw(sym, start, end, headers)
        if not df.empty:
            parts.append(df)
        if (i + 1) % 25 == 0:
            print(f"  buy/sell fetch {i+1}/{len(symbols)}", flush=True)
        time.sleep(FIREANT_DELAY)
    out = pd.concat(parts, ignore_index=True).drop_duplicates(["symbol", "date"])
    out.to_parquet(BUY_SELL_CACHE, index=False)
    out["date"] = pd.to_datetime(out["date"]).dt.normalize()
    return out[(out["symbol"].isin(symbols)) & (out["date"] >= start_ts) & (out["date"] <= end_ts)]


def ratio_on_signal(cache: pd.DataFrame, symbol: str, sig: pd.Timestamp, window: int) -> float | None:
    sub = cache[cache["symbol"] == symbol].sort_values("date").set_index("date")
    if sig not in sub.index and len(sub) == 0:
        return None
    if window == 1:
        if sig not in sub.index:
            return None
        sq = sub.loc[sig, "sell_quantity"]
        return float(sub.loc[sig, "buy_quantity"] / sq) if sq > 0 else None
    hist = sub.loc[:sig].tail(window)
    if len(hist) < window:
        return None
    s = hist["sell_quantity"].sum()
    return float(hist["buy_quantity"].sum() / s) if s > 0 else None


def build_stack_with_sector() -> dict[str, Any]:
    stack = build_baseline_stack()
    sector_map, _ = load_sector_map()
    stack["sector_map"] = sector_map
    stack["sector_rets"] = sector_daily_returns(stack["ctx"].panel, sector_map)
    stack["filter_map"] = build_signal_filter_map(stack["ctx"].panel)
    stack["s1_trades"] = apply_proximity_filter(stack["base_trades"], stack["filter_map"], S1_MIN_PROX)
    return stack


def verify_s1_baseline(stack: dict[str, Any]) -> tuple[dict[str, float], int, bool]:
    """Return S1-only OOS metrics, N_OOS, drift flag."""
    _, m, n = run_filtered_sim(stack, stack["s1_trades"])
    drift = abs(m["mar"] - S1_BASELINE_OOS_MAR) > MAR_TOLERANCE
    return m, n, drift


def oos_sub_mar(eq: pd.Series) -> tuple[float, float]:
    eq_a = slice_equity_years(eq, OOS_SUB_WINDOW_A[0], OOS_SUB_WINDOW_A[1])
    eq_b = slice_equity_years(eq, OOS_SUB_WINDOW_B[0], OOS_SUB_WINDOW_B[1])
    return float(_metrics_from_equity(eq_a)["mar"]), float(_metrics_from_equity(eq_b)["mar"])


def band_limit_fraction(
    panel: pd.DataFrame,
    sector_map: dict[str, str],
    triggers: pd.DataFrame,
    band: float = 0.07,
    member_frac: float = 0.20,
) -> float:
    """Fraction of trigger sector-days where >= member_frac of members hit +/- band."""
    if triggers.empty:
        return np.nan
    p = panel.copy()
    p["date"] = pd.to_datetime(p["date"]).dt.normalize()
    p["sector"] = p["symbol"].astype(str).map(sector_map).fillna("Unknown")
    p["ret"] = p.groupby("symbol")["close"].pct_change()
    flagged = 0
    for _, row in triggers.iterrows():
        dt = pd.Timestamp(row["date"]).normalize()
        sec = row["sector"]
        sub = p[(p["date"] == dt) & (p["sector"] == sec)].dropna(subset=["ret"])
        if len(sub) < 2:
            continue
        at_band = (sub["ret"].abs() >= band * 0.99).mean()
        if at_band >= member_frac:
            flagged += 1
    return flagged / len(triggers) if len(triggers) else np.nan


def persistence_by_sector(triggers: pd.DataFrame, window: tuple[int, int]) -> pd.DataFrame:
    t = triggers.copy()
    t["date"] = pd.to_datetime(t["date"])
    t = t[year_mask(t["date"], window)].dropna(subset=["next_ret"])
    if t.empty:
        return pd.DataFrame(columns=["sector", "rate", "n"])
    g = t.groupby("sector").agg(rate=("continued", "mean"), n=("continued", "count")).reset_index()
    return g


def write_harness_report(path: Path, title: str, sections: list[str], meta: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(sections), encoding="utf-8")
    meta_path = path.with_suffix(".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
