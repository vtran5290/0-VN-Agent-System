from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.data.fireant_client import RESTV2_BASE, FireAntClient  # noqa: E402

SSOT_DIR = REPO / "data" / "fireant_ssot"
STOCKS_DIR = REPO / "data" / "stocks"

# Legacy candidates — LFS pointers on this machine; kept only for audit / forbidden splice path.
TA_PANEL_CANDIDATES = [
    REPO / "data" / "research" / "ema_cloud" / "ohlcv_panel_full.parquet",
    REPO / "data" / "research" / "ema_cloud" / "ohlcv_panel_2018_2022.parquet",
    REPO / "data" / "research" / "ema_cloud" / "ohlcv_panel_cache.parquet",
]

PANEL_COLS = [
    "symbol",
    "date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "value",
    "close_raw",
    "source",
    "adjust_basis",
    "unit_vnd",
    "ca_suspect",
]


def _sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_lfs_pointer(path: Path) -> bool:
    if not path.exists() or path.stat().st_size > 512:
        return False
    try:
        head = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    return head.startswith("version https://git-lfs.github.com/spec/v1")


def audit_legacy_sources() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in TA_PANEL_CANDIDATES:
        rows.append(
            {
                "path": str(path.relative_to(REPO)).replace("\\", "/"),
                "exists": path.exists(),
                "size_bytes": path.stat().st_size if path.exists() else 0,
                "lfs_pointer": _is_lfs_pointer(path),
                "readable_parquet": False,
                "note": "forbidden as SSOT input under RE-FETCH_PRIMARY",
            }
        )
        if path.exists() and not _is_lfs_pointer(path):
            try:
                df = pd.read_parquet(path, columns=["symbol", "date", "close", "volume"])
                rows[-1]["readable_parquet"] = True
                rows[-1]["rows"] = int(len(df))
                rows[-1]["symbols"] = int(df["symbol"].nunique()) if "symbol" in df.columns else None
            except Exception as exc:
                rows[-1]["read_error"] = str(exc)

    stocks = list(STOCKS_DIR.glob("*.csv")) if STOCKS_DIR.exists() else []
    rows.append(
        {
            "path": "data/stocks/*.csv",
            "exists": bool(stocks),
            "file_count": len(stocks),
            "note": "universe list only; not concatenated into panel under RE-FETCH_PRIMARY",
        }
    )
    return rows


def universe_symbols() -> list[str]:
    if not STOCKS_DIR.exists():
        return []
    return sorted({fp.stem.upper() for fp in STOCKS_DIR.glob("*.csv")})


def _fetch_historical_raw(
    client: FireAntClient,
    symbol: str,
    start: str,
    end: str,
    page_limit: int = 5000,
) -> list[dict[str, Any]]:
    url = f"{RESTV2_BASE}/symbols/{symbol}/historical-quotes"
    out: list[dict[str, Any]] = []
    offset = 0
    while True:
        batch = client._get(
            url,
            {"startDate": start, "endDate": end, "offset": offset, "limit": page_limit},
        )
        if not batch:
            break
        if not isinstance(batch, list):
            raise TypeError(f"Unexpected payload type for {symbol}: {type(batch)}")
        out.extend(batch)
        if len(batch) < page_limit:
            break
        offset += len(batch)
        if offset > 200_000:
            break
    return out


def _rows_to_frame(symbol: str, raw: list[dict[str, Any]]) -> pd.DataFrame:
    if not raw:
        return pd.DataFrame(columns=PANEL_COLS)

    records: list[dict[str, Any]] = []
    for item in raw:
        date_val = item.get("date") or item.get("Date") or item.get("tradingDate")
        if not date_val:
            continue

        def _f(*keys: str, default: float | None = None) -> float | None:
            for k in keys:
                v = item.get(k)
                if v is not None:
                    try:
                        return float(v)
                    except (TypeError, ValueError):
                        continue
            return default

        unit = _f("unit", default=1000.0) or 1000.0
        adj = _f("adjRatio", default=1.0) or 1.0
        o = _f("priceOpen", "open")
        h = _f("priceHigh", "high")
        l_ = _f("priceLow", "low")
        c = _f("priceClose", "close")
        if c is None:
            continue
        vol = _f("dealVolume", "volume", default=0.0) or 0.0
        val = _f("totalValue")
        if val is None and c is not None:
            val = float(c) * unit * float(vol)

        records.append(
            {
                "symbol": symbol,
                "date": str(date_val)[:10],
                "open_raw": o if o is not None else c,
                "high_raw": h if h is not None else c,
                "low_raw": l_ if l_ is not None else c,
                "close_raw": c,
                "volume": vol,
                "value": val,
                "unit_vnd": unit,
                "adj_ratio": adj,
                "source": "fireant_restv2_historical_quotes",
                "adjust_basis": "fireant_adjRatio_asof_latest",
            }
        )

    df = pd.DataFrame.from_records(records)
    if df.empty:
        return pd.DataFrame(columns=PANEL_COLS)

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "close_raw"]).sort_values("date")
    df = df.drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)

    adj_last = float(df["adj_ratio"].iloc[-1]) if len(df) else 1.0
    if adj_last == 0:
        adj_last = 1.0
    scale = adj_last / df["adj_ratio"].replace(0, pd.NA)
    scale = scale.fillna(1.0)

    df["open"] = pd.to_numeric(df["open_raw"], errors="coerce") * scale
    df["high"] = pd.to_numeric(df["high_raw"], errors="coerce") * scale
    df["low"] = pd.to_numeric(df["low_raw"], errors="coerce") * scale
    df["close"] = pd.to_numeric(df["close_raw"], errors="coerce") * scale

    # ca_suspect: residual raw move beyond outer UPCOM band after adj_ratio change accounting
    raw_pc = df["close_raw"].pct_change()
    adj_changed = df["adj_ratio"].ne(df["adj_ratio"].shift(1)) & df["adj_ratio"].shift(1).notna()
    df["ca_suspect"] = (raw_pc.abs() > 0.155) & (~adj_changed.fillna(False))

    out = df[
        [
            "symbol",
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "value",
            "close_raw",
            "source",
            "adjust_basis",
            "unit_vnd",
            "ca_suspect",
            "adj_ratio",
        ]
    ].copy()
    return out


def fetch_panel(
    symbols: list[str],
    start: str,
    end: str,
    delay: float,
    limit_symbols: int | None = None,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    client = FireAntClient()
    if not client._token:
        raise RuntimeError("FIREANT_TOKEN not loaded — cannot RE-FETCH_PRIMARY")

    use = symbols[: limit_symbols] if limit_symbols else symbols
    frames: list[pd.DataFrame] = []
    fetch_log: list[dict[str, Any]] = []

    for i, sym in enumerate(use, start=1):
        status = "ok"
        n = 0
        err = None
        try:
            raw = _fetch_historical_raw(client, sym, start, end)
            frame = _rows_to_frame(sym, raw)
            n = int(len(frame))
            if frame.empty:
                status = "empty"
            else:
                frames.append(frame)
        except Exception as exc:
            status = "error"
            err = str(exc)

        fetch_log.append({"symbol": sym, "status": status, "rows": n, "error": err})
        if i == 1 or i % 50 == 0 or i == len(use):
            print(f"[fetch] {i}/{len(use)} {sym} status={status} rows={n}", flush=True)
        if delay > 0:
            time.sleep(delay)

    if not frames:
        return pd.DataFrame(columns=PANEL_COLS), fetch_log

    panel = pd.concat(frames, ignore_index=True)
    panel = panel.sort_values(["symbol", "date"]).drop_duplicates(
        subset=["symbol", "date"], keep="last"
    )
    return panel.reset_index(drop=True), fetch_log


def build_corporate_actions(
    symbols: list[str],
    panel: pd.DataFrame,
    delay: float,
    limit_symbols: int | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Yearly dividends endpoint (no ex-date) + ca_suspect rows from panel."""
    client = FireAntClient()
    use = symbols[: limit_symbols] if limit_symbols else symbols
    rows: list[dict[str, Any]] = []
    endpoint_ok = 0
    endpoint_fail = 0

    for i, sym in enumerate(use, start=1):
        try:
            r = client._session.get(
                f"{RESTV2_BASE}/symbols/{sym}/dividends",
                timeout=client._timeout,
            )
            if r.status_code == 404:
                endpoint_fail += 1
            elif r.ok:
                endpoint_ok += 1
                payload = r.json()
                if isinstance(payload, list):
                    for item in payload:
                        year = item.get("year")
                        rows.append(
                            {
                                "symbol": sym,
                                "date": pd.Timestamp(f"{int(year)}-12-31") if year else pd.NaT,
                                "event_type": "annual_dividend_summary",
                                "cash_dividend": item.get("cashDividend"),
                                "stock_dividend_pct": item.get("stockDividend"),
                                "source": "fireant_restv2_dividends",
                                "confidence": "low_no_exdate",
                                "notes": "year-level only; ex-date UNKNOWN",
                            }
                        )
            else:
                endpoint_fail += 1
        except Exception:
            endpoint_fail += 1

        if delay > 0:
            time.sleep(min(delay, 0.05))
        if i == 1 or i % 100 == 0 or i == len(use):
            print(f"[ca] dividends {i}/{len(use)}", flush=True)

    if not panel.empty and "ca_suspect" in panel.columns:
        sus = panel.loc[panel["ca_suspect"]].copy()
        for rec in sus.itertuples(index=False):
            rows.append(
                {
                    "symbol": rec.symbol,
                    "date": rec.date,
                    "event_type": "ca_suspect_gap",
                    "cash_dividend": None,
                    "stock_dividend_pct": None,
                    "source": "panel_residual_gt_limit",
                    "confidence": "suspect",
                    "notes": "raw close move >15.5% without adjRatio change",
                }
            )

    ca = pd.DataFrame(rows)
    meta = {
        "dividends_endpoint": "GET /symbols/{sym}/dividends",
        "dividends_ok_symbols": endpoint_ok,
        "dividends_fail_symbols": endpoint_fail,
        "dated_ca_endpoint": "unavailable_404_corporate-actions_events_rights",
        "ca_suspect_rows": int(panel["ca_suspect"].sum()) if not panel.empty and "ca_suspect" in panel.columns else 0,
    }
    return ca, meta


def backup_ssot(tag: str | None = None) -> Path:
    stamp = tag or date.today().isoformat()
    dest = SSOT_DIR / f"_backup_{stamp}"
    dest.mkdir(parents=True, exist_ok=True)
    for name in [
        "ta_ohlcv_panel.parquet",
        "ta_ohlcv_panel.parquet.bak",
        "ta_vnindex.parquet",
        "manifest.json",
        "corporate_actions.parquet",
        "ca_suspect_report.json",
    ]:
        src = SSOT_DIR / name
        if src.exists():
            shutil.copy2(src, dest / name)
    return dest


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


def write_manifest(
    ta_panel: pd.DataFrame,
    ta_path: Path,
    vnindex_manifest: dict[str, Any] | None,
    fetch_log: list[dict[str, Any]],
    ca_meta: dict[str, Any],
    backup_dir: Path,
    audit: list[dict[str, Any]],
    start: str,
    end: str,
) -> dict[str, Any]:
    source_hashes = {
        "build_script": {
            "path": "scripts/build_fireant_ssot.py",
            "sha256": _sha256_file(REPO / "scripts" / "build_fireant_ssot.py"),
        },
        "spec": {
            "path": "docs/DATA_SSOT_REBUILD_SPEC.md",
            "sha256": _sha256_file(REPO / "docs" / "DATA_SSOT_REBUILD_SPEC.md"),
        },
        "panel": {
            "path": str(ta_path.relative_to(REPO)).replace("\\", "/"),
            "sha256": _sha256_file(ta_path),
        },
    }
    for path in TA_PANEL_CANDIDATES:
        rel = str(path.relative_to(REPO)).replace("\\", "/")
        source_hashes[rel] = {
            "path": rel,
            "sha256": _sha256_file(path),
            "lfs_pointer": _is_lfs_pointer(path),
        }

    q_manifest = None
    a_manifest = None
    try:
        q_latest = _latest_file_by_mtime("all_financial_data_quarterly_*.parquet")
        a_latest = _latest_file_by_mtime("all_financial_data_annual_*.parquet")
        if not _is_lfs_pointer(q_latest):
            q_df = pd.read_parquet(q_latest)
            q_df.to_parquet(SSOT_DIR / "fa_quarterly.parquet", index=False)
            q_manifest = {
                "path": "data/fireant_ssot/fa_quarterly.parquet",
                "rows": int(len(q_df)),
                "symbols": int(q_df["symbol"].astype(str).nunique()),
                **_period_range(q_df[["year", "quarter"]].copy()),
                "source_file": str(q_latest.relative_to(REPO)).replace("\\", "/"),
                "sha256": _sha256_file(SSOT_DIR / "fa_quarterly.parquet"),
            }
        else:
            q_manifest = {
                "path": "data/fireant_ssot/fa_quarterly.parquet",
                "skipped": "source is git-LFS pointer",
                "source_file": str(q_latest.relative_to(REPO)).replace("\\", "/"),
            }
        if not _is_lfs_pointer(a_latest):
            a_df = pd.read_parquet(a_latest)
            a_df.to_parquet(SSOT_DIR / "fa_annual.parquet", index=False)
            a_manifest = {
                "path": "data/fireant_ssot/fa_annual.parquet",
                "rows": int(len(a_df)),
                "symbols": int(a_df["symbol"].astype(str).nunique()),
                "source_file": str(a_latest.relative_to(REPO)).replace("\\", "/"),
                "sha256": _sha256_file(SSOT_DIR / "fa_annual.parquet"),
            }
        else:
            a_manifest = {
                "path": "data/fireant_ssot/fa_annual.parquet",
                "skipped": "source is git-LFS pointer",
                "source_file": str(a_latest.relative_to(REPO)).replace("\\", "/"),
            }
    except Exception as exc:
        q_manifest = {"error": str(exc)}
        a_manifest = {"error": str(exc)}

    cov_src = REPO / "data" / "fireant_exports" / "financials" / "financial_symbol_coverage.csv"
    if cov_src.exists():
        (SSOT_DIR / "fa_symbol_coverage.csv").write_bytes(cov_src.read_bytes())

    fail_n = sum(1 for r in fetch_log if r["status"] != "ok")
    manifest: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_policy": (
            "RE-FETCH_PRIMARY: data/fireant_ssot/ta_ohlcv_panel.parquet is a single continuous "
            "FireAnt historical-quotes panel with per-row provenance. Do not splice ema_cloud + stocks CSV."
        ),
        "rebuild_spec": "docs/DATA_SSOT_REBUILD_SPEC.md",
        "backup_dir": str(backup_dir.relative_to(REPO)).replace("\\", "/"),
        "fetch_window": {"start": start, "end": end},
        "legacy_source_audit": audit,
        "fetch_summary": {
            "symbols_requested": len(fetch_log),
            "symbols_ok": sum(1 for r in fetch_log if r["status"] == "ok"),
            "symbols_non_ok": fail_n,
        },
        "source_hashes": source_hashes,
        "ta_ohlcv_panel": {
            "path": str(ta_path.relative_to(REPO)).replace("\\", "/"),
            "rows": int(len(ta_panel)),
            "symbols": int(ta_panel["symbol"].nunique()) if len(ta_panel) else 0,
            "min_date": str(ta_panel["date"].min().date()) if len(ta_panel) else None,
            "max_date": str(ta_panel["date"].max().date()) if len(ta_panel) else None,
            "sha256": _sha256_file(ta_path),
            "price_unit": "FireAnt quote (typically thousand VND); see unit_vnd column",
            "value_unit": "raw_VND_totalValue",
            "adjust_basis": "fireant_adjRatio_asof_latest",
        },
        "ta_vnindex": vnindex_manifest,
        "fa_quarterly": q_manifest,
        "fa_annual": a_manifest,
        "corporate_actions": ca_meta,
    }
    (SSOT_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (SSOT_DIR / "fetch_log.json").write_text(
        json.dumps(fetch_log, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Rebuild FireAnt OHLCV SSOT (RE-FETCH_PRIMARY)")
    p.add_argument("--start", default="2008-01-01")
    p.add_argument("--end", default=date.today().isoformat())
    p.add_argument("--delay", type=float, default=0.12)
    p.add_argument("--limit-symbols", type=int, default=None, help="Debug: only first N symbols")
    p.add_argument("--skip-backup", action="store_true")
    p.add_argument("--audit-only", action="store_true")
    p.add_argument("--skip-fa-refresh", action="store_true", help="Do not touch fa_*.parquet")
    args = p.parse_args(argv)

    audit = audit_legacy_sources()
    print(json.dumps({"legacy_source_audit": audit}, indent=2), flush=True)
    if args.audit_only:
        # --audit-only is strictly read-only: report to stdout, touch nothing.
        # Provenance guard (Council 2026-07-25): legacy_source_audit.json is a
        # FULL-BUILD artifact. Writing it (and mkdir-ing SSOT_DIR) before this
        # guard meant every diagnostic --audit-only run silently mutated the
        # canonical SSOT directory and reset the artifact's mtime, breaking the
        # G1.5 chain of custody. Do not move these writes back above this return.
        return 0

    SSOT_DIR.mkdir(parents=True, exist_ok=True)
    (SSOT_DIR / "legacy_source_audit.json").write_text(
        json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    if not args.skip_backup:
        backup_dir = backup_ssot()
        print(f"[backup] {backup_dir}", flush=True)
    else:
        backup_dir = SSOT_DIR / "_backup_skipped"

    symbols = universe_symbols()
    if not symbols:
        raise SystemExit("No symbols found under data/stocks/*.csv")

    panel, fetch_log = fetch_panel(
        symbols,
        start=args.start,
        end=args.end,
        delay=args.delay,
        limit_symbols=args.limit_symbols,
    )
    if panel.empty:
        raise SystemExit("RE-FETCH_PRIMARY produced empty panel")

    # Drop helper adj_ratio from published panel (kept during build for CA)
    publish_cols = [c for c in PANEL_COLS if c in panel.columns]
    ta_panel = panel[publish_cols].copy()
    ta_path = SSOT_DIR / "ta_ohlcv_panel.parquet"
    ta_panel.to_parquet(ta_path, index=False)
    print(
        f"[panel] rows={len(ta_panel)} symbols={ta_panel['symbol'].nunique()} "
        f"max_date={ta_panel['date'].max().date()}",
        flush=True,
    )

    ca_df, ca_meta = build_corporate_actions(
        symbols,
        panel=panel,
        delay=args.delay,
        limit_symbols=args.limit_symbols,
    )
    ca_path = SSOT_DIR / "corporate_actions.parquet"
    if not ca_df.empty:
        ca_df.to_parquet(ca_path, index=False)
    ca_meta["path"] = "data/fireant_ssot/corporate_actions.parquet"
    ca_meta["rows"] = int(len(ca_df))
    suspect_report = {
        "ca_suspect_count": int(ta_panel["ca_suspect"].sum()) if "ca_suspect" in ta_panel.columns else 0,
        "ca_suspect_by_date_top": (
            ta_panel.loc[ta_panel["ca_suspect"]]
            .groupby(ta_panel.loc[ta_panel["ca_suspect"], "date"].dt.strftime("%Y-%m-%d"))
            .size()
            .sort_values(ascending=False)
            .head(20)
            .to_dict()
            if "ca_suspect" in ta_panel.columns and ta_panel["ca_suspect"].any()
            else {}
        ),
        "note": "Dated CA endpoint unavailable; annual dividends are year-level only.",
    }
    (SSOT_DIR / "ca_suspect_report.json").write_text(
        json.dumps(suspect_report, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    ca_meta["suspect_report"] = "data/fireant_ssot/ca_suspect_report.json"

    vnindex_manifest = None
    vnindex_src = REPO / "data" / "fireant_exports" / "index_ohlcv" / "market" / "VNINDEX.csv"
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
            "sha256": _sha256_file(vnindex_path),
        }

    if args.skip_fa_refresh:
        # Still write TA-focused manifest without refreshing FA copies
        manifest = {
            "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source_policy": "RE-FETCH_PRIMARY TA panel only (FA refresh skipped)",
            "backup_dir": str(backup_dir.relative_to(REPO)).replace("\\", "/")
            if backup_dir.exists()
            else None,
            "legacy_source_audit": audit,
            "ta_ohlcv_panel": {
                "path": str(ta_path.relative_to(REPO)).replace("\\", "/"),
                "rows": int(len(ta_panel)),
                "symbols": int(ta_panel["symbol"].nunique()),
                "min_date": str(ta_panel["date"].min().date()),
                "max_date": str(ta_panel["date"].max().date()),
                "sha256": _sha256_file(ta_path),
            },
            "ta_vnindex": vnindex_manifest,
            "corporate_actions": ca_meta,
            "fetch_summary": {
                "symbols_requested": len(fetch_log),
                "symbols_ok": sum(1 for r in fetch_log if r["status"] == "ok"),
            },
        }
        (SSOT_DIR / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (SSOT_DIR / "fetch_log.json").write_text(
            json.dumps(fetch_log, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    else:
        manifest = write_manifest(
            ta_panel,
            ta_path,
            vnindex_manifest,
            fetch_log,
            ca_meta,
            backup_dir,
            audit,
            args.start,
            args.end,
        )

    print(json.dumps(manifest, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
