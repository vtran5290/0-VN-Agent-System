"""
Build data/decision/fa_council_slice.json from fa_quarterly parquet.

Extracts latest-quarter FA metrics for all book positions and formats
them for the Buffett council mind. Run after updating the parquet.

Usage:
  python scripts/build_fa_council_slice.py
  python scripts/build_fa_council_slice.py --tickers ACB,HSG,TCX
  python scripts/build_fa_council_slice.py --asof 2026-06-09

Notes:
- TTM OCF is built by summing last 4 quarters of CashflowFromOperatingActivity
  (no TTM cashflow column exists in the parquet)
- Financial institutions (banks, securities): revenue_ttm=None → EQ=EXEMPT
  OCF/NI metric does not apply due to loan/client cash treatment in CF statements
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

FA_COLS = [
    "symbol", "year", "quarter",
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

# D/E threshold above which we treat as financial institution (bank-like leverage)
FIN_INST_DE_THRESHOLD = 8.0


def _classify_type(revenue_ttm: float | None, debt_to_equity: float | None) -> str:
    """Detect financial institutions by revenue pattern and leverage.

    - revenue_ttm=None → no revenue base → financial institution
    - D/E > 8 → bank-like leverage
    """
    if revenue_ttm is None:
        return "financial_institution"
    if debt_to_equity is not None and debt_to_equity > FIN_INST_DE_THRESHOLD:
        return "financial_institution"
    return "general"


def _earnings_quality(ocf_ttm: float | None, net_income_ttm: float | None, is_fin_inst: bool) -> tuple[str, str]:
    """Return (flag, note)."""
    if is_fin_inst:
        return "EXEMPT", "OCF/NI not applicable for financial institutions (bank/securities CF treatment)"
    if ocf_ttm is None or net_income_ttm is None or net_income_ttm == 0:
        return "UNKNOWN", "TTM OCF or NI unavailable"
    if net_income_ttm < 0:
        return "WATCH", f"NI negative; OCF_TTM={ocf_ttm/1e9:.1f}B"
    ratio = ocf_ttm / net_income_ttm
    note = f"OCF_TTM/NI_TTM={ratio:.2f} (CLEAN≥0.8, WATCH 0.6–0.8, RED<0.6)"
    if ratio >= 0.8:
        return "CLEAN", note
    if ratio >= 0.6:
        return "WATCH", note
    return "RED", note


def _safe(val) -> float | None:
    if pd.isna(val):
        return None
    return float(val)


def _build_ttm_cashflow(df_ticker: pd.DataFrame, col: str) -> float | None:
    """Sum last 4 quarters of a CF column to get TTM approximation."""
    if col not in df_ticker.columns:
        return None
    vals = df_ticker[col].dropna().tail(4)
    if len(vals) < 2:
        return None
    return float(vals.sum())


def build_slice(tickers: list[str], asof: str) -> dict:
    df = pd.read_parquet(PARQUET).reset_index()
    avail_cols = [c for c in FA_COLS if c in df.columns]
    df_filtered = (
        df[df["symbol"].isin(tickers)]
        .sort_values(["symbol", "year", "quarter"])
    )

    # TTM cashflow aggregation (sum last 4 quarters per ticker)
    ocf_col = "financialValues_CashflowFromOperatingActivity"
    capex_col = "financialValues_CAPEX"
    ttm_ocf: dict[str, float | None] = {}
    ttm_capex: dict[str, float | None] = {}
    for ticker, grp in df_filtered.groupby("symbol"):
        ttm_ocf[ticker] = _build_ttm_cashflow(grp, ocf_col)
        ttm_capex[ticker] = _build_ttm_cashflow(grp, capex_col)

    # Latest row per ticker for balance sheet / income statement fields
    sub = df_filtered.groupby("symbol", as_index=False).last()[avail_cols]

    positions = []
    for _, row in sub.iterrows():
        ticker = row["symbol"]
        period = f"{int(row['year'])}Q{int(row['quarter'])}"

        roe = _safe(row.get("financialValues_ROE"))
        roa = _safe(row.get("financialValues_ROA"))
        gross_margin = _safe(row.get("financialValues_GrossMargin"))
        net_income_ttm = _safe(row.get("financialValues_ProfitAfterTax_TTM"))
        revenue_ttm = _safe(row.get("financialValues_TotalRevenue_TTM"))
        total_debt = _safe(row.get("financialValues_TotalDebt"))
        equity = _safe(row.get("financialValues_StockHolderEquity")) or _safe(row.get("financialValues_TotalEquity"))

        net_margin_ttm = (net_income_ttm / revenue_ttm) if (revenue_ttm and revenue_ttm != 0) else None
        debt_to_equity = (total_debt / equity) if (equity and equity != 0 and total_debt is not None) else None

        company_type = _classify_type(revenue_ttm, debt_to_equity)
        is_fin = company_type == "financial_institution"

        # FCF TTM: prefer parquet FCF field (may be latest quarter only),
        # else compute OCF_TTM - |CAPEX_TTM|
        fcf_raw = _safe(row.get("financialValues_FCF"))
        ocf_ttm = ttm_ocf.get(ticker)
        capex_ttm = ttm_capex.get(ticker)
        if fcf_raw is None and ocf_ttm is not None and capex_ttm is not None:
            fcf_raw = ocf_ttm - abs(capex_ttm)

        fcf_margin = (fcf_raw / revenue_ttm) if (fcf_raw is not None and revenue_ttm and revenue_ttm != 0) else None

        eq_flag, eq_note = _earnings_quality(ocf_ttm, net_income_ttm, is_fin)

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
            "earnings_quality_flag": eq_flag,
            "eq_note": eq_note,
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
        "schema_version": "1.1",
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
        positions_raw = json.loads(POSITIONS.read_text(encoding="utf-8"))
        tickers = [p["ticker"] for p in positions_raw]

    print(f"Building FA council slice for: {tickers}")
    payload = build_slice(tickers, args.asof)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUT} — {len(payload['positions'])} positions")

    for p in payload["positions"]:
        flag = p.get("earnings_quality_flag", "?")
        roe = p.get("roe_ttm")
        de = p.get("debt_to_equity")
        ctype = p.get("company_type", "?")
        print(f"  {p['ticker']:6s} type={ctype:22s} ROE={roe!r:7} D/E={de!r:6} EQ={flag}")


if __name__ == "__main__":
    main()
