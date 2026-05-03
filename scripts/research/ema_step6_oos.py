"""
Step 6: Single-split OOS
Train: signal_date <= 2024-12-31  |  Test: signal_date >= 2025-01-01
Best param selected on train per universe. Wilson 95% CI on test success rate.
Universes: full / ex-VIC / ex-VIC/VHM/VRE. VPL excluded entirely.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path

OUT_DIR = Path("data/research/ema_cloud")
EXCLUDE_ALL = ["VPL"]
VIN_STOCKS = ["VIC", "VHM", "VRE"]
TRAIN_END = pd.Timestamp("2024-12-31")
TEST_START = pd.Timestamp("2025-01-01")
MIN_TRAIN_N = 30
MIN_TEST_N = 5


def wilson_ci(n_success: int, n: int, z: float = 1.96):
    if n == 0:
        return np.nan, np.nan
    p = n_success / n
    denom = 1 + z ** 2 / n
    center = (p + z ** 2 / (2 * n)) / denom
    margin = z * np.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / denom
    return round(max(0.0, center - margin), 4), round(min(1.0, center + margin), 4)


def best_param_on_train(df: pd.DataFrame) -> str | None:
    sc = (
        df.groupby("param_key")
        .agg(
            n=("trade_success_63d", "count"),
            success=("trade_success_63d", "mean"),
            win=("win_63d", "mean"),
            ret=("fwd_ret_63d", "mean"),
        )
        .reset_index()
    )
    sc = sc[sc["n"] >= MIN_TRAIN_N]
    if sc.empty:
        return None
    sc["score"] = 0.6 * sc["success"] + 0.2 * sc["win"] + 0.2 * sc["ret"].clip(upper=0.3)
    return sc.loc[sc["score"].idxmax(), "param_key"]


def run_universe(df: pd.DataFrame, univ_name: str) -> list[dict]:
    rows = []
    train = df[df["signal_date"] <= TRAIN_END]
    test = df[df["signal_date"] >= TEST_START]
    best_key = best_param_on_train(train)
    if best_key is None:
        print(f"  [{univ_name}] no param with >={MIN_TRAIN_N} train rows")
        return rows

    tr_best = train[train["param_key"] == best_key]
    te_best = test[test["param_key"] == best_key]
    print(f"  [{univ_name}] best_param={best_key}  train_n={len(tr_best)}  test_n={len(te_best)}")

    for sig_type in ["all", "breakout", "retest", "reclaim"]:
        tr_sub = tr_best if sig_type == "all" else tr_best[tr_best["signal_type"] == sig_type]
        te_sub = te_best if sig_type == "all" else te_best[te_best["signal_type"] == sig_type]
        if len(te_sub) < MIN_TEST_N:
            continue
        n_test = len(te_sub)
        n_train = len(tr_sub)
        test_succ = float(te_sub["trade_success_63d"].mean())
        train_succ = float(tr_sub["trade_success_63d"].mean()) if n_train > 0 else np.nan
        ci_lo, ci_hi = wilson_ci(int(te_sub["trade_success_63d"].sum()), n_test)
        rows.append(
            {
                "universe": univ_name,
                "signal_type": sig_type,
                "best_param": best_key,
                "n_train": n_train,
                "n_test": n_test,
                "train_success_63d": round(train_succ, 4) if not np.isnan(train_succ) else np.nan,
                "test_success_63d": round(test_succ, 4),
                "ci_lo_95": ci_lo,
                "ci_hi_95": ci_hi,
                "train_mean_ret_63d": round(float(tr_sub["fwd_ret_63d"].mean()), 4) if n_train > 0 else np.nan,
                "test_mean_ret_63d": round(float(te_sub["fwd_ret_63d"].mean()), 4),
                "test_win_rate_63d": round(float(te_sub["win_63d"].mean()), 4),
            }
        )
    return rows


def write_md(df: pd.DataFrame, path: Path) -> None:
    lines = ["# Step 6: Single-Split OOS Results", "",
             f"Train: 2023-2024 (≤ {TRAIN_END.date()})  |  Test: 2025+ (≥ {TEST_START.date()})",
             "Truncated 63d events excluded. VPL excluded entirely.", ""]

    for univ in ["full", "ex-VIC", "ex-VIC/VHM/VRE"]:
        sub = df[df["universe"] == univ]
        if sub.empty:
            continue
        lines.append(f"## {univ}")
        lines.append("")
        lines.append("| signal_type | n_train | n_test | train_succ | test_succ | CI 95% | train_ret | test_ret |")
        lines.append("|-------------|---------|--------|------------|-----------|--------|-----------|----------|")
        for _, r in sub.iterrows():
            ci = f"[{r['ci_lo_95']:.1%}, {r['ci_hi_95']:.1%}]"
            lines.append(
                f"| {r['signal_type']} | {r['n_train']} | {r['n_test']} "
                f"| {r['train_success_63d']:.1%} | {r['test_success_63d']:.1%} "
                f"| {ci} | {r['train_mean_ret_63d']:+.2%} | {r['test_mean_ret_63d']:+.2%} |"
            )
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    print("Loading trades...")
    tr = pd.read_csv(OUT_DIR / "trades.csv")
    tr["signal_date"] = pd.to_datetime(tr["signal_date"])
    tr = tr[~tr["symbol"].isin(EXCLUDE_ALL)]
    tr = tr[tr["is_truncated_63d"] == 0]
    print(f"  Loaded {len(tr):,} non-truncated rows (VPL excluded)")

    train_total = tr[tr["signal_date"] <= TRAIN_END]
    test_total = tr[tr["signal_date"] >= TEST_START]
    print(f"  Train rows: {len(train_total):,}  Test rows: {len(test_total):,}")

    universes = {
        "full": tr,
        "ex-VIC": tr[tr["symbol"] != "VIC"],
        "ex-VIC/VHM/VRE": tr[~tr["symbol"].isin(VIN_STOCKS)],
    }

    all_rows: list[dict] = []
    for name, df in universes.items():
        print(f"\n--- {name} ---")
        all_rows.extend(run_universe(df, name))

    result = pd.DataFrame(all_rows)
    csv_path = OUT_DIR / "single_split_oos.csv"
    result.to_csv(csv_path, index=False)
    write_md(result, OUT_DIR / "single_split_oos.md")

    print("\n=== RESULTS ===")
    print(result.to_string(index=False))
    print(f"\nSaved: {csv_path}")
    print(f"Saved: {OUT_DIR / 'single_split_oos.md'}")


if __name__ == "__main__":
    main()
