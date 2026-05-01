# minervini_backtest/scripts/build_fa_minervini_csv.py — Build FA CSV for Minervini cohort study
"""
Build data/fa_minervini.csv from a raw fundamentals CSV.

Input (--in): quarterly fundamentals with columns (some may be missing):
  symbol, report_date,
  revenue, net_profit, equity,
  gross_profit OR gross_margin,
  total_debt,
  shares_outstanding (optional)

Output (--out): CSV with schema:
  symbol,report_date,
  eps_yoy,sales_yoy,roe,gross_margin,gross_margin_yoy,debt_to_equity,eps_qoq_accel_flag,
  earnings_yoy,earnings_qoq_accel_flag,
  earnings_accel_2step_flag,accel_confidence,profit_positive
  (2-step: yoy_q0 > yoy_q1 > yoy_q2; fallback 1-step with accel_confidence=low if missing q2)

Usage:
  python minervini_backtest/scripts/build_fa_minervini_csv.py --in data/fundamentals_raw.csv --out data/fa_minervini.csv
"""
from __future__ import annotations

import sys
from pathlib import Path
import argparse

import pandas as pd


def _to_float_or_none(value: object) -> float | None:
    """Convert scalar to float, guarding against pandas NA / NaN."""
    if value is None:
        return None
    # Guard explicit pandas NA scalars
    try:
        import pandas as _pd  # local import to avoid circulars
        if isinstance(value, type(_pd.NA)):
            return None
    except Exception:
        pass
    try:
        if pd.isna(value):
            return None
    except Exception:
        # If isna itself fails, fall back to best-effort float()
        try:
            return float(value)
        except Exception:
            return None
    try:
        return float(value)
    except Exception:
        return None


def build_fa_csv(in_path: str | Path, out_path: str | Path) -> None:
    in_path = Path(in_path)
    out_path = Path(out_path)

    if not in_path.exists():
        raise FileNotFoundError(f"Input fundamentals CSV not found: {in_path}")

    df = pd.read_csv(in_path)
    # Precheck: empty or tiny input → do not overwrite output
    if df.empty or len(df) < 5:
        print(
            "[WARN] fundamentals_raw empty or tiny; skipping rebuild; using existing data/fa_minervini.csv"
        )
        return
    required_basic = ["symbol", "report_date"]
    for col in required_basic:
        if col not in df.columns:
            raise ValueError(f"Input CSV must contain column '{col}'")

    # Normalize symbol and dates
    df["symbol"] = df["symbol"].astype(str).str.strip().str.upper()
    df["report_date"] = pd.to_datetime(df["report_date"])
    df = df.sort_values(["symbol", "report_date"]).reset_index(drop=True)

    # Compute gross_margin if missing
    if "gross_margin" in df.columns:
        gm = df["gross_margin"].astype(float)
    elif "gross_profit" in df.columns and "revenue" in df.columns:
        rev = df["revenue"].astype(float)
        gp = df["gross_profit"].astype(float)
        gm = gp / rev.replace(0, pd.NA)
    else:
        gm = pd.Series(pd.NA, index=df.index, dtype="float64")

    df["gross_margin_calc"] = gm

    # Compute EPS if shares_outstanding present
    if "shares_outstanding" in df.columns and "net_profit" in df.columns:
        sh = pd.to_numeric(df["shares_outstanding"], errors="coerce")
        npf = pd.to_numeric(df["net_profit"], errors="coerce")
        eps = npf / sh.replace(0, pd.NA)
    else:
        eps = pd.Series(pd.NA, index=df.index, dtype="float64")
    df["eps_calc"] = eps

    # Helper: compute YoY (% change vs t-4) per symbol
    def _yoy(series: pd.Series) -> pd.Series:
        prev = series.shift(4)
        return (series / prev.replace(0, pd.NA) - 1.0) * 100.0

    out_rows = []
    for sym, g in df.groupby("symbol"):
        g = g.sort_values("report_date").reset_index(drop=True)

        # base series
        revenue = g.get("revenue")
        net_profit = g.get("net_profit")
        equity = g.get("equity")
        gross_margin = g["gross_margin_calc"]
        eps_vals = g["eps_calc"]

        # YoY metrics
        eps_yoy = _yoy(eps_vals) if eps_vals.notna().any() else pd.Series(index=g.index, dtype="float64")
        sales_yoy = (
            _yoy(pd.to_numeric(revenue, errors="coerce"))
            if revenue is not None and revenue.notna().any()
            else pd.Series(index=g.index, dtype="float64")
        )
        gm_yoy = (
            _yoy(pd.to_numeric(gross_margin, errors="coerce"))
            if gross_margin.notna().any()
            else pd.Series(index=g.index, dtype="float64")
        )

        # Earnings YoY from net_profit (can be used as EPS proxy when shares series is missing)
        if net_profit is not None and net_profit.notna().any():
            npf_yoy_base = pd.to_numeric(net_profit, errors="coerce")
            earnings_yoy = _yoy(npf_yoy_base)
        else:
            earnings_yoy = pd.Series(index=g.index, dtype="float64")

        # TTM net profit and ROE proxy
        if net_profit is not None and equity is not None:
            npf = pd.to_numeric(net_profit, errors="coerce")
            eq = pd.to_numeric(equity, errors="coerce")
            npf_ttm = npf.rolling(4, min_periods=4).sum()
            # simple ROE proxy: 100 * TTM net profit / equity
            roe = 100.0 * npf_ttm / eq.replace(0, pd.NA)
        else:
            roe = pd.Series(index=g.index, dtype="float64")

        # Debt / equity
        if "total_debt" in g.columns and equity is not None:
            debt = pd.to_numeric(g["total_debt"], errors="coerce")
            dte = debt / eq.replace(0, pd.NA)
        else:
            dte = pd.Series(index=g.index, dtype="float64")

        # EPS accel flag
        accel_flag = pd.Series(0, index=g.index, dtype="int64")
        if eps_yoy.notna().any():
            prev_eps_yoy = eps_yoy.shift(1)
            mask = (eps_yoy.notna()) & (prev_eps_yoy.notna()) & (eps_yoy > prev_eps_yoy)
            accel_flag.loc[mask] = 1

        # Earnings accel flag (1-step: q0 > q1)
        earnings_accel_flag = pd.Series(0, index=g.index, dtype="int64")
        if earnings_yoy.notna().any():
            prev_earnings_yoy = earnings_yoy.shift(1)
            e_mask = (earnings_yoy.notna()) & (prev_earnings_yoy.notna()) & (earnings_yoy > prev_earnings_yoy)
            earnings_accel_flag.loc[e_mask] = 1

        # 2-step earnings accel (Mark-style): yoy_q0 > yoy_q1 > yoy_q2
        prev1 = earnings_yoy.shift(1)
        prev2 = earnings_yoy.shift(2)
        has_three = earnings_yoy.notna() & prev1.notna() & prev2.notna()
        two_step_mask = has_three & (earnings_yoy > prev1) & (prev1 > prev2)
        earnings_accel_2step_flag = pd.Series(0, index=g.index, dtype="int64")
        earnings_accel_2step_flag.loc[two_step_mask] = 1
        accel_confidence = pd.Series("low", index=g.index, dtype="object")
        accel_confidence.loc[has_three] = "high"

        for pos, (_, row) in enumerate(g.iterrows()):
            v_eps_yoy = _to_float_or_none(eps_yoy.iloc[pos])
            v_sales_yoy = _to_float_or_none(sales_yoy.iloc[pos])
            v_roe = _to_float_or_none(roe.iloc[pos])
            v_gm_yoy = _to_float_or_none(gm_yoy.iloc[pos])
            v_dte = _to_float_or_none(dte.iloc[pos])
            v_earnings_yoy = _to_float_or_none(earnings_yoy.iloc[pos])
            # Profit guard: current quarter net_profit > 0 (Mark: avoid accel from negative base)
            npf_val = _to_float_or_none(row.get("net_profit"))
            profit_positive = 1 if (npf_val is not None and npf_val > 0) else 0

            v_gross_margin = _to_float_or_none(row.get("gross_margin_calc"))
            out_rows.append(
                {
                    "symbol": sym,
                    "report_date": row["report_date"].date(),
                    "eps_yoy": v_eps_yoy,
                    "sales_yoy": v_sales_yoy,
                    "roe": v_roe,
                    "gross_margin": v_gross_margin,
                    "gross_margin_yoy": v_gm_yoy,
                    "debt_to_equity": v_dte,
                    "eps_qoq_accel_flag": int(accel_flag.iloc[pos]),
                    "earnings_yoy": v_earnings_yoy,
                    "earnings_qoq_accel_flag": int(earnings_accel_flag.iloc[pos]),
                    "earnings_accel_2step_flag": int(earnings_accel_2step_flag.iloc[pos]),
                    "accel_confidence": str(accel_confidence.iloc[pos]),
                    "profit_positive": profit_positive,
                }
            )

    if not out_rows:
        print("No rows produced; input may be empty. Skipping write to avoid overwriting.")
        return
    out_df = pd.DataFrame(out_rows)
    out_df = out_df.sort_values(["symbol", "report_date"]).reset_index(drop=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_path, index=False)
    print(f"Wrote FA CSV: {out_path} ({len(out_df)} rows, {out_df['symbol'].nunique()} symbols)")


def main() -> int:
    ap = argparse.ArgumentParser(description="Build fa_minervini.csv from fundamentals_raw.csv")
    ap.add_argument("--in", dest="in_path", required=True, help="Input fundamentals CSV (raw)")
    ap.add_argument("--out", dest="out_path", required=True, help="Output FA CSV (fa_minervini.csv)")
    args = ap.parse_args()

    try:
        build_fa_csv(args.in_path, args.out_path)
    except Exception as e:
        print(f"[build_fa_minervini_csv] Error: {e}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

