"""Merge VNINDEX from CSV + optional FireAnt; offline gate; source_used metadata."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

_REPO = Path(__file__).resolve().parents[3]

from src.intake.fireant_historical import fetch_historical  # noqa: E402

VNINDEX_CSV = _REPO / "minervini_backtest" / "data" / "raw" / "VNINDEX.csv"
VIN_SYMBOLS = ("VIC", "VHM", "VRE")
STOCK_CSV_LEGACY = _REPO / "minervini_backtest" / "data" / "raw"
STOCK_CSV_NEW = _REPO / "data" / "stocks"


@dataclass
class VnindexLoadMeta:
    csv_max_date: pd.Timestamp
    merged_max_date: pd.Timestamp
    extended_past_csv: bool


def _read_vnindex_csv_only() -> pd.DataFrame:
    df = pd.read_csv(VNINDEX_CSV)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def _stock_csv_only(symbol: str) -> pd.DataFrame:
    legacy = STOCK_CSV_LEGACY / f"{symbol}.csv"
    new = STOCK_CSV_NEW / f"{symbol}.csv"
    if legacy.exists():
        df = pd.read_csv(legacy)
        df["close"] = df["close"].astype(float) / 1000.0
    elif new.exists():
        df = pd.read_csv(new)
    else:
        return pd.DataFrame(columns=["date", "close", "volume"])
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def load_vnindex_tracked(end: str, offline: bool) -> tuple[pd.DataFrame, VnindexLoadMeta]:
    base = _read_vnindex_csv_only()
    csv_max = pd.Timestamp(base["date"].max())
    if offline:
        merged = base.copy()
        meta = VnindexLoadMeta(
            csv_max_date=csv_max,
            merged_max_date=pd.Timestamp(merged["date"].max()),
            extended_past_csv=False,
        )
        return merged, meta
    last_csv = csv_max
    fetch_start = (last_csv - pd.Timedelta(days=5)).date().isoformat()
    extended = False
    try:
        rows = fetch_historical("VNINDEX", fetch_start, end)
        if rows:
            recent = pd.DataFrame(
                [
                    {
                        "date": pd.Timestamp(r.d),
                        "open": float(r.o),
                        "high": float(r.h),
                        "low": float(r.l),
                        "close": float(r.c),
                        "volume": float(r.v) if r.v is not None else float("nan"),
                    }
                    for r in rows
                ]
            )
            merged = pd.concat([base, recent], ignore_index=True)
            merged = merged.drop_duplicates(subset=["date"], keep="last").sort_values("date").reset_index(drop=True)
            if pd.Timestamp(merged["date"].max()) > csv_max:
                extended = True
        else:
            merged = base.copy()
    except Exception:
        merged = base.copy()
    meta = VnindexLoadMeta(
        csv_max_date=csv_max,
        merged_max_date=pd.Timestamp(merged["date"].max()),
        extended_past_csv=extended,
    )
    return merged, meta


def stock_csv_max_dates() -> dict[str, pd.Timestamp]:
    out: dict[str, pd.Timestamp] = {}
    for sym in VIN_SYMBOLS:
        df = _stock_csv_only(sym)
        if df.empty:
            out[sym] = pd.NaT
        else:
            out[sym] = pd.Timestamp(df["date"].max())
    return out


def resolve_source_used(
    vnindex_meta: VnindexLoadMeta,
    end: str,
    offline: bool,
) -> str:
    if vnindex_meta.extended_past_csv:
        return "csv+fireant"
    if offline:
        return "csv_only"
    end_ts = pd.Timestamp(end)
    smax = stock_csv_max_dates()
    if any(pd.notna(smax[s]) and smax[s] < end_ts for s in VIN_SYMBOLS):
        return "csv+fireant"
    return "csv_only"


def build_source_meta(
    end: str,
    offline: bool,
    vnindex_meta: VnindexLoadMeta,
) -> dict[str, Any]:
    stock_csv = stock_csv_max_dates()
    assert_offline_coverage(end, offline, vnindex_meta, stock_csv)
    assert_merged_covers_end(end, vnindex_meta)
    return {
        "requested_end_date": end,
        "offline": offline,
        "vnindex_csv_max_date": str(vnindex_meta.csv_max_date.date()),
        "vnindex_merged_max_date": str(vnindex_meta.merged_max_date.date()),
        "stock_csv_max_dates": {k: (str(v.date()) if pd.notna(v) else None) for k, v in stock_csv.items()},
        "source_used": resolve_source_used(vnindex_meta, end, offline),
    }


def assert_merged_covers_end(end: str, vnindex_meta: VnindexLoadMeta) -> None:
    """Fail if merged VNINDEX does not reach requested calendar end (online or offline)."""
    end_ts = pd.Timestamp(end).normalize()
    if vnindex_meta.merged_max_date.normalize() < end_ts:
        raise SystemExit(
            "Data does not reach requested --end date (even after optional FireAnt fetch).\n"
            f"  requested_end_date: {end}\n"
            f"  merged_last_bar_date: {vnindex_meta.merged_max_date.date()}\n"
            "Fix: refresh CSVs, check network/cache, or choose a later available date as --end."
        )


def assert_offline_coverage(
    end: str,
    offline: bool,
    vnindex_meta: VnindexLoadMeta,
    stock_csv_max: dict[str, pd.Timestamp],
) -> None:
    if not offline:
        return
    end_ts = pd.Timestamp(end).normalize()
    merged_max = vnindex_meta.merged_max_date.normalize()
    if merged_max < end_ts:
        raise SystemExit(
            "OFFLINE reproducibility check failed: merged VNINDEX last bar is before --end.\n"
            f"  requested_end_date: {end}\n"
            f"  vnindex_csv_max_date: {vnindex_meta.csv_max_date.date()}\n"
            f"  merged_last_bar_date: {merged_max.date()}\n"
            "Fix: refresh minervini_backtest/data/raw/VNINDEX.csv through the requested date, "
            "or run without --offline to allow FireAnt fetch."
        )
    for sym, mx in stock_csv_max.items():
        if pd.isna(mx):
            raise SystemExit(
                f"OFFLINE: missing CSV for required symbol {sym}. "
                f"Provide data/stocks/{sym}.csv or minervini_backtest/data/raw/{sym}.csv"
            )
        if pd.Timestamp(mx).normalize() < end_ts:
            raise SystemExit(
                f"OFFLINE reproducibility check failed: {sym} CSV ends before --end.\n"
                f"  requested_end_date: {end}\n"
                f"  {sym}_csv_max_date: {mx.date()}\n"
                "Fix: refresh stock CSVs or run without --offline."
            )
