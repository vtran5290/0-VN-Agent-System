"""Breadth proxies from watchlist OHLCV aligned to master trading dates."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

VIN = frozenset({"VIC", "VHM", "VRE"})


def load_watchlist_symbols(path: Path) -> list[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [ln.strip().upper() for ln in lines if ln.strip() and not ln.strip().startswith("#")]


def _load_stock_series(repo: Path, symbol: str, end: str, offline: bool) -> pd.DataFrame:
    from scripts.research.vnindex_low_dist_ex_vin import _load_stock

    return _load_stock(symbol, end=end, offline=offline)


def build_close_panel(
    repo: Path,
    master_dates: pd.DatetimeIndex,
    symbols: list[str],
    end: str,
    offline: bool,
) -> tuple[pd.DataFrame, list[str]]:
    """Columns = symbols, index = master_dates; NaN where missing."""
    panel = pd.DataFrame(index=master_dates)
    loaded: list[str] = []
    for sym in symbols:
        df = _load_stock_series(repo, sym, end, offline)
        if df.empty or "close" not in df.columns:
            continue
        s = df.set_index("date")["close"].astype(float).sort_index()
        s = s.reindex(master_dates)
        if s.notna().sum() < 100:
            continue
        panel[sym] = s.values
        loaded.append(sym)
    return panel, loaded


def ema50(close: pd.Series) -> pd.Series:
    return close.ewm(span=50, min_periods=50, adjust=False).mean()


def breadth_snapshot_at_i(
    panel: pd.DataFrame,
    ema_panel: pd.DataFrame,
    i: int,
    fwd_short: int = 20,
) -> dict:
    """One anchor row: pct above EMA50, median fwd return, advance-decline proxy."""
    n = len(panel)
    if i >= n or i + 1 >= n:
        return {}
    row_c = panel.iloc[i]
    row_e = ema_panel.iloc[i]
    m = row_c.notna() & row_e.notna()
    if not m.any():
        return {"pct_above_ema50": None, "median_20d_fwd_return": None, "advance_decline_1d": None}
    pct = float((row_c[m] > row_e[m]).mean())
    if i + fwd_short < n:
        row_f = panel.iloc[i + fwd_short]
        rets = row_f[m] / row_c[m] - 1.0
        med20 = float(np.nanmedian(rets.values))
    else:
        med20 = None
    if i + 1 < n:
        c0, c1 = panel.iloc[i], panel.iloc[i + 1]
        mm = c0.notna() & c1.notna()
        if mm.any():
            adv = float((c1[mm] > c0[mm]).mean())
        else:
            adv = None
    else:
        adv = None
    return {
        "pct_above_ema50": pct,
        "median_20d_fwd_return": med20,
        "advance_decline_1d": adv,
    }


def compute_breadth_for_anchors(
    repo: Path,
    master_dates: pd.DatetimeIndex,
    anchor_indices: list[int],
    end: str,
    offline: bool,
    watchlist_path: Path,
) -> dict:
    syms = load_watchlist_symbols(watchlist_path)
    if not syms:
        return {"available": False, "note": "empty_watchlist"}
    panel_all, loaded = build_close_panel(repo, master_dates, syms, end, offline)
    if panel_all.shape[1] < 3:
        return {"available": False, "note": "too_few_symbols_loaded", "symbols_attempted": syms}
    ex_cols = [c for c in panel_all.columns if c not in VIN]
    panel_ex = panel_all[ex_cols] if ex_cols else panel_all.iloc[:, 0:0]

    ema_all = pd.DataFrame({c: ema50(panel_all[c]) for c in panel_all.columns}, index=panel_all.index)
    ema_ex = pd.DataFrame({c: ema50(panel_ex[c]) for c in panel_ex.columns}, index=panel_ex.index) if ex_cols else None

    rows_full: list[dict] = []
    rows_ex: list[dict] = []
    for i in sorted(set(anchor_indices)):
        if i >= len(master_dates):
            continue
        d = str(master_dates[i].date())
        bf = breadth_snapshot_at_i(panel_all, ema_all, i)
        bf["anchor_date"] = d
        rows_full.append(bf)
        if ema_ex is not None and panel_ex.shape[1] > 0:
            be = breadth_snapshot_at_i(panel_ex, ema_ex, i)
            be["anchor_date"] = d
            rows_ex.append(be)

    return {
        "available": True,
        "universe_source": str(watchlist_path),
        "symbols_loaded": loaded,
        "ex_vin_universe_excludes": sorted(VIN),
        "full_universe": {"by_anchor": rows_full},
        "ex_vin_universe": {"by_anchor": rows_ex} if rows_ex else {"by_anchor": [], "note": "no_non_vin_symbols"},
    }


def summarize_breadth_list(rows: list[dict]) -> dict:
    if not rows:
        return {}
    p50 = [r.get("pct_above_ema50") for r in rows if r.get("pct_above_ema50") is not None]
    m20 = [r.get("median_20d_fwd_return") for r in rows if r.get("median_20d_fwd_return") is not None]
    ad = [r.get("advance_decline_1d") for r in rows if r.get("advance_decline_1d") is not None]
    return {
        "median_pct_above_ema50_across_anchors": float(np.median(p50)) if p50 else None,
        "median_median_20d_fwd_across_anchors": float(np.median(m20)) if m20 else None,
        "median_ad_1d_across_anchors": float(np.median(ad)) if ad else None,
        "n_anchor_snapshots": len(rows),
    }
