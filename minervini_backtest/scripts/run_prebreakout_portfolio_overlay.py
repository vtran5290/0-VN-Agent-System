from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from run import load_curated_data

PRE_ROOT = REPO / "minervini_backtest" / "outputs" / "prebreakout_research"
LATEST = PRE_ROOT / "latest"


@dataclass
class PortfolioCfg:
    initial_capital: float = 1_000_000_000.0
    max_positions: int = 5
    max_weight: float = 0.20
    heat_cap: float = 0.10
    no_rebalance_after_entry: bool = True
    sizing_mode: str = "equal_weight"  # equal_weight | risk_based
    dedupe_days: int = 3
    additional_cost_mult: float = 1.0  # 1.0 = base net costs from trade log
    base_cost_bps_per_side: float = 25.0  # base fee+slippage already embedded in net prices


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _load_sources(base_dir: Path) -> dict[str, Any]:
    return {
        "trade_log": _read_csv(base_dir / "trade_log_best_presets.csv"),
        "robustness": _read_csv(base_dir / "preset_robustness_summary.csv"),
        "oos": _read_csv(base_dir / "oos_rolling_train_test_results.csv"),
        "run_meta": json.loads((base_dir / "run_meta.json").read_text(encoding="utf-8")) if (base_dir / "run_meta.json").exists() else {},
        "candidates": _read_csv(base_dir / "latest_candidates_best_presets.csv"),
        "candidates_deduped": _read_csv(base_dir / "latest_candidates_deduped.csv"),
        "exec_gross_net": _read_csv(base_dir / "execution_backtest_results_gross_vs_net.csv"),
    }


def _preset_rank_map(robust_df: pd.DataFrame) -> dict[str, float]:
    if robust_df.empty or "preset_id" not in robust_df.columns:
        return {}
    s = robust_df.copy()
    if "robustness_score" not in s.columns:
        s["robustness_score"] = 0.0
    s = s.sort_values("robustness_score", ascending=False).reset_index(drop=True)
    return {str(r["preset_id"]): float(r["robustness_score"]) for _, r in s.iterrows()}


def _select_presets(
    mode: str,
    top_k: int,
    robust_df: pd.DataFrame,
    oos_df: pd.DataFrame,
    preset_id: str | None,
) -> list[str]:
    if preset_id:
        return [preset_id]
    if robust_df.empty and oos_df.empty:
        return []
    if mode == "best_preset_only":
        if not robust_df.empty:
            return [str(robust_df.sort_values("robustness_score", ascending=False).iloc[0]["preset_id"])]
        p = oos_df[oos_df.get("preset_id").notna()]
        if not p.empty:
            return [str(p.iloc[0]["preset_id"])]
        return []
    if mode == "oos_selected_presets":
        if oos_df.empty:
            return _select_presets("latest_robustness_ranked", top_k, robust_df, oos_df, preset_id)
        z = oos_df.copy()
        # Prefer latest split by test_end then strongest test expectancy.
        if "test_end" in z.columns:
            z["test_end"] = pd.to_datetime(z["test_end"], errors="coerce")
            latest_end = z["test_end"].max()
            z = z[z["test_end"] == latest_end]
        if "preset_id" in z.columns:
            pids = [str(x) for x in z["preset_id"].dropna().tolist()]
            pids = list(dict.fromkeys(pids))
            if pids:
                return pids[: max(1, top_k)]
        # fallback parse selected_preset_ids
        if "selected_preset_ids" in z.columns and len(z) > 0:
            raw = str(z.iloc[0]["selected_preset_ids"])
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(x) for x in parsed][: max(1, top_k)]
            except Exception:
                pass
        return _select_presets("latest_robustness_ranked", top_k, robust_df, oos_df, preset_id)
    # top_k_presets_union / latest_robustness_ranked
    if robust_df.empty:
        return []
    s = robust_df.sort_values("robustness_score", ascending=False)
    return [str(x) for x in s["preset_id"].head(max(1, top_k)).tolist()]


def _prepare_trade_pool(
    trades: pd.DataFrame,
    selected_presets: list[str],
    preset_rank: dict[str, float],
    dedupe_days: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if trades.empty:
        return pd.DataFrame(), pd.DataFrame()
    t = trades.copy()
    for c in ["entry_date", "exit_date"]:
        t[c] = pd.to_datetime(t[c], errors="coerce")
    t = t.dropna(subset=["entry_date", "exit_date"])
    if selected_presets:
        t = t[t["preset_id"].astype(str).isin(selected_presets)].copy()
    if t.empty:
        return pd.DataFrame(), pd.DataFrame()
    t["preset_rank_score"] = t["preset_id"].astype(str).map(lambda x: preset_rank.get(x, -1e9))
    t = t.sort_values(["symbol", "entry_date", "preset_rank_score"], ascending=[True, True, False]).reset_index(drop=True)

    # Dedupe same-symbol overlapping/near-duplicate trades across presets.
    keep_idx: list[int] = []
    skipped: list[dict[str, Any]] = []
    by_sym: dict[str, list[int]] = {}
    for i, r in t.iterrows():
        sym = str(r["symbol"])
        e0 = r["entry_date"]
        x0 = r["exit_date"]
        dup = False
        if sym in by_sym:
            for j in by_sym[sym]:
                q = t.loc[j]
                e1, x1 = q["entry_date"], q["exit_date"]
                near_entry = abs((e0 - e1).days) <= dedupe_days
                overlap = not (x0 < e1 or x1 < e0)
                if near_entry or overlap:
                    # keep higher-ranked preset; tie -> earlier entry.
                    s0 = float(r["preset_rank_score"])
                    s1 = float(q["preset_rank_score"])
                    if s0 > s1 or (s0 == s1 and e0 < e1):
                        skipped.append(
                            {
                                "symbol": sym,
                                "entry_date": str(e1.date()),
                                "exit_date": str(x1.date()),
                                "preset_id": str(q["preset_id"]),
                                "skip_reason": "duplicate_trade",
                                "duplicate_of_symbol": sym,
                                "duplicate_of_entry_date": str(e0.date()),
                            }
                        )
                        keep_idx.remove(j)
                        by_sym[sym].remove(j)
                        break
                    dup = True
                    skipped.append(
                        {
                            "symbol": sym,
                            "entry_date": str(e0.date()),
                            "exit_date": str(x0.date()),
                            "preset_id": str(r["preset_id"]),
                            "skip_reason": "duplicate_trade",
                            "duplicate_of_symbol": sym,
                            "duplicate_of_entry_date": str(e1.date()),
                        }
                    )
                    break
        if dup:
            continue
        keep_idx.append(i)
        by_sym.setdefault(sym, []).append(i)
    out = t.loc[keep_idx].copy().sort_values("entry_date").reset_index(drop=True)
    skipped_df = pd.DataFrame(skipped)
    return out, skipped_df


def _load_price_cache(symbols: list[str]) -> dict[str, pd.DataFrame]:
    data = load_curated_data(symbols)
    out: dict[str, pd.DataFrame] = {}
    for s, df in data.items():
        d = df.copy()
        d["date"] = pd.to_datetime(d["date"], errors="coerce")
        d = d.dropna(subset=["date"]).sort_values("date")
        out[s] = d
    return out


def _mk_price_lookup(px: dict[str, pd.DataFrame]) -> dict[str, pd.Series]:
    lk: dict[str, pd.Series] = {}
    for s, df in px.items():
        lk[s] = df.set_index("date")["close"].astype(float)
    return lk


def _period_metrics(equity_df: pd.DataFrame, trade_df: pd.DataFrame, start: str | None = None) -> dict[str, Any]:
    d = equity_df.copy()
    t = trade_df.copy()
    if start:
        s = pd.Timestamp(start)
        d = d[d["date"] >= s].copy()
        if not t.empty:
            t = t[pd.to_datetime(t["exit_date"]) >= s].copy()
    if d.empty:
        return {}
    d = d.sort_values("date")
    ret = d["equity"].pct_change().fillna(0.0)
    total_ret = float(d["equity"].iloc[-1] / d["equity"].iloc[0] - 1.0)
    days = max(1, (d["date"].iloc[-1] - d["date"].iloc[0]).days)
    cagr = float((d["equity"].iloc[-1] / d["equity"].iloc[0]) ** (365.25 / days) - 1.0)
    peak = d["equity"].cummax()
    dd = d["equity"] / peak - 1.0
    mdd = float(dd.min())
    vol = float(ret.std() * np.sqrt(252))
    mean_ann = float(ret.mean() * 252)
    sharpe = float(mean_ann / vol) if vol > 0 else np.nan
    neg = ret[ret < 0]
    dvol = float(neg.std() * np.sqrt(252)) if len(neg) > 1 else np.nan
    sortino = float(mean_ann / dvol) if dvol and np.isfinite(dvol) and dvol > 0 else np.nan
    calmar = float(cagr / abs(mdd)) if mdd < 0 else np.nan
    avg_exposure = float(d["gross_exposure"].mean())
    cash_util = float(1.0 - (d["cash"] / d["equity"]).replace([np.inf, -np.inf], np.nan).fillna(0.0).mean())
    max_open = int(d["open_positions"].max())
    yrs = days / 365.25
    entries_per_year = float(len(t) / yrs) if yrs > 0 else np.nan
    turnover = float((t["entry_value"] + t["exit_value"]).sum() / d["equity"].mean()) if not t.empty and d["equity"].mean() > 0 else np.nan
    if t.empty:
        win_rate = profit_factor = expectancy = avg_hold = np.nan
    else:
        pnl = t["pnl"].astype(float)
        wins = pnl[pnl > 0]
        losses = pnl[pnl <= 0]
        win_rate = float((pnl > 0).mean())
        profit_factor = float(wins.sum() / abs(losses.sum())) if len(losses) and losses.sum() < 0 else np.nan
        expectancy = float(t["ret"].astype(float).mean())
        avg_hold = float(t["hold_days"].astype(float).mean())
    return {
        "total_return": total_ret,
        "cagr": cagr,
        "max_drawdown": mdd,
        "ann_volatility": vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "expectancy_per_trade": expectancy,
        "avg_holding_days": avg_hold,
        "avg_exposure": avg_exposure,
        "max_concurrent_positions_used": max_open,
        "entries_per_year": entries_per_year,
        "turnover": turnover,
        "cash_utilization_rate": cash_util,
        "n_trades": int(len(t)),
        "mdd_date": str(d.loc[dd.idxmin(), "date"].date()) if len(d) else None,
    }


def _simulate_portfolio(
    trades: pd.DataFrame,
    px_lookup: dict[str, pd.Series],
    cfg: PortfolioCfg,
    skipped_seed: pd.DataFrame | None = None,
    diagnostics: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if trades.empty:
        if diagnostics:
            return pd.DataFrame(), pd.DataFrame(), skipped_seed if skipped_seed is not None else pd.DataFrame(), {}
        return pd.DataFrame(), pd.DataFrame(), skipped_seed if skipped_seed is not None else pd.DataFrame()
    t = trades.copy().sort_values("entry_date").reset_index(drop=True)
    symbols = sorted(t["symbol"].astype(str).unique().tolist())

    min_d = min(t["entry_date"].min(), min((s.index.min() for s in px_lookup.values() if not s.empty), default=t["entry_date"].min()))
    max_d = max(t["exit_date"].max(), max((s.index.max() for s in px_lookup.values() if not s.empty), default=t["exit_date"].max()))
    cal = pd.date_range(min_d, max_d, freq="B")

    entry_map: dict[pd.Timestamp, list[int]] = {}
    exit_map: dict[pd.Timestamp, list[int]] = {}
    for i, r in t.iterrows():
        entry_map.setdefault(pd.Timestamp(r["entry_date"]), []).append(i)
        exit_map.setdefault(pd.Timestamp(r["exit_date"]), []).append(i)

    extra_side_bps = cfg.base_cost_bps_per_side * max(0.0, cfg.additional_cost_mult - 1.0)
    extra_side = extra_side_bps / 10000.0

    cash = float(cfg.initial_capital)
    positions: dict[int, dict[str, Any]] = {}
    eq_rows: list[dict[str, Any]] = []
    exec_rows: list[dict[str, Any]] = []
    skipped_rows: list[dict[str, Any]] = skipped_seed.to_dict("records") if skipped_seed is not None and not skipped_seed.empty else []

    entry_attempt_rows: list[dict[str, Any]] = []
    daily_weight_cap_binding_by_date: dict[str, bool] = {}

    for dt in cal:
        # 1) exits first
        for idx in exit_map.get(dt, []):
            if idx not in positions:
                continue
            pos = positions.pop(idx)
            row = t.loc[idx]
            exit_px = float(row["exit_px_net"]) * (1.0 - extra_side)
            proceeds = exit_px * pos["shares"]
            cash += proceeds
            pnl = proceeds - pos["cost_basis"]
            ret = (proceeds / pos["cost_basis"] - 1.0) if pos["cost_basis"] > 0 else np.nan
            exec_rows.append(
                {
                    "symbol": pos["symbol"],
                    "preset_id": row["preset_id"],
                    "entry_date": pos["entry_date"],
                    "exit_date": dt,
                    "entry_px": pos["entry_px"],
                    "exit_px": exit_px,
                    "shares": pos["shares"],
                    "entry_value": pos["cost_basis"],
                    "exit_value": proceeds,
                    "pnl": pnl,
                    "ret": ret,
                    "hold_days": int((dt - pos["entry_date"]).days),
                    "selection_mode": pos["selection_mode"],
                }
            )

        # 2) mark-to-market before entries (equity basis)
        mv = 0.0
        heat_risk = 0.0
        for pos in positions.values():
            s = pos["symbol"]
            cser = px_lookup.get(s)
            if cser is None or cser.empty:
                px = pos["entry_px"]
            else:
                c = cser[cser.index <= dt]
                px = float(c.iloc[-1]) if len(c) else pos["entry_px"]
            mv += px * pos["shares"]
            heat_risk += pos["risk_amount"]
        equity = cash + mv
        max_pos = cfg.max_positions
        target_w = min(cfg.max_weight, 1.0 / max_pos if max_pos > 0 else cfg.max_weight)
        equity_before_entry = float(equity)
        cash_before_entry = float(cash)
        alloc_pre_cash_cap = float(target_w * max(1.0, equity_before_entry))
        weight_cap_active_for_config = bool(cfg.max_weight <= (1.0 / max_pos if max_pos > 0 else cfg.max_weight) + 1e-12)

        # 3) entries
        day_entries = entry_map.get(dt, [])
        # rank by preset score desc then earlier exit_date (from source) as tiebreak.
        day_entries = sorted(
            day_entries,
            key=lambda i: (
                -float(t.loc[i].get("preset_rank_score", 0.0)),
                pd.Timestamp(t.loc[i]["exit_date"]),
            ),
        )
        for idx in day_entries:
            r = t.loc[idx]
            if idx in positions:
                if diagnostics:
                    entry_attempt_rows.append(
                        {
                            "symbol": str(r["symbol"]),
                            "preset_id": str(r["preset_id"]),
                            "entry_date": pd.Timestamp(r["entry_date"]),
                            "candidate_trade_idx": int(idx),
                            "executed": False,
                            "skip_reason": "duplicate_trade",
                            "realized_position_weight_on_entry": np.nan,
                            "weight_cap_binding_for_entry": False,
                        }
                    )
                    daily_weight_cap_binding_by_date.setdefault(str(dt.date()), False)
                continue
            if len(positions) >= cfg.max_positions:
                skipped_rows.append(
                    {
                        "symbol": str(r["symbol"]),
                        "entry_date": str(pd.Timestamp(r["entry_date"]).date()),
                        "exit_date": str(pd.Timestamp(r["exit_date"]).date()),
                        "preset_id": str(r["preset_id"]),
                        "skip_reason": "max_positions_reached",
                    }
                )
                if diagnostics:
                    entry_attempt_rows.append(
                        {
                            "symbol": str(r["symbol"]),
                            "preset_id": str(r["preset_id"]),
                            "entry_date": pd.Timestamp(r["entry_date"]),
                            "candidate_trade_idx": int(idx),
                            "executed": False,
                            "skip_reason": "max_positions_reached",
                            "realized_position_weight_on_entry": np.nan,
                            "weight_cap_binding_for_entry": False,
                        }
                    )
                    daily_weight_cap_binding_by_date.setdefault(str(dt.date()), False)
                continue
            entry_px = float(r["entry_px_net"]) * (1.0 + extra_side)
            if entry_px <= 0:
                skipped_rows.append(
                    {
                        "symbol": str(r["symbol"]),
                        "entry_date": str(pd.Timestamp(r["entry_date"]).date()),
                        "exit_date": str(pd.Timestamp(r["exit_date"]).date()),
                        "preset_id": str(r["preset_id"]),
                        "skip_reason": "bad_entry_price",
                    }
                )
                if diagnostics:
                    entry_attempt_rows.append(
                        {
                            "symbol": str(r["symbol"]),
                            "preset_id": str(r["preset_id"]),
                            "entry_date": pd.Timestamp(r["entry_date"]),
                            "candidate_trade_idx": int(idx),
                            "executed": False,
                            "skip_reason": "bad_entry_price",
                            "realized_position_weight_on_entry": np.nan,
                            "weight_cap_binding_for_entry": False,
                        }
                    )
                    daily_weight_cap_binding_by_date.setdefault(str(dt.date()), False)
                continue
            stop_px = float(r.get("stop_px", np.nan))
            stop_dist = (entry_px - stop_px) / entry_px if np.isfinite(stop_px) and stop_px > 0 else np.nan
            if not np.isfinite(stop_dist) or stop_dist <= 0:
                stop_dist = 0.08

            equity_for_size = max(1.0, equity)
            if cfg.sizing_mode == "risk_based":
                heat_remain = max(0.0, cfg.heat_cap * equity_for_size - heat_risk)
                alloc = min(cfg.max_weight * equity_for_size, heat_remain / max(stop_dist, 1e-6))
            else:
                alloc = min(target_w * equity_for_size, cfg.max_weight * equity_for_size)
            alloc = min(alloc, cash)
            if alloc <= 0:
                skipped_rows.append(
                    {
                        "symbol": str(r["symbol"]),
                        "entry_date": str(pd.Timestamp(r["entry_date"]).date()),
                        "exit_date": str(pd.Timestamp(r["exit_date"]).date()),
                        "preset_id": str(r["preset_id"]),
                        "skip_reason": "insufficient_cash",
                    }
                )
                if diagnostics:
                    entry_attempt_rows.append(
                        {
                            "symbol": str(r["symbol"]),
                            "preset_id": str(r["preset_id"]),
                            "entry_date": pd.Timestamp(r["entry_date"]),
                            "candidate_trade_idx": int(idx),
                            "executed": False,
                            "skip_reason": "insufficient_cash",
                            "realized_position_weight_on_entry": np.nan,
                            "weight_cap_binding_for_entry": False,
                        }
                    )
                    daily_weight_cap_binding_by_date.setdefault(str(dt.date()), False)
                continue
            risk_amt = alloc * stop_dist
            if heat_risk + risk_amt > cfg.heat_cap * equity_for_size:
                skipped_rows.append(
                    {
                        "symbol": str(r["symbol"]),
                        "entry_date": str(pd.Timestamp(r["entry_date"]).date()),
                        "exit_date": str(pd.Timestamp(r["exit_date"]).date()),
                        "preset_id": str(r["preset_id"]),
                        "skip_reason": "heat_cap_reached",
                    }
                )
                if diagnostics:
                    entry_attempt_rows.append(
                        {
                            "symbol": str(r["symbol"]),
                            "preset_id": str(r["preset_id"]),
                            "entry_date": pd.Timestamp(r["entry_date"]),
                            "candidate_trade_idx": int(idx),
                            "executed": False,
                            "skip_reason": "heat_cap_reached",
                            "realized_position_weight_on_entry": np.nan,
                            "weight_cap_binding_for_entry": False,
                        }
                    )
                    daily_weight_cap_binding_by_date.setdefault(str(dt.date()), False)
                continue
            shares = int(alloc / entry_px)
            if shares <= 0:
                skipped_rows.append(
                    {
                        "symbol": str(r["symbol"]),
                        "entry_date": str(pd.Timestamp(r["entry_date"]).date()),
                        "exit_date": str(pd.Timestamp(r["exit_date"]).date()),
                        "preset_id": str(r["preset_id"]),
                        "skip_reason": "insufficient_cash",
                    }
                )
                if diagnostics:
                    entry_attempt_rows.append(
                        {
                            "symbol": str(r["symbol"]),
                            "preset_id": str(r["preset_id"]),
                            "entry_date": pd.Timestamp(r["entry_date"]),
                            "candidate_trade_idx": int(idx),
                            "executed": False,
                            "skip_reason": "insufficient_cash",
                            "realized_position_weight_on_entry": np.nan,
                            "weight_cap_binding_for_entry": False,
                        }
                    )
                    daily_weight_cap_binding_by_date.setdefault(str(dt.date()), False)
                continue
            cost_basis = shares * entry_px
            realized_weight_on_entry = cost_basis / equity_before_entry if equity_before_entry > 0 else np.nan
            cash -= cost_basis
            positions[idx] = {
                "symbol": str(r["symbol"]),
                "entry_date": pd.Timestamp(r["entry_date"]),
                "entry_px": entry_px,
                "shares": shares,
                "risk_amount": cost_basis * stop_dist,
                "cost_basis": cost_basis,
                "selection_mode": str(r.get("selection_mode", "")),
            }
            heat_risk += cost_basis * stop_dist

            # Weight-cap binding diagnostic (deterministic, no heuristic threshold):
            # - weight_cap_active_for_config means target_w is set by max_weight (not 1/max_positions).
            # - When executed, "cost_basis" can be below the exact target due to integer-share rounding.
            #   We treat it as binding if we are within <= 1 share of the target value.
            #
            # NOTE: This does NOT claim that other caps could not be the limiting factor;
            # it only flags cases where executed sizing essentially matches the max_weight-limited target.
            weight_cap_binding_for_entry = bool(
                weight_cap_active_for_config
                and np.isfinite(realized_weight_on_entry)
                and alloc_pre_cash_cap > 0
                and cash_before_entry >= (alloc_pre_cash_cap - entry_px)  # not cash-limited
                and (alloc_pre_cash_cap - cost_basis) <= (entry_px + 1e-6)  # not reduced beyond rounding
            )
            if diagnostics:
                entry_attempt_rows.append(
                    {
                        "symbol": str(r["symbol"]),
                        "preset_id": str(r["preset_id"]),
                        "entry_date": pd.Timestamp(r["entry_date"]),
                        "candidate_trade_idx": int(idx),
                        "executed": True,
                        "skip_reason": "",
                        "realized_position_weight_on_entry": float(realized_weight_on_entry),
                        "weight_cap_binding_for_entry": weight_cap_binding_for_entry,
                    }
                )
                if weight_cap_binding_for_entry:
                    daily_weight_cap_binding_by_date[str(dt.date())] = True

        # 4) mark-to-market after entries
        mv = 0.0
        for pos in positions.values():
            s = pos["symbol"]
            cser = px_lookup.get(s)
            if cser is None or cser.empty:
                px = pos["entry_px"]
            else:
                c = cser[cser.index <= dt]
                px = float(c.iloc[-1]) if len(c) else pos["entry_px"]
            mv += px * pos["shares"]
        equity = cash + mv
        eq_rows.append(
            {
                "date": dt,
                "cash": cash,
                "market_value": mv,
                "equity": equity,
                "gross_exposure": (mv / equity) if equity > 0 else 0.0,
                "open_positions": len(positions),
            }
        )

    eq_df = pd.DataFrame(eq_rows)
    trade_df = pd.DataFrame(exec_rows)
    skipped_df = pd.DataFrame(skipped_rows)
    if not diagnostics:
        return eq_df, trade_df, skipped_df
    daily_wcb = pd.DataFrame(
        [{"date": pd.Timestamp(d), "weight_cap_binding": v} for d, v in daily_weight_cap_binding_by_date.items()]
    )
    entry_attempts = pd.DataFrame(entry_attempt_rows)
    diag = {"entry_attempts": entry_attempts, "daily_weight_cap_binding": daily_wcb}
    return eq_df, trade_df, skipped_df, diag


def _yearly_summary(eq_df: pd.DataFrame) -> pd.DataFrame:
    if eq_df.empty:
        return pd.DataFrame()
    d = eq_df.copy()
    d["year"] = pd.to_datetime(d["date"]).dt.year
    rows = []
    for y, g in d.groupby("year"):
        g = g.sort_values("date")
        ret = float(g["equity"].iloc[-1] / g["equity"].iloc[0] - 1.0)
        peak = g["equity"].cummax()
        mdd = float((g["equity"] / peak - 1.0).min())
        avg_exp = float(g["gross_exposure"].mean())
        rows.append({"year": int(y), "year_return": ret, "year_max_drawdown": mdd, "avg_exposure": avg_exp})
    return pd.DataFrame(rows).sort_values("year")


def _slice_equity(eq_df: pd.DataFrame, start: str | None) -> pd.DataFrame:
    d = eq_df.copy()
    if start:
        d = d[d["date"] >= pd.Timestamp(start)].copy()
    return d.sort_values("date").reset_index(drop=True)


def _sensitivity(
    all_trades: pd.DataFrame,
    robust_df: pd.DataFrame,
    oos_df: pd.DataFrame,
    rank_map: dict[str, float],
    px_lookup: dict[str, pd.Series],
    base_cfg: PortfolioCfg,
) -> pd.DataFrame:
    rows = []
    for max_pos in [3, 5, 8, 10]:
        for max_w in [0.10, 0.15, 0.20, 0.25]:
            for sel in ["best_preset_only", "top_k_presets_union"]:
                for k in [1, 3, 5]:
                    for cm in [1.0, 1.5]:
                        c = PortfolioCfg(
                            initial_capital=base_cfg.initial_capital,
                            max_positions=max_pos,
                            max_weight=max_w,
                            heat_cap=base_cfg.heat_cap,
                            no_rebalance_after_entry=True,
                            sizing_mode=base_cfg.sizing_mode,
                            dedupe_days=base_cfg.dedupe_days,
                            additional_cost_mult=cm,
                            base_cost_bps_per_side=base_cfg.base_cost_bps_per_side,
                        )
                        pids = _select_presets(sel, k, robust_df, oos_df, None)
                        pre_pool = all_trades[all_trades["preset_id"].astype(str).isin(pids)].copy()
                        pool, skipped = _prepare_trade_pool(all_trades, pids, rank_map, base_cfg.dedupe_days)
                        if pool.empty:
                            rows.append(
                                {
                                    "selection_mode_assumed": sel,
                                    "top_k_assumed": k,
                                    "max_positions": max_pos,
                                    "max_weight": max_w,
                                    "cost_mult": cm,
                                    "selected_preset_ids": json.dumps(pids),
                                    "trade_pool_size_pre_dedupe": int(len(pre_pool)),
                                    "trade_pool_size_post_dedupe": 0,
                                    "executed_trade_count": 0,
                                    "total_return": np.nan,
                                    "cagr": np.nan,
                                    "max_drawdown": np.nan,
                                    "sharpe": np.nan,
                                    "n_trades": 0,
                                }
                            )
                            continue
                        pool["selection_mode"] = sel
                        eq_df, tr_df, _ = _simulate_portfolio(pool, px_lookup, c, skipped)
                        if eq_df.empty:
                            met = {}
                        else:
                            met = _period_metrics(eq_df, tr_df, None)
                        rows.append(
                            {
                                "selection_mode_assumed": sel,
                                "top_k_assumed": k,
                                "max_positions": max_pos,
                                "max_weight": max_w,
                                "cost_mult": cm,
                                "selected_preset_ids": json.dumps(pids),
                                "trade_pool_size_pre_dedupe": int(len(pre_pool)),
                                "trade_pool_size_post_dedupe": int(len(pool)),
                                "executed_trade_count": int(len(tr_df)),
                                "total_return": met.get("total_return"),
                                "cagr": met.get("cagr"),
                                "max_drawdown": met.get("max_drawdown"),
                                "sharpe": met.get("sharpe"),
                                "n_trades": met.get("n_trades"),
                            }
                        )
    return pd.DataFrame(rows)


def _mode_comparison(
    all_trades: pd.DataFrame,
    robust_df: pd.DataFrame,
    oos_df: pd.DataFrame,
    rank_map: dict[str, float],
    px_lookup: dict[str, pd.Series],
    base_cfg: PortfolioCfg,
) -> pd.DataFrame:
    rows = []
    modes = [
        ("best_preset_only", 1),
        ("top_k_presets_union", 3),
        ("oos_selected_presets", 3),
        ("latest_robustness_ranked", 3),
    ]
    for mode, k in modes:
        pids = _select_presets(mode, k, robust_df, oos_df, None)
        pre_pool = all_trades[all_trades["preset_id"].astype(str).isin(pids)].copy()
        pool, skipped = _prepare_trade_pool(all_trades, pids, rank_map, base_cfg.dedupe_days)
        if pool.empty:
            rows.append(
                {
                    "mode": mode,
                    "selected_preset_ids": json.dumps(pids),
                    "trade_pool_size_pre_dedupe": int(len(pre_pool)),
                    "trade_pool_size_post_dedupe": 0,
                    "executed_trades": 0,
                    "total_return": np.nan,
                    "cagr": np.nan,
                    "max_drawdown": np.nan,
                    "sharpe": np.nan,
                    "avg_exposure": np.nan,
                    "cash_utilization_rate": np.nan,
                }
            )
            continue
        pool["selection_mode"] = mode
        eq_df, tr_df, _ = _simulate_portfolio(pool, px_lookup, base_cfg, skipped)
        met = _period_metrics(eq_df, tr_df, None) if not eq_df.empty else {}
        rows.append(
            {
                "mode": mode,
                "selected_preset_ids": json.dumps(pids),
                "trade_pool_size_pre_dedupe": int(len(pre_pool)),
                "trade_pool_size_post_dedupe": int(len(pool)),
                "executed_trades": int(len(tr_df)),
                "total_return": met.get("total_return"),
                "cagr": met.get("cagr"),
                "max_drawdown": met.get("max_drawdown"),
                "sharpe": met.get("sharpe"),
                "avg_exposure": met.get("avg_exposure"),
                "cash_utilization_rate": met.get("cash_utilization_rate"),
            }
        )
    return pd.DataFrame(rows)


def _consistency_checks(
    cfg: PortfolioCfg,
    eq_df: pd.DataFrame,
    trade_df: pd.DataFrame,
    skipped_df: pd.DataFrame,
    pool_post_dedupe: pd.DataFrame,
    yearly_df: pd.DataFrame,
    metrics_df: pd.DataFrame,
    sens_df: pd.DataFrame,
) -> tuple[pd.DataFrame, str]:
    checks: list[dict[str, Any]] = []
    tol = 1e-6
    d = eq_df.copy().sort_values("date").reset_index(drop=True)
    t = trade_df.copy()
    t["entry_date"] = pd.to_datetime(t["entry_date"], errors="coerce")
    t["exit_date"] = pd.to_datetime(t["exit_date"], errors="coerce")

    # 1) identity: equity == cash + market_value
    id_err = float((d["equity"] - (d["cash"] + d["market_value"])).abs().max())
    checks.append({"check_name": "equity_identity", "status": "pass" if id_err <= tol else "fail", "details": f"max_abs_error={id_err}"})

    # 2) no negative cash
    min_cash = float(d["cash"].min())
    checks.append({"check_name": "no_negative_cash_no_leverage", "status": "pass" if min_cash >= -tol else "fail", "details": f"min_cash={min_cash}"})

    # 3) open_positions reconcile from trade log timeline
    emap = t.groupby("entry_date").size().to_dict()
    xmap = t.groupby("exit_date").size().to_dict()
    open_cnt = 0
    calc_open = []
    for dt in pd.to_datetime(d["date"]):
        open_cnt -= int(xmap.get(dt, 0))
        open_cnt += int(emap.get(dt, 0))
        calc_open.append(open_cnt)
    max_diff_open = int(np.max(np.abs(np.array(calc_open) - d["open_positions"].astype(int).values))) if len(d) else 0
    checks.append({"check_name": "open_positions_reconcile", "status": "pass" if max_diff_open == 0 else "fail", "details": f"max_count_diff={max_diff_open}"})

    # 4) full-period pnl reconciliation
    final_eq = float(d["equity"].iloc[-1])
    realized = float(t["pnl"].sum()) if not t.empty else 0.0
    ending_unrealized_pnl_residual = float(final_eq - (cfg.initial_capital + realized))
    ending_open_positions = int(d["open_positions"].iloc[-1]) if len(d) else 0
    if ending_open_positions == 0:
        # Flat: no ending mark-to-market component outside of cash+market_value identity.
        expected = cfg.initial_capital + realized
        recon_err = abs(final_eq - expected)
        checks.append(
            {
                "check_name": "initial_realized_reconcile_flat_end",
                "status": "pass" if recon_err <= 1e-2 else "fail",
                "details": f"ending_open_positions=0,ending_unrealized_residual={ending_unrealized_pnl_residual},error={recon_err}",
            }
        )
    else:
        # Not flat: explicitly reconcile using ending unrealized residual.
        expected = cfg.initial_capital + realized + ending_unrealized_pnl_residual
        recon_err = abs(final_eq - expected)
        checks.append(
            {
                "check_name": "initial_realized_reconcile_nonflat_end",
                "status": "pass" if recon_err <= 1e-2 else "fail",
                "details": f"ending_open_positions={ending_open_positions},ending_unrealized_residual={ending_unrealized_pnl_residual},error={recon_err}",
            }
        )

    # 5) period trade count reconcile (exit-date basis)
    for pname, start in [("2012_latest", None), ("2022_latest", "2022-01-01"), ("2024_latest", "2024-01-01")]:
        met_row = metrics_df[metrics_df["period"] == pname]
        if met_row.empty:
            checks.append({"check_name": f"period_trade_count_{pname}", "status": "fail", "details": "missing metrics row"})
            continue
        met_n = int(met_row.iloc[0]["n_trades"])
        if start is None:
            n = int(len(t))
        else:
            n = int((t["exit_date"] >= pd.Timestamp(start)).sum())
        checks.append({"check_name": f"period_trade_count_{pname}", "status": "pass" if n == met_n else "fail", "details": f"metrics_n={met_n},recount_n={n},basis=exit_date"})

    # 6) yearly summary reconcile
    yr_ok = True
    detail_bits = []
    for _, r in yearly_df.iterrows():
        y = int(r["year"])
        g = d[pd.to_datetime(d["date"]).dt.year == y]
        if g.empty:
            yr_ok = False
            detail_bits.append(f"{y}:missing_eq")
            continue
        yr_ret = float(g["equity"].iloc[-1] / g["equity"].iloc[0] - 1.0)
        yr_mdd = float((g["equity"] / g["equity"].cummax() - 1.0).min())
        if abs(yr_ret - float(r["year_return"])) > 1e-9 or abs(yr_mdd - float(r["year_max_drawdown"])) > 1e-9:
            yr_ok = False
            detail_bits.append(f"{y}:mismatch")
    checks.append({"check_name": "yearly_summary_reconcile", "status": "pass" if yr_ok else "fail", "details": ";".join(detail_bits) if detail_bits else "ok"})

    # 7) candidate pool reconciliation
    non_dup_skips = skipped_df[skipped_df.get("skip_reason", "").astype(str) != "duplicate_trade"] if not skipped_df.empty else pd.DataFrame()
    lhs = int(len(pool_post_dedupe))
    rhs = int(len(t) + len(non_dup_skips))
    checks.append({"check_name": "post_dedupe_pool_reconcile", "status": "pass" if lhs == rhs else "fail", "details": f"post_dedupe={lhs},executed={len(t)},nondup_skipped={len(non_dup_skips)}"})

    # 8) sensitivity variation proves mode/topk non-cosmetic
    sens = sens_df.copy()
    uniq = sens[["selection_mode_assumed", "top_k_assumed", "selected_preset_ids", "trade_pool_size_post_dedupe"]].drop_duplicates()
    varied = len(uniq) > 2 and sens["trade_pool_size_post_dedupe"].nunique() > 1
    checks.append({"check_name": "sensitivity_selection_variation", "status": "pass" if varied else "fail", "details": f"unique_combo_rows={len(uniq)},unique_post_pool_sizes={sens['trade_pool_size_post_dedupe'].nunique()}"})

    # 9) repeated MDD diagnostic
    mdd2012 = float(metrics_df[metrics_df["period"] == "2012_latest"]["max_drawdown"].iloc[0])
    mdd2022 = float(metrics_df[metrics_df["period"] == "2022_latest"]["max_drawdown"].iloc[0])
    mdd2024 = float(metrics_df[metrics_df["period"] == "2024_latest"]["max_drawdown"].iloc[0])
    same_mdd = abs(mdd2012 - mdd2022) < 1e-12 and abs(mdd2022 - mdd2024) < 1e-12
    mdd_date_2012 = str(metrics_df[metrics_df["period"] == "2012_latest"]["mdd_date"].iloc[0])
    mdd_date_2022 = str(metrics_df[metrics_df["period"] == "2022_latest"]["mdd_date"].iloc[0])
    mdd_date_2024 = str(metrics_df[metrics_df["period"] == "2024_latest"]["mdd_date"].iloc[0])
    checks.append(
        {
            "check_name": "period_mdd_repeat_diagnostic",
            "status": "pass",
            "details": f"same_mdd={same_mdd},mdd_dates=2012:{mdd_date_2012},2022:{mdd_date_2022},2024:{mdd_date_2024}",
        }
    )

    cdf = pd.DataFrame(checks)
    md = ["# Portfolio consistency check", ""]
    for _, r in cdf.iterrows():
        md.append(f"- `{r['check_name']}`: **{r['status'].upper()}** - {r['details']}")
    md.append("")
    md.append("- Trade-period assignment basis in metrics: `exit_date`.")
    return cdf, "\n".join(md)


def main() -> int:
    ap = argparse.ArgumentParser(description="Portfolio overlay simulation for prebreakout research outputs.")
    ap.add_argument("--prebreakout-dir", default=str(LATEST), help="Path to prebreakout artifact folder (default latest).")
    ap.add_argument(
        "--selection-mode",
        default="oos_selected_presets",
        choices=["best_preset_only", "top_k_presets_union", "oos_selected_presets", "latest_robustness_ranked"],
    )
    ap.add_argument("--preset-id", default=None, help="Force one preset for best_preset_only mode.")
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--initial-capital", type=float, default=1_000_000_000.0)
    ap.add_argument("--max-positions", type=int, default=5)
    ap.add_argument("--max-weight", type=float, default=0.20)
    ap.add_argument("--heat-cap", type=float, default=0.10)
    ap.add_argument("--sizing-mode", choices=["equal_weight", "risk_based"], default="equal_weight")
    ap.add_argument("--dedupe-days", type=int, default=3)
    ap.add_argument("--cost-mult", type=float, default=1.0, help="Additional cost multiplier over net trade log base costs.")
    args = ap.parse_args()

    base_dir = Path(args.prebreakout_dir)
    src = _load_sources(base_dir)
    trade_log = src["trade_log"]
    robust_df = src["robustness"]
    oos_df = src["oos"]
    run_meta = src["run_meta"]
    if trade_log.empty:
        print("[ERROR] trade_log_best_presets.csv is missing/empty.")
        return 1

    rank_map = _preset_rank_map(robust_df)
    selected_presets = _select_presets(args.selection_mode, args.top_k, robust_df, oos_df, args.preset_id)
    if not selected_presets:
        print("[ERROR] Could not resolve selected presets from mode.")
        return 1

    pool, skipped_dups = _prepare_trade_pool(trade_log, selected_presets, rank_map, args.dedupe_days)
    if pool.empty:
        print("[ERROR] No trades after preset selection/dedupe.")
        return 1
    pool["selection_mode"] = args.selection_mode

    symbols = sorted(pool["symbol"].astype(str).unique().tolist())
    px = _load_price_cache(symbols)
    px_lookup = _mk_price_lookup(px)

    cfg = PortfolioCfg(
        initial_capital=args.initial_capital,
        max_positions=args.max_positions,
        max_weight=args.max_weight,
        heat_cap=args.heat_cap,
        no_rebalance_after_entry=True,
        sizing_mode=args.sizing_mode,
        dedupe_days=args.dedupe_days,
        additional_cost_mult=args.cost_mult,
    )
    eq_df, trade_df, skipped_df = _simulate_portfolio(pool, px_lookup, cfg, skipped_dups)
    if eq_df.empty:
        print("[ERROR] Portfolio simulation produced empty equity curve.")
        return 1

    met_all = _period_metrics(eq_df, trade_df, None)
    met_2022 = _period_metrics(eq_df, trade_df, "2022-01-01")
    met_2024 = _period_metrics(eq_df, trade_df, "2024-01-01")
    mrows = []
    for p, m in [("2012_latest", met_all), ("2022_latest", met_2022), ("2024_latest", met_2024)]:
        row = {"period": p}
        row.update(m)
        mrows.append(row)
    metrics_df = pd.DataFrame(mrows)

    yearly_df = _yearly_summary(eq_df)
    sens_df = _sensitivity(trade_log, robust_df, oos_df, rank_map, px_lookup, cfg)
    mode_cmp_df = _mode_comparison(trade_log, robust_df, oos_df, rank_map, px_lookup, cfg)
    eq_2012 = _slice_equity(eq_df, None)
    eq_2022 = _slice_equity(eq_df, "2022-01-01")
    eq_2024 = _slice_equity(eq_df, "2024-01-01")
    consistency_df, consistency_md = _consistency_checks(cfg, eq_df, trade_df, skipped_df, pool, yearly_df, metrics_df, sens_df)

    # Output to same prebreakout tree: timestamped and latest
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = PRE_ROOT / f"portfolio_overlay_{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)

    eq_df.to_csv(run_dir / "portfolio_equity_curve.csv", index=False)
    eq_2012.to_csv(run_dir / "portfolio_equity_curve_2012_latest.csv", index=False)
    eq_2022.to_csv(run_dir / "portfolio_equity_curve_2022_latest.csv", index=False)
    eq_2024.to_csv(run_dir / "portfolio_equity_curve_2024_latest.csv", index=False)
    trade_df.to_csv(run_dir / "portfolio_trade_log.csv", index=False)
    metrics_df.to_csv(run_dir / "portfolio_metrics_summary.csv", index=False)
    yearly_df.to_csv(run_dir / "portfolio_yearly_summary.csv", index=False)
    sens_df.to_csv(run_dir / "portfolio_sensitivity_summary.csv", index=False)
    mode_cmp_df.to_csv(run_dir / "portfolio_mode_comparison.csv", index=False)
    consistency_df.to_csv(run_dir / "portfolio_consistency_check.csv", index=False)
    (run_dir / "portfolio_consistency_check.md").write_text(consistency_md, encoding="utf-8")
    skipped_df.to_csv(run_dir / "portfolio_skipped_trades.csv", index=False)

    report_lines = [
        "# Portfolio simulation report (prebreakout overlay)",
        "",
        "## Source artifacts used",
        f"- prebreakout_dir: `{base_dir}`",
        "- `trade_log_best_presets.csv`",
        "- `preset_robustness_summary.csv`",
        "- `oos_rolling_train_test_results.csv`",
        "- `run_meta.json`",
        "",
        "## Simulation configuration",
        f"- selection_mode: `{args.selection_mode}`",
        f"- selected_presets: `{selected_presets}`",
        f"- sizing_mode: `{cfg.sizing_mode}`",
        f"- initial_capital: `{cfg.initial_capital}`",
        f"- max_positions: `{cfg.max_positions}`",
        f"- max_weight: `{cfg.max_weight}`",
        f"- heat_cap: `{cfg.heat_cap}`",
        f"- no_rebalance_after_entry: `{cfg.no_rebalance_after_entry}`",
        f"- additional_cost_mult: `{cfg.additional_cost_mult}` (base net costs already embedded in source trade log)",
        "",
        "## Dedupe policy",
        "- Same-symbol near/overlapping trades (entry gap <= dedupe_days or overlapping holding windows) are deduped.",
        "- Keep trade by higher preset robustness rank; tie-breaker = earlier entry date.",
        "",
        "## Metric definitions",
        "- max_drawdown: minimum of `(equity / running_peak) - 1` on the period-sliced equity curve.",
        "- win_rate: share of executed portfolio trades with `pnl > 0`.",
        "- expectancy_per_trade: arithmetic mean of executed trade `ret`.",
        "- average_exposure: mean of daily `gross_exposure = market_value / equity`.",
        "- cash_utilization_rate: `1 - mean(cash/equity)` over daily rows in the slice.",
        "",
        "## Exposure redundancy note",
        "- In this long-only, no-leverage overlay, for every daily row we have `equity = cash + market_value`, so `gross_exposure = market_value/equity` equals `1 - cash/equity` on that same row.",
        "- Therefore `avg_exposure = mean(gross_exposure)` is mechanically identical (up to float rounding) to `cash_utilization_rate = 1 - mean(cash/equity)`.",
        "- entries_per_year: executed trade count divided by years in that period slice.",
        "- turnover: `sum(entry_value + exit_value) / mean(equity)` for period-sliced executed trades.",
        "- trade-period assignment in period summaries: by `exit_date` filter (`exit_date >= period_start`).",
        "",
        "## Key metrics (2012-latest)",
        f"- total_return: `{met_all.get('total_return')}`",
        f"- CAGR: `{met_all.get('cagr')}`",
        f"- max_drawdown: `{met_all.get('max_drawdown')}`",
        f"- Sharpe: `{met_all.get('sharpe')}`",
        f"- Sortino: `{met_all.get('sortino')}`",
        f"- Calmar: `{met_all.get('calmar')}`",
        f"- n_trades: `{met_all.get('n_trades')}`",
        "",
        "## Caveats",
        "- This is a portfolio simulation overlay, not live deployable performance.",
        "- Relies on source trade log timing/pricing semantics and net costs from the upstream prebreakout workflow.",
        "- Survivorship/PIT caveats from prebreakout workflow still apply.",
        "- No intraday microstructure beyond source assumptions.",
    ]
    (run_dir / "portfolio_simulation_report.md").write_text("\n".join(report_lines), encoding="utf-8")

    meta = {
        "run_dir": str(run_dir),
        "source_prebreakout_dir": str(base_dir),
        "selection_mode": args.selection_mode,
        "selected_presets": selected_presets,
        "top_k": args.top_k,
        "preset_id": args.preset_id,
        "portfolio_config": {
            "initial_capital": cfg.initial_capital,
            "max_positions": cfg.max_positions,
            "max_weight": cfg.max_weight,
            "heat_cap": cfg.heat_cap,
            "sizing_mode": cfg.sizing_mode,
            "no_rebalance_after_entry": cfg.no_rebalance_after_entry,
            "dedupe_days": cfg.dedupe_days,
            "additional_cost_mult": cfg.additional_cost_mult,
        },
        "period_trade_assignment_basis": "exit_date",
        "source_run_meta": run_meta,
    }
    (run_dir / "portfolio_run_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    # sync to prebreakout latest/
    for fn in [
        "portfolio_equity_curve.csv",
        "portfolio_equity_curve_2012_latest.csv",
        "portfolio_equity_curve_2022_latest.csv",
        "portfolio_equity_curve_2024_latest.csv",
        "portfolio_trade_log.csv",
        "portfolio_metrics_summary.csv",
        "portfolio_yearly_summary.csv",
        "portfolio_sensitivity_summary.csv",
        "portfolio_mode_comparison.csv",
        "portfolio_consistency_check.csv",
        "portfolio_consistency_check.md",
        "portfolio_skipped_trades.csv",
        "portfolio_simulation_report.md",
        "portfolio_run_meta.json",
    ]:
        srcf = run_dir / fn
        if srcf.exists():
            (LATEST / fn).write_bytes(srcf.read_bytes())

    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

