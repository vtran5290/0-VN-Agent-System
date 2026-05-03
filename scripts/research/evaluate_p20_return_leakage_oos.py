#!/usr/bin/env python3
"""p20 return-leakage / OOS evaluation. For Vingroup + robustness policy on related research, see
`docs/research/VIN_EMA_CLOUD_BASELINE.md` (full vs ex-VIN reporting, VPL history, VNINDEX caveat).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.data.fireant_client import get_client  # noqa: E402


REQUIRED_COLS = ["date", "symbol", "p20", "label_wave20", "fwd_ret20", "fwd_mdd20"]


@dataclass
class TradeResult:
    trades: pd.DataFrame
    summary: dict[str, Any]


def _safe_mean(x: pd.Series) -> float:
    x = pd.to_numeric(x, errors="coerce")
    return float(x.mean()) if x.notna().any() else np.nan


def _payoff_ratio(ret: pd.Series) -> float:
    ret = pd.to_numeric(ret, errors="coerce")
    wins = ret[ret > 0]
    losses = ret[ret <= 0]
    if len(wins) == 0 or len(losses) == 0:
        return np.nan
    lm = float(losses.mean())
    if lm == 0:
        return np.nan
    return float(wins.mean() / abs(lm))


def _turnover_proxy(x: pd.DataFrame, top_n: int) -> float:
    if x.empty:
        return np.nan
    prev: set[str] = set()
    vals: list[float] = []
    for _, g in x.groupby("signal_date"):
        cur = set(g["symbol"].astype(str).tolist())
        if prev:
            vals.append(1.0 - len(cur & prev) / max(top_n, 1))
        prev = cur
    return float(np.mean(vals)) if vals else np.nan


def _portfolio_max_drawdown(monthly_ret: pd.Series) -> float:
    if monthly_ret.empty:
        return np.nan
    eq = (1.0 + monthly_ret.fillna(0.0)).cumprod()
    peak = eq.cummax()
    dd = eq / peak - 1.0
    return float(dd.min())


def _eval_trade_rows(x: pd.DataFrame, top_n: int) -> dict[str, Any]:
    if x.empty:
        return {
            "n": 0,
            "hit_rate": np.nan,
            "avg_net_ret": np.nan,
            "median_net_ret": np.nan,
            "avg_mdd": np.nan,
            "median_mdd": np.nan,
            "payoff_ratio": np.nan,
            "avg_holding_days": np.nan,
            "median_holding_days": np.nan,
            "turnover_proxy": np.nan,
        }
    ret = pd.to_numeric(x["net_return"], errors="coerce")
    mdd = pd.to_numeric(x["trade_mdd"], errors="coerce")
    hold = pd.to_numeric(x["holding_days"], errors="coerce")
    return {
        "n": int(len(x)),
        "hit_rate": float((ret > 0).mean()),
        "avg_net_ret": float(ret.mean()),
        "median_net_ret": float(ret.median()),
        "avg_mdd": float(mdd.mean()),
        "median_mdd": float(mdd.median()),
        "payoff_ratio": _payoff_ratio(ret),
        "avg_holding_days": float(hold.mean()),
        "median_holding_days": float(hold.median()),
        "turnover_proxy": _turnover_proxy(x, top_n=top_n),
    }


def _monthly_compare(base: pd.DataFrame, var: pd.DataFrame, strategy_name: str) -> pd.DataFrame:
    rows = []
    months = sorted(set(base["entry_date"].dt.to_period("M").astype(str)) | set(var["entry_date"].dt.to_period("M").astype(str)))
    for m in months:
        b = base[base["entry_date"].dt.to_period("M").astype(str) == m]
        v = var[var["entry_date"].dt.to_period("M").astype(str) == m]
        mb = _eval_trade_rows(b, top_n=max(1, int(b.groupby("signal_date").size().max() if not b.empty else 20)))
        mv = _eval_trade_rows(v, top_n=max(1, int(v.groupby("signal_date").size().max() if not v.empty else 20)))
        beat = (
            np.isfinite(mv["avg_net_ret"])
            and np.isfinite(mb["avg_net_ret"])
            and mv["avg_net_ret"] >= mb["avg_net_ret"]
            and np.isfinite(mv["avg_mdd"])
            and np.isfinite(mb["avg_mdd"])
            and mv["avg_mdd"] >= mb["avg_mdd"] - 0.005
            and np.isfinite(mv["hit_rate"])
            and np.isfinite(mb["hit_rate"])
            and mv["hit_rate"] >= mb["hit_rate"] - 0.005
        )
        rows.append(
            {
                "test_month": m,
                "strategy_name": strategy_name,
                "baseline_n": mb["n"],
                "variant_n": mv["n"],
                "coverage_ratio": float(mv["n"] / mb["n"]) if mb["n"] > 0 else np.nan,
                "baseline_hit_rate": mb["hit_rate"],
                "variant_hit_rate": mv["hit_rate"],
                "hit_rate_uplift": mv["hit_rate"] - mb["hit_rate"] if np.isfinite(mv["hit_rate"]) and np.isfinite(mb["hit_rate"]) else np.nan,
                "baseline_avg_ret": mb["avg_net_ret"],
                "variant_avg_ret": mv["avg_net_ret"],
                "avg_ret_uplift": mv["avg_net_ret"] - mb["avg_net_ret"] if np.isfinite(mv["avg_net_ret"]) and np.isfinite(mb["avg_net_ret"]) else np.nan,
                "baseline_avg_mdd": mb["avg_mdd"],
                "variant_avg_mdd": mv["avg_mdd"],
                "avg_mdd_uplift": mv["avg_mdd"] - mb["avg_mdd"] if np.isfinite(mv["avg_mdd"]) and np.isfinite(mb["avg_mdd"]) else np.nan,
                "baseline_payoff_ratio": mb["payoff_ratio"],
                "variant_payoff_ratio": mv["payoff_ratio"],
                "variant_beats_baseline_flag": bool(beat),
            }
        )
    return pd.DataFrame(rows)


def _write_md(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines), encoding="utf-8")


def load_panel(panel_csv: str, start: str, end: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    df = pd.read_csv(panel_csv)
    qa: dict[str, Any] = {}
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    qa["missing_required_columns"] = missing
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    qa["n_rows_raw"] = int(len(df))
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    qa["date_parse_na"] = int(df["date"].isna().sum())
    df = df.dropna(subset=["date"]).copy()
    df = df[(df["date"] >= pd.Timestamp(start)) & (df["date"] <= pd.Timestamp(end))].copy()
    dup = df.duplicated(subset=["date", "symbol"], keep=False)
    qa["duplicate_symbol_date_rows"] = int(dup.sum())
    if dup.any():
        df = df[~df.duplicated(subset=["date", "symbol"], keep="first")].copy()
    df["symbol"] = df["symbol"].astype(str).str.upper()
    num_cols = ["p20", "label_wave20", "fwd_ret20", "fwd_mdd20", "adv50_vnd", "traded_value_vnd", "close", "open", "high", "low", "volume"]
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    qa["nonfinite_p20_rows"] = int((~np.isfinite(df["p20"])).sum())
    before = len(df)
    df = df.dropna(subset=["p20", "label_wave20", "fwd_ret20", "fwd_mdd20"]).copy()
    qa["rows_dropped_for_core"] = int(before - len(df))
    qa["n_rows_clean"] = int(len(df))
    qa["n_symbols"] = int(df["symbol"].nunique())
    qa["n_dates"] = int(df["date"].nunique())
    qa["has_ohlc_in_panel"] = bool(set(["open", "high", "low", "close", "volume"]).issubset(df.columns))
    return df.sort_values(["date", "symbol"]).reset_index(drop=True), qa


def build_baseline_episodes(panel: pd.DataFrame, candidate_pool_n: int, top_n: int, cooldown_days: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    x = panel.sort_values(["date", "p20"], ascending=[True, False]).copy()
    x["rank_on_start_date"] = x.groupby("date")["p20"].rank(method="first", ascending=False).astype(int)
    cand = x.groupby("date", as_index=False).head(candidate_pool_n).copy()
    if cand.empty:
        return cand, cand
    dlist = sorted(pd.to_datetime(cand["date"]).unique().tolist())
    d2i = {d: i for i, d in enumerate(dlist)}
    next_allowed: dict[str, int] = {}
    rows = []
    for dt, g in cand.groupby("date"):
        di = d2i[pd.Timestamp(dt)]
        chosen = 0
        for _, r in g.sort_values("rank_on_start_date").iterrows():
            sym = str(r["symbol"])
            if di < next_allowed.get(sym, -10**9):
                continue
            rows.append(r.to_dict())
            next_allowed[sym] = di + cooldown_days
            chosen += 1
            if chosen >= top_n:
                break
    episodes = pd.DataFrame(rows)
    return cand, episodes


def _load_cached_symbol(cache_dir: Path, sym: str) -> pd.DataFrame:
    fp = cache_dir / f"{sym}.csv"
    if not fp.exists():
        return pd.DataFrame()
    x = pd.read_csv(fp)
    x["date"] = pd.to_datetime(x["date"], errors="coerce")
    for c in ["open", "high", "low", "close", "volume"]:
        if c in x.columns:
            x[c] = pd.to_numeric(x[c], errors="coerce")
    x = x.dropna(subset=["date", "open", "high", "low", "close", "volume"]).sort_values("date").reset_index(drop=True)
    return x


def build_ohlcv_cache(
    symbols: list[str],
    start: str,
    end: str,
    cache_dir: Path,
    refresh_cache: bool,
    max_workers: int,
) -> dict[str, Any]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    start_dt = pd.Timestamp(start)
    end_dt = pd.Timestamp(end)
    client = get_client(timeout=60)
    summary: dict[str, Any] = {
        "requested_symbols": len(symbols),
        "cached_symbols": 0,
        "fetched_symbols": 0,
        "missing_symbols": [],
        "errors": [],
    }

    def _fetch(sym: str) -> tuple[str, bool, str]:
        fp = cache_dir / f"{sym}.csv"
        if fp.exists() and not refresh_cache:
            return sym, True, "cache_hit"
        try:
            h = client.get_ohlcv(sym, start=start_dt.strftime("%Y-%m-%d"), end=end_dt.strftime("%Y-%m-%d"))
            if h.empty:
                return sym, False, "empty"
            h = h[["date", "open", "high", "low", "close", "volume"]].copy()
            h.to_csv(fp, index=False)
            return sym, True, "fetched"
        except Exception as exc:  # pragma: no cover
            return sym, False, f"error:{exc}"

    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as ex:
        futs = {ex.submit(_fetch, s): s for s in symbols}
        for fut in as_completed(futs):
            sym, ok, status = fut.result()
            if ok:
                summary["cached_symbols"] += 1
                if status == "fetched":
                    summary["fetched_symbols"] += 1
            else:
                summary["missing_symbols"].append(sym)
                summary["errors"].append({"symbol": sym, "status": status})
    summary["coverage_ratio"] = float(summary["cached_symbols"] / max(len(symbols), 1))
    return summary


def _series_lookup(df: pd.DataFrame) -> dict[pd.Timestamp, int]:
    return {pd.Timestamp(d): i for i, d in enumerate(df["date"].tolist())}


def reconstruct_trades_from_episodes(
    episodes: pd.DataFrame,
    cache_dir: Path,
    transaction_cost_bps: float,
    entry_mode: str = "next_close",
    horizon_days: int = 20,
) -> TradeResult:
    rows = []
    missing = 0
    for _, r in episodes.iterrows():
        sym = str(r["symbol"])
        sig = pd.Timestamp(r["date"])
        px = _load_cached_symbol(cache_dir, sym)
        if px.empty:
            missing += 1
            continue
        idx = _series_lookup(px)
        i = idx.get(sig)
        if i is None:
            missing += 1
            continue
        entry_i = i
        if entry_mode == "next_close":
            entry_i = i + 1
        elif entry_mode == "next_open":
            entry_i = i + 1
        if entry_i >= len(px):
            missing += 1
            continue
        exit_i = entry_i + horizon_days
        if exit_i >= len(px):
            continue
        entry_px = float(px.iloc[entry_i]["close"] if entry_mode != "next_open" else px.iloc[entry_i]["open"])
        exit_px = float(px.iloc[exit_i]["close"])
        if not np.isfinite(entry_px) or not np.isfinite(exit_px) or entry_px <= 0:
            continue
        gross = exit_px / entry_px - 1.0
        net = gross - transaction_cost_bps / 10000.0
        path = px.iloc[entry_i + 1 : exit_i + 1]["close"]
        if len(path) == 0:
            continue
        trade_mdd = float(path.min() / entry_px - 1.0)
        trade_mae = trade_mdd
        trade_mfe = float(path.max() / entry_px - 1.0)
        rows.append(
            {
                "signal_date": sig,
                "entry_date": pd.Timestamp(px.iloc[entry_i]["date"]),
                "exit_date": pd.Timestamp(px.iloc[exit_i]["date"]),
                "symbol": sym,
                "p20": float(r["p20"]),
                "rank_on_start_date": int(r.get("rank_on_start_date", np.nan)) if np.isfinite(r.get("rank_on_start_date", np.nan)) else np.nan,
                "industryCode": r.get("industryCode", np.nan),
                "entry_price": entry_px,
                "exit_price": exit_px,
                "gross_return": gross,
                "net_return": net,
                "trade_mdd": trade_mdd,
                "trade_mae": trade_mae,
                "trade_mfe": trade_mfe,
                "holding_days": horizon_days,
                "panel_label_wave20": float(r["label_wave20"]),
                "panel_fwd_ret20": float(r["fwd_ret20"]),
                "panel_fwd_mdd20": float(r["fwd_mdd20"]),
            }
        )
    trades = pd.DataFrame(rows).sort_values(["signal_date", "symbol"]) if rows else pd.DataFrame()
    sm = _eval_trade_rows(trades, top_n=max(1, int(trades.groupby("signal_date").size().max() if not trades.empty else 20)))
    sm["missing_paths"] = int(missing)
    sm["entry_mode"] = entry_mode
    sm["horizon_days"] = horizon_days
    return TradeResult(trades=trades, summary=sm)


def baseline_reconstruction_summary(same_close: pd.DataFrame) -> dict[str, Any]:
    if same_close.empty:
        return {}
    x = same_close.dropna(subset=["net_return", "panel_fwd_ret20"]).copy()
    diff = x["net_return"] - x["panel_fwd_ret20"]
    return {
        "n_compared": int(len(x)),
        "corr_realized_vs_panel": float(x["net_return"].corr(x["panel_fwd_ret20"])) if len(x) > 2 else np.nan,
        "mean_diff": float(diff.mean()) if len(diff) else np.nan,
        "median_diff": float(diff.median()) if len(diff) else np.nan,
        "p95_abs_diff": float(diff.abs().quantile(0.95)) if len(diff) else np.nan,
    }


def return_anatomy(trades: pd.DataFrame) -> dict[str, pd.DataFrame]:
    x = trades.copy()
    x["ret"] = pd.to_numeric(x["net_return"], errors="coerce")
    total = float(x["ret"].sum()) if len(x) else np.nan
    pct_rows = []
    for p, name in [(0.99, "top_1pct"), (0.95, "top_5pct"), (0.90, "top_10pct"), (0.80, "top_20pct"), (0.10, "bottom_10pct"), (0.20, "bottom_20pct")]:
        if len(x) == 0:
            pct_rows.append({"bucket": name, "sum_ret": np.nan, "share_of_total": np.nan})
            continue
        thr = x["ret"].quantile(p)
        if "bottom" in name:
            sub = x[x["ret"] <= thr]
        else:
            sub = x[x["ret"] >= thr]
        s = float(sub["ret"].sum())
        pct_rows.append({"bucket": name, "sum_ret": s, "share_of_total": s / total if np.isfinite(total) and total != 0 else np.nan})
    contribution = pd.DataFrame(pct_rows)

    cap_rows = []
    for cap in [0.10, 0.15, 0.20, 0.30]:
        y = x["ret"].clip(upper=cap)
        cap_rows.append({"winner_cap": cap, "avg_ret_after_cap": float(y.mean()), "delta_vs_base_pp": 100.0 * float(y.mean() - x["ret"].mean())})
    winner_cap = pd.DataFrame(cap_rows)

    floor_rows = []
    for fl in [-0.05, -0.08, -0.10, -0.12]:
        y = x["ret"].clip(lower=fl)
        floor_rows.append({"loser_floor": fl, "avg_ret_after_floor": float(y.mean()), "delta_vs_base_pp": 100.0 * float(y.mean() - x["ret"].mean())})
    loser_floor = pd.DataFrame(floor_rows)

    rb = x.copy()
    rb["rank_bucket"] = np.where(
        rb["rank_on_start_date"] <= 5,
        "1_5",
        np.where(rb["rank_on_start_date"] <= 10, "6_10", np.where(rb["rank_on_start_date"] <= 20, "11_20", "21_plus")),
    )
    rank_bucket = rb.groupby("rank_bucket", as_index=False).agg(n=("symbol", "size"), avg_ret=("ret", "mean"), avg_mdd=("trade_mdd", "mean"))

    symbol_contrib = x.groupby("symbol", as_index=False).agg(n=("symbol", "size"), sum_ret=("ret", "sum"), avg_ret=("ret", "mean")).sort_values("sum_ret", ascending=False)
    if "industryCode" in x.columns:
        ind_contrib = x.groupby("industryCode", as_index=False).agg(n=("symbol", "size"), sum_ret=("ret", "sum"), avg_ret=("ret", "mean")).sort_values("sum_ret", ascending=False)
    else:
        ind_contrib = pd.DataFrame(columns=["industryCode", "n", "sum_ret", "avg_ret"])
    return {
        "summary": contribution,
        "winner_cap": winner_cap,
        "loser_floor": loser_floor,
        "rank_bucket": rank_bucket,
        "symbol_contrib": symbol_contrib,
        "industry_contrib": ind_contrib,
    }


def _add_path_fields(trades: pd.DataFrame, cache_dir: Path) -> pd.DataFrame:
    rows = []
    for _, r in trades.iterrows():
        sym = str(r["symbol"])
        px = _load_cached_symbol(cache_dir, sym)
        if px.empty:
            continue
        idx = _series_lookup(px)
        e = idx.get(pd.Timestamp(r["entry_date"]))
        if e is None:
            continue
        rec = dict(r)
        for d in [1, 3, 5, 10]:
            j = e + d
            if j < len(px):
                rec[f"ret_d{d}"] = float(px.iloc[j]["close"] / float(r["entry_price"]) - 1.0)
            else:
                rec[f"ret_d{d}"] = np.nan
        j5 = min(e + 5, len(px) - 1)
        j10 = min(e + 10, len(px) - 1)
        path5 = px.iloc[e + 1 : j5 + 1]["close"]
        rec["mae5"] = float(path5.min() / float(r["entry_price"]) - 1.0) if len(path5) else np.nan
        rec["mfe5"] = float(path5.max() / float(r["entry_price"]) - 1.0) if len(path5) else np.nan
        if np.isfinite(rec.get("ret_d5", np.nan)):
            end_i = idx.get(pd.Timestamp(r["exit_date"]))
            if end_i is not None and end_i > j5:
                rec["ret_5_to_20"] = float(px.iloc[end_i]["close"] / px.iloc[j5]["close"] - 1.0)
            else:
                rec["ret_5_to_20"] = np.nan
        if np.isfinite(rec.get("ret_d10", np.nan)):
            end_i = idx.get(pd.Timestamp(r["exit_date"]))
            if end_i is not None and end_i > j10:
                rec["ret_10_to_20"] = float(px.iloc[end_i]["close"] / px.iloc[j10]["close"] - 1.0)
            else:
                rec["ret_10_to_20"] = np.nan
        rows.append(rec)
    return pd.DataFrame(rows)


def apply_entry_rule(base: pd.DataFrame, cache_dir: Path, rule: str, tx_bps: float) -> pd.DataFrame:
    rows = []
    for _, r in base.iterrows():
        sym = str(r["symbol"])
        px = _load_cached_symbol(cache_dir, sym)
        if px.empty:
            continue
        idx = _series_lookup(px)
        s = idx.get(pd.Timestamp(r["signal_date"]))
        if s is None:
            continue
        entry_i = s + 1  # baseline next close
        if rule == "E1_next_open":
            entry_i = s + 1
        if entry_i >= len(px):
            continue
        if rule in ["E2_pullback_ma5_or_ma10_skip", "E2_pullback_ma5_or_ma10_fallback", "E3_tight_day_skip", "E3_tight_day_fallback", "E4_breakout_signal_high", "E5_reclaim_signal_close"]:
            # requires explicit OHLC path trigger; if not found then skip/fallback.
            found = None
            sig_close = float(px.iloc[s]["close"])
            sig_high = float(px.iloc[s]["high"])
            for k in range(s + 1, min(s + 6, len(px))):
                w = px.iloc[max(0, k - 20) : k + 1]
                ma5 = float(w["close"].tail(5).mean()) if len(w) >= 5 else np.nan
                ma10 = float(w["close"].tail(10).mean()) if len(w) >= 10 else np.nan
                ma20 = float(w["close"].tail(20).mean()) if len(w) >= 20 else np.nan
                rng = float((px.iloc[k]["high"] - px.iloc[k]["low"]) / px.iloc[k]["close"]) if px.iloc[k]["close"] > 0 else np.nan
                med_rng = float(((w["high"] - w["low"]) / w["close"]).tail(10).median()) if len(w) >= 10 else np.nan
                vol20 = float(w["volume"].tail(20).mean()) if len(w) >= 20 else np.nan
                cond = False
                if rule.startswith("E2"):
                    cond = (px.iloc[k]["low"] <= ma5 or px.iloc[k]["low"] <= ma10) and (px.iloc[k]["close"] >= ma20 if np.isfinite(ma20) else True)
                elif rule.startswith("E3"):
                    cond = (np.isfinite(rng) and np.isfinite(med_rng) and rng < med_rng) and (px.iloc[k]["close"] >= ma20 if np.isfinite(ma20) else True)
                elif rule == "E4_breakout_signal_high":
                    cond = (px.iloc[k]["close"] > sig_high) and (px.iloc[k]["volume"] > 1.2 * vol20 if np.isfinite(vol20) else False)
                elif rule == "E5_reclaim_signal_close":
                    # wait below then reclaim
                    prior = px.iloc[s + 1 : k]
                    seen_below = bool((prior["close"] < sig_close).any()) if len(prior) else False
                    cond = seen_below and (px.iloc[k]["close"] > sig_close)
                if cond:
                    found = k
                    break
            if found is None:
                if rule.endswith("_fallback"):
                    entry_i = s + 1
                else:
                    continue
            else:
                entry_i = found
        exit_i = entry_i + 20
        if exit_i >= len(px):
            continue
        entry_px = float(px.iloc[entry_i]["open"] if rule == "E1_next_open" else px.iloc[entry_i]["close"])
        exit_px = float(px.iloc[exit_i]["close"])
        if not np.isfinite(entry_px) or not np.isfinite(exit_px) or entry_px <= 0:
            continue
        gross = exit_px / entry_px - 1.0
        net = gross - tx_bps / 10000.0
        path = px.iloc[entry_i + 1 : exit_i + 1]["close"]
        rows.append(
            {
                **r.to_dict(),
                "entry_date": pd.Timestamp(px.iloc[entry_i]["date"]),
                "exit_date": pd.Timestamp(px.iloc[exit_i]["date"]),
                "entry_price": entry_px,
                "exit_price": exit_px,
                "gross_return": gross,
                "net_return": net,
                "trade_mdd": float(path.min() / entry_px - 1.0) if len(path) else np.nan,
                "trade_mfe": float(path.max() / entry_px - 1.0) if len(path) else np.nan,
                "holding_days": 20,
                "strategy_name": rule,
            }
        )
    return pd.DataFrame(rows)


def apply_exit_rule(base: pd.DataFrame, cache_dir: Path, rule: str, tx_bps: float) -> pd.DataFrame:
    rows = []
    for _, r in base.iterrows():
        sym = str(r["symbol"])
        px = _load_cached_symbol(cache_dir, sym)
        if px.empty:
            continue
        idx = _series_lookup(px)
        e = idx.get(pd.Timestamp(r["entry_date"]))
        s = idx.get(pd.Timestamp(r["signal_date"]))
        if e is None or s is None:
            continue
        entry_px = float(r["entry_price"])
        sig_low = float(px.iloc[s]["low"]) if s < len(px) else np.nan
        exit_i = min(e + 20, len(px) - 1)
        peak = entry_px
        activated = False
        for k in range(e + 1, min(e + 31, len(px))):
            cl = float(px.iloc[k]["close"])
            peak = max(peak, cl)
            w = px.iloc[max(0, k - 20) : k + 1]
            ma10 = float(w["close"].tail(10).mean()) if len(w) >= 10 else np.nan
            ma20 = float(w["close"].tail(20).mean()) if len(w) >= 20 else np.nan
            if rule == "X0_fixed_20d":
                pass
            elif rule == "X1_profit_take_12pct" and cl >= entry_px * 1.12:
                exit_i = k
                break
            elif rule == "X2_profit_take_15pct" and cl >= entry_px * 1.15:
                exit_i = k
                break
            elif rule == "X3_profit_take_20pct" and cl >= entry_px * 1.20:
                exit_i = k
                break
            elif rule == "X4_trailing_stop_8pct_from_peak_close" and cl <= peak * 0.92:
                exit_i = k
                break
            elif rule == "X5_ma10_fail" and np.isfinite(ma10) and cl < ma10:
                exit_i = k
                break
            elif rule == "X6_ma20_fail" and np.isfinite(ma20) and cl < ma20:
                exit_i = k
                break
            elif rule == "X7_signal_day_low_fail" and np.isfinite(sig_low) and cl < sig_low:
                exit_i = k
                break
            elif rule == "X8_fail_fast_minus5pct" and (cl / entry_px - 1.0) <= -0.05:
                exit_i = k
                break
            elif rule == "X9_time_stop_day10_if_negative" and k == min(e + 10, len(px) - 1) and (cl / entry_px - 1.0) < 0:
                exit_i = k
                break
            elif rule == "X10_profit_take_15_then_trailing_8":
                if cl >= entry_px * 1.15:
                    activated = True
                if activated and cl <= peak * 0.92:
                    exit_i = k
                    break
            elif rule == "X11_hold_winner_to_30d_if_positive_day20":
                if k == min(e + 20, len(px) - 1):
                    if (cl / entry_px - 1.0) > 0 and (e + 30) < len(px):
                        exit_i = e + 30
                    else:
                        exit_i = k
                    break
        exit_px = float(px.iloc[exit_i]["close"])
        gross = exit_px / entry_px - 1.0
        net = gross - tx_bps / 10000.0
        path = px.iloc[e + 1 : exit_i + 1]["close"]
        rows.append(
            {
                **r.to_dict(),
                "exit_date": pd.Timestamp(px.iloc[exit_i]["date"]),
                "exit_price": exit_px,
                "gross_return": gross,
                "net_return": net,
                "trade_mdd": float(path.min() / entry_px - 1.0) if len(path) else np.nan,
                "trade_mfe": float(path.max() / entry_px - 1.0) if len(path) else np.nan,
                "holding_days": int(exit_i - e),
                "strategy_name": rule,
            }
        )
    return pd.DataFrame(rows)


def apply_horizon_rule(base: pd.DataFrame, cache_dir: Path, rule: str, tx_bps: float) -> pd.DataFrame:
    mapping = {"H5": 5, "H10": 10, "H15": 15, "H20": 20, "H30": 30, "H50": 50}
    if rule in mapping:
        return _rebuild_fixed_horizon(base, cache_dir, mapping[rule], tx_bps, rule)
    if rule == "CH1_H10_if_negative_else_H20":
        return _conditional_horizon(base, cache_dir, tx_bps, neg_day=10, pos_h=20, name=rule)
    if rule == "CH2_H10_if_negative_else_H30":
        return _conditional_horizon(base, cache_dir, tx_bps, neg_day=10, pos_h=30, name=rule)
    if rule == "CH3_H20_if_positive_extend_H30_with_trailing_8":
        return _extend_if_positive(base, cache_dir, tx_bps, check_day=20, extend_to=30, name=rule)
    if rule == "CH4_H20_if_positive_extend_H50_with_ma20_fail":
        return _extend_if_positive(base, cache_dir, tx_bps, check_day=20, extend_to=50, name=rule)
    if rule == "CH5_H30_with_ma20_fail":
        return apply_exit_rule(_rebuild_fixed_horizon(base, cache_dir, 30, tx_bps, rule), cache_dir, "X6_ma20_fail", tx_bps)
    return pd.DataFrame()


def _rebuild_fixed_horizon(base: pd.DataFrame, cache_dir: Path, h: int, tx_bps: float, name: str) -> pd.DataFrame:
    rows = []
    for _, r in base.iterrows():
        px = _load_cached_symbol(cache_dir, str(r["symbol"]))
        if px.empty:
            continue
        idx = _series_lookup(px)
        e = idx.get(pd.Timestamp(r["entry_date"]))
        if e is None or e + h >= len(px):
            continue
        entry_px = float(r["entry_price"])
        exit_i = e + h
        exit_px = float(px.iloc[exit_i]["close"])
        gross = exit_px / entry_px - 1.0
        net = gross - tx_bps / 10000.0
        path = px.iloc[e + 1 : exit_i + 1]["close"]
        rows.append({**r.to_dict(), "exit_date": pd.Timestamp(px.iloc[exit_i]["date"]), "exit_price": exit_px, "gross_return": gross, "net_return": net, "trade_mdd": float(path.min() / entry_px - 1.0) if len(path) else np.nan, "trade_mfe": float(path.max() / entry_px - 1.0) if len(path) else np.nan, "holding_days": h, "strategy_name": name})
    return pd.DataFrame(rows)


def _conditional_horizon(base: pd.DataFrame, cache_dir: Path, tx_bps: float, neg_day: int, pos_h: int, name: str) -> pd.DataFrame:
    rows = []
    for _, r in base.iterrows():
        px = _load_cached_symbol(cache_dir, str(r["symbol"]))
        if px.empty:
            continue
        idx = _series_lookup(px)
        e = idx.get(pd.Timestamp(r["entry_date"]))
        if e is None or e + max(neg_day, pos_h) >= len(px):
            continue
        entry_px = float(r["entry_price"])
        chk = float(px.iloc[e + neg_day]["close"] / entry_px - 1.0)
        h = neg_day if chk < 0 else pos_h
        exit_i = e + h
        exit_px = float(px.iloc[exit_i]["close"])
        gross = exit_px / entry_px - 1.0
        net = gross - tx_bps / 10000.0
        path = px.iloc[e + 1 : exit_i + 1]["close"]
        rows.append({**r.to_dict(), "exit_date": pd.Timestamp(px.iloc[exit_i]["date"]), "exit_price": exit_px, "gross_return": gross, "net_return": net, "trade_mdd": float(path.min() / entry_px - 1.0) if len(path) else np.nan, "trade_mfe": float(path.max() / entry_px - 1.0) if len(path) else np.nan, "holding_days": h, "strategy_name": name})
    return pd.DataFrame(rows)


def _extend_if_positive(base: pd.DataFrame, cache_dir: Path, tx_bps: float, check_day: int, extend_to: int, name: str) -> pd.DataFrame:
    rows = []
    for _, r in base.iterrows():
        px = _load_cached_symbol(cache_dir, str(r["symbol"]))
        if px.empty:
            continue
        idx = _series_lookup(px)
        e = idx.get(pd.Timestamp(r["entry_date"]))
        if e is None or e + extend_to >= len(px):
            continue
        entry_px = float(r["entry_price"])
        ret_chk = float(px.iloc[e + check_day]["close"] / entry_px - 1.0)
        h = extend_to if ret_chk > 0 else check_day
        exit_i = e + h
        exit_px = float(px.iloc[exit_i]["close"])
        gross = exit_px / entry_px - 1.0
        net = gross - tx_bps / 10000.0
        path = px.iloc[e + 1 : exit_i + 1]["close"]
        rows.append({**r.to_dict(), "exit_date": pd.Timestamp(px.iloc[exit_i]["date"]), "exit_price": exit_px, "gross_return": gross, "net_return": net, "trade_mdd": float(path.min() / entry_px - 1.0) if len(path) else np.nan, "trade_mfe": float(path.max() / entry_px - 1.0) if len(path) else np.nan, "holding_days": h, "strategy_name": name})
    return pd.DataFrame(rows)


def verdict_execution(base: dict[str, Any], var: dict[str, Any], monthly: pd.DataFrame, coverage_min: float) -> str:
    if monthly.empty:
        return "FAIL"
    win = float(monthly["variant_beats_baseline_flag"].mean())
    cov = float(monthly["coverage_ratio"].mean())
    ret_pp = 100.0 * (var["avg_net_ret"] - base["avg_net_ret"]) if np.isfinite(var["avg_net_ret"]) and np.isfinite(base["avg_net_ret"]) else np.nan
    mdd_pp = 100.0 * (var["avg_mdd"] - base["avg_mdd"]) if np.isfinite(var["avg_mdd"]) and np.isfinite(base["avg_mdd"]) else np.nan
    hit_pp = 100.0 * (var["hit_rate"] - base["hit_rate"]) if np.isfinite(var["hit_rate"]) and np.isfinite(base["hit_rate"]) else np.nan
    pass_flag = np.isfinite(ret_pp) and ret_pp >= 0.30 and np.isfinite(mdd_pp) and mdd_pp >= 0.50 and np.isfinite(hit_pp) and hit_pp >= -1.0 and np.isfinite(win) and win >= 0.55 and np.isfinite(cov) and cov >= coverage_min
    if pass_flag:
        return "PASS"
    return "WATCH" if np.isfinite(ret_pp) and ret_pp > 0 else "FAIL"


def verdict_sizing(base_monthly_ret: pd.Series, var_monthly_ret: pd.Series, base_turn: float, var_turn: float) -> str:
    if base_monthly_ret.empty or var_monthly_ret.empty:
        return "FAIL"
    base_dd = _portfolio_max_drawdown(base_monthly_ret)
    var_dd = _portfolio_max_drawdown(var_monthly_ret)
    dd_imp = 100.0 * (var_dd - base_dd) / abs(base_dd) if np.isfinite(base_dd) and base_dd != 0 and np.isfinite(var_dd) else np.nan
    ret_diff_pp = 100.0 * float(var_monthly_ret.mean() - base_monthly_ret.mean())
    all_idx = sorted(set(base_monthly_ret.index.tolist()) | set(var_monthly_ret.index.tolist()))
    b = base_monthly_ret.reindex(all_idx)
    v = var_monthly_ret.reindex(all_idx)
    cmp = (v >= b).astype(float)
    win = float(cmp.mean()) if len(cmp) else np.nan
    turn_ok = (not np.isfinite(base_turn)) or (not np.isfinite(var_turn)) or (var_turn <= base_turn * 1.20)
    pass_flag = np.isfinite(dd_imp) and dd_imp <= -10.0 and np.isfinite(ret_diff_pp) and ret_diff_pp >= -0.20 and np.isfinite(win) and win >= 0.55 and turn_ok
    if pass_flag:
        return "PASS"
    return "WATCH" if np.isfinite(dd_imp) and dd_imp < 0 else "FAIL"


def build_context_audit(out_dir: Path) -> None:
    lines = [
        "# p20 Return Leakage Context Audit",
        "",
        "- Baseline p20 remains benchmark from prior strict episode-level OOS tests.",
        "- Complex alpha recalibrations (v2/v2.2/v2.3) failed production-grade PASS.",
        "- RS overlays failed as ranking add-ons: always-on RS, event-based RS, RS+range+slope all FAIL.",
        "- Current objective shifts from alpha replacement to realized-return leakage diagnosis on top of baseline p20.",
        "- Data limitation: `super_alpha_panel_from_2023.csv` may not include full OHLC path fields for every symbol-date, so OHLCV cache fetch is required.",
        "",
        "Do not redo alpha recalibration. Current task is to identify whether realized return can be improved through trade execution, exit, holding horizon, sizing, or exposure control on top of baseline p20.",
    ]
    _write_md(out_dir / "p20_return_leakage_context_audit.md", lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel-csv", default=str(REPO / "data" / "research" / "super_alpha_panel_from_2023.csv"))
    ap.add_argument("--start", default="2023-01-01")
    ap.add_argument("--end", default="2026-04-30")
    ap.add_argument("--top-n", type=int, default=20)
    ap.add_argument("--candidate-pool-n", type=int, default=100)
    ap.add_argument("--episode-cooldown-days", type=int, default=20)
    ap.add_argument("--transaction-cost-bps", type=float, default=30)
    ap.add_argument("--ohlcv-cache-dir", default=str(REPO / "data" / "research" / "cache" / "fireant_ohlcv"))
    ap.add_argument("--refresh-cache", action="store_true")
    ap.add_argument("--max-workers", type=int, default=8)
    ap.add_argument("--fetch-history-buffer-days", type=int, default=300)
    ap.add_argument("--fetch-forward-buffer-days", type=int, default=120)
    ap.add_argument(
        "--mode",
        choices=[
            "audit",
            "cache",
            "baseline",
            "anatomy",
            "early_path",
            "entry",
            "exit",
            "horizon",
            "sizing",
            "exposure",
            "rs_execution",
            "all",
        ],
        default="all",
    )
    ap.add_argument("--out-dir", default=str(REPO / "data" / "research"))
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = Path(args.ohlcv_cache_dir)
    build_context_audit(out_dir)

    panel, panel_qa = load_panel(args.panel_csv, args.start, args.end)
    cand_pool, episodes = build_baseline_episodes(panel, args.candidate_pool_n, args.top_n, args.episode_cooldown_days)
    panel_qa["candidate_pool_rows"] = int(len(cand_pool))
    panel_qa["baseline_episode_rows"] = int(len(episodes))
    panel_qa_path = out_dir / "p20_return_leakage_panel_qa.json"
    panel_qa_path.write_text(json.dumps(panel_qa, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_md(
        out_dir / "p20_return_leakage_panel_qa.md",
        [
            "# Panel QA",
            "",
            f"- n_rows_clean: {panel_qa['n_rows_clean']}",
            f"- n_symbols: {panel_qa['n_symbols']}",
            f"- n_dates: {panel_qa['n_dates']}",
            f"- duplicate_symbol_date_rows: {panel_qa['duplicate_symbol_date_rows']}",
            f"- has_ohlc_in_panel: {panel_qa['has_ohlc_in_panel']}",
            f"- baseline_episode_rows: {panel_qa['baseline_episode_rows']}",
        ],
    )
    episodes.to_csv(out_dir / "p20_return_leakage_baseline_signal_episodes.csv", index=False)

    if args.mode == "audit":
        print(json.dumps({"mode": "audit", "panel_qa_json": str(panel_qa_path), "episodes": int(len(episodes))}, ensure_ascii=False, indent=2))
        return

    needed_syms = sorted(set(cand_pool["symbol"].astype(str).str.upper().tolist()) | set(episodes["symbol"].astype(str).str.upper().tolist()))
    cache_start = (pd.Timestamp(args.start) - pd.Timedelta(days=args.fetch_history_buffer_days)).strftime("%Y-%m-%d")
    cache_end = (pd.Timestamp(args.end) + pd.Timedelta(days=args.fetch_forward_buffer_days)).strftime("%Y-%m-%d")
    cache_summary = build_ohlcv_cache(
        needed_syms,
        start=cache_start,
        end=cache_end,
        cache_dir=cache_dir,
        refresh_cache=args.refresh_cache,
        max_workers=args.max_workers,
    )
    (out_dir / "p20_return_leakage_ohlcv_cache_summary.json").write_text(json.dumps(cache_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_md(
        out_dir / "p20_return_leakage_ohlcv_cache_summary.md",
        [
            "# OHLCV Cache Summary",
            "",
            f"- requested_symbols: {cache_summary['requested_symbols']}",
            f"- cached_symbols: {cache_summary['cached_symbols']}",
            f"- fetched_symbols: {cache_summary['fetched_symbols']}",
            f"- coverage_ratio: {cache_summary['coverage_ratio']:.4f}",
            f"- missing_symbols: {len(cache_summary['missing_symbols'])}",
        ],
    )

    if args.mode == "cache":
        print(json.dumps({"mode": "cache", "cache_summary": cache_summary}, ensure_ascii=False, indent=2))
        return

    # Baseline reconstruction
    base_same = reconstruct_trades_from_episodes(episodes, cache_dir, args.transaction_cost_bps, entry_mode="same_close", horizon_days=20)
    base_next_close = reconstruct_trades_from_episodes(episodes, cache_dir, args.transaction_cost_bps, entry_mode="next_close", horizon_days=20)
    base_next_open = reconstruct_trades_from_episodes(episodes, cache_dir, args.transaction_cost_bps, entry_mode="next_open", horizon_days=20)
    base_next_close.trades.to_csv(out_dir / "p20_return_leakage_baseline_trades.csv", index=False)
    recon = baseline_reconstruction_summary(base_same.trades)
    recon["coverage_vs_episodes"] = float(len(base_next_close.trades) / max(len(episodes), 1))
    recon["same_close_summary"] = base_same.summary
    recon["next_close_summary"] = base_next_close.summary
    recon["next_open_summary"] = base_next_open.summary
    (out_dir / "p20_return_leakage_baseline_reconstruction_summary.json").write_text(json.dumps(recon, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_md(
        out_dir / "p20_return_leakage_baseline_reconstruction_summary.md",
        [
            "# Baseline Reconstruction Summary",
            "",
            f"- corr_realized_vs_panel: {recon.get('corr_realized_vs_panel')}",
            f"- mean_diff: {recon.get('mean_diff')}",
            f"- median_diff: {recon.get('median_diff')}",
            f"- p95_abs_diff: {recon.get('p95_abs_diff')}",
            f"- coverage_vs_episodes: {recon.get('coverage_vs_episodes')}",
        ],
    )
    if args.mode == "baseline":
        print(json.dumps({"mode": "baseline", "reconstruction": recon}, ensure_ascii=False, indent=2))
        return

    base = base_next_close.trades.copy()
    outputs: dict[str, Any] = {}

    # Anatomy
    if args.mode in ["anatomy", "all"]:
        anat = return_anatomy(base)
        anat["summary"].to_csv(out_dir / "p20_return_anatomy_summary.csv", index=False)
        anat["rank_bucket"].to_csv(out_dir / "p20_return_anatomy_rank_buckets.csv", index=False)
        anat["symbol_contrib"].to_csv(out_dir / "p20_return_anatomy_symbol_contribution.csv", index=False)
        anat["industry_contrib"].to_csv(out_dir / "p20_return_anatomy_industry_contribution.csv", index=False)
        js = {
            "top_5pct_share": float(anat["summary"].loc[anat["summary"]["bucket"] == "top_5pct", "share_of_total"].iloc[0]) if not anat["summary"].empty else np.nan,
            "top_10pct_share": float(anat["summary"].loc[anat["summary"]["bucket"] == "top_10pct", "share_of_total"].iloc[0]) if not anat["summary"].empty else np.nan,
        }
        (out_dir / "p20_return_anatomy_summary.json").write_text(json.dumps(js, ensure_ascii=False, indent=2), encoding="utf-8")
        _write_md(out_dir / "p20_return_anatomy_summary.md", ["# Return Anatomy Summary", "", f"- top_5pct_share: {js.get('top_5pct_share')}", f"- top_10pct_share: {js.get('top_10pct_share')}"])
        outputs["anatomy"] = js
    if args.mode == "anatomy":
        print(json.dumps({"mode": "anatomy", "outputs": outputs}, ensure_ascii=False, indent=2))
        return

    # Early path + fail-fast
    if args.mode in ["early_path", "all"]:
        path = _add_path_fields(base, cache_dir)
        if path.empty:
            ep_sum = {}
            ff_month = pd.DataFrame()
        else:
            ep_sum = {
                "avg_final_ret_if_negative_d5": _safe_mean(path[path["ret_d5"] < 0]["net_return"]),
                "avg_final_ret_if_positive_d5": _safe_mean(path[path["ret_d5"] > 0]["net_return"]),
                "avg_final_ret_if_negative_d10": _safe_mean(path[path["ret_d10"] < 0]["net_return"]),
                "avg_final_ret_if_positive_d10": _safe_mean(path[path["ret_d10"] > 0]["net_return"]),
                "recovery_after_mae5_minus5": _safe_mean(path[path["mae5"] < -0.05]["net_return"]),
            }
            fail_fast_defs = {
                "F1_exit_if_negative_day5": lambda d: np.where(d["ret_d5"] < 0, 5, 20),
                "F2_exit_if_negative_day10": lambda d: np.where(d["ret_d10"] < 0, 10, 20),
                "F3_exit_if_down_5pct_anytime": lambda d: np.where(d["mae5"] < -0.05, 5, 20),
                "F4_exit_if_mae5_less_than_minus5pct": lambda d: np.where(d["mae5"] < -0.05, 5, 20),
            }
            ff_rows = []
            for name, fn in fail_fast_defs.items():
                mod = []
                for _, r in path.iterrows():
                    h = int(fn(pd.DataFrame([r]))[0])
                    re = _rebuild_fixed_horizon(pd.DataFrame([r]), cache_dir, h, args.transaction_cost_bps, name)
                    if not re.empty:
                        mod.append(re.iloc[0].to_dict())
                v = pd.DataFrame(mod)
                mm = _monthly_compare(base, v, name)
                ff_rows.append(mm)
            ff_month = pd.concat(ff_rows, ignore_index=True) if ff_rows else pd.DataFrame()
        path.to_csv(out_dir / "p20_early_path_diagnostics.csv", index=False)
        ff_month.to_csv(out_dir / "p20_early_path_failfast_monthly_oos.csv", index=False)
        (out_dir / "p20_early_path_summary.json").write_text(json.dumps(ep_sum, ensure_ascii=False, indent=2), encoding="utf-8")
        _write_md(out_dir / "p20_early_path_summary.md", ["# Early Path Summary", ""] + [f"- {k}: {v}" for k, v in ep_sum.items()])
        outputs["early_path"] = ep_sum
    if args.mode == "early_path":
        print(json.dumps({"mode": "early_path", "outputs": outputs}, ensure_ascii=False, indent=2))
        return

    # Entry tests
    if args.mode in ["entry", "all"]:
        entry_rules = [
            "E0_next_close_baseline",
            "E1_next_open",
            "E2_pullback_ma5_or_ma10_skip",
            "E2_pullback_ma5_or_ma10_fallback",
            "E3_tight_day_skip",
            "E3_tight_day_fallback",
            "E4_breakout_signal_high",
            "E5_reclaim_signal_close",
        ]
        entry_rows = []
        entry_month = []
        entry_sum = []
        base_summary = _eval_trade_rows(base, args.top_n)
        for rname in entry_rules:
            variant = base.copy() if rname == "E0_next_close_baseline" else apply_entry_rule(base, cache_dir, rname, args.transaction_cost_bps)
            if rname == "E0_next_close_baseline":
                variant["strategy_name"] = rname
            entry_rows.append(variant)
            mm = _monthly_compare(base, variant, rname)
            entry_month.append(mm)
            sm = _eval_trade_rows(variant, args.top_n)
            sm["strategy_name"] = rname
            sm["coverage_ratio"] = float(len(variant) / max(len(base), 1))
            sm["monthly_win_rate"] = float(mm["variant_beats_baseline_flag"].mean()) if not mm.empty else np.nan
            cov_min = 0.70 if rname.endswith("_skip") or rname in ["E4_breakout_signal_high", "E5_reclaim_signal_close"] else 0.90
            sm["verdict"] = verdict_execution(base_summary, sm, mm, cov_min)
            entry_sum.append(sm)
        all_entry = pd.concat(entry_rows, ignore_index=True) if entry_rows else pd.DataFrame()
        all_entry_month = pd.concat(entry_month, ignore_index=True) if entry_month else pd.DataFrame()
        entry_summary = pd.DataFrame(entry_sum).sort_values("avg_net_ret", ascending=False)
        all_entry.to_csv(out_dir / "p20_entry_timing_trades.csv", index=False)
        all_entry_month.to_csv(out_dir / "p20_entry_timing_monthly_oos.csv", index=False)
        entry_summary.to_csv(out_dir / "p20_entry_timing_summary.csv", index=False)
        (out_dir / "p20_entry_timing_summary.json").write_text(entry_summary.to_json(orient="records"), encoding="utf-8")
        _write_md(out_dir / "p20_entry_timing_summary.md", ["# Entry Timing Summary", "", f"- best_rule: {entry_summary.iloc[0]['strategy_name'] if not entry_summary.empty else 'N/A'}"])
        outputs["entry_best"] = entry_summary.iloc[0].to_dict() if not entry_summary.empty else {}
    if args.mode == "entry":
        print(json.dumps({"mode": "entry", "outputs": outputs}, ensure_ascii=False, indent=2))
        return

    # Exit tests
    if args.mode in ["exit", "all"]:
        exit_rules = ["X0_fixed_20d", "X1_profit_take_12pct", "X2_profit_take_15pct", "X3_profit_take_20pct", "X4_trailing_stop_8pct_from_peak_close", "X5_ma10_fail", "X6_ma20_fail", "X7_signal_day_low_fail", "X8_fail_fast_minus5pct", "X9_time_stop_day10_if_negative", "X10_profit_take_15_then_trailing_8", "X11_hold_winner_to_30d_if_positive_day20"]
        exit_rows = []
        exit_month = []
        exit_sum = []
        base_summary = _eval_trade_rows(base, args.top_n)
        for rname in exit_rules:
            variant = base.copy() if rname == "X0_fixed_20d" else apply_exit_rule(base, cache_dir, rname, args.transaction_cost_bps)
            variant["strategy_name"] = rname
            exit_rows.append(variant)
            mm = _monthly_compare(base, variant, rname)
            exit_month.append(mm)
            sm = _eval_trade_rows(variant, args.top_n)
            sm["strategy_name"] = rname
            sm["coverage_ratio"] = float(len(variant) / max(len(base), 1))
            sm["monthly_win_rate"] = float(mm["variant_beats_baseline_flag"].mean()) if not mm.empty else np.nan
            sm["verdict"] = verdict_execution(base_summary, sm, mm, 0.90)
            exit_sum.append(sm)
        all_exit = pd.concat(exit_rows, ignore_index=True) if exit_rows else pd.DataFrame()
        all_exit_month = pd.concat(exit_month, ignore_index=True) if exit_month else pd.DataFrame()
        exit_summary = pd.DataFrame(exit_sum).sort_values("avg_net_ret", ascending=False)
        all_exit.to_csv(out_dir / "p20_exit_rules_trades.csv", index=False)
        all_exit_month.to_csv(out_dir / "p20_exit_rules_monthly_oos.csv", index=False)
        exit_summary.to_csv(out_dir / "p20_exit_rules_summary.csv", index=False)
        (out_dir / "p20_exit_rules_summary.json").write_text(exit_summary.to_json(orient="records"), encoding="utf-8")
        _write_md(out_dir / "p20_exit_rules_summary.md", ["# Exit Rule Summary", "", f"- best_rule: {exit_summary.iloc[0]['strategy_name'] if not exit_summary.empty else 'N/A'}"])
        outputs["exit_best"] = exit_summary.iloc[0].to_dict() if not exit_summary.empty else {}
    if args.mode == "exit":
        print(json.dumps({"mode": "exit", "outputs": outputs}, ensure_ascii=False, indent=2))
        return

    # Horizon tests
    if args.mode in ["horizon", "all"]:
        horizon_rules = ["H5", "H10", "H15", "H20", "H30", "H50", "CH1_H10_if_negative_else_H20", "CH2_H10_if_negative_else_H30", "CH3_H20_if_positive_extend_H30_with_trailing_8", "CH4_H20_if_positive_extend_H50_with_ma20_fail", "CH5_H30_with_ma20_fail"]
        hr_rows = []
        hr_month = []
        hr_sum = []
        base_h = _rebuild_fixed_horizon(base, cache_dir, 20, args.transaction_cost_bps, "H20")
        base_summary = _eval_trade_rows(base_h, args.top_n)
        for rule in horizon_rules:
            variant = base_h.copy() if rule == "H20" else apply_horizon_rule(base, cache_dir, rule, args.transaction_cost_bps)
            variant["strategy_name"] = rule
            hr_rows.append(variant)
            mm = _monthly_compare(base_h, variant, rule)
            hr_month.append(mm)
            sm = _eval_trade_rows(variant, args.top_n)
            sm["strategy_name"] = rule
            sm["coverage_ratio"] = float(len(variant) / max(len(base_h), 1))
            sm["monthly_win_rate"] = float(mm["variant_beats_baseline_flag"].mean()) if not mm.empty else np.nan
            sm["verdict"] = verdict_execution(base_summary, sm, mm, 0.90)
            hr_sum.append(sm)
        all_hr = pd.concat(hr_rows, ignore_index=True) if hr_rows else pd.DataFrame()
        all_hr_month = pd.concat(hr_month, ignore_index=True) if hr_month else pd.DataFrame()
        hr_summary = pd.DataFrame(hr_sum).sort_values("avg_net_ret", ascending=False)
        all_hr.to_csv(out_dir / "p20_horizon_trades.csv", index=False)
        all_hr_month.to_csv(out_dir / "p20_horizon_monthly_oos.csv", index=False)
        hr_summary.to_csv(out_dir / "p20_horizon_summary.csv", index=False)
        (out_dir / "p20_horizon_summary.json").write_text(hr_summary.to_json(orient="records"), encoding="utf-8")
        _write_md(out_dir / "p20_horizon_summary.md", ["# Horizon Summary", "", f"- best_rule: {hr_summary.iloc[0]['strategy_name'] if not hr_summary.empty else 'N/A'}"])
        outputs["horizon_best"] = hr_summary.iloc[0].to_dict() if not hr_summary.empty else {}
    if args.mode == "horizon":
        print(json.dumps({"mode": "horizon", "outputs": outputs}, ensure_ascii=False, indent=2))
        return

    # Sizing
    if args.mode in ["sizing", "all"]:
        x = base.copy()
        x["month"] = x["entry_date"].dt.to_period("M").astype(str)
        x["p20_pct"] = x.groupby("signal_date")["p20"].rank(method="average", pct=True)
        # simple vol proxy from mdd magnitude
        x["vol_proxy"] = x["trade_mdd"].abs().clip(lower=0.01)
        variants = {}
        # S0
        s0 = x.copy()
        s0["weight"] = s0.groupby("signal_date")["symbol"].transform(lambda s: 1.0 / max(len(s), 1))
        variants["S0_equal_weight"] = s0
        # S3
        s3 = x.copy()
        z = s3.groupby("signal_date")["p20_pct"].transform("sum").replace(0, np.nan)
        s3["weight"] = (s3["p20_pct"] / z).fillna(0.0)
        s3["weight"] = s3.groupby("signal_date")["weight"].transform(lambda s: s / max(s.sum(), 1e-9))
        variants["S3_p20_score_weighted"] = s3
        # S1/S2/S4 using proxy volatility
        for nm, cap in [("S1_inverse_ATR20", None), ("S2_inverse_ATR20_10pct_cap", 0.10), ("S4_hybrid_p20_inverse_vol", 0.10)]:
            v = x.copy()
            raw = (1.0 / v["vol_proxy"]) if nm != "S4_hybrid_p20_inverse_vol" else (v["p20_pct"] / v["vol_proxy"])
            v["weight"] = raw.groupby(v["signal_date"]).transform(lambda s: s / max(s.sum(), 1e-9))
            if cap is not None:
                v["weight"] = v["weight"].clip(upper=cap)
                v["weight"] = v.groupby("signal_date")["weight"].transform(lambda s: s / max(s.sum(), 1e-9))
            variants[nm] = v
        sum_rows = []
        monthly_rows = []
        weight_rows = []
        base_monthly = None
        base_turn = None
        for nm, v in variants.items():
            t = v.copy()
            t["weighted_ret"] = t["weight"] * t["net_return"]
            t["weighted_mdd"] = t["weight"] * t["trade_mdd"]
            by_date = t.groupby(["signal_date", "month"], as_index=False).agg(ret=("weighted_ret", "sum"), mdd=("weighted_mdd", "sum"))
            monthly = by_date.groupby("month")["ret"].mean()
            turn = _turnover_proxy(t.rename(columns={"signal_date": "signal_date"}), args.top_n)
            if nm == "S0_equal_weight":
                base_monthly = monthly
                base_turn = turn
            verdict = verdict_sizing(base_monthly if base_monthly is not None else monthly, monthly, base_turn if base_turn is not None else turn, turn)
            sum_rows.append(
                {
                    "strategy_name": nm,
                    "avg_monthly_ret": float(monthly.mean()) if len(monthly) else np.nan,
                    "portfolio_max_drawdown": _portfolio_max_drawdown(monthly),
                    "turnover_proxy": turn,
                    "verdict": verdict,
                }
            )
            for m, rv in monthly.items():
                monthly_rows.append({"test_month": m, "strategy_name": nm, "monthly_ret": float(rv)})
            weight_rows.append(t[["signal_date", "symbol", "weight"]].assign(strategy_name=nm))
        sizing_summary = pd.DataFrame(sum_rows).sort_values("avg_monthly_ret", ascending=False)
        pd.DataFrame(monthly_rows).to_csv(out_dir / "p20_sizing_exposure_monthly_oos.csv", index=False)
        pd.concat(weight_rows, ignore_index=True).to_csv(out_dir / "p20_sizing_exposure_trade_weights.csv", index=False)
        sizing_summary.to_csv(out_dir / "p20_sizing_exposure_summary.csv", index=False)
        (out_dir / "p20_sizing_exposure_summary.json").write_text(sizing_summary.to_json(orient="records"), encoding="utf-8")
        _write_md(out_dir / "p20_sizing_exposure_summary.md", ["# Sizing/Exposure Summary", "", f"- best_rule: {sizing_summary.iloc[0]['strategy_name'] if not sizing_summary.empty else 'N/A'}"])
        outputs["sizing_best"] = sizing_summary.iloc[0].to_dict() if not sizing_summary.empty else {}
    if args.mode == "sizing":
        print(json.dumps({"mode": "sizing", "outputs": outputs}, ensure_ascii=False, indent=2))
        return

    # Exposure/regime maps
    if args.mode in ["exposure", "all"]:
        c = get_client(timeout=45)
        vni = c.get_ohlcv("VNINDEX", start=args.start, end=args.end)
        vni["date"] = pd.to_datetime(vni["date"], errors="coerce")
        vni["close"] = pd.to_numeric(vni["close"], errors="coerce")
        vni["volume"] = pd.to_numeric(vni["volume"], errors="coerce")
        vni = vni.dropna(subset=["date", "close"]).sort_values("date").reset_index(drop=True)
        vni["ma20"] = vni["close"].rolling(20, min_periods=20).mean()
        vni["ma50"] = vni["close"].rolling(50, min_periods=50).mean()
        vni["ma100"] = vni["close"].rolling(100, min_periods=100).mean()
        vni["slope20_5"] = vni["ma20"] / vni["ma20"].shift(5) - 1.0
        prev_c = vni["close"].shift(1)
        prev_v = vni["volume"].shift(1)
        vni["dist"] = ((vni["close"] <= prev_c * (1 - 0.002)) & (vni["volume"] > prev_v)).astype(float)
        vni["dist20"] = vni["dist"].rolling(20, min_periods=10).sum()
        reg = vni[["date", "close", "ma20", "ma50", "ma100", "slope20_5", "dist20"]].copy()
        reg["regime"] = np.where(
            ((reg["close"] < reg["ma50"]) & (reg["slope20_5"] < 0)) | (reg["dist20"] >= 6),
            "Red",
            np.where((reg["close"] > reg["ma50"]) & (reg["slope20_5"] > 0), "Green", "Yellow"),
        )
        ex = episodes.merge(reg[["date", "regime"]], on="date", how="left")
        maps = {
            "EX0_top20_baseline": {"Green": 20, "Yellow": 20, "Red": 20},
            "EX1_top10_only": {"Green": 10, "Yellow": 10, "Red": 10},
            "EX2_top15_only": {"Green": 15, "Yellow": 15, "Red": 15},
            "R1_G20_Y15_R8": {"Green": 20, "Yellow": 15, "Red": 8},
            "R2_G20_Y10_R5": {"Green": 20, "Yellow": 10, "Red": 5},
            "R3_G15_Y10_R3": {"Green": 15, "Yellow": 10, "Red": 3},
            "R4_G20_Y10_R0": {"Green": 20, "Yellow": 10, "Red": 0},
        }
        sum_rows = []
        for nm, mp in maps.items():
            rows = []
            for dt, g in ex.groupby("date"):
                rg = str(g["regime"].iloc[0] if g["regime"].notna().any() else "Yellow")
                n = int(mp.get(rg, 20))
                if n <= 0:
                    continue
                rows.append(g.sort_values("rank_on_start_date").head(n))
            v = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=ex.columns)
            t = reconstruct_trades_from_episodes(v, cache_dir, args.transaction_cost_bps, entry_mode="next_close", horizon_days=20).trades
            mm = t.groupby(t["entry_date"].dt.to_period("M").astype(str))["net_return"].mean() if not t.empty else pd.Series(dtype=float)
            base_mm = base.groupby(base["entry_date"].dt.to_period("M").astype(str))["net_return"].mean() if not base.empty else pd.Series(dtype=float)
            vrd = verdict_sizing(base_mm, mm, _turnover_proxy(base, args.top_n), _turnover_proxy(t.rename(columns={"signal_date": "signal_date"}), args.top_n))
            all_idx = sorted(set(mm.index.tolist()) | set(base_mm.index.tolist()))
            mm_al = mm.reindex(all_idx)
            bm_al = base_mm.reindex(all_idx)
            mw = float((mm_al >= bm_al).astype(float).mean()) if len(all_idx) else np.nan
            sum_rows.append(
                {
                    "strategy_name": nm,
                    "n_trades": int(len(t)),
                    "avg_monthly_ret": float(mm.mean()) if len(mm) else np.nan,
                    "portfolio_max_drawdown": _portfolio_max_drawdown(mm),
                    "monthly_win_rate_vs_base": mw,
                    "verdict": vrd,
                }
            )
        ex_sum = pd.DataFrame(sum_rows).sort_values("avg_monthly_ret", ascending=False)
        ex_sum.to_csv(out_dir / "p20_exposure_summary.csv", index=False)
        outputs["exposure_best"] = ex_sum.iloc[0].to_dict() if not ex_sum.empty else {}
    if args.mode == "exposure":
        print(json.dumps({"mode": "exposure", "outputs": outputs}, ensure_ascii=False, indent=2))
        return

    # RS execution filter (not rank replacement)
    if args.mode in ["rs_execution", "all"]:
        c = get_client(timeout=45)
        vni = c.get_ohlcv("VNINDEX", start=args.start, end=args.end)
        vni["date"] = pd.to_datetime(vni["date"], errors="coerce")
        vni["close"] = pd.to_numeric(vni["close"], errors="coerce")
        vni = vni.dropna(subset=["date", "close"]).sort_values("date")
        vni["h10"] = vni["close"].rolling(10, min_periods=5).max()
        vni["dd10"] = vni["close"] / vni["h10"] - 1.0
        vni["ma10"] = vni["close"].rolling(10, min_periods=10).mean()
        vni["ma50"] = vni["close"].rolling(50, min_periods=50).mean()
        reg = vni[["date", "close", "dd10", "ma10", "ma50"]].copy()
        reg["pullback"] = ((reg["dd10"] <= -0.02) | ((reg["close"] < reg["ma10"]) & (reg["close"] > reg["ma50"]))).astype(float)
        rs_trades = base.copy()
        # Build signal-time RS from past 10 trading days only (no future leakage).
        idx_lookup = {pd.Timestamp(d): i for i, d in enumerate(vni["date"].tolist())}
        idx_close = vni["close"].to_numpy(dtype=float)
        rs_vals = []
        for _, tr in rs_trades.iterrows():
            sym = str(tr["symbol"])
            sig = pd.Timestamp(tr["signal_date"])
            px = _load_cached_symbol(cache_dir, sym)
            if px.empty:
                rs_vals.append(np.nan)
                continue
            sidx = {pd.Timestamp(d): i for i, d in enumerate(px["date"].tolist())}.get(sig)
            iidx = idx_lookup.get(sig)
            if sidx is None or iidx is None or sidx < 10 or iidx < 10:
                rs_vals.append(np.nan)
                continue
            sc = float(px.iloc[sidx]["close"])
            sc10 = float(px.iloc[sidx - 10]["close"])
            ic = float(idx_close[iidx])
            ic10 = float(idx_close[iidx - 10])
            if sc10 <= 0 or ic10 <= 0:
                rs_vals.append(np.nan)
                continue
            sret10 = sc / sc10 - 1.0
            iret10 = ic / ic10 - 1.0
            rs_vals.append(sret10 - iret10)
        rs_trades["rs_strength_signal"] = rs_vals
        if rs_trades.empty:
            rs_sum = pd.DataFrame()
        else:
            rs_trades = rs_trades.merge(reg[["date", "pullback"]].rename(columns={"date": "signal_date"}), on="signal_date", how="left")
            rs_trades["rs_strength"] = rs_trades["rs_strength_signal"].fillna(0.0)
            variants = []
            # RSF1 delay weak RS in pullback (approx with skip weak)
            v1 = rs_trades[(rs_trades["pullback"] < 0.5) | (rs_trades["rs_strength"] > -0.02)].copy()
            v1["strategy_name"] = "RSF1_delay_weak_rs_in_pullback"
            variants.append(v1)
            # RSF2 size adjust
            v2 = rs_trades.copy()
            v2["size_mult"] = np.where((v2["pullback"] > 0.5) & (v2["rs_strength"] < -0.02), 0.5, np.where((v2["pullback"] > 0.5) & (v2["rs_strength"] > 0.02), 1.25, 1.0))
            v2["net_return"] = v2["net_return"] * v2["size_mult"]
            v2["strategy_name"] = "RSF2_size_down_weak_rs_in_pullback"
            variants.append(v2)
            # RSF3 allow only strong RS in pullback
            v3 = rs_trades[(rs_trades["pullback"] < 0.5) | (rs_trades["rs_strength"] > 0.0)].copy()
            v3["strategy_name"] = "RSF3_allow_only_strong_rs_in_pullback"
            variants.append(v3)
            sum_rows = []
            month_rows = []
            base_summary = _eval_trade_rows(base, args.top_n)
            for v in variants:
                nm = str(v["strategy_name"].iloc[0]) if not v.empty else "unknown"
                mm = _monthly_compare(base, v, nm)
                sm = _eval_trade_rows(v, args.top_n)
                sm["strategy_name"] = nm
                sm["coverage_ratio"] = float(len(v) / max(len(base), 1))
                sm["monthly_win_rate"] = float(mm["variant_beats_baseline_flag"].mean()) if not mm.empty else np.nan
                sm["verdict"] = verdict_execution(base_summary, sm, mm, 0.60)
                sum_rows.append(sm)
                month_rows.append(mm)
            rs_sum = pd.DataFrame(sum_rows).sort_values("avg_net_ret", ascending=False)
            pd.concat(month_rows, ignore_index=True).to_csv(out_dir / "p20_rs_execution_filter_monthly_oos.csv", index=False)
            rs_sum.to_csv(out_dir / "p20_rs_execution_filter_summary.csv", index=False)
            (out_dir / "p20_rs_execution_filter_summary.json").write_text(rs_sum.to_json(orient="records"), encoding="utf-8")
            _write_md(out_dir / "p20_rs_execution_filter_summary.md", ["# RS Execution Filter Summary", "", f"- best_rule: {rs_sum.iloc[0]['strategy_name'] if not rs_sum.empty else 'N/A'}"])
        outputs["rs_execution_best"] = rs_sum.iloc[0].to_dict() if isinstance(rs_sum, pd.DataFrame) and not rs_sum.empty else {}
    if args.mode == "rs_execution":
        print(json.dumps({"mode": "rs_execution", "outputs": outputs}, ensure_ascii=False, indent=2))
        return

    # Master summary
    if args.mode == "all":
        lines = [
            "# p20 Return Leakage Master Summary",
            "",
            "## Executive conclusion",
        ]
        pass_any = False
        for k in ["entry_best", "exit_best", "horizon_best", "sizing_best", "exposure_best", "rs_execution_best"]:
            v = outputs.get(k, {})
            if isinstance(v, dict) and str(v.get("verdict", "")) == "PASS":
                pass_any = True
        if pass_any:
            lines.append("The overlay passes strict OOS criteria and may be promoted to paper-trading, not live production yet.")
        else:
            lines.append("Return-leakage tests did not produce production-grade OOS improvement. Baseline p20 remains the benchmark. Next step is paper-trading baseline p20 with discretionary chart confirmation or expanding data history.")
        lines += [
            "",
            "## QA / coverage",
            f"- panel rows: {panel_qa['n_rows_clean']}, symbols: {panel_qa['n_symbols']}, dates: {panel_qa['n_dates']}",
            f"- OHLCV cache coverage: {cache_summary.get('coverage_ratio')}",
            "",
            "## Baseline reconstruction",
            f"- corr vs panel fwd_ret20: {recon.get('corr_realized_vs_panel')}",
            f"- p95 abs diff: {recon.get('p95_abs_diff')}",
            "",
            "## Best by module",
        ]
        for k in ["entry_best", "exit_best", "horizon_best", "sizing_best", "exposure_best", "rs_execution_best"]:
            v = outputs.get(k, {})
            lines.append(f"- {k}: {v.get('strategy_name', v.get('strategy', 'N/A'))} / verdict={v.get('verdict', 'N/A')}")
        _write_md(out_dir / "p20_return_leakage_master_summary.md", lines)
        master = {
            "context_audit": str(out_dir / "p20_return_leakage_context_audit.md"),
            "panel_qa": panel_qa,
            "ohlcv_cache_summary": cache_summary,
            "baseline_reconstruction": recon,
            "module_best": outputs,
        }
        (out_dir / "p20_return_leakage_master_summary.json").write_text(json.dumps(master, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"mode": "all", "outputs": outputs, "master_summary": str(out_dir / "p20_return_leakage_master_summary.json")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

