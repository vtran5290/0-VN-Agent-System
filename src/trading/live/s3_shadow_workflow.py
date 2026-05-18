"""S3 max60 paper-shadow workflow — no OMS, no A3 P&L."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from src.trading.config import REPO_ROOT, load_live_trading_config
from src.trading.live.paper_accounts import get_paper_account
from src.trading.live.path_safety import validate_live_output_path
from src.trading.live.scan_resolver import resolve_scan
from src.trading.live.s3_flag import s3_shadow_block_reason
from src.trading.live.s3_shadow_paper_ledger import S3ShadowPaperLedger


def _filter_scan_to_date(
    df: pd.DataFrame,
    asof_date: str,
    *,
    allow_undated_scan: bool = False,
) -> tuple[pd.DataFrame, List[str]]:
    """Return rows for asof_date only; warnings if undated."""
    warnings: List[str] = []
    ad = asof_date[:10]
    if "as_of_date" in df.columns:
        df = df.copy()
        df["as_of_date"] = pd.to_datetime(df["as_of_date"], errors="coerce").dt.strftime("%Y-%m-%d")
        day = df[df["as_of_date"] == ad]
        return day, warnings
    for col in ("date", "asof_date", "signal_date"):
        if col in df.columns:
            df = df.copy()
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%Y-%m-%d")
            day = df[df[col] == ad]
            return day, warnings
    if allow_undated_scan:
        warnings.append("undated_scan_allowed")
        return df, warnings
    warnings.append("missing_date_column_fail_closed")
    return pd.DataFrame(), warnings


def update_s3_shadow(
    asof_date: str,
    scan_path: Optional[Path] = None,
    *,
    test_mode: bool = False,
    allow_undated_scan: bool = False,
) -> Dict[str, Any]:
    get_paper_account("S3_MAX60_SHADOW_PAPER")
    base = load_live_trading_config()
    base.allow_sample_scan = test_mode
    scan = resolve_scan(base, asof_date, cli_scan_path=scan_path, test_mode=test_mode)
    if scan.blocked and not test_mode:
        return {"error": scan.errors, "aborted": True, "scan": scan.metadata}

    ledger = S3ShadowPaperLedger()
    validate_live_output_path(ledger.root, context="s3_shadow")

    df = pd.read_csv(scan.path, dtype=object)
    day, date_warnings = _filter_scan_to_date(
        df, asof_date, allow_undated_scan=allow_undated_scan or test_mode
    )
    if day.empty and date_warnings:
        return {
            "asof_date": asof_date,
            "aborted": True,
            "error": date_warnings,
            "scan": scan.metadata,
            "recorded": 0,
            "skipped": 0,
        }

    recorded = 0
    skipped = 0
    blocked: List[Dict[str, Any]] = []

    for idx, row in day.iterrows():
        block = s3_shadow_block_reason(row.get("s3_no_real_order_flag"))
        shadow_action = str(row.get("s3_shadow_action") or row.get("final_action", ""))
        if shadow_action not in ("PAPER_S3_SHADOW", "PAPER_S3_RESEARCH_MONITOR"):
            skipped += 1
            continue
        if block:
            blocked.append({
                "symbol": row.get("symbol", ""),
                "date": asof_date,
                "s3_shadow_action": shadow_action,
                "s3_shadow_blocked_reason": block,
            })
            skipped += 1
            continue
        try:
            ledger.record_shadow_intent({
                "symbol": row.get("symbol", ""),
                "date": asof_date,
                "s3_shadow_action": shadow_action,
                "s3_no_real_order_flag": True,
                "action": shadow_action,
                "reason_code": row.get("final_action", ""),
            })
            recorded += 1
        except ValueError:
            skipped += 1

    diag_path = None
    if blocked:
        ymd = asof_date.replace("-", "")
        diag_path = ledger.root / f"s3_shadow_blocked_{ymd}.csv"
        pd.DataFrame(blocked).to_csv(diag_path, index=False)

    return {
        "asof_date": asof_date,
        "scan": scan.metadata,
        "recorded": recorded,
        "skipped": skipped,
        "blocked_count": len(blocked),
        "blocked_diagnostic": str(diag_path) if diag_path else "",
        "date_warnings": date_warnings,
        "rows_in_date": len(day),
        "ledger_root": str(ledger.root),
    }


def s3_shadow_summary() -> Dict[str, Any]:
    ledger = S3ShadowPaperLedger()
    trades = ledger._load_trades()
    return {
        "account_id": "S3_MAX60_SHADOW_PAPER",
        "ledger_root": str(ledger.root),
        "shadow_rows": len(trades),
        "symbols": trades["symbol"].tolist() if not trades.empty else [],
    }
