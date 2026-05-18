"""Run daily paper workflows for all A3 accounts (+ optional S3 shadow)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.trading.config import REPO_ROOT, load_live_trading_config
from src.trading.live.paper_observation import finalize_paper_observation
from src.trading.live.paper_accounts import (
    A3_PAPER_RUN_ORDER,
    build_live_config_for_account,
    get_paper_account,
)
from src.trading.live.s3_shadow_workflow import update_s3_shadow
from src.trading.live.scan_resolver import resolve_scan
from src.trading.live.workflow import run as run_workflow

A3_RUN_ORDER = A3_PAPER_RUN_ORDER


def _load_latest_status(cfg) -> Dict[str, Any]:
    p = cfg.dashboard_dir / "latest_status.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def format_operator_summary(result: Dict[str, Any]) -> str:
    lines = [
        "=" * 60,
        "PAPER-LIVE DAILY RUN SUMMARY",
        "=" * 60,
        f"Date: {result.get('asof_date', '')}",
    ]
    scan = result.get("scan") or {}
    lines.append(f"Scan: {scan.get('path', scan.get('resolved_path', ''))}")
    lines.append(f"Scan hash: {scan.get('scan_hash', '')}")
    if scan.get("is_sample"):
        lines.append("WARNING: sample scan")
    if scan.get("is_stale"):
        lines.append("WARNING: stale scan")
    lines.append("")
    for r in result.get("account_results", []):
        aid = r.get("account_id", "")
        st = _load_latest_status(r.get("_config")) if r.get("_config") else {}
        traffic = st.get("traffic_light_status", r.get("traffic_light", "UNKNOWN"))
        reasons = st.get("traffic_light_reasons", [])
        lines.extend([
            f"--- {aid} ---",
            f"  Status: {'ABORTED' if r.get('aborted') else 'OK'}",
            f"  Traffic light: {traffic}",
            f"  Reasons: {', '.join(reasons) if reasons else '-'}",
            f"  Intents: {r.get('intents_count', 0)} | Paper fills: {r.get('paper_fills', 0)}",
            f"  Manual review: {st.get('manual_review_count', 0)} | Risk rejects: {st.get('risk_rejection_count', 0)}",
            f"  Reconciliation: {st.get('reconciliation_status', r.get('reconciliation', 'UNKNOWN'))}",
            f"  Equity: {st.get('equity', 0):,.0f} VND",
            "",
        ])
    s3 = result.get("s3_shadow")
    if s3:
        lines.extend([
            "--- S3_MAX60_SHADOW_PAPER ---",
            f"  Recorded: {s3.get('recorded', 0)} | Skipped: {s3.get('skipped', 0)}",
            f"  Blocked: {s3.get('blocked_count', 0)}",
            "",
        ])
    lines.append(f"Compare report: {result.get('compare_report', '')}")
    lines.append(f"Valid paper day: {result.get('valid_paper_day', '')}")
    lines.append(f"Daily operator pack (paste to ChatGPT): {result.get('daily_operator_pack', '')}")
    lines.append("Real capital: NO-GO | DSE/DNSE live: NO-GO | live_auto: NO-GO")
    lines.append("=" * 60)
    return "\n".join(lines)


def run_all_paper_accounts(
    asof_date: str,
    scan_path: Optional[Path] = None,
    *,
    force: bool = False,
    include_s3_shadow: bool = False,
    allow_sample: bool = False,
    test_mode: bool = False,
    continue_on_error: bool = False,
) -> Dict[str, Any]:
    base = load_live_trading_config()
    if allow_sample:
        base.allow_sample_scan = True
    scan = resolve_scan(base, asof_date, cli_scan_path=scan_path, test_mode=test_mode)
    if scan.blocked and not (test_mode or allow_sample):
        return _finalize(
            asof_date, scan, [], None, list(scan.errors),
            aborted=True, test_mode=test_mode, allow_sample=allow_sample,
        )

    account_results: List[Dict[str, Any]] = []
    errors: List[str] = []

    for aid in A3_RUN_ORDER:
        cfg, acct = build_live_config_for_account(aid)
        try:
            r = run_workflow(
                "paper",
                asof_date,
                scan_path=scan.path,
                force=force,
                account_id=aid,
                test_mode=test_mode or allow_sample,
            )
            status = _load_latest_status(cfg)
            entry = {
                "account_id": aid,
                "_config": cfg,
                **r,
                "traffic_light": status.get("traffic_light_status", "UNKNOWN"),
                "traffic_light_reasons": status.get("traffic_light_reasons", []),
            }
            account_results.append(entry)
            if r.get("aborted") and not continue_on_error:
                return _finalize(
                    asof_date, scan, account_results, None, errors,
                    aborted=True, stopped_at=aid, test_mode=test_mode, allow_sample=allow_sample,
                )
        except Exception as e:
            errors.append(f"{aid}: {e}")
            account_results.append({"account_id": aid, "aborted": True, "error": str(e)})
            if not continue_on_error:
                return _finalize(
                    asof_date, scan, account_results, None, errors,
                    aborted=True, stopped_at=aid, test_mode=test_mode, allow_sample=allow_sample,
                )

    s3_result = None
    if include_s3_shadow:
        s3_result = update_s3_shadow(
            asof_date,
            scan_path=scan.path,
            test_mode=test_mode or allow_sample,
            allow_undated_scan=test_mode or allow_sample,
        )

    return _finalize(
        asof_date, scan, account_results, s3_result, errors,
        aborted=False, test_mode=test_mode, allow_sample=allow_sample,
    )


def _finalize(
    asof_date: str,
    scan,
    account_results: List[Dict[str, Any]],
    s3_result: Optional[Dict[str, Any]],
    errors: List[str],
    *,
    aborted: bool,
    stopped_at: str = "",
    test_mode: bool = False,
    allow_sample: bool = False,
) -> Dict[str, Any]:
    scan_meta = scan.metadata if scan else {}
    obs_paths = finalize_paper_observation(
        asof_date,
        scan_meta=scan_meta,
        account_results=account_results,
        s3_shadow=s3_result,
        test_mode=test_mode,
        allow_sample=allow_sample,
        workflow_aborted=aborted,
        errors=errors,
    )
    out: Dict[str, Any] = {
        "aborted": aborted,
        "asof_date": asof_date,
        "stopped_at": stopped_at,
        "scan": scan_meta,
        "account_results": [{k: v for k, v in r.items() if k != "_config"} for r in account_results],
        "s3_shadow": s3_result,
        "errors": errors,
        **obs_paths,
    }
    summary_path = REPO_ROOT / "data" / "trading" / "live" / "accounts" / f"run_all_summary_{asof_date.replace('-', '')}.md"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    out_for_print = {**out, "account_results": account_results}
    summary_text = format_operator_summary(out_for_print)
    summary_path.write_text(summary_text, encoding="utf-8")
    out["operator_summary_path"] = str(summary_path)
    out["operator_summary_text"] = summary_text
    return out
