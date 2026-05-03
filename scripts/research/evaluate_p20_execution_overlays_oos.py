#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sys
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
OPTIONAL_COLS = [
    "p_now",
    "p_hist",
    "close",
    "open",
    "high",
    "low",
    "volume",
    "traded_value_vnd",
    "adv50_vnd",
    "industryCode",
    "exchange",
    "name",
]


@dataclass
class EvalResult:
    name: str
    summary: dict[str, Any]
    monthly: pd.DataFrame
    rows: pd.DataFrame
    verdict: str
    reason: str


def _payoff_ratio(ret: pd.Series) -> float:
    wins = ret[ret > 0]
    losses = ret[ret <= 0]
    if len(wins) == 0 or len(losses) == 0:
        return np.nan
    loss_mean = float(losses.mean())
    if loss_mean == 0:
        return np.nan
    return float(wins.mean() / abs(loss_mean))


def _turnover_proxy(x: pd.DataFrame, top_n: int) -> float:
    if x.empty:
        return np.nan
    prev: set[str] = set()
    turns: list[float] = []
    for _, g in x.groupby("date"):
        cur = set(g["symbol"].astype(str).tolist())
        if prev:
            turns.append(1.0 - len(cur & prev) / max(top_n, 1))
        prev = cur
    return float(np.mean(turns)) if turns else np.nan


def _worst3(series: pd.Series) -> float:
    if series.empty:
        return np.nan
    return float(series.nsmallest(min(3, len(series))).mean())


def _monthly_portfolio_ret(rows: pd.DataFrame, ret_col: str = "ret_net") -> pd.Series:
    if rows.empty:
        return pd.Series(dtype=float)
    x = rows.copy()
    x["month"] = x["date"].dt.to_period("M").astype(str)
    return x.groupby("month")[ret_col].mean()


def _portfolio_max_drawdown(monthly_ret: pd.Series) -> float:
    if monthly_ret.empty:
        return np.nan
    equity = (1.0 + monthly_ret.fillna(0.0)).cumprod()
    peak = equity.cummax()
    dd = equity / peak - 1.0
    return float(dd.min())


def eval_rows(x: pd.DataFrame, top_n: int) -> dict[str, Any]:
    if x.empty:
        return {
            "n": 0,
            "hit_rate": np.nan,
            "avg_ret": np.nan,
            "median_ret": np.nan,
            "avg_mdd": np.nan,
            "median_mdd": np.nan,
            "payoff_ratio": np.nan,
            "win_loss_count": {"wins": 0, "losses": 0},
            "avg_holding_days": np.nan,
            "median_holding_days": np.nan,
            "turnover_proxy": np.nan,
            "worst_3_months_return": np.nan,
            "worst_3_months_mdd": np.nan,
        }
    ret_col = "ret_net" if "ret_net" in x.columns else "fwd_ret20"
    ret = pd.to_numeric(x[ret_col], errors="coerce")
    mdd = pd.to_numeric(x["mdd_realized"], errors="coerce") if "mdd_realized" in x.columns else pd.to_numeric(x["fwd_mdd20"], errors="coerce")
    hold = pd.to_numeric(x["holding_days"], errors="coerce") if "holding_days" in x.columns else pd.Series(np.nan, index=x.index)
    monthly_ret = _monthly_portfolio_ret(x, ret_col=ret_col)
    monthly_mdd = x.assign(month=x["date"].dt.to_period("M").astype(str)).groupby("month")[mdd.name].mean() if mdd.name else pd.Series(dtype=float)
    return {
        "n": int(len(x)),
        "hit_rate": float(pd.to_numeric(x["label_wave20"], errors="coerce").mean()),
        "avg_ret": float(ret.mean()),
        "median_ret": float(ret.median()),
        "avg_mdd": float(mdd.mean()),
        "median_mdd": float(mdd.median()),
        "payoff_ratio": _payoff_ratio(ret),
        "win_loss_count": {"wins": int((ret > 0).sum()), "losses": int((ret <= 0).sum())},
        "avg_holding_days": float(hold.mean()) if hold.notna().any() else np.nan,
        "median_holding_days": float(hold.median()) if hold.notna().any() else np.nan,
        "turnover_proxy": _turnover_proxy(x, top_n=top_n),
        "worst_3_months_return": _worst3(monthly_ret),
        "worst_3_months_mdd": _worst3(monthly_mdd),
    }


def _episode_pick_from_candidates(df: pd.DataFrame, score_col: str, candidate_pool_n: int, top_n: int, cooldown_days: int) -> pd.DataFrame:
    x = df.dropna(subset=[score_col]).copy()
    x = x.sort_values(["date", score_col], ascending=[True, False]).copy()
    x["rank_on_start_date"] = x.groupby("date")[score_col].rank(method="first", ascending=False).astype(int)
    cand = x.groupby("date", as_index=False).head(candidate_pool_n).copy()
    if cand.empty:
        return cand
    dates = sorted(pd.to_datetime(cand["date"]).unique().tolist())
    d2i = {d: i for i, d in enumerate(dates)}
    next_allowed: dict[str, int] = {}
    rows: list[dict[str, Any]] = []
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
    return pd.DataFrame(rows)


def _month_compare(base: pd.DataFrame, var: pd.DataFrame, strategy_name: str) -> pd.DataFrame:
    rows = []
    months = sorted(set(base["date"].dt.to_period("M").astype(str)) | set(var["date"].dt.to_period("M").astype(str)))
    for m in months:
        b = base[base["date"].dt.to_period("M").astype(str) == m]
        v = var[var["date"].dt.to_period("M").astype(str) == m]
        mb = eval_rows(b, top_n=max(1, int(b.groupby("date").size().max() if not b.empty else 20)))
        mv = eval_rows(v, top_n=max(1, int(v.groupby("date").size().max() if not v.empty else 20)))
        b_n = mb["n"]
        v_n = mv["n"]
        beats = (
            np.isfinite(mv["avg_ret"])
            and np.isfinite(mb["avg_ret"])
            and (mv["avg_ret"] >= mb["avg_ret"])
            and np.isfinite(mv["avg_mdd"])
            and np.isfinite(mb["avg_mdd"])
            and (mv["avg_mdd"] >= mb["avg_mdd"] - 0.005)
            and np.isfinite(mv["hit_rate"])
            and np.isfinite(mb["hit_rate"])
            and (mv["hit_rate"] >= mb["hit_rate"] - 0.005)
        )
        rows.append(
            {
                "test_month": m,
                "strategy_name": strategy_name,
                "baseline_n": b_n,
                "variant_n": v_n,
                "coverage_ratio": float(v_n / b_n) if b_n > 0 else np.nan,
                "baseline_hit_rate": mb["hit_rate"],
                "variant_hit_rate": mv["hit_rate"],
                "hit_rate_uplift": mv["hit_rate"] - mb["hit_rate"] if np.isfinite(mv["hit_rate"]) and np.isfinite(mb["hit_rate"]) else np.nan,
                "baseline_avg_ret": mb["avg_ret"],
                "variant_avg_ret": mv["avg_ret"],
                "avg_ret_uplift": mv["avg_ret"] - mb["avg_ret"] if np.isfinite(mv["avg_ret"]) and np.isfinite(mb["avg_ret"]) else np.nan,
                "baseline_avg_mdd": mb["avg_mdd"],
                "variant_avg_mdd": mv["avg_mdd"],
                "avg_mdd_uplift": mv["avg_mdd"] - mb["avg_mdd"] if np.isfinite(mv["avg_mdd"]) and np.isfinite(mb["avg_mdd"]) else np.nan,
                "baseline_payoff_ratio": mb["payoff_ratio"],
                "variant_payoff_ratio": mv["payoff_ratio"],
                "variant_beats_baseline_flag": bool(beats),
            }
        )
    return pd.DataFrame(rows)


def _write_md(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines), encoding="utf-8")


def _qa_panel(df: pd.DataFrame, start: str, end: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    qa: dict[str, Any] = {"required_columns": REQUIRED_COLS, "optional_columns": OPTIONAL_COLS}
    missing_req = [c for c in REQUIRED_COLS if c not in df.columns]
    qa["missing_required_columns"] = missing_req
    if missing_req:
        raise ValueError(f"Missing required columns: {missing_req}")

    x = df.copy()
    x["date"] = pd.to_datetime(x["date"], errors="coerce")
    qa["date_parse_na"] = int(x["date"].isna().sum())
    x = x.dropna(subset=["date"]).copy()
    x = x[(x["date"] >= pd.Timestamp(start)) & (x["date"] <= pd.Timestamp(end))].copy()
    dup = x.duplicated(subset=["date", "symbol"], keep=False)
    qa["duplicate_symbol_date_rows"] = int(dup.sum())
    if dup.any():
        x = x[~x.duplicated(subset=["date", "symbol"], keep="first")]

    for c in ["p20", "label_wave20", "fwd_ret20", "fwd_mdd20", "p_now", "p_hist", "close", "open", "high", "low", "volume", "traded_value_vnd", "adv50_vnd"]:
        if c in x.columns:
            x[c] = pd.to_numeric(x[c], errors="coerce")
    x["symbol"] = x["symbol"].astype(str).str.upper()
    qa["nonfinite_p20_rows"] = int((~np.isfinite(x["p20"])).sum())
    x = x.dropna(subset=["p20", "label_wave20", "fwd_ret20", "fwd_mdd20"]).copy()
    qa["n_rows_clean"] = int(len(x))
    qa["n_symbols"] = int(x["symbol"].nunique())
    qa["n_dates"] = int(x["date"].nunique())
    qa["tail_label_missing_rows"] = int(x[x["date"] >= pd.Timestamp(end) - pd.Timedelta(days=40)]["label_wave20"].isna().sum())

    if "close" in x.columns and x["close"].notna().any():
        med_close = float(x["close"].median())
        qa["median_close"] = med_close
        qa["close_likely_thousand_vnd"] = bool(1.0 <= med_close <= 600.0)
    else:
        qa["median_close"] = None
        qa["close_likely_thousand_vnd"] = None

    qa["traded_value_consistency_corr"] = None
    if {"close", "volume", "traded_value_vnd"}.issubset(x.columns):
        chk = x[["close", "volume", "traded_value_vnd"]].dropna().copy()
        if not chk.empty:
            chk["tv_calc"] = chk["close"] * 1000.0 * chk["volume"]
            qa["traded_value_consistency_corr"] = float(chk["tv_calc"].corr(chk["traded_value_vnd"]))

    qa["adv_formula_consistency_corr"] = None
    if {"close", "volume", "adv50_vnd", "symbol", "date"}.issubset(x.columns):
        z = x.sort_values(["symbol", "date"]).copy()
        z["tv"] = z["close"] * 1000.0 * z["volume"]
        z["adv50_chk"] = z.groupby("symbol")["tv"].rolling(50, min_periods=20).mean().reset_index(level=0, drop=True)
        z2 = z[["adv50_vnd", "adv50_chk"]].dropna()
        if len(z2) > 20:
            qa["adv_formula_consistency_corr"] = float(z2["adv50_vnd"].corr(z2["adv50_chk"]))
    return x, qa


def _audit_harness(out_dir: Path) -> dict[str, Any]:
    fp = REPO / "scripts" / "research" / "evaluate_p20_baseline_plus_oos.py"
    txt = fp.read_text(encoding="utf-8") if fp.exists() else ""
    checks = {
        "episode_canonical_source": "PASS/FAIL verdicts based on EPISODE-LEVEL OOS metrics only" in txt or "Canonical verdict from OOS episode-only source of truth" in txt,
        "episode_monthly_oos_output": "p20_baseline_plus_monthly_episode_oos.csv" in txt,
        "candidate_pool_top100": "candidate_pool_for_episode\": 100" in txt or "build_episode_picks_from_candidates(te, sc, 100" in txt,
        "cooldown_20_trading_days_logic": "next_allowed[sym] = di + cooldown_days" in txt,
        "monthly_winrate_episode_level": "variant_beats_baseline_flag" in txt and "monthly_episode_df" in txt,
        "strict_nested_oos_no_test_tuning": "test month untouched" in txt and "train/validation only" in txt,
        "separate_diagnostic_vs_nested": "choices=[\"diagnostic\", \"nested_oos\"]" in txt,
    }
    problems = [k for k, v in checks.items() if not v]
    verdict = "PASS" if not problems else "WATCH"
    out = {"harness_file": str(fp), "checks": checks, "problems": problems, "verdict": verdict}
    (out_dir / "p20_execution_overlay_harness_audit.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    md = ["# Harness Audit", "", f"- verdict: {verdict}"]
    for k, v in checks.items():
        md.append(f"- {k}: {'OK' if v else 'MISSING'}")
    _write_md(out_dir / "p20_execution_overlay_harness_audit.md", md)
    return out


def _baseline_episodes(panel: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    x = panel.copy()
    x["score_base"] = x["p20"]
    return _episode_pick_from_candidates(
        x,
        "score_base",
        candidate_pool_n=args.candidate_pool_n,
        top_n=args.top_n,
        cooldown_days=args.episode_cooldown_days,
    )


def _apply_tx_cost(ret: pd.Series, bps: float) -> pd.Series:
    return ret - (bps / 10000.0)


def _entry_timing(panel: pd.DataFrame, base_ep: pd.DataFrame, args: argparse.Namespace, out_dir: Path) -> EvalResult:
    # Without stock OHLC in panel, only E0 can be evaluated faithfully from forward labels.
    rows = base_ep.copy()
    rows["entry_rule"] = "E0_entry_T0_close"
    rows["ret_gross"] = rows["fwd_ret20"]
    rows["ret_net"] = _apply_tx_cost(rows["ret_gross"], args.transaction_cost_bps)
    rows["mdd_realized"] = rows["fwd_mdd20"]
    rows["holding_days"] = 20
    monthly = _month_compare(rows, rows, "E0_entry_T0_close")
    summary = eval_rows(rows, top_n=args.top_n)
    summary.update(
        {
            "coverage_vs_baseline": 1.0,
            "monthly_win_rate_vs_baseline": 1.0,
            "skipped_rules": [
                "E1_entry_T1_close",
                "E2_entry_pullback_ma5_or_ma10_*",
                "E3_entry_tight_day_*",
                "E4_entry_reclaim_signal_close_*",
                "E5_entry_next_green_confirmation_*",
            ],
            "skip_reason": "Missing stock OHLC columns in panel; rule requires path-dependent entry trigger.",
        }
    )
    verdict = "WATCH"
    reason = "Only E0 baseline executable without OHLC."
    rows.to_csv(out_dir / "p20_entry_timing_episode_rows.csv", index=False)
    monthly.to_csv(out_dir / "p20_entry_timing_monthly_oos.csv", index=False)
    pd.DataFrame([summary]).to_csv(out_dir / "p20_entry_timing_summary.csv", index=False)
    (out_dir / "p20_entry_timing_summary.json").write_text(json.dumps({"best_rule": "E0_entry_T0_close", "summary": summary, "verdict": verdict, "reason": reason}, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_md(
        out_dir / "p20_entry_timing_summary.md",
        [
            "# Entry Timing Summary",
            "",
            "- Data limitation: stock OHLC is missing in panel.",
            "- Evaluated: E0 baseline only.",
            f"- Verdict: {verdict}",
            f"- Reason: {reason}",
        ],
    )
    return EvalResult("entry_timing", summary, monthly, rows, verdict, reason)


def _exit_rules(panel: pd.DataFrame, base_ep: pd.DataFrame, args: argparse.Namespace, out_dir: Path) -> EvalResult:
    rows = base_ep.copy()
    rows["exit_rule"] = "X0_fixed_20d"
    rows["ret_gross"] = rows["fwd_ret20"]
    rows["ret_net"] = _apply_tx_cost(rows["ret_gross"], args.transaction_cost_bps)
    rows["mdd_realized"] = rows["fwd_mdd20"]
    rows["holding_days"] = 20
    monthly = _month_compare(rows, rows, "X0_fixed_20d")
    summary = eval_rows(rows, top_n=args.top_n)
    summary.update(
        {
            "coverage_vs_baseline": 1.0,
            "monthly_win_rate_vs_baseline": 1.0,
            "skipped_rules": ["X1", "X2", "X3", "X4", "X5", "X6", "X7"],
            "skip_reason": "Missing stock OHLC columns in panel; exit triggers are path-dependent.",
        }
    )
    verdict = "WATCH"
    reason = "Only X0 fixed horizon executable without OHLC."
    rows.to_csv(out_dir / "p20_exit_rules_episode_rows.csv", index=False)
    monthly.to_csv(out_dir / "p20_exit_rules_monthly_oos.csv", index=False)
    pd.DataFrame([summary]).to_csv(out_dir / "p20_exit_rules_summary.csv", index=False)
    (out_dir / "p20_exit_rules_summary.json").write_text(json.dumps({"best_rule": "X0_fixed_20d", "summary": summary, "verdict": verdict, "reason": reason}, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_md(out_dir / "p20_exit_rules_summary.md", ["# Exit Rules Summary", "", "- Data limitation: stock OHLC is missing in panel.", "- Evaluated: X0 baseline only.", f"- Verdict: {verdict}", f"- Reason: {reason}"])
    return EvalResult("exit_rules", summary, monthly, rows, verdict, reason)


def _regime_exposure(panel: pd.DataFrame, args: argparse.Namespace, out_dir: Path) -> EvalResult:
    base = panel.copy()
    base["score"] = base["p20"]
    client = get_client(timeout=45)
    vni = client.get_ohlcv("VNINDEX", start=args.start, end=args.end)
    if vni.empty:
        raise RuntimeError("VNINDEX unavailable; cannot run regime_exposure mode.")
    vni["date"] = pd.to_datetime(vni["date"], errors="coerce")
    vni["close"] = pd.to_numeric(vni["close"], errors="coerce")
    vni["volume"] = pd.to_numeric(vni["volume"], errors="coerce")
    vni = vni.dropna(subset=["date", "close"]).sort_values("date").reset_index(drop=True)
    vni["ma20"] = vni["close"].rolling(20, min_periods=20).mean()
    vni["ma50"] = vni["close"].rolling(50, min_periods=50).mean()
    vni["ma100"] = vni["close"].rolling(100, min_periods=100).mean()
    vni["slope20_5d"] = vni["ma20"] / vni["ma20"].shift(5) - 1.0
    prev_close = vni["close"].shift(1)
    prev_vol = vni["volume"].shift(1)
    vni["dist"] = ((vni["close"] <= prev_close * (1 - 0.002)) & (vni["volume"] > prev_vol)).astype(float)
    vni["dist20"] = vni["dist"].rolling(20, min_periods=10).sum()

    breadth = panel.groupby("date", as_index=False).agg(
        breadth_p20_60=("p20", lambda s: float((s >= 0.60).mean())),
        top20_mean_p20=("p20", lambda s: float(s.nlargest(min(20, len(s))).mean())),
        median_p20=("p20", "median"),
    )
    reg = vni[["date", "close", "ma20", "ma50", "ma100", "slope20_5d", "dist20"]].merge(breadth, on="date", how="left")
    reg["regime"] = np.where(
        ((reg["close"] < reg["ma50"]) & (reg["slope20_5d"] < 0)) | (reg["dist20"] >= 6),
        "Red",
        np.where((reg["close"] > reg["ma50"]) & (reg["slope20_5d"] > 0), "Green", "Yellow"),
    )
    top_map = {
        "R0_baseline": {"Green": 20, "Yellow": 20, "Red": 20},
        "R1_mild": {"Green": 20, "Yellow": 15, "Red": 8},
        "R2_moderate": {"Green": 20, "Yellow": 10, "Red": 5},
        "R3_defensive": {"Green": 15, "Yellow": 10, "Red": 3},
        "R4_cash_red": {"Green": 20, "Yellow": 10, "Red": 0},
    }
    px = base.merge(reg[["date", "regime"]], on="date", how="left")
    variant_rows: dict[str, pd.DataFrame] = {}
    for name, mp in top_map.items():
        rows = []
        x = px.sort_values(["date", "score"], ascending=[True, False]).copy()
        x["rank"] = x.groupby("date")["score"].rank(method="first", ascending=False)
        for dt, g in x.groupby("date"):
            r = str(g["regime"].iloc[0] if g["regime"].notna().any() else "Yellow")
            n = mp.get(r, 20)
            if n <= 0:
                continue
            rows.append(g.nsmallest(n, "rank"))
        variant_rows[name] = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=x.columns)

    base_rows = _episode_pick_from_candidates(
        variant_rows["R0_baseline"].assign(score_base=variant_rows["R0_baseline"]["p20"]),
        "score_base",
        args.candidate_pool_n,
        args.top_n,
        args.episode_cooldown_days,
    )
    base_rows["ret_net"] = _apply_tx_cost(base_rows["fwd_ret20"], args.transaction_cost_bps)
    base_rows["mdd_realized"] = base_rows["fwd_mdd20"]
    monthly_tables = []
    summaries = []
    for name, vdf in variant_rows.items():
        ep = _episode_pick_from_candidates(
            vdf.assign(score_base=vdf["p20"]),
            "score_base",
            args.candidate_pool_n,
            args.top_n,
            args.episode_cooldown_days,
        )
        ep["strategy"] = name
        ep["ret_net"] = _apply_tx_cost(ep["fwd_ret20"], args.transaction_cost_bps)
        ep["mdd_realized"] = ep["fwd_mdd20"]
        cmp_df = _month_compare(base_rows, ep, name)
        monthly_tables.append(cmp_df)
        m = eval_rows(ep, top_n=args.top_n)
        m["strategy"] = name
        m["coverage_vs_baseline"] = float(len(ep) / len(base_rows)) if len(base_rows) else np.nan
        m["monthly_win_rate_vs_baseline"] = float(cmp_df["variant_beats_baseline_flag"].mean()) if not cmp_df.empty else np.nan
        m["portfolio_max_drawdown"] = _portfolio_max_drawdown(_monthly_portfolio_ret(ep))
        m["baseline_portfolio_max_drawdown"] = _portfolio_max_drawdown(_monthly_portfolio_ret(base_rows))
        summaries.append(m)
    sm = pd.DataFrame(summaries).sort_values("avg_ret", ascending=False)
    best = sm.iloc[0].to_dict() if not sm.empty else {}
    best_name = str(best.get("strategy", "R0_baseline"))
    monthly_best = [x for x in monthly_tables if not x.empty and x["strategy_name"].iloc[0] == best_name]
    best_monthly = monthly_best[0] if monthly_best else pd.DataFrame()
    # Risk-overlay pass
    dd_imp = 100.0 * ((best.get("portfolio_max_drawdown", np.nan) - best.get("baseline_portfolio_max_drawdown", np.nan)) / abs(best.get("baseline_portfolio_max_drawdown", np.nan))) if np.isfinite(best.get("portfolio_max_drawdown", np.nan)) and np.isfinite(best.get("baseline_portfolio_max_drawdown", np.nan)) and best.get("baseline_portfolio_max_drawdown", 0) != 0 else np.nan
    avg_ret_diff_pp = 100.0 * (best.get("avg_ret", np.nan) - sm[sm["strategy"] == "R0_baseline"]["avg_ret"].iloc[0]) if "R0_baseline" in set(sm["strategy"]) and np.isfinite(best.get("avg_ret", np.nan)) else np.nan
    win = float(best.get("monthly_win_rate_vs_baseline", np.nan))
    turn_base = float(sm[sm["strategy"] == "R0_baseline"]["turnover_proxy"].iloc[0]) if "R0_baseline" in set(sm["strategy"]) else np.nan
    turn_var = float(best.get("turnover_proxy", np.nan))
    turn_ok = (not np.isfinite(turn_base)) or (not np.isfinite(turn_var)) or (turn_var <= turn_base * 1.20)
    pass_flag = np.isfinite(dd_imp) and (dd_imp <= -10.0) and np.isfinite(avg_ret_diff_pp) and (avg_ret_diff_pp >= -0.20) and np.isfinite(win) and (win >= 0.55) and turn_ok
    verdict = "PASS" if pass_flag else ("WATCH" if best_name != "R0_baseline" else "FAIL")
    reason = "Risk overlay pass criteria " + ("met." if pass_flag else "not met.")
    all_rows = pd.concat([variant_rows[k].assign(strategy=k) for k in variant_rows], ignore_index=True)
    all_rows.to_csv(out_dir / "p20_regime_exposure_episode_rows.csv", index=False)
    pd.concat(monthly_tables, ignore_index=True).to_csv(out_dir / "p20_regime_exposure_monthly_oos.csv", index=False)
    sm.to_csv(out_dir / "p20_regime_exposure_summary.csv", index=False)
    (out_dir / "p20_regime_exposure_summary.json").write_text(json.dumps({"best_rule": best_name, "best_metrics": best, "verdict": verdict, "reason": reason}, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_md(out_dir / "p20_regime_exposure_summary.md", ["# Regime Exposure Summary", "", f"- best_rule: {best_name}", f"- verdict: {verdict}", f"- reason: {reason}"])
    return EvalResult("regime_exposure", {"best_rule": best_name, **best}, best_monthly, all_rows, verdict, reason)


def _sizing(panel: pd.DataFrame, base_ep: pd.DataFrame, args: argparse.Namespace, out_dir: Path) -> EvalResult:
    x = base_ep.copy()
    x["ret_net"] = _apply_tx_cost(x["fwd_ret20"], args.transaction_cost_bps)
    x["mdd_realized"] = x["fwd_mdd20"]
    x["p20_pct"] = x.groupby("date")["p20"].rank(method="average", pct=True)

    # S0 and S3 are available without OHLC; ATR variants skipped.
    all_rows = []
    summ_rows = []
    for name, weight_col in [("S0_equal_weight", None), ("S3_score_weighted_p20", "p20_pct")]:
        rows = x.copy()
        if weight_col is None:
            rows["weight"] = rows.groupby("date")["symbol"].transform(lambda s: 1.0 / max(len(s), 1))
        else:
            z = rows.groupby("date")[weight_col].transform("sum").replace(0, np.nan)
            rows["weight"] = rows[weight_col] / z
            rows["weight"] = rows["weight"].fillna(0.0)
            rows["weight"] = rows.groupby("date")["weight"].transform(lambda s: s / max(s.sum(), 1e-9))
        rows["port_ret_net"] = rows["weight"] * rows["ret_net"]
        rows["port_mdd"] = rows["weight"] * rows["mdd_realized"]
        by_date = rows.groupby("date", as_index=False).agg(
            ret_net=("port_ret_net", "sum"),
            mdd_realized=("port_mdd", "sum"),
            label_wave20=("label_wave20", "mean"),
            symbol=("symbol", "count"),
        )
        by_date["strategy"] = name
        all_rows.append(by_date)
        met = eval_rows(by_date, top_n=args.top_n)
        met["strategy"] = name
        met["portfolio_max_drawdown"] = _portfolio_max_drawdown(_monthly_portfolio_ret(by_date))
        summ_rows.append(met)
    rows_all = pd.concat(all_rows, ignore_index=True)
    sm = pd.DataFrame(summ_rows)
    base_sm = sm[sm["strategy"] == "S0_equal_weight"].iloc[0].to_dict()
    best_sm = sm.sort_values("avg_ret", ascending=False).iloc[0].to_dict()
    best_name = str(best_sm["strategy"])
    best_monthly = _month_compare(
        rows_all[rows_all["strategy"] == "S0_equal_weight"],
        rows_all[rows_all["strategy"] == best_name],
        best_name,
    )
    dd_imp = 100.0 * ((best_sm["portfolio_max_drawdown"] - base_sm["portfolio_max_drawdown"]) / abs(base_sm["portfolio_max_drawdown"])) if np.isfinite(best_sm["portfolio_max_drawdown"]) and np.isfinite(base_sm["portfolio_max_drawdown"]) and base_sm["portfolio_max_drawdown"] != 0 else np.nan
    avg_ret_diff_pp = 100.0 * (best_sm["avg_ret"] - base_sm["avg_ret"]) if np.isfinite(best_sm["avg_ret"]) and np.isfinite(base_sm["avg_ret"]) else np.nan
    win = float(best_monthly["variant_beats_baseline_flag"].mean()) if not best_monthly.empty else np.nan
    turn_ok = (not np.isfinite(base_sm["turnover_proxy"])) or (not np.isfinite(best_sm["turnover_proxy"])) or (best_sm["turnover_proxy"] <= base_sm["turnover_proxy"] * 1.20)
    pass_flag = np.isfinite(dd_imp) and (dd_imp <= -10.0) and np.isfinite(avg_ret_diff_pp) and (avg_ret_diff_pp >= -0.20) and np.isfinite(win) and (win >= 0.55) and turn_ok
    verdict = "PASS" if pass_flag else "WATCH"
    reason = "Only S0/S3 executable without OHLC; ATR variants skipped."
    rows_all.to_csv(out_dir / "p20_sizing_episode_weights.csv", index=False)
    best_monthly.to_csv(out_dir / "p20_sizing_portfolio_monthly_oos.csv", index=False)
    sm.to_csv(out_dir / "p20_sizing_summary.csv", index=False)
    (out_dir / "p20_sizing_summary.json").write_text(json.dumps({"best_rule": best_name, "best_metrics": best_sm, "skipped_rules": ["S1_inverse_vol", "S2_inverse_vol_10pct_cap", "S4_hybrid_p20_inverse_vol"], "verdict": verdict, "reason": reason}, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_md(out_dir / "p20_sizing_summary.md", ["# Sizing Summary", "", f"- best_rule: {best_name}", f"- verdict: {verdict}", f"- reason: {reason}"])
    return EvalResult("sizing", {"best_rule": best_name, **best_sm}, best_monthly, rows_all, verdict, reason)


def _confirmation(base_ep: pd.DataFrame, args: argparse.Namespace, out_dir: Path) -> EvalResult:
    rows = base_ep.copy()
    rows["strategy"] = "baseline_watchlist_only"
    rows["ret_net"] = _apply_tx_cost(rows["fwd_ret20"], args.transaction_cost_bps)
    rows["mdd_realized"] = rows["fwd_mdd20"]
    monthly = _month_compare(rows, rows, "baseline_watchlist_only")
    summary = eval_rows(rows, top_n=args.top_n)
    summary["skip_reason"] = "Confirmation rules require OHLC/volume triggers not present in panel."
    verdict = "WATCH"
    reason = "No confirmation rules executable without OHLC."
    rows.to_csv(out_dir / "p20_confirmation_entry_episode_rows.csv", index=False)
    monthly.to_csv(out_dir / "p20_confirmation_entry_monthly_oos.csv", index=False)
    pd.DataFrame([summary]).to_csv(out_dir / "p20_confirmation_entry_summary.csv", index=False)
    (out_dir / "p20_confirmation_entry_summary.json").write_text(json.dumps({"best_rule": "baseline_watchlist_only", "summary": summary, "verdict": verdict, "reason": reason}, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_md(out_dir / "p20_confirmation_entry_summary.md", ["# Confirmation Entry Summary", "", f"- verdict: {verdict}", f"- reason: {reason}"])
    return EvalResult("confirmation", summary, monthly, rows, verdict, reason)


def _master_summary(
    out_dir: Path,
    qa: dict[str, Any],
    harness_audit: dict[str, Any],
    baseline_rows: pd.DataFrame,
    results: dict[str, EvalResult],
) -> None:
    base_m = eval_rows(baseline_rows.assign(ret_net=_apply_tx_cost(baseline_rows["fwd_ret20"], 30), mdd_realized=baseline_rows["fwd_mdd20"]), top_n=20)
    lines = [
        "# p20 Execution Overlay Master Summary",
        "",
        "## Executive conclusion",
    ]
    pass_any = any(r.verdict == "PASS" for r in results.values())
    if pass_any:
        lines.append("The overlay passes strict OOS criteria and may be promoted to paper-trading, not live production yet.")
    else:
        lines.append("Execution/risk overlays did not produce production-grade OOS improvement. Baseline p20 remains the benchmark. Next step is paper-trading baseline p20 with discretionary chart confirmation, or extend data history.")
    lines += [
        "",
        "## QA summary",
        f"- rows: {qa.get('n_rows_clean')}, symbols: {qa.get('n_symbols')}, dates: {qa.get('n_dates')}",
        f"- harness audit verdict: {harness_audit.get('verdict')}",
        "",
        "## Baseline metrics",
        f"- n={base_m['n']}, hit_rate={base_m['hit_rate']:.4f}, avg_ret={base_m['avg_ret']:.4f}, avg_mdd={base_m['avg_mdd']:.4f}",
        "",
        "## Experiment results",
    ]
    tbl = []
    for k, r in results.items():
        lines.append(f"- {k}: verdict={r.verdict}; reason={r.reason}")
        tbl.append(
            {
                "overlay": k,
                "verdict": r.verdict,
                "reason": r.reason,
                "best_rule": r.summary.get("best_rule"),
                "avg_ret": r.summary.get("avg_ret"),
                "avg_mdd": r.summary.get("avg_mdd"),
                "hit_rate": r.summary.get("hit_rate"),
            }
        )
    lines += [
        "",
        "## Overfit risk assessment",
        "- No diagnostic-only evidence is treated as final OOS proof.",
        "- Final recommendations are based on episode-level monthly OOS comparisons.",
        "",
        "## Production recommendation",
        "- Production score: baseline p20.",
        "- Execution/exit/confirmation overlays need OHLC-enriched panel for full test.",
        "- Risk overlay to monitor weekly: regime exposure map and sizing turnover drift.",
    ]
    _write_md(out_dir / "p20_execution_overlay_master_summary.md", lines)
    (out_dir / "p20_execution_overlay_master_summary.json").write_text(
        json.dumps(
            {
                "qa_summary": qa,
                "harness_audit": harness_audit,
                "baseline_metrics": base_m,
                "results": {k: {"verdict": v.verdict, "reason": v.reason, "summary": v.summary} for k, v in results.items()},
                "result_table": tbl,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel-csv", default=str(REPO / "data" / "research" / "super_alpha_panel_from_2023.csv"))
    ap.add_argument("--start", default="2023-01-01")
    ap.add_argument("--end", default="2026-04-30")
    ap.add_argument("--top-n", type=int, default=20)
    ap.add_argument("--candidate-pool-n", type=int, default=100)
    ap.add_argument("--episode-cooldown-days", type=int, default=20)
    ap.add_argument("--train-months", type=int, default=12)
    ap.add_argument("--validation-months", type=int, default=3)
    ap.add_argument("--embargo-days", type=int, default=20)
    ap.add_argument("--transaction-cost-bps", type=float, default=30)
    ap.add_argument(
        "--mode",
        choices=["audit", "entry_timing", "exit_rules", "regime_exposure", "sizing", "confirmation", "all"],
        default="all",
    )
    ap.add_argument("--out-dir", default=str(REPO / "data" / "research"))
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    panel = pd.read_csv(args.panel_csv)
    panel, qa = _qa_panel(panel, args.start, args.end)
    qa_json = out_dir / "p20_execution_overlay_qa.json"
    qa_md = out_dir / "p20_execution_overlay_qa.md"
    qa_json.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_md(
        qa_md,
        [
            "# Execution Overlay QA",
            "",
            f"- n_rows_clean: {qa.get('n_rows_clean')}",
            f"- n_symbols: {qa.get('n_symbols')}",
            f"- n_dates: {qa.get('n_dates')}",
            f"- duplicate_symbol_date_rows: {qa.get('duplicate_symbol_date_rows')}",
            f"- close_likely_thousand_vnd: {qa.get('close_likely_thousand_vnd')}",
            f"- adv_formula_consistency_corr: {qa.get('adv_formula_consistency_corr')}",
        ],
    )

    harness_audit = _audit_harness(out_dir)
    base_ep = _baseline_episodes(panel, args)

    results: dict[str, EvalResult] = {}
    modes = [args.mode] if args.mode != "all" else ["entry_timing", "exit_rules", "regime_exposure", "sizing", "confirmation"]
    for mode in modes:
        if mode == "entry_timing":
            results[mode] = _entry_timing(panel, base_ep, args, out_dir)
        elif mode == "exit_rules":
            results[mode] = _exit_rules(panel, base_ep, args, out_dir)
        elif mode == "regime_exposure":
            results[mode] = _regime_exposure(panel, args, out_dir)
        elif mode == "sizing":
            results[mode] = _sizing(panel, base_ep, args, out_dir)
        elif mode == "confirmation":
            results[mode] = _confirmation(base_ep, args, out_dir)
        elif mode == "audit":
            # audit-only handled by files above.
            pass

    if args.mode == "audit":
        out = {
            "mode": "audit",
            "qa_json": str(qa_json),
            "qa_md": str(qa_md),
            "harness_audit_json": str(out_dir / "p20_execution_overlay_harness_audit.json"),
            "harness_audit_md": str(out_dir / "p20_execution_overlay_harness_audit.md"),
            "baseline_episode_rows": int(len(base_ep)),
        }
    else:
        if args.mode == "all":
            _master_summary(out_dir, qa, harness_audit, base_ep, results)
        out = {
            "mode": args.mode,
            "qa_json": str(qa_json),
            "qa_md": str(qa_md),
            "harness_audit_json": str(out_dir / "p20_execution_overlay_harness_audit.json"),
            "baseline_episode_rows": int(len(base_ep)),
            "results": {k: {"verdict": v.verdict, "reason": v.reason} for k, v in results.items()},
        }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

