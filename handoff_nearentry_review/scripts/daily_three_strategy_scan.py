#!/usr/bin/env python3
"""
Daily three-strategy signal scanner (Vietnam equities).

Updates OHLCV panel + VNINDEX parquet from FireAnt when stale, then scans:
  B_cloud20_100, B_cloud21_55, C_GK_regime (GK + G07 regime gate).

Each regular run also prints:
  - CONVERGENCE: symbols appearing on 2+ of the three BUY-today lists
  - REMOVAL / RISK: near-entry watchlist staleness (vs prior snapshot) and
    C_GK_regime open-row flags (GK_Sell flip or G07 OFF). Cloud trail/TP exits deferred.

Near-entry watchlist (B_cloud20_100 / B_cloud21_55): symbols within the asymmetric
per-strategy window of the most recent cloud buy signal in the last 30 bars (ex-today),
not already open; see report section "NEAR-ENTRY WATCHLIST". BUY-today fill order:
B_cloud20_100 by ema_dist only; B_cloud21_55 by mom20 with optional mom60 tiebreak.
Watchlist sorts: B_cloud20_100 ema_dist then informational mom60; B_cloud21_55 mom20 only.

Persists `data/paper_trade/reports/scan_watchlists_last.json` for next-run staleness.

Usage:
  .venv\\Scripts\\python.exe pp_backtest/daily_three_strategy_scan.py
  .venv\\Scripts\\python.exe pp_backtest/daily_three_strategy_scan.py --pre-atc
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, Iterable, Literal

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pp_backtest.ema_levels.indicators import compute_atr, ema_cloud
from pp_backtest.ema_levels.entry import cloud_only_entry
from src.data.fireant_client import get_client

# ── Paths ────────────────────────────────────────────────────────────────────
PANEL_PATH = REPO / "data" / "research" / "ema_cloud" / "ohlcv_panel_ext2012.parquet"
VNINDEX_PATH = REPO / "data" / "fireant_ssot" / "ta_vnindex.parquet"
POSITIONS_CSV = REPO / "data" / "paper_trade" / "positions.csv"
REPORTS_DIR = REPO / "data" / "paper_trade" / "reports"
WATCHLIST_SNAPSHOT_PATH = REPORTS_DIR / "scan_watchlists_last.json"

EXCLUDE_UNIVERSE = {"VIC", "VHM", "VRE", "VPL"}
MIN_BARS_TOTAL = 110
WARMUP_CLOUD = 105
MIN_BARS_BEAR = 3
MAX_POS = 20

# ── Near-entry window thresholds ──────────────────────────────────────────────
# Validated via realistic exit-replay (run_nearentry_realistic.py, 2026-05-14).
# Asymmetric per strategy; C_GK remains on legacy symmetric until validated.
#
# KEY FINDING: >+14% entries are NOT bad — they are momentum-confirmed
# (A3: 10.4% mean_net vs 6.6% baseline; S3: 11.6% vs 6.4% baseline).
# No upside hard cap is applied. All entries beyond near_up are labeled
# "momentum_confirmed" and shown in the watchlist as high-priority.
#
# To revert all strategies to legacy behaviour, set every constant to 0.07.
NEAR_ENTRY_B20100_UP = 0.08   # A3: "acceptable"→"stretched" label boundary
NEAR_ENTRY_B20100_DN = 0.10   # A3: hard downside; beyond→"deep_pullback"
NEAR_ENTRY_B2155_UP  = 0.08   # S3: same upside boundary
NEAR_ENTRY_B2155_DN  = 0.06   # S3: tighter downside; <-6%→"damaged" (caution)
CGK_NEAR_ENTRY_PCT   = 0.07   # C_GK: unchanged — no asymmetric validation yet

STRAT_B20100 = "B_cloud20_100"
STRAT_B2155 = "B_cloud21_55"
STRAT_CGK = "C_GK_regime"

GK_LEN = 100
GK_MULT = 2.0
GK_ATR = 14
GK_LAG = 49  # floor((100 - 1) / 2)

VNINDEX_CANDIDATES = ("VNINDEX", "VNI")


def _fmt_pct(x: float | None, digits: int = 1) -> str:
    if x is None or not np.isfinite(x):
        return "n/a"
    return f"{x * 100:+.{digits}f}%"


def _near_entry_band_str(up: float, dn: float) -> str:
    """Human-readable entry-window label for section headers."""
    def _pct(v: float) -> str:
        p = v * 100.0
        return f"{p:.0f}%" if abs(p - round(p)) < 1e-9 else f"{p:g}%"
    return f"[-{_pct(dn)},+{_pct(up)}]"


def _ensure_date_cols(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"]).dt.normalize()
    return out


def load_panel() -> pd.DataFrame:
    df = pd.read_parquet(PANEL_PATH)
    return _ensure_date_cols(df)


def load_vnindex_parquet() -> pd.DataFrame:
    df = pd.read_parquet(VNINDEX_PATH)
    return _ensure_date_cols(df)


def save_panel(df: pd.DataFrame) -> None:
    df = _ensure_date_cols(df)
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)
    df.to_parquet(PANEL_PATH, index=False)


def save_vnindex(df: pd.DataFrame) -> None:
    df = _ensure_date_cols(df)
    df = df.sort_values("date").reset_index(drop=True)
    df.to_parquet(VNINDEX_PATH, index=False)


def update_panel_from_fireant() -> tuple[pd.Timestamp, int, int]:
    """
    Refresh panel + ta_vnindex if latest panel date < calendar today.
    Returns (new_max_date, rows_added, n_fetch_failed).
    """
    panel = load_panel()
    n_rows_before = len(panel)
    panel_last = panel["date"].max()
    today_d = pd.Timestamp.now().normalize()
    client = get_client()
    n_fail = 0
    chunks: list[pd.DataFrame] = []
    end = today_d.strftime("%Y-%m-%d")

    if pd.Timestamp(panel_last).normalize() < today_d:
        start = (pd.Timestamp(panel_last) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        symbols = sorted(panel["symbol"].astype(str).str.upper().unique())
        for sym in symbols:
            try:
                raw = client.get_ohlcv(sym, start=start, end=end)
                time.sleep(0.05)
                if raw is None or raw.empty:
                    n_fail += 1
                    continue
                sdf = raw.copy()
                sdf["symbol"] = sym.upper()
                sdf["date"] = pd.to_datetime(sdf["date"]).dt.normalize()
                for c in ("open", "high", "low", "close", "volume"):
                    if c not in sdf.columns:
                        sdf[c] = np.nan
                cols = ["symbol", "date", "open", "high", "low", "close", "volume"]
                if "value" in panel.columns and "value" not in sdf.columns:
                    sdf["value"] = np.nan
                    cols.append("value")
                chunks.append(sdf[cols])
            except Exception:
                n_fail += 1
                time.sleep(0.05)

        if chunks:
            new_rows = pd.concat(chunks, ignore_index=True)
            panel = pd.concat([panel, new_rows], ignore_index=True)
            panel = _ensure_date_cols(panel)
            panel = panel.drop_duplicates(subset=["symbol", "date"], keep="last")
            save_panel(panel)

    # VNINDEX parquet (same calendar end range; refresh if behind today)
    vnx = load_vnindex_parquet()
    v_last = vnx["date"].max()
    if pd.Timestamp(v_last).normalize() < today_d:
        v_start = (pd.Timestamp(v_last) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        vdf = None
        for cand in VNINDEX_CANDIDATES:
            raw = client.get_ohlcv(cand, start=v_start, end=end)
            time.sleep(0.05)
            if raw is not None and not raw.empty:
                vdf = raw.copy()
                vdf["date"] = pd.to_datetime(vdf["date"]).dt.normalize()
                break
        if vdf is not None:
            vnx = pd.concat([vnx, vdf], ignore_index=True)
            vnx = _ensure_date_cols(vnx)
            vnx = vnx.drop_duplicates(subset=["date"], keep="last")
            save_vnindex(vnx)

    panel2 = load_panel()
    new_max = pd.Timestamp(panel2["date"].max())
    added = max(0, len(panel2) - n_rows_before)
    return new_max, added, n_fail


def load_open_positions() -> pd.DataFrame:
    if not POSITIONS_CSV.exists() or POSITIONS_CSV.stat().st_size == 0:
        return pd.DataFrame(columns=["symbol", "status"])
    df = pd.read_csv(POSITIONS_CSV)
    if "symbol" not in df.columns:
        return pd.DataFrame(columns=["symbol", "status"])
    df["symbol"] = df["symbol"].astype(str).str.upper()
    if "status" not in df.columns:
        df["status"] = ""
    df["status"] = df["status"].astype(str).str.lower()
    return df


def strategy_open_stats(pos: pd.DataFrame, strategy: str) -> tuple[int, set[str]]:
    """Return (open_count, set of open symbols) for a strategy."""
    open_mask = pos["status"] == "open"
    if "strategy" not in pos.columns:
        if strategy == STRAT_B20100:
            sub = pos[open_mask]
        else:
            sub = pos.iloc[0:0]
    else:
        sub = pos[open_mask & (pos["strategy"].astype(str) == strategy)]
    return len(sub), set(sub["symbol"].astype(str).str.upper())


def open_symbols_any_strategy(pos: pd.DataFrame) -> set[str]:
    if pos.empty or "status" not in pos.columns:
        return set()
    m = pos["status"].astype(str).str.lower() == "open"
    return set(pos.loc[m, "symbol"].astype(str).str.upper())


def vnindex_regime_gate(vnx: pd.DataFrame) -> tuple[pd.Series, bool]:
    """
    G07 gate indexed by date: close > ema50 AND ema20 > ema50.
    Returns (gate_by_date, gate_today_bool for last row).
    """
    w = vnx.sort_values("date").reset_index(drop=True)
    c = w["close"].astype(float)
    ema20 = c.ewm(span=20, adjust=False).mean()
    ema50 = c.ewm(span=50, adjust=False).mean()
    gate = (c > ema50) & (ema20 > ema50)
    idx = pd.to_datetime(w["date"]).dt.normalize()
    s = pd.Series(gate.values, index=idx)
    last = bool(gate.iloc[-1]) if len(gate) else False
    return s, last


def compute_gk(close: pd.Series, high: pd.Series, low: pd.Series) -> dict[str, pd.Series]:
    past_close = close.shift(GK_LAG).fillna(close)
    zl_input = close + (close - past_close)
    gk_zl = zl_input.ewm(span=GK_LEN, adjust=False).mean()
    atr = compute_atr(high, low, close, period=GK_ATR)
    gk_upper = gk_zl + GK_MULT * atr
    gk_lower = gk_zl - GK_MULT * atr
    above = close > gk_upper
    zl_rising = gk_zl > gk_zl.shift(1)
    gk_bull = above & above.shift(1).fillna(False).astype(bool) & zl_rising

    trend = pd.Series(np.nan, index=close.index, dtype=float)
    trend.loc[gk_bull] = 1.0
    trend.loc[close < gk_lower] = -1.0
    trend = trend.ffill().fillna(0).astype(int)

    prev = trend.shift(1).fillna(0).astype(int)
    gk_buy = (trend == 1) & (prev != 1)
    # Trend flip to bear (-1), non-zero — aligns with research GK_Sell flip
    flip = (trend != prev) & (trend != 0)
    gk_sell = (flip & (trend == -1)).fillna(False)

    return {
        "gk_zl": gk_zl,
        "atr": atr,
        "gk_upper": gk_upper,
        "gk_lower": gk_lower,
        "gk_bull": gk_bull,
        "trend": trend,
        "gk_buy": gk_buy.fillna(False),
        "gk_sell": gk_sell,
    }


def slice_symbol(panel: pd.DataFrame, sym: str) -> pd.DataFrame:
    sdf = panel[panel["symbol"] == sym].sort_values("date").reset_index(drop=True)
    return sdf


WatchlistSort = Literal["primary_then_mom60", "mom60_then_primary", "primary_only"]


def _near_entry_label_b20100(pct_vs: float) -> str:
    """A3 near-entry quality label (B_cloud20_100 / PRIMARY). Validated 2026-05-14."""
    if pct_vs < -0.10:
        return "deep_pullback"
    if pct_vs < -0.02:
        return "ideal_pullback"
    if pct_vs <= 0.08:
        return "acceptable"
    if pct_vs <= 0.14:
        return "stretched"
    return "momentum_confirmed"


def _near_entry_label_b2155(pct_vs: float) -> str:
    """S3 near-entry quality label (B_cloud21_55 / SHADOW). Validated 2026-05-14."""
    if pct_vs < -0.06:
        return "damaged"
    if pct_vs < -0.02:
        return "ideal"
    if pct_vs <= 0.08:
        return "acceptable"
    if pct_vs <= 0.14:
        return "stretched"
    return "momentum_confirmed"


def scan_cloud_strategy(
    panel: pd.DataFrame,
    universe: Iterable[str],
    as_of: pd.Timestamp,
    ema_fast: int,
    ema_slow: int,
    rank_fn: Callable[[pd.DataFrame, dict], float],
    key_metric_name: str,
    rank_mom60_fn: Callable[[pd.DataFrame, dict], float] | None = None,
    *,
    near_entry_up: float = 0.07,
    near_entry_dn: float = 0.07,
    label_fn: Callable[[float], str] | None = None,
    watchlist_sort: WatchlistSort = "primary_then_mom60",
    buy_sort_mom60_tiebreak: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Returns (buy_today_df, watchlist_df) with columns for printing.

    BUY-today: sorted by rank_value (primary rank_fn). If buy_sort_mom60_tiebreak and
    rank_mom60_fn is set, secondary sort by ema_dist_mom60 (e.g. B_cloud21_55).

    Near-entry watchlist: downside floor at -near_entry_dn; no upside hard cap (Mode C).
    Entries beyond near_entry_up are labeled via label_fn (e.g. "momentum_confirmed").
    """
    buy_rows: list[dict] = []
    watch_rows: list[dict] = []

    sub = panel[panel["symbol"].isin(universe) & (panel["date"] <= as_of)]

    for sym, sdf in sub.groupby("symbol", sort=False):
        sdf = sdf.sort_values("date").reset_index(drop=True)
        if len(sdf) < MIN_BARS_TOTAL:
            continue
        last_dt = sdf["date"].iloc[-1]
        if last_dt != as_of:
            continue

        close = sdf["close"].astype(float)
        cloud = ema_cloud(close, ema_fast, ema_slow)
        ef = cloud["ema_fast"]
        es = cloud["ema_slow"]
        bull = cloud["cloud_bull"]
        ctx = {"close": close, "ema_fast": ef, "ema_slow": es, "cloud": cloud}
        sig = cloud_only_entry(
            close, ef, bull, min_bars_bear=MIN_BARS_BEAR, warmup=WARMUP_CLOUD
        )

        mom60 = float("nan")
        if rank_mom60_fn is not None:
            mom60 = rank_mom60_fn(sdf, ctx)

        # BUY today
        if bool(sig.iloc[-1]):
            rk = rank_fn(sdf, ctx)
            cl_last = float(close.iloc[-1])
            sl_last = float(es.iloc[-1])
            ema_dist_today = (cl_last - sl_last) / sl_last if sl_last > 0 else float("nan")
            buy_rows.append(
                {
                    "symbol": sym,
                    "close": cl_last,
                    "key_metric": rk,
                    "ema_dist": ema_dist_today,
                    "ema_dist_mom60": mom60,
                    "rank_value": rk,
                }
            )

        # Near-entry watchlist: most recent signal in last 30 bars excluding today bar
        n = len(sdf)
        if n < 2:
            continue
        lo = max(0, n - 31)
        hi = n - 2  # up to yesterday bar
        window_sig = sig.iloc[lo : hi + 1]
        if not window_sig.any():
            continue
        rel_idx = window_sig[window_sig].index.max()
        sig_close = float(close.iloc[rel_idx])
        cur_close = float(close.iloc[-1])
        pct_vs = (cur_close - sig_close) / sig_close if sig_close else np.nan
        bars_ago = n - 1 - rel_idx
        slow_today = float(es.iloc[-1])
        rk_w = rank_fn(sdf, ctx)
        slow_at_sig = float(es.iloc[rel_idx])
        ema_dist_at_signal = (
            (sig_close - slow_at_sig) / slow_at_sig if slow_at_sig > 0 else float("nan")
        )
        # Mode C: downside floor only; no upside cap — stretched/momentum entries labeled
        if pct_vs >= -near_entry_dn and cur_close > slow_today * 0.97:
            if label_fn is not None:
                entry_lbl = label_fn(pct_vs)
            else:
                entry_lbl = "acceptable" if abs(pct_vs) <= near_entry_up else "stretched"
            watch_rows.append(
                {
                    "symbol": sym,
                    "signal_date": sdf["date"].iloc[rel_idx],
                    "signal_close": sig_close,
                    "current_close": cur_close,
                    "pct_vs_signal": pct_vs,
                    "bars_ago": int(bars_ago),
                    "rank_value": rk_w,
                    "ema_dist_at_signal": ema_dist_at_signal,
                    "ema_dist_mom60": mom60,
                    "entry_window_label": entry_lbl,
                }
            )

    buy_df = pd.DataFrame(buy_rows)
    if not buy_df.empty:
        sort_cols = ["rank_value"]
        if (
            buy_sort_mom60_tiebreak
            and rank_mom60_fn is not None
            and "ema_dist_mom60" in buy_df.columns
        ):
            sort_cols.append("ema_dist_mom60")
        buy_df = buy_df.sort_values(sort_cols, ascending=[False] * len(sort_cols), na_position="last").reset_index(
            drop=True
        )
        buy_df.insert(0, "rank", range(1, len(buy_df) + 1))

    watch_df = pd.DataFrame(watch_rows)
    if not watch_df.empty:
        has_m60 = rank_mom60_fn is not None and "ema_dist_mom60" in watch_df.columns
        if has_m60 and watchlist_sort == "mom60_then_primary":
            sort_cols_w = ["ema_dist_mom60", "rank_value"]
        elif has_m60 and watchlist_sort == "primary_then_mom60":
            sort_cols_w = ["rank_value", "ema_dist_mom60"]
        else:
            sort_cols_w = ["rank_value"]
        watch_df = watch_df.sort_values(sort_cols_w, ascending=[False] * len(sort_cols_w), na_position="last").reset_index(
            drop=True
        )

    return buy_df, watch_df


def rank_ema_dist(sdf: pd.DataFrame, ctx: dict) -> float:
    c = ctx["close"]
    es = ctx["ema_slow"]
    cl = float(c.iloc[-1])
    sl = float(es.iloc[-1])
    return (cl - sl) / sl if sl > 0 else float("nan")


def rank_mom20(sdf: pd.DataFrame, ctx: dict) -> float:
    c = ctx["close"]
    if len(c) < 21:
        return float("nan")
    return float(c.iloc[-1] / c.iloc[-21] - 1.0)


def rank_mom60(sdf: pd.DataFrame, ctx: dict) -> float:
    """60-bar price ROC: close[t] / close[t-60] - 1 (informational; BUY tie-break for B_cloud21_55 when enabled)."""
    c = ctx["close"]
    if len(c) < 61:
        return float("nan")
    return float(c.iloc[-1] / c.iloc[-61] - 1.0)


def scan_c_gk(
    panel: pd.DataFrame,
    universe: Iterable[str],
    as_of: pd.Timestamp,
    gate_by_date: pd.Series,
) -> tuple[pd.DataFrame, pd.DataFrame, bool]:
    buy_rows: list[dict] = []
    watch_rows: list[dict] = []
    gmap = {
        pd.Timestamp(k).normalize(): bool(v)
        for k, v in gate_by_date.items()
    }
    as_of_n = pd.Timestamp(as_of).normalize()
    gate_on = bool(gmap.get(as_of_n, False))

    if not gate_on:
        return pd.DataFrame(), pd.DataFrame(), False

    sub = panel[panel["symbol"].isin(universe) & (panel["date"] <= as_of)]

    for sym, sdf in sub.groupby("symbol", sort=False):
        sdf = sdf.sort_values("date").reset_index(drop=True)
        if len(sdf) < MIN_BARS_TOTAL:
            continue
        if sdf["date"].iloc[-1] != as_of:
            continue

        close = sdf["close"].astype(float)
        high = sdf["high"].astype(float) if "high" in sdf.columns else close
        low = sdf["low"].astype(float) if "low" in sdf.columns else close
        gk = compute_gk(close, high, low)
        dates = sdf["date"]
        gate_row = dates.map(lambda d, gm=gmap: bool(gm.get(pd.Timestamp(d).normalize(), False)))
        combined = gk["gk_buy"].to_numpy() & gate_row.to_numpy()

        ema55 = close.ewm(span=55, adjust=False).mean()
        es55 = float(ema55.iloc[-1])
        cl = float(close.iloc[-1])
        ema_dist_55 = (cl - es55) / es55 if es55 > 0 else float("nan")

        if bool(combined[-1]):
            buy_rows.append(
                {
                    "symbol": sym,
                    "close": cl,
                    "key_metric": ema_dist_55,
                    "rank_value": ema_dist_55,
                }
            )

        n = len(sdf)
        sig = pd.Series(combined, index=sdf.index, dtype=bool)
        lo = max(0, n - 31)
        hi = n - 2
        window_sig = sig.iloc[lo : hi + 1]
        if not window_sig.any():
            continue
        rel_idx = window_sig[window_sig].index.max()
        sig_close = float(close.iloc[rel_idx])
        cur_close = float(close.iloc[-1])
        pct_vs = (cur_close - sig_close) / sig_close if sig_close else np.nan
        bars_ago = n - 1 - rel_idx
        if abs(pct_vs) <= CGK_NEAR_ENTRY_PCT and cur_close > es55 * 0.97:
            watch_rows.append(
                {
                    "symbol": sym,
                    "signal_date": sdf["date"].iloc[rel_idx],
                    "signal_close": sig_close,
                    "current_close": cur_close,
                    "pct_vs_signal": pct_vs,
                    "bars_ago": int(bars_ago),
                    "rank_value": ema_dist_55,
                    "label": "holding" if pct_vs >= 0 else "pullback",
                }
            )

    buy_df = pd.DataFrame(buy_rows)
    if not buy_df.empty:
        buy_df = buy_df.sort_values("rank_value", ascending=False).reset_index(drop=True)
        buy_df.insert(0, "rank", range(1, len(buy_df) + 1))

    watch_df = pd.DataFrame(watch_rows)
    if not watch_df.empty:
        watch_df = watch_df.sort_values("rank_value", ascending=False).reset_index(drop=True)

    return buy_df, watch_df, True


def attach_status(
    buy_df: pd.DataFrame,
    strategy: str,
    open_syms: set[str],
    open_count: int,
) -> pd.DataFrame:
    if buy_df.empty:
        return buy_df
    free = max(0, MAX_POS - open_count)
    out = buy_df.copy()
    statuses: list[str] = []
    fill_n = 0
    for _, row in out.iterrows():
        sym = str(row["symbol"]).upper()
        if sym in open_syms:
            statuses.append("already open")
        elif fill_n < free:
            fill_n += 1
            statuses.append(f"FILL #{fill_n}")
        else:
            statuses.append("skip")
    out["status"] = statuses
    return out


def filter_watch_open(watch_df: pd.DataFrame, open_syms: set[str]) -> pd.DataFrame:
    if watch_df.empty:
        return watch_df
    return watch_df[~watch_df["symbol"].astype(str).str.upper().isin(open_syms)].reset_index(
        drop=True
    )


def pre_atc_cloud_setups(
    panel: pd.DataFrame,
    universe: Iterable[str],
    yday: pd.Timestamp,
    ema_fast: int,
    ema_slow: int,
    open_syms: set[str],
) -> pd.DataFrame:
    """
    Setup-ready rows using closes through yday only.
    """
    rows: list[dict] = []
    sub = panel[panel["symbol"].isin(universe) & (panel["date"] <= yday)]

    alpha = 2.0 / (ema_fast + 1.0)

    for sym, sdf in sub.groupby("symbol", sort=False):
        sdf = sdf.sort_values("date").reset_index(drop=True)
        if len(sdf) < MIN_BARS_TOTAL or sdf["date"].iloc[-1] != yday:
            continue
        close = sdf["close"].astype(float)
        cloud = ema_cloud(close, ema_fast, ema_slow)
        ef = cloud["ema_fast"]
        es = cloud["ema_slow"]
        c_y = float(close.iloc[-1])
        ef_y = float(ef.iloc[-1])
        es_y = float(es.iloc[-1])

        if not (ef_y > es_y):
            continue
        last10 = close.iloc[-10:]
        ef10 = ef.iloc[-10:]
        bear_cnt = int((last10 < ef10).sum())
        if bear_cnt < 3:
            continue
        # Yesterday's close within 5% BELOW EMA_fast
        if not (c_y < ef_y and c_y >= ef_y * 0.95):
            continue
        if sym in open_syms:
            continue

        trigger = ef_y + alpha * (c_y - ef_y)
        gap_pct = (trigger - c_y) / c_y if c_y else float("nan")
        ema_dist_if = (trigger - es_y) / es_y if es_y > 0 else float("nan")
        rows.append(
            {
                "symbol": sym,
                "yesterday_close": c_y,
                "trigger_price": round(trigger, 2),
                "gap_pct": gap_pct,
                "bear_bars": bear_cnt,
                "ema_dist_if_fired": ema_dist_if,
                "priority": gap_pct,
            }
        )

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("gap_pct", ascending=True).reset_index(drop=True)
    return df


def print_and_collect(lines: list[str], s: str) -> None:
    print(s)
    lines.append(s)


def df_to_md_table(df: pd.DataFrame, float_cols: Iterable[str] | None = None) -> str:
    if df.empty:
        return "_None_\n"
    try:
        return df.to_markdown(index=False) + "\n"
    except (ImportError, ValueError):
        cols = list(df.columns)
        lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
        for _, row in df.iterrows():
            cells = [str(row[c]) for c in cols]
            lines.append("| " + " | ".join(cells) + " |")
        return "\n".join(lines) + "\n"


def _buy_symbols(df: pd.DataFrame) -> set[str]:
    if df is None or df.empty:
        return set()
    return set(df["symbol"].astype(str).str.upper())


def convergence_table(b_buy: pd.DataFrame, b2_buy: pd.DataFrame, c_buy: pd.DataFrame) -> pd.DataFrame:
    s1, s2, s3 = _buy_symbols(b_buy), _buy_symbols(b2_buy), _buy_symbols(c_buy)
    uni = s1 | s2 | s3
    rows: list[dict] = []
    for sym in sorted(uni):
        tags: list[str] = []
        if sym in s1:
            tags.append("B20100")
        if sym in s2:
            tags.append("B2155")
        if sym in s3:
            tags.append("CGK")
        if len(tags) >= 2:
            rows.append(
                {
                    "symbol": sym,
                    "n_strategies": len(tags),
                    "strategies": "+".join(tags),
                }
            )
    if not rows:
        return pd.DataFrame(columns=["symbol", "n_strategies", "strategies"])
    return pd.DataFrame(rows).sort_values(["n_strategies", "symbol"], ascending=[False, True]).reset_index(
        drop=True
    )


def load_watchlist_snapshot() -> dict | None:
    if not WATCHLIST_SNAPSHOT_PATH.exists():
        return None
    try:
        return json.loads(WATCHLIST_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def save_watchlist_snapshot(
    as_of: pd.Timestamp,
    b_watch: pd.DataFrame,
    b2_watch: pd.DataFrame,
    c_watch: pd.DataFrame,
) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    def _syms(w: pd.DataFrame) -> list[str]:
        if w is None or w.empty:
            return []
        return sorted(w["symbol"].astype(str).str.upper().unique().tolist())

    payload = {
        "as_of_date": str(pd.Timestamp(as_of).normalize().date()),
        STRAT_B20100: _syms(b_watch),
        STRAT_B2155: _syms(b2_watch),
        STRAT_CGK: _syms(c_watch),
    }
    WATCHLIST_SNAPSHOT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def watchlist_staleness_table(
    snapshot: dict | None,
    b_watch: pd.DataFrame,
    b2_watch: pd.DataFrame,
    c_watch: pd.DataFrame,
) -> pd.DataFrame:
    """Symbols on prior snapshot watchlist for a strategy but not on today's watchlist."""
    if not snapshot:
        return pd.DataFrame(columns=["symbol", "strategy", "note"])

    def _set(w: pd.DataFrame) -> set[str]:
        if w is None or w.empty:
            return set()
        return set(w["symbol"].astype(str).str.upper())

    cur = {
        STRAT_B20100: _set(b_watch),
        STRAT_B2155: _set(b2_watch),
        STRAT_CGK: _set(c_watch),
    }
    rows: list[dict] = []
    for strat in (STRAT_B20100, STRAT_B2155, STRAT_CGK):
        prev_list = snapshot.get(strat) or []
        prev = set(str(x).upper() for x in prev_list)
        dropped = prev - cur.get(strat, set())
        for sym in sorted(dropped):
            rows.append(
                {
                    "symbol": sym,
                    "strategy": strat,
                    "note": "was_near_entry_watchlist_not_today",
                }
            )
    if not rows:
        return pd.DataFrame(columns=["symbol", "strategy", "note"])
    return pd.DataFrame(rows).sort_values(["strategy", "symbol"]).reset_index(drop=True)


def open_c_gk_symbols(pos: pd.DataFrame) -> list[str]:
    if pos.empty or "strategy" not in pos.columns:
        return []
    m = (pos["status"].astype(str).str.lower() == "open") & (
        pos["strategy"].astype(str) == STRAT_CGK
    )
    if not m.any():
        return []
    return pos.loc[m, "symbol"].astype(str).str.upper().tolist()


def c_gk_open_removal_table(
    panel: pd.DataFrame,
    pos: pd.DataFrame,
    as_of: pd.Timestamp,
    gate_by_date: pd.Series,
) -> pd.DataFrame:
    """
    Open C_GK_regime positions: flag GK_Sell flip today or G07 regime OFF on as_of.
    (Trail/TP exits for cloud books are deferred — not computed here.)
    """
    syms = open_c_gk_symbols(pos)
    if not syms:
        return pd.DataFrame(columns=["symbol", "strategy", "note"])

    gmap = {pd.Timestamp(k).normalize(): bool(v) for k, v in gate_by_date.items()}
    as_of_n = pd.Timestamp(as_of).normalize()
    regime_on = bool(gmap.get(as_of_n, False))

    rows: list[dict] = []
    sub = panel[panel["symbol"].isin(syms) & (panel["date"] <= as_of)]
    for sym in syms:
        sdf = sub[sub["symbol"] == sym].sort_values("date").reset_index(drop=True)
        if sdf.empty or sdf["date"].iloc[-1] != as_of:
            rows.append(
                {
                    "symbol": sym,
                    "strategy": STRAT_CGK,
                    "note": "missing_asof_bar_in_panel",
                }
            )
            continue
        close = sdf["close"].astype(float)
        high = sdf["high"].astype(float) if "high" in sdf.columns else close
        low = sdf["low"].astype(float) if "low" in sdf.columns else close
        gk = compute_gk(close, high, low)
        notes: list[str] = []
        if bool(gk["gk_sell"].iloc[-1]):
            notes.append("gk_sell")
        if not regime_on:
            notes.append("g07_regime_off")
        if notes:
            rows.append({"symbol": sym, "strategy": STRAT_CGK, "note": ", ".join(notes)})
    if not rows:
        return pd.DataFrame(columns=["symbol", "strategy", "note"])
    return pd.DataFrame(rows).sort_values("symbol").reset_index(drop=True)


def removal_combined_table(stale: pd.DataFrame, cgk_rem: pd.DataFrame) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    if not stale.empty:
        s = stale.copy()
        s["category"] = "watchlist_stale"
        parts.append(s[["symbol", "category", "strategy", "note"]])
    if not cgk_rem.empty:
        c = cgk_rem.copy()
        c["category"] = "c_gk_open_signal"
        parts.append(c[["symbol", "category", "strategy", "note"]])
    if not parts:
        return pd.DataFrame(columns=["symbol", "category", "strategy", "note"])
    return pd.concat(parts, ignore_index=True)


def run_regular(panel: pd.DataFrame, vnx: pd.DataFrame, cal_today: date) -> str:
    lines: list[str] = []
    b_near_band = _near_entry_band_str(NEAR_ENTRY_B20100_UP, NEAR_ENTRY_B20100_DN)
    b2_near_band = _near_entry_band_str(NEAR_ENTRY_B2155_UP, NEAR_ENTRY_B2155_DN)
    c_near_band = _near_entry_band_str(CGK_NEAR_ENTRY_PCT, CGK_NEAR_ENTRY_PCT)
    as_of = pd.Timestamp(panel["date"].max())
    universe = sorted(
        s for s in panel["symbol"].astype(str).str.upper().unique() if s not in EXCLUDE_UNIVERSE
    )

    gate_by_date, _ = vnindex_regime_gate(vnx)
    prev_watch_snapshot = load_watchlist_snapshot()

    pos = load_open_positions()
    open_all = open_symbols_any_strategy(pos)
    oc_b1, sy_b1 = strategy_open_stats(pos, STRAT_B20100)
    oc_b2, sy_b2 = strategy_open_stats(pos, STRAT_B2155)
    oc_c, sy_c = strategy_open_stats(pos, STRAT_CGK)

    md_parts: list[str] = []
    md_parts.append(f"# Daily signal scan — {cal_today.isoformat()}\n")
    md_parts.append(f"**As-of panel date:** {as_of.date().isoformat()}\n")

    print_and_collect(lines, "=" * 60)
    print_and_collect(lines, f"DAILY SIGNAL SCAN - {cal_today.isoformat()}")
    print_and_collect(lines, "=" * 60)

    # ── B 20/100 ────────────────────────────────────────────────────────────
    b_buy, b_watch = scan_cloud_strategy(
        panel,
        universe,
        as_of,
        20,
        100,
        rank_ema_dist,
        "ema_dist",
        rank_mom60_fn=rank_mom60,
        near_entry_up=NEAR_ENTRY_B20100_UP,
        near_entry_dn=NEAR_ENTRY_B20100_DN,
        label_fn=_near_entry_label_b20100,
        watchlist_sort="primary_then_mom60",
        buy_sort_mom60_tiebreak=False,
    )
    b_buy = attach_status(b_buy, STRAT_B20100, sy_b1, oc_b1)
    b_watch = filter_watch_open(b_watch, open_all)

    print_and_collect(lines, "")
    print_and_collect(
        lines,
        f"-- {STRAT_B20100}  (EMA 20/100 cloud, ema_dist fill order) --",
    )
    print_and_collect(
        lines,
        f"Open: {oc_b1}/{MAX_POS}  |  Signals today: {len(b_buy)}  |  Free slots: {max(0, MAX_POS - oc_b1)}",
    )
    print_and_collect(lines, "")
    print_and_collect(lines, "BUY SIGNALS TODAY:")
    print_and_collect(lines, "  # Symbol   Close  EMA_dist   mom60      Status")
    if b_buy.empty:
        print_and_collect(lines, "  (none)")
    else:
        for _, r in b_buy.iterrows():
            print_and_collect(
                lines,
                f"  {int(r['rank']):d} {r['symbol']:<6} {r['close']:>8.2f}  "
                f"{_fmt_pct(r['key_metric']):>8} {_fmt_pct(r['ema_dist_mom60']):>8}  {r['status']}",
            )
    print_and_collect(lines, "")
    print_and_collect(
        lines,
        f"NEAR-ENTRY WATCHLIST ({b_near_band} vs last signal bar in last 30 bars, ex-today, not open) "
        "- sorted: ema_dist desc (primary), mom60 informational:",
    )
    print_and_collect(
        lines,
        "  Symbol   Sig_date   Sig_cls  Now    vs_sig  Bars  rank_value  mom60      Entry_label",
    )
    if b_watch.empty:
        print_and_collect(lines, "  (none)")
    else:
        for _, r in b_watch.iterrows():
            sd = pd.Timestamp(r["signal_date"]).strftime("%Y-%m-%d")
            print_and_collect(
                lines,
                f"  {r['symbol']:<6} {sd}  {r['signal_close']:>7.2f}  {r['current_close']:>7.2f}  "
                f"{_fmt_pct(r['pct_vs_signal']):>7}  {int(r['bars_ago']):>3}  "
                f"{_fmt_pct(r['rank_value']):>8} {_fmt_pct(r['ema_dist_mom60']):>8}  {r['entry_window_label']}",
            )

    md_parts.append(f"## {STRAT_B20100}\n")
    md_parts.append(
        f"Open: {oc_b1}/{MAX_POS} | Signals today: {len(b_buy)} | Free slots: {max(0, MAX_POS - oc_b1)}\n\n"
    )
    md_parts.append("### BUY SIGNALS TODAY\n\n")
    if not b_buy.empty:
        show = b_buy.copy()
        show["key_metric"] = show["key_metric"].map(lambda x: _fmt_pct(x))
        show["rank_value"] = show["rank_value"].map(lambda x: _fmt_pct(x))
        show["ema_dist_mom60"] = show["ema_dist_mom60"].map(lambda x: _fmt_pct(x))
        show = show[["rank", "symbol", "close", "key_metric", "ema_dist_mom60", "rank_value", "status"]]
        md_parts.append(df_to_md_table(show))
    else:
        md_parts.append("_None_\n\n")
    md_parts.append("### NEAR-ENTRY WATCHLIST\n\n")
    md_parts.append(
        f"_Window {b_near_band} of most recent cloud buy signal (last 30 bars, excluding today); "
        "not already open. Sort: **ema_dist** desc (primary, OOS-validated), **mom60** informational. "
        "No upside hard cap — momentum_confirmed entries included with label._\n\n"
    )
    if not b_watch.empty:
        w = b_watch.copy()
        w["signal_date"] = pd.to_datetime(w["signal_date"]).dt.strftime("%Y-%m-%d")
        w["pct_vs_signal"] = w["pct_vs_signal"].map(lambda x: _fmt_pct(x))
        w["rank_value"] = w["rank_value"].map(lambda x: _fmt_pct(x))
        w["ema_dist_mom60"] = w["ema_dist_mom60"].map(lambda x: _fmt_pct(x))
        w = w[
            [
                "symbol",
                "signal_date",
                "signal_close",
                "current_close",
                "pct_vs_signal",
                "bars_ago",
                "rank_value",
                "ema_dist_mom60",
                "entry_window_label",
            ]
        ]
        md_parts.append(df_to_md_table(w))
    else:
        md_parts.append("_None_\n\n")

    # ── B 21/55 ─────────────────────────────────────────────────────────────
    b2_buy, b2_watch = scan_cloud_strategy(
        panel,
        universe,
        as_of,
        21,
        55,
        rank_mom20,
        "mom20",
        rank_mom60_fn=rank_mom60,
        near_entry_up=NEAR_ENTRY_B2155_UP,
        near_entry_dn=NEAR_ENTRY_B2155_DN,
        label_fn=_near_entry_label_b2155,
        watchlist_sort="primary_only",
    )
    b2_buy = attach_status(b2_buy, STRAT_B2155, sy_b2, oc_b2)
    b2_watch = filter_watch_open(b2_watch, open_all)

    print_and_collect(lines, "")
    print_and_collect(
        lines,
        f"-- {STRAT_B2155}  (EMA 21/55 cloud, mom20 then mom60 fill) --",
    )
    print_and_collect(
        lines,
        f"Open: {oc_b2}/{MAX_POS}  |  Signals today: {len(b2_buy)}  |  Free slots: {max(0, MAX_POS - oc_b2)}",
    )
    print_and_collect(lines, "")
    print_and_collect(lines, "BUY SIGNALS TODAY:")
    print_and_collect(lines, "  # Symbol   Close  mom20      ema_dist   mom60      Status")
    if b2_buy.empty:
        print_and_collect(lines, "  (none)")
    else:
        for _, r in b2_buy.iterrows():
            print_and_collect(
                lines,
                f"  {int(r['rank']):d} {r['symbol']:<6} {r['close']:>8.2f}  "
                f"{_fmt_pct(r['key_metric']):>8} {_fmt_pct(r['ema_dist']):>8} {_fmt_pct(r['ema_dist_mom60']):>8}  {r['status']}",
            )
    print_and_collect(lines, "")
    print_and_collect(
        lines,
        f"NEAR-ENTRY WATCHLIST ({b2_near_band} vs last signal bar, not open) - sorted: mom20 (rank_value) only:",
    )
    print_and_collect(
        lines,
        "  Symbol   Sig_date   Sig_cls  Now    vs_sig  Bars  rank_value  ema_dist@sig  mom60      Entry_label",
    )
    if b2_watch.empty:
        print_and_collect(lines, "  (none)")
    else:
        for _, r in b2_watch.iterrows():
            sd = pd.Timestamp(r["signal_date"]).strftime("%Y-%m-%d")
            print_and_collect(
                lines,
                f"  {r['symbol']:<6} {sd}  {r['signal_close']:>7.2f}  {r['current_close']:>7.2f}  "
                f"{_fmt_pct(r['pct_vs_signal']):>7}  {int(r['bars_ago']):>3}  "
                f"{_fmt_pct(r['rank_value']):>8} {_fmt_pct(r['ema_dist_at_signal']):>8} "
                f"{_fmt_pct(r['ema_dist_mom60']):>8}  {r['entry_window_label']}",
            )

    md_parts.append(f"## {STRAT_B2155}\n")
    md_parts.append(
        f"Open: {oc_b2}/{MAX_POS} | Signals today: {len(b2_buy)} | Free slots: {max(0, MAX_POS - oc_b2)}\n\n"
    )
    md_parts.append("### BUY SIGNALS TODAY\n\n")
    if not b2_buy.empty:
        show = b2_buy.copy()
        show["key_metric"] = show["key_metric"].map(lambda x: _fmt_pct(x))
        show["ema_dist"] = show["ema_dist"].map(lambda x: _fmt_pct(x))
        show["rank_value"] = show["rank_value"].map(lambda x: _fmt_pct(x))
        show["ema_dist_mom60"] = show["ema_dist_mom60"].map(lambda x: _fmt_pct(x))
        show = show[["rank", "symbol", "close", "key_metric", "ema_dist", "ema_dist_mom60", "rank_value", "status"]]
        md_parts.append(df_to_md_table(show))
    else:
        md_parts.append("_None_\n\n")
    md_parts.append("### NEAR-ENTRY WATCHLIST\n\n")
    md_parts.append(
        f"_Window {b2_near_band} of most recent cloud buy signal (last 30 bars, excluding today); "
        "not already open. Sort: **mom20** desc (primary, OOS-validated); **ema_dist** and **mom60** informational. "
        "No upside hard cap — momentum_confirmed entries included with label._\n\n"
    )
    if not b2_watch.empty:
        w = b2_watch.copy()
        w["signal_date"] = pd.to_datetime(w["signal_date"]).dt.strftime("%Y-%m-%d")
        w["pct_vs_signal"] = w["pct_vs_signal"].map(lambda x: _fmt_pct(x))
        w["rank_value"] = w["rank_value"].map(lambda x: _fmt_pct(x))
        w["ema_dist_at_signal"] = w["ema_dist_at_signal"].map(lambda x: _fmt_pct(x))
        w["ema_dist_mom60"] = w["ema_dist_mom60"].map(lambda x: _fmt_pct(x))
        w = w[
            [
                "symbol",
                "signal_date",
                "signal_close",
                "current_close",
                "pct_vs_signal",
                "bars_ago",
                "rank_value",
                "ema_dist_at_signal",
                "ema_dist_mom60",
                "entry_window_label",
            ]
        ]
        md_parts.append(df_to_md_table(w))
    else:
        md_parts.append("_None_\n\n")

    # ── C GK regime ─────────────────────────────────────────────────────────
    c_buy, c_watch, gate_ok = scan_c_gk(panel, universe, as_of, gate_by_date)
    print_and_collect(lines, "")
    print_and_collect(lines, f"-- {STRAT_CGK}  (GK signal + G07 regime gate) --")
    if not gate_ok:
        msg = f"{STRAT_CGK}: regime gate OFF -- no entries"
        print_and_collect(lines, msg)
        md_parts.append(f"## {STRAT_CGK}\n\n**{msg}**\n\n")
    else:
        c_buy = attach_status(c_buy, STRAT_CGK, sy_c, oc_c)
        c_watch = filter_watch_open(c_watch, open_all)
        print_and_collect(
            lines,
            f"Open: {oc_c}/{MAX_POS}  |  Signals today: {len(c_buy)}  |  Free slots: {max(0, MAX_POS - oc_c)}",
        )
        print_and_collect(lines, "")
        print_and_collect(lines, "BUY SIGNALS TODAY:")
        print_and_collect(lines, "  # Symbol   Close  ema_dist_55  Status")
        if c_buy.empty:
            print_and_collect(lines, "  (none)")
        else:
            for _, r in c_buy.iterrows():
                print_and_collect(
                    lines,
                    f"  {int(r['rank']):d} {r['symbol']:<6} {r['close']:>8.2f}  "
                    f"{_fmt_pct(r['key_metric']):>10}  {r['status']}",
                )
        print_and_collect(lines, "")
        print_and_collect(
            lines,
            f"NEAR-ENTRY WATCHLIST (last 30 bars, not open, within {c_near_band}):",
        )
        print_and_collect(lines, "  Symbol   Sig_date   Sig_cls  Now    vs_sig  Bars  rank_value  Label")
        if c_watch.empty:
            print_and_collect(lines, "  (none)")
        else:
            for _, r in c_watch.iterrows():
                sd = pd.Timestamp(r["signal_date"]).strftime("%Y-%m-%d")
                print_and_collect(
                    lines,
                    f"  {r['symbol']:<6} {sd}  {r['signal_close']:>7.2f}  {r['current_close']:>7.2f}  "
                    f"{_fmt_pct(r['pct_vs_signal']):>7}  {int(r['bars_ago']):>3}  "
                    f"{_fmt_pct(r['rank_value']):>8}  {r['label']}",
                )

        md_parts.append(f"## {STRAT_CGK}\n")
        md_parts.append(
            f"Open: {oc_c}/{MAX_POS} | Signals today: {len(c_buy)} | Free slots: {max(0, MAX_POS - oc_c)}\n\n"
        )
        md_parts.append("### BUY SIGNALS TODAY\n\n")
        if not c_buy.empty:
            show = c_buy.copy()
            show["key_metric"] = show["key_metric"].map(lambda x: _fmt_pct(x))
            show["rank_value"] = show["rank_value"].map(lambda x: _fmt_pct(x))
            md_parts.append(df_to_md_table(show))
        else:
            md_parts.append("_None_\n\n")
        md_parts.append("### NEAR-ENTRY WATCHLIST\n\n")
        md_parts.append(
            f"_Within {c_near_band} of most recent gated GK buy signal (last 30 bars, excluding today); "
            "not already open. Legacy symmetric threshold — not asymmetric-validated._\n\n"
        )
        if not c_watch.empty:
            w = c_watch.copy()
            w["signal_date"] = pd.to_datetime(w["signal_date"]).dt.strftime("%Y-%m-%d")
            w["pct_vs_signal"] = w["pct_vs_signal"].map(lambda x: _fmt_pct(x))
            w["rank_value"] = w["rank_value"].map(lambda x: _fmt_pct(x))
            md_parts.append(df_to_md_table(w))
        else:
            md_parts.append("_None_\n\n")

    # ── Convergence & removal (cross-strategy) ─────────────────────────────
    conv_df = convergence_table(b_buy, b2_buy, c_buy)
    stale_df = watchlist_staleness_table(prev_watch_snapshot, b_watch, b2_watch, c_watch)
    cgk_rem_df = c_gk_open_removal_table(panel, pos, as_of, gate_by_date)
    rem_df = removal_combined_table(stale_df, cgk_rem_df)

    print_and_collect(lines, "")
    print_and_collect(lines, "-- CONVERGENCE (2+ BUY lists today) --")
    if conv_df.empty:
        print_and_collect(lines, "  (none)")
    else:
        print_and_collect(lines, "  Symbol   n  Strategies")
        for _, r in conv_df.iterrows():
            print_and_collect(
                lines,
                f"  {r['symbol']:<8} {int(r['n_strategies'])}  {r['strategies']}",
            )

    print_and_collect(lines, "")
    print_and_collect(lines, "-- REMOVAL / RISK (watchlist stale + C_GK open signals) --")
    print_and_collect(
        lines,
        "  Note: B_cloud trail/TP1 exits not shown - deferred until ledger exit fields wired.",
    )
    if rem_df.empty:
        print_and_collect(lines, "  (none)")
    else:
        print_and_collect(lines, "  Symbol   category              strategy        note")
        for _, r in rem_df.iterrows():
            print_and_collect(
                lines,
                f"  {r['symbol']:<8} {str(r['category']):<22} {str(r['strategy']):<15} {r['note']}",
            )

    md_parts.append("## CONVERGENCE (2+ BUY lists today)\n\n")
    md_parts.append(df_to_md_table(conv_df) if not conv_df.empty else "_None_\n\n")
    md_parts.append("## REMOVAL / RISK\n\n")
    md_parts.append(
        "_B_cloud20_100 / B_cloud21_55: trail + TP exits not listed here._\n\n"
    )
    md_parts.append("### Watchlist staleness (was on prior near-entry snapshot, not today)\n\n")
    md_parts.append(df_to_md_table(stale_df) if not stale_df.empty else "_None_\n\n")
    md_parts.append("### C_GK_regime open rows: GK_Sell today or G07 OFF\n\n")
    md_parts.append(df_to_md_table(cgk_rem_df) if not cgk_rem_df.empty else "_None_\n\n")
    md_parts.append("### Combined removal table\n\n")
    md_parts.append(df_to_md_table(rem_df) if not rem_df.empty else "_None_\n\n")

    save_watchlist_snapshot(as_of, b_watch, b2_watch, c_watch)

    print_and_collect(lines, "")
    print_and_collect(lines, "=" * 60)
    return "".join(md_parts)


def run_pre_atc(panel: pd.DataFrame, vnx: pd.DataFrame, cal_today: date) -> str:
    lines: list[str] = []
    yday = pd.Timestamp(cal_today - timedelta(days=1))
    panel_y = panel[panel["date"] <= yday]
    vnx_y = vnx[vnx["date"] <= yday]
    gate_by_date, gate_y = vnindex_regime_gate(vnx_y)

    universe = sorted(
        s for s in panel["symbol"].astype(str).str.upper().unique() if s not in EXCLUDE_UNIVERSE
    )
    pos = load_open_positions()
    open_all = open_symbols_any_strategy(pos)

    md_parts: list[str] = []
    md_parts.append(f"# PRE-ATC scan — {cal_today.isoformat()}\n")
    md_parts.append(f"**Data through:** {yday.date().isoformat()} (no fetch)\n\n")

    print_and_collect(lines, "=" * 60)
    print_and_collect(lines, f"PRE-ATC SCAN - {cal_today.isoformat()}")
    print_and_collect(lines, "PRE-ATC SCAN - submit ATC orders for stocks at/near trigger price")
    print_and_collect(lines, "Regime gate (C_GK_regime): " + ("ON" if gate_y else "OFF") + " based on yesterday's VNINDEX close")
    print_and_collect(lines, "=" * 60)

    s1 = pre_atc_cloud_setups(panel_y, universe, yday, 20, 100, open_all)
    print_and_collect(lines, "")
    print_and_collect(lines, f"-- {STRAT_B20100}  SETUP-READY (pre-close) --")
    print_and_collect(lines, "  Symbol | Yesterday_close | Trigger_price | Gap_pct | Bear_bars | EMA_dist_if_fired | Priority")
    if s1.empty:
        print_and_collect(lines, "  (none)")
    else:
        for _, r in s1.iterrows():
            print_and_collect(
                lines,
                f"  {r['symbol']:<6} | {r['yesterday_close']:>14.2f} | {r['trigger_price']:>13.2f} | "
                f"{_fmt_pct(r['gap_pct']):>7} | {int(r['bear_bars']):>9} | "
                f"{_fmt_pct(r['ema_dist_if_fired']):>17} | {_fmt_pct(r['priority'])}",
            )
    md_parts.append(f"## {STRAT_B20100} — SETUP-READY\n\n")
    md_parts.append(df_to_md_table(s1) if not s1.empty else "_None_\n\n")

    s2 = pre_atc_cloud_setups(panel_y, universe, yday, 21, 55, open_all)
    print_and_collect(lines, "")
    print_and_collect(lines, f"-- {STRAT_B2155}  SETUP-READY (pre-close) --")
    print_and_collect(lines, "  Symbol | Yesterday_close | Trigger_price | Gap_pct | Bear_bars | EMA_dist_if_fired | Priority")
    if s2.empty:
        print_and_collect(lines, "  (none)")
    else:
        for _, r in s2.iterrows():
            print_and_collect(
                lines,
                f"  {r['symbol']:<6} | {r['yesterday_close']:>14.2f} | {r['trigger_price']:>13.2f} | "
                f"{_fmt_pct(r['gap_pct']):>7} | {int(r['bear_bars']):>9} | "
                f"{_fmt_pct(r['ema_dist_if_fired']):>17} | {_fmt_pct(r['priority'])}",
            )
    md_parts.append(f"## {STRAT_B2155} — SETUP-READY\n\n")
    md_parts.append(df_to_md_table(s2) if not s2.empty else "_None_\n\n")

    print_and_collect(lines, "")
    print_and_collect(lines, f"-- {STRAT_CGK}  (GK signal + G07 regime gate) --")
    note = (
        "PRE-ATC: GK entries depend on today's OHLC vs adaptive bands; "
        "no single trigger_price grid. Use post-close scan for C_GK_regime entries."
    )
    print_and_collect(lines, note)
    md_parts.append(f"## {STRAT_CGK}\n\n{note}\n\n_Regime yesterday:_ **{'ON' if gate_y else 'OFF'}**\n\n")

    print_and_collect(lines, "")
    print_and_collect(lines, "=" * 60)
    return "".join(md_parts)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pre-atc", action="store_true", help="Use yesterday-only panel; no fetch.")
    args = ap.parse_args()
    cal_today = datetime.now().date()

    if args.pre_atc:
        panel = load_panel()
        vnx = load_vnindex_parquet()
        md_body = run_pre_atc(panel, vnx, cal_today)
    else:
        panel0 = load_panel()
        lb0 = panel0["date"].max()
        lb0_n = pd.Timestamp(lb0).normalize()
        today_n = pd.Timestamp.now().normalize()

        _nm, added_rows, n_fail = update_panel_from_fireant()

        panel = load_panel()
        lb1_n = pd.Timestamp(panel["date"].max()).normalize()

        if lb0_n >= today_n:
            print(f"Panel already current (max {lb0_n.date()}); no fetch.")
        else:
            print(f"Panel updated {lb0_n.date()} -> {lb1_n.date()}  (+{added_rows} rows)")
        if n_fail:
            print(f"Fetch failures (symbols skipped): {n_fail}")

        vnx = load_vnindex_parquet()
        md_body = run_regular(panel, vnx, cal_today)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_md = REPORTS_DIR / f"scan_{cal_today.isoformat()}.md"
    prefix = "# PRE-ATC\n\n" if args.pre_atc else ""
    out_md.write_text(prefix + md_body, encoding="utf-8")
    print(f"\nReport saved: {out_md}")


if __name__ == "__main__":
    main()
