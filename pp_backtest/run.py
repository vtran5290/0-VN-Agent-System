# pp_backtest/run.py — Run backtest for watchlist, output CSV (win_rate, expectancy, max_drawdown, profit_factor)
from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Run from repo root: PYTHONPATH=. python -m pp_backtest.run  OR  cd pp_backtest && python run.py
_REPO = Path(__file__).resolve().parent.parent
_PP = Path(__file__).resolve().parent


def _config_hash(cfg: object, tickers: list[str], exit_fixed_bars: int | None = None, exit_armed_after: int | None = None, entry_undercut_rally: bool = False) -> str:
    """Stable short hash for reproducibility (no git required)."""
    import hashlib
    key = f"{getattr(cfg,'start','')}|{getattr(cfg,'end','')}|{len(tickers)}|{sorted(tickers)}|{getattr(cfg,'fee_bps',0)}|{getattr(cfg,'slippage_bps',0)}|{getattr(cfg,'min_hold_bars',0)}|exit_fixed={exit_fixed_bars}|exit_armed={exit_armed_after}|entry_ur={entry_undercut_rally}"
    return hashlib.sha256(key.encode()).hexdigest()[:12]


def _git_rev() -> str:
    """Return git HEAD short rev or 'n/a' if not a repo."""
    import subprocess
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=_REPO, capture_output=True, text=True, timeout=2,
        )
        return (r.stdout or "").strip() or "n/a"
    except Exception:
        return "n/a"
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_PP) not in sys.path:
    sys.path.insert(0, str(_PP))

try:
    from pp_backtest.config import BacktestConfig, PocketPivotParams, SellParams
    from pp_backtest.data import fetch_ohlcv_fireant, fetch_ohlcv_vnstock
    from pp_backtest.signals import pocket_pivot, sell_morales_kacher_v4, distribution_day_count_series, undercut_rally_signal, buyable_gap_up_signal, right_side_of_base_signal, avoid_extended_signal, atr as atr_signal
    from pp_backtest.signals_darvas import darvas_box, entry_darvas_breakout, exit_darvas_box_low
    from pp_backtest.signals_livermore import (
        market_filter_lolr,
        entry_livermore_reversal_pivot,
        entry_livermore_continuation_pivot,
        exit_livermore_pivot_failure,
        exit_livermore_ma20,
        exit_livermore_ma50,
    )
    from pp_backtest.backtest import run_single_symbol_with_ledger
    from pp_backtest.market_regime import add_book_regime_columns
    from src.signals.setup_quality import setup_quality
except ImportError:
    from config import BacktestConfig, PocketPivotParams, SellParams
    from data import fetch_ohlcv_fireant, fetch_ohlcv_vnstock
    from signals import pocket_pivot, sell_morales_kacher_v4, distribution_day_count_series, undercut_rally_signal, buyable_gap_up_signal, right_side_of_base_signal, avoid_extended_signal, atr as atr_signal
    from signals_darvas import darvas_box, entry_darvas_breakout, exit_darvas_box_low
    from signals_livermore import (
        market_filter_lolr,
        entry_livermore_reversal_pivot,
        entry_livermore_continuation_pivot,
        exit_livermore_pivot_failure,
        exit_livermore_ma20,
        exit_livermore_ma50,
    )
    from backtest import run_single_symbol_with_ledger
    from market_regime import add_book_regime_columns
    try:
        from src.signals.setup_quality import setup_quality
    except ImportError:
        setup_quality = None

# Default tickers; override by loading config/watchlist.txt if present
DEFAULT_TICKERS = [
    "SSI", "VCI", "SHS", "TCX", "MBB", "STB", "SHB", "DCM", "PVD", "PC1",
    "DXG", "VSC", "GMD", "MWG",
]


def load_tickers(watchlist_path: Path | None = None) -> list[str]:
    if watchlist_path is not None:
        p = watchlist_path if watchlist_path.is_absolute() else _REPO / watchlist_path
        if p.exists():
            lines = p.read_text(encoding="utf-8").strip().splitlines()
            return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]
        return DEFAULT_TICKERS.copy()
    watchlist = _REPO / "config" / "watchlist.txt"
    if watchlist.exists():
        lines = watchlist.read_text(encoding="utf-8").strip().splitlines()
        return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]
    return DEFAULT_TICKERS.copy()


# Market DD: threshold to trigger sell_mkt_dd (O'Neil: 5-6 warning; VN often 6-7)
MARKET_DD_THRESHOLD = 5
STOCK_DD_LB = 15
STOCK_DD_THRESHOLD = 3
MARKET_DD_LB = 20

# Gate: entry = PP AND setup_quality_score >= 50; None/NaN → skip (Option A, pre-registered)
USE_GATE_DEFAULT = True


def _add_setup_quality_column(df: pd.DataFrame) -> None:
    """Fill df['setup_quality_score'] per bar; None when warmup insufficient."""
    if setup_quality is None:
        return
    scores = []
    for i in range(len(df)):
        out = setup_quality(df, bar_index=i)
        scores.append(out["setup_quality_score"])
    df["setup_quality_score"] = scores


def main(use_vnstock: bool = False, args: object = None, use_gate: bool | None = None, soft_sell: bool = False, no_sell_v4: bool = False):
    cfg = BacktestConfig()
    if args and getattr(args, "start", None):
        cfg.start = args.start
    if args and getattr(args, "end", None):
        cfg.end = args.end
    if args and getattr(args, "min_hold_bars", None) is not None:
        cfg.min_hold_bars = int(args.min_hold_bars)
    if args and getattr(args, "fee_bps", None) is not None:
        cfg.fee_bps = float(args.fee_bps)
    if args and getattr(args, "slip_bps", None) is not None:
        cfg.slippage_bps = float(args.slip_bps)
    pp = PocketPivotParams()
    sp = SellParams(confirmation_closes=2 if soft_sell else 1)
    gate = use_gate if use_gate is not None else USE_GATE_DEFAULT

    fetch = fetch_ohlcv_vnstock if use_vnstock else fetch_ohlcv_fireant
    watchlist_path = Path(getattr(args, "watchlist", None)) if args and getattr(args, "watchlist", None) else None
    tickers = load_tickers(watchlist_path)
    if args and getattr(args, "symbols", None):
        wanted = {s.strip().upper() for s in args.symbols if s.strip()}
        tickers = [t for t in tickers if t.strip().upper() in wanted]

    universe_by_year = None
    if args and getattr(args, "universe", None) == "liquidity_topn":
        try:
            from pp_backtest.universe_liquidity import build_liquidity_universe_by_year, load_candidates
        except ImportError:
            from universe_liquidity import build_liquidity_universe_by_year, load_candidates
        candidates_path = getattr(args, "candidates", None) or "config/universe_186.txt"
        candidates = load_candidates(candidates_path, _REPO)
        if not candidates:
            print("[universe] No candidates loaded; falling back to watchlist.")
        else:
            liq_topn = int(getattr(args, "liq_topn", 50) or 50)
            # Optional year-band overrides (e.g. liq_topn_2012_2016 -> years 2012..2016)
            top_n: int | dict[int, int] = liq_topn
            for attr in dir(args):
                if attr.startswith("liq_topn_") and attr != "liq_topn":
                    part = attr.replace("liq_topn_", "")
                    if "_" in part:
                        a, b = part.split("_", 1)
                        try:
                            y1, y2 = int(a), int(b)
                            val = int(getattr(args, attr, 0))
                            if val and y1 <= y2:
                                if isinstance(top_n, int):
                                    top_n = {}
                                for y in range(y1, y2 + 1):
                                    top_n[y] = val
                        except (ValueError, TypeError):
                            pass
            universe_by_year = build_liquidity_universe_by_year(
                candidates, cfg.start, cfg.end, top_n, fetch,
                min_price=5000, min_bars_before=250,
            )
            tickers = sorted(set().union(*universe_by_year.values())) if universe_by_year else tickers
            sizes = [len(universe_by_year[y]) for y in sorted(universe_by_year.keys())]
            print(f"[universe] liquidity_topn top_n={liq_topn} candidates={len(candidates)} -> {len(tickers)} symbols, per-year sizes {sizes}")
    regime_ma200 = getattr(args, "regime_ma200", False) if args else False
    regime_liquidity = getattr(args, "regime_liquidity", False) if args else False
    meta_v1 = getattr(args, "meta_v1", False) if args else False
    _dist_max = getattr(args, "dist_entry_max", None) if args else None
    dist_entry_max = int(_dist_max) if _dist_max is not None and int(_dist_max) > 0 else None
    use_dist_entry = dist_entry_max is not None
    above_ma50 = getattr(args, "above_ma50", False) if args else False
    demand_thrust = getattr(args, "demand_thrust", False) if args else False
    tightness = getattr(args, "tightness", False) if args else False
    right_side = getattr(args, "right_side", False) if args else False
    avoid_extended = getattr(args, "avoid_extended", False) if args else False
    entry_bgu = getattr(args, "entry_bgu", False) if args else False
    exit_fixed = getattr(args, "exit_fixed_bars", None) if args else None
    exit_armed = getattr(args, "exit_armed_after", None) if args else None
    entry_ur = getattr(args, "entry_undercut_rally", False) if args else False
    book_regime = getattr(args, "book_regime", False) if args else False
    entry_mode = getattr(args, "entry", "pp") if args else "pp"
    exit_mode_arg = getattr(args, "exit", None) if args else None
    # Default exit by entry: darvas→darvas_box, livermore_*→livermore_pf; else full sell stack for pp
    if exit_mode_arg is not None:
        exit_mode_name = exit_mode_arg
    elif entry_mode == "darvas":
        exit_mode_name = "darvas_box"
    elif entry_mode in ("livermore_rpp", "livermore_cpp"):
        exit_mode_name = "livermore_pf"
    else:
        exit_mode_name = None
    # Gate off for Darvas/Livermore (setup_quality is PP-specific)
    if entry_mode in ("darvas", "livermore_rpp", "livermore_cpp"):
        gate = False
    # U&R pre-registered: Option B = fixed 5-bar exit for gross edge research (docs/PP_TWEAKS_RESEARCH.md)
    if entry_ur and exit_fixed is None:
        exit_fixed = 5
    exit_mode = "fixed_" + str(exit_fixed) if exit_fixed is not None else ("armed_" + str(exit_armed) if exit_armed is not None else "full")
    # Frozen config line + hash for reproducibility (red-flag 1); [run] = checklist for config drift
    config_hash = _config_hash(cfg, tickers, exit_fixed_bars=exit_fixed, exit_armed_after=exit_armed, entry_undercut_rally=entry_ur)
    commit = _git_rev()
    gates = "liquidity" + ("+ma200" if regime_ma200 else "") + ("+meta_v1" if meta_v1 else "") + ("+dist_entry" if use_dist_entry else "") + ("+book_regime" if book_regime else "") + ("+ma50" if above_ma50 else "") + ("+demand_thrust" if demand_thrust else "") + ("+tightness" if tightness else "") + ("+right_side" if right_side else "") + ("+avoid_extended" if avoid_extended else "")
    print(f"[run] config_hash={config_hash} commit={commit}")
    entry_name = entry_mode if entry_mode != "pp" else ("bgu" if entry_bgu else ("undercut_rally" if entry_ur else "pp"))
    exit_name = exit_mode_name if exit_mode_name else exit_mode
    print(f"[run] start={cfg.start} end={cfg.end} symbols={len(tickers)} tickers={tickers[:5]}{'...' if len(tickers)>5 else ''} gate={gate} entry={entry_name} exit={exit_name} entry_gates={gates} min_hold_bars={getattr(cfg, 'min_hold_bars', 0)} fee_bps={cfg.fee_bps} slip_bps={cfg.slippage_bps} exit_mode={exit_mode} no_sell_v4={no_sell_v4}")
    if not tickers:
        print("[pp_backtest.run] No symbols to run after filtering. "
              "Check watchlist.txt and --symbols list.")
        return
    # Market series for mkt_dd_count (VN30); optional regime; Darvas RS needs index close before merge trim
    market_df = None
    market_df_rs = None
    try:
        market_df = fetch("VN30", cfg.start, cfg.end)
        market_df["mkt_dd_count"] = distribution_day_count_series(market_df, lb=MARKET_DD_LB)
        if regime_ma200:
            market_df["ma200"] = market_df["close"].rolling(200).mean()
            market_df["regime_on"] = (market_df["close"] > market_df["ma200"]).fillna(False)
        if regime_liquidity:
            vol = market_df["volume"]
            r30 = vol.rolling(30, min_periods=25).mean()
            r126 = vol.rolling(126, min_periods=100).mean()
            market_df["liquidity_on"] = (r30 > r126).fillna(False)
        if book_regime:
            market_df = add_book_regime_columns(market_df)
        if entry_mode in ("livermore_rpp", "livermore_cpp"):
            market_df["lolr_risk_on"] = market_filter_lolr(market_df, vol_atr_pct_max=0.05)
        # Meta-layer v1: TRENDING = (index > MA) & (MA slope > 0) & (ATR%/close < vol_max). Optional stability bars.
        if meta_v1:
            try:
                period = int(getattr(args, "regime_ma_period", 50) or 50)
                vol_max = float(getattr(args, "regime_vol_max", 0.05) or 0.05)
                stability_bars = int(getattr(args, "regime_stability_bars", 0) or 0)
                market_df["_ma"] = market_df["close"].astype(float).rolling(period).mean()
                market_df["_ma_slope"] = market_df["_ma"].diff(5)
                a = atr_signal(market_df, 14)
                market_df["_atr_pct"] = a / market_df["close"].astype(float).replace(0, np.nan)
                raw = (
                    (market_df["close"] > market_df["_ma"])
                    & (market_df["_ma_slope"] > 0)
                    & (market_df["_atr_pct"] < vol_max)
                )
                if stability_bars >= 1:
                    market_df["meta_trending"] = (
                        raw.astype(float).rolling(stability_bars, min_periods=stability_bars).sum() == stability_bars
                    )
                else:
                    market_df["meta_trending"] = raw
                market_df["meta_trending"] = market_df["meta_trending"].fillna(False)
                market_df = market_df.drop(columns=["_ma", "_ma_slope", "_atr_pct"], errors="ignore")
            except Exception as e:
                print(f"[meta_v1] Failed: {e}. Disabling meta_v1.")
                meta_v1 = False
        market_df_rs = market_df[["date", "close"]].copy() if entry_mode == "darvas" and "close" in market_df.columns else None
        merge_cols = ["date", "mkt_dd_count"] + (["regime_on"] if regime_ma200 else []) + (["liquidity_on"] if regime_liquidity else []) + (["regime_ftd", "no_new_positions"] if book_regime else []) + (["lolr_risk_on"] if entry_mode in ("livermore_rpp", "livermore_cpp") else []) + (["meta_trending"] if meta_v1 else [])
        market_df = market_df[[c for c in merge_cols if c in market_df.columns]].copy()
    except Exception as e:
        print(f"[market] VN30 not loaded: {e}. sell_mkt_dd will be False.")

    rows = []
    ledgers = []
    total_symbol_bars = 0
    for sym in tickers:
        try:
            df = fetch(sym, cfg.start, cfg.end)
        except Exception as e:
            print(f"[skip] {sym}: {e}")
            continue

        total_symbol_bars += len(df)
        if entry_mode == "darvas":
            darvas_relaxed = getattr(args, "darvas_relaxed", False)
            _tol = getattr(args, "darvas_tol", None)
            darvas_tol = 0.3 if darvas_relaxed else (float(_tol) if _tol is not None else 0.2)
            _stab = getattr(args, "darvas_stability_bars", None)
            darvas_stability = 2 if darvas_relaxed else (int(_stab) if _stab is not None else 0)
            _gap = getattr(args, "darvas_touch_gap", None)
            darvas_gap = 1 if darvas_relaxed else (int(_gap) if _gap is not None else 0)
            _max_r = getattr(args, "darvas_max_range_pct", None)
            darvas_max_range_pct = (0.015 if darvas_relaxed else None) if _max_r is None else float(_max_r)
            df = darvas_box(
                df, L=20, touch_high_min=2, touch_low_min=1,
                atr_tolerance_mult=darvas_tol, stability_bars=darvas_stability,
                touch_min_gap=darvas_gap, max_range_pct=darvas_max_range_pct,
            )
            index_for_rs = market_df_rs if market_df_rs is not None and getattr(args, "rs_filter", False) else None
            new_high_N = None if getattr(args, "darvas_no_new_high", False) else 120
            require_confirm = not getattr(args, "darvas_no_confirm", False)
            _vk = getattr(args, "darvas_vol_k", None)
            darvas_vol_k = 1.5 if _vk is None else float(_vk)
            df["pp"] = entry_darvas_breakout(
                df, L=20, vol_k=darvas_vol_k, new_high_N=new_high_N,
                require_box_confirm=require_confirm, index_df=index_for_rs, rs_lookback=60,
            )
            ex = exit_darvas_box_low(df, atr_buffer=0.25)
            df["sell_darvas_box"] = ex
            try:
                from pp_backtest.signals import atr as _atr
            except ImportError:
                from signals import atr as _atr
            df["darvas_stop_buffer"] = 0.25 * _atr(df, 14)
            df["sell_v4"] = False
            df["sell_mkt_dd"] = False
            df["sell_stk_dd"] = False
            df["sell_final"] = ex
            df["stk_dd_count"] = 0
        elif entry_mode in ("livermore_rpp", "livermore_cpp"):
            if entry_mode == "livermore_rpp":
                df["pp"] = entry_livermore_reversal_pivot(df, N=10, volume_confirm=True)
                df["trigger_level"] = df["high"].rolling(10, min_periods=10).max().shift(1)
            else:
                df["pp"] = entry_livermore_continuation_pivot(df, L=20, vol_k=1.2, above_ma=20)
                df["trigger_level"] = df["high"].rolling(20, min_periods=20).max().shift(1)
            if exit_mode_name == "livermore_pf":
                ex = exit_livermore_pivot_failure(df, trigger_col="trigger_level", K=3)
                df["sell_livermore_pf"] = ex
                df["sell_final"] = ex
            elif exit_mode_name == "ma20":
                ex = exit_livermore_ma20(df)
                df["sell_livermore_ma20"] = ex
                df["sell_final"] = ex
            elif exit_mode_name == "ma50":
                ex = exit_livermore_ma50(df)
                df["sell_livermore_ma50"] = ex
                df["sell_final"] = ex
            else:
                ex = exit_livermore_pivot_failure(df, trigger_col="trigger_level", K=3)
                df["sell_livermore_pf"] = ex
                df["sell_final"] = ex
            df["sell_v4"] = False
            df["sell_mkt_dd"] = False
            df["sell_stk_dd"] = False
            df["stk_dd_count"] = 0
        else:
            df = pocket_pivot(df, pp)
            df = sell_morales_kacher_v4(df, sp)
            df["stk_dd_count"] = distribution_day_count_series(df, lb=STOCK_DD_LB)
            df["sell_stk_dd"] = (df["stk_dd_count"] >= STOCK_DD_THRESHOLD).fillna(False)
            df["sell_mkt_dd"] = False  # set after merge if market_df has mkt_dd_count
            if no_sell_v4:
                df["sell_v4"] = False
                df["sell_final"] = df["sell_mkt_dd"] | df["sell_stk_dd"] | df["sell_ugly_only"].fillna(False)
            else:
                df["sell_v4"] = df["sell"].fillna(False)
                df["sell_final"] = df["sell_v4"] | df["sell_mkt_dd"] | df["sell_stk_dd"]
            if entry_ur:
                df["pp"] = undercut_rally_signal(df)
            if entry_bgu:
                df["pp"] = buyable_gap_up_signal(df)
            if right_side:
                df["right_side_of_base"] = right_side_of_base_signal(df)
            if avoid_extended:
                df["avoid_extended"] = avoid_extended_signal(df)

        if market_df is not None:
            df = df.merge(market_df, on="date", how="left")
            if entry_mode in ("livermore_rpp", "livermore_cpp"):
                df["pp"] = df["pp"] & df["lolr_risk_on"].fillna(False)
            if entry_mode not in ("darvas", "livermore_rpp", "livermore_cpp"):
                df["sell_mkt_dd"] = (df["mkt_dd_count"] >= MARKET_DD_THRESHOLD).fillna(False)
            if entry_mode in ("darvas", "livermore_rpp", "livermore_cpp"):
                df["mkt_dd_count"] = df.get("mkt_dd_count", np.nan)
                df["sell_mkt_dd"] = False
            if not regime_ma200 and "regime_on" in df.columns:
                df = df.drop(columns=["regime_on"], errors="ignore")
            if not regime_liquidity and "liquidity_on" in df.columns:
                df = df.drop(columns=["liquidity_on"], errors="ignore")
            if not meta_v1 and "meta_trending" in df.columns:
                df = df.drop(columns=["meta_trending"], errors="ignore")
            if not book_regime:
                for col in ("regime_ftd", "no_new_positions"):
                    if col in df.columns:
                        df = df.drop(columns=[col], errors="ignore")
        else:
            df["mkt_dd_count"] = np.nan
            df["sell_mkt_dd"] = False
            if entry_mode in ("livermore_rpp", "livermore_cpp"):
                df["lolr_risk_on"] = True

        if gate:
            if setup_quality is not None:
                _add_setup_quality_column(df)
            elif sym == tickers[0]:
                print("[gate] setup_quality not available; running baseline (no gate).")

        # Liquidity-topn universe: only allow entry when symbol is in universe for that bar's year
        if universe_by_year is not None and "pp" in df.columns:
            df["in_universe"] = df["date"].apply(
                lambda d: sym in universe_by_year.get(pd.Timestamp(d).year, [])
            )
            df["pp"] = (df["pp"].fillna(False) & df["in_universe"].fillna(False))

        exit_armed_after = getattr(args, "exit_armed_after", None) if args else None
        use_fixed = exit_fixed is not None
        use_armed = exit_armed_after is not None and not use_fixed
        use_darvas_trail = entry_mode == "darvas" and exit_mode_name == "darvas_box"
        use_livermore_k = entry_mode in ("livermore_rpp", "livermore_cpp") and exit_mode_name == "livermore_pf"
        livermore_k = int(getattr(args, "livermore_pf_k", 3) or 3) if args else 3
        pyramid_darvas = getattr(args, "pyramid_darvas", False) if args else False
        pyramid_livermore = getattr(args, "pyramid_livermore", False) if args else False
        stats, ledger = run_single_symbol_with_ledger(
            df, cfg, use_gate=gate, use_regime_ma200=regime_ma200, use_regime_liquidity=regime_liquidity,
            use_meta_v1=meta_v1, use_dist_entry_filter=use_dist_entry, dist_entry_max=dist_entry_max or 0,
            use_regime_ftd=book_regime, use_no_new_positions=book_regime,
            use_above_ma50=above_ma50, use_demand_thrust=demand_thrust, use_tightness=tightness,
            use_right_side_of_base=right_side, use_avoid_extended=avoid_extended,
            use_exit_fixed_bars=use_fixed, fixed_exit_bars=int(exit_fixed or 10),
            use_exit_armed_after=use_armed, exit_armed_after_bars=int(exit_armed_after or 10),
            use_darvas_trailing=use_darvas_trail, use_livermore_pf_k_bars=use_livermore_k,
            livermore_pf_k=livermore_k,
            use_pyramid_darvas=pyramid_darvas, max_adds_darvas=1,
            use_pyramid_livermore=pyramid_livermore, max_adds_livermore=1, pyramid_livermore_pct=0.08,
            engine=entry_mode,
        )
        stats["symbol"] = sym
        rows.append(stats)
        if not ledger.empty:
            ledger["symbol"] = sym
            ledgers.append(ledger)

    if not rows:
        print("No symbols completed. Check data source and date range.")
        return

    out = pd.DataFrame(rows)
    out = out.sort_values(["profit_factor", "win_rate", "avg_ret"], ascending=[False, False, False])
    csv_path = _PP / "pp_sell_backtest_results.csv"
    out.to_csv(csv_path, index=False)
    print(out.to_string())
    if gate and "skipped_due_to_warmup" in out.columns:
        total_warmup = out["skipped_due_to_warmup"].fillna(0).astype(int).sum()
        total_gate = out["skipped_due_to_gate"].fillna(0).astype(int).sum()
        print(f"\n[gate] skipped_due_to_warmup (total): {total_warmup}")
        print(f"[gate] skipped_due_to_gate (total):   {total_gate}")
    # Gate filter counts — red-flag 2: demand_thrust must filter (Exp3 < Exp2 trades)
    for col in ("filtered_by_liquidity", "filtered_by_ma50", "filtered_by_demand_thrust", "filtered_by_tightness", "filtered_by_right_side", "filtered_by_avoid_extended"):
        if col in out.columns:
            total = out[col].fillna(0).astype(int).sum()
            print(f"[gate] {col}: {total}")
    print(f"\nWrote: {csv_path}")

    if ledgers:
        all_ledger = pd.concat(ledgers, ignore_index=True)
        ledger_path = _PP / "pp_trade_ledger.csv"
        all_ledger.to_csv(ledger_path, index=False)
        print(f"Wrote: {ledger_path} (cols: hold_cal_days, hold_trading_bars, engine, entry_bar_index; exit_reason: SELL_V4 / MARKET_DD / STOCK_DD / DARVAS_BOX / LIVERMORE_PF / UGLY_BAR / FIXED_BARS / EOD_FORCE)")
        # Aggregate metrics (pre-registered for exit experiments; copy to validation table)
        ret = all_ledger["ret"].astype(float).values
        n = len(ret)
        wins = ret[ret > 0]
        losses = ret[ret <= 0]
        agg_pf = (wins.sum() / (-losses.sum())) if len(losses) and losses.sum() < 0 and len(wins) else np.nan
        cum = np.cumprod(1.0 + ret) - 1.0
        peak = np.maximum.accumulate(1.0 + cum)
        agg_mdd = float((((1.0 + cum) / peak) - 1.0).min()) if len(cum) else np.nan
        agg_tail5 = float(np.nanpercentile(ret, 5))
        if "hold_trading_bars" in all_ledger.columns:
            agg_median_bars = float(all_ledger["hold_trading_bars"].median())
        else:
            agg_median_bars = float(all_ledger["hold_bars"].median()) if "hold_bars" in all_ledger.columns else np.nan
        # Exposure % and turnover (for meta comparison)
        hold_bars_sum = all_ledger["hold_trading_bars"].sum() if "hold_trading_bars" in all_ledger.columns else all_ledger.get("hold_bars", pd.Series([0])).sum()
        exposure_pct = 100.0 * hold_bars_sum / total_symbol_bars if total_symbol_bars else np.nan
        num_years = (pd.Timestamp(cfg.end) - pd.Timestamp(cfg.start)).days / 365.25
        turnover_per_year = n / num_years if num_years and num_years > 0 else np.nan
        total_skipped_regime = int(out["skipped_due_to_regime"].fillna(0).sum()) if "skipped_due_to_regime" in out.columns else None
        total_skipped_dist = int(out["skipped_due_to_dist"].fillna(0).sum()) if "skipped_due_to_dist" in out.columns else None
        print(f"[aggregate] trades={n} PF={agg_pf:.4f}" if np.isfinite(agg_pf) else f"[aggregate] trades={n} PF=nan")
        print(f"[aggregate] tail5={agg_tail5:.2%} max_drawdown={agg_mdd:.2%} median_hold_bars={agg_median_bars:.1f}")
        print(f"[aggregate] exposure_pct={exposure_pct:.2f}% turnover_per_year={turnover_per_year:.1f}" if np.isfinite(exposure_pct) and np.isfinite(turnover_per_year) else f"[aggregate] exposure_pct={exposure_pct} turnover_per_year={turnover_per_year}")
        if total_skipped_regime is not None and total_skipped_regime > 0:
            print(f"[aggregate] skipped_due_to_regime={total_skipped_regime}")
        if total_skipped_dist is not None and total_skipped_dist > 0:
            print(f"[aggregate] skipped_due_to_dist={total_skipped_dist}")
        # One-line summary for meta comparison table (copy-paste)
        skip_str = f" skipped_regime={total_skipped_regime}" if total_skipped_regime is not None and total_skipped_regime > 0 else ""
        if total_skipped_dist is not None and total_skipped_dist > 0:
            skip_str += f" skipped_dist={total_skipped_dist}"
        print(f"[summary] trades={n} PF={agg_pf:.4f} tail5={agg_tail5:.2%} maxDD={agg_mdd:.2%} exposure_pct={exposure_pct:.2f} turnover_yr={turnover_per_year:.1f}{skip_str}")
        print(f"[aggregate] avg_ret={ret.mean():.2%} win_rate={(ret>0).mean():.2%} avg_win={wins.mean():.2%}" if len(wins) else "[aggregate] avg_ret=... win_rate=... avg_win=nan")
        if len(losses):
            print(f"[aggregate] avg_loss={losses.mean():.2%}")

    print("\nRead order: profit_factor >1.2 ok, >1.5 good; avg_ret; #trades; avg_hold_days; max_drawdown.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--vnstock", action="store_true", help="Use vnstock instead of FireAnt")
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=None,
        help="Optional list of symbols to backtest (e.g., --symbols MBB SSI). "
             "If provided, only runs symbols in watchlist that match this list."
    )
    parser.add_argument("--no-gate", action="store_true", help="Disable setup_quality gate (baseline PP only)")
    parser.add_argument("--soft-sell", action="store_true", help="SOFT_SELL: 2 consecutive closes below tier MA (sell_v4_confirmation_closes=2)")
    parser.add_argument("--start", default=None, help="Override config start date (e.g. 2018-01-01); use same for baseline and soft_sell")
    parser.add_argument("--end", default=None, help="Override config end date; use same for baseline and soft_sell")
    parser.add_argument("--min-hold-bars", type=int, default=None, help="VN T+2.5: min trading days (bar count) before any exit (e.g. 3). 0 = current. Pre-registered for baseline_vn_realistic.")
    parser.add_argument("--no-sell-v4", action="store_true", help="Disable SELL_V4 (MA-trailing); keep STOCK_DD, MARKET_DD, UglyBar only. Pre-registered for no_SELL_V4 experiment.")
    parser.add_argument("--regime-ma200", action="store_true", help="Pre-registered: trade only when VN30 close > MA200. Single regime filter, no grid search.")
    parser.add_argument("--regime-liquidity", action="store_true", help="Pre-registered: trade only when VN30 30d vol > 126d vol (liquidity expansion).")
    parser.add_argument("--above-ma50", action="store_true", help="PP_GIL_V4.2: entry only when stock close > MA50 (structural gate, no tune).")
    parser.add_argument("--demand-thrust", action="store_true", help="PP_GIL_V4.2: entry only when close>prev_close and close in upper 30%% of range.")
    parser.add_argument("--tightness", action="store_true", help="PP_GIL_V4.2: entry only when at least 2 of last 5 bars have vol < MA20(vol).")
    parser.add_argument("--fee-bps", type=float, default=None, help="Override fee in bps per side (e.g. 25 for RT 30bps with slip 5).")
    parser.add_argument("--slip-bps", type=float, default=None, help="Override slippage in bps per side (e.g. 5).")
    parser.add_argument("--watchlist", default=None, help="Path to watchlist file (e.g. config/watchlist_80.txt). Relative to repo root.")
    parser.add_argument("--exit-fixed-bars", type=int, default=None, metavar="N", help="Exit after exactly N bars (no SELL_V4/DD). Oracle for alpha vs exit.")
    parser.add_argument("--exit-armed-after", type=int, default=None, metavar="N", help="Delay arming: bars 1..N-1 only UglyBar; from bar N full SELL_V4+DD. Test 5,10,15.")
    parser.add_argument("--entry-undercut-rally", action="store_true", help="Entry = U&R (Undercut & Rally). Exit = fixed 5 bars (Option B) unless --exit-fixed-bars set. Pre-registered for gross edge test.")
    parser.add_argument("--book-regime", action="store_true", help="Gil/O'Neil book regime: FTD (close>MA50 & MA50 slope>0) + no new positions when dist_days_last_10>=3. Luôn bật khi test book conditions.")
    parser.add_argument("--entry-bgu", action="store_true", help="Entry = Buyable Gap-Up (gap>=3% & vol>=1.5*avg_vol). Sách 2010/2012.")
    parser.add_argument("--right-side", action="store_true", help="Pattern: entry only when close > midpoint of last 3m range (right-side-of-base).")
    parser.add_argument("--avoid-extended", action="store_true", help="Pattern: entry only when distance from MA10 < 5%% (avoid extended).")
    parser.add_argument("--entry", choices=["pp", "darvas", "livermore_rpp", "livermore_cpp"], default="pp", help="Entry: pp (default) | darvas | livermore_rpp (reversal pivot) | livermore_cpp (continuation pivot).")
    parser.add_argument("--exit", choices=["darvas_box", "livermore_pf", "ma20", "ma50"], default=None, help="Exit: darvas_box | livermore_pf | ma20 | ma50. Default by entry.")
    parser.add_argument("--rs-filter", action="store_true", help="Darvas: entry only when stock_ret_60d > index_ret_60d.")
    parser.add_argument("--pyramid-darvas", action="store_true", help="Darvas: add when new higher box + unrealized profit (max 1 add).")
    parser.add_argument("--pyramid-livermore", action="store_true", help="Livermore: add when price +8%% from entry + new pivotal point (max 1 add).")
    parser.add_argument("--livermore-pf-k", type=int, default=3, choices=[2, 3, 5], metavar="K", help="Livermore: exit if close < trigger within K bars. Sweep 2/3/5.")
    parser.add_argument("--darvas-relaxed", action="store_true", help="Darvas Option A: tol=0.3, stability=2, gap=1, max_range_pct=1.5%% (nới để có trades audit).")
    parser.add_argument("--darvas-tol", type=float, default=None, metavar="X", help="Darvas: atr_tolerance_mult (default 0.2; with --darvas-relaxed 0.3). Sweep 0.2/0.3/0.4.")
    parser.add_argument("--darvas-stability-bars", type=int, default=None, metavar="N", help="Darvas: box stable N bars before counting touches (0=off; with --darvas-relaxed 2).")
    parser.add_argument("--darvas-touch-gap", type=int, default=None, metavar="N", help="Darvas: min gap between touch events (0=raw count; with --darvas-relaxed 1).")
    parser.add_argument("--darvas-max-range-pct", type=float, default=None, metavar="X", help="Darvas: box_confirm only if box_range_pct <= X (e.g. 0.015=1.5%%). None=no filter.")
    parser.add_argument("--darvas-no-new-high", action="store_true", help="Darvas: tắt filter close>=highest(close,120).")
    parser.add_argument("--darvas-no-confirm", action="store_true", help="Darvas: require_box_confirm=False (audit / tìm nút nghẽn).")
    parser.add_argument("--darvas-vol-k", type=float, default=None, help="Darvas: vol_k (default 1.5). 0 = bỏ qua volume để debug.")
    parser.add_argument("--universe", choices=["watchlist", "liquidity_topn"], default="watchlist", help="Universe: watchlist (default) | liquidity_topn (Top N by median value 60d per year, no forward bias).")
    parser.add_argument("--liq-topn", type=int, default=50, metavar="N", help="When --universe liquidity_topn: top N symbols per year (default 50).")
    parser.add_argument("--candidates", default=None, help="When --universe liquidity_topn: path to candidate symbols file (default config/universe_186.txt).")
    parser.add_argument("--meta-v1", action="store_true", help="Meta-layer v1: trade only when TRENDING (VN30>MA, MA slope>0, ATR%%<vol_max). Else no trade.")
    parser.add_argument("--regime-ma-period", type=int, default=50, metavar="N", help="Meta v1: MA period for index (default 50). Test 50 vs 100.")
    parser.add_argument("--regime-vol-max", type=float, default=0.05, metavar="X", help="Meta v1: max ATR14/close for index (default 0.05).")
    parser.add_argument("--regime-stability-bars", type=int, default=0, metavar="N", help="Meta v1: require regime True for N bars before flip (default 0; use 3 to reduce whipsaw).")
    parser.add_argument("--dist-entry-max", type=int, default=None, metavar="N", help="O'Neil: no new entry when VN30 distribution days (20d) >= N (e.g. 4). 0 or omit = off. Spec: docs/META_LAYER_SPEC.md §11.")
    args = parser.parse_args()
    main(
        use_vnstock=args.vnstock,
        args=args,
        use_gate=not getattr(args, "no_gate", False),
        soft_sell=getattr(args, "soft_sell", False),
        no_sell_v4=getattr(args, "no_sell_v4", False),
    )
