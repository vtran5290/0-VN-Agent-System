# minervini_backtest/scripts/decision_matrix.py — Decision Matrix: realism settings, pass/fail, Survivors / Gross-only / Noise
"""
Facts-first, gate-first, cost-first. Run M1–M8 at:
  Realism: fee_bps in (20, 30), min_hold_bars=3
  Gross:   fee_bps=0, min_hold_bars=0 (to detect Gross-only)
Output: table with expectancy_r, PF, MaxDD, trades/year, pct_hit_1r/2r, top10_pct_pnl,
        pass/fail vs rule-of-thumb, and group: Survivors | Gross-only | Noise.
Run: python minervini_backtest/scripts/decision_matrix.py [--fetch] [--start] [--end] [--out]
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = ROOT.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT))
# Repo root first so run.fetch_fireant can import src.intake.fireant_historical
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from run import load_config, load_curated_data, fetch_fireant, run_one
from metrics import trade_metrics, trades_per_year, minervini_r_metrics

VERSIONS = ["M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8", "M9", "M10", "M11"]
REALISM_SETTINGS = [
    {"fee_bps": 20, "min_hold_bars": 3, "label": "fee20_minhold3"},
    {"fee_bps": 30, "min_hold_bars": 3, "label": "fee30_minhold3"},
]
GROSS_SETTING = {"fee_bps": 0, "min_hold_bars": 0, "label": "gross"}

# Rule-of-thumb (khuyến nghị)
MIN_EXPECTANCY_R = 0.10
MIN_PF_REALISM = 1.10
MIN_TRADES_PER_YEAR = 10.0
MAX_TOP10_PCT_PNL = 0.60  # < 55–60%


def _pf(ledger: pd.DataFrame) -> float | None:
    if ledger is None or ledger.empty:
        return None
    ret = ledger["ret"].astype(float)
    wins, losses = ret[ret > 0], ret[ret <= 0]
    if len(losses) and losses.sum() < 0 and len(wins):
        return float(wins.sum() / (-losses.sum()))
    return None


def _one_run(version: str, data: dict, override: dict) -> dict:
    try:
        _, ledger = run_one(version, data, override)
    except Exception as e:
        return {"error": str(e), "trades": 0}
    if ledger.empty:
        return {"trades": 0, "expectancy_r": np.nan, "profit_factor": np.nan, "max_drawdown": np.nan,
                "trades_per_year": np.nan, "pct_hit_1r": np.nan, "pct_hit_2r": np.nan, "top10_pct_pnl": np.nan}
    m = trade_metrics(ledger)
    r = minervini_r_metrics(ledger)
    return {
        "trades": len(ledger),
        "expectancy_r": r.get("expectancy_r", np.nan),
        "profit_factor": _pf(ledger),
        "max_drawdown": m.get("max_drawdown", np.nan),
        "trades_per_year": trades_per_year(ledger),
        "pct_hit_1r": r.get("pct_hit_1r", np.nan),
        "pct_hit_2r": r.get("pct_hit_2r", np.nan),
        "top10_pct_pnl": r.get("top10_pct_pnl", np.nan),
    }


def _pass_fail(row: dict, is_realism: bool) -> dict:
    exp_r = row.get("expectancy_r") if row.get("expectancy_r") == row.get("expectancy_r") else None
    pf = row.get("profit_factor")
    tpy = row.get("trades_per_year") if row.get("trades_per_year") == row.get("trades_per_year") else None
    top10 = row.get("top10_pct_pnl") if row.get("top10_pct_pnl") == row.get("top10_pct_pnl") else None
    pass_exp_r = (exp_r is not None and exp_r > MIN_EXPECTANCY_R)
    pass_pf = (pf is not None and pf > MIN_PF_REALISM) if is_realism else (pf is not None and pf > 1.0)
    pass_tpy = (tpy is not None and tpy >= MIN_TRADES_PER_YEAR)
    pass_top10 = (top10 is None or top10 < MAX_TOP10_PCT_PNL)
    return {
        "pass_exp_r": pass_exp_r,
        "pass_pf": pass_pf,
        "pass_tpy": pass_tpy,
        "pass_top10": pass_top10,
        "pass_realism": (pass_exp_r and pass_pf and pass_tpy and pass_top10) if is_realism else None,
    }


def main():
    import argparse
    p = argparse.ArgumentParser(description="Decision Matrix: realism + gross, pass/fail, groups")
    p.add_argument("--symbols", nargs="*", default=None)
    p.add_argument("--fetch", action="store_true")
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--out", "-o", default=None)
    args = p.parse_args()

    data = load_curated_data(args.symbols)
    if not data and args.fetch:
        start = args.start or "2018-01-01"
        end = args.end or "2024-12-31"
        for sym in (args.symbols or ["MBB", "SSI", "VCI", "TCB", "FPT", "MWG", "VPB", "STB"]):
            try:
                data[sym.upper()] = fetch_fireant(sym, start, end)
            except Exception as e:
                print(f"[skip] {sym}: {e}")
    if not data:
        print("No data. Use --fetch or data/curated.")
        return 1

    if args.start or args.end:
        for sym in list(data):
            data[sym] = data[sym].copy().set_index("date")
            if args.start:
                data[sym] = data[sym].loc[args.start:]
            if args.end:
                data[sym] = data[sym].loc[:args.end]
            data[sym] = data[sym].reset_index()

    rows = []
    for version in VERSIONS:
        for setting in REALISM_SETTINGS:
            override = {"fee_bps": setting["fee_bps"], "min_hold_bars": setting["min_hold_bars"]}
            run = _one_run(version, data, override)
            run["version"] = version
            run["setting"] = setting["label"]
            run["realism"] = True
            pf = _pass_fail(run, is_realism=True)
            run.update(pf)
            rows.append(run)
        # Gross (fee=0, min_hold=0)
        run = _one_run(version, data, GROSS_SETTING)
        run["version"] = version
        run["setting"] = GROSS_SETTING["label"]
        run["realism"] = False
        run.update(_pass_fail(run, is_realism=False))
        rows.append(run)

    df = pd.DataFrame(rows)

    # Classify each version: need at least one realism pass for Survivors; gross pass but no realism = Gross-only; else Noise
    group = []
    for version in VERSIONS:
        realism_rows = df[(df["version"] == version) & (df["realism"] == True)]
        gross_row = df[(df["version"] == version) & (df["setting"] == "gross")].iloc[0]
        any_realism_pass = realism_rows["pass_realism"].fillna(False).any()
        gross_ok = (gross_row.get("profit_factor") or 0) > 1.05 and (gross_row.get("expectancy_r") == gross_row.get("expectancy_r") and (gross_row.get("expectancy_r") or 0) > 0.05)
        if any_realism_pass:
            group.append("Survivors")
        elif gross_ok:
            group.append("Gross-only")
        else:
            group.append("Noise")
    # Map version -> group (one per version, use fee30_minhold3 as reference for Survivors)
    version_group = dict(zip(VERSIONS, group))
    df["group"] = df["version"].map(version_group)

    out_path = Path(args.out) if args.out else ROOT / "decision_matrix.csv"
    df.to_csv(out_path, index=False)

    # Print summary: realism table + groups
    print("=== Decision Matrix (realism = fee 20/30 bps, min_hold_bars=3) ===\n")
    real = df[df["realism"] == True]
    for v in VERSIONS:
        r20 = real[(real["version"] == v) & (real["setting"] == "fee20_minhold3")]
        r30 = real[(real["version"] == v) & (real["setting"] == "fee30_minhold3")]
        row20 = r20.iloc[0] if len(r20) else {}
        row30 = r30.iloc[0] if len(r30) else {}
        print(f"{v} [{version_group[v]}]:")
        print(f"  fee20_minhold3: exp_r={row20.get('expectancy_r', np.nan):.3f}  PF={row20.get('profit_factor')}  tpy={row20.get('trades_per_year')}  top10%={row20.get('top10_pct_pnl')}  pass={row20.get('pass_realism')}")
        print(f"  fee30_minhold3: exp_r={row30.get('expectancy_r', np.nan):.3f}  PF={row30.get('profit_factor')}  tpy={row30.get('trades_per_year')}  top10%={row30.get('top10_pct_pnl')}  pass={row30.get('pass_realism')}")
    print("\n--- Groups ---")
    for v in VERSIONS:
        print(f"  {v}: {version_group[v]}")
    print(f"\nRule-of-thumb: expectancy_r > {MIN_EXPECTANCY_R}, PF > {MIN_PF_REALISM} @ realism, trades/year >= {MIN_TRADES_PER_YEAR}, top10_pct_pnl < {MAX_TOP10_PCT_PNL*100:.0f}%")
    print(f"Wrote: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
