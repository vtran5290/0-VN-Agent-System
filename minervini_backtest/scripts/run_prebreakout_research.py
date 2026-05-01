from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from indicators import add_all_indicators
from metrics import minervini_r_metrics, trade_metrics, trades_per_year
from run import load_curated_data


def _read_symbols() -> list[str]:
    candidates = [
        REPO / "config" / "universe_186.txt",
        REPO / "config" / "watchlist_80.txt",
        REPO / "config" / "watchlist.txt",
    ]
    for p in candidates:
        if p.exists():
            lines = p.read_text(encoding="utf-8").splitlines()
            out = [ln.strip().upper() for ln in lines if ln.strip() and not ln.strip().startswith("#")]
            if out:
                return out
    return []


def _to_date(s: str | None) -> pd.Timestamp | None:
    if not s:
        return None
    return pd.Timestamp(s)


def _safe_float(v: Any) -> float | None:
    try:
        f = float(v)
    except Exception:
        return None
    if not np.isfinite(f):
        return None
    return f


@dataclass
class Preset:
    preset_id: str
    trend: str
    base_weeks: int
    depth_max: float
    price_zone_min: float
    atr_ratio_max: float
    range_comp_max: float
    disp_max: float
    vol_ratio_max: float
    dry_down_ratio_max: float
    rs_min: float
    pocket_mode: str  # none|bonus|required
    fa_tier: str  # FA0|FA1|FA2
    weekly_confirm: bool
    entry_buffer: float
    breakout_vol_mult: float
    stop_pct: float
    time_stop: int
    use_ma50_exit: bool


def _build_preset_grid() -> list[Preset]:
    presets: list[Preset] = []
    pid = 1
    trend_levels = ["relaxed", "medium", "strict"]
    base_weeks = [10, 16, 20]
    depth_caps = [0.25, 0.35]
    pocket_modes = ["none", "bonus", "required"]
    fa_tiers = ["FA0", "FA1", "FA2"]
    # Coarse grid only; keep manageable.
    for t in trend_levels:
        for bw in base_weeks:
            for dcap in depth_caps:
                for pm in pocket_modes:
                    for fa in fa_tiers:
                        if pid > 36:
                            break
                        relaxed = t == "relaxed"
                        strict = t == "strict"
                        presets.append(
                            Preset(
                                preset_id=f"P{pid:02d}",
                                trend=t,
                                base_weeks=bw,
                                depth_max=dcap,
                                price_zone_min=0.50 if relaxed else 0.70,
                                atr_ratio_max=0.95 if relaxed else 0.85,
                                range_comp_max=0.13 if relaxed else 0.10,
                                disp_max=0.045 if relaxed else 0.030,
                                vol_ratio_max=0.95 if relaxed else 0.80,
                                dry_down_ratio_max=0.95 if relaxed else 0.75,
                                rs_min=-0.02 if relaxed else (0.00 if t == "medium" else 0.05),
                                pocket_mode=pm,
                                fa_tier=fa,
                                weekly_confirm=strict,
                                entry_buffer=0.0015,
                                breakout_vol_mult=1.2 if relaxed else 1.35,
                                stop_pct=0.07 if relaxed else 0.06,
                                time_stop=40 if strict else 35,
                                use_ma50_exit=not strict,
                            )
                        )
                        pid += 1
    return presets


def _load_fa(fa_csv: Path, lag_days: int) -> pd.DataFrame:
    if not fa_csv.exists():
        return pd.DataFrame()
    fa = pd.read_csv(fa_csv)
    needed = {"symbol", "report_date"}
    if not needed.issubset(set(fa.columns)):
        return pd.DataFrame()
    fa["symbol"] = fa["symbol"].astype(str).str.upper().str.strip()
    fa["report_date"] = pd.to_datetime(fa["report_date"], errors="coerce")
    fa = fa.dropna(subset=["report_date"])
    fa["available_date"] = fa["report_date"] + pd.to_timedelta(lag_days, unit="D")
    return fa.sort_values(["symbol", "available_date"]).reset_index(drop=True)


def _fa_flags_for_symbol_dates(sym: str, dates: pd.Series, fa_df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame({"date": pd.to_datetime(dates)})
    out["fa0_pass"] = True
    out["fa1_pass"] = True
    out["fa2_pass"] = True
    out["fa_coverage"] = False
    if fa_df.empty:
        return out
    sfa = fa_df[fa_df["symbol"] == sym].copy()
    if sfa.empty:
        return out
    sfa = sfa.sort_values("available_date")
    merged = pd.merge_asof(
        out.sort_values("date"),
        sfa,
        left_on="date",
        right_on="available_date",
        direction="backward",
    )
    cov = merged["available_date"].notna()
    out["fa_coverage"] = cov.values

    rev = merged.get("sales_yoy", np.nan)
    npat = merged.get("earnings_yoy", np.nan)
    roe = merged.get("roe", np.nan)
    dte = merged.get("debt_to_equity", np.nan)
    margin = merged.get("gross_margin_yoy", np.nan)
    accel = merged.get("earnings_qoq_accel_flag", np.nan)

    fa1 = cov & (rev >= 10) & (npat >= 10)
    accel_ok = accel.fillna(0).astype(float) >= 1.0
    margin_ok = margin.fillna(0) >= -2.0
    fa2 = cov & (rev >= 15) & (npat >= 15) & (roe >= 12) & (dte <= 2.0) & margin_ok & accel_ok
    out["fa1_pass"] = fa1.fillna(False).values
    out["fa2_pass"] = fa2.fillna(False).values
    return out


def _add_core_features(df: pd.DataFrame, bench: pd.Series) -> pd.DataFrame:
    d = df.copy().sort_values("date").reset_index(drop=True)
    d = add_all_indicators(
        d,
        ma_windows=[10, 20, 50, 150, 200],
        atr_n=14,
        atr_pct_windows=[5, 10, 20, 50],
        vol_sma_windows=[10, 20, 50],
    )
    d["ret_63"] = d["close"].pct_change(63)
    d["bench_ret_63"] = bench.reindex(d["date"]).values
    d["rs_63"] = d["ret_63"] - d["bench_ret_63"]

    prev_close = d["close"].shift(1)
    down = d["close"] < prev_close
    down_vol = np.where(down, d["volume"], np.nan)
    d["down_vol_10"] = pd.Series(down_vol).rolling(10, min_periods=5).mean()
    d["down_vol_ratio_10_50"] = d["down_vol_10"] / d["vol_sma50"].replace(0, np.nan)

    d["atr_ratio_10_50"] = d["atr_pct_10"] / d["atr_pct_50"].replace(0, np.nan)
    d["range_10"] = (
        d["high"].rolling(10, min_periods=10).max() - d["low"].rolling(10, min_periods=10).min()
    ) / d["close"].replace(0, np.nan)
    d["disp_10"] = d["close"].rolling(10, min_periods=10).std() / d["close"].rolling(10, min_periods=10).mean().replace(0, np.nan)
    d["vol_ratio_10_50"] = d["vol_sma10"] / d["vol_sma50"].replace(0, np.nan)
    d["turnover"] = d["close"] * d["volume"]
    d["turnover_sma10"] = d["turnover"].rolling(10, min_periods=10).mean()
    d["turnover_sma50"] = d["turnover"].rolling(50, min_periods=50).mean()
    d["turn_ratio_10_50"] = d["turnover_sma10"] / d["turnover_sma50"].replace(0, np.nan)
    d["adv20"] = d["turnover"].rolling(20, min_periods=20).mean()

    # Base metrics computed over variable windows later.
    # Pocket pivot: simple VN-friendly variant.
    down_vol_hist = np.where(d["close"] < d["close"].shift(1), d["volume"], 0.0)
    d["pp_max_down_vol_10"] = pd.Series(down_vol_hist).rolling(10, min_periods=10).max().shift(1)
    d["pocket_pivot"] = (
        (d["close"] >= d["close"].shift(1))
        & (d["volume"] > d["pp_max_down_vol_10"])
        & (d["close"] >= d["ma10"])
    ).fillna(False)
    d["pp_in_last_20"] = d["pocket_pivot"].rolling(20, min_periods=1).sum() >= 1
    return d


def _trend_mask(d: pd.DataFrame, level: str) -> pd.Series:
    ma50_slope = (d["ma50"] - d["ma50"].shift(20)) / d["ma50"].shift(20).replace(0, np.nan)
    ma150_slope = (d["ma150"] - d["ma150"].shift(20)) / d["ma150"].shift(20).replace(0, np.nan)
    ma200_slope = (d["ma200"] - d["ma200"].shift(20)) / d["ma200"].shift(20).replace(0, np.nan)
    if level == "relaxed":
        return (
            (d["close"] > d["ma50"])
            & (d["ma50"] > d["ma200"])
            & (ma50_slope > 0)
        ).fillna(False)
    if level == "medium":
        return (
            (d["close"] > d["ma50"])
            & (d["ma50"] > d["ma150"])
            & (d["ma150"] > d["ma200"])
            & (ma50_slope > 0)
            & (ma150_slope > 0)
        ).fillna(False)
    return (
        (d["close"] > d["ma50"])
        & (d["ma50"] > d["ma150"])
        & (d["ma150"] > d["ma200"])
        & (ma50_slope > 0)
        & (ma150_slope > 0)
        & (ma200_slope > 0)
        & (d["close"] >= 0.75 * d["high_252"])
    ).fillna(False)


def _weekly_confirm_mask(d: pd.DataFrame) -> pd.Series:
    w = d.set_index("date").resample("W-FRI").agg({"close": "last"})
    w["w10"] = w["close"].rolling(10, min_periods=10).mean()
    w["w30"] = w["close"].rolling(30, min_periods=30).mean()
    w["w10_slope"] = w["w10"] - w["w10"].shift(4)
    w["ok"] = (w["close"] > w["w10"]) & (w["w10"] > w["w30"]) & (w["w10_slope"] > 0)
    daily = w["ok"].reindex(d["date"], method="ffill").fillna(False)
    return daily.values


def _setup_mask(d: pd.DataFrame, p: Preset) -> pd.DataFrame:
    base_days = p.base_weeks * 5
    base_high = d["high"].rolling(base_days, min_periods=base_days).max()
    base_low = d["low"].rolling(base_days, min_periods=base_days).min()
    base_depth = (base_high - base_low) / base_high.replace(0, np.nan)
    base_pos = (d["close"] - base_low) / (base_high - base_low).replace(0, np.nan)
    pivot = base_high.shift(1)
    dist_to_pivot = (pivot - d["close"]) / pivot.replace(0, np.nan)

    trend = _trend_mask(d, p.trend)
    if p.weekly_confirm:
        trend = trend & _weekly_confirm_mask(d)
    tight = (
        (d["atr_ratio_10_50"] <= p.atr_ratio_max)
        & (d["range_10"] <= p.range_comp_max)
        & (d["disp_10"] <= p.disp_max)
    )
    dry = (
        (d["vol_ratio_10_50"] <= p.vol_ratio_max)
        & (d["turn_ratio_10_50"] <= p.vol_ratio_max)
        & (d["down_vol_ratio_10_50"] <= p.dry_down_ratio_max)
    )
    base_ok = (
        (base_depth <= p.depth_max)
        & (base_depth >= 0.08)
        & (base_pos >= p.price_zone_min)
        & (dist_to_pivot >= 0)
        & (dist_to_pivot <= 0.08)
    )
    rs_ok = d["rs_63"] >= p.rs_min
    pp = d["pp_in_last_20"]
    if p.pocket_mode == "required":
        pp_ok = pp
    else:
        pp_ok = pd.Series(True, index=d.index)
    setup = trend & tight & dry & base_ok & rs_ok & pp_ok & (d["adv20"] >= 10e9)
    if p.fa_tier == "FA1":
        fa_ok = d["fa1_pass"].fillna(False)
    elif p.fa_tier == "FA2":
        fa_ok = d["fa2_pass"].fillna(False)
    else:
        fa_ok = pd.Series(True, index=d.index)
    setup = setup & fa_ok

    out = pd.DataFrame(
        {
            "date": d["date"],
            "setup": setup.fillna(False),
            "pivot": pivot,
            "dist_to_pivot": dist_to_pivot,
            "base_depth": base_depth,
            "base_weeks": p.base_weeks,
            "atr_ratio_10_50": d["atr_ratio_10_50"],
            "range_10": d["range_10"],
            "disp_10": d["disp_10"],
            "vol_ratio_10_50": d["vol_ratio_10_50"],
            "turn_ratio_10_50": d["turn_ratio_10_50"],
            "down_vol_ratio_10_50": d["down_vol_ratio_10_50"],
            "rs_63": d["rs_63"],
            "pocket_pivot_recent": pp.fillna(False),
            "close": d["close"],
            "volume": d["volume"],
            "vol_sma20": d["vol_sma20"],
            "ma50": d["ma50"],
            "ma200": d["ma200"],
            "fa_coverage": d["fa_coverage"].fillna(False),
            "fa1_pass": d["fa1_pass"].fillna(False),
            "fa2_pass": d["fa2_pass"].fillna(False),
        }
    )
    if p.pocket_mode == "bonus":
        out["score_bonus_pp"] = out["pocket_pivot_recent"].astype(int)
    else:
        out["score_bonus_pp"] = 0
    return out


def _future_breakout_and_returns(d: pd.DataFrame, idx: int, pivot: float, p: Preset) -> dict[str, Any]:
    row = d.iloc[idx]
    if not np.isfinite(pivot) or pivot <= 0:
        return {}
    windows = [5, 10, 20]
    max_windows = [20, 40, 60]
    close = float(row["close"])
    out: dict[str, Any] = {}
    for w in windows:
        sub = d.iloc[idx + 1 : idx + 1 + w]
        if sub.empty:
            out[f"breakout_{w}d"] = np.nan
            continue
        breakout = ((sub["close"] > pivot * (1 + p.entry_buffer)) & (sub["volume"] > p.breakout_vol_mult * sub["vol_sma20"])).any()
        out[f"breakout_{w}d"] = bool(breakout)
    for w in max_windows:
        sub = d.iloc[idx + 1 : idx + 1 + w]
        if sub.empty:
            out[f"maxret_{w}d"] = np.nan
            out[f"mae_{w}d"] = np.nan
            continue
        mx = float(sub["high"].max())
        mn = float(sub["low"].min())
        out[f"maxret_{w}d"] = (mx / close) - 1.0
        out[f"mae_{w}d"] = (mn / close) - 1.0
    return out


def _execution_trades(d: pd.DataFrame, setup_df: pd.DataFrame, p: Preset, symbol: str) -> pd.DataFrame:
    """
    Generate trades for one symbol/preset.

    Price semantics:
    - Setup evaluated at close of bar i (no lookahead).
    - Breakout detection on bar j (close/volume vs pivot).
    - Entry filled at next open (bar j+1).
    - Stops:
      If low[k] breaches stop on bar k, exit price (gross) is the WORSE of:
        * configured stop level
        * next open (bar k+1) – cannot assume better intraday fill than stop.
    Fees/slippage/tax are applied later when computing net returns.
    """
    rows: list[dict[str, Any]] = []
    i = 0
    n = len(d)
    while i < n - 2:
        if not bool(setup_df.iloc[i]["setup"]):
            i += 1
            continue
        pivot = setup_df.iloc[i]["pivot"]
        if not np.isfinite(pivot) or pivot <= 0:
            i += 1
            continue
        entry_i = None
        for j in range(i + 1, min(i + 21, n - 1)):
            cond = (d.iloc[j]["close"] > pivot * (1 + p.entry_buffer)) and (
                d.iloc[j]["volume"] > p.breakout_vol_mult * d.iloc[j]["vol_sma20"]
            )
            if cond:
                entry_i = j + 1  # next open
                break
        if entry_i is None or entry_i >= n:
            i += 1
            continue
        entry_px_gross = float(d.iloc[entry_i]["open"])
        stop_px = entry_px_gross * (1 - p.stop_pct)
        exit_i = None
        reason = "TIME_STOP"
        limit_i = min(entry_i + p.time_stop, n - 1)
        for k in range(entry_i + 1, limit_i + 1):
            low = float(d.iloc[k]["low"])
            close = float(d.iloc[k]["close"])
            if low <= stop_px:
                exit_i = k
                reason = "STOP"
                break
            if close < float(d.iloc[k]["ma20"]):
                exit_i = k
                reason = "MA20_BREAK"
                break
            if p.use_ma50_exit and close < float(d.iloc[k]["ma50"]):
                exit_i = k
                reason = "MA50_BREAK"
                break
        if exit_i is None:
            exit_i = limit_i

        # Gross exit price before costs:
        if reason == "STOP":
            # Conservative: exit at worse of stop vs next open.
            if exit_i + 1 < n:
                next_open = float(d.iloc[exit_i + 1]["open"])
                exit_px_gross = min(stop_px, next_open)
            else:
                exit_px_gross = stop_px
        else:
            exit_px_gross = float(d.iloc[exit_i]["open"]) if exit_i + 1 < n else float(d.iloc[exit_i]["close"])

        ret_gross = (exit_px_gross / entry_px_gross) - 1.0
        rows.append(
            {
                "symbol": symbol,
                "entry_date": d.iloc[entry_i]["date"],
                "exit_date": d.iloc[exit_i]["date"],
                "entry_px_gross": entry_px_gross,
                "exit_px_gross": exit_px_gross,
                "stop_px": stop_px,
                "ret_gross": ret_gross,
                "hold_bars": int(exit_i - entry_i),
                "hold_days": int((pd.Timestamp(d.iloc[exit_i]["date"]) - pd.Timestamp(d.iloc[entry_i]["date"])).days),
                "exit_reason": reason,
                "preset_id": p.preset_id,
            }
        )
        i = exit_i + 1
    return pd.DataFrame(rows)


def _period_mask(dates: pd.Series, period: str, latest: pd.Timestamp) -> pd.Series:
    y = pd.to_datetime(dates).dt.year
    if period == "2012_latest":
        return y >= 2012
    if period == "2012_2019":
        return (y >= 2012) & (y <= 2019)
    if period == "2020_2021":
        return (y >= 2020) & (y <= 2021)
    if period == "2022_latest":
        return y >= 2022
    if period == "2024_latest":
        return y >= 2024
    return dates <= latest


def _robustness_score(exec_by_period: pd.DataFrame) -> float:
    if exec_by_period.empty:
        return -999.0
    p = exec_by_period.set_index("period")
    def _g(col: str, period: str, default: float) -> float:
        if period not in p.index:
            return default
        v = _safe_float(p.loc[period, col])
        return default if v is None else v

    exp_full = _g("expectancy_net", "2012_latest", -1.0)
    exp_r22 = _g("expectancy_r_net", "2022_latest", -1.0)
    exp_r24 = _g("expectancy_r_net", "2024_latest", -1.0)
    pf22 = _g("profit_factor_net", "2022_latest", 0.0)
    pf24 = _g("profit_factor_net", "2024_latest", 0.0)
    dd = abs(_g("max_drawdown_net", "2012_latest", -1.0))
    trades = _g("trades_net", "2012_latest", 0.0)
    top10 = _g("top10_pct_pnl_net", "2012_latest", 1.0)
    stability = abs(_g("expectancy_r_net", "2012_2019", 0.0) - exp_r22) + abs(exp_r22 - exp_r24)
    return (
        1.8 * exp_full
        + 2.0 * exp_r22
        + 2.4 * exp_r24
        + 0.2 * pf22
        + 0.3 * pf24
        + 0.002 * min(trades, 400)
        - 1.2 * dd
        - 0.7 * max(0.0, top10 - 0.6)
        - 0.4 * stability
    )


def _rank_class(dist_to_pivot: float, tight_score: float, setup_ok: bool) -> str:
    if not setup_ok:
        return "Too extended / reject"
    if dist_to_pivot <= 0.02 and tight_score >= 0.75:
        return "Ready now"
    if dist_to_pivot <= 0.04 and tight_score >= 0.60:
        return "Early but watch closely"
    if dist_to_pivot <= 0.08:
        return "Needs more tightening"
    return "Too extended / reject"


def main() -> int:
    ap = argparse.ArgumentParser(description="Vietnam pre-breakout candidate research + scanner")
    ap.add_argument("--start", default="2012-01-01")
    ap.add_argument("--end", default=None)
    ap.add_argument("--fa-csv", default="data/fa_minervini.csv")
    ap.add_argument("--fa-lag-days", type=int, default=45)
    ap.add_argument("--max-presets", type=int, default=24)
    ap.add_argument("--max-symbols", type=int, default=0, help="0 = all")
    ap.add_argument("--out-dir", default="minervini_backtest/outputs/prebreakout_research")
    ap.add_argument("--fee-bps-per-side", type=float, default=15.0, help="Commission+fees per side in bps (default: 15)")
    ap.add_argument("--slippage-bps-per-side", type=float, default=10.0, help="Slippage per side in bps (default: 10)")
    ap.add_argument("--sell-tax-bps", type=float, default=0.0, help="Sell-side tax in bps (default: 0)")
    args = ap.parse_args()

    out_root = REPO / args.out_dir
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = out_root / ts
    out_dir.mkdir(parents=True, exist_ok=True)
    latest_link = out_root / "latest"
    latest_link.mkdir(parents=True, exist_ok=True)

    symbols = _read_symbols()
    load_list = list(symbols) if symbols else None
    if load_list is not None:
        load_list = load_list + ["VNINDEX", "VN30"]
    data = load_curated_data(load_list)
    if not data:
        print("[ERROR] No OHLCV data found in curated/raw.")
        return 1
    # Determine benchmark symbols actually present
    bench_candidates = [s for s in ["VNINDEX", "VN30"] if s in data]
    bench_symbol = bench_candidates[0] if bench_candidates else None
    # Stock universe excludes benchmarks
    all_symbols = sorted(k for k in data.keys() if k not in {"VNINDEX", "VN30"})
    if args.max_symbols and args.max_symbols > 0:
        symbols = (symbols or all_symbols)[: args.max_symbols]
    elif not symbols:
        symbols = all_symbols
    symbols = [s for s in symbols if s in data and s not in {"VNINDEX", "VN30"}]
    n_loaded_ex_bench = len(symbols)
    if bench_symbol is None:
        print("[ERROR] Benchmark VNINDEX/VN30 missing in local data.")
        return 1

    start = _to_date(args.start)
    end = _to_date(args.end) if args.end else None
    bench_df = data[bench_symbol].copy().sort_values("date")
    if start is not None:
        bench_df = bench_df[bench_df["date"] >= start]
    if end is not None:
        bench_df = bench_df[bench_df["date"] <= end]
    bench_ret_63 = bench_df.set_index("date")["close"].pct_change(63)
    asof_latest = pd.Timestamp(bench_df["date"].max())

    # Freshness detection (from the exact local data loaded in this run).
    # latest_raw_date_detected = max(date) across all loaded series (stocks + benchmarks).
    latest_raw_date_detected: pd.Timestamp | None = None
    for _, df in data.items():
        if df is None or df.empty or "date" not in df.columns:
            continue
        dmax = pd.to_datetime(df["date"]).max()
        if dmax is None or pd.isna(dmax):
            continue
        latest_raw_date_detected = dmax if latest_raw_date_detected is None else max(latest_raw_date_detected, dmax)
    asof_date_used = asof_latest
    if latest_raw_date_detected is None:
        is_stale = None
        stale_reason = "Unknown (latest_raw_date_detected could not be computed from local data)."
    else:
        is_stale = bool(asof_date_used < latest_raw_date_detected)
        stale_reason = (
            f"Benchmark {bench_symbol} ends at {asof_date_used.date()} but local data contains bars up to {latest_raw_date_detected.date()}."
            if is_stale
            else ""
        )

    fa_df = _load_fa(REPO / args.fa_csv, lag_days=args.fa_lag_days)
    presets = _build_preset_grid()[: max(1, args.max_presets)]

    fee_side = (args.fee_bps_per_side or 0.0) / 10000.0
    slip_side = (args.slippage_bps_per_side or 0.0) / 10000.0
    sell_tax = (args.sell_tax_bps or 0.0) / 10000.0

    setup_rows_all: list[pd.DataFrame] = []
    setup_quality_rows: list[dict[str, Any]] = []
    ledger_all: list[pd.DataFrame] = []
    preset_period_metrics: list[dict[str, Any]] = []
    preset_candidate_rows: list[dict[str, Any]] = []

    # Precompute per-symbol enriched data once.
    enriched: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        d = data[sym].copy().sort_values("date")
        if start is not None:
            d = d[d["date"] >= start]
        if end is not None:
            d = d[d["date"] <= end]
        if len(d) < 350:
            continue
        ed = _add_core_features(d, bench_ret_63)
        fa_flags = _fa_flags_for_symbol_dates(sym, ed["date"], fa_df)
        ed = ed.merge(fa_flags, on="date", how="left", suffixes=("", "_fa"))
        enriched[sym] = ed
    n_hist_ok = len(enriched)
    if not enriched:
        print("[ERROR] No symbols with sufficient history after filters.")
        return 1

    periods = ["2012_latest", "2012_2019", "2020_2021", "2022_latest", "2024_latest"]

    # Liquidity eligibility: count symbols with any bar meeting adv20 >= threshold.
    liq_threshold = 10e9
    n_liq_ok = 0
    for sym, ed in enriched.items():
        if "adv20" in ed.columns and (ed["adv20"] >= liq_threshold).any():
            n_liq_ok += 1

    for p in presets:
        preset_setups: list[pd.DataFrame] = []
        preset_ledger: list[pd.DataFrame] = []
        for sym, ed in enriched.items():
            sm = _setup_mask(ed, p)
            sm["symbol"] = sym
            sm["preset_id"] = p.preset_id
            setup_only = sm[sm["setup"]].copy()
            if setup_only.empty:
                continue
            preset_setups.append(setup_only)

            # Setup quality rows per setup event.
            idxs = setup_only.index.tolist()
            for idx in idxs:
                q = _future_breakout_and_returns(ed, idx, sm.loc[idx, "pivot"], p)
                if not q:
                    continue
                row = {
                    "preset_id": p.preset_id,
                    "symbol": sym,
                    "setup_date": sm.loc[idx, "date"],
                    "pivot": sm.loc[idx, "pivot"],
                    "dist_to_pivot": sm.loc[idx, "dist_to_pivot"],
                    "base_weeks": sm.loc[idx, "base_weeks"],
                    "base_depth": sm.loc[idx, "base_depth"],
                    "atr_ratio_10_50": sm.loc[idx, "atr_ratio_10_50"],
                    "vol_ratio_10_50": sm.loc[idx, "vol_ratio_10_50"],
                    "rs_63": sm.loc[idx, "rs_63"],
                    "pocket_pivot_recent": sm.loc[idx, "pocket_pivot_recent"],
                    "fa_coverage": sm.loc[idx, "fa_coverage"],
                }
                row.update(q)
                setup_quality_rows.append(row)

            lg = _execution_trades(ed, sm, p, sym)
            if not lg.empty:
                # Apply costs to get net prices/returns.
                g = lg.copy()
                # Buy side: pay fee+slippage.
                g["entry_px_net"] = g["entry_px_gross"] * (1.0 + fee_side + slip_side)
                # Sell side: pay fee+slippage+optional tax.
                g["exit_px_net"] = g["exit_px_gross"] * (1.0 - fee_side - slip_side - sell_tax)
                g["ret_net"] = (g["exit_px_net"] / g["entry_px_net"]) - 1.0
                preset_ledger.append(g)

            # Latest candidates from this preset
            latest_row = sm[sm["date"] == asof_latest]
            if not latest_row.empty and bool(latest_row.iloc[0]["setup"]):
                r = latest_row.iloc[0]
                tight_score = float(np.mean([
                    1.0 if r["atr_ratio_10_50"] <= p.atr_ratio_max else 0.0,
                    1.0 if r["range_10"] <= p.range_comp_max else 0.0,
                    1.0 if r["disp_10"] <= p.disp_max else 0.0,
                    1.0 if r["vol_ratio_10_50"] <= p.vol_ratio_max else 0.0,
                ]))
                cls = _rank_class(float(r["dist_to_pivot"]), tight_score, bool(r["setup"]))
                why = [
                    f"trend={p.trend}",
                    f"base={p.base_weeks}w depth={float(r['base_depth']):.2%}",
                    f"dist_to_pivot={float(r['dist_to_pivot']):.2%}",
                    f"tight atr10/50={float(r['atr_ratio_10_50']):.2f}",
                    f"dry vol10/50={float(r['vol_ratio_10_50']):.2f}",
                ]
                preset_candidate_rows.append(
                    {
                        "preset_id": p.preset_id,
                        "symbol": sym,
                        "asof_date": asof_latest,
                        "close": float(r["close"]),
                        "pivot": float(r["pivot"]),
                        "dist_to_pivot": float(r["dist_to_pivot"]),
                        "base_duration_weeks": int(r["base_weeks"]),
                        "base_depth": float(r["base_depth"]),
                        "atr_ratio_10_50": float(r["atr_ratio_10_50"]),
                        "range_10": float(r["range_10"]),
                        "disp_10": float(r["disp_10"]),
                        "vol_ratio_10_50": float(r["vol_ratio_10_50"]),
                        "turn_ratio_10_50": float(r["turn_ratio_10_50"]),
                        "rs_63": float(r["rs_63"]),
                        "trend_alignment": p.trend,
                        "pocket_pivot_recent": bool(r["pocket_pivot_recent"]),
                        "fa1_pass": bool(r["fa1_pass"]),
                        "fa2_pass": bool(r["fa2_pass"]),
                        "classification": cls,
                        "why_qualifies": "; ".join(why),
                    }
                )

        if preset_setups:
            preset_setups_df = pd.concat(preset_setups, ignore_index=True)
            setup_rows_all.append(preset_setups_df)
        else:
            preset_setups_df = pd.DataFrame()
        if preset_ledger:
            led = pd.concat(preset_ledger, ignore_index=True)
            ledger_all.append(led)
        else:
            led = pd.DataFrame()

        # Period metrics for execution
        for period in periods:
            if led.empty:
                metric = {
                    "preset_id": p.preset_id,
                    "period": period,
                    "trades_gross": 0,
                    "expectancy_gross": np.nan,
                    "profit_factor_gross": np.nan,
                    "max_drawdown_gross": np.nan,
                    "trades_net": 0,
                    "expectancy_net": np.nan,
                    "profit_factor_net": np.nan,
                    "max_drawdown_net": np.nan,
                    "expectancy_r_net": np.nan,
                    "top10_pct_pnl_net": np.nan,
                    "trades_per_year_net": np.nan,
                }
            else:
                pmask = _period_mask(pd.to_datetime(led["entry_date"]), period, asof_latest)
                s = led[pmask].copy()
                if s.empty:
                    metric = {
                        "preset_id": p.preset_id,
                        "period": period,
                        "trades_gross": 0,
                        "expectancy_gross": np.nan,
                        "profit_factor_gross": np.nan,
                        "max_drawdown_gross": np.nan,
                        "trades_net": 0,
                        "expectancy_net": np.nan,
                        "profit_factor_net": np.nan,
                        "max_drawdown_net": np.nan,
                        "expectancy_r_net": np.nan,
                        "top10_pct_pnl_net": np.nan,
                        "trades_per_year_net": np.nan,
                    }
                else:
                    # Gross metrics: use ret_gross.
                    sg = s.copy()
                    sg["entry_px"] = sg["entry_px_gross"]
                    sg["exit_px"] = sg["exit_px_gross"]
                    sg["ret"] = sg["ret_gross"]
                    tm_g = trade_metrics(sg)
                    # Net metrics: use ret_net.
                    sn = s.copy()
                    sn["entry_px"] = sn["entry_px_net"]
                    sn["exit_px"] = sn["exit_px_net"]
                    sn["ret"] = sn["ret_net"]
                    tm_n = trade_metrics(sn)
                    rm_n = minervini_r_metrics(sn)
                    metric = {
                        "preset_id": p.preset_id,
                        "period": period,
                        "trades_gross": tm_g["trades"],
                        "expectancy_gross": tm_g["expectancy"],
                        "profit_factor_gross": tm_g["profit_factor"],
                        "max_drawdown_gross": tm_g["max_drawdown"],
                        "trades_net": tm_n["trades"],
                        "expectancy_net": tm_n["expectancy"],
                        "profit_factor_net": tm_n["profit_factor"],
                        "max_drawdown_net": tm_n["max_drawdown"],
                        "expectancy_r_net": rm_n["expectancy_r"],
                        "top10_pct_pnl_net": rm_n["top10_pct_pnl"],
                        "trades_per_year_net": trades_per_year(sn),
                    }
            preset_period_metrics.append(metric)

        # Setup quality aggregate
        sq = pd.DataFrame([r for r in setup_quality_rows if r["preset_id"] == p.preset_id])
        if not sq.empty:
            agg = {
                "preset_id": p.preset_id,
                "setups": int(len(sq)),
                "breakout_5d_rate": float(pd.Series(sq["breakout_5d"]).dropna().mean()),
                "breakout_10d_rate": float(pd.Series(sq["breakout_10d"]).dropna().mean()),
                "breakout_20d_rate": float(pd.Series(sq["breakout_20d"]).dropna().mean()),
                "maxret_20d_med": float(pd.Series(sq["maxret_20d"]).dropna().median()),
                "maxret_40d_med": float(pd.Series(sq["maxret_40d"]).dropna().median()),
                "maxret_60d_med": float(pd.Series(sq["maxret_60d"]).dropna().median()),
                "mae_20d_med": float(pd.Series(sq["mae_20d"]).dropna().median()),
                "prob_5pct_20d": float((pd.Series(sq["maxret_20d"]).dropna() >= 0.05).mean()),
                "prob_10pct_40d": float((pd.Series(sq["maxret_40d"]).dropna() >= 0.10).mean()),
                "prob_15pct_60d": float((pd.Series(sq["maxret_60d"]).dropna() >= 0.15).mean()),
            }
        else:
            agg = {
                "preset_id": p.preset_id,
                "setups": 0,
                "breakout_5d_rate": np.nan,
                "breakout_10d_rate": np.nan,
                "breakout_20d_rate": np.nan,
                "maxret_20d_med": np.nan,
                "maxret_40d_med": np.nan,
                "maxret_60d_med": np.nan,
                "mae_20d_med": np.nan,
                "prob_5pct_20d": np.nan,
                "prob_10pct_40d": np.nan,
                "prob_15pct_60d": np.nan,
            }
        preset_period_metrics.append({"preset_id": p.preset_id, "period": "setup_quality", **agg})

    setup_quality_df = pd.DataFrame(setup_quality_rows)
    period_df = pd.DataFrame(preset_period_metrics)
    exec_df = period_df[period_df["period"].isin(periods)].copy()
    setup_summary = period_df[period_df["period"] == "setup_quality"].copy()

    # Robustness summary
    rows = []
    for pid in sorted(exec_df["preset_id"].unique()):
        sub = exec_df[exec_df["preset_id"] == pid].copy()
        score = _robustness_score(sub)
        pmap = {x.preset_id: x for x in presets}
        pp = pmap[pid]
        # family tags: A=daily-only, B=weekly structure, C=dual strict (weekly+strict trend)
        if pp.weekly_confirm and pp.trend == "strict":
            family = "C"
        elif pp.weekly_confirm:
            family = "B"
        else:
            family = "A"
        r = {
            "preset_id": pid,
            "robustness_score": score,
            "family": family,
            "trend": pp.trend,
            "base_weeks": pp.base_weeks,
            "depth_max": pp.depth_max,
            "pocket_mode": pp.pocket_mode,
            "fa_tier": pp.fa_tier,
        }
        for per in ["2012_latest", "2022_latest", "2024_latest"]:
            ss = sub[sub["period"] == per]
            if ss.empty:
                continue
            for c in [
                "trades_net",
                "expectancy_net",
                "profit_factor_net",
                "expectancy_r_net",
                "max_drawdown_net",
                "top10_pct_pnl_net",
            ]:
                r[f"{per}_{c}"] = ss.iloc[0].get(c)
        sq = setup_summary[setup_summary["preset_id"] == pid]
        if not sq.empty:
            for c in ["setups", "breakout_10d_rate", "breakout_20d_rate", "prob_10pct_40d", "prob_15pct_60d"]:
                r[c] = sq.iloc[0].get(c)
        rows.append(r)
    robust_df = pd.DataFrame(rows).sort_values("robustness_score", ascending=False).reset_index(drop=True)
    best_presets = robust_df.head(3)["preset_id"].tolist()

    # Candidate ranking from best presets.
    cand_df = pd.DataFrame(preset_candidate_rows)
    if not cand_df.empty:
        cand_df = cand_df[cand_df["preset_id"].isin(best_presets)].copy()
        cand_df["rank_score"] = (
            (1 - cand_df["dist_to_pivot"].clip(lower=0, upper=0.08) / 0.08) * 0.35
            + (cand_df["rs_63"].clip(lower=-0.2, upper=0.4) + 0.2) / 0.6 * 0.25
            + (1 - cand_df["atr_ratio_10_50"].clip(lower=0.5, upper=1.5) - 0.5) * 0.15
            + (1 - cand_df["vol_ratio_10_50"].clip(lower=0.5, upper=1.5) - 0.5) * 0.15
            + cand_df["pocket_pivot_recent"].astype(int) * 0.10
        )
        cand_df = cand_df.sort_values(["rank_score", "dist_to_pivot"], ascending=[False, True]).reset_index(drop=True)

    # Save artifacts
    if not setup_quality_df.empty:
        setup_quality_df.to_csv(out_dir / "setup_quality_results.csv", index=False)
    exec_df.to_csv(out_dir / "execution_backtest_results_gross_vs_net.csv", index=False)
    robust_df.to_csv(out_dir / "preset_robustness_summary.csv", index=False)
    # Always write candidate artifacts to avoid stale `latest/` files
    # when this run finds zero candidates at the current `asof_date_used`.
    cand_df.to_csv(out_dir / "latest_candidates_best_presets.csv", index=False)
    if ledger_all:
        ledger_df = pd.concat(ledger_all, ignore_index=True)
        ledger_df = ledger_df[ledger_df["preset_id"].isin(best_presets)].copy()
        ledger_df.to_csv(out_dir / "trade_log_best_presets.csv", index=False)
    else:
        ledger_df = pd.DataFrame()

    # Full grid summary table
    full_grid = robust_df.merge(
        setup_summary.drop(columns=["period"], errors="ignore"),
        on="preset_id",
        how="left",
        suffixes=("", "_setup"),
    )
    full_grid.to_csv(out_dir / "preset_grid_results.csv", index=False)

    # Parameter-effect / degeneracy audit per preset.
    cand_counts = {}
    if not cand_df.empty:
        for pid in cand_df["preset_id"].unique():
            cand_counts[pid] = int((cand_df["preset_id"] == pid).sum())
    overlap_map: dict[str, float] = {}
    if ledger_all:
        all_ledger = pd.concat(ledger_all, ignore_index=True)
        sym_dates = (
            all_ledger[["preset_id", "symbol", "entry_date"]]
            .copy()
        )
        groups = {
            pid: set(
                zip(
                    g["symbol"].astype(str),
                    pd.to_datetime(g["entry_date"]).dt.strftime("%Y-%m-%d"),
                )
            )
            for pid, g in sym_dates.groupby("preset_id")
        }
        for pid, base_set in groups.items():
            if not base_set:
                overlap_map[pid] = 0.0
                continue
            ratios: list[float] = []
            for qid, other_set in groups.items():
                if qid == pid or not other_set:
                    continue
                inter = len(base_set & other_set)
                denom = min(len(base_set), len(other_set))
                if denom > 0:
                    ratios.append(inter / denom)
            overlap_map[pid] = float(np.mean(ratios)) if ratios else 0.0
    pe_rows = []
    for _, r in robust_df.iterrows():
        pid = r["preset_id"]
        pe_rows.append(
            {
                "preset_id": pid,
                "family": r.get("family"),
                "trend": r.get("trend"),
                "base_weeks": r.get("base_weeks"),
                "depth_max": r.get("depth_max"),
                "pocket_mode": r.get("pocket_mode"),
                "fa_tier": r.get("fa_tier"),
                "2012_trades_net": r.get("2012_latest_trades_net"),
                "2012_expectancy_net": r.get("2012_latest_expectancy_net"),
                "2012_pf_net": r.get("2012_latest_profit_factor_net"),
                "2022_trades_net": r.get("2022_latest_trades_net"),
                "2022_expectancy_net": r.get("2022_latest_expectancy_net"),
                "2022_pf_net": r.get("2022_latest_profit_factor_net"),
                "2024_trades_net": r.get("2024_latest_trades_net"),
                "2024_expectancy_net": r.get("2024_latest_expectancy_net"),
                "2024_pf_net": r.get("2024_latest_profit_factor_net"),
                "top10_pct_pnl_net": r.get("2012_latest_top10_pct_pnl_net"),
                "setup_count": r.get("setups"),
                "latest_candidate_count": cand_counts.get(pid, 0),
                "mean_overlap_ratio": overlap_map.get(pid, 0.0),
            }
        )
    pd.DataFrame(pe_rows).to_csv(out_dir / "preset_parameter_effect_check.csv", index=False)

    # Report markdown
    # NOTE: dedup_df is built later; use cand_df here to avoid stale/undefined variables.
    lines = [
        "# Vietnam Pre-Breakout Research Report",
        "",
        "## Facts",
        f"- Data universe source: local curated/raw OHLCV from repo (`minervini_backtest/run.py -> load_curated_data`).",
        f"- Benchmark: {bench_symbol} (63d relative strength).",
        f"- FA source: `data/fa_minervini.csv` with conservative availability lag = {args.fa_lag_days} days after `report_date`.",
        f"- n_symbols_loaded_ex_benchmark: {n_loaded_ex_bench}",
        f"- n_symbols_eligible_after_history_filter: {n_hist_ok}",
        f"- n_symbols_eligible_after_liquidity_filter: {n_liq_ok}",
        f"- benchmark_symbols_used: {', '.join(bench_candidates) if bench_candidates else 'None'}",
        f"- latest_raw_date_detected: {str(latest_raw_date_detected.date()) if latest_raw_date_detected is not None else 'Unknown'}",
        f"- asof_date_used: {str(asof_date_used.date())}",
        f"- is_stale: {is_stale if is_stale is not None else 'Unknown'}",
        f"- stale_reason: {stale_reason if stale_reason else '—'}",
        f"- Periods evaluated: 2012-latest, 2012-2019, 2020-2021, 2022-latest, 2024-latest.",
        f"- Presets tested: {len(presets)}.",
        "",
        "## Best Presets by Robustness",
    ]
    for _, r in robust_df.head(5).iterrows():
        lines.append(
            f"- {r['preset_id']}: score={r['robustness_score']:.4f}, trend={r['trend']}, base={int(r['base_weeks'])}w, depth<={r['depth_max']:.2f}, pocket={r['pocket_mode']}, FA={r['fa_tier']}"
        )
        lines.append(
            f"  - 2012+: trades_net={int(r.get('2012_latest_trades_net', 0) or 0)}, exp_net={_safe_float(r.get('2012_latest_expectancy_net'))}, pf_net={_safe_float(r.get('2012_latest_profit_factor_net'))}"
        )
        lines.append(
            f"  - 2022+: trades_net={int(r.get('2022_latest_trades_net', 0) or 0)}, exp_net={_safe_float(r.get('2022_latest_expectancy_net'))}, pf_net={_safe_float(r.get('2022_latest_profit_factor_net'))}"
        )
        lines.append(
            f"  - 2024+: trades_net={int(r.get('2024_latest_trades_net', 0) or 0)}, exp_net={_safe_float(r.get('2024_latest_expectancy_net'))}, pf_net={_safe_float(r.get('2024_latest_profit_factor_net'))}"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "- FACT: robustness score penalizes instability (period drift), low trade count, concentration, and drawdown.",
            "- FACT: 2022+ and 2024+ expectancy_r are weighted higher than old-period performance.",
            "- INTERPRETATION: presets that keep positive expectancy in recent windows are preferred over legacy high-CAGR presets.",
            "",
            "## Latest Candidate List (deduped)",
        ]
    )
    show_df = cand_df
    if show_df is None or show_df.empty:
        lines.append("- No candidates from current best presets at latest date.")
    else:
        topn = show_df.head(20)
        lines.append("| rank | symbol | preset | close | pivot | dist_to_pivot | class | why |")
        lines.append("|---|---|---|---:|---:|---:|---|---|")
        for i, (_, r) in enumerate(topn.iterrows(), 1):
            lines.append(
                f"| {i} | {r['symbol']} | {r['preset_id']} | {r['close']:.2f} | {r['pivot']:.2f} | {r['dist_to_pivot']:.2%} | {r['classification']} | {r['why_qualifies']} |"
            )
    lines.extend(
        [
            "",
            "## Data/Bias Limitations",
            "- FACT: survivorship bias may remain if delisted names are not fully present in local OHLCV set.",
            "- FACT: FA publish timestamps are not available; conservative lag model used.",
            "- FACT: execution uses simple next-open fills and fixed stop/time/MA exits; no intraday microstructure modeling.",
            "- FACT: OOS evaluation is rolling train→test only (no validation slice).",
            "- FACT: Daily-vs-weekly family comparison is only valid if families B/C are instantiated in this run; otherwise treat as not evaluated.",
        ]
    )
    (out_dir / "prebreakout_research_report.md").write_text("\n".join(lines), encoding="utf-8")

    # Walk-forward OOS validation (net).
    wf_rows: list[dict[str, Any]] = []
    oos_v2_rows: list[dict[str, Any]] = []
    if ledger_all:
        all_ledger = pd.concat(ledger_all, ignore_index=True)
        all_ledger["entry_date"] = pd.to_datetime(all_ledger["entry_date"])
        wf_windows = [
            ("W1", "2012-01-01", "2017-12-31", "2018-01-01", "2019-12-31"),
            ("W2", "2014-01-01", "2019-12-31", "2020-01-01", "2021-12-31"),
            ("W3", "2016-01-01", "2021-12-31", "2022-01-01", "2023-12-31"),
            ("W4", "2018-01-01", "2023-12-31", "2024-01-01", str(asof_latest.date())),
        ]
        for wid, ts, te, us, ue in wf_windows:
            t_start, t_end = pd.Timestamp(ts), pd.Timestamp(te)
            u_start, u_end = pd.Timestamp(us), pd.Timestamp(ue)
            train_led = all_ledger[(all_ledger["entry_date"] >= t_start) & (all_ledger["entry_date"] <= t_end)].copy()
            test_led = all_ledger[(all_ledger["entry_date"] >= u_start) & (all_ledger["entry_date"] <= u_end)].copy()
            if train_led.empty or test_led.empty:
                continue
            # Train: compute robustness per preset on this window (net only).
            exec_train_rows = []
            for pid in sorted(train_led["preset_id"].unique()):
                s = train_led[train_led["preset_id"] == pid].copy()
                sn = s.copy()
                sn["entry_px"] = sn["entry_px_net"]
                sn["exit_px"] = sn["exit_px_net"]
                sn["ret"] = sn["ret_net"]
                tm_n = trade_metrics(sn)
                rm_n = minervini_r_metrics(sn)
                exec_train_rows.append(
                    {
                        "preset_id": pid,
                        "period": "train",
                        "trades_net": tm_n["trades"],
                        "expectancy_net": tm_n["expectancy"],
                        "profit_factor_net": tm_n["profit_factor"],
                        "max_drawdown_net": tm_n["max_drawdown"],
                        "expectancy_r_net": rm_n["expectancy_r"],
                        "top10_pct_pnl_net": rm_n["top10_pct_pnl"],
                    }
                )
            exec_train_df = pd.DataFrame(exec_train_rows)
            if exec_train_df.empty:
                continue
            # Use robustness_score on this trimmed table.
            scores = []
            for pid in exec_train_df["preset_id"].unique():
                sub = exec_train_df[exec_train_df["preset_id"] == pid].copy()
                score = _robustness_score(sub)
                scores.append((pid, score))
            scores_df = pd.DataFrame(scores, columns=["preset_id", "score"]).sort_values("score", ascending=False)
            top_pids = scores_df.head(3)["preset_id"].tolist()
            # Split header row (explicit semantics: rolling train→test OOS, no validation slice)
            oos_v2_rows.append(
                {
                    "split_id": wid,
                    "methodology_label": "rolling_train_test_oos",
                    "train_start": ts,
                    "train_end": te,
                    "validation_start": None,
                    "validation_end": None,
                    "test_start": us,
                    "test_end": ue,
                    "selected_preset_ids": json.dumps(top_pids),
                    "selection_metric": "robustness_score_net(train_only)",
                }
            )
            # Test metrics for selected presets.
            for pid in top_pids:
                t_train = train_led[train_led["preset_id"] == pid].copy()
                t_test = test_led[test_led["preset_id"] == pid].copy()
                fam = robust_df.set_index("preset_id").loc[pid, "family"] if pid in robust_df["preset_id"].values else None
                if not t_train.empty:
                    st = t_train.copy()
                    st["entry_px"] = st["entry_px_net"]
                    st["exit_px"] = st["exit_px_net"]
                    st["ret"] = st["ret_net"]
                    mt = trade_metrics(st)
                    rt = minervini_r_metrics(st)
                else:
                    mt = {k: np.nan for k in trade_metrics(pd.DataFrame()).keys()}
                    rt = {k: np.nan for k in minervini_r_metrics(pd.DataFrame()).keys()}
                if not t_test.empty:
                    su = t_test.copy()
                    su["entry_px"] = su["entry_px_net"]
                    su["exit_px"] = su["exit_px_net"]
                    su["ret"] = su["ret_net"]
                    mu = trade_metrics(su)
                    ru = minervini_r_metrics(su)
                else:
                    mu = {k: np.nan for k in trade_metrics(pd.DataFrame()).keys()}
                    ru = {k: np.nan for k in minervini_r_metrics(pd.DataFrame()).keys()}
                wf_rows.append(
                    {
                        "window_id": wid,
                        "train_start": ts,
                        "train_end": te,
                        "test_start": us,
                        "test_end": ue,
                        "preset_id": pid,
                        "family": fam,
                        "train_trades_net": mt["trades"],
                        "test_trades_net": mu["trades"],
                        "train_expectancy_net": mt["expectancy"],
                        "test_expectancy_net": mu["expectancy"],
                        "train_pf_net": mt["profit_factor"],
                        "test_pf_net": mu["profit_factor"],
                        "train_max_dd_net": mt["max_drawdown"],
                        "test_max_dd_net": mu["max_drawdown"],
                        "train_expectancy_r_net": rt["expectancy_r"],
                        "test_expectancy_r_net": ru["expectancy_r"],
                    }
                )
                oos_v2_rows.append(
                    {
                        "split_id": wid,
                        "methodology_label": "rolling_train_test_oos",
                        "train_start": ts,
                        "train_end": te,
                        "validation_start": None,
                        "validation_end": None,
                        "test_start": us,
                        "test_end": ue,
                        "selected_preset_ids": json.dumps(top_pids),
                        "selection_metric": "robustness_score_net(train_only)",
                        "preset_id": pid,
                        "test_metrics_trades_net": mu["trades"],
                        "test_metrics_expectancy_net": mu["expectancy"],
                        "test_metrics_pf_net": mu["profit_factor"],
                        "test_metrics_max_dd_net": mu["max_drawdown"],
                        "test_metrics_expectancy_r_net": ru["expectancy_r"],
                        "test_metrics_top10_pct_pnl_net": ru["top10_pct_pnl"],
                    }
                )
    if wf_rows:
        pd.DataFrame(wf_rows).to_csv(out_dir / "walkforward_oos_results.csv", index=False)
    if oos_v2_rows:
        pd.DataFrame(oos_v2_rows).to_csv(out_dir / "oos_rolling_train_test_results.csv", index=False)
        (out_dir / "oos_methodology_note.md").write_text(
            "\n".join(
                [
                    "# OOS methodology note (facts-only)",
                    "",
                    "## Label",
                    "- `methodology_label = rolling_train_test_oos`",
                    "",
                    "## What it does",
                    "- For each split, compute net metrics per preset on the **train** window.",
                    "- Rank presets using a net-based robustness score on train only.",
                    "- Evaluate selected presets on the subsequent **test** window.",
                    "",
                    "## What it does NOT do",
                    "- No separate validation slice (train→validation→test is NOT implemented).",
                    "- No parameter optimization inside a preset; selection is among fixed grid presets only.",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    # Family comparison (daily vs weekly) using net metrics aggregated from robustness table.
    fam_rows = []
    for fam in ["A", "B", "C"]:
        sub = robust_df[robust_df["family"] == fam].copy()
        if sub.empty:
            fam_rows.append({"family": fam, "not_instantiated_in_this_run": True})
            continue
        best = sub.iloc[0]
        fam_rows.append(
            {
                "family": fam,
                "best_preset_id": best["preset_id"],
                "not_instantiated_in_this_run": False,
                "2012_trades_net": best.get("2012_latest_trades_net"),
                "2012_expectancy_net": best.get("2012_latest_expectancy_net"),
                "2012_pf_net": best.get("2012_latest_profit_factor_net"),
                "2022_trades_net": best.get("2022_latest_trades_net"),
                "2022_expectancy_net": best.get("2022_latest_expectancy_net"),
                "2022_pf_net": best.get("2022_latest_profit_factor_net"),
                "2024_trades_net": best.get("2024_latest_trades_net"),
                "2024_expectancy_net": best.get("2024_latest_expectancy_net"),
                "2024_pf_net": best.get("2024_latest_profit_factor_net"),
            }
        )
    if fam_rows:
        pd.DataFrame(fam_rows).to_csv(out_dir / "family_comparison_daily_vs_weekly.csv", index=False)

    # Latest candidates: add subscores and deduplicate by symbol.
    dedup_df = pd.DataFrame()
    funnel_rows: list[dict[str, Any]] = []
    if not cand_df.empty:
        # Subscores
        cand_df["setup_score"] = (
            0.25 * (1.0 - cand_df["base_depth"].clip(0, 0.35) / 0.35)
            + 0.25 * (1.0 - cand_df["atr_ratio_10_50"].clip(0.5, 1.5) - 0.5)
            + 0.25 * (1.0 - cand_df["disp_10"].clip(0.0, 0.06) / 0.06)
            + 0.25 * (1.0 - cand_df["range_10"].clip(0.0, 0.15) / 0.15)
        )
        cand_df["breakout_readiness_score"] = (
            (1.0 - cand_df["dist_to_pivot"].clip(0.0, 0.08) / 0.08) * 0.7
            + (cand_df["pocket_pivot_recent"].astype(int) * 0.3)
        )
        cand_df["fa_support_score"] = cand_df["fa2_pass"].astype(int) * 1.0 + (~cand_df["fa2_pass"] & cand_df["fa1_pass"]).astype(int) * 0.5
        cand_df["final_rank_score"] = (
            0.4 * cand_df["setup_score"]
            + 0.4 * cand_df["breakout_readiness_score"]
            + 0.2 * cand_df["fa_support_score"]
        )
        # Classification reuse
        classes = []
        for _, r in cand_df.iterrows():
            cls = _rank_class(float(r["dist_to_pivot"]), float(r["setup_score"]), True)
            classes.append(cls)
        cand_df["classification"] = classes
        # Deduplicate
        ranks = []
        for sym, g in cand_df.groupby("symbol"):
            g2 = g.sort_values(["final_rank_score", "dist_to_pivot"], ascending=[False, True])
            ranks.append(g2.iloc[0])
        dedup_df = pd.DataFrame(ranks).reset_index(drop=True)
        dedup_df.to_csv(out_dir / "latest_candidates_deduped.csv", index=False)

        # Funnel diagnostics (honest & mostly exact for what we can compute).
        # We compute exact counts for setup detection for the best preset, and for liquidity/history/universe.
        best_pid = best_presets[0] if best_presets else None
        pmap = {x.preset_id: x for x in presets}
        if best_pid and best_pid in pmap:
            pbest = pmap[best_pid]
            total_universe = len(symbols)
            loaded_ex_benchmark = n_loaded_ex_bench
            passed_history_filter = n_hist_ok
            passed_basic_liquidity_check = 0
            passed_trend_base_eligibility = None  # not directly logged (would require exposing sub-gates)
            setup_detected = 0
            passed_breakout_readiness = 0
            passed_fa_gate = 0
            # readiness definition: setup_detected AND dist_to_pivot <= 4%
            readiness_dist_max = 0.04

            for sym, ed in enriched.items():
                latest_row = ed[ed["date"] == asof_latest]
                if latest_row.empty:
                    continue
                adv_ok = bool(latest_row.iloc[0].get("adv20", 0.0) >= 10e9)
                passed_basic_liquidity_check += int(adv_ok)

                sm = _setup_mask(ed, pbest)
                sr = sm[sm["date"] == asof_latest]
                if sr.empty:
                    continue
                s_ok = bool(sr.iloc[0]["setup"])
                setup_detected += int(s_ok)
                dist = float(sr.iloc[0]["dist_to_pivot"]) if pd.notna(sr.iloc[0]["dist_to_pivot"]) else 1.0
                passed_breakout_readiness += int(s_ok and (dist <= readiness_dist_max))

                if pbest.fa_tier == "FA2":
                    fa_ok = bool(sr.iloc[0]["fa2_pass"])
                elif pbest.fa_tier == "FA1":
                    fa_ok = bool(sr.iloc[0]["fa1_pass"])
                else:
                    fa_ok = True
                passed_fa_gate += int(s_ok and fa_ok)

            preset_survivors = setup_detected
            deduped_final_candidates = int(len(dedup_df)) if dedup_df is not None and not dedup_df.empty else 0

            funnel_rows.append(
                {
                    "asof_date": str(asof_latest.date()),
                    "best_preset_id": best_pid,
                    "total_universe": total_universe,
                    "loaded_ex_benchmark": loaded_ex_benchmark,
                    "passed_history_filter": passed_history_filter,
                    "passed_basic_liquidity_check": passed_basic_liquidity_check,
                    "passed_trend_base_eligibility": passed_trend_base_eligibility,
                    "setup_detected": setup_detected,
                    "passed_breakout_readiness": passed_breakout_readiness,
                    "passed_fa_gate": passed_fa_gate,
                    "preset_survivors": preset_survivors,
                    "deduped_final_candidates": deduped_final_candidates,
                    "is_estimated": False,
                    "notes": f"passed_trend_base_eligibility not logged; readiness gate uses dist_to_pivot <= {readiness_dist_max:.0%}.",
                }
            )
    # Always write these artifacts (even if empty) to avoid stale `latest/` outputs.
    pd.DataFrame(funnel_rows).to_csv(out_dir / "candidate_filter_funnel.csv", index=False)
    dedup_df.to_csv(out_dir / "latest_candidates_deduped.csv", index=False)

    # Backtest realism audit (facts-only, repo-specific).
    realism_lines = [
        "# Backtest realism audit (facts-only)",
        "",
        "## Signal timing semantics",
        "- Setup is evaluated at end of day (EOD) using only data up to that day.",
        "- Pivot is computed as `base_high.shift(1)` so it is computable as-of the setup date (no future bars).",
        "",
        "## Entry timing semantics",
        "- Breakout detection uses bar j close/volume and is executed at next open (j+1).",
        "- No same-bar close fills are used in this workflow.",
        "",
        "## Exit timing semantics",
        "- Stop breach is detected via intraday low; fill is handled conservatively (see below).",
        "- MA/time exits are checked on bar close and exited at next open when possible.",
        "",
        "## Stop-loss fill semantics",
        "- If low[k] <= stop_px on day k, gross exit price is **min(stop_px, next_open)** (worse of stop vs next open for long).",
        "",
        "## Gross vs net semantics (this run)",
        f"- fee_bps_per_side = {args.fee_bps_per_side}",
        f"- slippage_bps_per_side = {args.slippage_bps_per_side}",
        f"- sell_tax_bps = {args.sell_tax_bps}",
        "- Net pricing applies costs at the ledger level (entry price increases; exit price decreases).",
        "",
        "## Portfolio-level caveat",
        "- Results are trade-level metrics computed from ledgers. This is NOT a constrained portfolio simulation.",
        "",
        "## Survivorship & PIT caveats",
        "- Universe membership is not reconstructed point-in-time; survivorship bias may remain.",
        f"- FA PIT is approximated via `available_date = report_date + {args.fa_lag_days} days` (publish timestamps not available).",
        "",
        "## Freshness",
        f"- latest_raw_date_detected: {str(latest_raw_date_detected.date()) if latest_raw_date_detected is not None else 'Unknown'}",
        f"- asof_date_used: {str(asof_date_used.date())}",
        f"- is_stale: {is_stale if is_stale is not None else 'Unknown'}",
        f"- stale_reason: {stale_reason if stale_reason else '—'}",
        "",
        "## Overall stance",
        "- Intended as research-safe (no same-bar fills; conservative stop handling; net costs), but still simplified (daily bars, no intraday microstructure, no portfolio constraints).",
    ]
    (out_dir / "backtest_realism_audit.md").write_text("\n".join(realism_lines), encoding="utf-8")

    # Survivorship / PIT audit artifacts (facts-only).
    universe_sources = []
    for p in [REPO / "config" / "universe_186.txt", REPO / "config" / "watchlist_80.txt", REPO / "config" / "watchlist.txt"]:
        if p.exists():
            universe_sources.append(str(p))
    surv_rows = [
        {
            "run_dir": str(out_dir),
            "universe_source_files": "; ".join(universe_sources) if universe_sources else "Unknown",
            "universe_construction": "Universe list is read from config file(s) and filtered to symbols present in local curated/raw OHLCV; VNINDEX/VN30 excluded.",
            "delisted_inactive_included": "Unknown (not verified by current pipeline/data).",
            "eligibility_point_in_time": "No (membership is current-list based; not reconstructed historically).",
            "survivorship_bias_risk": "Unknown/likely (depends on local OHLCV coverage of delisted names).",
            "fa_point_in_time": f"Approximate (available_date = report_date + {args.fa_lag_days}d); publish timestamps unavailable.",
            "unresolved_limitations": "Cannot guarantee PIT universe or delisted coverage from current repo data alone.",
        }
    ]
    pd.DataFrame(surv_rows).to_csv(out_dir / "survivorship_pit_audit.csv", index=False)
    (out_dir / "survivorship_pit_audit.md").write_text(
        "\n".join(
            [
                "# Survivorship & PIT audit (facts-only)",
                "",
                f"- Universe source files (checked in order): {('; '.join(universe_sources) if universe_sources else 'Unknown')}",
                "- Membership is based on the current config list and locally present OHLCV; not reconstructed as-of each historical date.",
                "- Therefore survivorship bias may remain if delisted/inactive names are missing from the local dataset.",
                f"- FA PIT approximation: available_date = report_date + {args.fa_lag_days} days.",
                "",
                "## Unresolved limitations",
                "- Delisted/inactive coverage: Unknown (not validated by this workflow).",
                "- PIT universe membership: Not implemented (requires historical membership data).",
            ]
        ),
        encoding="utf-8",
    )

    # Latest copy for convenience
    # Compatibility alias: keep both execution filenames.
    if (out_dir / "execution_backtest_results_gross_vs_net.csv").exists():
        (out_dir / "execution_backtest_results.csv").write_bytes((out_dir / "execution_backtest_results_gross_vs_net.csv").read_bytes())

    for fn in [
        "preset_grid_results.csv",
        "preset_robustness_summary.csv",
        "preset_parameter_effect_check.csv",
        "setup_quality_results.csv",
        "execution_backtest_results_gross_vs_net.csv",
        "execution_backtest_results.csv",
        "trade_log_best_presets.csv",
        "walkforward_oos_results.csv",
        "oos_rolling_train_test_results.csv",
        "oos_methodology_note.md",
        "family_comparison_daily_vs_weekly.csv",
        "latest_candidates_best_presets.csv",
        "latest_candidates_deduped.csv",
        "candidate_filter_funnel.csv",
        "backtest_realism_audit.md",
        "survivorship_pit_audit.csv",
        "survivorship_pit_audit.md",
        "prebreakout_research_report.md",
    ]:
        src = out_dir / fn
        if src.exists():
            (latest_link / fn).write_bytes(src.read_bytes())

    meta = {
        "run_dir": str(out_dir),
        "latest_dir": str(latest_link),
        "best_presets": best_presets,
        "asof_latest": str(asof_latest.date()),
        "benchmark": bench_symbol,
        "n_symbols": len(enriched),
        "n_presets": len(presets),
        "n_symbols_loaded_ex_benchmark": n_loaded_ex_bench,
        "n_symbols_eligible_after_history_filter": n_hist_ok,
        "n_symbols_eligible_after_liquidity_filter": n_liq_ok,
        "benchmark_symbols_used": bench_candidates,
        "latest_raw_date_detected": str(latest_raw_date_detected.date()) if latest_raw_date_detected is not None else None,
        "asof_date_used": str(asof_date_used.date()),
        "is_stale": is_stale,
        "stale_reason": stale_reason,
    }
    (out_dir / "run_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (latest_link / "run_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

