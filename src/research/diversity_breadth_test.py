"""Gate B statistical tests for diversity-weighted breadth indicator.

RESEARCH_ONLY — pre-registered gates in knowledge/research_backlog.md §1 Gate B.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from src.research.diversity_breadth import (
    DEFAULT_OUT_DIR,
    RESEARCH_ONLY_LABEL,
    _repo_root,
)

logger = logging.getLogger(__name__)

DEFAULT_VNINDEX_PATH = Path("data/fireant_ssot/ta_vnindex.parquet")
DEFAULT_REGIME_LOG = Path("data/regime_log_2012_now.csv")
ROLLING_WINDOW_MONTHS = 36
GATE_R_THRESHOLD = 0.15
GATE_HIT_RATE_THRESHOLD = 0.55
GATE_ROLLING_PCT_THRESHOLD = 0.50
MIN_OBS_FOR_TEST = 24


def load_vnindex_monthly_returns(vnindex_path: Path | None = None) -> pd.DataFrame:
    """Monthly open-to-open VNINDEX returns aligned to diversity rebalance calendar."""
    root = _repo_root()
    path = vnindex_path or (root / DEFAULT_VNINDEX_PATH)
    idx = pd.read_parquet(path)
    idx["date"] = pd.to_datetime(idx["date"]).dt.normalize()
    idx = idx.sort_values("date").drop_duplicates("date")

    trading_dates = pd.DatetimeIndex(idx["date"])
    month_ends = pd.Series(trading_dates, index=trading_dates).groupby(
        trading_dates.to_period("M")
    ).max()

    rows: list[dict] = []
    reb_dates = list(month_ends.values)
    for i, reb in enumerate(reb_dates[:-1]):
        next_reb = reb_dates[i + 1]
        entry = trading_dates[trading_dates > reb]
        exit_ = trading_dates[trading_dates > next_reb]
        if len(entry) == 0 or len(exit_) == 0:
            continue
        e_open = float(idx.loc[idx["date"] == entry[0], "open"].iloc[0])
        x_open = float(idx.loc[idx["date"] == exit_[0], "open"].iloc[0])
        if e_open <= 0:
            continue
        rows.append(
            {
                "date": pd.Timestamp(reb),
                "vnindex_ret": x_open / e_open - 1.0,
            }
        )
    return pd.DataFrame(rows)


def _align_spread_forward_index(
    diversity: pd.DataFrame,
    vnindex_monthly: pd.DataFrame,
    spread_col: str = "spread_p050_vs_p100",
) -> pd.DataFrame:
    d = diversity[["date", spread_col]].copy()
    d["date"] = pd.to_datetime(d["date"]).dt.normalize()
    v = vnindex_monthly.copy()
    v["date"] = pd.to_datetime(v["date"]).dt.normalize()
    merged = d.merge(v, on="date", how="inner")
    merged = merged.rename(columns={spread_col: "spread", "vnindex_ret": "vnindex_ret_same_period"})
    merged = merged.sort_values("date").reset_index(drop=True)
    merged["vnindex_ret_fwd"] = merged["vnindex_ret_same_period"].shift(-1)
    return merged.dropna(subset=["spread", "vnindex_ret_fwd"])


def test_correlation(aligned: pd.DataFrame) -> dict[str, Any]:
    if len(aligned) < MIN_OBS_FOR_TEST:
        return {
            "n": len(aligned),
            "r": None,
            "p_value": None,
            "status": "INSUFFICIENT_DATA",
        }
    r, p = stats.pearsonr(aligned["spread"], aligned["vnindex_ret_fwd"])
    return {
        "n": int(len(aligned)),
        "r": float(r),
        "p_value": float(p),
        "status": "OK",
    }


def test_hit_rate(aligned: pd.DataFrame) -> dict[str, Any]:
    if len(aligned) < MIN_OBS_FOR_TEST:
        return {
            "n": len(aligned),
            "hit_rate": None,
            "median_spread": None,
            "status": "INSUFFICIENT_DATA",
        }
    median_spread = float(aligned["spread"].median())
    pred_bull = aligned["spread"] > median_spread
    actual_bull = aligned["vnindex_ret_fwd"] > 0
    hits = (pred_bull == actual_bull).sum()
    hit_rate = float(hits / len(aligned))
    return {
        "n": int(len(aligned)),
        "hit_rate": hit_rate,
        "median_spread": median_spread,
        "status": "OK",
    }


def test_rolling_stability(
    aligned: pd.DataFrame,
    window: int = ROLLING_WINDOW_MONTHS,
) -> dict[str, Any]:
    if len(aligned) < window + 1:
        return {
            "window_months": window,
            "n_windows": 0,
            "min_r": None,
            "max_r": None,
            "pct_windows_r_above_threshold": None,
            "status": "INSUFFICIENT_DATA",
        }
    rs: list[float] = []
    for start in range(0, len(aligned) - window + 1):
        chunk = aligned.iloc[start : start + window]
        if chunk["spread"].std() == 0 or chunk["vnindex_ret_fwd"].std() == 0:
            continue
        r, _ = stats.pearsonr(chunk["spread"], chunk["vnindex_ret_fwd"])
        rs.append(float(r))
    if not rs:
        return {
            "window_months": window,
            "n_windows": 0,
            "min_r": None,
            "max_r": None,
            "pct_windows_r_above_threshold": None,
            "status": "INSUFFICIENT_DATA",
        }
    arr = np.array(rs)
    return {
        "window_months": window,
        "n_windows": int(len(rs)),
        "min_r": float(arr.min()),
        "max_r": float(arr.max()),
        "pct_windows_r_above_threshold": float((arr > GATE_R_THRESHOLD).mean()),
        "status": "OK",
    }


def _market_regime_bucket(market_status: str) -> str:
    s = (market_status or "").lower()
    if s in ("confirmed_uptrend",):
        return "bull"
    if s in ("downtrend", "correction"):
        return "bear"
    return "neutral"


def load_historical_regime_buckets(regime_log_path: Path | None = None) -> pd.DataFrame:
    """Map regime_log market_status to bull/neutral/bear at month-end."""
    root = _repo_root()
    path = regime_log_path or (root / DEFAULT_REGIME_LOG)
    if not path.exists():
        return pd.DataFrame(columns=["date", "regime_bucket"])
    log = pd.read_csv(path)
    log["date"] = pd.to_datetime(log["date"]).dt.normalize()
    log["regime_bucket"] = log["market_status"].map(_market_regime_bucket)
    log = log.sort_values("date")
    month_ends = log.groupby(log["date"].dt.to_period("M")).tail(1)
    return month_ends[["date", "regime_bucket", "market_status"]].reset_index(drop=True)


def test_regime_conditional(
    aligned: pd.DataFrame,
    regime_monthly: pd.DataFrame,
) -> dict[str, Any]:
    if regime_monthly.empty:
        return {
            "status": "NO_REGIME_LOG",
            "note": "regime_state.json is point-in-time only; historical buckets from regime_log_2012_now.csv",
            "by_regime": {},
        }
    m = aligned.merge(regime_monthly[["date", "regime_bucket"]], on="date", how="left")
    m = m.dropna(subset=["regime_bucket"])
    by_regime: dict[str, Any] = {}
    for bucket in ("bull", "neutral", "bear"):
        sub = m[m["regime_bucket"] == bucket]
        by_regime[bucket] = {
            "correlation": test_correlation(sub),
            "hit_rate": test_hit_rate(sub),
            "n_months": int(len(sub)),
        }
    return {
        "status": "OK",
        "note": (
            "Historical bull/neutral/bear from data/regime_log_2012_now.csv market_status "
            "(regime_state.json is current snapshot only)."
        ),
        "by_regime": by_regime,
    }


def evaluate_gate_b(test_results: dict[str, Any]) -> dict[str, Any]:
    corr = test_results.get("test1_correlation", {})
    hit = test_results.get("test2_hit_rate", {})
    roll = test_results.get("test3_rolling_stability", {})

    r_ok = corr.get("r") is not None and corr["r"] > GATE_R_THRESHOLD
    hit_ok = hit.get("hit_rate") is not None and hit["hit_rate"] > GATE_HIT_RATE_THRESHOLD
    signal_ok = r_ok or hit_ok

    roll_pct = roll.get("pct_windows_r_above_threshold")
    stability_ok = roll_pct is not None and roll_pct > GATE_ROLLING_PCT_THRESHOLD

    overall = signal_ok and stability_ok
    return {
        "verdict": "PASS" if overall else "FAIL",
        "signal_criterion_met": signal_ok,
        "stability_criterion_met": stability_ok,
        "r_above_threshold": r_ok,
        "hit_rate_above_threshold": hit_ok,
        "criteria": {
            "r_threshold": GATE_R_THRESHOLD,
            "hit_rate_threshold": GATE_HIT_RATE_THRESHOLD,
            "rolling_pct_threshold": GATE_ROLLING_PCT_THRESHOLD,
            "rolling_window_months": ROLLING_WINDOW_MONTHS,
        },
        "label": RESEARCH_ONLY_LABEL,
    }


def run_gate_b_tests(
    diversity: pd.DataFrame,
    *,
    vnindex_path: Path | None = None,
    regime_log_path: Path | None = None,
    spread_col: str = "spread_p050_vs_p100",
) -> dict[str, Any]:
    vnindex_monthly = load_vnindex_monthly_returns(vnindex_path)
    aligned = _align_spread_forward_index(diversity, vnindex_monthly, spread_col=spread_col)
    aligned_exvin = _align_spread_forward_index(
        diversity, vnindex_monthly, spread_col="spread_p050_vs_p100_exvin"
    )
    regime_monthly = load_historical_regime_buckets(regime_log_path)

    results: dict[str, Any] = {
        "research_label": RESEARCH_ONLY_LABEL,
        "spread_column": spread_col,
        "date_range": {
            "start": str(aligned["date"].min()) if not aligned.empty else None,
            "end": str(aligned["date"].max()) if not aligned.empty else None,
        },
        "n_aligned_months": int(len(aligned)),
        "limitations": [
            "VN100 membership approximated by top-N ADV at each rebalance (no PIT reconstitution log).",
            "OHLCV panel uses raw close for ADV; value column = close*volume*1000 VND turnover.",
            "VNINDEX used as VN100 proxy for forward return test (native VN100 series not loaded).",
            "No transaction costs; RESEARCH_ONLY predictive signal test.",
        ],
        "test1_correlation": test_correlation(aligned),
        "test2_hit_rate": test_hit_rate(aligned),
        "test3_rolling_stability": test_rolling_stability(aligned),
        "test4_regime_conditional": test_regime_conditional(aligned, regime_monthly),
        "ex_vin_variant": {
            "test1_correlation": test_correlation(aligned_exvin),
            "test2_hit_rate": test_hit_rate(aligned_exvin),
            "n_aligned_months": int(len(aligned_exvin)),
        },
    }
    results["gate_verdict"] = evaluate_gate_b(results)
    return results


def write_gate_b_outputs(
    results: dict[str, Any],
    out_dir: Path | None = None,
) -> tuple[Path, Path]:
    root = _repo_root()
    dest = out_dir or (root / DEFAULT_OUT_DIR)
    dest.mkdir(parents=True, exist_ok=True)

    json_path = dest / "gate_b_results.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)

    md_path = dest / "gate_b_summary.md"
    md_path.write_text(_format_summary_md(results), encoding="utf-8")
    return json_path, md_path


def _format_summary_md(results: dict[str, Any]) -> str:
    gv = results.get("gate_verdict", {})
    t1 = results.get("test1_correlation", {})
    t2 = results.get("test2_hit_rate", {})
    t3 = results.get("test3_rolling_stability", {})
    t4 = results.get("test4_regime_conditional", {})
    ex = results.get("ex_vin_variant", {})

    lines = [
        "# Diversity Breadth — Gate B Summary",
        "",
        f"**Label:** {RESEARCH_ONLY_LABEL}",
        "",
        "## Verdict",
        f"- **Gate B:** {gv.get('verdict', 'UNKNOWN')}",
        f"- Signal criterion (r>{GATE_R_THRESHOLD} OR hit>{GATE_HIT_RATE_THRESHOLD:.0%}): "
        f"{'YES' if gv.get('signal_criterion_met') else 'NO'}",
        f"- Rolling stability (>{GATE_ROLLING_PCT_THRESHOLD:.0%} of {ROLLING_WINDOW_MONTHS}m windows with r>{GATE_R_THRESHOLD}): "
        f"{'YES' if gv.get('stability_criterion_met') else 'NO'}",
        "",
        "## Test 1 — Correlation (spread vs next-month VNINDEX)",
        f"- n={t1.get('n')}, r={t1.get('r')}, p={t1.get('p_value')}",
        "",
        "## Test 2 — Hit rate (spread vs median → next-month sign)",
        f"- n={t2.get('n')}, hit_rate={t2.get('hit_rate')}, median_spread={t2.get('median_spread')}",
        "",
        "## Test 3 — Rolling stability",
        f"- windows={t3.get('n_windows')}, min_r={t3.get('min_r')}, max_r={t3.get('max_r')}, "
        f"pct_r>{GATE_R_THRESHOLD}={t3.get('pct_windows_r_above_threshold')}",
        "",
        "## Test 4 — Regime conditional",
        f"- {t4.get('note', '')}",
    ]
    by = t4.get("by_regime") or {}
    for bucket, stats_d in by.items():
        c = stats_d.get("correlation", {})
        h = stats_d.get("hit_rate", {})
        lines.append(
            f"- **{bucket}:** n={stats_d.get('n_months')}, r={c.get('r')}, hit_rate={h.get('hit_rate')}"
        )

    lines.extend(
        [
            "",
            "## ex-VIN variant",
            f"- n={ex.get('n_aligned_months')}, r={ex.get('test1_correlation', {}).get('r')}, "
            f"hit_rate={ex.get('test2_hit_rate', {}).get('hit_rate')}",
            "",
            "## Limitations",
        ]
    )
    for lim in results.get("limitations", []):
        lines.append(f"- {lim}")
    lines.append("")
    return "\n".join(lines)
