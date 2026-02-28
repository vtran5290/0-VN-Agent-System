from __future__ import annotations

"""
fetch_fundamentals_raw.py
=========================

Build `data/fundamentals_raw.csv` for FA Cohort Study by pulling quarterly
fundamentals from FireAnt.

Schema (CSV header):
  symbol,report_date,revenue,net_profit,equity,gross_profit,gross_margin,total_debt,shares_outstanding

Notes:
- Uses `src.canslim.fireant_fetcher` (same BASE_URL/session & token handling).
- If any field (e.g. equity, total_debt, shares_outstanding) is unavailable for
  a given (symbol, quarter), it is left empty (NaN) but the row is still kept.
- Units: FireAnt raw VND numbers are preserved; no scaling is applied.
- `report_date` is the quarter-end date: YYYY-03-31, YYYY-06-30, YYYY-09-30, YYYY-12-31.

Typical usage (from repo root):

  .\.venv\Scripts\python.exe minervini_backtest/scripts/fetch_fundamentals_raw.py ^
      --symbols-file minervini_backtest/config/watchlist_80.txt ^
      --start 2014-01-01 --end 2024-12-31 ^
      --out data/fundamentals_raw.csv
"""

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, date
from pathlib import Path
from typing import Iterable, List, Dict, Any, Tuple

import pandas as pd

# ---------------------------------------------------------------------------
# Import FireAnt helpers from repo (BASE_URL, session, financials parser)
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent  # .../minervini_backtest
REPO_ROOT = ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    # Reuse existing FireAnt plumbing (BASE_URL, session, token via FIREANT_TOKEN)
    from src.canslim.fireant_fetcher import (  # type: ignore
        BASE_URL,
        _get as fireant_get,
        fetch_financial_statements,
        _parse_financials,
    )
except Exception as e:  # pragma: no cover - defensive, should not happen in normal runs
    raise RuntimeError(
        "Failed to import src.canslim.fireant_fetcher. "
        "Run this script from the repo root so that 'src' is importable."
    ) from e


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_Q_END_DAY = {
    1: (3, 31),
    2: (6, 30),
    3: (9, 30),
    4: (12, 31),
}


def _quarter_end_date(year: int, quarter: int) -> date:
    """Map (year, quarter) -> quarter-end date."""
    if quarter not in _Q_END_DAY:
        raise ValueError(f"Invalid quarter: {quarter}")
    m, d = _Q_END_DAY[quarter]
    return date(year, m, d)


def _parse_bs_series(item: Dict[str, Any]) -> Dict[Tuple[int, int], float]:
    """Convert one balance-sheet line item into {(year, quarter): value}."""
    out: Dict[Tuple[int, int], float] = {}
    for v in item.get("values", []) or []:
        y = v.get("year")
        q = v.get("quarter")
        val = v.get("value")
        if y is None or q is None or val is None:
            continue
        try:
            out[(int(y), int(q))] = float(val)
        except (TypeError, ValueError):
            continue
    return out


def _match_name(name: str, patterns: Iterable[str]) -> bool:
    n = (name or "").lower()
    return any(p in n for p in patterns)


def _parse_balance_sheet(raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Parse FireAnt full-financial-reports balance sheet payload into
    year/quarter-level equity, total_debt, and (approximate) shares_outstanding.

    Heuristics (facts-only, no fabrication):
    - total_debt: line "A. Nợ phải trả" (total liabilities).
    - equity: prefer "I. Vốn chủ sở hữu" if present (owner's equity),
      else fallback to "B. Nguồn vốn chủ sở hữu" (total equity).
    - shares_outstanding (approx): derived from line "1. Vốn đầu tư của chủ sở hữu"
      by dividing by par value 10,000 VND/share. If that line is missing, the field
      is left as None (facts-only, no extrapolation).

    Returns list of dicts:
      {year, quarter, equity, total_debt, shares_outstanding}
    """
    if not raw or not isinstance(raw, list):
        return []

    total_liab: Dict[Tuple[int, int], float] = {}
    equity_owner: Dict[Tuple[int, int], float] = {}
    equity_total: Dict[Tuple[int, int], float] = {}
    capital_owner: Dict[Tuple[int, int], float] = {}

    for item in raw:
        name = item.get("name", "")
        if _match_name(name, ["a. nợ phải trả", "nợ phải trả"]):
            total_liab = _parse_bs_series(item)
        elif _match_name(name, ["i. vốn chủ sở hữu"]):
            equity_owner = _parse_bs_series(item)
        elif _match_name(name, ["b. nguồn vốn chủ sở hữu", "nguồn vốn chủ sở hữu"]):
            equity_total = _parse_bs_series(item)
        elif _match_name(name, ["vốn đầu tư của chủ sở hữu"]):
            # vốn điều lệ / vốn góp của chủ sở hữu
            capital_owner = _parse_bs_series(item)

    equity = equity_owner if equity_owner else equity_total
    keys = sorted(set(total_liab.keys()) | set(equity.keys()) | set(capital_owner.keys()))
    if not keys:
        return []

    records: List[Dict[str, Any]] = []
    for (y, q) in keys:
        if q == 0:
            # Ignore annual-only rows here; FA cohort works on quarterlies.
            continue
        eq_val = equity.get((y, q))
        debt_val = total_liab.get((y, q))
        cap_val = capital_owner.get((y, q))

        # Approximate shares_outstanding from capital / 10,000 VND par.
        if cap_val is not None:
            try:
                shares_val: float | None = float(cap_val) / 10000.0
            except (TypeError, ValueError):
                shares_val = None
        else:
            shares_val = None
        records.append(
            {
                "year": y,
                "quarter": q,
                "equity": float(eq_val) if eq_val is not None else None,
                "total_debt": float(debt_val) if debt_val is not None else None,
                    "shares_outstanding": float(shares_val) if shares_val is not None else None,
            }
        )
    return records


@dataclass
class FundamentalsRow:
    symbol: str
    report_date: date
    revenue: float | None
    net_profit: float | None
    equity: float | None
    gross_profit: float | None
    gross_margin: float | None
    total_debt: float | None
    shares_outstanding: float | None


def _load_symbols(path: Path) -> List[str]:
    text = path.read_text(encoding="utf-8")
    syms: List[str] = []
    for ln in text.splitlines():
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        syms.append(s.upper())
    return syms


def fetch_fundamentals_for_symbol(
    symbol: str,
    start: date,
    end: date,
    income_limit: int = 80,
    balance_limit: int = 80,
) -> List[FundamentalsRow]:
    """
    Fetch quarterly fundamentals for one symbol between start/end (inclusive).

    Income statement: FireAnt full-financial-reports type=2 (via _parse_financials).
    Balance sheet:    FireAnt full-financial-reports type=1 (parsed here).

    - If any component (income / balance sheet) is missing for a given quarter,
      the corresponding fields are left as None but the row is still kept.
    """
    rows: List[FundamentalsRow] = []

    # Determine anchor year/quarter near `end` for FireAnt "limit" window
    end_year = end.year
    end_q = (end.month - 1) // 3 + 1

    # --- Income statement (type=2) ---
    try:
        raw_income = fetch_financial_statements(
            symbol=symbol,
            year=end_year,
            quarter=end_q,
            limit=income_limit,
            report_type=2,
        )
        inc_records = _parse_financials(raw_income)
    except Exception as e:
        print(f"[fundamentals_raw] {symbol}: income fetch failed: {e}", file=sys.stderr)
        inc_records = []

    inc_df = (
        pd.DataFrame(inc_records)
        if inc_records
        else pd.DataFrame(columns=["year", "quarter", "revenue", "net_income", "eps", "gross_margin"])
    )

    # --- Balance sheet (type=1) ---
    try:
        raw_bs = fetch_financial_statements(
            symbol=symbol,
            year=end_year,
            quarter=end_q,
            limit=balance_limit,
            report_type=1,  # 1 = Balance sheet in FireAnt full-financial-reports
        )
        bs_records = _parse_balance_sheet(raw_bs)
    except Exception as e:
        print(f"[fundamentals_raw] {symbol}: balance-sheet fetch failed: {e}", file=sys.stderr)
        bs_records = []

    bs_df = (
        pd.DataFrame(bs_records)
        if bs_records
        else pd.DataFrame(columns=["year", "quarter", "equity", "total_debt", "shares_outstanding"])
    )

    if inc_df.empty and bs_df.empty:
        return []

    merged = pd.merge(
        inc_df,
        bs_df,
        on=["year", "quarter"],
        how="outer",
        suffixes=("", "_bs"),
    )

    # Only quarters 1–4, filter by date range
    valid_quarters = merged["quarter"].astype(int).between(1, 4)
    merged = merged[valid_quarters].copy()

    def _to_report_date(row: pd.Series) -> date:
        y = int(row["year"])
        q = int(row["quarter"])
        return _quarter_end_date(y, q)

    merged["report_date"] = merged.apply(_to_report_date, axis=1)
    merged = merged[(merged["report_date"] >= start) & (merged["report_date"] <= end)].copy()
    if merged.empty:
        return []

    merged = merged.sort_values(["year", "quarter"]).reset_index(drop=True)

    for _, row in merged.iterrows():
        rev = row.get("revenue")
        ni = row.get("net_income")
        gm = row.get("gross_margin")

        try:
            rev_f = float(rev) if pd.notna(rev) else None
        except (TypeError, ValueError):
            rev_f = None

        try:
            ni_f = float(ni) if pd.notna(ni) else None
        except (TypeError, ValueError):
            ni_f = None

        try:
            gm_f = float(gm) if pd.notna(gm) else None
        except (TypeError, ValueError):
            gm_f = None

        # Derive gross_profit if both revenue and gross_margin are present.
        gp_f: float | None
        if rev_f is not None and gm_f is not None:
            gp_f = rev_f * gm_f
        else:
            gp_f = None

        eq = row.get("equity")
        debt = row.get("total_debt")
        sh = row.get("shares_outstanding")
        try:
            eq_f = float(eq) if pd.notna(eq) else None
        except (TypeError, ValueError):
            eq_f = None
        try:
            debt_f = float(debt) if pd.notna(debt) else None
        except (TypeError, ValueError):
            debt_f = None
        try:
            shares = float(sh) if pd.notna(sh) else None
        except (TypeError, ValueError):
            shares = None

        rows.append(
            FundamentalsRow(
                symbol=symbol.upper(),
                report_date=row["report_date"],
                revenue=rev_f,
                net_profit=ni_f,
                equity=eq_f,
                gross_profit=gp_f,
                gross_margin=gm_f,
                total_debt=debt_f,
                shares_outstanding=shares,
            )
        )

    return rows


def build_fundamentals_csv(
    symbols_file: Path,
    start_str: str,
    end_str: str,
    out_path: Path,
) -> None:
    start = datetime.strptime(start_str, "%Y-%m-%d").date()
    end = datetime.strptime(end_str, "%Y-%m-%d").date()
    if start > end:
        raise ValueError(f"start ({start}) must be <= end ({end})")

    if not symbols_file.exists():
        raise FileNotFoundError(f"Symbols file not found: {symbols_file}")

    symbols = _load_symbols(symbols_file)
    if not symbols:
        raise ValueError(f"No symbols found in {symbols_file}")

    all_rows: List[FundamentalsRow] = []
    for sym in symbols:
        print(f"[fundamentals_raw] Fetching fundamentals for {sym}...")
        try:
            sym_rows = fetch_fundamentals_for_symbol(sym, start, end)
        except Exception as e:
            print(f"[fundamentals_raw] {sym}: failed with error: {e}", file=sys.stderr)
            continue
        all_rows.extend(sym_rows)

    if not all_rows:
        print("[fundamentals_raw] No fundamentals rows fetched; nothing to write.", file=sys.stderr)
        # Still write an empty CSV with header to satisfy downstream scripts.
        cols = [
            "symbol",
            "report_date",
            "revenue",
            "net_profit",
            "equity",
            "gross_profit",
            "gross_margin",
            "total_debt",
            "shares_outstanding",
        ]
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=cols).to_csv(out_path, index=False)
        return

    df = pd.DataFrame(
        [
            {
                "symbol": r.symbol,
                "report_date": r.report_date,
                "revenue": r.revenue,
                "net_profit": r.net_profit,
                "equity": r.equity,
                "gross_profit": r.gross_profit,
                "gross_margin": r.gross_margin,
                "total_debt": r.total_debt,
                "shares_outstanding": r.shares_outstanding,
            }
            for r in all_rows
        ]
    )

    df["symbol"] = df["symbol"].astype(str).str.strip().str.upper()
    df["report_date"] = pd.to_datetime(df["report_date"])
    df = df.sort_values(["symbol", "report_date"]).reset_index(drop=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    n_rows = len(df)
    n_syms = df["symbol"].nunique()
    print(f"[fundamentals_raw] Wrote {n_rows} rows for {n_syms} symbols to {out_path}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch quarterly fundamentals from FireAnt and build fundamentals_raw.csv")
    ap.add_argument(
        "--symbols-file",
        required=True,
        help="Path to text file with one symbol per line",
    )
    ap.add_argument(
        "--start",
        required=True,
        help="Start date (YYYY-MM-DD) — mapped to earliest quarter-end >= this date",
    )
    ap.add_argument(
        "--end",
        required=True,
        help="End date (YYYY-MM-DD) — mapped to latest quarter-end <= this date",
    )
    ap.add_argument(
        "--out",
        required=True,
        help="Output CSV path (fundamentals_raw.csv)",
    )
    args = ap.parse_args()

    try:
        build_fundamentals_csv(
            symbols_file=Path(args.symbols_file),
            start_str=args.start,
            end_str=args.end,
            out_path=Path(args.out),
        )
    except Exception as e:
        print(f"[fundamentals_raw] Error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

