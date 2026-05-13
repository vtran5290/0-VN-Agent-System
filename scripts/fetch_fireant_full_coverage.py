from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.data.fireant_client import get_client


logger = logging.getLogger("fetch_fireant_full_coverage")

MARKET_INDEX_ALLOWLIST = {"VNINDEX", "VN30", "HNXINDEX", "HNX30", "UPINDEX"}
MARKET_INDEX_KEYWORDS = ["VN", "HNX", "UP", "30", "100", "MID", "SMALL", "ALL"]


def _slugify(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", text.strip())
    return slug.strip("_") or "unknown"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_csv(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    out.to_csv(path, index=False)


def _write_parquet(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def _collect_market_indices(client) -> List[Dict[str, Any]]:
    found: Dict[str, Dict[str, Any]] = {}
    for kw in MARKET_INDEX_KEYWORDS:
        items = client.search_symbols(kw, symbol_type="index", limit=50)
        for item in items:
            symbol = str(item.get("symbol") or "").upper().strip()
            if symbol in MARKET_INDEX_ALLOWLIST:
                found[symbol] = {
                    "symbol": symbol,
                    "name": item.get("name"),
                    "type": item.get("type"),
                }

    for symbol in sorted(MARKET_INDEX_ALLOWLIST):
        found.setdefault(symbol, {"symbol": symbol, "name": None, "type": "index"})

    return [found[symbol] for symbol in sorted(found)]


def _fetch_market_index_histories(
    client,
    indices: List[Dict[str, Any]],
    start: str,
    end: str,
    out_dir: Path,
    delay: float,
) -> List[Dict[str, Any]]:
    manifest: List[Dict[str, Any]] = []
    for item in indices:
        symbol = item["symbol"]
        df = client.get_ohlcv(symbol, start, end)
        warnings = list(df.attrs.get("warnings", []))
        row = {
            "dataset": "market_index",
            "symbol": symbol,
            "name": item.get("name"),
            "rows": int(len(df)),
            "start": None,
            "end": None,
            "status": "ok" if not df.empty else "empty",
            "warnings": warnings,
        }
        if not df.empty:
            row["start"] = str(pd.to_datetime(df["date"]).min().date())
            row["end"] = str(pd.to_datetime(df["date"]).max().date())
            _write_csv(out_dir / "market" / f"{symbol}.csv", df[["date", "open", "high", "low", "close", "volume"]])
        manifest.append(row)
        logger.info("Market index %s: %s rows", symbol, len(df))
        time.sleep(delay)
    return manifest


def _fetch_icb_index_histories(
    client,
    start: str,
    end: str,
    out_dir: Path,
    delay: float,
) -> List[Dict[str, Any]]:
    latest = client.get_icb_latest_index()
    latest_path = out_dir / "icb_latest_index_snapshot.json"
    _write_json(latest_path, latest)

    manifest: List[Dict[str, Any]] = []
    total = len(latest)
    for idx, item in enumerate(latest, start=1):
        industry_code = str(item.get("industryCode") or "")
        values = item.get("indexValues") or {}
        industry_name = str(values.get("ICBName") or industry_code)
        df = client.get_icb_historical_index(industry_code, start, end)
        warnings = list(df.attrs.get("warnings", []))
        row = {
            "dataset": "icb_index",
            "industry_code": industry_code,
            "industry_name": industry_name,
            "rows": int(len(df)),
            "start": None,
            "end": None,
            "status": "ok" if not df.empty else "empty",
            "warnings": warnings,
        }
        if not df.empty:
            row["start"] = str(pd.to_datetime(df["date"]).min().date())
            row["end"] = str(pd.to_datetime(df["date"]).max().date())
            _write_csv(
                out_dir / "icb" / f"ICB_{industry_code}_{_slugify(industry_name)}.csv",
                df[["date", "open", "high", "low", "close", "volume", "value"]],
            )
        manifest.append(row)
        if idx == 1 or idx % 25 == 0 or idx == total:
            logger.info("ICB history progress: %s/%s", idx, total)
        time.sleep(delay)
    return manifest


def _normalize_financial_rows(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    df = pd.json_normalize(rows, sep="_")
    if "symbol" in df.columns:
        df["symbol"] = df["symbol"].astype(str).str.upper().str.strip()
    return df


def _filter_quarterly(df: pd.DataFrame, start_year: int, end_year: int, end_quarter: int) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    out = out[out["quarter"].astype(int).between(1, 4)]
    out = out[out["year"].astype(int).between(start_year, end_year)]
    out = out[
        ((out["year"].astype(int) < end_year))
        | (
            (out["year"].astype(int) == end_year)
            & (out["quarter"].astype(int) <= end_quarter)
        )
    ]
    return out.sort_values(["symbol", "year", "quarter"]).reset_index(drop=True)


def _filter_annual(df: pd.DataFrame, start_year: int, end_year: int) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    out = out[out["quarter"].astype(int) == 0]
    out = out[out["year"].astype(int).between(start_year, end_year)]
    return out.sort_values(["symbol", "year"]).reset_index(drop=True)


def _fetch_financial_coverage(
    client,
    start_year: int,
    end_year: int,
    end_quarter: int,
    out_dir: Path,
) -> Dict[str, Any]:
    quarterly_count = (end_year - start_year + 1) * 4 + 4
    annual_count = (end_year - start_year + 1) + 2

    quarterly_rows = client.get_all_financial_data("Q", quarterly_count)
    annual_rows = client.get_all_financial_data("Y", annual_count)

    quarterly_df = _filter_quarterly(
        _normalize_financial_rows(quarterly_rows),
        start_year=start_year,
        end_year=end_year,
        end_quarter=end_quarter,
    )
    annual_df = _filter_annual(
        _normalize_financial_rows(annual_rows),
        start_year=start_year,
        end_year=end_year,
    )

    quarterly_path = (
        out_dir
        / f"all_financial_data_quarterly_{start_year}Q1_{end_year}Q{end_quarter}.parquet"
    )
    annual_path = out_dir / f"all_financial_data_annual_{start_year}_{end_year}.parquet"
    symbols_path = out_dir / "financial_symbol_coverage.csv"

    _write_parquet(quarterly_path, quarterly_df)
    _write_parquet(annual_path, annual_df)

    covered_symbols = sorted(
        set(quarterly_df.get("symbol", pd.Series(dtype=str)).dropna().tolist())
        | set(annual_df.get("symbol", pd.Series(dtype=str)).dropna().tolist())
    )
    pd.DataFrame({"symbol": covered_symbols}).to_csv(symbols_path, index=False)

    return {
        "quarterly_file": str(quarterly_path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "annual_file": str(annual_path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "symbol_file": str(symbols_path.relative_to(REPO_ROOT)),
        "quarterly_rows": int(len(quarterly_df)),
        "annual_rows": int(len(annual_df)),
        "symbols": int(len(covered_symbols)),
        "quarterly_period": f"{start_year}Q1..{end_year}Q{end_quarter}",
        "annual_period": f"{start_year}..{end_year}",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch full FireAnt index OHLCV coverage and 10-year financial coverage."
    )
    parser.add_argument("--index-start", default="2012-01-01", help="Index OHLCV start date.")
    parser.add_argument("--index-end", default=pd.Timestamp.today().strftime("%Y-%m-%d"), help="Index OHLCV end date.")
    parser.add_argument("--fa-start-year", type=int, default=2016, help="Financial data start year.")
    parser.add_argument("--fa-end-year", type=int, default=2025, help="Financial data end year.")
    parser.add_argument("--fa-end-quarter", type=int, default=4, help="Financial data ending quarter in the end year.")
    parser.add_argument(
        "--out-dir",
        default=str(REPO_ROOT / "data" / "fireant_exports"),
        help="Output directory for fetched datasets.",
    )
    parser.add_argument("--request-delay", type=float, default=0.05, help="Sleep between index requests.")
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="HTTP timeout in seconds for FireAnt requests (all-financial-data often needs >=300).",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    out_dir = Path(args.out_dir)
    index_dir = out_dir / "index_ohlcv"
    fa_dir = out_dir / "financials"

    client = get_client(timeout=args.timeout)

    logger.info("Resolving market index coverage...")
    market_indices = _collect_market_indices(client)
    market_manifest = _fetch_market_index_histories(
        client=client,
        indices=market_indices,
        start=args.index_start,
        end=args.index_end,
        out_dir=index_dir,
        delay=args.request_delay,
    )

    logger.info("Fetching ICB industry index histories...")
    icb_manifest = _fetch_icb_index_histories(
        client=client,
        start=args.index_start,
        end=args.index_end,
        out_dir=index_dir,
        delay=args.request_delay,
    )

    logger.info("Fetching all-company financial coverage...")
    fa_summary = _fetch_financial_coverage(
        client=client,
        start_year=args.fa_start_year,
        end_year=args.fa_end_year,
        end_quarter=args.fa_end_quarter,
        out_dir=fa_dir,
    )

    market_ok = sum(1 for row in market_manifest if row["status"] == "ok")
    icb_ok = sum(1 for row in icb_manifest if row["status"] == "ok")
    summary = {
        "index_period": {"start": args.index_start, "end": args.index_end},
        "financial_period": {
            "start_year": args.fa_start_year,
            "end_year": args.fa_end_year,
            "end_quarter": args.fa_end_quarter,
        },
        "market_index_manifest_file": str(
            (index_dir / "market_index_manifest.json").relative_to(REPO_ROOT)
        ),
        "icb_index_manifest_file": str(
            (index_dir / "icb_index_manifest.json").relative_to(REPO_ROOT)
        ),
        "market_indices_total": len(market_manifest),
        "market_indices_ok": market_ok,
        "icb_indices_total": len(icb_manifest),
        "icb_indices_ok": icb_ok,
        "financials": fa_summary,
    }

    _write_json(index_dir / "market_index_manifest.json", market_manifest)
    _write_json(index_dir / "icb_index_manifest.json", icb_manifest)
    _write_json(out_dir / "summary.json", summary)

    logger.info("Done. Summary written to %s", out_dir / "summary.json")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
