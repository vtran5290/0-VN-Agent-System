# minervini_backtest/scripts/walk_forward.py — Train 2020-2022, Validate 2023, Holdout 2024
"""
Do NOT optimize on full period. Report PF/expectancy on train / val / holdout separately.
Uses pre-split warmup: for each split load data from (split_start - warmup) so engine
has enough bars; then filter ledger to entry_date in [split_start, split_end].
Run: python minervini_backtest/scripts/walk_forward.py [--config M1] [--sanity] [--fetch]
"""
from __future__ import annotations
import sys
from pathlib import Path
from datetime import timedelta
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = ROOT.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from run import load_config, load_curated_data, fetch_fireant, run_one
from metrics import minervini_r_metrics

SPLITS = {
    "train": ("2020-01-01", "2022-12-31"),
    "validate": ("2023-01-01", "2023-12-31"),
    "holdout": ("2024-01-01", "2024-12-31"),
}

# Calendar days to add before split_start so we have enough bars for warmup (~292 trading days ~ 1.5 years)
WARMUP_CALENDAR_DAYS = 550


def _warmup_bars(cfg: dict) -> int:
    lb = int(cfg.get("lookback_base", 40))
    return int(cfg.get("warmup_bars", 252 + lb))


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--config", "-c", default="M1")
    p.add_argument("--versions", nargs="*", default=None, help="Run multiple versions (e.g. M3 M4); else single --config")
    p.add_argument("--symbols", nargs="*", default=None)
    p.add_argument("--fetch", action="store_true")
    p.add_argument("--realism", action="store_true", help="Apply fee=30, min_hold_bars=3 for deploy gates")
    p.add_argument("--out", "-o", default=None)
    p.add_argument("--sanity", action="store_true", help="Print bars-after-warmup and regime_on % per split")
    args = p.parse_args()

    data = load_curated_data(args.symbols)
    if not data and args.fetch:
        # Fetch from earlier so train split has warmup (2018 -> 2020 train)
        for sym in (args.symbols or ["MBB", "SSI", "VCI", "TCB", "FPT", "MWG", "VPB", "STB", "ACB", "CTG", "BID", "VNM", "HPG", "MSN", "VIC"]):
            try:
                data[sym.upper()] = fetch_fireant(sym, "2018-01-01", "2024-12-31")
            except Exception as e:
                print(f"[skip] {sym}: {e}")
    if not data:
        print("No data. Use --fetch or data/curated.")
        return 1

    versions = args.versions or [args.config]
    override = {"fee_bps": 30, "min_hold_bars": 3} if args.realism else None
    rows = []
    for version in versions:
        try:
            cfg = load_config(version)
            if override:
                cfg = {**cfg, **override}
            warmup_bars = _warmup_bars(cfg)
        except FileNotFoundError:
            warmup_bars = 292
        for split_name, (start, end) in SPLITS.items():
            start_dt = pd.to_datetime(start)
            start_extended = (start_dt - timedelta(days=WARMUP_CALENDAR_DAYS)).strftime("%Y-%m-%d")
            filtered = {}
            for sym, df in data.items():
                d = df.copy()
                d["date"] = pd.to_datetime(d["date"])
                d = d[(d["date"] >= start_extended) & (d["date"] <= end)]
                if len(d) > warmup_bars:
                    filtered[sym] = d
            if not filtered:
                if args.sanity:
                    print(f"[sanity] {version} {split_name}: no symbol with >{warmup_bars} bars after extend")
                rows.append({"version": version, "split": split_name, "start": start, "end": end, "trades": 0, "profit_factor": None, "expectancy": None, "expectancy_r": None, "top10_pct_pnl": None})
                continue
            if args.sanity:
                bars_after = min(len(df) - warmup_bars for df in filtered.values())
                d0 = next(iter(filtered.values()))
                date_min, date_max = d0["date"].min(), d0["date"].max()
                msg = f"[sanity] {version} {split_name}: bars_after_warmup={bars_after} (min), date_range={date_min.date()}..{date_max.date()}"
                if "regime_on" in d0.columns:
                    reg = pd.concat([df["regime_on"] for df in filtered.values()])
                    msg += f", regime_on%={reg.mean() * 100:.1f}"
                print(msg)
            try:
                _, ledger = run_one(version, filtered, override)
            except Exception as e:
                print(f"[{version} {split_name}] Error: {e}")
                rows.append({"version": version, "split": split_name, "start": start, "end": end, "trades": 0, "profit_factor": None, "expectancy": None, "expectancy_r": None, "top10_pct_pnl": None})
                continue
            if ledger.empty:
                rows.append({"version": version, "split": split_name, "start": start, "end": end, "trades": 0, "profit_factor": None, "expectancy": None, "expectancy_r": None, "top10_pct_pnl": None})
                continue
            # Only count trades that ENTERED in this split window
            ledger["entry_date"] = pd.to_datetime(ledger["entry_date"])
            in_split = ledger[(ledger["entry_date"] >= start) & (ledger["entry_date"] <= end)]
            if in_split.empty:
                rows.append({"version": version, "split": split_name, "start": start, "end": end, "trades": 0, "profit_factor": None, "expectancy": None, "expectancy_r": None, "top10_pct_pnl": None})
                continue
            ret = in_split["ret"].astype(float)
            wins, losses = ret[ret > 0], ret[ret <= 0]
            pf = (wins.sum() / (-losses.sum())) if len(losses) and losses.sum() < 0 and len(wins) else None
            r_met = minervini_r_metrics(in_split)
            rows.append({
                "version": version,
                "split": split_name,
                "start": start,
                "end": end,
                "trades": len(in_split),
                "profit_factor": round(pf, 4) if pf is not None else None,
                "expectancy": round(ret.mean(), 4),
                "expectancy_r": round(r_met["expectancy_r"], 4) if r_met.get("expectancy_r") == r_met.get("expectancy_r") else None,
                "top10_pct_pnl": round(r_met["top10_pct_pnl"], 4) if r_met.get("top10_pct_pnl") == r_met.get("top10_pct_pnl") else None,
            })
    df = pd.DataFrame(rows)
    out = Path(args.out) if args.out else ROOT / "walk_forward_results.csv"
    df.to_csv(out, index=False)
    print(df.to_string())
    print(f"\nWrote: {out}. Do not optimize on full period; compare train/val/holdout.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
