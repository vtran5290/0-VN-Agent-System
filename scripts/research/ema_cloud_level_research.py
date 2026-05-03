#!/usr/bin/env python3
"""
EMA Cloud + Price Level Breakout/Retest/Reclaim Research Pipeline
Vietnam equities, 2023-01-01 to latest available.

Strict no-leakage: signal on bar t uses only data known by close of bar t.
Entry at open of bar t+1. All levels built from data up to t-1 (exclusive).

Research baseline (Vingroup / robustness): `docs/research/VIN_EMA_CLOUD_BASELINE.md`
- Default: **VPL** dropped from the panel if it has **< 252** daily bars (use `--keep-vpl-below-252` to keep it).
- Use **`--ex-vin`** for an ex-VIN cut (excludes VIC, VHM, VRE). Important conclusions should compare **full vs ex-VIN** (two runs).

Usage:
    .venv/Scripts/python.exe scripts/research/ema_cloud_level_research.py
    .venv/Scripts/python.exe scripts/research/ema_cloud_level_research.py --no-fetch
    .venv/Scripts/python.exe scripts/research/ema_cloud_level_research.py --workers 8
    .venv/Scripts/python.exe scripts/research/ema_cloud_level_research.py --rebuild-cache
    .venv/Scripts/python.exe scripts/research/ema_cloud_level_research.py --focused-grid --ex-vin
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from src.data.fireant_client import get_client  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────────────────────
DATA_STOCKS = REPO / "data" / "stocks"
OUT_DIR = REPO / "data" / "research" / "ema_cloud"
CACHE_PARQUET = OUT_DIR / "ohlcv_panel_cache.parquet"
UNIVERSE_FILE = REPO / "config" / "universe_liquid_adv50_2b.txt"

# ── Research constants ────────────────────────────────────────────────────────
HISTORY_START = "2023-01-01"
LOCAL_CSV_START = "2024-01-30"   # local data/stocks/*.csv start
SUCCESS_TARGET = 0.15            # +15% target for trade success
SUCCESS_STOP = 0.08              # -8% stop for trade success
HORIZON_TRADING = [63, 126]      # trading-day horizons (~quarter, ~half-year)
HORIZON_CALENDAR = [90, 180]     # calendar-day approximations
HORIZON_NAMES = ["63d", "126d", "90cal", "180cal"]
MIN_TRADES_TRAIN = 30            # minimum trades in train slice to count a param combo

# Vingroup + VPL policy — SSOT: docs/research/VIN_EMA_CLOUD_BASELINE.md
EX_VIN_SYMBOLS = frozenset({"VIC", "VHM", "VRE"})
VPL_SYMBOL = "VPL"
MIN_BARS_VPL_FOR_RESEARCH = 252


# ─── Parameter Dataclasses ───────────────────────────────────────────────────

@dataclass
class EMAParams:
    fast: int = 21
    slow: int = 55


@dataclass
class LevelParams:
    max_candles: int = 240           # bars to look back for level detection (broad mode)
    use_recent_base: bool = False    # if True, anchor scan to recent base low
    recent_base_window: int = 120    # bars to scan for lowest low (recent-base mode)
    min_bars_after_base: int = 20    # scan levels only >= this many bars after the base low
    pct_diff: float = 0.50           # % tolerance to group nearby highs/lows into one level
    min_matches: int = 4             # minimum touches to qualify as a level
    min_dist_pct: float = 2.0        # % minimum distance between two adjacent levels
    n_levels: int = 5                # keep at most n nearest levels each side


@dataclass
class SignalParams:
    close_buffer: float = 0.30       # % above resistance required for breakout close
    retest_window: int = 8           # max bars after breakout to watch for retest
    reclaim_lookback: int = 8        # max bars after level-loss to watch for reclaim
    touch_tolerance: float = 0.50    # % — retest low must be within this % above the level
    undercut_tolerance: float = 0.80 # % — retest low may dip this % below the level
    vol_mult_breakout: float = 1.2   # volume must be >= this × vol_ma20 for breakout
    retest_vol_max: float = 1.3      # retest volume must be <= this × vol_ma20
    adv50_min_bn: float = 2.0        # ADV50 >= 2B VND/day (0 = no filter)


@dataclass
class ResearchParams:
    ema: EMAParams = field(default_factory=EMAParams)
    level: LevelParams = field(default_factory=LevelParams)
    signal: SignalParams = field(default_factory=SignalParams)

    def key(self) -> str:
        e, l, s = self.ema, self.level, self.signal
        return (
            f"f{e.fast}_s{e.slow}"
            f"_rb{int(l.use_recent_base)}"
            f"_mc{l.max_candles}"
            f"_rbw{l.recent_base_window}"
            f"_pd{l.pct_diff:.2f}"
            f"_mm{l.min_matches}"
            f"_cb{s.close_buffer:.2f}"
        )

    def to_flat_dict(self) -> dict:
        d: dict = {}
        for k, v in asdict(self.ema).items():
            d[f"ema_{k}"] = v
        for k, v in asdict(self.level).items():
            d[f"lvl_{k}"] = v
        for k, v in asdict(self.signal).items():
            d[f"sig_{k}"] = v
        return d


# ─── SECTION 1: DATA LOADING ─────────────────────────────────────────────────

def load_universe() -> List[str]:
    return [s.strip() for s in UNIVERSE_FILE.read_text().splitlines() if s.strip()]


def apply_vin_baseline_panel_filters(
    panel: pd.DataFrame,
    *,
    ex_vin: bool,
    exclude_vpl_if_bars_lt_252: bool,
) -> Tuple[pd.DataFrame, List[str]]:
    """Filter loaded OHLCV panel per VIN_EMA_CLOUD_BASELINE. Returns (filtered_panel, log_lines)."""
    notes: List[str] = []
    if panel.empty:
        return panel, ["Panel empty — no baseline filters applied."]
    sym_counts = panel.groupby("symbol", observed=True).size()
    keep = set(sym_counts.index.astype(str))

    if exclude_vpl_if_bars_lt_252 and VPL_SYMBOL in keep:
        nbar = int(sym_counts[VPL_SYMBOL])
        if nbar < MIN_BARS_VPL_FOR_RESEARCH:
            keep.discard(VPL_SYMBOL)
            notes.append(
                f"Excluded {VPL_SYMBOL}: {nbar} bars in panel (< {MIN_BARS_VPL_FOR_RESEARCH} per research baseline)."
            )

    if ex_vin:
        removed = sorted(EX_VIN_SYMBOLS & keep)
        keep -= EX_VIN_SYMBOLS
        if removed:
            notes.append("ex-VIN universe: removed " + ", ".join(removed) + ".")

    out = panel[panel["symbol"].astype(str).isin(keep)].copy()
    if not notes:
        notes.append(
            "VIN baseline filters: VPL policy satisfied or N/A; ex-VIN not requested "
            "(see docs/research/VIN_EMA_CLOUD_BASELINE.md for dual full vs ex-VIN reporting)."
        )
    return out, notes


def _load_local_csv(symbol: str) -> pd.DataFrame:
    path = DATA_STOCKS / f"{symbol}.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    df.columns = [c.lower() for c in df.columns]
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "value" not in df.columns:
        df["value"] = df["close"] * df["volume"] * 1000  # thousands VND × volume
    return df


def _fetch_fireant(client, symbol: str, start: str, end: str) -> pd.DataFrame:
    try:
        df = client.get_ohlcv(symbol, start=start, end=end)
        if df is None or df.empty:
            return pd.DataFrame()
        df["date"] = pd.to_datetime(df["date"])
        df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
        if "value" not in df.columns:
            df["value"] = df["close"] * df["volume"] * 1000
        return df
    except Exception as exc:
        log.debug(f"FireAnt {symbol}: {exc}")
        return pd.DataFrame()


def _combine_local_and_fetched(df_fa: pd.DataFrame, df_local: pd.DataFrame) -> pd.DataFrame:
    cutoff = pd.Timestamp(LOCAL_CSV_START)
    parts = []
    if not df_fa.empty:
        parts.append(df_fa[df_fa["date"] < cutoff].copy())
    if not df_local.empty:
        parts.append(df_local[df_local["date"] >= cutoff].copy())
    if not parts:
        return pd.DataFrame()
    df = pd.concat(parts).drop_duplicates(subset="date").sort_values("date").reset_index(drop=True)
    return df


def load_panel(
    symbols: List[str],
    start: str,
    end: str,
    no_fetch: bool = False,
    rebuild_cache: bool = False,
    workers: int = 4,
) -> pd.DataFrame:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not rebuild_cache and CACHE_PARQUET.exists():
        log.info(f"Loading cached panel from {CACHE_PARQUET}")
        panel = pd.read_parquet(CACHE_PARQUET)
        panel["date"] = pd.to_datetime(panel["date"])
        return panel

    log.info(f"Building OHLCV panel for {len(symbols)} symbols ({start} → {end})")
    client = None if no_fetch else get_client(timeout=60)

    def fetch_one(sym: str) -> Optional[pd.DataFrame]:
        df_local = _load_local_csv(sym)
        if no_fetch or client is None:
            df = df_local
        else:
            df_fa = _fetch_fireant(client, sym, start, LOCAL_CSV_START)
            df = _combine_local_and_fetched(df_fa, df_local)
        if df.empty:
            return None
        df["symbol"] = sym
        return df

    dfs: List[pd.DataFrame] = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fetch_one, s): s for s in symbols}
        done = 0
        for fut in as_completed(futs):
            sym = futs[fut]
            try:
                df = fut.result()
                if df is not None and not df.empty:
                    dfs.append(df)
            except Exception as exc:
                log.warning(f"Failed {sym}: {exc}")
            done += 1
            if done % 50 == 0:
                log.info(f"  loaded {done}/{len(symbols)}")

    if not dfs:
        raise RuntimeError("No data loaded for any symbol.")

    panel = pd.concat(dfs, ignore_index=True)
    panel["date"] = pd.to_datetime(panel["date"])
    panel = panel[
        (panel["date"] >= pd.Timestamp(start)) & (panel["date"] <= pd.Timestamp(end))
    ].copy()
    panel.sort_values(["symbol", "date"], inplace=True)
    panel.reset_index(drop=True, inplace=True)

    log.info(f"Panel: {panel['symbol'].nunique()} symbols, {len(panel):,} rows. Caching...")
    panel.to_parquet(CACHE_PARQUET)
    return panel


# ─── SECTION 2: INDICATORS ───────────────────────────────────────────────────

def add_ema_cloud(df: pd.DataFrame, fast: int, slow: int) -> pd.DataFrame:
    df = df.copy()
    df["ema_fast"] = df["close"].ewm(span=fast, adjust=False).mean()
    df["ema_slow"] = df["close"].ewm(span=slow, adjust=False).mean()
    df["bull_cloud"] = df["ema_fast"] > df["ema_slow"]
    df["above_cloud"] = df["close"] > df[["ema_fast", "ema_slow"]].max(axis=1)
    return df


def add_vol_ma(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    df = df.copy()
    df["vol_ma20"] = df["volume"].rolling(period, min_periods=max(period // 2, 5)).mean()
    return df


def add_adv50(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "value" not in df.columns:
        df["value"] = df["close"] * df["volume"] * 1000
    # adv50 in billions VND
    df["adv50"] = df["value"].rolling(50, min_periods=25).mean() / 1e9
    return df


# ─── SECTION 3: PRICE LEVEL DETECTION ───────────────────────────────────────

def precompute_local_extrema(
    high: np.ndarray, low: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    """Return (local_high_indices, local_low_indices). Strict: requires adjacent bars."""
    n = len(high)
    if n < 3:
        return np.array([], dtype=int), np.array([], dtype=int)
    lh = np.zeros(n, bool)
    ll = np.zeros(n, bool)
    lh[1:-1] = (high[1:-1] > high[:-2]) & (high[1:-1] > high[2:])
    ll[1:-1] = (low[1:-1] < low[:-2]) & (low[1:-1] < low[2:])
    return np.where(lh)[0], np.where(ll)[0]


def cluster_prices(prices: np.ndarray, pct_diff: float, min_matches: int) -> List[float]:
    """
    Sort prices, then greedily merge into groups where each price is within
    pct_diff % of the group's first member. Return mean of groups >= min_matches.
    """
    if len(prices) == 0:
        return []
    arr = np.sort(prices.astype(float))
    groups: List[List[float]] = [[arr[0]]]
    for p in arr[1:]:
        ref = groups[-1][0]
        if ref > 0 and (p - ref) / ref * 100.0 <= pct_diff:
            groups[-1].append(p)
        else:
            groups.append([p])
    return [float(np.mean(g)) for g in groups if len(g) >= min_matches]


def thin_levels(levels: List[float], min_dist_pct: float) -> List[float]:
    """Remove levels too close to each other (keep the lower one of each pair)."""
    if len(levels) <= 1:
        return list(levels)
    srt = sorted(levels)
    result = [srt[0]]
    for lvl in srt[1:]:
        if result[-1] > 0 and (lvl - result[-1]) / result[-1] * 100.0 >= min_dist_pct:
            result.append(lvl)
    return result


def compute_levels_at_bar(
    t: int,
    lh_idx: np.ndarray,
    ll_idx: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    current_close: float,
    lp: LevelParams,
) -> Tuple[Optional[float], Optional[float]]:
    """
    At bar t, compute nearest resistance (above close) and nearest support (below close).
    Uses ONLY bars in [window_start, t-1] — strict no-leakage.
    Local highs at bar i require high[i+1] to be known, so bars up to t-2 are confirmed;
    we use t-1 as the exclusive upper bound (bar t-1's local-high status confirmed at t).
    """
    window_end = t - 1
    if window_end < 2:
        return None, None

    window_start = max(0, t - lp.max_candles)

    if lp.use_recent_base:
        base_start = max(0, t - lp.recent_base_window)
        base_end = t  # look at lows[base_start : t]
        if base_end > base_start + 1:
            base_low_rel = int(np.argmin(low[base_start:base_end]))
            base_low_abs = base_start + base_low_rel
            scan_start = base_low_abs + lp.min_bars_after_base
            window_start = max(window_start, scan_start)

    if window_start >= window_end:
        return None, None

    # Slice pre-computed local extrema indices to the window
    mask_h = (lh_idx >= window_start) & (lh_idx < window_end)
    lh_prices = high[lh_idx[mask_h]] if mask_h.any() else np.array([])

    mask_l = (ll_idx >= window_start) & (ll_idx < window_end)
    ll_prices = low[ll_idx[mask_l]] if mask_l.any() else np.array([])

    raw_res = cluster_prices(lh_prices, lp.pct_diff, lp.min_matches)
    raw_sup = cluster_prices(ll_prices, lp.pct_diff, lp.min_matches)

    res_levels = thin_levels(raw_res, lp.min_dist_pct)
    sup_levels = thin_levels(raw_sup, lp.min_dist_pct)

    res_above = sorted([l for l in res_levels if l > current_close])[: lp.n_levels]
    sup_below = sorted([l for l in sup_levels if l < current_close], reverse=True)[: lp.n_levels]

    return (res_above[0] if res_above else None, sup_below[0] if sup_below else None)


# ─── SECTION 4: SIGNAL DETECTION ─────────────────────────────────────────────

SIGNAL_BREAKOUT = "breakout"
SIGNAL_RETEST = "retest"
SIGNAL_RECLAIM = "reclaim"


def detect_signals_for_symbol(
    symbol: str,
    df: pd.DataFrame,
    params: ResearchParams,
) -> pd.DataFrame:
    """
    Bar-by-bar signal detection. Returns DataFrame of signal events.
    Entry price is open[t+1] (next bar open after signal).
    """
    min_bars = params.ema.slow + 30
    if len(df) < min_bars + 2:
        return pd.DataFrame()

    df = add_ema_cloud(df, params.ema.fast, params.ema.slow)
    df = add_vol_ma(df)
    df = add_adv50(df)

    high = df["high"].values.astype(float)
    low = df["low"].values.astype(float)
    close = df["close"].values.astype(float)
    open_ = df["open"].values.astype(float)
    volume = df["volume"].values.astype(float)
    ema_fast = df["ema_fast"].values
    ema_slow = df["ema_slow"].values
    bull_cloud = df["bull_cloud"].values
    above_cloud = df["above_cloud"].values
    vol_ma = df["vol_ma20"].values
    adv50 = df["adv50"].values
    dates = df["date"].values
    n = len(df)

    lh_idx, ll_idx = precompute_local_extrema(high, low)
    lp = params.level
    sp = params.signal

    # Pre-compute levels for all bars (avoids double-computing t and t-1 in the loop)
    all_res = np.full(n, np.nan)
    all_sup = np.full(n, np.nan)
    warmup = max(params.ema.slow + 10, 60)
    for t in range(warmup, n):
        r, s = compute_levels_at_bar(t, lh_idx, ll_idx, high, low, close[t], lp)
        all_res[t] = r if r is not None else np.nan
        all_sup[t] = s if s is not None else np.nan

    rows: List[dict] = []

    # State machine: tracks one active setup at a time per symbol
    state: Optional[dict] = None  # keys: type, bar, level, [loss_bar]

    for t in range(warmup + 1, n - 1):  # -1 so open[t+1] exists
        # Liquidity gate
        if not np.isnan(adv50[t]) and adv50[t] < sp.adv50_min_bn:
            continue
        if np.isnan(ema_fast[t]) or np.isnan(ema_slow[t]):
            continue

        prev_res = all_res[t - 1]  # resistance known at close of bar t-1
        vol_ratio = (
            volume[t] / vol_ma[t]
            if (vol_ma[t] > 0 and not np.isnan(vol_ma[t]))
            else np.nan
        )
        vol_ratio_f = float(vol_ratio) if not np.isnan(vol_ratio) else 1.0

        def _make_row(sig_type: str, level: float) -> dict:
            return {
                "symbol": symbol,
                "signal_bar": t,
                "signal_date": pd.Timestamp(dates[t]),
                "signal_type": sig_type,
                "level_price": level,
                "close_at_signal": float(close[t]),
                "entry_price": float(open_[t + 1]),
                "ema_fast_val": float(ema_fast[t]),
                "ema_slow_val": float(ema_slow[t]),
                "bull_cloud": bool(bull_cloud[t]),
                "above_cloud": bool(above_cloud[t]),
                "vol_ratio": vol_ratio_f,
            }

        # ── BREAKOUT ──────────────────────────────────────────────────────────
        if (
            not np.isnan(prev_res)
            and bool(bull_cloud[t])
            and bool(above_cloud[t])
            and close[t] > prev_res * (1.0 + sp.close_buffer / 100.0)
            and (np.isnan(vol_ratio) or vol_ratio >= sp.vol_mult_breakout)
        ):
            rows.append(_make_row(SIGNAL_BREAKOUT, float(prev_res)))
            state = {"type": "post_breakout", "bar": t, "level": float(prev_res)}
            continue  # don't check retest/reclaim on the breakout bar itself

        # ── RETEST (post-breakout window) ─────────────────────────────────────
        if (
            state is not None
            and state["type"] == "post_breakout"
            and 0 < t - state["bar"] <= sp.retest_window
        ):
            L = state["level"]
            low_near = low[t] <= L * (1.0 + sp.touch_tolerance / 100.0)
            no_deep_cut = low[t] >= L * (1.0 - sp.undercut_tolerance / 100.0)
            close_holds = close[t] >= L * (1.0 - sp.undercut_tolerance / 100.0)
            above_fast = close[t] > ema_fast[t]
            vol_ok = np.isnan(vol_ratio) or vol_ratio <= sp.retest_vol_max

            if (low_near and no_deep_cut and close_holds and above_fast
                    and bool(bull_cloud[t]) and bool(above_cloud[t]) and vol_ok):
                rows.append(_make_row(SIGNAL_RETEST, L))
                state = None
                continue

            # Price closes below level → switch to watching for reclaim
            if close[t] < L:
                state = {"type": "post_loss", "bar": state["bar"], "loss_bar": t, "level": L}

        # ── RECLAIM (post-loss window) ─────────────────────────────────────────
        elif (
            state is not None
            and state["type"] == "post_loss"
            and 0 < t - state["loss_bar"] <= sp.reclaim_lookback
        ):
            L = state["level"]
            close_above = close[t] > L * (1.0 + sp.close_buffer / 100.0)
            vol_ok = np.isnan(vol_ratio) or vol_ratio >= sp.vol_mult_breakout

            if close_above and bool(bull_cloud[t]) and bool(above_cloud[t]) and vol_ok:
                rows.append(_make_row(SIGNAL_RECLAIM, L))
                state = None
                continue

        # ── EXPIRE STATE ──────────────────────────────────────────────────────
        if state is not None:
            ref_bar = state.get("loss_bar", state["bar"])
            window = sp.reclaim_lookback if state["type"] == "post_loss" else sp.retest_window
            if t - ref_bar > window:
                state = None

    return pd.DataFrame(rows) if rows else pd.DataFrame()


# ─── SECTION 5: FORWARD RETURNS ──────────────────────────────────────────────

def compute_forward_returns(df_sym: pd.DataFrame, signals: pd.DataFrame) -> pd.DataFrame:
    """
    Attach forward return columns to signal rows.
    Entry at open[t+1]. Horizons: 63d, 126d trading days; 90cal, 180cal calendar days.
    trade_success_Xd = hit +15% before -8% within horizon.
    """
    if signals.empty:
        return signals

    close = df_sym["close"].values.astype(float)
    high = df_sym["high"].values.astype(float)
    low = df_sym["low"].values.astype(float)
    dates = pd.to_datetime(df_sym["date"].values)
    n = len(df_sym)

    result_rows = []
    for _, row in signals.iterrows():
        t = int(row["signal_bar"])
        entry_t = t + 1
        if entry_t >= n:
            continue
        entry_px = float(row["entry_price"])
        if entry_px <= 0:
            continue

        r = dict(row)

        # Trading-day horizons
        for h_bars, h_name in zip(HORIZON_TRADING, ["63d", "126d"]):
            exit_t = min(entry_t + h_bars, n - 1)
            if exit_t <= entry_t:
                continue
            r[f"is_truncated_{h_name}"] = int(exit_t == n - 1 and entry_t + h_bars > n - 1)
            fwd = close[exit_t] / entry_px - 1.0
            mfe = float(np.max(high[entry_t : exit_t + 1])) / entry_px - 1.0
            mae = float(np.min(low[entry_t : exit_t + 1])) / entry_px - 1.0
            r[f"fwd_ret_{h_name}"] = round(float(fwd), 6)
            r[f"mfe_{h_name}"] = round(float(mfe), 6)
            r[f"mae_{h_name}"] = round(float(mae), 6)
            r[f"win_{h_name}"] = int(fwd > 0)
            r[f"win10_{h_name}"] = int(fwd > 0.10)
            r[f"win15_{h_name}"] = int(fwd > 0.15)
            # Trade success: hit +15% before -8%
            success = False
            for b in range(entry_t, exit_t + 1):
                if high[b] / entry_px - 1.0 >= SUCCESS_TARGET:
                    success = True
                    break
                if low[b] / entry_px - 1.0 <= -SUCCESS_STOP:
                    break
            r[f"trade_success_{h_name}"] = int(success)

        # Calendar-day horizons
        entry_date = dates[entry_t]
        for cal_days, h_name in zip(HORIZON_CALENDAR, ["90cal", "180cal"]):
            target_date = entry_date + pd.Timedelta(days=cal_days)
            idx = int(np.searchsorted(dates, target_date))
            exit_t = min(max(idx, entry_t + 1), n - 1)
            if exit_t <= entry_t:
                continue
            r[f"is_truncated_{h_name}"] = int(exit_t == n - 1 and idx >= n - 1)
            fwd = close[exit_t] / entry_px - 1.0
            mfe = float(np.max(high[entry_t : exit_t + 1])) / entry_px - 1.0
            mae = float(np.min(low[entry_t : exit_t + 1])) / entry_px - 1.0
            r[f"fwd_ret_{h_name}"] = round(float(fwd), 6)
            r[f"mfe_{h_name}"] = round(float(mfe), 6)
            r[f"mae_{h_name}"] = round(float(mae), 6)
            r[f"win_{h_name}"] = int(fwd > 0)
            r[f"win10_{h_name}"] = int(fwd > 0.10)
            r[f"win15_{h_name}"] = int(fwd > 0.15)
            success2 = False
            for b in range(entry_t, exit_t + 1):
                if high[b] / entry_px - 1.0 >= SUCCESS_TARGET:
                    success2 = True
                    break
                if low[b] / entry_px - 1.0 <= -SUCCESS_STOP:
                    break
            r[f"trade_success_{h_name}"] = int(success2)

        result_rows.append(r)

    return pd.DataFrame(result_rows) if result_rows else pd.DataFrame()


# ─── SECTION 6: PARAM GRID ───────────────────────────────────────────────────

def build_param_grid(focused: bool = False) -> List[ResearchParams]:
    """
    Bounded grid as specified.
    Full grid: ~3300 combos (run overnight).
    Focused grid: ~150 combos covering the key dimensions (run in ~25 min with 4 workers).
    """
    if focused:
        ema_pairs = [(10, 50), (21, 55), (21, 60)]
        broad = [
            dict(use_recent_base=False, max_candles=mc)
            for mc in [120, 240]
        ]
        recent = [
            dict(use_recent_base=True, recent_base_window=rw, min_bars_after_base=mb)
            for rw, mb in [(80, 20), (120, 20), (180, 25)]
        ]
        pct_diffs = [0.30, 0.50, 0.86]
        min_matches_opts = [3, 5]
        close_buffers = [0.20, 0.30]
    else:
        ema_pairs = [
            (10, 50), (10, 55),
            (20, 50), (20, 55),
            (21, 50), (21, 55), (21, 60),
        ]
        broad = [
            dict(use_recent_base=False, max_candles=mc)
            for mc in [80, 120, 180, 240, 480]
        ]
        recent = [
            dict(use_recent_base=True, recent_base_window=rw, min_bars_after_base=mb)
            for rw, mb in [
                (60, 15), (80, 20), (100, 20),
                (120, 20), (120, 25), (180, 25),
            ]
        ]
        pct_diffs = [0.30, 0.50, 0.70, 0.86]
        min_matches_opts = [3, 4, 5]
        close_buffers = [0.15, 0.20, 0.30, 0.40]

    grid: List[ResearchParams] = []
    for fast, slow in ema_pairs:
        for lc in broad + recent:
            for pct in pct_diffs:
                for mm in min_matches_opts:
                    for cb in close_buffers:
                        p = ResearchParams(
                            ema=EMAParams(fast=fast, slow=slow),
                            level=LevelParams(
                                max_candles=lc.get("max_candles", 240),
                                use_recent_base=lc["use_recent_base"],
                                recent_base_window=lc.get("recent_base_window", 120),
                                min_bars_after_base=lc.get("min_bars_after_base", 20),
                                pct_diff=pct,
                                min_matches=mm,
                            ),
                            signal=SignalParams(close_buffer=cb),
                        )
                        grid.append(p)

    seen = set()
    deduped = []
    for p in grid:
        k = p.key()
        if k not in seen:
            seen.add(k)
            deduped.append(p)
    log.info(f"Parameter grid: {len(deduped)} unique combos ({'focused' if focused else 'full'})")
    return deduped


# ─── SECTION 7: MAIN RESEARCH LOOP ───────────────────────────────────────────

def run_all_signals(
    panel: pd.DataFrame,
    param_grid: List[ResearchParams],
    workers: int = 4,
) -> pd.DataFrame:
    """
    For each param combo, run signal detection + forward returns across all symbols.
    Returns combined trades DataFrame with param_key column.
    """
    symbols = panel["symbol"].unique().tolist()
    all_parts: List[pd.DataFrame] = []

    for pi, params in enumerate(param_grid):
        key = params.key()
        log.info(f"[{pi+1}/{len(param_grid)}] {key}")

        def process_sym(sym: str) -> pd.DataFrame:
            df_sym = panel[panel["symbol"] == sym].copy().reset_index(drop=True)
            sigs = detect_signals_for_symbol(sym, df_sym, params)
            if sigs.empty:
                return pd.DataFrame()
            return compute_forward_returns(df_sym, sigs)

        combo_parts: List[pd.DataFrame] = []
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(process_sym, s): s for s in symbols}
            for fut in as_completed(futs):
                try:
                    df_out = fut.result()
                    if df_out is not None and not df_out.empty:
                        combo_parts.append(df_out)
                except Exception as exc:
                    log.debug(f"  error: {exc}")

        if not combo_parts:
            continue

        combo_df = pd.concat(combo_parts, ignore_index=True)
        combo_df["param_key"] = key
        flat = params.to_flat_dict()
        for k, v in flat.items():
            combo_df[k] = v
        all_parts.append(combo_df)

        n_sig = len(combo_df)
        n_syms = combo_df["symbol"].nunique()
        log.info(f"  → {n_sig} signals, {n_syms} symbols")

    if not all_parts:
        return pd.DataFrame()
    return pd.concat(all_parts, ignore_index=True)


# ─── SECTION 8: EVENT STUDY ───────────────────────────────────────────────────

def aggregate_event_study(trades: pd.DataFrame) -> pd.DataFrame:
    """Aggregate forward return statistics by (param_key, signal_type) and all horizons."""
    if trades.empty:
        return pd.DataFrame()

    records = []
    grouping_cols = ["param_key", "signal_type"]

    for (key, sig_type), grp in trades.groupby(grouping_cols):
        row: dict = {
            "param_key": key,
            "signal_type": sig_type,
            "n": len(grp),
            "n_symbols": grp["symbol"].nunique(),
        }
        for h in HORIZON_NAMES:
            ret_col = f"fwd_ret_{h}"
            sc_col = f"trade_success_{h}"
            win_col = f"win_{h}"
            w10_col = f"win10_{h}"
            w15_col = f"win15_{h}"
            mfe_col = f"mfe_{h}"
            mae_col = f"mae_{h}"
            trunc_col = f"is_truncated_{h}"
            if ret_col not in grp.columns:
                continue
            # Exclude truncated forward-return windows from all stats for this horizon
            gh = grp[grp[trunc_col] == 0] if trunc_col in grp.columns else grp
            g = gh[ret_col].dropna()
            if len(g) == 0:
                continue
            row[f"n_{h}"] = len(g)
            row[f"n_truncated_{h}"] = int(len(grp) - len(gh)) if trunc_col in grp.columns else 0
            row[f"win_rate_{h}"] = round(float(gh[win_col].mean()), 4) if win_col in gh else np.nan
            row[f"win10_rate_{h}"] = round(float(gh[w10_col].mean()), 4) if w10_col in gh else np.nan
            row[f"win15_rate_{h}"] = round(float(gh[w15_col].mean()), 4) if w15_col in gh else np.nan
            row[f"success_rate_{h}"] = round(float(gh[sc_col].mean()), 4) if sc_col in gh else np.nan
            row[f"median_ret_{h}"] = round(float(g.median()), 4)
            row[f"mean_ret_{h}"] = round(float(g.mean()), 4)
            row[f"p25_ret_{h}"] = round(float(g.quantile(0.25)), 4)
            row[f"p75_ret_{h}"] = round(float(g.quantile(0.75)), 4)
            if mfe_col in gh.columns:
                row[f"mean_mfe_{h}"] = round(float(gh[mfe_col].mean()), 4)
                row[f"mean_mae_{h}"] = round(float(gh[mae_col].mean()), 4)
        records.append(row)

    df_out = pd.DataFrame(records)

    # Add param metadata columns from the first row of each key group
    meta_cols = [c for c in trades.columns if c.startswith("ema_") or c.startswith("lvl_") or c.startswith("sig_")]
    if meta_cols:
        meta = (
            trades[["param_key"] + meta_cols]
            .drop_duplicates(subset="param_key")
            .set_index("param_key")
        )
        df_out = df_out.join(meta, on="param_key")

    return df_out


# ─── SECTION 9: WALK-FORWARD OOS ─────────────────────────────────────────────

def run_walk_forward_oos(
    trades: pd.DataFrame,
    train_months: int = 12,
    embargo_months: int = 1,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Monthly expanding-window walk-forward OOS.
    - Train: months 0..M (expanding)
    - Test: month M+1 (one month at a time)
    - Select best param_key on train by: 0.6 * success_rate_63d + 0.2 * win_rate_63d + 0.2 * mean_ret_63d
    - Evaluate that key on the test month

    Returns: (oos_monthly_df, oos_param_summary_df)
    """
    if trades.empty:
        return pd.DataFrame(), pd.DataFrame()

    t_df = trades.copy()
    t_df["signal_date"] = pd.to_datetime(t_df["signal_date"])
    t_df["month"] = t_df["signal_date"].dt.to_period("M")

    months = sorted(t_df["month"].unique())
    if len(months) < train_months + 2:
        log.warning("Not enough months for walk-forward OOS.")
        return pd.DataFrame(), pd.DataFrame()

    oos_rows: List[dict] = []
    param_usage: Dict[str, int] = {}

    for i in range(train_months, len(months) - embargo_months):
        test_month = months[i + embargo_months]
        train_set = set(months[: i])

        train = t_df[t_df["month"].isin(train_set)].copy()
        test = t_df[t_df["month"] == test_month].copy()
        if train.empty or test.empty:
            continue

        # Select best param combo on train
        sc_col = "trade_success_63d"
        win_col = "win_63d"
        ret_col = "fwd_ret_63d"
        needed = [sc_col, win_col, ret_col, "param_key"]
        if not all(c in train.columns for c in needed):
            continue

        train_h = train[train["is_truncated_63d"] == 0] if "is_truncated_63d" in train.columns else train
        stats = (
            train_h.groupby("param_key")
            .agg(n=(sc_col, "count"), sc=(sc_col, "mean"), wr=(win_col, "mean"), mr=(ret_col, "mean"))
            .reset_index()
        )
        stats = stats[stats["n"] >= MIN_TRADES_TRAIN]
        if stats.empty:
            continue

        stats["score"] = 0.6 * stats["sc"] + 0.2 * stats["wr"] + 0.2 * stats["mr"].clip(upper=0.3)
        best_key = stats.loc[stats["score"].idxmax(), "param_key"]
        param_usage[best_key] = param_usage.get(best_key, 0) + 1

        test_sub = test[test["param_key"] == best_key].copy()
        if test_sub.empty:
            continue

        for sig_type in ["all", SIGNAL_BREAKOUT, SIGNAL_RETEST, SIGNAL_RECLAIM]:
            subset = test_sub if sig_type == "all" else test_sub[test_sub["signal_type"] == sig_type]
            if len(subset) < 3:
                continue
            row: dict = {
                "test_month": str(test_month),
                "best_param_key": best_key,
                "signal_type": sig_type,
                "n": len(subset),
            }
            for h in HORIZON_NAMES:
                r_col, s_col, w_col = f"fwd_ret_{h}", f"trade_success_{h}", f"win_{h}"
                trunc_col = f"is_truncated_{h}"
                if r_col not in subset.columns:
                    continue
                sub_h = subset[subset[trunc_col] == 0] if trunc_col in subset.columns else subset
                g = sub_h[r_col].dropna()
                if len(g) == 0:
                    continue
                row[f"oos_n_{h}"] = len(g)
                row[f"oos_win_{h}"] = round(float(sub_h[w_col].mean()), 4)
                row[f"oos_success_{h}"] = round(float(sub_h[s_col].mean()), 4)
                row[f"oos_median_{h}"] = round(float(g.median()), 4)
                row[f"oos_mean_{h}"] = round(float(g.mean()), 4)
                row[f"oos_p25_{h}"] = round(float(g.quantile(0.25)), 4)
                row[f"oos_p75_{h}"] = round(float(g.quantile(0.75)), 4)
            oos_rows.append(row)

    oos_df = pd.DataFrame(oos_rows) if oos_rows else pd.DataFrame()

    # Param usage summary
    param_summary_rows = []
    for pk, cnt in sorted(param_usage.items(), key=lambda x: -x[1]):
        param_summary_rows.append({"param_key": pk, "times_selected": cnt})
    param_summary = pd.DataFrame(param_summary_rows)

    return oos_df, param_summary


# ─── SECTION 10: PORTFOLIO BACKTEST ──────────────────────────────────────────

def run_portfolio_backtest(
    trades: pd.DataFrame,
    max_positions: int = 10,
    hold_bars: int = 63,
    start_capital: float = 1.0,
) -> Dict:
    """
    Simple equal-weight portfolio backtest.
    - Entry at open[t+1] after signal
    - Exit at fixed horizon (hold_bars) or at failure (mae <= -8%)
    - Max concurrent positions = max_positions
    - Selects by earliest signal date, then highest vol_ratio as tiebreaker
    """
    if trades.empty:
        return {}

    df = trades.sort_values(["signal_date", "vol_ratio"], ascending=[True, False]).copy()
    df["signal_date"] = pd.to_datetime(df["signal_date"])

    # Use 63d forward return as the trade P&L
    ret_col = "fwd_ret_63d"
    if ret_col not in df.columns:
        return {}

    all_dates = sorted(df["signal_date"].unique())
    capital = start_capital
    portfolio_value = [capital]
    portfolio_dates = [all_dates[0] if all_dates else pd.Timestamp.today()]

    active: List[dict] = []  # {exit_date, ret, symbol}
    trade_log: List[dict] = []
    max_dd_peak = capital
    max_dd = 0.0

    for d in all_dates:
        # Settle trades that have exited by today
        still_active = []
        for pos in active:
            if pos["exit_date"] <= d:
                # realized P&L
                pnl = pos["ret"]
                capital *= (1.0 + pnl / max_positions)
                trade_log.append({"date": pos["entry_date"], "symbol": pos["symbol"], "ret": pnl})
            else:
                still_active.append(pos)
        active = still_active

        # Open new positions
        today_sigs = df[df["signal_date"] == d].head(max(0, max_positions - len(active)))
        for _, row in today_sigs.iterrows():
            if len(active) >= max_positions:
                break
            r = row.get(ret_col, 0.0)
            if pd.isna(r):
                continue
            entry_d = pd.Timestamp(row["signal_date"])
            exit_d = entry_d + pd.Timedelta(days=hold_bars * 1.4)  # approx calendar days
            active.append({
                "entry_date": entry_d,
                "exit_date": exit_d,
                "ret": float(r),
                "symbol": row["symbol"],
            })

        portfolio_value.append(capital)
        portfolio_dates.append(d)
        if capital > max_dd_peak:
            max_dd_peak = capital
        dd = (max_dd_peak - capital) / max_dd_peak
        if dd > max_dd:
            max_dd = dd

    if not trade_log:
        return {}

    tl = pd.DataFrame(trade_log)
    n_years = max((all_dates[-1] - all_dates[0]).days / 365.25, 0.1)
    total_ret = capital / start_capital - 1.0
    cagr = (capital / start_capital) ** (1.0 / n_years) - 1.0
    sharpe = tl["ret"].mean() / tl["ret"].std() * np.sqrt(252 / hold_bars) if tl["ret"].std() > 0 else np.nan
    hit_rate = float((tl["ret"] > 0).mean())
    avg_trade = float(tl["ret"].mean())

    return {
        "n_trades": len(tl),
        "total_return": round(total_ret, 4),
        "cagr": round(cagr, 4),
        "hit_rate": round(hit_rate, 4),
        "avg_trade_ret": round(avg_trade, 4),
        "max_drawdown": round(max_dd, 4),
        "sharpe_approx": round(float(sharpe), 3) if not np.isnan(sharpe) else None,
    }


# ─── SECTION 11: OUTPUT GENERATION ───────────────────────────────────────────

def pick_best_params(event_study: pd.DataFrame) -> Dict[str, str]:
    """Pick best param_key per signal type by OOS success rate (event study on all data as proxy)."""
    if event_study.empty:
        return {}
    best: Dict[str, str] = {}
    for sig_type in [SIGNAL_BREAKOUT, SIGNAL_RETEST, SIGNAL_RECLAIM, "all"]:
        sub = event_study[event_study["signal_type"] == sig_type].copy() if sig_type != "all" else event_study.copy()
        if sub.empty:
            continue
        if "success_rate_63d" in sub.columns and "n_63d" in sub.columns:
            sub = sub[sub.get("n_63d", pd.Series(dtype=float)).fillna(0) >= 20]
        if sub.empty:
            continue
        score_col = "success_rate_63d"
        if score_col not in sub.columns:
            continue
        idx = sub[score_col].idxmax()
        best[sig_type] = sub.loc[idx, "param_key"]
    return best


def format_pct(v) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "n/a"
    return f"{v*100:.1f}%"


def write_results_summary(
    event_study: pd.DataFrame,
    oos_df: pd.DataFrame,
    param_summary: pd.DataFrame,
    portfolio_stats: dict,
    out_path: Path,
    baseline_notes: Optional[List[str]] = None,
) -> None:
    lines: List[str] = []
    lines.append("# EMA Cloud + Price Level Research — Results Summary")
    lines.append(f"\nData: Vietnam equities, {HISTORY_START} to latest (ADV50 ≥ 2B VND/day)\n")

    # OOS aggregate by signal type
    lines.append("## OOS Aggregate (walk-forward monthly, signal_type × horizon)")
    lines.append("")
    if not oos_df.empty and "oos_success_63d" in oos_df.columns:
        agg = (
            oos_df.groupby("signal_type")
            .agg(
                n_months=("test_month", "nunique"),
                n_total=("n", "sum"),
                success_63d=("oos_success_63d", "mean"),
                win_63d=("oos_win_63d", "mean"),
                median_ret_63d=("oos_median_63d", "mean"),
                success_126d=("oos_success_126d", "mean"),
                win_126d=("oos_win_126d", "mean"),
            )
            .reset_index()
        )
        lines.append("| Signal | Months | Trades | Success63d | Win63d | Median63d | Success126d | Win126d |")
        lines.append("|--------|--------|--------|-----------|--------|-----------|------------|---------|")
        for _, r in agg.iterrows():
            lines.append(
                f"| {r['signal_type']} | {int(r.get('n_months',0))} | {int(r.get('n_total',0))} | "
                f"{format_pct(r.get('success_63d'))} | {format_pct(r.get('win_63d'))} | "
                f"{format_pct(r.get('median_ret_63d'))} | "
                f"{format_pct(r.get('success_126d'))} | {format_pct(r.get('win_126d'))} |"
            )
    else:
        lines.append("_OOS data not available (insufficient months)._")

    lines.append("")

    # Most-selected params in OOS
    lines.append("## Most Selected Parameters (OOS fold count)")
    lines.append("")
    if not param_summary.empty:
        for _, r in param_summary.head(10).iterrows():
            lines.append(f"- `{r['param_key']}`: selected {int(r['times_selected'])} fold(s)")
    else:
        lines.append("_No OOS param selection data._")

    lines.append("")

    # Recent-base vs broad comparison
    lines.append("## Recent-Base-Only vs Broad-Level Comparison (event study, 63d)")
    lines.append("")
    if not event_study.empty and "success_rate_63d" in event_study.columns:
        if "lvl_use_recent_base" in event_study.columns:
            cmp = (
                event_study.groupby("lvl_use_recent_base")
                .agg(
                    n=("n", "sum"),
                    success_63d=("success_rate_63d", "mean"),
                    win_63d=("win_rate_63d", "mean"),
                    median_ret_63d=("median_ret_63d", "mean"),
                )
                .reset_index()
            )
            for _, r in cmp.iterrows():
                mode = "Recent-Base" if r["lvl_use_recent_base"] else "Broad"
                lines.append(
                    f"- **{mode}**: n={int(r['n'])}, "
                    f"success={format_pct(r.get('success_63d'))}, "
                    f"win={format_pct(r.get('win_63d'))}, "
                    f"median={format_pct(r.get('median_ret_63d'))}"
                )

    lines.append("")

    # Portfolio stats
    lines.append("## Portfolio Backtest (best params, 63d hold, max 10 positions)")
    lines.append("")
    if portfolio_stats:
        for k, v in portfolio_stats.items():
            lines.append(f"- **{k}**: {v}")
    else:
        lines.append("_No portfolio stats._")

    lines.append("")

    # Recommended params (most OOS-selected)
    lines.append("## Recommended Default Parameters")
    lines.append("")
    if not param_summary.empty:
        best_key = param_summary.iloc[0]["param_key"]
        lines.append(f"**Most OOS-robust param key:** `{best_key}`")
        lines.append("")
        lines.append("Decode: `f{fast}_s{slow}_rb{recent_base}_mc{max_candles}_rbw{rbw}_pd{pct_diff}_mm{min_matches}_cb{close_buffer}`")
    else:
        lines.append("_Insufficient OOS data for recommendation. See `event_study.csv` for full-sample stats._")

    lines.append("")
    lines.append("## Caveats")
    lines.append("")
    lines.append("### Universe / VIN research baseline (this run)")
    lines.append("")
    for ln in baseline_notes or ["(no baseline filter metadata passed)"]:
        lines.append(f"- {ln}")
    lines.append(
        "- For robustness, compare **full universe** vs **`--ex-vin`** runs; VIN can distort **return tails** "
        "even when aggregate success rates move little (`docs/research/VIN_EMA_CLOUD_BASELINE.md`)."
    )
    lines.append("")
    lines.append("- OOS walk-forward uses expanding window from 2023-01; early folds have thin sample sizes.")
    lines.append("- Level detection is bar-by-bar with strict no-leakage (local highs confirmed to t-2).")
    lines.append("- Entry at next-bar open; slippage and transaction costs not modeled.")
    lines.append("- VN T+2.5 settlement not modeled — live implementation must account for this.")
    lines.append("- ADV50 ≥ 2B VND filter applied; results may differ for smaller stocks.")
    lines.append("- `trade_success` = hit +15% before -8% within horizon; does not model pyramiding or partial exits.")
    lines.append("")
    lines.append("## Files")
    lines.append("")
    lines.append("| File | Description |")
    lines.append("|------|-------------|")
    lines.append("| `trades.csv` | All signal events + forward returns for every param combo |")
    lines.append("| `event_study.csv` | Aggregated statistics per (param_key, signal_type) |")
    lines.append("| `parameter_results.csv` | Ranked param combos by OOS success rate |")
    lines.append("| `oos_summary.csv` | Monthly walk-forward OOS results |")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"Results summary → {out_path}")


# ─── SECTION 12: SERENA ONBOARDING SUPPORT ───────────────────────────────────
# (called at end of main after outputs are written)

def _write_serena_memory_info() -> dict:
    return {
        "project": "EMA Cloud + Price Level research pipeline, VN equities",
        "main_script": "scripts/research/ema_cloud_level_research.py",
        "outputs": str(OUT_DIR),
        "cache": str(CACHE_PARQUET),
        "strategy_spec": "docs/ema_cloud_strategy_spec.md",
        "rule_mapping": "docs/ema_cloud_exact_rule_mapping.md",
        "notes": [
            "No AFL files exist — strategy ported from spec in prompt",
            "Data: FireAnt API for 2023, data/stocks/ for 2024+",
            "Universe: config/universe_liquid_adv50_2b.txt (272 symbols)",
            "Strict no-leakage: levels use data[0:t-1], signal on bar t, entry at bar t+1 open",
            "VIN + robustness baseline: docs/research/VIN_EMA_CLOUD_BASELINE.md; script flags --ex-vin, --keep-vpl-below-252",
        ],
    }


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="EMA Cloud + Level Breakout/Retest/Reclaim Research")
    ap.add_argument("--start", default=HISTORY_START, help="Data start date (default 2023-01-01)")
    ap.add_argument("--end", default="2026-04-30", help="Data end date")
    ap.add_argument("--no-fetch", action="store_true", help="Use local CSVs only (no FireAnt API)")
    ap.add_argument("--rebuild-cache", action="store_true", help="Rebuild OHLCV cache from scratch")
    ap.add_argument("--workers", type=int, default=4, help="Thread pool workers")
    ap.add_argument("--train-months", type=int, default=12, help="Walk-forward initial train window (months)")
    ap.add_argument("--adv-filter", type=float, default=2.0, help="ADV50 filter in billions VND (0 = off)")
    ap.add_argument("--max-positions", type=int, default=10, help="Portfolio max concurrent positions")
    ap.add_argument("--quick", action="store_true", help="Quick mode: 10-combo grid for testing")
    ap.add_argument("--focused-grid", action="store_true", help="Focused grid: ~150 combos, ~25 min run")
    ap.add_argument(
        "--ex-vin",
        action="store_true",
        help="Exclude VIC, VHM, VRE from the panel (ex-VIN universe; see docs/research/VIN_EMA_CLOUD_BASELINE.md)",
    )
    ap.add_argument(
        "--keep-vpl-below-252",
        action="store_true",
        help="Keep VPL even when the panel has fewer than 252 daily bars for VPL (opt out of baseline exclusion)",
    )
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load universe
    symbols = load_universe()
    log.info(f"Universe: {len(symbols)} symbols from {UNIVERSE_FILE.name}")

    # 2. Load panel
    panel = load_panel(
        symbols=symbols,
        start=args.start,
        end=args.end,
        no_fetch=args.no_fetch,
        rebuild_cache=args.rebuild_cache,
        workers=args.workers,
    )
    log.info(
        f"Panel ready: {panel['symbol'].nunique()} symbols, "
        f"{panel['date'].min().date()} → {panel['date'].max().date()}, "
        f"{len(panel):,} rows"
    )

    panel, baseline_notes = apply_vin_baseline_panel_filters(
        panel,
        ex_vin=args.ex_vin,
        exclude_vpl_if_bars_lt_252=not args.keep_vpl_below_252,
    )
    for bn in baseline_notes:
        log.info(f"VIN baseline: {bn}")
    if panel.empty:
        log.error("Panel empty after VIN baseline filters — aborting.")
        return

    # 3. Build param grid
    param_grid = build_param_grid(focused=args.focused_grid)
    if args.quick:
        param_grid = param_grid[:10]
        log.info("Quick mode: using first 10 combos")

    # Override ADV filter from CLI
    for p in param_grid:
        p.signal.adv50_min_bn = args.adv_filter

    # 4. Run all signals + forward returns
    log.info(f"Running signal detection for {len(param_grid)} param combos × {panel['symbol'].nunique()} symbols...")
    trades = run_all_signals(panel, param_grid, workers=args.workers)

    if trades.empty:
        log.warning("No signals generated. Check data range, universe, and parameters.")
        return

    log.info(f"Total signal events: {len(trades):,} across {trades['symbol'].nunique()} symbols, "
             f"{trades['param_key'].nunique()} param combos")

    # 5. Event study
    log.info("Aggregating event study...")
    event_study = aggregate_event_study(trades)

    # 6. Walk-forward OOS
    log.info(f"Running walk-forward OOS (train_months={args.train_months})...")
    oos_df, param_summary = run_walk_forward_oos(trades, train_months=args.train_months)

    # 7. Portfolio backtest (use the most OOS-selected param key if available)
    portfolio_stats: dict = {}
    if not param_summary.empty and not trades.empty:
        best_key = param_summary.iloc[0]["param_key"]
        best_trades = trades[trades["param_key"] == best_key].copy()
        portfolio_stats = run_portfolio_backtest(
            best_trades,
            max_positions=args.max_positions,
            hold_bars=63,
        )
        log.info(f"Portfolio stats (key={best_key}): {portfolio_stats}")

    # 8. Build parameter results table (ranked by OOS)
    if not oos_df.empty:
        param_results = (
            oos_df.groupby(["best_param_key", "signal_type"])
            .agg(
                oos_folds=("test_month", "nunique"),
                avg_n=("n", "mean"),
                avg_success_63d=("oos_success_63d", "mean"),
                avg_win_63d=("oos_win_63d", "mean"),
                avg_median_63d=("oos_median_63d", "mean"),
                avg_success_126d=("oos_success_126d", "mean"),
            )
            .reset_index()
            .rename(columns={"best_param_key": "param_key"})
            .sort_values("avg_success_63d", ascending=False)
        )
    else:
        # Fall back to full-sample event study ranking
        param_results = event_study.sort_values("success_rate_63d", ascending=False) if not event_study.empty else pd.DataFrame()
        log.warning("OOS data empty — using full-sample event study for param_results.csv")

    # 9. Save outputs
    log.info(f"Writing outputs to {OUT_DIR}/")
    trades.to_csv(OUT_DIR / "trades.csv", index=False)
    event_study.to_csv(OUT_DIR / "event_study.csv", index=False)
    if not param_results.empty:
        param_results.to_csv(OUT_DIR / "parameter_results.csv", index=False)
    if not oos_df.empty:
        oos_df.to_csv(OUT_DIR / "oos_summary.csv", index=False)
    if not param_summary.empty:
        param_summary.to_csv(OUT_DIR / "oos_param_selection.csv", index=False)

    write_results_summary(
        event_study,
        oos_df,
        param_summary,
        portfolio_stats,
        OUT_DIR / "results_summary.md",
        baseline_notes=baseline_notes,
    )

    # 10. Console summary
    log.info("=" * 60)
    log.info("DONE. Key outputs:")
    log.info(f"  trades.csv         : {len(trades):,} rows")
    log.info(f"  event_study.csv    : {len(event_study):,} rows")
    log.info(f"  oos_summary.csv    : {len(oos_df):,} rows" if not oos_df.empty else "  oos_summary.csv    : empty (need more months)")
    log.info(f"  results_summary.md : {OUT_DIR / 'results_summary.md'}")

    if not oos_df.empty and "oos_success_63d" in oos_df.columns:
        best_oos = oos_df.groupby("signal_type")["oos_success_63d"].mean().sort_values(ascending=False)
        log.info("OOS success_63d by signal type (mean across months):")
        for stype, val in best_oos.items():
            log.info(f"  {stype:10s}: {val:.1%}")


if __name__ == "__main__":
    main()
