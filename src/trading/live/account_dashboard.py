"""Per-account paper dashboard outputs and cross-account compare."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from src.trading.config import REPO_ROOT, LiveTradingConfig
from src.trading.live.csv_parse import parse_csv_bool
from src.trading.live.paper_accounts import (
    A3_PAPER_RUN_ORDER,
    PaperAccountConfig,
    account_observation_role,
    build_live_config_for_account,
    get_paper_account,
    scan_size_basis_metadata,
)
from src.trading.live.paper_ledger import PaperLedger
from src.trading.live.recon_status import load_reconciliation_status
from src.trading.util.timeutil import utc_now_iso


def _read_broker_cash(config: LiveTradingConfig) -> float:
    p = config.paper_broker_state_path
    if not p.exists():
        return float(getattr(config, "initial_cash_vnd", 0))
    data = json.loads(p.read_text(encoding="utf-8"))
    return float(data.get("cash_vnd", 0))


def _ledger_stats(config: LiveTradingConfig) -> Dict[str, Any]:
    ledger = PaperLedger(config)
    trades = ledger._load_trades()
    pos = ledger._load_positions()
    realized = 0.0
    closed = 0
    open_trades = 0
    if not trades.empty:
        closed_df = trades[trades["state"] == "CLOSED"]
        closed = len(closed_df)
        if "realized_pnl" in closed_df.columns:
            realized = float(pd.to_numeric(closed_df["realized_pnl"], errors="coerce").fillna(0).sum())
        open_states = {"NEW_T1", "PB_WAIT", "T2_ADDED", "HOLD_T1_ONLY", "TP1_HIT", "TRAIL_EXIT"}
        open_trades = int(trades["state"].isin(open_states).sum())
    unrealized = 0.0
    if not pos.empty and "unrealized_pnl" in pos.columns:
        unrealized = float(pd.to_numeric(pos["unrealized_pnl"], errors="coerce").fillna(0).sum())
    cash = _read_broker_cash(config)
    exposure = float(pos["market_value_VND"].sum()) if not pos.empty and "market_value_VND" in pos.columns else 0.0
    equity = cash + exposure
    return {
        "cash_vnd": cash,
        "positions_count": len(pos),
        "open_trades": open_trades,
        "closed_trades": closed,
        "realized_pnl": realized,
        "unrealized_pnl": unrealized,
        "equity": equity,
    }


def _intent_stats(intents: Optional[pd.DataFrame]) -> Dict[str, Any]:
    stats: Dict[str, Any] = {
        "intents_processed": 0,
        "buy_t1": 0,
        "buy_t2": 0,
        "sell_tp1": 0,
        "sell_exit": 0,
        "skip_count": 0,
        "manual_review": 0,
        "sizing_adjustments": 0,
        "capped_orders": 0,
        "below_min_trade": 0,
        "liquidity_cap_hits": 0,
        "capped_by_max_order_value": 0,
        "capped_by_cash": 0,
        "capped_by_adv_liquidity": 0,
        "risk_rejects_by_reason": {},
    }
    if intents is None or intents.empty:
        return stats
    stats["intents_processed"] = len(intents)
    for _, row in intents.iterrows():
        act = str(row.get("action", ""))
        if act in ("BUY_T1", "BUY_T1_MANUAL_REVIEW"):
            stats["buy_t1"] += 1
        elif act == "BUY_T2":
            stats["buy_t2"] += 1
        elif act == "SELL_TP1":
            stats["sell_tp1"] += 1
        elif act == "SELL_EXIT":
            stats["sell_exit"] += 1
        elif act.startswith("SKIP") or act == "WATCH_INVALID_SIZE":
            stats["skip_count"] += 1
        if parse_csv_bool(row.get("requires_manual_review", False)):
            stats["manual_review"] += 1
        reason = str(row.get("sizing_adjustment_reason", ""))
        if reason in ("capped_to_account_limits", "capped_to_liquidity", "liquidity_cap_hit"):
            stats["sizing_adjustments"] += 1
            stats["capped_orders"] += 1
            if reason in ("capped_to_liquidity", "liquidity_cap_hit"):
                stats["liquidity_cap_hits"] += 1
        elif reason == "below_min_trade_value":
            stats["below_min_trade"] += 1
        if parse_csv_bool(row.get("capped_by_max_order_value", False)):
            stats["capped_by_max_order_value"] += 1
        if parse_csv_bool(row.get("capped_by_cash", False)):
            stats["capped_by_cash"] += 1
        if parse_csv_bool(row.get("capped_by_adv_liquidity", False)):
            stats["capped_by_adv_liquidity"] += 1
    return stats


def _portfolio_metrics(
    config: LiveTradingConfig,
    account: PaperAccountConfig,
    stats: Dict[str, Any],
) -> Dict[str, float]:
    start = float(account.starting_cash_VND or 1)
    equity = float(stats.get("equity", 0))
    cash = float(stats.get("cash_vnd", 0))
    exposure = equity - cash if equity >= cash else 0.0
    ret_pct = ((equity - start) / start * 100.0) if start > 0 else 0.0
    cash_drag = (cash / equity * 100.0) if equity > 0 else 100.0
    gross_exp = (exposure / equity * 100.0) if equity > 0 else 0.0
    max_slots = int(account.max_slots or 1)
    pos_util = (stats.get("positions_count", 0) / max_slots * 100.0) if max_slots > 0 else 0.0
    ledger = PaperLedger(config)
    pos = ledger._load_positions()
    avg_pos = 0.0
    largest_pct = 0.0
    if not pos.empty and equity > 0 and "market_value_VND" in pos.columns:
        mv = pd.to_numeric(pos["market_value_VND"], errors="coerce").fillna(0)
        if len(mv) > 0:
            avg_pos = float(mv.mean())
            largest_pct = float(mv.max() / equity * 100.0)
    return {
        "return_pct": ret_pct,
        "cash_drag_pct": cash_drag,
        "gross_exposure_pct": gross_exp,
        "position_utilization_pct": pos_util,
        "avg_position_size_vnd": avg_pos,
        "largest_position_pct": largest_pct,
    }


def _latest_manifest(config: LiveTradingConfig) -> Dict[str, Any]:
    mdir = config.run_manifests_dir
    if not mdir.exists():
        return {}
    files = sorted(mdir.glob("run_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return {}
    data = json.loads(files[0].read_text(encoding="utf-8"))
    return {
        "latest_run_date": data.get("date", ""),
        "latest_run_mode": data.get("mode", ""),
        "latest_run_status": data.get("status", ""),
        "scan_file": data.get("scan_file", ""),
        "scan_hash": data.get("scan_hash", ""),
    }


def compute_traffic_light(
    *,
    health_status: Optional[Dict[str, Any]] = None,
    kill_switch: Optional[Dict[str, Any]] = None,
    scan_meta: Optional[Dict[str, Any]] = None,
    recon: Optional[Dict[str, Any]] = None,
    intents: Optional[pd.DataFrame] = None,
    orders: Optional[List[Any]] = None,
    workflow_error: str = "",
) -> tuple[str, List[str]]:
    reasons: List[str] = []
    hs = health_status or {}
    ks = kill_switch or {}
    sm = scan_meta or {}
    rc = recon or {}

    if workflow_error:
        return "RED", [f"workflow_error:{workflow_error}"]
    if hs.get("status") == "CRITICAL_FAIL":
        reasons.append("data_health_critical")
    if sm.get("is_sample") and not sm.get("allow_sample"):
        reasons.append("sample_scan")
    if sm.get("is_stale"):
        reasons.append("stale_scan")
    if rc.get("BLOCK_NEW_ORDERS") or str(rc.get("status", "")).upper() in ("BLOCK", "DIRTY"):
        reasons.append("reconciliation_dirty")
    if str(ks.get("status", "")).upper() == "BLOCK":
        reasons.append("kill_switch_block")

    if reasons:
        return "RED", reasons

    yellow: List[str] = []
    if hs.get("status") == "WARN":
        yellow.append("data_health_warn")
    ist = _intent_stats(intents)
    if ist["manual_review"] > 0:
        yellow.append("manual_review_pending")
    if ist["below_min_trade"] > 0 or ist["capped_orders"] > 0 or ist.get("liquidity_cap_hits", 0) > 0:
        yellow.append("account_sizing_constraints")
    if intents is not None and not intents.empty:
        tradeable = intents[intents["action"].isin(["BUY_T1", "BUY_T1_MANUAL_REVIEW", "BUY_T2", "SELL_TP1", "SELL_EXIT"])]
        filled = 0
        if orders:
            filled = sum(1 for o in orders if getattr(getattr(o, "state", None), "value", str(o.state)) == "FILLED")
        if len(tradeable) == 0 and ist["skip_count"] > 0:
            yellow.append("no_tradeable_intents")
    if yellow:
        return "YELLOW", yellow
    return "GREEN", ["workflow_ok"]


def account_summary(config: LiveTradingConfig, account: PaperAccountConfig) -> Dict[str, Any]:
    stats = _ledger_stats(config)
    recon = load_reconciliation_status(config) or {}
    manifest = _latest_manifest(config)
    return {
        "account_id": account.account_id,
        "account_type": account.type,
        "strategy": account.strategy,
        "starting_cash_VND": account.starting_cash_VND,
        "sizing_policy": getattr(account, "sizing_policy", ""),
        "ledger_root": str(config.account_root or config.live_dir),
        **stats,
        **manifest,
        "reconciliation_status": recon.get("status", "UNKNOWN"),
        "reconciliation_issues": recon.get("issues", []),
    }


def write_account_dashboard(
    config: LiveTradingConfig,
    account: PaperAccountConfig,
    asof_date: str,
    *,
    intents: Optional[pd.DataFrame] = None,
    orders: Optional[List[Any]] = None,
    health_status: Optional[Dict[str, Any]] = None,
    kill_switch: Optional[Dict[str, Any]] = None,
    scan_meta: Optional[Dict[str, Any]] = None,
) -> Path:
    dash = config.dashboard_dir
    dash.mkdir(parents=True, exist_ok=True)
    ymd = asof_date.replace("-", "")
    stats = _ledger_stats(config)
    recon = load_reconciliation_status(config) or {}
    ist = _intent_stats(intents)
    pm = _portfolio_metrics(config, account, stats)
    role = account_observation_role(account)
    basis = scan_size_basis_metadata(account)
    max_slots = int(account.max_slots or 0)
    pos_util = pm["position_utilization_pct"]

    mr_count = ist["manual_review"]
    risk_rej = 0
    risk_reasons: Dict[str, int] = {}
    fills_today = 0
    exits_today = 0
    if orders:
        for o in orders:
            sig_date = getattr(getattr(o, "proposal", None), "signal", None)
            ad = getattr(sig_date, "asof_date", "")[:10] if sig_date else ""
            if ad != asof_date[:10]:
                continue
            st = getattr(o, "state", None)
            st_val = st.value if hasattr(st, "value") else str(st)
            if st_val == "FILLED":
                fills_today += 1
                meta = getattr(o.proposal.signal, "metadata", {}) if o.proposal else {}
                act = meta.get("action", "") if isinstance(meta, dict) else ""
                if "SELL" in str(act).upper() or "EXIT" in str(act).upper():
                    exits_today += 1
            if st_val == "REJECTED_BY_RISK":
                risk_rej += 1
                for rid in getattr(o.risk_verdict, "rule_ids", []) or []:
                    risk_reasons[rid] = risk_reasons.get(rid, 0) + 1

    traffic, traffic_reasons = compute_traffic_light(
        health_status=health_status,
        kill_switch=kill_switch,
        scan_meta=scan_meta,
        recon=recon,
        intents=intents,
        orders=orders,
    )

    status = {
        "account_id": account.account_id,
        "account_type": account.type,
        "asof_date": asof_date,
        "generated_at": utc_now_iso(),
        "starting_cash_VND": account.starting_cash_VND,
        "current_cash_VND": stats["cash_vnd"],
        "equity": stats["equity"],
        "realized_pnl": stats["realized_pnl"],
        "unrealized_pnl": stats["unrealized_pnl"],
        "open_positions": stats["positions_count"],
        "open_trades": stats["open_trades"],
        "closed_trades": stats["closed_trades"],
        "new_fills_today": fills_today,
        "exits_today": exits_today,
        "manual_review_count": mr_count,
        "risk_rejection_count": risk_rej,
        "reconciliation_status": recon.get("status", "UNKNOWN"),
        "kill_switch_status": (kill_switch or {}).get("status", "UNKNOWN"),
        "traffic_light_status": traffic,
        "traffic_light_reasons": traffic_reasons,
        "scan": scan_meta or {},
        "intent_stats": ist,
        "observation_role": role,
        "return_pct": pm["return_pct"],
        "cash_drag_pct": pm["cash_drag_pct"],
        "gross_exposure_pct": pm["gross_exposure_pct"],
        "max_slots": max_slots,
        "position_utilization_pct": pos_util,
        "liquidity_cap_hits": ist.get("liquidity_cap_hits", 0),
        "capacity_attribution": ist,
        **basis,
        "a3_production_only": account.is_a3_production and not account.allow_s3,
    }
    (dash / "latest_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")

    lines = [
        f"# Paper daily summary — {account.account_id}",
        f"- Date: {asof_date}",
        f"- Account ID: {account.account_id}",
        f"- Observation role: **{role}**",
        f"- Traffic light: **{traffic}** ({', '.join(traffic_reasons)})",
        f"- Type: {account.type} | Strategy: {account.strategy} | Sizing: {getattr(account, 'sizing_policy', '')}",
        f"- Scan size basis: {basis.get('scan_size_basis', '')} | Ref NAV: {basis.get('scan_reference_nav_VND', 0):,.0f} | "
        f"NAV scaling: {basis.get('account_nav_scaling_enabled', False)}",
        f"- Starting NAV: {account.starting_cash_VND:,.0f} VND",
        f"- Current equity: {stats['equity']:,.0f} VND | Return: {pm['return_pct']:.2f}%",
        f"- Current cash: {stats['cash_vnd']:,.0f} VND | Cash drag: {pm['cash_drag_pct']:.1f}%",
        f"- Gross exposure: {pm['gross_exposure_pct']:.1f}%",
        f"- Realized P&L: {stats['realized_pnl']:,.0f} VND",
        f"- Unrealized P&L: {stats['unrealized_pnl']:,.0f} VND",
        f"- Open positions: {stats['positions_count']} / max slots {max_slots} ({pos_util:.0f}% utilization)",
        f"- New fills today: {fills_today}",
        f"- Exits today: {exits_today}",
        f"- Manual review: {mr_count}",
        f"- Risk rejections: {risk_rej}",
        f"- Sizing adjustments: {ist['sizing_adjustments']} | Capped: {ist['capped_orders']} | "
        f"Liquidity cap hits: {ist.get('liquidity_cap_hits', 0)} | Below min: {ist['below_min_trade']}",
        f"- Cap attribution: max_order={ist.get('capped_by_max_order_value', 0)} | "
        f"ADV={ist.get('capped_by_adv_liquidity', 0)} | cash={ist.get('capped_by_cash', 0)}",
        f"- Reconciliation: {recon.get('status', 'UNKNOWN')}",
        f"- Kill switch: {(kill_switch or {}).get('status', 'UNKNOWN')}",
    ]
    if basis.get("reference_sizing_warning_text"):
        lines.append(f"- **Reference sizing:** {basis['reference_sizing_warning_text']}")
    if account.account_id == "A3_SCALE_PAPER_20B" and pm["cash_drag_pct"] > 50.0:
        lines.append(
            "- **Warning:** High cash drag may indicate capacity/liquidity limitation."
        )
    if account.account_id == "A3_DSE_PILOT_PAPER_SMALL" and fills_today == 0 and (
        ist["below_min_trade"] > 0 or ist["capped_orders"] > 0 or ist["skip_count"] > 0
    ):
        lines.append(
            "- **Note:** Small account rejected/skipped due to account-size constraints; "
            "not a strategy failure."
        )
    if scan_meta:
        lines.append(f"- Scan: {scan_meta.get('path', '')} hash={scan_meta.get('scan_hash', '')}")
    (dash / f"daily_summary_{ymd}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    ledger = PaperLedger(config)
    ledger.export_dashboard(dash)
    trades = ledger._load_trades()
    if not trades.empty:
        closed = trades[trades["state"] == "CLOSED"]
        if not closed.empty:
            closed.to_csv(dash / "closed_trades.csv", index=False)
    if intents is not None and not intents.empty:
        intents.to_csv(dash / f"order_intents_snapshot_{ymd}.csv", index=False)
    return dash / f"daily_summary_{ymd}.md"


def _load_intents_for_account(cfg: LiveTradingConfig, asof_date: str) -> pd.DataFrame:
    p = cfg.order_intents_path(asof_date)
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p, dtype=object)


def write_compare_report(asof_date: str, account_ids: Optional[List[str]] = None) -> Path:
    ids = account_ids or list(A3_PAPER_RUN_ORDER)
    rows: List[Dict[str, Any]] = []
    scan_path = ""
    scan_hash = ""
    by_id: Dict[str, Dict[str, Any]] = {}
    for aid in ids:
        try:
            acct = get_paper_account(aid)
            if not acct.is_a3_production:
                continue
            cfg, _ = build_live_config_for_account(aid)
            stats = _ledger_stats(cfg)
            s = account_summary(cfg, acct)
            pm = _portfolio_metrics(cfg, acct, stats)
            intents = _load_intents_for_account(cfg, asof_date)
            ist = _intent_stats(intents)
            s.update(ist)
            s.update(pm)
            s.update(scan_size_basis_metadata(acct))
            s["observation_role"] = account_observation_role(acct)
            s["max_slots"] = int(acct.max_slots or 0)
            status_path = cfg.dashboard_dir / "latest_status.json"
            if status_path.exists():
                try:
                    st = json.loads(status_path.read_text(encoding="utf-8"))
                    s["traffic_light_status"] = st.get("traffic_light_status", "UNKNOWN")
                    s["traffic_light_reasons"] = st.get("traffic_light_reasons", [])
                    s["new_fills_today"] = st.get("new_fills_today", 0)
                    s["exits_today"] = st.get("exits_today", 0)
                    s["risk_rejection_count"] = st.get("risk_rejection_count", 0)
                    s["kill_switch_status"] = st.get("kill_switch_status", "UNKNOWN")
                except (json.JSONDecodeError, OSError):
                    s.setdefault("kill_switch_status", "UNKNOWN")
            else:
                s.setdefault("kill_switch_status", "UNKNOWN")
            if not scan_path:
                manifest = _latest_manifest(cfg)
                scan_path = manifest.get("scan_file", "")
                scan_hash = manifest.get("scan_hash", "")
            rows.append(s)
            by_id[aid] = s
        except KeyError:
            continue
    ymd = asof_date.replace("-", "")
    out_dir = REPO_ROOT / "data" / "trading" / "live" / "accounts"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"compare_{ymd}.md"
    lines = [
        f"# Paper account compare — {asof_date}",
        "",
        "> **Hard rule:** Differences across 30M / 5B / 10B / 20B paper accounts reflect "
        "**account sizing and liquidity capacity**, not strategy logic. Same scan / same "
        "`final_action` expected.",
        "",
        f"- Scan path: `{scan_path}`",
        f"- Scan hash: `{scan_hash}`",
        f"- Accounts compared: {', '.join(ids)}",
        "",
    ]
    for r in rows:
        lines.extend([
            f"## {r['account_id']} ({r.get('observation_role', '')})",
            f"- Starting cash: {r.get('starting_cash_VND', 0):,.0f} VND",
            f"- Current cash: {r.get('cash_vnd', 0):,.0f} VND",
            f"- Total equity: {r.get('equity', 0):,.0f} VND | Return: {r.get('return_pct', 0):.2f}%",
            f"- Realized P&L: {r.get('realized_pnl', 0):,.0f} VND",
            f"- Unrealized P&L: {r.get('unrealized_pnl', 0):,.0f} VND",
            f"- Open positions: {r.get('positions_count', 0)} | Closed trades: {r.get('closed_trades', 0)}",
            f"- Max slots: {r.get('max_slots', 0)} | Position utilization: {r.get('position_utilization_pct', 0):.0f}%",
            f"- Sizing policy: {r.get('sizing_policy', '')}",
            f"- Scan size basis: `{r.get('scan_size_basis', '')}` | Ref NAV: {r.get('scan_reference_nav_VND', 0):,.0f} | "
            f"NAV scaling: {r.get('account_nav_scaling_enabled', False)}",
            f"- Cash drag: {r.get('cash_drag_pct', 0):.1f}% | Gross exposure: {r.get('gross_exposure_pct', 0):.1f}%",
            f"- Avg position size: {r.get('avg_position_size_vnd', 0):,.0f} VND | "
            f"Largest position: {r.get('largest_position_pct', 0):.1f}% of equity",
            f"- Intents processed: {r.get('intents_processed', 0)}",
            f"- BUY_T1: {r.get('buy_t1', 0)} | BUY_T2: {r.get('buy_t2', 0)} | SELL_TP1: {r.get('sell_tp1', 0)} | SELL_EXIT: {r.get('sell_exit', 0)}",
            f"- SKIP: {r.get('skip_count', 0)} | MANUAL_REVIEW: {r.get('manual_review', 0)}",
            f"- Sizing adjustments: {r.get('sizing_adjustments', 0)} | Capped: {r.get('capped_orders', 0)} | "
            f"Liquidity cap hits: {r.get('liquidity_cap_hits', 0)} | Below-min: {r.get('below_min_trade', 0)}",
            f"- Reconciliation: {r.get('reconciliation_status', 'UNKNOWN')}",
            f"- Kill switch: {r.get('kill_switch_status', 'UNKNOWN')}",
            f"- Traffic light: {r.get('traffic_light_status', 'UNKNOWN')}",
            f"- New fills today: {r.get('new_fills_today', 0)} | Exits today: {r.get('exits_today', 0)}",
            f"- Risk rejections: {r.get('risk_rejection_count', 0)}",
            f"- Latest run: {r.get('latest_run_date', '')} ({r.get('latest_run_status', '')})",
            "",
            "### Capacity attribution",
            f"- Max-order cap hits: {r.get('capped_by_max_order_value', 0)}",
            f"- ADV/liquidity cap hits: {r.get('capped_by_adv_liquidity', 0)}",
            f"- Cash cap hits: {r.get('capped_by_cash', 0)}",
            f"- Below-min-trade skips: {r.get('below_min_trade', 0)}",
        ])
        if r.get("reference_sizing_warning_text"):
            lines.append(f"- **Scan-size basis warning:** {r['reference_sizing_warning_text']}")
        lines.append("")

    def _row(aid: str) -> Dict[str, Any]:
        return by_id.get(aid, {})

    lines.extend([
        "## Scale interpretation",
        "",
        "### A. Small account (A3_DSE_PILOT_PAPER_SMALL — 30M)",
    ])
    sm = _row("A3_DSE_PILOT_PAPER_SMALL")
    if sm:
        note = (
            "Likely rejects/skips from min trade value or max order cap — expected at 30M NAV."
            if sm.get("below_min_trade", 0) or sm.get("capped_orders", 0) or sm.get("skip_count", 0)
            else "No major sizing skips today; pilot mimic behaving within tiny-NAV limits."
        )
        lines.append(f"- {note}")
    else:
        lines.append("- Account not run / no data.")

    lines.extend(["", "### B. 5B reference (A3_PROD_PAPER_5B)"])
    ref = _row("A3_PROD_PAPER_5B")
    if ref:
        lines.append(
            f"- Reference A3 production paper: return {ref.get('return_pct', 0):.2f}%, "
            f"cash drag {ref.get('cash_drag_pct', 0):.1f}%, fills today {ref.get('new_fills_today', 0)}."
        )
    else:
        lines.append("- Account not run / no data.")

    lines.extend(["", "### C. 10B scale check (A3_SCALE_PAPER_10B)"])
    s10 = _row("A3_SCALE_PAPER_10B")
    if s10 and ref:
        similar = abs(s10.get("return_pct", 0) - ref.get("return_pct", 0)) < 2.0
        lines.append(
            "- Behaves similarly to 5B on return/fills."
            if similar and s10.get("liquidity_cap_hits", 0) == 0
            else "- May diverge from 5B due to slot/cash/liquidity constraints — not strategy change."
        )
    elif s10:
        lines.append("- 10B data present; compare to 5B when both have runs.")
    else:
        lines.append("- Account not run / no data.")

    lines.extend(["", "### D. 20B liquidity stress (A3_SCALE_PAPER_20B)"])
    s20 = _row("A3_SCALE_PAPER_20B")
    if s20:
        adv_caps = s20.get("capped_by_adv_liquidity", 0)
        drag = s20.get("cash_drag_pct", 0)
        lines.append(
            f"- Cash drag {drag:.1f}%; ADV cap hits {adv_caps}; max-order caps "
            f"{s20.get('capped_by_max_order_value', 0)}; below-min {s20.get('below_min_trade', 0)}."
        )
        if drag > 50 and adv_caps == 0:
            lines.append(
                "- High cash drag, few ADV caps → likely **5B scan-size basis / under-deployment**, not liquidity."
            )
        elif drag > 50 and adv_caps > 0:
            lines.append("- High cash drag + ADV caps → likely **liquidity/capacity constraint**.")
        if ref and s20.get("return_pct", 0) < ref.get("return_pct", 0) - 1.0:
            lines.append(
                "- Underperformance vs 5B may reflect **capacity/liquidity or reference sizing**, not strategy deterioration."
            )
        if s20.get("reference_sizing_warning_text"):
            lines.append(f"- {s20['reference_sizing_warning_text']}")
    else:
        lines.append("- Account not run / no data.")

    lines.extend([
        "",
        "## S3 shadow (separate)",
        "- S3 max60 paper-shadow is **not** included in A3 P&L above. Use `s3-shadow summary`.",
        "",
    ])
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path
