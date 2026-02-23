# minervini_backtest/run.py — Run backtest for one or all configs (M1–M5), output comparison table
from __future__ import annotations
import sys
from pathlib import Path
import argparse
import yaml
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
DATA_RAW = ROOT / "data" / "raw"
DATA_CURATED = ROOT / "data" / "curated"
CONFIGS = ROOT / "configs"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from engine import run_backtest, run_single_symbol, prepare_bars
from metrics import trade_metrics, trades_per_year, minervini_r_metrics


def load_config(name: str) -> dict:
    path = CONFIGS / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def fetch_fireant(symbol: str, start: str, end: str) -> pd.DataFrame:
    """Use repo's FireAnt historical (same as pp_backtest)."""
    import importlib.util
    _repo = ROOT.parent
    _path = _repo / "src" / "intake" / "fireant_historical.py"
    if not _path.exists():
        raise RuntimeError("Repo src/intake/fireant_historical.py not found; run from repo root.")
    try:
        spec = importlib.util.spec_from_file_location("fireant_historical", _path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["fireant_historical"] = mod
        spec.loader.exec_module(mod)
        fetch_historical = mod.fetch_historical
    except Exception as e:
        raise RuntimeError(f"Failed to load fireant_historical: {e!r}") from e
    rows = fetch_historical(symbol, start, end)
    if not rows:
        raise ValueError(f"No data for {symbol}")
    df = pd.DataFrame([
        {"date": r.d, "open": r.o, "high": r.h, "low": r.l, "close": r.c, "volume": r.v or 0.0}
        for r in rows
    ])
    df["date"] = pd.to_datetime(df["date"])
    return df[["date", "open", "high", "low", "close", "volume"]]


def load_curated_data(symbols: list[str] | None = None) -> dict[str, pd.DataFrame]:
    """Load parquet from data/curated; if missing, try data/raw CSV."""
    out = {}
    want = {s.upper() for s in (symbols or [])}
    if DATA_CURATED.exists():
        for fp in DATA_CURATED.glob("*.parquet"):
            stem = fp.stem.upper()
            if want and stem not in want:
                continue
            try:
                out[stem] = pd.read_parquet(fp)
                out[stem]["date"] = pd.to_datetime(out[stem]["date"])
            except Exception as e:
                print(f"[warn] Skip {fp}: {e}")
    if DATA_RAW.exists():
        for fp in DATA_RAW.glob("*.csv"):
            stem = fp.stem.upper()
            if stem in out:
                continue
            if want and stem not in want:
                continue
            try:
                df = pd.read_csv(fp)
                for c in ["date", "open", "high", "low", "close", "volume"]:
                    if c.capitalize() in df.columns and c not in df.columns:
                        df = df.rename(columns={c.capitalize(): c})
                df["date"] = pd.to_datetime(df["date"])
                out[stem] = df
            except Exception as e:
                print(f"[warn] Skip {fp}: {e}")
    return out


def _market_regime_df(start: str | None, end: str | None, data: dict) -> pd.DataFrame | None:
    """VN30: regime_on = (vol 30d > vol 126d) or (close > MA200). Merge key = date."""
    try:
        if not data:
            return None
        first = next(iter(data.values()))
        if first is None or first.empty:
            return None
        d_min = first["date"].min()
        d_max = first["date"].max()
        s, e = start or str(d_min)[:10], end or str(d_max)[:10]
        mkt = fetch_fireant("VN30", s, e)
    except Exception:
        return None
    mkt["date"] = pd.to_datetime(mkt["date"])
    vol = mkt["volume"]
    mkt["vol_30"] = vol.rolling(30, min_periods=25).mean()
    mkt["vol_126"] = vol.rolling(126, min_periods=100).mean()
    mkt["ma200"] = mkt["close"].rolling(200, min_periods=150).mean()
    mkt["regime_on"] = ((mkt["vol_30"] > mkt["vol_126"]) | (mkt["close"] > mkt["ma200"])).fillna(False)
    return mkt[["date", "regime_on"]]


def _merge_regime(data: dict[str, pd.DataFrame], cfg: dict) -> dict[str, pd.DataFrame]:
    if not cfg.get("regime_gate"):
        return data
    regime = _market_regime_df(None, None, data)
    if regime is None:
        return data
    out = {}
    for sym, df in data.items():
        d = df.copy()
        d["date"] = pd.to_datetime(d["date"])
        d = d.merge(regime, on="date", how="left")
        d["regime_on"] = d["regime_on"].fillna(False)
        out[sym] = d
    return out


def run_one(config_name: str, data: dict[str, pd.DataFrame], cfg_override: dict | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    cfg = load_config(config_name)
    if cfg_override:
        cfg.update(cfg_override)
    data = _merge_regime(data, cfg)
    stats_df, ledger_df = run_backtest(data, cfg)
    return stats_df, ledger_df


def main():
    parser = argparse.ArgumentParser(description="Minervini-style backtest (M1–M5)")
    parser.add_argument("--config", "-c", default=None, help="Single config (e.g. M1). If omitted, run M1..M5")
    parser.add_argument("--symbols", nargs="*", default=None, help="Limit symbols (default: all in curated/raw)")
    parser.add_argument("--start", default=None, help="Filter data from date (YYYY-MM-DD)")
    parser.add_argument("--end", default=None, help="Filter data to date")
    parser.add_argument("--fee-bps", type=float, default=None, help="Override fee_bps")
    parser.add_argument("--out", "-o", default=None, help="Output CSV path for comparison table")
    parser.add_argument("--ledger", action="store_true", help="Write trade ledger CSV per config")
    parser.add_argument("--fetch", action="store_true", help="Fetch OHLCV from FireAnt (repo intake) for --symbols or watchlist")
    parser.add_argument("--watchlist", default=None, help="Path to watchlist (one symbol per line); used with --fetch")
    parser.add_argument("--golden", nargs=2, metavar=("SYMBOL", "YEAR"), default=None, help="Golden test: run M1 for SYMBOL in YEAR, write full ledger for manual spot-check")
    args = parser.parse_args()

    data = load_curated_data(args.symbols)
    if not data and args.fetch:
        start = args.start or "2018-01-01"
        end = args.end or "2026-12-31"
        watchlist_path = Path(args.watchlist) if args.watchlist else ROOT.parent / "config" / "watchlist.txt"
        tickers = list(args.symbols) if args.symbols else []
        if not tickers and watchlist_path.exists():
            tickers = [ln.strip() for ln in watchlist_path.read_text(encoding="utf-8").strip().splitlines() if ln.strip()]
        if not tickers:
            tickers = ["VN30", "MBB", "SSI", "VCI", "TCB"]
        for sym in tickers:
            try:
                data[sym.upper()] = fetch_fireant(sym, start, end)
            except Exception as e:
                print(f"[skip] {sym}: {e}")
    if not data:
        print("No data. Use data/curated (parquet) or data/raw (CSV), or run with --fetch to use FireAnt.")
        return

    # Golden test: one symbol, one year; use 2 years prior for warmup so 52w/ATR valid
    if args.golden:
        sym, year = args.golden[0].upper(), int(args.golden[1])
        if sym not in data:
            print(f"Golden: symbol {sym} not in data. Available: {list(data.keys())}")
            return
        df = data[sym].copy()
        df["date"] = pd.to_datetime(df["date"])
        start_warm = f"{year - 2}-01-01"
        end_year = f"{year}-12-31"
        df = df[(df["date"] >= start_warm) & (df["date"] <= end_year)]
        if df.empty or len(df) < 260:
            print(f"Golden: need data from {start_warm} to {end_year} for {sym} (warmup + year).")
            return
        cfg = load_config("M1")
        _, ledger_df = run_single_symbol(df, cfg, symbol=sym)
        # Keep only trades that exit in the requested year (for spot-check)
        if not ledger_df.empty and "exit_date" in ledger_df.columns:
            ledger_df = ledger_df[pd.to_datetime(ledger_df["exit_date"]).dt.year == year]
        out_path = ROOT / f"golden_ledger_{sym}_{year}.csv"
        ledger_df.to_csv(out_path, index=False)
        print(f"Golden test: {sym} {year} -> {out_path} ({len(ledger_df)} trades). Spot-check pivot, volume, stop, exit.")
        return

    if args.start or args.end:
        for sym in data:
            data[sym] = data[sym].copy()
            data[sym] = data[sym].set_index("date")
            if args.start:
                data[sym] = data[sym].loc[args.start:]
            if args.end:
                data[sym] = data[sym].loc[:args.end]
            data[sym] = data[sym].reset_index()
    configs = [args.config] if args.config else ["M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8", "M9", "M10", "M11"]
    cfg_override = {}
    if args.fee_bps is not None:
        cfg_override["fee_bps"] = args.fee_bps

    rows = []
    for cname in configs:
        try:
            stats_df, ledger_df = run_one(cname, data, cfg_override)
        except Exception as e:
            print(f"[{cname}] Error: {e}")
            continue
        if stats_df.empty:
            continue
        if not ledger_df.empty:
            m = trade_metrics(ledger_df)
            r_metrics = minervini_r_metrics(ledger_df)
            row = {"version": cname, **m, "trades_per_year": trades_per_year(ledger_df), **r_metrics}
        else:
            row = {"version": cname, "trades": 0, "win_rate": np.nan, "profit_factor": np.nan, "expectancy": np.nan, "max_drawdown": np.nan, "trades_per_year": np.nan}
        rows.append(row)
        if args.ledger and not ledger_df.empty:
            ledger_path = ROOT / f"ledger_{cname}.csv"
            ledger_df.to_csv(ledger_path, index=False)
            print(f"Wrote {ledger_path}")
    out_df = pd.DataFrame(rows)
    out_path = Path(args.out) if args.out else ROOT / "minervini_backtest_results.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_path, index=False)
    print(out_df.to_string())
    print(f"\nWrote: {out_path}")


if __name__ == "__main__":
    main()
