#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.data.fireant_client import get_client  # noqa: E402


def load_backtest(path: Path) -> pd.DataFrame:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("per_date", [])
    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError(f"No per_date rows in {path}")
    df["date"] = pd.to_datetime(df["date"])
    for c in ["industries_selected", "industries_hit", "stocks_selected", "stocks_hit"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    return df


def load_vnindex_from_fireant(start: str, end: str) -> pd.DataFrame:
    client = get_client(timeout=30)
    df = client.get_ohlcv("VNINDEX", start=start, end=end)
    if df.empty:
        raise ValueError("VNINDEX history is empty from FireAnt.")
    df = df[["date", "close"]].copy()
    df["date"] = pd.to_datetime(df["date"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["date", "close"]).sort_values("date").reset_index(drop=True)
    return df


def add_ma_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for w in (20, 50, 100, 150, 200):
        out[f"ma{w}"] = out["close"].rolling(w, min_periods=w).mean()
        out[f"above_ma{w}"] = out["close"] > out[f"ma{w}"]
        for lb in (5, 10, 20):
            out[f"slope_ma{w}_{lb}"] = out[f"ma{w}"] / out[f"ma{w}"].shift(lb) - 1.0
    return out


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    ctr = (p + z * z / (2 * n)) / den
    half = z * np.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / den
    return float(ctr - half), float(ctr + half)


def random_config(rng: random.Random) -> dict[str, Any]:
    ma_choices = [20, 50, 100, 150, 200]
    n_above = rng.randint(1, len(ma_choices))
    n_slope = rng.randint(1, len(ma_choices))
    above = sorted(rng.sample(ma_choices, n_above))
    slope_mas = sorted(rng.sample(ma_choices, n_slope))
    slope = {ma: rng.choice([5, 10, 20]) for ma in slope_mas}
    return {"above": above, "slope": slope}


def pass_gate(row: pd.Series, cfg: dict[str, Any]) -> bool:
    for ma in cfg["above"]:
        if not bool(row.get(f"above_ma{ma}", False)):
            return False
    for ma, lb in cfg["slope"].items():
        v = row.get(f"slope_ma{ma}_{lb}", np.nan)
        if not np.isfinite(v) or float(v) <= 0:
            return False
    return True


def evaluate(df: pd.DataFrame, cfg: dict[str, Any], min_stock_n: int) -> dict[str, Any]:
    mask = df.apply(lambda r: pass_gate(r, cfg), axis=1)
    x = df[mask].copy()
    ind_n = int(x["industries_selected"].sum())
    ind_k = int(x["industries_hit"].sum())
    stk_n = int(x["stocks_selected"].sum())
    stk_k = int(x["stocks_hit"].sum())
    if stk_n < min_stock_n:
        return {
            "valid": False,
            "dates": int(mask.sum()),
            "ind_n": ind_n,
            "ind_hit_rate": np.nan,
            "stk_n": stk_n,
            "stk_hit_rate": np.nan,
            "score": -1.0,
        }
    ind_hr = ind_k / ind_n if ind_n else np.nan
    stk_hr = stk_k / stk_n if stk_n else np.nan
    # Optimize stock hit-rate; lightly reward breadth of sample to avoid tiny-n overfit.
    score = stk_hr + 0.02 * np.log1p(stk_n / 100.0)
    return {
        "valid": True,
        "dates": int(mask.sum()),
        "ind_n": ind_n,
        "ind_hits": ind_k,
        "ind_hit_rate": ind_hr,
        "stk_n": stk_n,
        "stk_hits": stk_k,
        "stk_hit_rate": stk_hr,
        "score": float(score),
    }


def evaluate_ensemble(
    df: pd.DataFrame,
    cfgs: list[dict[str, Any]],
    vote_threshold: float,
    min_stock_n: int,
) -> dict[str, Any]:
    if not cfgs:
        return {
            "valid": False,
            "dates": 0,
            "ind_n": 0,
            "ind_hit_rate": np.nan,
            "stk_n": 0,
            "stk_hit_rate": np.nan,
            "score": -1.0,
        }
    # vote threshold in [0, 1]: pass if fraction of configs passed >= threshold.
    votes = df.apply(
        lambda r: sum(1 for cfg in cfgs if pass_gate(r, cfg)) / len(cfgs),
        axis=1,
    )
    mask = votes >= vote_threshold
    x = df[mask].copy()
    ind_n = int(x["industries_selected"].sum())
    ind_k = int(x["industries_hit"].sum())
    stk_n = int(x["stocks_selected"].sum())
    stk_k = int(x["stocks_hit"].sum())
    if stk_n < min_stock_n:
        return {
            "valid": False,
            "dates": int(mask.sum()),
            "ind_n": ind_n,
            "ind_hit_rate": np.nan,
            "stk_n": stk_n,
            "stk_hit_rate": np.nan,
            "score": -1.0,
        }
    ind_hr = ind_k / ind_n if ind_n else np.nan
    stk_hr = stk_k / stk_n if stk_n else np.nan
    score = stk_hr + 0.02 * np.log1p(stk_n / 100.0)
    return {
        "valid": True,
        "dates": int(mask.sum()),
        "ind_n": ind_n,
        "ind_hits": ind_k,
        "ind_hit_rate": ind_hr,
        "stk_n": stk_n,
        "stk_hits": stk_k,
        "stk_hit_rate": stk_hr,
        "score": float(score),
    }


def fmt_cfg(cfg: dict[str, Any]) -> str:
    ab = ",".join([f"MA{x}" for x in cfg["above"]])
    sl = ",".join([f"MA{k}>0@{v}d" for k, v in sorted(cfg["slope"].items())])
    return f"above[{ab}] & slope[{sl}]"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--train-json",
        default=str(REPO / "data" / "research" / "random_backtest_p20_high_n50.json"),
    )
    ap.add_argument(
        "--valid-json",
        default=str(REPO / "data" / "research" / "random_backtest_p20_high_n30.json"),
    )
    ap.add_argument("--vnindex-start", default="2012-01-01")
    ap.add_argument("--vnindex-end", default=pd.Timestamp.today().strftime("%Y-%m-%d"))
    ap.add_argument("--trials", type=int, default=600)
    ap.add_argument("--loops", type=int, default=3)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--min-stock-n", type=int, default=1200)
    ap.add_argument("--ensemble-top-n", type=int, default=20)
    ap.add_argument(
        "--out-json",
        default=str(REPO / "data" / "research" / "trend_gate_optimization.json"),
    )
    args = ap.parse_args()

    train = load_backtest(Path(args.train_json))
    valid = load_backtest(Path(args.valid_json))
    vni = add_ma_features(load_vnindex_from_fireant(args.vnindex_start, args.vnindex_end))

    # Join gate features by date
    keep_cols = ["date"] + [c for c in vni.columns if c.startswith("above_ma") or c.startswith("slope_ma")]
    train = train.merge(vni[keep_cols], on="date", how="left")
    valid = valid.merge(vni[keep_cols], on="date", how="left")

    rng = random.Random(args.seed)
    trials: list[dict[str, Any]] = []
    seen = set()

    # Self-improving loop: each loop seeds around currently top configs + fresh random.
    seed_pool: list[dict[str, Any]] = []
    for lp in range(args.loops):
        this_round: list[dict[str, Any]] = []
        for _ in range(args.trials):
            if seed_pool and rng.random() < 0.6:
                base = rng.choice(seed_pool)
                cfg = json.loads(json.dumps(base))
                # mutate one part
                if rng.random() < 0.5 and cfg["above"]:
                    ma_all = [20, 50, 100, 150, 200]
                    if rng.random() < 0.5 and len(cfg["above"]) > 1:
                        cfg["above"].remove(rng.choice(cfg["above"]))
                    else:
                        addable = [m for m in ma_all if m not in cfg["above"]]
                        if addable:
                            cfg["above"].append(rng.choice(addable))
                    cfg["above"] = sorted(set(cfg["above"]))
                else:
                    if cfg["slope"]:
                        k = rng.choice(list(cfg["slope"].keys()))
                        cfg["slope"][k] = rng.choice([5, 10, 20])
                    else:
                        k = rng.choice([20, 50, 100, 150, 200])
                        cfg["slope"][k] = rng.choice([5, 10, 20])
            else:
                cfg = random_config(rng)
            key = json.dumps(cfg, sort_keys=True)
            if key in seen:
                continue
            seen.add(key)
            tr = evaluate(train, cfg, args.min_stock_n)
            if not tr["valid"]:
                continue
            va = evaluate(valid, cfg, max(500, args.min_stock_n // 2))
            this_round.append(
                {
                    "config": cfg,
                    "rule_text": fmt_cfg(cfg),
                    "train": tr,
                    "valid": va,
                    "loop": lp + 1,
                }
            )
        if this_round:
            this_round = sorted(
                this_round,
                key=lambda x: (
                    x["train"]["stk_hit_rate"],
                    x["valid"]["stk_hit_rate"] if x["valid"]["valid"] else -1.0,
                ),
                reverse=True,
            )
            # keep best 12 as seeds for next loop
            seed_pool = [x["config"] for x in this_round[:12]]
            trials.extend(this_round)

    if not trials:
        raise RuntimeError("No valid configs. Lower --min-stock-n or increase --trials.")

    trials = sorted(
        trials,
        key=lambda x: (x["train"]["stk_hit_rate"], x["valid"]["stk_hit_rate"] if x["valid"]["valid"] else -1.0),
        reverse=True,
    )
    best = trials[0]
    top_n = max(1, min(args.ensemble_top_n, len(trials)))
    ensemble_cfgs = [t["config"] for t in trials[:top_n]]
    vote_grid = [0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.60, 0.70, 0.80]
    ens_trials: list[dict[str, Any]] = []
    for vt in vote_grid:
        tr = evaluate_ensemble(train, ensemble_cfgs, vt, args.min_stock_n)
        if not tr["valid"]:
            continue
        va = evaluate_ensemble(valid, ensemble_cfgs, vt, max(500, args.min_stock_n // 2))
        ens_trials.append({"vote_threshold": vt, "train": tr, "valid": va})
    best_ens = None
    if ens_trials:
        ens_trials = sorted(
            ens_trials,
            key=lambda x: (x["train"]["stk_hit_rate"], x["valid"]["stk_hit_rate"] if x["valid"]["valid"] else -1.0),
            reverse=True,
        )
        best_ens = ens_trials[0]

    # Baseline: no gate (all sampled dates)
    baseline_cfg = {"above": [], "slope": {}}
    base_train = evaluate(train, baseline_cfg, 0)
    base_valid = evaluate(valid, baseline_cfg, 0)

    out = {
        "params": {
            "trials": args.trials,
            "loops": args.loops,
            "seed": args.seed,
            "min_stock_n": args.min_stock_n,
            "ensemble_top_n": top_n,
        },
        "baseline": {
            "config": baseline_cfg,
            "rule_text": "no trend gate",
            "train": base_train,
            "valid": base_valid,
            "train_stk_ci95": wilson_ci(base_train["stk_hits"], base_train["stk_n"]),
            "valid_stk_ci95": wilson_ci(base_valid["stk_hits"], base_valid["stk_n"]),
        },
        "best": {
            "config": best["config"],
            "rule_text": best["rule_text"],
            "train": best["train"],
            "valid": best["valid"],
            "train_stk_ci95": wilson_ci(best["train"]["stk_hits"], best["train"]["stk_n"]),
            "valid_stk_ci95": wilson_ci(best["valid"]["stk_hits"], best["valid"]["stk_n"])
            if best["valid"]["valid"]
            else (float("nan"), float("nan")),
        },
        "best_ensemble": (
            {
                "method": "topn_vote",
                "vote_threshold": best_ens["vote_threshold"],
                "top_n": top_n,
                "train": best_ens["train"],
                "valid": best_ens["valid"],
                "train_stk_ci95": wilson_ci(best_ens["train"]["stk_hits"], best_ens["train"]["stk_n"]),
                "valid_stk_ci95": wilson_ci(best_ens["valid"]["stk_hits"], best_ens["valid"]["stk_n"])
                if best_ens["valid"]["valid"]
                else (float("nan"), float("nan")),
            }
            if best_ens is not None
            else None
        ),
        "top5": trials[:5],
        "top20": trials[:20],
        "ensemble_vote_trials": ens_trials,
    }

    out_path = Path(args.out_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(out["baseline"], ensure_ascii=False, indent=2))
    print(json.dumps(out["best"], ensure_ascii=False, indent=2))
    if out["best_ensemble"] is not None:
        print(json.dumps(out["best_ensemble"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
