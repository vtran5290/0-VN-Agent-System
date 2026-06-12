#!/usr/bin/env python3
"""
Compute MA200 snapshot for liquid + institutional-favorite universe.

Liquid filter  : adv20 >= 2B VND AND adv50 >= 1.5B VND (backtest_manifest policy)
IA filter      : Tier 2 or Tier 3 on latest IA scan date from panel_scores.parquet
OHLCV source   : data/research/sector_l4_causality/stock_daily_cloud_panel.parquet
                 (most recent available: 2026-05-25; 272 symbols with adv20/adv50)
VNINDEX source : data/research/ema_cloud/vnindex_cache.parquet

Output         : data/state/ma200_snapshot.json
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]

# ── paths ──────────────────────────────────────────────────────────────────
OHLCV_PATH = REPO / "data/research/sector_l4_causality/stock_daily_cloud_panel.parquet"
VNI_PATH   = REPO / "data/research/ema_cloud/vnindex_cache.parquet"
IA_PATH    = REPO / "data/research/institutional_accumulation/panel_scores.parquet"
OUT_PATH   = REPO / "data/state/ma200_snapshot.json"

# ── constants ──────────────────────────────────────────────────────────────
ADV20_MIN  = 2_000_000_000   # 2B VND
ADV50_MIN  = 1_500_000_000   # 1.5B VND
MA_WINDOW  = 200
IA_TIERS   = {"Tier 2", "Tier 3"}


def compute_ma200(df: pd.DataFrame, symbol_col: str = "symbol",
                  date_col: str = "date", close_col: str = "close") -> pd.DataFrame:
    """Return DataFrame with [symbol, last_date, last_close, ma200, pct_vs_ma200, above_ma200]."""
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values([symbol_col, date_col])

    rows = []
    for sym, grp in df.groupby(symbol_col):
        closes = grp[close_col].dropna()
        if len(closes) < MA_WINDOW:
            continue
        ma200 = float(closes.iloc[-MA_WINDOW:].mean())
        last_close = float(closes.iloc[-1])
        last_date  = str(grp[date_col].iloc[-1].date())
        pct = round((last_close - ma200) / ma200 * 100, 2)
        rows.append({
            "symbol":      sym,
            "last_date":   last_date,
            "last_close":  round(last_close, 2),
            "ma200":       round(ma200, 2),
            "pct_vs_ma200": pct,
            "above_ma200": last_close >= ma200,
        })
    return pd.DataFrame(rows)


def main() -> None:
    # ── load OHLCV + liquidity ─────────────────────────────────────────────
    ohlcv = pd.read_parquet(OHLCV_PATH)
    ohlcv["date"] = pd.to_datetime(ohlcv["date"])

    # Determine liquid symbols: use LAST available adv20/adv50 per symbol
    latest_liq = (
        ohlcv.sort_values("date")
             .groupby("symbol")[["adv20", "adv50"]]
             .last()
             .reset_index()
    )
    liquid_syms = set(
        latest_liq.loc[
            (latest_liq["adv20"] >= ADV20_MIN) & (latest_liq["adv50"] >= ADV50_MIN),
            "symbol",
        ].tolist()
    )

    # ── load IA favorites ──────────────────────────────────────────────────
    ia = pd.read_parquet(IA_PATH)
    latest_scan = ia["scan_date"].max()
    ia_latest   = ia[ia["scan_date"] == latest_scan]
    ia_fav_syms = set(
        ia_latest.loc[ia_latest["tier"].isin(IA_TIERS), "ticker"].tolist()
    )

    # ── combined universe: liquid AND institutional favorite ───────────────
    universe = liquid_syms & ia_fav_syms
    ohlcv_uni = ohlcv[ohlcv["symbol"].isin(universe)]

    # ── compute MA200 for filtered universe ───────────────────────────────
    ma_df = compute_ma200(ohlcv_uni)

    # Attach tier, adv20, adv50 from latest row
    adv_map  = latest_liq.set_index("symbol")[["adv20", "adv50"]].to_dict("index")
    tier_map = ia_latest.set_index("ticker")["tier"].to_dict()

    records = []
    for _, row in ma_df.iterrows():
        sym  = row["symbol"]
        adv  = adv_map.get(sym, {})
        tier = tier_map.get(sym, "Unknown")
        records.append({
            "symbol":       sym,
            "tier":         tier,
            "last_date":    row["last_date"],
            "last_close":   row["last_close"],
            "ma200":        row["ma200"],
            "pct_vs_ma200": row["pct_vs_ma200"],
            "above_ma200":  bool(row["above_ma200"]),
            "adv20_bn":     round(adv.get("adv20", 0) / 1e9, 2),
            "adv50_bn":     round(adv.get("adv50", 0) / 1e9, 2),
        })
    records.sort(key=lambda x: x["pct_vs_ma200"], reverse=True)

    # ── VNINDEX MA200 ──────────────────────────────────────────────────────
    vni = pd.read_parquet(VNI_PATH)
    vni["date"] = pd.to_datetime(vni["date"])
    vni_closes  = vni.sort_values("date")["close"].dropna()
    vni_ma200   = float(vni_closes.iloc[-MA_WINDOW:].mean()) if len(vni_closes) >= MA_WINDOW else None
    vni_last    = float(vni_closes.iloc[-1]) if len(vni_closes) else None
    vni_date    = str(vni.sort_values("date")["date"].iloc[-1].date())
    vni_pct     = round((vni_last - vni_ma200) / vni_ma200 * 100, 2) if (vni_last and vni_ma200) else None

    # ── assemble output ───────────────────────────────────────────────────
    output = {
        "asof_date":      str(pd.Timestamp.now().date()),
        "ohlcv_max_date": str(ohlcv["date"].max().date()),
        "ia_scan_date":   latest_scan,
        "liquid_filter":  {"adv20_min_bn": ADV20_MIN / 1e9, "adv50_min_bn": ADV50_MIN / 1e9},
        "universe_size":  len(records),
        "liquid_count":   len(liquid_syms),
        "ia_fav_count":   len(ia_fav_syms),
        "vnindex": {
            "last_date":    vni_date,
            "last_close":   vni_last,
            "ma200":        round(vni_ma200, 2) if vni_ma200 else None,
            "pct_vs_ma200": vni_pct,
            "above_ma200":  (vni_last >= vni_ma200) if (vni_last and vni_ma200) else None,
            "note":         "VNINDEX close stale — vnindex_cache max date; not real-time",
        },
        "stocks": records,
        "data_note": (
            "OHLCV from sector_l4_causality/stock_daily_cloud_panel.parquet "
            "(max 2026-05-25). MA200 = simple 200-day mean of last 200 closes. "
            "Symbols with < 200 bars excluded. "
            "IA tiers from institutional_accumulation/panel_scores.parquet latest scan."
        ),
    }

    OUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Written: {OUT_PATH}")
    print(f"Universe: {len(records)} symbols (liquid={len(liquid_syms)}, IA_fav={len(ia_fav_syms)}, overlap={len(universe)})")
    print(f"VNINDEX MA200: {output['vnindex']['ma200']} | last_close: {vni_last} | pct: {vni_pct}%")
    print("\nStocks above MA200:")
    for r in records:
        flag = "+" if r["above_ma200"] else "-"
        print(f"  [{flag}] {r['symbol']:6s} [{r['tier']}]  close={r['last_close']:>8.2f}  ma200={r['ma200']:>8.2f}  pct={r['pct_vs_ma200']:>+6.1f}%  adv20={r['adv20_bn']:.1f}B")


if __name__ == "__main__":
    main()
