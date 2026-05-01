"""
Compute VNINDEX level and P/E excluding VIC, VHM, VRE, VPL (VinGroup basket).

Uses FireAnt: HOSE symbols, latest close per symbol, quarterly fundamentals (shares, net_income).
- Index ex-4 = VNINDEX_current * (sum market_cap ex-4 / sum market_cap full).
- P/E = sum(market_cap) / sum(net_income_ttm); same ex-4.

Usage:
  python scripts/vnindex_ex_vin_group.py [--asof YYYY-MM-DD] [--delay 0.12] [--limit N]
  --limit: max symbols to process (default: all HOSE); use for quick test.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import pandas as pd

from src.data.fireant_client import get_client


EXCLUDE_SYMBOLS = {"VIC", "VHM", "VRE", "VPL"}
VNINDEX_CSV = REPO / "data" / "fireant_exports" / "index_ohlcv" / "market" / "VNINDEX.csv"


def _vnindex_last_close_from_csv() -> float | None:
    if not VNINDEX_CSV.exists():
        return None
    df = pd.read_csv(VNINDEX_CSV)
    if df.empty or "close" not in df.columns:
        return None
    return float(df.iloc[-1]["close"])


def _vnindex_from_api(client, asof: str | None) -> float | None:
    end = asof or pd.Timestamp.today().strftime("%Y-%m-%d")
    start = (pd.Timestamp(end) - pd.Timedelta(days=14)).strftime("%Y-%m-%d")
    df = client.get_index_ohlcv("VNINDEX", start=start, end=end)
    if df.empty:
        return None
    return float(df.iloc[-1]["close"])


def main() -> int:
    ap = argparse.ArgumentParser(description="VNINDEX and P/E ex VIC,VHM,VRE,VPL")
    ap.add_argument("--asof", default=None, help="Snapshot date YYYY-MM-DD")
    ap.add_argument("--delay", type=float, default=0.12, help="Delay between API calls (s)")
    ap.add_argument("--limit", type=int, default=None, help="Max HOSE symbols (default: all)")
    ap.add_argument("--out", default=None, help="Write result JSON path")
    args = ap.parse_args()

    asof = args.asof or pd.Timestamp.today().strftime("%Y-%m-%d")
    end = asof
    start = (pd.Timestamp(asof) - pd.Timedelta(days=30)).strftime("%Y-%m-%d")

    client = get_client(timeout=60)
    vni_close = _vnindex_last_close_from_csv() or _vnindex_from_api(client, asof)
    if vni_close is None:
        print("Could not get VNINDEX level (CSV or API).", file=sys.stderr)
        return 1

    symbols = client.get_symbols("HOSE")
    if not symbols:
        symbols = client.get_symbols("HSX")
    if not symbols and (REPO / "data" / "fireant_exports" / "financials" / "financial_symbol_coverage.csv").exists():
        cov = pd.read_csv(REPO / "data" / "fireant_exports" / "financials" / "financial_symbol_coverage.csv")
        symbols = cov["symbol"].astype(str).str.upper().str.strip().dropna().unique().tolist()
    if args.limit:
        symbols = symbols[: args.limit]
    # Always include Vin basket so we can compute cap/earnings ex-4 even with --limit
    for ex in EXCLUDE_SYMBOLS:
        if ex not in symbols:
            symbols.append(ex)
    symbols = [s for s in symbols if s not in ("", "AGRIBANK")]  # skip empty / odd
    if not symbols:
        print("No HOSE/HSX symbols (API empty and no local coverage file).", file=sys.stderr)
        return 1

    rows = []
    for i, sym in enumerate(symbols):
        try:
            df_ohlcv = client.get_ohlcv(sym, start, end)
            if df_ohlcv.empty or len(df_ohlcv) < 1:
                time.sleep(args.delay)
                continue
            close = float(df_ohlcv.iloc[-1]["close"])
            if close <= 0:
                time.sleep(args.delay)
                continue

            df_fa = client.get_fundamentals_quarterly(sym, n_quarters=4)
            if df_fa.empty:
                time.sleep(args.delay)
                continue
            # Last 4 quarters: net_income (ttm), latest shares_outstanding
            if "net_income" not in df_fa.columns:
                time.sleep(args.delay)
                continue
            ni = df_fa["net_income"].dropna()
            if ni.empty:
                time.sleep(args.delay)
                continue
            net_income_ttm = float(ni.tail(4).sum())
            shares = None
            if "shares_outstanding" in df_fa.columns:
                sh = df_fa["shares_outstanding"].dropna()
                if not sh.empty:
                    shares = float(sh.iloc[-1])
            if shares is None or shares <= 0:
                time.sleep(args.delay)
                continue

            cap = close * shares
            rows.append({
                "symbol": sym,
                "close": close,
                "shares_outstanding": shares,
                "market_cap": cap,
                "net_income_ttm": net_income_ttm,
            })
        except Exception as e:
            pass  # skip symbol on any error
        time.sleep(args.delay)
        if (i + 1) % 50 == 0:
            print(f"  ... {i+1}/{len(symbols)} symbols", file=sys.stderr)

    if not rows:
        print("No symbols with valid price + fundamentals.", file=sys.stderr)
        return 1

    df = pd.DataFrame(rows)
    total_cap = df["market_cap"].sum()
    total_ni = df["net_income_ttm"].sum()
    pe_full = total_cap / total_ni if total_ni and total_ni > 0 else None

    df_ex = df[~df["symbol"].str.upper().isin(EXCLUDE_SYMBOLS)]
    cap_ex = df_ex["market_cap"].sum()
    ni_ex = df_ex["net_income_ttm"].sum()
    pe_ex = cap_ex / ni_ex if ni_ex and ni_ex > 0 else None
    # Index ex-4: same divisor => index_ex = index_full * (cap_ex / cap_full)
    index_ex = vni_close * (cap_ex / total_cap) if total_cap and total_cap > 0 else None

    cap_excluded = total_cap - cap_ex
    weight_excluded_pct = 100.0 * cap_excluded / total_cap if total_cap else 0

    result = {
        "asof": asof,
        "vnindex_level": round(vni_close, 2),
        "symbols_used": int(len(df)),
        "symbols_excluded_vin": list(EXCLUDE_SYMBOLS),
        "total_market_cap_full": round(total_cap, 0),
        "total_net_income_ttm_full": round(total_ni, 0),
        "pe_full": round(pe_full, 2) if pe_full is not None else None,
        "total_market_cap_ex_vin": round(cap_ex, 0),
        "total_net_income_ttm_ex_vin": round(ni_ex, 0),
        "pe_ex_vin": round(pe_ex, 2) if pe_ex is not None else None,
        "vnindex_level_ex_vin": round(index_ex, 2) if index_ex is not None else None,
        "weight_vin_basket_pct": round(weight_excluded_pct, 2),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.out:
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
