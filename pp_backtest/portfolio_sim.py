from __future__ import annotations

"""
pp_backtest/portfolio_sim.py

Overlapping portfolio simulator for weekly Pocket Pivot strategy.

- All monetary amounts in VND (initial_equity, cash, position values, risk budget, liquidity cap).
- Process exits first (at next week open when exit signal from this week close), then entries.
- Size by risk budget (VND), max heat, max positions, max symbol weight, liquidity cap (5% ADTV20).
- Regime: require regime_ftd==True; block when no_new_positions==True.
- Fees: 15 bps per side on entry and exit.
- Equity = cash + mark-to-market value of open positions (weekly close).
"""

import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple, Any

import numpy as np
import pandas as pd

from .eligibility import EligibilityMap, get_global_eligibility
from src.backtest.execution import ExecutionConfig, FillTiming, apply_costs, build_execution_audit, execution_mode_label

_PP = Path(__file__).resolve().parent

# Default NAV in VND (1 billion)
DEFAULT_INITIAL_EQUITY_VND = 1_000_000_000


@dataclass
class PortfolioConfig:
    risk_per_trade: float = 0.005       # 0.5% of NAV
    max_heat: float = 0.04             # 4% of NAV
    max_positions: int = 8
    max_symbol_weight: float = 0.10    # 10% of NAV per symbol
    liquidity_participation_cap: float = 0.05   # 5% of ADTV20 (VND)
    initial_equity: float = DEFAULT_INITIAL_EQUITY_VND  # VND
    fee_bps_per_side: float = 15.0
    # Optional admission filters (None = no filter)
    base_depth_pct_max: Optional[float] = None   # e.g. 0.30
    tightness_3w_pct_max: Optional[float] = None  # e.g. 0.08
    ext_vs_ma10_max: Optional[float] = None       # e.g. 0.12


def _compute_base_features(
    wdf: pd.DataFrame,
    idx: int,
    max_lookback_weeks: int = 30,
) -> Tuple[int, float, float]:
    if idx <= 0 or wdf.empty:
        return 0, np.nan, np.nan
    start = max(0, idx - max_lookback_weeks)
    base = wdf.iloc[start:idx]
    if base.empty:
        return 0, np.nan, np.nan
    high = base["high"].astype(float).values
    low = base["low"].astype(float).values
    base_length = len(base)
    peak = float(high.max())
    trough = float(low.min())
    base_depth_pct = (peak - trough) / peak if peak > 0 else np.nan
    tail = base.tail(3)
    if len(tail) < 3:
        tight_3w = np.nan
    else:
        t_high = float(tail["high"].astype(float).max())
        t_low = float(tail["low"].astype(float).min())
        last_close = float(tail["close"].astype(float).iloc[-1])
        tight_3w = (t_high - t_low) / last_close if last_close > 0 else np.nan
    return base_length, base_depth_pct, tight_3w


def _compute_ext_ma10(row: pd.Series) -> float:
    close = float(row["close"])
    ma10 = float(row.get("ma10", np.nan))
    if np.isnan(ma10) or ma10 <= 0:
        return np.nan
    return (close - ma10) / ma10


def _compute_stop_price(row: pd.Series) -> float:
    close = float(row["close"])
    low = float(row["low"])
    ma10 = float(row.get("ma10", np.nan))
    ema21 = float(row.get("ema21", np.nan))
    stop_pp = low
    stop_ma10 = ma10 * 0.99 if not np.isnan(ma10) else close * 0.92
    stop_ema21 = ema21 * 0.99 if not np.isnan(ema21) else close * 0.92
    return max(stop_pp, stop_ma10, stop_ema21)


def run_portfolio_backtest(
    weekly_dfs: Dict[str, pd.DataFrame],
    config: PortfolioConfig,
    eligibility: Optional[EligibilityMap] = None,
    ranking_mode: str = "default",
    exec_cfg: ExecutionConfig | None = None,
) -> tuple[pd.DataFrame, dict]:
    """
    Overlapping portfolio simulation. All amounts in VND.
    Exit: signal from this week close -> exit at next week open (or current close at EOS).
    Equity = cash + mark-to-market (positions at weekly close).
    Fees: fee_bps_per_side on entry and exit.
    ranking_mode: "default"|"current" | "adtv20_only"|"adtv_only" | "tightness_only" | "ext_only"|"extension_only" |
      "extension_first" | "tightness_first" | "volume_thrust_first" | "liquidity_first" | "simple_composite" |
      "random"|"random_seed_42"
    """
    # Normalize naming for experiment runner
    _mode = ranking_mode.strip().lower()
    if _mode == "current":
        _mode = "default"
    elif _mode == "adtv_only":
        _mode = "adtv20_only"
    elif _mode == "extension_only":
        _mode = "ext_only"
    elif _mode == "liquidity_first":
        _mode = "adtv20_only"
    elif _mode == "extension_first":
        _mode = "ext_only"
    elif _mode == "tightness_first":
        _mode = "tightness_only"
    elif _mode == "random_seed_42":
        _mode = "random"
    ranking_mode = _mode

    if eligibility is None:
        eligibility = get_global_eligibility()

    _exec = exec_cfg or ExecutionConfig(
        entry_timing=FillTiming.NEXT_BAR_OPEN,
        exit_timing=FillTiming.NEXT_BAR_OPEN,
        fee_bps_per_side=float(config.fee_bps_per_side),
        slippage_bps_per_side=0.0,  # portfolio sim historically uses fee only; keep default 0 unless passed in
        liquidity_participation_cap=float(config.liquidity_participation_cap),
    )
    fee_mult = _exec.fee_mult()
    slip_mult = _exec.slip_mult()
    entry_delay = int(_exec.entry_delay_bars or 0)
    exit_delay = int(_exec.exit_delay_bars or 0)
    nav_vnd = config.initial_equity
    cash_vnd = nav_vnd
    all_dates = sorted(set().union(*(set(w["date"].astype(str)) for w in weekly_dfs.values())))
    if not all_dates:
        return pd.DataFrame(), {}

    positions: Dict[str, dict] = {}
    equity_path = [nav_vnd]
    heat_path = [0.0]
    gross_exposure_path = [0.0]
    dates_path = [pd.to_datetime(all_dates[0])]
    trades: list[dict] = []
    signal_log_rows: list[dict] = []
    position_sizes_vnd: list[float] = []

    skipped_ineligible = 0
    skipped_heat = 0
    skipped_max_positions = 0
    skipped_liquidity = 0
    skipped_regime_off = 0
    skipped_no_new_positions = 0
    post_regime_candidates = 0
    rejected_max_positions_count = 0

    for i, dt in enumerate(all_dates):
        cur_date = pd.to_datetime(dt)

        # --- 1) Exits first: signal at this week close -> exit at next week open (research-safe default) ---
        to_close: list[str] = []
        for sym, pos in list(positions.items()):
            wdf = weekly_dfs.get(sym)
            if wdf is None:
                continue
            row = wdf[wdf["date"].astype(str) == dt]
            if row.empty:
                continue
            row = row.iloc[0]
            exit_sig = bool(row.get("exit_ma10", False))
            if not exit_sig:
                continue

            # Exit at next week open (+ optional delay); if no next bar, use this week close (EOS fallback)
            next_idx = i + 1 + exit_delay
            next_dt = all_dates[next_idx] if next_idx < len(all_dates) else None
            if next_dt is not None:
                next_row = wdf[wdf["date"].astype(str) == next_dt]
                if not next_row.empty:
                    exit_price_raw = float(next_row["open"].iloc[0])
                    exit_date = pd.to_datetime(next_dt)
                else:
                    exit_price_raw = float(row["close"])
                    exit_date = cur_date
            else:
                exit_price_raw = float(row["close"])
                exit_date = cur_date
            exit_price = apply_costs(exit_price_raw, "sell", fee_mult, slip_mult)

            size = pos["shares"]
            entry_price = pos["entry_price"]
            exit_value_vnd = exit_price * size
            entry_value_vnd = entry_price * size
            # entry_price is stored as net-of-costs fill, so compute PnL in consistent net terms
            pnl_vnd = exit_value_vnd - entry_value_vnd
            cash_vnd += exit_value_vnd

            to_close.append(sym)
            ret_pct = (exit_price - entry_price) / entry_price if entry_price > 0 else np.nan
            trades.append({
                "symbol": sym,
                "entry_date": pos["entry_date"],
                "exit_date": exit_date,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "exit_open_raw": exit_price_raw,
                "shares": size,
                "pnl": pnl_vnd,
                "ret": ret_pct,
                "risk_budget": pos["risk_budget"],
            })
        for sym in to_close:
            positions.pop(sym, None)

        # --- 2) Mark-to-market equity (cash + positions at this week close) ---
        position_value_vnd = 0.0
        for sym, pos in positions.items():
            wdf = weekly_dfs.get(sym)
            if wdf is None or wdf.empty:
                position_value_vnd += pos["entry_price"] * pos["shares"]
                continue
            row = wdf[wdf["date"].astype(str) == dt]
            if row.empty:
                position_value_vnd += pos["entry_price"] * pos["shares"]
            else:
                position_value_vnd += float(row.iloc[0]["close"]) * pos["shares"]
        equity_vnd = cash_vnd + position_value_vnd
        open_risk_vnd = sum(p["risk_budget"] for p in positions.values())
        free_heat_vnd = max(0.0, config.max_heat * equity_vnd - open_risk_vnd)

        # --- 3) Regime for this week (for entry gate) ---
        regime_ftd = False
        no_new_positions = True
        regime_row = None
        for wdf in weekly_dfs.values():
            r = wdf[wdf["date"].astype(str) == dt]
            if not r.empty:
                regime_row = r.iloc[0]
                break
        if regime_row is not None:
            regime_ftd = bool(regime_row.get("regime_ftd", False))
            no_new_positions = bool(regime_row.get("no_new_positions", True))

        # --- 4) Gather candidates (weekly_pp True) ---
        candidates: list[dict] = []
        for sym, wdf in weekly_dfs.items():
            row = wdf[wdf["date"].astype(str) == dt]
            if row.empty:
                continue
            row = row.iloc[0]
            if not bool(row.get("weekly_pp", False)):
                continue
            idx = row.name
            base_len, base_depth, tight_3w = _compute_base_features(wdf, idx)
            ext_ma10 = _compute_ext_ma10(row)
            rs_score = row.get("rs_score", np.nan)
            rs_val = float(rs_score) if rs_score is not None and not (isinstance(rs_score, float) and np.isnan(rs_score)) else np.nan
            if isinstance(rs_val, (int, float)) and np.isnan(rs_val):
                rs_val = np.nan
            adtv20, adtv50 = eligibility.adtv(sym, cur_date)
            eligible_flag = eligibility.is_eligible(sym, cur_date)
            vol = row.get("volume", np.nan)
            vol_avg_10 = np.nan
            if idx >= 10 and "volume" in wdf.columns:
                vol_avg_10 = float(wdf["volume"].iloc[max(0, idx - 10) : idx].mean())
            vol_ratio = (float(vol) / vol_avg_10) if vol_avg_10 and vol_avg_10 > 0 and isinstance(vol, (int, float)) else np.nan
            candidates.append({
                "symbol": sym,
                "row": row,
                "idx": idx,
                "base_len": base_len,
                "base_depth": base_depth,
                "tight_3w": tight_3w,
                "ext_ma10": ext_ma10,
                "rs": rs_val,
                "adtv20": adtv20,
                "adtv50": adtv50,
                "eligible_flag": eligible_flag,
                "vol_ratio": vol_ratio,
            })

        def _rank_key_default(c: dict) -> tuple:
            rs = c["rs"]
            tight = c["tight_3w"]
            ext = c["ext_ma10"]
            adtv20 = c["adtv20"] if c["adtv20"] is not None else 0.0
            rs_sort = -rs if not (isinstance(rs, float) and np.isnan(rs)) else 0.0
            tight_sort = tight if not (isinstance(tight, float) and np.isnan(tight)) else 1e6
            ext_sort = ext if not (isinstance(ext, float) and np.isnan(ext)) else 1e6
            return (rs_sort, tight_sort, ext_sort, -adtv20)

        if regime_ftd and not no_new_positions:
            post_regime_candidates += len(candidates)

        if ranking_mode == "adtv20_only":
            candidates_sorted = sorted(
                candidates,
                key=lambda c: -(c["adtv20"] or 0.0),
            )
        elif ranking_mode == "tightness_only":
            # ascending: lower tightness first; NaN last
            candidates_sorted = sorted(
                candidates,
                key=lambda c: (c["tight_3w"] if isinstance(c["tight_3w"], (int, float)) and not np.isnan(c["tight_3w"]) else 1e6),
            )
        elif ranking_mode == "ext_only":
            # ascending: lower extension first; NaN last
            candidates_sorted = sorted(
                candidates,
                key=lambda c: (c["ext_ma10"] if isinstance(c["ext_ma10"], (int, float)) and not np.isnan(c["ext_ma10"]) else 1e6),
            )
        elif ranking_mode == "volume_thrust_first":
            # stronger weekly pivot thrust first (higher vol_ratio first); NaN last
            candidates_sorted = sorted(
                candidates,
                key=lambda c: -(c["vol_ratio"] if isinstance(c.get("vol_ratio"), (int, float)) and not np.isnan(c["vol_ratio"]) else -1e6),
            )
        elif ranking_mode == "simple_composite":
            # lower score = better: ext + tight - adtv20/1e12 (ascending)
            def _composite_score(c: dict) -> float:
                ext = c["ext_ma10"] if isinstance(c["ext_ma10"], (int, float)) and not np.isnan(c["ext_ma10"]) else 1e6
                tight = c["tight_3w"] if isinstance(c["tight_3w"], (int, float)) and not np.isnan(c["tight_3w"]) else 1e6
                adtv = c["adtv20"] if c["adtv20"] is not None else 0.0
                return ext + tight - (float(adtv) / 1e12)
            candidates_sorted = sorted(candidates, key=_composite_score)
        elif ranking_mode == "random":
            candidates_sorted = list(candidates)
            rng = random.Random(42)
            rng.shuffle(candidates_sorted)
        else:
            candidates_sorted = sorted(candidates, key=_rank_key_default)

        # --- 5) Entries in ranked order (regime gate, VND sizing, costs) ---
        for rank, c in enumerate(candidates_sorted, start=1):
            sym = c["symbol"]
            row = c["row"]
            idx = c["idx"]
            base_len = c["base_len"]
            base_depth = c["base_depth"]
            tight_3w = c["tight_3w"]
            ext_ma10 = c["ext_ma10"]
            rs_val = c["rs"]
            adtv20 = c["adtv20"]
            adtv50 = c["adtv50"]
            eligible_flag = c["eligible_flag"]

            chosen_flag = False
            reject_reason = ""

            if sym in positions:
                reject_reason = "already_open"
            elif not regime_ftd:
                reject_reason = "regime_off"
                skipped_regime_off += 1
            elif no_new_positions:
                reject_reason = "no_new_positions"
                skipped_no_new_positions += 1
            elif not eligible_flag or adtv20 is None or adtv50 is None:
                reject_reason = "ineligible"
                skipped_ineligible += 1
            elif len(positions) >= config.max_positions:
                reject_reason = "max_positions"
                skipped_max_positions += 1
                rejected_max_positions_count += 1
            elif free_heat_vnd <= 0:
                reject_reason = "no_heat"
                skipped_heat += 1
            elif getattr(config, "base_depth_pct_max", None) is not None and isinstance(base_depth, (int, float)) and not np.isnan(base_depth) and base_depth > config.base_depth_pct_max:
                reject_reason = "filter_base_depth"
            elif getattr(config, "tightness_3w_pct_max", None) is not None and isinstance(tight_3w, (int, float)) and not np.isnan(tight_3w) and tight_3w > config.tightness_3w_pct_max:
                reject_reason = "filter_tightness"
            elif getattr(config, "ext_vs_ma10_max", None) is not None and isinstance(ext_ma10, (int, float)) and not np.isnan(ext_ma10) and ext_ma10 > config.ext_vs_ma10_max:
                reject_reason = "filter_ext"
            else:
                next_idx = i + 1 + entry_delay
                next_dt = all_dates[next_idx] if next_idx < len(all_dates) else None
                if next_dt is None:
                    reject_reason = "no_next_bar"
                else:
                    wdf = weekly_dfs[sym]
                    next_row = wdf[wdf["date"].astype(str) == next_dt]
                    if next_row.empty:
                        reject_reason = "no_next_bar"
                    else:
                        entry_price_raw = float(next_row["open"].iloc[0])
                        entry_price = apply_costs(entry_price_raw, "buy", fee_mult, slip_mult)
                        if entry_price_raw <= 0 or entry_price <= 0:
                            reject_reason = "bad_entry_price"
                        else:
                            stop_price = _compute_stop_price(row)
                            stop_dist = (entry_price - stop_price) / entry_price
                            if stop_dist <= 0:
                                reject_reason = "invalid_stop"
                            else:
                                stop_dist = min(stop_dist, 0.10)
                                risk_budget_vnd = min(config.risk_per_trade * equity_vnd, free_heat_vnd)
                                if risk_budget_vnd <= 0:
                                    reject_reason = "no_heat"
                                    skipped_heat += 1
                                else:
                                    nominal_value_vnd = risk_budget_vnd / stop_dist
                                    nominal_value_vnd = min(nominal_value_vnd, config.max_symbol_weight * equity_vnd)
                                    max_by_liq_vnd = config.liquidity_participation_cap * adtv20 if adtv20 else 0.0
                                    if max_by_liq_vnd <= 0:
                                        reject_reason = "liquidity_cap"
                                        skipped_liquidity += 1
                                    else:
                                        nominal_value_vnd = min(nominal_value_vnd, max_by_liq_vnd)
                                        shares = int(nominal_value_vnd / entry_price)
                                        if shares <= 0:
                                            reject_reason = "liquidity_cap"
                                            skipped_liquidity += 1
                                        else:
                                            entry_value_vnd = shares * entry_price
                                            entry_fee_vnd = entry_value_vnd * fee_mult
                                            if cash_vnd < entry_value_vnd + entry_fee_vnd:
                                                reject_reason = "insufficient_cash"
                                            else:
                                                cash_vnd -= (entry_value_vnd + entry_fee_vnd)
                                                position_sizes_vnd.append(entry_value_vnd)
                                                positions[sym] = {
                                                    "entry_date": pd.to_datetime(next_dt),
                                                    "entry_price": entry_price,
                                                    "shares": shares,
                                                    "risk_budget": risk_budget_vnd,
                                                }
                                                free_heat_vnd -= risk_budget_vnd
                                                chosen_flag = True

            signal_log_rows.append({
                "symbol": sym,
                "entry_week": cur_date.strftime("%Y-%m-%d"),
                "candidate_rank": rank,
                "chosen_flag": chosen_flag,
                "reject_reason": reject_reason,
                "rs_score": rs_val if not (isinstance(rs_val, float) and np.isnan(rs_val)) else np.nan,
                "tightness_3w_pct": tight_3w,
                "ext_vs_ma10": ext_ma10,
                "adtv20": adtv20,
                "adtv50": adtv50,
                "base_length": base_len,
                "base_depth_pct": base_depth,
            })

        # --- 6) End-of-week equity (cash + MTM) ---
        position_value_vnd = 0.0
        for sym, pos in positions.items():
            wdf = weekly_dfs.get(sym)
            if wdf is None or wdf.empty:
                position_value_vnd += pos["entry_price"] * pos["shares"]
                continue
            row = wdf[wdf["date"].astype(str) == dt]
            if row.empty:
                position_value_vnd += pos["entry_price"] * pos["shares"]
            else:
                position_value_vnd += float(row.iloc[0]["close"]) * pos["shares"]
        equity_vnd = cash_vnd + position_value_vnd
        equity_path.append(equity_vnd)
        heat_path.append(sum(p["risk_budget"] for p in positions.values()))
        gross_exposure_path.append(position_value_vnd / equity_vnd if equity_vnd > 0 else 0.0)
        dates_path.append(cur_date)

    if signal_log_rows:
        pd.DataFrame(signal_log_rows).to_csv(_PP / "pp_portfolio_signal_log.csv", index=False)

    trades_df = pd.DataFrame(trades)
    actual_entries = len(trades_df)
    chosen_rate = actual_entries / post_regime_candidates if post_regime_candidates > 0 else np.nan
    if trades_df.empty:
        stats_empty = {
            "cagr": np.nan, "mdd": np.nan, "mar": np.nan, "n_trades": 0,
            "final_equity": config.initial_equity, "avg_heat": 0.0, "avg_gross_exposure": 0.0,
            "skipped_ineligible": skipped_ineligible, "skipped_heat": skipped_heat,
            "skipped_max_positions": skipped_max_positions, "skipped_liquidity": skipped_liquidity,
            "skipped_regime_off": skipped_regime_off, "skipped_no_new_positions": skipped_no_new_positions,
            "post_regime_candidates": post_regime_candidates, "actual_entries": actual_entries,
            "chosen_rate": chosen_rate, "rejected_max_positions": rejected_max_positions_count,
        }
        return trades_df, stats_empty

    eq = np.array(equity_path, dtype=float)
    dates_arr = np.array(dates_path)
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    mdd = float(dd.min())
    years = (dates_arr[-1] - dates_arr[0]).days / 365.25
    cagr = (eq[-1] / eq[0]) ** (1.0 / years) - 1.0 if years > 0 and eq[0] > 0 else np.nan
    mar = cagr / abs(mdd) if mdd < 0 else np.nan

    mean_equity = float(np.mean(eq)) if np.mean(eq) > 0 else 1.0
    mean_heat_vnd = float(np.mean(heat_path))
    avg_pos_vnd = float(np.mean(position_sizes_vnd)) if position_sizes_vnd else np.nan
    max_pos_vnd = float(np.max(position_sizes_vnd)) if position_sizes_vnd else np.nan
    stats = {
        "execution_mode": build_execution_audit(
            engine="pp_portfolio_sim",
            cfg=_exec,
            research_safe_default=_exec.entry_timing == FillTiming.NEXT_BAR_OPEN and _exec.exit_timing == FillTiming.NEXT_BAR_OPEN,
            notes="Weekly: signal at week t close -> fill at week t+1 open (default). Costs applied via ExecutionConfig.",
        ).to_dict(),
        "cagr": cagr,
        "mdd": mdd,
        "mar": mar,
        "n_trades": len(trades_df),
        "final_equity": float(eq[-1]),
        "avg_heat": mean_heat_vnd / mean_equity,
        "avg_gross_exposure": float(np.mean(gross_exposure_path)),
        "skipped_ineligible": skipped_ineligible,
        "skipped_heat": skipped_heat,
        "skipped_max_positions": skipped_max_positions,
        "skipped_liquidity": skipped_liquidity,
        "skipped_regime_off": skipped_regime_off,
        "skipped_no_new_positions": skipped_no_new_positions,
        "avg_position_size_vnd": avg_pos_vnd,
        "max_position_size_vnd": max_pos_vnd,
        "post_regime_candidates": post_regime_candidates,
        "actual_entries": len(trades_df),
        "chosen_rate": actual_entries / post_regime_candidates if post_regime_candidates > 0 else np.nan,
        "rejected_max_positions": rejected_max_positions_count,
    }
    return trades_df, stats
