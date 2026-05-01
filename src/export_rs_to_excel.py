from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import RSEngineConfig
from .data_loader import load_stock_universe
from .rs_engine import run_rs_engine


def export_last_90_days_rs_to_excel(
    stock_list_xlsx: str,
    output_xlsx: str = "All_Stock_List_with_RS.xlsx",
    days: int = 90,
) -> None:
    """
    Populate an Excel file with RS metrics for the last N trading days
    for all tickers listed in the input workbook.
    """
    cfg = RSEngineConfig()
    universe = load_stock_universe(cfg.data_stocks_dir)
    result = run_rs_engine(universe, cfg)

    ts = result.full_timeseries.copy()

    # Load tickers from your Excel list (expects a column named 'ticker')
    stock_list_path = Path(stock_list_xlsx)
    df_list = pd.read_excel(stock_list_path)
    df_list.columns = [str(c).strip().lower() for c in df_list.columns]
    if "ticker" not in df_list.columns:
        raise ValueError("Expected a column named 'ticker' in the Excel file.")

    tickers = df_list["ticker"].astype(str).str.upper().unique().tolist()

    # Filter to those tickers
    ts = ts[ts["ticker"].isin(tickers)].copy()

    # Keep only last `days` per ticker (trading days)
    ts = ts.sort_values(["ticker", "date"])
    ts["rank_recent"] = ts.groupby("ticker")["date"].rank(
        method="first", ascending=False
    )
    ts_n = ts[ts["rank_recent"] <= days].copy().drop(columns=["rank_recent"])

    ts_n = ts_n[
        [
            "date",
            "ticker",
            "close",
            "value",
            "rs_line",
            "rs_score",
            "rs_percentile",
        ]
    ].sort_values(["ticker", "date"])

    # Write to Excel: original list + RS panel
    with pd.ExcelWriter(output_xlsx, engine="openpyxl") as writer:
        df_list.to_excel(writer, sheet_name="Stock_List", index=False)
        ts_n.to_excel(writer, sheet_name="RS_Last_90d", index=False)


if __name__ == "__main__":
    export_last_90_days_rs_to_excel(
        r"c:\Users\LOLII\Downloads\All Stock List.xlsx",
        output_xlsx=r"c:\Users\LOLII\Downloads\All_Stock_List_with_RS.xlsx",
        days=90,
    )

