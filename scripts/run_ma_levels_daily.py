#!/usr/bin/env python3
"""
P0: Daily MA levels snapshot for book positions + watchlist.

Priority chain per symbol:
  1. DNA primary_support_line (if confidence HIGH/MEDIUM)
  2. E&MA Research best_ma_2y
  3. Fallback: EMA10

Scope:
  - Book positions: data/raw/current_positions_derived.json
  - Watchlist: data/state/ma200_snapshot.json (liquid IA-fav universe)

OHLCV source: data/research/sector_l4_causality/stock_daily_cloud_panel.parquet

Outputs:
  - data/state/ma_levels_daily.json   (primary SSOT)
  - data/alerts/market_flags.json     (appends ma_breach_alerts section)

Run after market close alongside sell_signals pipeline.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]

# ── paths ──────────────────────────────────────────────────────────────────
OHLCV_PATH    = REPO / "data/research/sector_l4_causality/stock_daily_cloud_panel.parquet"
DNA_PATH      = REPO / "data/research/stock_dna/stock_dna_symbol_profiles.json"
EMA_PATH      = REPO / "data/research/ma_reaction_stocks.json"
POSITIONS_PATH = REPO / "data/raw/current_positions_derived.json"
WATCHLIST_PATH = REPO / "data/state/ma200_snapshot.json"
FLAGS_PATH    = REPO / "data/alerts/market_flags.json"
OUT_PATH      = REPO / "data/state/ma_levels_daily.json"

# ── confidence filter for DNA lines ───────────────────────────────────────
DNA_MIN_CONFIDENCE = {"HIGH", "MEDIUM"}


def _parse_ma(label: str) -> tuple[str, int]:
    """Parse 'sma50' → ('SMA', 50), 'ema200' → ('EMA', 200)."""
    label = label.strip().lower()
    m = re.match(r"^(ema|sma)(\d+)$", label)
    if not m:
        raise ValueError(f"Cannot parse MA label: {label!r}")
    return m.group(1).upper(), int(m.group(2))


def _compute_ma_value(closes: pd.Series, ma_type: str, period: int) -> Optional[float]:
    """Compute MA on closes; return latest value or None if insufficient data."""
    if len(closes) < period:
        return None
    if ma_type == "SMA":
        return float(closes.iloc[-period:].mean())
    else:  # EMA — use full series for accuracy
        ema = closes.ewm(span=period, adjust=False).mean()
        return float(ema.iloc[-1])


def load_universe() -> dict[str, str]:
    """Return {symbol: source_tag} for book + watchlist."""
    universe: dict[str, str] = {}

    # Book positions
    raw = json.loads(POSITIONS_PATH.read_text(encoding="utf-8"))
    for row in raw:
        sym = row.get("ticker", "").upper().strip()
        if sym:
            universe[sym] = "book"

    # Watchlist (IA-fav liquid)
    if WATCHLIST_PATH.exists():
        snap = json.loads(WATCHLIST_PATH.read_text(encoding="utf-8"))
        for row in snap.get("stocks", []):
            sym = row.get("symbol", "").upper().strip()
            if sym and sym not in universe:
                universe[sym] = "watchlist"

    return universe


def build_line_map() -> dict[str, dict]:
    """
    For each symbol, determine which MA line to use and from which source.
    Returns {symbol: {ma_label, ma_type, ma_period, source}}.
    """
    # Load DNA profiles
    dna_raw = json.loads(DNA_PATH.read_text(encoding="utf-8"))
    dna_map: dict[str, dict] = {
        p["symbol"]: p for p in dna_raw.get("profiles", [])
    }

    # Load E&MA research per-symbol bests
    ema_raw = json.loads(EMA_PATH.read_text(encoding="utf-8"))
    ema_map: dict[str, dict] = ema_raw.get("per_symbol_best_2y", {})

    line_map: dict[str, dict] = {}

    def _resolve(sym: str) -> dict:
        # 1. DNA primary_support_line (confidence filter)
        dp = dna_map.get(sym)
        if dp:
            conf = dp.get("confidence", "")
            psl = dp.get("primary_support_line", "")
            if conf in DNA_MIN_CONFIDENCE and psl:
                try:
                    t, p = _parse_ma(psl)
                    return {"ma_label": psl.lower(), "ma_type": t, "ma_period": p, "source": "dna"}
                except ValueError:
                    pass

        # 2. E&MA research best_ma_2y
        ep = ema_map.get(sym)
        if ep:
            best = ep.get("best_ma", "")
            if best:
                try:
                    t, p = _parse_ma(best)
                    return {"ma_label": best.lower(), "ma_type": t, "ma_period": p, "source": "ema_research"}
                except ValueError:
                    pass

        # 3. Fallback
        return {"ma_label": "ema10", "ma_type": "EMA", "ma_period": 10, "source": "fallback"}

    return _resolve, dna_map, ema_map


def main() -> None:
    universe = load_universe()
    resolve_fn, dna_map, ema_map = build_line_map()

    # Load OHLCV
    ohlcv = pd.read_parquet(OHLCV_PATH)
    ohlcv["date"] = pd.to_datetime(ohlcv["date"])
    ohlcv = ohlcv.sort_values(["symbol", "date"])

    asof_date = str(ohlcv["date"].max().date())
    records = []

    for sym, src_tag in sorted(universe.items()):
        line = resolve_fn(sym)

        sym_df = ohlcv[ohlcv["symbol"] == sym].sort_values("date")
        if sym_df.empty:
            records.append({
                "symbol": sym, "source_tag": src_tag,
                "ma_label": line["ma_label"], "ma_source": line["source"],
                "last_date": None, "last_close": None,
                "primary_ma_value": None, "pct_distance": None,
                "above_below": None, "primary_ma_breach": None,
                "note": "OHLCV not found",
            })
            continue

        closes = sym_df["close"].dropna()
        last_close = float(closes.iloc[-1])
        last_date  = str(sym_df["date"].iloc[-1].date())
        ma_val = _compute_ma_value(closes, line["ma_type"], line["ma_period"])

        if ma_val is None:
            pct_dist = None
            above    = None
            breach   = None
            note     = f"Insufficient bars for {line['ma_label']} ({len(closes)} < {line['ma_period']})"
        else:
            pct_dist = round((last_close - ma_val) / ma_val * 100, 2)
            above    = last_close >= ma_val
            breach   = last_close < ma_val
            note     = ""

        # Enrich with DNA danger_line info if available
        danger_line = None
        dp = dna_map.get(sym)
        if dp:
            danger_line = dp.get("danger_line")

        # Enrich with E&MA score
        ema_score = None
        ep = ema_map.get(sym)
        if ep:
            ema_score = ep.get("score")

        records.append({
            "symbol":           sym,
            "source_tag":       src_tag,
            "last_date":        last_date,
            "last_close":       round(last_close, 2),
            "ma_label":         line["ma_label"],
            "ma_type":          line["ma_type"],
            "ma_period":        line["ma_period"],
            "ma_source":        line["source"],
            "primary_ma_value": round(ma_val, 2) if ma_val else None,
            "pct_distance":     pct_dist,
            "above_below":      "above" if above else ("below" if above is not None else None),
            "primary_ma_breach": breach,
            "danger_line":      danger_line,
            "ema_research_score": ema_score,
            "note":             note,
        })

    # Sort: breaches first, then by pct_distance ascending
    records.sort(key=lambda r: (
        not bool(r.get("primary_ma_breach")),
        r.get("pct_distance") if r.get("pct_distance") is not None else 999,
    ))

    # ── Write primary SSOT ─────────────────────────────────────────────────
    breach_symbols = [r["symbol"] for r in records if r.get("primary_ma_breach")]
    output = {
        "asof_date":       str(pd.Timestamp.now().date()),
        "ohlcv_max_date":  asof_date,
        "universe_size":   len(records),
        "book_count":      sum(1 for r in records if r["source_tag"] == "book"),
        "watchlist_count": sum(1 for r in records if r["source_tag"] == "watchlist"),
        "breach_count":    len(breach_symbols),
        "breach_symbols":  breach_symbols,
        "records":         records,
        "data_note": (
            "primary MA = DNA primary_support_line (HIGH/MEDIUM conf) "
            "> E&MA Research best_ma_2y > fallback EMA10. "
            f"OHLCV max {asof_date}."
        ),
    }
    OUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Written: {OUT_PATH}")

    # ── Append ma_breach_alerts to market_flags.json ───────────────────────
    if FLAGS_PATH.exists():
        flags = json.loads(FLAGS_PATH.read_text(encoding="utf-8"))
    else:
        flags = {}

    flags["ma_breach_alerts"] = {
        "computed_date": str(pd.Timestamp.now().date()),
        "breach_count":  len(breach_symbols),
        "breach_symbols": breach_symbols,
        "details": [
            {
                "symbol":      r["symbol"],
                "source_tag":  r["source_tag"],
                "ma_label":    r["ma_label"],
                "ma_source":   r["ma_source"],
                "last_close":  r["last_close"],
                "primary_ma_value": r["primary_ma_value"],
                "pct_distance": r["pct_distance"],
                "primary_ma_breach": r["primary_ma_breach"],
            }
            for r in records if r.get("primary_ma_breach")
        ],
    }
    FLAGS_PATH.write_text(json.dumps(flags, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Updated: {FLAGS_PATH} (ma_breach_alerts)")

    # ── Console summary ────────────────────────────────────────────────────
    print(f"\nMA Levels Daily — {asof_date}")
    print(f"Universe: {len(records)} ({sum(1 for r in records if r['source_tag']=='book')} book + "
          f"{sum(1 for r in records if r['source_tag']=='watchlist')} watchlist)")
    print(f"Breaches: {len(breach_symbols)} — {breach_symbols}\n")
    print(f"  {'Sym':<6} {'Tag':<10} {'MA':<8} {'Src':<13} {'Close':>8} {'MA_val':>8} {'Pct':>7} {'Status'}")
    print(f"  {'-'*72}")
    for r in records:
        status = "BREACH" if r.get("primary_ma_breach") else ("above" if r.get("above_below") == "above" else "—")
        print(
            f"  {r['symbol']:<6} {r['source_tag']:<10} {r['ma_label']:<8} {r['ma_source']:<13} "
            f"{r['last_close'] or 0:>8.2f} {r['primary_ma_value'] or 0:>8.2f} "
            f"{r['pct_distance'] or 0:>+6.1f}% {status}"
        )


if __name__ == "__main__":
    main()
