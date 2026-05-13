#!/usr/bin/env python3
"""
Daily three-strategy signal scanner (Vietnam equities).

Updates OHLCV panel + VNINDEX parquet from FireAnt when stale, then scans:
  B_cloud20_100, B_cloud21_55, C_GK_regime (GK + G07 regime gate).

Usage:
  .venv\\Scripts\\python.exe pp_backtest/daily_three_strategy_scan.py
  .venv\\Scripts\\python.exe pp_backtest/daily_three_strategy_scan.py --pre-atc
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, Iterable

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

EXCLUDE_UNIVERSE = {"VIC", "VHM", "VRE", "VPL"}
MIN_BARS_TOTAL = 110
WARMUP_CLOUD = 105
MIN_BARS_BEAR = 3
MAX_POS = 20

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

    return {
        "gk_zl": gk_zl,
        "atr": atr,
        "gk_upper": gk_upper,
        "gk_lower": gk_lower,
        "gk_bull": gk_bull,
        "trend": trend,
        "gk_buy": gk_buy.fillna(False),
    }


def slice_symbol(panel: pd.DataFrame, sym: str) -> pd.DataFrame:
    sdf = panel[panel["symbol"] == sym].sort_values("date").reset_index(drop=True)
    return sdf


def scan_cloud_strategy(
    panel: pd.DataFrame,
    universe: Iterable[str],
    as_of: pd.Timestamp,
    ema_fast: int,
    ema_slow: int,
    rank_fn: Callable[[pd.DataFrame, dict], float],
    key_metric_name: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Returns (buy_today_df, watchlist_df) with columns for printing.
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
        sig = cloud_only_entry(
            close, ef, bull, min_bars_bear=MIN_BARS_BEAR, warmup=WARMUP_CLOUD
        )

        # BUY today
        if bool(sig.iloc[-1]):
            rk = rank_fn(sdf, {"close": close, "ema_fast": ef, "ema_slow": es, "cloud": cloud})
            buy_rows.append(
                {
                    "symbol": sym,
                    "close": float(close.iloc[-1]),
                    "key_metric": rk,
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
        rk_w = rank_fn(sdf, {"close": close, "ema_fast": ef, "ema_slow": es, "cloud": cloud})
        if abs(pct_vs) <= 0.07 and cur_close > slow_today * 0.97:
            watch_rows.append(
                {
                    "symbol": sym,
                    "signal_date": sdf["date"].iloc[rel_idx],
                    "signal_close": sig_close,
                    "current_close": cur_close,
                    "pct_vs_signal": pct_vs,
                    "bars_ago": int(bars_ago),
                    "rank_value": rk_w,
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
        if abs(pct_vs) <= 0.07 and cur_close > es55 * 0.97:
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


def run_regular(panel: pd.DataFrame, vnx: pd.DataFrame, cal_today: date) -> str:
    lines: list[str] = []
    as_of = pd.Timestamp(panel["date"].max())
    universe = sorted(
        s for s in panel["symbol"].astype(str).str.upper().unique() if s not in EXCLUDE_UNIVERSE
    )

    gate_by_date, _ = vnindex_regime_gate(vnx)

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
        panel, universe, as_of, 20, 100, rank_ema_dist, "ema_dist"
    )
    b_buy = attach_status(b_buy, STRAT_B20100, sy_b1, oc_b1)
    b_watch = filter_watch_open(b_watch, open_all)

    print_and_collect(lines, "")
    print_and_collect(lines, f"-- {STRAT_B20100}  (EMA 20/100 cloud, ema_dist fill) --")
    print_and_collect(
        lines,
        f"Open: {oc_b1}/{MAX_POS}  |  Signals today: {len(b_buy)}  |  Free slots: {max(0, MAX_POS - oc_b1)}",
    )
    print_and_collect(lines, "")
    print_and_collect(lines, "BUY SIGNALS TODAY:")
    print_and_collect(lines, "  # Symbol   Close  EMA_dist   Status")
    if b_buy.empty:
        print_and_collect(lines, "  (none)")
    else:
        for _, r in b_buy.iterrows():
            print_and_collect(
                lines,
                f"  {int(r['rank']):d} {r['symbol']:<6} {r['close']:>8.2f}  "
                f"{_fmt_pct(r['key_metric']):>8}  {r['status']}",
            )
    print_and_collect(lines, "")
    print_and_collect(lines, "NEAR-ENTRY WATCHLIST (last 30 bars, not open, within +/-7%):")
    print_and_collect(lines, "  Symbol   Sig_date   Sig_cls  Now    vs_sig  Bars  rank_value  Label")
    if b_watch.empty:
        print_and_collect(lines, "  (none)")
    else:
        for _, r in b_watch.iterrows():
            sd = pd.Timestamp(r["signal_date"]).strftime("%Y-%m-%d")
            print_and_collect(
                lines,
                f"  {r['symbol']:<6} {sd}  {r['signal_close']:>7.2f}  {r['current_close']:>7.2f}  "
                f"{_fmt_pct(r['pct_vs_signal']):>7}  {int(r['bars_ago']):>3}  "
                f"{_fmt_pct(r['rank_value']):>8}  {r['label']}",
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
        md_parts.append(df_to_md_table(show))
    else:
        md_parts.append("_None_\n\n")
    md_parts.append("### NEAR-ENTRY WATCHLIST\n\n")
    if not b_watch.empty:
        w = b_watch.copy()
        w["signal_date"] = pd.to_datetime(w["signal_date"]).dt.strftime("%Y-%m-%d")
        w["pct_vs_signal"] = w["pct_vs_signal"].map(lambda x: _fmt_pct(x))
        w["rank_value"] = w["rank_value"].map(lambda x: _fmt_pct(x))
        md_parts.append(df_to_md_table(w))
    else:
        md_parts.append("_None_\n\n")

    # ── B 21/55 ─────────────────────────────────────────────────────────────
    b2_buy, b2_watch = scan_cloud_strategy(
        panel, universe, as_of, 21, 55, rank_mom20, "mom20"
    )
    b2_buy = attach_status(b2_buy, STRAT_B2155, sy_b2, oc_b2)
    b2_watch = filter_watch_open(b2_watch, open_all)

    print_and_collect(lines, "")
    print_and_collect(lines, f"-- {STRAT_B2155}  (EMA 21/55 cloud, momentum fill) --")
    print_and_collect(
        lines,
        f"Open: {oc_b2}/{MAX_POS}  |  Signals today: {len(b2_buy)}  |  Free slots: {max(0, MAX_POS - oc_b2)}",
    )
    print_and_collect(lines, "")
    print_and_collect(lines, "BUY SIGNALS TODAY:")
    print_and_collect(lines, "  # Symbol   Close  mom20      Status")
    if b2_buy.empty:
        print_and_collect(lines, "  (none)")
    else:
        for _, r in b2_buy.iterrows():
            print_and_collect(
                lines,
                f"  {int(r['rank']):d} {r['symbol']:<6} {r['close']:>8.2f}  "
                f"{_fmt_pct(r['key_metric']):>8}  {r['status']}",
            )
    print_and_collect(lines, "")
    print_and_collect(lines, "NEAR-ENTRY WATCHLIST (last 30 bars, not open, within +/-7%):")
    print_and_collect(lines, "  Symbol   Sig_date   Sig_cls  Now    vs_sig  Bars  rank_value  Label")
    if b2_watch.empty:
        print_and_collect(lines, "  (none)")
    else:
        for _, r in b2_watch.iterrows():
            sd = pd.Timestamp(r["signal_date"]).strftime("%Y-%m-%d")
            print_and_collect(
                lines,
                f"  {r['symbol']:<6} {sd}  {r['signal_close']:>7.2f}  {r['current_close']:>7.2f}  "
                f"{_fmt_pct(r['pct_vs_signal']):>7}  {int(r['bars_ago']):>3}  "
                f"{_fmt_pct(r['rank_value']):>8}  {r['label']}",
            )

    md_parts.append(f"## {STRAT_B2155}\n")
    md_parts.append(
        f"Open: {oc_b2}/{MAX_POS} | Signals today: {len(b2_buy)} | Free slots: {max(0, MAX_POS - oc_b2)}\n\n"
    )
    md_parts.append("### BUY SIGNALS TODAY\n\n")
    if not b2_buy.empty:
        show = b2_buy.copy()
        show["key_metric"] = show["key_metric"].map(lambda x: _fmt_pct(x))
        show["rank_value"] = show["rank_value"].map(lambda x: _fmt_pct(x))
        md_parts.append(df_to_md_table(show))
    else:
        md_parts.append("_None_\n\n")
    md_parts.append("### NEAR-ENTRY WATCHLIST\n\n")
    if not b2_watch.empty:
        w = b2_watch.copy()
        w["signal_date"] = pd.to_datetime(w["signal_date"]).dt.strftime("%Y-%m-%d")
        w["pct_vs_signal"] = w["pct_vs_signal"].map(lambda x: _fmt_pct(x))
        w["rank_value"] = w["rank_value"].map(lambda x: _fmt_pct(x))
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
        print_and_collect(lines, "NEAR-ENTRY WATCHLIST (last 30 bars, not open, within +/-7%):")
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
        if not c_watch.empty:
            w = c_watch.copy()
            w["signal_date"] = pd.to_datetime(w["signal_date"]).dt.strftime("%Y-%m-%d")
            w["pct_vs_signal"] = w["pct_vs_signal"].map(lambda x: _fmt_pct(x))
            w["rank_value"] = w["rank_value"].map(lambda x: _fmt_pct(x))
            md_parts.append(df_to_md_table(w))
        else:
            md_parts.append("_None_\n\n")

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
            print(f"Panel updated {lb0_n.date()} → {lb1_n.date()}  (+{added_rows} rows)")
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
