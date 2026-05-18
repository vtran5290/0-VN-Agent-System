"""Intraday A3/S3 preview scan — never routes live orders."""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import yaml

from pp_backtest.portfolio_optimization_final_steps import compute_phase36_scan_df, load_vnindex
from pp_backtest.portfolio_optimization_phase2 import build_gk_cache
from src.trading.config import REPO_ROOT
from src.trading.intraday.data_adapter import (
    detect_intraday_source_capability,
    fetch_intraday_quote,
    fetch_intraday_quotes,
)
from src.trading.intraday.panel_overlay import EOD_PANEL_DEFAULT, build_provisional_panel, load_eod_panel
from src.trading.intraday.report import write_intraday_report
from src.trading.intraday.session import (
    detect_session_phase,
    minutes_to_close,
    minutes_to_lunch_break,
    now_hcm,
)
from src.trading.intraday.vnindex_overlay import build_vnindex_intraday_overlay
from src.trading.intraday.volume_projection import mode_volume_confidence_cap

logger = logging.getLogger(__name__)

_CANDIDATE_ACTIONS = frozenset({
    "NEW_T1",
    "NEW_T1_MANUAL_REVIEW_BREADTH",
    "ADD_T2",
    "WAIT_PB",
    "TP1_PARTIAL",
    "TRAIL_EXIT",
    "MAX_HOLD_EXIT",
})

_EXIT_ACTIONS = frozenset({"TP1_PARTIAL", "TRAIL_EXIT", "MAX_HOLD_EXIT"})


def load_intraday_config(path: Optional[Path] = None) -> Dict[str, Any]:
    cfg_path = path or (REPO_ROOT / "configs" / "intraday_scan.yaml")
    if not cfg_path.exists():
        return {}
    return yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}


def resolve_symbol_list(
    symbols: Optional[List[str]],
    cfg: Dict[str, Any],
    eod_scan_path: Optional[Path] = None,
) -> List[str]:
    if symbols:
        return [s.strip().upper() for s in symbols if s.strip()]
    src = (cfg.get("default_symbols_source") or "watchlist").lower()
    if src == "holdings":
        hp = cfg.get("holdings_path") or "data/trading/holdings.txt"
        path = REPO_ROOT / str(hp) if not Path(str(hp)).is_absolute() else Path(str(hp))
        if path.exists():
            return [
                ln.strip().upper()
                for ln in path.read_text(encoding="utf-8").splitlines()
                if ln.strip() and not ln.strip().startswith("#")
            ]
    if src == "eod_scan":
        p = eod_scan_path or REPO_ROOT / str(cfg.get("eod_scan_path", ""))
        if p.exists():
            df = pd.read_csv(p)
            return sorted(df["symbol"].astype(str).str.upper().unique().tolist())
    wl = REPO_ROOT / str(cfg.get("watchlist_path", "config/watchlist.txt"))
    if wl.exists():
        return [ln.strip().upper() for ln in wl.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")]
    return list(cfg.get("probe_symbols") or ["HPG", "VPB", "FPT"])


def _quoted_equity_symbols(quotes_df: pd.DataFrame) -> set[str]:
    if quotes_df is None or quotes_df.empty:
        return set()
    eq = quotes_df[quotes_df["symbol"].astype(str).str.upper() != "VNINDEX"]
    if eq.empty:
        return set()
    if "data_quality" in eq.columns:
        eq = eq[eq["data_quality"].isin(["OK", "PARTIAL_VOLUME_ESTIMATE", "LOW_CONFIDENCE"])]
    if "is_stale" in eq.columns:
        eq = eq[eq["is_stale"] != True]
    return set(eq["symbol"].astype(str).str.upper())


def _resolve_breadth_source(quoted: set[str], scan_symbols: set[str]) -> str:
    if not quoted:
        return "eod_fallback"
    if scan_symbols and scan_symbols <= quoted:
        return "live_panel_full_intraday"
    return "mixed_intraday_eod_panel"


def _resolve_holdings_path(cfg: Dict[str, Any]) -> Path:
    hp = cfg.get("holdings_path") or "data/trading/holdings.txt"
    path = Path(str(hp))
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path


def _holdings_status(cfg: Dict[str, Any]) -> Dict[str, Any]:
    path = _resolve_holdings_path(cfg)
    exists = path.exists()
    symbols: List[str] = []
    if exists:
        symbols = [
            ln.strip().upper()
            for ln in path.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]
    return {
        "holdings_path": str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path),
        "holdings_file_exists": exists,
        "holdings_symbol_count": len(symbols),
        "holdings_symbols": symbols,
    }


def _attach_quote_coverage_meta(
    meta: Dict[str, Any],
    *,
    quoted_syms: set[str],
    scan_symbols: set[str],
    symbols_requested: List[str],
) -> None:
    n_requested = len(symbols_requested)
    n_quoted = len(quoted_syms)
    n_scan = len(scan_symbols)
    missing_in_scan = len(scan_symbols - quoted_syms) if scan_symbols else 0
    meta["quoted_symbols_count"] = n_quoted
    meta["scan_symbols_count"] = n_scan
    meta["missing_quote_count"] = missing_in_scan
    meta["intraday_quote_coverage_pct"] = (n_quoted / n_requested) if n_requested else 0.0
    meta["quoted_equity_symbols"] = sorted(quoted_syms)


def _apply_intraday_policy(
    scan_df: pd.DataFrame,
    quotes_df: pd.DataFrame,
    *,
    asof_timestamp: datetime,
    cfg: Dict[str, Any],
    mode: str,
    capability: Dict[str, Any],
    quoted_equity_symbols: Optional[set[str]] = None,
) -> pd.DataFrame:
    if scan_df.empty:
        return scan_df

    out = scan_df.copy()
    out["would_be_final_action"] = out["final_action"]
    out["intraday_timestamp"] = asof_timestamp.isoformat()
    out["intraday_source"] = capability.get("recommended_method") or "FireAnt"
    out["is_intraday_preview"] = True
    out["provisional_bar"] = True
    out["auto_order_allowed"] = False
    out["manual_review_required"] = False
    out["intraday_candidate"] = False
    out["eod_panel_asof_date"] = out.get("as_of_date", pd.NaT)

    phase = detect_session_phase(asof_timestamp)
    out["session_phase"] = phase
    out["minutes_to_close"] = minutes_to_close(asof_timestamp)
    out["minutes_to_lunch_break"] = minutes_to_lunch_break(asof_timestamp)

    if quoted_equity_symbols is None:
        quoted_equity_symbols = _quoted_equity_symbols(quotes_df)

    stale_syms = set()
    if not quotes_df.empty:
        stale_syms = set(
            quotes_df.loc[quotes_df["is_stale"] == True, "symbol"].astype(str).str.upper()
        )

    cap_conf = mode_volume_confidence_cap(mode)
    statuses = []
    qualities = []
    for _, row in out.iterrows():
        sym = str(row["symbol"]).upper()
        wfa = str(row["would_be_final_action"])

        if not capability.get("available"):
            qualities.append("SOURCE_UNAVAILABLE")
            statuses.append("SOURCE_UNAVAILABLE")
            out.at[row.name, "final_action"] = "INTRADAY_PREVIEW"
            out.at[row.name, "manual_review_required"] = False
            out.at[row.name, "intraday_candidate"] = False
            continue

        if sym not in quoted_equity_symbols:
            qualities.append("MISSING_INTRADAY_QUOTE")
            statuses.append("STALE_DATA_NO_ACTION")
            out.at[row.name, "final_action"] = "INTRADAY_PREVIEW"
            out.at[row.name, "manual_review_required"] = False
            out.at[row.name, "intraday_candidate"] = False
            continue

        dq = "OK"
        if sym in stale_syms:
            dq = "STALE"
        elif not capability.get("available"):
            dq = "SOURCE_UNAVAILABLE"
        elif phase in ("CLOSED", "LUNCH_BREAK"):
            dq = "OUT_OF_SESSION"
        qualities.append(dq)

        if dq in ("SOURCE_UNAVAILABLE", "STALE") or not capability.get("available"):
            status = "STALE_DATA_NO_ACTION" if dq == "STALE" else (
                "SOURCE_UNAVAILABLE" if dq == "SOURCE_UNAVAILABLE" else "OUT_OF_SESSION_NO_ACTION"
            )
            out.at[row.name, "final_action"] = "INTRADAY_PREVIEW"
            out.at[row.name, "manual_review_required"] = False
            out.at[row.name, "intraday_candidate"] = False
        elif phase in ("CLOSED", "LUNCH_BREAK"):
            status = "OUT_OF_SESSION_NO_ACTION"
            out.at[row.name, "final_action"] = "INTRADAY_PREVIEW"
        elif wfa in _CANDIDATE_ACTIONS:
            status = "MANUAL_REVIEW_REQUIRED"
            out.at[row.name, "intraday_candidate"] = True
            out.at[row.name, "manual_review_required"] = True
            out.at[row.name, "final_action"] = "INTRADAY_PREVIEW"
        else:
            status = "PREVIEW_ONLY"
            out.at[row.name, "final_action"] = "INTRADAY_PREVIEW"

        if wfa in _EXIT_ACTIONS and status == "MANUAL_REVIEW_REQUIRED":
            out.at[row.name, "intraday_candidate"] = True
        statuses.append(status)

    out["intraday_data_quality"] = qualities
    out["intraday_action_status"] = statuses
    out["intraday_price_stale"] = out["symbol"].astype(str).isin(stale_syms)
    out["volume_projection_confidence"] = out.get("volume_projection_confidence", cap_conf)
    if mode == "pre-lunch":
        out.loc[out["volume_projection_confidence"] == "high", "volume_projection_confidence"] = "medium"
    return out


def run_intraday_scan(
    asof_timestamp: Optional[datetime] = None,
    symbols: Optional[List[str]] = None,
    mode: str = "ad-hoc",
    volume_projection: Optional[str] = None,
    *,
    config_path: Optional[Path] = None,
    write_outputs: bool = True,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Run intraday preview scan. Never writes EOD panel; optional CSV/MD to intraday dir only.
    """
    cfg = load_intraday_config(config_path)
    asof_timestamp = asof_timestamp or now_hcm()
    mode_cfg = (cfg.get("modes") or {}).get(mode, {})
    vol_method = volume_projection or mode_cfg.get("volume_projection") or cfg.get("default_volume_projection", "session_time")
    out_dir = REPO_ROOT / str(cfg.get("output_dir", "data/research/intraday"))
    panel_path = REPO_ROOT / str(cfg.get("eod_panel_path", str(EOD_PANEL_DEFAULT)))
    stale_sec = float(cfg.get("stale_price_threshold_seconds", 300))
    min_elapsed = float(cfg.get("min_elapsed_fraction_for_volume_projection", 0.15))

    explicit_symbols = bool(symbols)
    sym_list = resolve_symbol_list(symbols, cfg)
    probe_path = out_dir / "source_probe" / f"fireant_probe_{asof_timestamp.strftime('%Y%m%d_%H%M')}.json"
    capability = detect_intraday_source_capability(
        cfg.get("probe_symbols") or sym_list[:5],
        save_probe_path=probe_path,
    )

    meta: Dict[str, Any] = {
        "asof_timestamp": asof_timestamp.isoformat(),
        "mode": mode,
        "capability": capability,
        "symbols_requested": sym_list,
        "explicit_symbols": explicit_symbols,
        "status": "OK",
    }
    meta.update(_holdings_status(cfg))

    if not capability.get("available"):
        meta["status"] = "SOURCE_UNAVAILABLE"
        _attach_quote_coverage_meta(meta, quoted_syms=set(), scan_symbols=set(), symbols_requested=sym_list)
        meta["breadth_source"] = "eod_fallback"
        empty = pd.DataFrame()
        if write_outputs:
            _write_outputs(empty, meta, cfg, mode, asof_timestamp, out_dir, quotes_df=pd.DataFrame())
        return empty, meta

    quotes_df = fetch_intraday_quotes(sym_list, stale_threshold_sec=stale_sec)
    vn_quote = fetch_intraday_quote("VNINDEX", stale_threshold_sec=stale_sec)
    if vn_quote.get("data_quality") not in ("SOURCE_UNAVAILABLE", "MISSING_PRICE"):
        quotes_df = pd.concat([quotes_df, pd.DataFrame([vn_quote])], ignore_index=True)
    ok_quotes = quotes_df[quotes_df["data_quality"].isin(["OK", "PARTIAL_VOLUME_ESTIMATE", "LOW_CONFIDENCE"])]
    equity_quotes = ok_quotes[ok_quotes["symbol"].astype(str).str.upper() != "VNINDEX"]
    vn_ok = vn_quote.get("data_quality") not in ("SOURCE_UNAVAILABLE", "MISSING_PRICE")
    quoted_syms = _quoted_equity_symbols(quotes_df)

    if equity_quotes.empty and not vn_ok:
        meta["status"] = "NO_VALID_QUOTES"
        _attach_quote_coverage_meta(meta, quoted_syms=set(), scan_symbols=set(), symbols_requested=sym_list)
        meta["breadth_source"] = "eod_fallback"
        empty = pd.DataFrame()
        if write_outputs:
            _write_outputs(empty, meta, cfg, mode, asof_timestamp, out_dir, quotes_df=quotes_df)
        return empty, meta

    eod_panel = load_eod_panel(panel_path)
    eod_max = pd.Timestamp(eod_panel["date"].max()).normalize()
    target_date = pd.Timestamp(asof_timestamp.date()).normalize()
    if equity_quotes.empty:
        prov_panel = eod_panel
        meta["status"] = "VNINDEX_ONLY_MACRO"
    else:
        prov_panel = build_provisional_panel(
            eod_panel,
            equity_quotes,
            target_date=target_date,
            run_timestamp=asof_timestamp,
            volume_projection_method=vol_method,
            exchange_calendar=cfg,
            min_elapsed_fraction=min_elapsed,
        )

    vnx_eod = load_vnindex()
    vnx, vn_meta = build_vnindex_intraday_overlay(
        vnx_eod,
        target_date=target_date,
        run_timestamp=asof_timestamp,
        stale_threshold_sec=stale_sec,
        quote=vn_quote,
    )
    gk_cache = build_gk_cache(prov_panel)
    scan_df, scan_meta = compute_phase36_scan_df(
        prov_panel, vnx, gk_cache, sector_map=None, intraday_macro=True,
    )
    scan_meta["vnindex"] = vn_meta
    scan_meta["eod_panel_asof_date"] = eod_max.date()
    scan_meta["session_phase"] = detect_session_phase(asof_timestamp)
    if explicit_symbols:
        sym_set = {s.strip().upper() for s in symbols if s and str(s).strip()}
        scan_df = scan_df[scan_df["symbol"].astype(str).str.upper().isin(sym_set)].copy()

    scan_symbols = set(scan_df["symbol"].astype(str).str.upper()) if not scan_df.empty else set()

    scan_df = _apply_intraday_policy(
        scan_df,
        quotes_df,
        asof_timestamp=asof_timestamp,
        cfg=cfg,
        mode=mode,
        capability=capability,
        quoted_equity_symbols=quoted_syms,
    )
    if not quotes_df.empty and "timestamp" in quotes_df.columns:
        scan_df["price_source_time"] = (
            quotes_df.set_index("symbol")["timestamp"].reindex(scan_df["symbol"]).values
        )
    scan_df["intraday_volume_stale"] = scan_df["intraday_price_stale"]
    scan_df["volume_projection_method"] = vol_method
    meta.update(scan_meta)
    _attach_quote_coverage_meta(
        meta, quoted_syms=quoted_syms, scan_symbols=scan_symbols, symbols_requested=sym_list,
    )
    meta["breadth_source"] = _resolve_breadth_source(quoted_syms, scan_symbols)
    meta["n_rows"] = len(scan_df)
    meta["quotes_fetched"] = len(equity_quotes)
    meta["vnindex_quote_fetched"] = vn_ok

    if write_outputs:
        _write_outputs(scan_df, meta, cfg, mode, asof_timestamp, out_dir, quotes_df=quotes_df)

    return scan_df, meta


def _write_outputs(
    scan_df: pd.DataFrame,
    meta: Dict[str, Any],
    cfg: Dict[str, Any],
    mode: str,
    ts: datetime,
    out_dir: Path,
    *,
    quotes_df: Optional[pd.DataFrame] = None,
) -> None:
    import json

    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = (cfg.get("modes") or {}).get(mode, {}).get("output_prefix", "phase36_intraday_scan")
    stamp = ts.strftime("%Y%m%d_%H%M")
    path = out_dir / f"{prefix}_{stamp}.csv"
    latest = out_dir / "phase36_intraday_scan_latest.csv"
    latest_meta = out_dir / "phase36_intraday_scan_latest_meta.json"
    scan_df.to_csv(path, index=False)
    scan_df.to_csv(latest, index=False)
    meta_path = out_dir / f"{prefix}_{stamp}_meta.json"
    meta_json = json.dumps(meta, indent=2, default=str)
    meta_path.write_text(meta_json, encoding="utf-8")
    latest_meta.write_text(meta_json, encoding="utf-8")
    write_intraday_report(
        scan_df,
        meta,
        quotes_df if quotes_df is not None else pd.DataFrame(),
        cfg,
        mode,
        ts,
        out_dir,
    )
