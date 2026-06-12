"""
Build data/decision/fa_council_slice.json from fa_quarterly parquet.

Extracts latest-quarter FA metrics for all book positions and formats
them for the Buffett council mind. Run after updating the parquet.

Usage:
  python scripts/build_fa_council_slice.py
  python scripts/build_fa_council_slice.py --tickers ACB,HSG,TCX
  python scripts/build_fa_council_slice.py --asof 2026-06-09
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
PARQUET = REPO / "data" / "fireant_ssot" / "fa_quarterly.parquet"
POSITIONS = REPO / "data" / "raw" / "current_positions_derived.json"
OUT = REPO / "data" / "decision" / "fa_council_slice.json"

# Columns to pull from parquet
FA_COLS = [
    "symbol", "year", "quarter", "companyType",
    "financialValues_ROE",
    "financialValues_ROA",
    "financialValues_GrossMargin",
    "financialValues_ProfitAfterTax_TTM",
    "financialValues_TotalRevenue_TTM",
    "financialValues_TotalDebt",
    "financialValues_StockHolderEquity",
    "financialValues_TotalEquity",
    "financialValues_CashflowFromOperatingActivity",
    "financialValues_CAPEX",
    "financialValues_TotalAsset",
    "financialValues_FCF",
]

# Banks and securities use different revenue bases — flag them
BANK_TYPES = {"bank", "banking", "1"}
SECURITIES_TYPES = {"securities", "ctck", "2"}


def _classify_type(company_type: str | None) -> str:
    if company_type is None:
        return "general"
    ct = str(company_type).lower()
    if any(k in ct for k in BANK_TYPES):
        return "bank"
    if any(k in ct for k in SECURITIES_TYPES):
        return "securities"
    return "general"


def _earnings_quality(ocf: float | None, net_income: float | None) -> str:
    """OCF/NI ratio check. Healthy >0.8, WATCH 0.6-0.8, RED <0.6."""
    if ocf is None or net_income is None or net_income == 0:
        return "UNKNOWN"
    if net_income < 0:
        return "WATCH"  # loss-making; positive OCF might still be ok
    ratio = ocf / net_income
    if ratio >= 0.8:
        return "CLEAN"
    if ratio >= 0.6:
        return "WATCH"
    return "RED"


def _safe(val) -> float | None:
    if pd.isna(val):
        return None
    return float(val)


def build_slice(tickers: list[str], asof: str) -> dict:
    df = pd.read_parquet(PARQUET).reset_index()
    avail_cols = [c for c in FA_COLS if c in df.columns]
    sub = (
        df[df["symbol"].isin(tickers)]
        .sort_values(["symbol", "year", "quarter"])
        .groupby("symbol", as_index=False)
        .last()[avail_cols]
    )

    positions = []
    for _, row in sub.iterrows():
        ticker = row["symbol"]
        company_type = _classify_type(row.get("companyType"))
        period = f"{int(row['year'])}Q{int(row['quarter'])}"

        # Core ratios
        roe = _safe(row.get("financialValues_ROE"))
        roa = _safe(row.get("financialValues_ROA"))
        gross_margin = _safe(row.get("financialValues_GrossMargin"))
        net_income_ttm = _safe(row.get("financialValues_ProfitAfterTax_TTM"))
        revenue_ttm = _safe(row.get("financialValues_TotalRevenue_TTM"))
        total_debt = _safe(row.get("financialValues_TotalDebt"))
        equity = _safe(row.get("financialValues_StockHolderEquity")) or _safe(row.get("financialValues_TotalEquity"))
        ocf = _safe(row.get("financialValues_CashflowFromOperatingActivity"))
        capex = _safe(row.get("financialValues_CAPEX"))
        total_asset = _safe(row.get("financialValues_TotalAsset"))

        # Computed
        net_margin_ttm = (net_income_ttm / revenue_ttm) if (revenue_ttm and revenue_ttm != 0) else None
        debt_to_equity = (total_debt / equity) if (equity and equity != 0 and total_debt is not None) else None

        # FCF: prefer parquet field, else compute from OCF - CAPEX
        fcf_raw = _safe(row.get("financialValues_FCF"))
        if fcf_raw is None and ocf is not None and capex is not None:
            fcf_raw = ocf - abs(capex)  # CAPEX stored as negative in some parquets

        fcf_margin = (fcf_raw / revenue_ttm) if (fcf_raw is not None and revenue_ttm and revenue_ttm != 0) else None

        eq_quality = _earnings_quality(ocf, net_income_ttm)

        positions.append({
            "ticker": ticker,
            "period": period,
            "company_type": company_type,
            "roe_ttm": round(roe, 4) if roe is not None else None,
            "roa_ttm": round(roa, 4) if roa is not None else None,
            "gross_margin_ttm": round(gross_margin, 4) if gross_margin is not None else None,
            "net_margin_ttm": round(net_margin_ttm, 4) if net_margin_ttm is not None else None,
            "debt_to_equity": round(debt_to_equity, 2) if debt_to_equity is not None else None,
            "fcf_margin_ttm": round(fcf_margin, 4) if fcf_margin is not None else None,
            "earnings_quality_flag": eq_quality,
            "ocf_to_ni_note": "OCF/NI ratio used for earnings quality; <0.6 = RED",
            "revenue_base_note": f"company_type={company_type}; revenue_ttm=None for banks/securities" if revenue_ttm is None else None,
            "source": "fa_quarterly parquet",
            "last_updated": asof,
        })

    # Tickers in book but missing from parquet
    in_parquet = {p["ticker"] for p in positions}
    for t in tickers:
        if t not in in_parquet:
            positions.append({
                "ticker": t,
                "period": None,
                "earnings_quality_flag": "UNKNOWN",
                "source": "fa_quarterly parquet",
                "last_updated": asof,
                "note": "Not found in fa_quarterly — Buffett must vote INSUFFICIENT_DATA",
            })

    return {
        "asof_date": asof,
        "status": "populated",
        "note": "Auto-generated by scripts/build_fa_council_slice.py. Buffett mind allowed input.",
        "schema_version": "1.0",
        "positions": positions,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tickers", default=None, help="Comma-separated tickers (default: all book positions)")
    ap.add_argument("--asof", default=date.today().isoformat())
    args = ap.parse_args()

    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",")]
    else:
        # Load from current_positions_derived
        positions_raw = json.loads(POSITIONS.read_text(encoding="utf-8"))
        tickers = [p["ticker"] for p in positions_raw]

    print(f"Building FA council slice for: {tickers}")
    payload = build_slice(tickers, args.asof)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUT} — {len(payload['positions'])} positions")

    # Print summary
    for p in payload["positions"]:
        flag = p.get("earnings_quality_flag", "?")
        roe = p.get("roe_ttm")
        de = p.get("debt_to_equity")
        print(f"  {p['ticker']:6s} ROE={roe!r:7} D/E={de!r:6} EQ={flag}")


if __name__ == "__main__":
    main()
