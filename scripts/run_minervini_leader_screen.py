from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from src.canslim.fireant_fetcher import fetch_all_symbols, fetch_ohlcv
from src.data.fireant_client import get_client, reset_client
from src.screeners.minervini_metrics import (
    ScreenerConfig,
    add_indicators,
    compute_rs,
    compute_volume_profile_metrics,
    detect_best_base,
    normalize_ohlcv,
    score_ticker,
)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run Minervini/O'Neil leader screen on Vietnam market using FireAnt.")
    p.add_argument("--asof-date", default=None)
    p.add_argument("--universe", choices=["all", "hose", "hnx", "upcom"], default="all")
    p.add_argument("--min-avg-value", type=float, default=2_000_000_000)
    p.add_argument("--daily-lookback", type=int, default=260)
    p.add_argument("--weekly-lookback", type=int, default=156)
    p.add_argument("--vp-bins", type=int, default=100)
    p.add_argument("--value-area-pct", type=float, default=0.70)
    p.add_argument("--top-n", type=int, default=50)
    p.add_argument("--calibration", choices=["strict", "balanced", "aggressive", "adaptive"], default="adaptive")
    p.add_argument("--target-leaders", type=int, default=10)
    return p.parse_args()


def _json_safe(v: Any) -> Any:
    if isinstance(v, (np.float64, np.float32, float)):
        if np.isnan(v) or np.isinf(v):
            return None
        return float(v)
    if isinstance(v, (np.int64, np.int32, int)):
        return int(v)
    if isinstance(v, (pd.Timestamp, datetime, date)):
        return pd.Timestamp(v).strftime("%Y-%m-%d")
    return v


def _load_local_universe_fallback() -> List[str]:
    candidates = [
        Path("config/universe_liquid_adv50_2b.txt"),
        Path("config/universe_186.txt"),
        Path("config/universe_full_from_user.txt"),
    ]
    out: Dict[str, None] = {}
    for fp in candidates:
        if not fp.exists():
            continue
        for line in fp.read_text(encoding="utf-8").splitlines():
            s = line.strip().upper()
            if s and not s.startswith("#"):
                out[s] = None
    return sorted(out.keys())


def _get_universe(universe: str) -> Tuple[List[str], List[str]]:
    preferred_liquid = Path("config/universe_liquid_adv50_2b.txt")
    if universe == "all" and preferred_liquid.exists():
        syms = [x.strip().upper() for x in preferred_liquid.read_text(encoding="utf-8").splitlines() if x.strip() and not x.strip().startswith("#")]
        return sorted(set(syms)), ["using_repo_liquid_universe_file"]

    boards = ["HOSE", "HNX", "UPCOM"] if universe == "all" else [universe.upper()]
    out: Dict[str, None] = {}
    warnings: List[str] = []
    for b in boards:
        for s in fetch_all_symbols(b):
            sym = str(s).strip().upper()
            if sym:
                out[sym] = None
    symbols = sorted(out.keys())
    if not symbols:
        symbols = _load_local_universe_fallback()
        warnings.append("market_board_symbol_list_unavailable_using_repo_universe_fallback")
    return symbols, warnings


def _is_common_stock_symbol(sym: str) -> bool:
    s = sym.upper()
    # Exclude common VN ETF/fund/index product prefixes.
    if s.startswith("FUE") or s.startswith("E1") or s.startswith("FU"):
        return False
    return True


def _get_date_range(asof_date: str, daily_lookback: int, weekly_lookback: int) -> Tuple[str, str]:
    end = pd.Timestamp(asof_date)
    # include buffer for holidays/non-trading days
    days_back = max(int(daily_lookback * 2.2), int(weekly_lookback * 7 * 1.3), 520)
    start = end - timedelta(days=days_back)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _passes_leader_filter(row: Dict[str, Any], warnings: List[str]) -> bool:
    severe = {"insufficient_data", "abnormal_corporate_action_not_adjusted", "median_traded_value_unstable", "missing_benchmark_alignment"}
    severe_hit = any(w in severe for w in warnings)
    return (
        row["avg_value_50"] is not None
        and row["avg_value_50"] > 2_000_000_000
        and row["total_score"] >= 14
        and row["rs_score"] >= 1
        and row["trend_score"] >= 1
        and row["tightness_score"] >= 1
        and row["base_score"] >= 1
        and not severe_hit
    )


def _status_label(row: Dict[str, Any]) -> str:
    if row["pivot_score"] == 2:
        return "breakout-ready"
    if row["pivot_score"] == 1:
        return "near pivot"
    if row["tightness_score"] < 1:
        return "needs tightening"
    if row["close"] and row["ma50"] and row["close"] > 1.25 * row["ma50"]:
        return "extended"
    return "avoid chase"


def run() -> Dict[str, Any]:
    args = _parse_args()
    asof = args.asof_date or pd.Timestamp.today().strftime("%Y-%m-%d")
    cfg = ScreenerConfig(
        min_avg_value=args.min_avg_value,
        daily_lookback=args.daily_lookback,
        weekly_lookback=args.weekly_lookback,
        vp_bins=args.vp_bins,
        value_area_pct=args.value_area_pct,
    )
    start, end = _get_date_range(asof, cfg.daily_lookback, cfg.weekly_lookback)
    universe, global_warnings = _get_universe(args.universe)
    reset_client()
    get_client(timeout=5, cache_ttl=3600)

    vnindex_raw = fetch_ohlcv("VNINDEX", start=start, end=end, resolution="D")
    vnindex = add_indicators(vnindex_raw)

    leaders_rows: List[Dict[str, Any]] = []
    leaders_json: List[Dict[str, Any]] = []
    liquid_scored_rows: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    chosen_profile = "strict"
    if args.calibration == "adaptive":
        profiles = ["strict", "balanced", "aggressive"]
    else:
        profiles = [args.calibration]

    raw_cache: Dict[str, Tuple[pd.DataFrame, pd.DataFrame]] = {}

    fail_streak = 0
    for ticker in universe:
        if not _is_common_stock_symbol(ticker):
            rejected.append({"ticker": ticker, "reason": "non_stock_instrument"})
            continue
        warnings: List[str] = ["unadjusted_price_data"] + global_warnings
        errors: List[str] = []
        try:
            d_raw = fetch_ohlcv(ticker, start=start, end=end, resolution="D")
            d = add_indicators(d_raw)
            w = (
                add_indicators(
                    normalize_ohlcv(d_raw)
                    .set_index("date")
                    .resample("W-FRI")
                    .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
                    .dropna()
                    .reset_index()
                )
                if d_raw is not None and not d_raw.empty
                else pd.DataFrame()
            )
        except Exception as exc:  # pragma: no cover
            d = pd.DataFrame()
            w = pd.DataFrame()
            errors.append(str(exc))
        if d.empty:
            fail_streak += 1
        else:
            fail_streak = 0
            raw_cache[ticker] = (d.copy(), w.copy())
        if fail_streak >= 40:
            global_warnings.append("too_many_consecutive_fetch_failures_stopping_early")
            break

        if d.empty or len(d) < 120:
            rejected.append({"ticker": ticker, "reason": "insufficient_data"})
            continue

        required = {"open", "high", "low", "close", "volume"}
        if not required.issubset(set(d.columns)) or d[["open", "high", "low", "close", "volume"]].isna().any(axis=None):
            rejected.append({"ticker": ticker, "reason": "missing_ohlcv"})
            continue

        # FireAnt prices for VN stocks may be in thousand-VND units; scale trading value to VND.
        price_scale = 1000.0 if float(d["close"].tail(120).median()) < 1000 else 1.0
        if price_scale != 1.0:
            warnings.append("price_unit_detected_kvnd_scaled_to_vnd_for_value_metrics")
        avg_value_50 = float((d["close"] * price_scale * d["volume"]).rolling(50, min_periods=50).mean().iloc[-1])
        if not np.isfinite(avg_value_50) or avg_value_50 <= cfg.min_avg_value:
            rejected.append({"ticker": ticker, "reason": "avg_value_50_below_threshold"})
            continue

        if (d.tail(50)["volume"] == 0).sum() > 10:
            warnings.append("suspended_or_illiquid_recently")

        # defer scoring; first pass validates liquidity/data only
        pass

    liquid_tickers = [t for t in raw_cache.keys()]
    best_pack: Dict[str, Any] = {"leaders_rows": [], "leaders_json": [], "scored_rows": [], "rejected": list(rejected), "profile": "strict"}

    for prof in profiles:
        _leaders_rows: List[Dict[str, Any]] = []
        _leaders_json: List[Dict[str, Any]] = []
        _scored: List[Dict[str, Any]] = []
        _rejected = [x for x in rejected if x["reason"] != "failed_min_score"]

        for ticker in liquid_tickers:
            d, w = raw_cache[ticker]
            warnings = ["unadjusted_price_data"] + global_warnings
            row = d.iloc[-1]
            price_scale = 1000.0 if float(d["close"].tail(120).median()) < 1000 else 1.0
            avg_value_50 = float((d["close"] * price_scale * d["volume"]).rolling(50, min_periods=50).mean().iloc[-1])
            rs_df = compute_rs(d, vnindex) if not vnindex.empty else pd.DataFrame()
            if rs_df.empty:
                warnings.append("missing_benchmark_alignment")
            vp = compute_volume_profile_metrics(d, cfg.vp_bins, cfg.value_area_pct)
            base = detect_best_base(d)
            if not base:
                warnings.append("insufficient_data_for_base_detection")
            score = score_ticker(d, rs_df, w, vp, base, profile=prof)
            warnings.extend(score["warnings"])
            short_vp, mid_vp = vp["short"], vp["mid"]
            out_row = {
                "ticker": ticker.upper(), "close": _json_safe(row["close"]), "avg_value_50": _json_safe(avg_value_50),
                "total_score": score["total_score"], "grade": score["grade"],
                "trend_score": score["scores"]["trend"], "base_score": score["scores"]["base"], "tightness_score": score["scores"]["tightness"],
                "volume_dryup_score": score["scores"]["volume_dryup"], "pivot_score": score["scores"]["pivot"], "rs_score": score["scores"]["rs"],
                "vsa_score": score["scores"]["vsa"], "obv_cmf_score": score["scores"]["obv_cmf"], "macd_score": score["scores"]["macd"], "vp_score": score["scores"]["vp"],
                "rs_20": _json_safe(score["extras"]["rs_20"]), "rs_60": _json_safe(score["extras"]["rs_60"]), "atr14_pct": _json_safe(row["atr14_pct"]),
                "range10_pct": _json_safe(row["range10_pct"]), "close_stdev5_pct": _json_safe(row["close_stdev5_pct"]), "base_depth_pct": _json_safe(base.get("base_depth_pct")),
                "distance_to_pivot": _json_safe(base.get("distance_to_pivot")), "pivot": _json_safe(base.get("pivot")), "ma20": _json_safe(row["ma20"]),
                "ma50": _json_safe(row["ma50"]), "ma100": _json_safe(row["ma100"]), "ma150": _json_safe(row["ma150"]), "ma200": _json_safe(row["ma200"]),
                "cmf20": _json_safe(row["cmf20"]), "macd": _json_safe(row["macd"]), "signal": _json_safe(row["signal"]), "histogram": _json_safe(row["histogram"]),
                "short_poc": _json_safe(short_vp["poc"]), "short_val": _json_safe(short_vp["val"]), "short_vah": _json_safe(short_vp["vah"]),
                "mid_poc": _json_safe(mid_vp["poc"]), "mid_val": _json_safe(mid_vp["val"]), "mid_vah": _json_safe(mid_vp["vah"]),
                "main_support": _json_safe(short_vp["val"] if short_vp["val"] is not None else row["ma50"]),
                "main_resistance": _json_safe(base.get("pivot") if base.get("pivot") else short_vp["vah"]), "warnings": ";".join(sorted(set(warnings))),
            }
            _scored.append(out_row)
            _leaders_json.append({"ticker": ticker.upper(), "latest_date": _json_safe(row["date"]), "scores": score["scores"], "total_score": score["total_score"], "grade": score["grade"], "computed_metrics": {k: _json_safe(v) for k, v in out_row.items() if k not in {"ticker", "grade", "warnings"}}, "warnings": sorted(set(warnings)), "errors": [], "interpretation": f"{ticker} scored {score['total_score']}/20 under {prof} profile"})
            if out_row["total_score"] < 14:
                _rejected.append({"ticker": ticker, "reason": "failed_min_score"})
                continue
            if any(x in warnings for x in ["insufficient_data", "missing_benchmark_alignment"]):
                _rejected.append({"ticker": ticker, "reason": "severe_warning"})
                continue
            _leaders_rows.append(out_row)

        if len(_leaders_rows) >= args.target_leaders:
            chosen_profile = prof
            best_pack = {"leaders_rows": _leaders_rows, "leaders_json": _leaders_json, "scored_rows": _scored, "rejected": _rejected, "profile": prof}
            break
        if len(_leaders_rows) > len(best_pack["leaders_rows"]):
            chosen_profile = prof
            best_pack = {"leaders_rows": _leaders_rows, "leaders_json": _leaders_json, "scored_rows": _scored, "rejected": _rejected, "profile": prof}

    leaders_rows = best_pack["leaders_rows"]
    leaders_json = best_pack["leaders_json"]
    liquid_scored_rows = best_pack["scored_rows"]
    rejected = best_pack["rejected"]

    leaders_df = pd.DataFrame(leaders_rows)
    if not leaders_df.empty:
        leaders_df = leaders_df.sort_values(["total_score", "avg_value_50"], ascending=[False, False]).reset_index(drop=True)
    top_df = leaders_df.head(args.top_n).copy() if not leaders_df.empty else leaders_df

    out_dir = Path("artifacts") / "minervini_leader_screen" / asof
    out_dir.mkdir(parents=True, exist_ok=True)
    leaders_csv = out_dir / "leaders_ranked.csv"
    leaders_json_fp = out_dir / "leaders_ranked.json"
    summary_md = out_dir / "top_leaders_summary.md"
    rejected_csv = out_dir / "rejected_summary.csv"

    req_cols = [
        "ticker", "close", "avg_value_50", "total_score", "grade",
        "trend_score", "base_score", "tightness_score", "volume_dryup_score",
        "pivot_score", "rs_score", "vsa_score", "obv_cmf_score", "macd_score", "vp_score",
        "rs_20", "rs_60", "atr14_pct", "range10_pct", "close_stdev5_pct",
        "base_depth_pct", "distance_to_pivot", "pivot",
        "ma20", "ma50", "ma100", "ma150", "ma200",
        "cmf20", "macd", "signal", "histogram",
        "short_poc", "short_val", "short_vah", "mid_poc", "mid_val", "mid_vah",
        "main_support", "main_resistance", "warnings",
    ]
    if top_df.empty:
        pd.DataFrame(columns=req_cols).to_csv(leaders_csv, index=False)
    else:
        for c in req_cols:
            if c not in top_df.columns:
                top_df[c] = None
        top_df[req_cols].to_csv(leaders_csv, index=False)

    leaders_json_fp.write_text(json.dumps(leaders_json, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(rejected).to_csv(rejected_csv, index=False)

    md_lines = ["# Top Minervini/O'Neil Leaders", "", f"As of: **{asof}**", ""]
    for r in top_df.head(args.top_n).to_dict(orient="records"):
        status = _status_label(r)
        why = []
        if r["trend_score"] >= 1:
            why.append("trend template holds")
        if r["rs_score"] >= 1:
            why.append("relative strength positive")
        if r["tightness_score"] >= 1:
            why.append("tightness/base contraction present")
        risks = []
        if r["vp_score"] == 0:
            risks.append("overhead volume profile resistance")
        if r["macd_score"] == 0:
            risks.append("momentum not confirmed")
        if not risks:
            risks.append("watch for failed breakout risk")
        md_lines.extend(
            [
                f"## {r['ticker']}",
                f"- Total score: **{r['total_score']}** ({r['grade']})",
                f"- Why passed: {', '.join(why) if why else 'unclear'}",
                f"- Key risks: {', '.join(risks)}",
                f"- Actionable status: **{status}**",
                f"- Key levels: pivot={r.get('pivot')}, support={r.get('main_support')}, invalidation={r.get('main_support')}, resistance={r.get('main_resistance')}",
                "",
            ]
        )
    summary_md.write_text("\n".join(md_lines), encoding="utf-8")

    # Validation checks requested by user
    if not leaders_df.empty:
        if not ((leaders_df["total_score"] >= 0) & (leaders_df["total_score"] <= 20)).all():
            raise ValueError("score validation failed: total_score out of 0..20 range")
        required = ["ticker", "close", "avg_value_50", "total_score", "grade"]
        for _, rr in leaders_df.iterrows():
            miss = any(pd.isna(rr[c]) for c in required)
            warn = isinstance(rr.get("warnings"), str) and rr.get("warnings")
            if miss and not warn:
                raise ValueError("required field contains NaN without warning")
        if not (leaders_df["avg_value_50"] > cfg.min_avg_value).all():
            raise ValueError("liquidity filter validation failed")
    for fp in [leaders_csv, leaders_json_fp, summary_md, rejected_csv]:
        if not fp.exists():
            raise FileNotFoundError(f"missing output artifact: {fp}")

    scored_df = pd.DataFrame(liquid_scored_rows)
    if not scored_df.empty:
        scored_df = scored_df.sort_values(["total_score", "avg_value_50"], ascending=[False, False]).reset_index(drop=True)

    return {
        "output_dir": str(out_dir),
        "leaders_csv": str(leaders_csv),
        "leaders_json": str(leaders_json_fp),
        "summary_md": str(summary_md),
        "rejected_csv": str(rejected_csv),
        "top20": scored_df.head(20)[["ticker", "total_score", "grade"]].to_dict(orient="records") if not scored_df.empty else [],
        "major_warnings_count": int(sum(1 for x in rejected if x["reason"] == "severe_warning")),
        "failed_tickers_count": len(rejected),
        "universe_size": len(universe),
        "calibration_profile_used": chosen_profile,
    }


if __name__ == "__main__":
    res = run()
    print(json.dumps(res, ensure_ascii=False, indent=2))

