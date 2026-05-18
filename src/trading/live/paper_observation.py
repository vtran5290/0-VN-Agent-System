"""Paper-observation diagnostics: valid-day marker and daily operator pack."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.trading.config import REPO_ROOT
from src.trading.live.account_dashboard import (
    _intent_stats,
    _ledger_stats,
    _load_intents_for_account,
    _portfolio_metrics,
    write_compare_report,
)
from src.trading.live.csv_parse import parse_csv_bool
from src.trading.live.paper_accounts import (
    A3_PAPER_RUN_ORDER,
    PaperAccountConfig,
    account_observation_role,
    build_live_config_for_account,
    get_paper_account,
    scan_size_basis_metadata,
)
from src.trading.live.path_safety import is_under_paper_trade
from src.trading.live.recon_status import load_reconciliation_status
from src.trading.live.run_lock import DailyRunLock
from src.trading.util.timeutil import utc_now_iso

REFERENCE_SIZING_WARNING = (
    "This account may show cash drag because scan sizing is based on reference NAV, "
    "not account-scaled target sizing."
)


def _manifest_for_date(cfg, asof_date: str) -> Dict[str, Any]:
    lock = DailyRunLock(cfg)
    m = lock.load_manifest(asof_date, "paper", getattr(cfg, "account_id", "") or "")
    if m is None:
        return {}
    return m.to_dict()


def collect_account_observation(
    account_id: str,
    asof_date: str,
) -> Dict[str, Any]:
    acct = get_paper_account(account_id)
    cfg, _ = build_live_config_for_account(account_id)
    stats = _ledger_stats(cfg)
    recon = load_reconciliation_status(cfg) or {}
    pm = _portfolio_metrics(cfg, acct, stats)
    intents = _load_intents_for_account(cfg, asof_date)
    ist = _intent_stats(intents)
    basis = scan_size_basis_metadata(acct)
    manifest = _manifest_for_date(cfg, asof_date)
    status_path = cfg.dashboard_dir / "latest_status.json"
    st: Dict[str, Any] = {}
    if status_path.exists():
        try:
            st = json.loads(status_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    root = str(cfg.account_root or "").replace("\\", "/")
    return {
        "account_id": account_id,
        "observation_role": account_observation_role(acct),
        "traffic_light_status": st.get("traffic_light_status", "UNKNOWN"),
        "traffic_light_reasons": st.get("traffic_light_reasons", []),
        "reconciliation_status": st.get("reconciliation_status", recon.get("status", "UNKNOWN")),
        "manifest_status": manifest.get("status", "MISSING"),
        "ledger_root": root,
        "ledger_contaminated": is_under_paper_trade(Path(root)) if root else False,
        **basis,
        **pm,
        **stats,
        **ist,
        "new_fills_today": st.get("new_fills_today", 0),
        "exits_today": st.get("exits_today", 0),
        "risk_rejection_count": st.get("risk_rejection_count", 0),
    }


def evaluate_valid_paper_day(
    asof_date: str,
    *,
    scan_meta: Dict[str, Any],
    account_rows: List[Dict[str, Any]],
    s3_shadow: Optional[Dict[str, Any]] = None,
    test_mode: bool = False,
    allow_sample: bool = False,
    workflow_aborted: bool = False,
    errors: Optional[List[str]] = None,
) -> Dict[str, Any]:
    invalid: List[str] = []
    warnings: List[str] = []

    if workflow_aborted:
        invalid.append("workflow_aborted")
    if errors:
        for e in errors:
            warnings.append(f"run_error:{e}")

    if scan_meta.get("is_stale"):
        invalid.append("stale_scan")
    if scan_meta.get("is_sample") and not (test_mode or allow_sample):
        invalid.append("sample_scan")

    health = str(scan_meta.get("data_health_status", "") or "")
    if health == "CRITICAL_FAIL":
        invalid.append("data_health_critical")

    required = list(A3_PAPER_RUN_ORDER)
    ran_ids = {r.get("account_id") for r in account_rows}
    for aid in required:
        if aid not in ran_ids:
            invalid.append(f"missing_account_run:{aid}")

    for row in account_rows:
        aid = row.get("account_id", "")
        if row.get("traffic_light_status") == "RED":
            invalid.append(f"traffic_light_red:{aid}")
        recon = str(row.get("reconciliation_status", "")).upper()
        if recon in ("BLOCK", "DIRTY"):
            invalid.append(f"reconciliation_dirty:{aid}")
        if row.get("ledger_contaminated"):
            invalid.append(f"ledger_under_paper_trade:{aid}")
        mst = str(row.get("manifest_status", "")).upper()
        if not test_mode and mst and mst not in ("COMPLETED",):
            invalid.append(f"manifest_not_completed:{aid}:{mst}")
        elif not test_mode and mst == "MISSING":
            invalid.append(f"manifest_missing:{aid}")
        if row.get("traffic_light_status") == "YELLOW":
            warnings.append(f"traffic_light_yellow:{aid}")
        if row.get("manual_review", 0) > 0:
            warnings.append(f"manual_review_pending:{aid}")
        if row.get("reference_sizing_warning"):
            warnings.append(f"reference_scan_sizing:{aid}")

    s3_status = "not_run"
    if s3_shadow is not None:
        s3_status = "ok"
        blocked = s3_shadow.get("blocked_count", 0) if isinstance(s3_shadow, dict) else 0
        if int(blocked or 0) > 0:
            warnings.append("s3_shadow_blocked_rows")

    valid = len(invalid) == 0
    return {
        "date": asof_date,
        "scan_path": scan_meta.get("path", scan_meta.get("resolved_path", "")),
        "scan_hash": scan_meta.get("scan_hash", ""),
        "accounts": account_rows,
        "s3_shadow_status": s3_status,
        "s3_shadow": s3_shadow if isinstance(s3_shadow, dict) else {},
        "valid_paper_day": valid,
        "invalid_reasons": invalid,
        "warnings": warnings,
        "generated_at": utc_now_iso(),
        "test_mode": test_mode,
        "allow_sample": allow_sample,
    }


def write_valid_paper_day_json(
    asof_date: str,
    payload: Dict[str, Any],
) -> Path:
    ymd = asof_date.replace("-", "")
    out = REPO_ROOT / "data" / "trading" / "live" / "accounts" / f"valid_paper_day_{ymd}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def _capacity_interpretation_20b(row: Dict[str, Any]) -> str:
    drag = float(row.get("cash_drag_pct", 0))
    liq = int(row.get("capped_by_adv_liquidity", 0) or row.get("liquidity_cap_hits", 0))
    if drag > 50 and liq == 0:
        return (
            "High cash drag with few ADV liquidity caps — likely **under-deployment** from "
            "5B scan-size basis / insufficient signals, not necessarily liquidity limits."
        )
    if drag > 50 and liq > 0:
        return "High cash drag with ADV cap hits — likely **liquidity/capacity constraint**."
    return "20B stress account within normal deployment band for today."


def write_daily_operator_pack(
    asof_date: str,
    *,
    scan_meta: Dict[str, Any],
    account_rows: List[Dict[str, Any]],
    valid_day: Dict[str, Any],
    compare_path: Optional[Path] = None,
    s3_shadow: Optional[Dict[str, Any]] = None,
) -> Path:
    ymd = asof_date.replace("-", "")
    out = REPO_ROOT / "data" / "trading" / "live" / "accounts" / f"daily_operator_pack_{ymd}.md"
    by_id = {r["account_id"]: r for r in account_rows}

    lines = [
        f"# Daily operator pack — {asof_date}",
        "",
        "> Paste this file back into ChatGPT for paper-observation review. "
        "Account differences are **sizing/liquidity**, not strategy changes.",
        "",
        "## A. Scan status",
        f"- Resolved scan: `{scan_meta.get('path', scan_meta.get('resolved_path', ''))}`",
        f"- Scan date: {asof_date}",
        f"- Scan hash: `{scan_meta.get('scan_hash', '')}`",
        f"- Stale: {scan_meta.get('is_stale', False)}",
        f"- Sample: {scan_meta.get('is_sample', False)}",
        f"- Wrong-date / blocked: {scan_meta.get('blocked', False)}",
        "",
        "## B. Account traffic lights",
    ]
    for aid in A3_PAPER_RUN_ORDER:
        r = by_id.get(aid, {})
        lines.extend([
            f"### {aid}",
            f"- Traffic light: **{r.get('traffic_light_status', 'UNKNOWN')}**",
            f"- Cash: {r.get('cash_vnd', 0):,.0f} VND | Equity: {r.get('equity', 0):,.0f} VND",
            f"- Return: {r.get('return_pct', 0):.2f}% | Cash drag: {r.get('cash_drag_pct', 0):.1f}%",
            f"- Gross exposure: {r.get('gross_exposure_pct', 0):.1f}%",
            f"- New fills: {r.get('new_fills_today', 0)} | Exits: {r.get('exits_today', 0)}",
            f"- Manual review intents: {r.get('manual_review', 0)}",
            f"- Risk rejects: {r.get('risk_rejection_count', 0)}",
            f"- Reconciliation: {r.get('reconciliation_status', 'UNKNOWN')}",
            f"- Scan size basis: `{r.get('scan_size_basis', '')}` (ref NAV {r.get('scan_reference_nav_VND', 0):,.0f})",
            "",
        ])

    lines.extend(["## C. Capacity interpretation", ""])
    sm = by_id.get("A3_DSE_PILOT_PAPER_SMALL", {})
    if sm.get("new_fills_today", 0) == 0 and (
        sm.get("below_min_trade", 0) or sm.get("capped_orders", 0) or sm.get("skip_count", 0)
    ):
        lines.append(
            "- **30M small:** No fills — likely min-trade / account cap skips (not strategy failure)."
        )
    else:
        lines.append(f"- **30M small:** Fills={sm.get('new_fills_today', 0)}; below-min={sm.get('below_min_trade', 0)}.")

    ref = by_id.get("A3_PROD_PAPER_5B", {})
    lines.append(
        f"- **5B reference:** Return {ref.get('return_pct', 0):.2f}%; cash drag {ref.get('cash_drag_pct', 0):.1f}%."
    )

    s10 = by_id.get("A3_SCALE_PAPER_10B", {})
    lines.append(
        f"- **10B scale:** Return {s10.get('return_pct', 0):.2f}%; "
        f"similar to 5B if within ~2% — else slot/cash/cap effects."
    )
    if s10.get("reference_sizing_warning"):
        lines.append(f"  - {REFERENCE_SIZING_WARNING}")

    s20 = by_id.get("A3_SCALE_PAPER_20B", {})
    lines.append(f"- **20B stress:** {_capacity_interpretation_20b(s20)}")
    lines.append(
        f"  - Caps: max_order={s20.get('capped_by_max_order_value', 0)} | "
        f"ADV={s20.get('capped_by_adv_liquidity', 0)} | cash={s20.get('capped_by_cash', 0)} | "
        f"below-min={s20.get('below_min_trade', 0)}"
    )
    if s20.get("reference_sizing_warning"):
        lines.append(f"  - {REFERENCE_SIZING_WARNING}")
    lines.append("")

    lines.extend(["## D. S3 shadow"])
    if s3_shadow:
        lines.extend([
            f"- Processed: {s3_shadow.get('recorded', 0)} | Skipped: {s3_shadow.get('skipped', 0)}",
            f"- Blocked: {s3_shadow.get('blocked_count', 0)}",
            "- No A3 ledger contamination (separate `s3_shadow/` ledger).",
            "- No DSE/DNSE route (shadow only).",
        ])
    else:
        lines.append("- Not run today (`--include-s3-shadow` not set).")
    lines.append("")

    lines.extend([
        "## E. Compare summary",
        f"- Full compare: `{compare_path or ''}`",
        "- Differences across 30M / 5B / 10B / 20B = **account size & liquidity capacity**, not A3 logic.",
        "",
        "## F. Problems / warnings",
    ])
    if valid_day.get("invalid_reasons"):
        for r in valid_day["invalid_reasons"]:
            lines.append(f"- INVALID: {r}")
    for w in valid_day.get("warnings", []):
        lines.append(f"- WARNING: {w}")
    if not valid_day.get("invalid_reasons") and not valid_day.get("warnings"):
        lines.append("- None.")
    lines.append("")

    lines.extend(["## G. Verdict", ""])
    if valid_day.get("valid_paper_day") and not valid_day.get("warnings"):
        verdict = "Clean paper day"
    elif valid_day.get("valid_paper_day"):
        verdict = "Valid paper day with warnings"
    elif any("reconciliation" in x or "data_health" in x or "stale" in x for x in valid_day.get("invalid_reasons", [])):
        verdict = "Stop: data/reconciliation issue"
    else:
        verdict = "Invalid paper day / rerun needed"
    lines.append(f"**{verdict}**")
    lines.append("")

    lines.extend([
        "## H. Next action",
        f"- valid_paper_day: {valid_day.get('valid_paper_day')}",
        "- Manual review needed?"
        + (" Yes — see per-account queues." if any(r.get("manual_review", 0) for r in account_rows) else " No."),
        "- Tomorrow proceed normally?"
        + (" Yes, if warnings addressed." if valid_day.get("valid_paper_day") else " No — fix invalid reasons first."),
        "",
        "---",
        "Real capital: NO-GO | DSE/DNSE live: NO-GO | live_auto: NO-GO",
    ])
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def finalize_paper_observation(
    asof_date: str,
    *,
    scan_meta: Dict[str, Any],
    account_results: List[Dict[str, Any]],
    s3_shadow: Optional[Dict[str, Any]] = None,
    test_mode: bool = False,
    allow_sample: bool = False,
    workflow_aborted: bool = False,
    errors: Optional[List[str]] = None,
) -> Dict[str, str]:
    """Write compare (if not done), valid_paper_day JSON, operator pack; return paths."""
    compare_path = write_compare_report(asof_date, A3_PAPER_RUN_ORDER)
    rows = [collect_account_observation(aid, asof_date) for aid in A3_PAPER_RUN_ORDER]
    valid = evaluate_valid_paper_day(
        asof_date,
        scan_meta=scan_meta,
        account_rows=rows,
        s3_shadow=s3_shadow,
        test_mode=test_mode,
        allow_sample=allow_sample,
        workflow_aborted=workflow_aborted,
        errors=errors,
    )
    valid_path = write_valid_paper_day_json(asof_date, valid)
    pack_path = write_daily_operator_pack(
        asof_date,
        scan_meta=scan_meta,
        account_rows=rows,
        valid_day=valid,
        compare_path=compare_path,
        s3_shadow=s3_shadow,
    )
    return {
        "compare_report": str(compare_path),
        "valid_paper_day": str(valid_path),
        "daily_operator_pack": str(pack_path),
    }
