from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd


REPO = Path(__file__).resolve().parents[1]
SSOT_DIR = REPO / "data" / "fireant_ssot"

TA_PANEL_CANDIDATES = [
    REPO / "data" / "research" / "ema_cloud" / "ohlcv_panel_full.parquet",
    REPO / "data" / "research" / "ema_cloud" / "ohlcv_panel_2018_2022.parquet",
    REPO / "data" / "research" / "ema_cloud" / "ohlcv_panel_cache.parquet",
]


def _load_ta_parquets(paths: Iterable[Path]) -> list[pd.DataFrame]:
    frames: list[pd.DataFrame] = []
    for path in paths:
        if not path.exists():
            continue
        df = pd.read_parquet(path)
        needed = {"symbol", "date", "open", "high", "low", "close", "volume"}
        if not needed.issubset(df.columns):
            continue
        use_cols = ["symbol", "date", "open", "high", "low", "close", "volume"]
        if "value" in df.columns:
            use_cols.append("value")
        df = df[use_cols].copy()
        frames.append(df)
    return frames


def _load_stocks_csv_panel(stocks_dir: Path) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for fp in stocks_dir.glob("*.csv"):
        sym = fp.stem.upper()
        try:
            df = pd.read_csv(fp, usecols=["date", "open", "high", "low", "close", "volume"])
        except Exception:
            continue
        df["symbol"] = sym
        rows.append(df)

    if not rows:
        return pd.DataFrame(columns=["symbol", "date", "open", "high", "low", "close", "volume", "value"])

    out = pd.concat(rows, ignore_index=True)
    out["value"] = pd.to_numeric(out["close"], errors="coerce") * pd.to_numeric(out["volume"], errors="coerce")
    return out


def _standardize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["symbol"] = out["symbol"].astype(str).str.upper().str.strip()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    for col in ["open", "high", "low", "close", "volume", "value"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
        else:
            out[col] = pd.NA
    out = out.dropna(subset=["symbol", "date", "close"])
    out = out.sort_values(["symbol", "date"]).drop_duplicates(subset=["symbol", "date"], keep="last")
    return out.reset_index(drop=True)


def _latest_file_by_mtime(pattern: str) -> Path:
    files = list((REPO / "data" / "fireant_exports" / "financials").glob(pattern))
    if not files:
        raise FileNotFoundError(f"No files match pattern: {pattern}")
    return max(files, key=lambda p: p.stat().st_mtime)


def _period_range(df: pd.DataFrame) -> dict[str, str]:
    y_min, y_max = int(df["year"].min()), int(df["year"].max())
    q_min = int(df[df["year"] == y_min]["quarter"].min())
    q_max = int(df[df["year"] == y_max]["quarter"].max())
    return {"min_period": f"{y_min}Q{q_min}", "max_period": f"{y_max}Q{q_max}"}


def main() -> int:
    SSOT_DIR.mkdir(parents=True, exist_ok=True)

    ta_parts = _load_ta_parquets(TA_PANEL_CANDIDATES)
    ta_parts.append(_load_stocks_csv_panel(REPO / "data" / "stocks"))
    ta_panel = _standardize_ohlcv(pd.concat(ta_parts, ignore_index=True))
    ta_path = SSOT_DIR / "ta_ohlcv_panel.parquet"
    ta_panel.to_parquet(ta_path, index=False)

    vnindex_src = REPO / "data" / "fireant_exports" / "index_ohlcv" / "market" / "VNINDEX.csv"
    vnindex_manifest = None
    if vnindex_src.exists():
        vnindex = pd.read_csv(vnindex_src)
        vnindex["date"] = pd.to_datetime(vnindex["date"], errors="coerce")
        vnindex = vnindex.sort_values("date").drop_duplicates(subset=["date"], keep="last")
        vnindex_path = SSOT_DIR / "ta_vnindex.parquet"
        vnindex.to_parquet(vnindex_path, index=False)
        vnindex_manifest = {
            "path": str(vnindex_path.relative_to(REPO)).replace("\\", "/"),
            "rows": int(len(vnindex)),
            "min_date": str(vnindex["date"].min().date()),
            "max_date": str(vnindex["date"].max().date()),
            "source_file": str(vnindex_src.relative_to(REPO)).replace("\\", "/"),
        }

    q_latest = _latest_file_by_mtime("all_financial_data_quarterly_*.parquet")
    a_latest = _latest_file_by_mtime("all_financial_data_annual_*.parquet")

    q_df = pd.read_parquet(q_latest)
    a_df = pd.read_parquet(a_latest)
    q_df.to_parquet(SSOT_DIR / "fa_quarterly.parquet", index=False)
    a_df.to_parquet(SSOT_DIR / "fa_annual.parquet", index=False)

    cov_src = REPO / "data" / "fireant_exports" / "financials" / "financial_symbol_coverage.csv"
    if cov_src.exists():
        cov_dst = SSOT_DIR / "fa_symbol_coverage.csv"
        cov_dst.write_bytes(cov_src.read_bytes())

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_policy": "Use files under data/fireant_ssot as the single source for FireAnt TA/FA in this repo.",
        "ta_ohlcv_panel": {
            "path": str(ta_path.relative_to(REPO)).replace("\\", "/"),
            "rows": int(len(ta_panel)),
            "symbols": int(ta_panel["symbol"].nunique()),
            "min_date": str(ta_panel["date"].min().date()),
            "max_date": str(ta_panel["date"].max().date()),
        },
        "ta_vnindex": vnindex_manifest,
        "fa_quarterly": {
            "path": "data/fireant_ssot/fa_quarterly.parquet",
            "rows": int(len(q_df)),
            "symbols": int(q_df["symbol"].astype(str).nunique()),
            **_period_range(q_df[["year", "quarter"]].copy()),
            "source_file": str(q_latest.relative_to(REPO)).replace("\\", "/"),
        },
        "fa_annual": {
            "path": "data/fireant_ssot/fa_annual.parquet",
            "rows": int(len(a_df)),
            "symbols": int(a_df["symbol"].astype(str).nunique()),
            "source_file": str(a_latest.relative_to(REPO)).replace("\\", "/"),
        },
    }

    (SSOT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
