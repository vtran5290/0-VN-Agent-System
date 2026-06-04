"""VNINDEX-style market P/E and P/B (LTM + Fwd 2026 planning), full vs ex-Vin."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.data.fireant_client import get_client

EXCLUDE_VIN = frozenset({"VIC", "VHM", "VRE", "VPL"})
FA_Q = REPO / "data" / "fireant_ssot" / "fa_quarterly.parquet"
OHLCV = REPO / "data" / "research" / "ema_cloud" / "ohlcv_panel_ext2012.parquet"
VNINDEX_CSV = REPO / "data" / "fireant_exports" / "index_ohlcv" / "market" / "VNINDEX.csv"


def _metrics(df: pd.DataFrame, label: str) -> dict:
    cap = float(df["cap"].sum())
    w = df["cap"] / cap
    ni_sum = float(df["ni_ttm"].fillna(0).sum())
    eq_sum = float(df.loc[df["eq"] > 0, "eq"].sum())
    pos = df[df["ni_ttm"] > 0]
    pe_all = cap / ni_sum if ni_sum > 0 else None
    pe_pos = float(pos["cap"].sum() / pos["ni_ttm"].sum()) if len(pos) else None
    pb = cap / eq_sum if eq_sum > 0 else None
    pe_w = float((w * df["financialValues_PE"]).sum())
    pb_w = float((w * df["financialValues_PB"]).sum())

    has_plan = df["plan26"].notna() & (df["plan26"] > 0)
    cap_plan = float(df.loc[has_plan, "cap"].sum())
    plan_sum = float(df.loc[has_plan, "plan26"].sum())
    pe_fwd_subset = cap_plan / plan_sum if plan_sum > 0 else None

    blend = np.where(has_plan, df["plan26"], df["ni_ttm"])
    blend = pd.Series(blend, index=df.index).fillna(0)
    blend_pos = float(blend[blend > 0].sum())
    pe_fwd_blend = cap / blend_pos if blend_pos > 0 else None

    return {
        "label": label,
        "symbols": int(len(df)),
        "cap_vnd_trn": round(cap / 1e12, 2),
        "pe_ltm_aggregate": round(pe_all, 2) if pe_all else None,
        "pe_ltm_positive_earners": round(pe_pos, 2) if pe_pos else None,
        "pb_ltm_aggregate": round(pb, 2) if pb else None,
        "pe_ltm_cap_weighted_median_proxy": round(pe_w, 2),
        "pb_ltm_cap_weighted_median_proxy": round(pb_w, 2),
        "pe_fwd2026_planning_subset": round(pe_fwd_subset, 2) if pe_fwd_subset else None,
        "pe_fwd2026_plan_or_ttm_blend": round(pe_fwd_blend, 2) if pe_fwd_blend else None,
        "fwd2026_plan_symbols": int(has_plan.sum()),
        "fwd2026_plan_cap_coverage_pct": round(100 * cap_plan / cap, 1) if cap else None,
    }


def build(asof: str) -> dict:
    client = get_client(timeout=60)
    hose = set(client.get_symbols("HSX") or client.get_symbols("HOSE") or [])

    fa = pd.read_parquet(FA_Q).sort_values(["symbol", "year", "quarter"]).groupby("symbol").tail(1)
    px = pd.read_parquet(OHLCV)
    px["date"] = pd.to_datetime(px["date"])
    px = px.sort_values(["symbol", "date"]).groupby("symbol").tail(1)[["symbol", "close", "date"]]

    plan26 = (
        pd.read_parquet(FA_Q)
        .loc[lambda d: d["financialValues_Year"] == 2026]
        .sort_values(["symbol", "year", "quarter"])
        .groupby("symbol")
        .tail(1)[["symbol", "financialValues_PlanningProfitAfterTax"]]
    )

    m = fa.merge(px, on="symbol", how="left").merge(plan26, on="symbol", how="left", suffixes=("", "_p26"))
    if hose:
        m = m[m["symbol"].isin(hose)]

    price_fa = m["financialValues_PriceAtPeriodEnd"]
    price_now = m["close"] * 1000.0
    ratio = (price_now / price_fa).where((price_fa > 0) & price_now.notna(), np.nan)
    m["cap"] = m["financialValues_MarketCapAtPeriodEnd"] * ratio
    sh = m["financialValues_ShareAtPeriodEnd"]
    bad = m["cap"].isna() | (m["cap"] <= 0)
    m.loc[bad, "cap"] = price_now[bad] * sh[bad]

    m["ni_ttm"] = m["financialValues_ParentCompanyShareholderProfitAfterTax_TTM"]
    m["eq"] = m["financialValues_TotalStockHolderEquity"]
    m["plan26"] = m["financialValues_PlanningProfitAfterTax"]

    base = m[m["cap"].notna() & (m["cap"] > 0)].copy()
    vin_cap = float(base.loc[base["symbol"].isin(EXCLUDE_VIN), "cap"].sum())
    total_cap = float(base["cap"].sum())

    vn = pd.read_csv(VNINDEX_CSV)
    vn["date"] = pd.to_datetime(vn["date"])
    vni = float(vn.sort_values("date").iloc[-1]["close"])

    return {
        "asof": asof,
        "price_asof_max": str(base["date"].max().date()) if base["date"].notna().any() else None,
        "vnindex_close": round(vni, 2),
        "source": "FireAnt SSOT (fa_quarterly.parquet + ema_cloud OHLCV scaled cap)",
        "universe": f"HOSE/HSX ({len(hose)} listed; {len(base)} with cap+FA)",
        "vin_exclude": sorted(EXCLUDE_VIN),
        "weight_vin_basket_pct": round(100 * vin_cap / total_cap, 2) if total_cap else None,
        "methods": {
            "pe_ltm": "sum(market_cap) / sum(parent_NI_TTM)",
            "pb_ltm": "sum(market_cap) / sum(total_equity where >0)",
            "pe_fwd2026_subset": "sum(cap with 2026 plan) / sum(PlanningProfitAfterTax, year=2026)",
            "pe_fwd2026_blend": "denominator uses 2026 plan if available else TTM (positive only)",
            "pb_fwd2026": "not available — no forward book value in FireAnt SSOT",
        },
        "full": _metrics(base, "full"),
        "ex_vin": _metrics(base[~base["symbol"].isin(EXCLUDE_VIN)], "ex_vin"),
        "vin_only": _metrics(base[base["symbol"].isin(EXCLUDE_VIN)], "vin_only"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--asof", default=pd.Timestamp.today().strftime("%Y-%m-%d"))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    result = build(args.asof)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
