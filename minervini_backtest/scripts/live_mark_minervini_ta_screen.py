from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
MINV = REPO_ROOT / "minervini_backtest"
SRC = MINV / "src"

for p in (MINV, SRC):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from minervini_candidates.utils import get_asof_date, load_price_data
from indicators import add_all_indicators
from filters import tt_lite
from setups import three_week_tight, vcp_proxy


def _load_watchlist_symbols(path: Path) -> list[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    for ln in lines:
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        out.append(ln.upper())
    return out


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Live Mark/Minervini-style TA proxy screen (TT + VCP + 3WT).")
    ap.add_argument(
        "--asof",
        default=None,
        help="Cutoff date (YYYY-MM-DD). Use latest trading date <= this date.",
    )
    args = ap.parse_args()

    watchlist_path = REPO_ROOT / "config" / "watchlist.txt"
    symbols = _load_watchlist_symbols(watchlist_path)
    if not symbols:
        print(f"[ERROR] No symbols in watchlist: {watchlist_path}")
        return 1

    price_dir = MINV / "data" / "raw"
    price_data = load_price_data(price_dir)
    if not price_data:
        print(f"[ERROR] No price data loaded from: {price_dir}")
        return 1

    asof = None
    if args.asof:
        try:
            cutoff = pd.Timestamp(args.asof)
        except Exception:
            print(f"[ERROR] Invalid --asof: {args.asof}")
            return 1
        # Latest common trading date <= cutoff (based on VNINDEX if present).
        idx = price_data.get("VNINDEX")
        if idx is not None and not idx.empty and "date" in idx.columns:
            asof = pd.to_datetime(idx["date"])
            asof = asof[asof <= cutoff].max() if (asof <= cutoff).any() else None
        if asof is None:
            # Fallback: any symbol
            latest = None
            for df in price_data.values():
                if df is None or df.empty or "date" not in df.columns:
                    continue
                d = pd.to_datetime(df["date"])
                m = d[d <= cutoff].max() if (d <= cutoff).any() else None
                if m is not None and (latest is None or m > latest):
                    latest = m
            asof = latest
    else:
        asof = get_asof_date(price_data, prefer_symbol="VNINDEX")
    if asof is None:
        print("[ERROR] Could not determine as-of date from price data.")
        return 1

    pass_all = 0
    pass_tt = 0
    pass_vcp = 0
    pass_3wt = 0
    price_present = 0
    pass_symbols: list[str] = []
    pass_tt_3wt_symbols: list[str] = []

    # Proxy params (match configs used in repo backtests)
    # - TT Lite: sepa MAs trend (Close > MA50 > MA200; MA200 slope up)
    # - VCP proxy: contraction stack (ATR% contracting) + volume dry-up (VolSMA5 < VolSMA20)
    # - 3WT proxy: tight base (15d range <= 6%) + vol dry-up (VolSMA5 < VolSMA20)
    for sym in symbols:
        px = price_data.get(sym)
        if px is None or px.empty:
            continue
        d = px[px["date"] <= asof].sort_values("date")
        if d.empty:
            continue
        price_present += 1

        # Compute all rolling features once per symbol (MA/ATR/vol/52w high/low).
        d = add_all_indicators(
            d,
            ma_windows=[20, 50, 150, 200],
            atr_n=14,
            atr_pct_windows=[5, 10, 20],
            vol_sma_windows=[5, 20],
        )

        tt_ok = bool(tt_lite(d, ma200_slope_bars=20).iloc[-1])
        vcp_ok = bool(vcp_proxy(d).iloc[-1])
        wt_ok = bool(three_week_tight(d, window=15, max_range_pct=0.06, vol5_lt_vol20=True).iloc[-1])

        pass_tt += 1 if tt_ok else 0
        pass_vcp += 1 if vcp_ok else 0
        pass_3wt += 1 if wt_ok else 0
        if tt_ok and wt_ok:
            pass_tt_3wt_symbols.append(sym)
        if tt_ok and vcp_ok and wt_ok:
            pass_all += 1
            pass_symbols.append(sym)

    print(f"asof={asof.strftime('%Y-%m-%d')}")
    print(f"watchlist_count={len(symbols)}")
    print(f"price_present={price_present}")
    print(f"pass_TT_Lite={pass_tt}")
    print(f"pass_VCP_proxy={pass_vcp}")
    print(f"pass_3WT_proxy={pass_3wt}")
    print(f"pass_TT+3WT={len(pass_tt_3wt_symbols)}")
    print(f"pass_TT+VCP+3WT={pass_all}")
    if pass_tt_3wt_symbols:
        print("pass_tt_3wt_symbols=" + ",".join(pass_tt_3wt_symbols))
    if pass_symbols:
        print("pass_symbols=" + ",".join(pass_symbols))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

