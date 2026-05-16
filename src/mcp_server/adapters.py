"""Adapters over existing repo modules — no strategy/risk logic duplication."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yaml

from src.mcp_server.audit import file_mtime_iso, file_sha256, parquet_max_date, utc_now_iso
from src.mcp_server.config import PATHS, RULE_VERSION, STALE_DAYS
from src.mcp_server.permissions import MCPPermissions, load_permissions
from src.mcp_server.schemas import validate_order_intent
from src.regime.state_machine import LiquiditySignals, detect_regime, explain_regime
from src.trading.config import TradingConfig, load_live_trading_config, load_trading_config
from src.trading.models import OrderProposal, OrderSide, PortfolioState, Position, Signal
from src.trading.monitoring.kill_switch import evaluate_kill_switch, load_kill_switch
from src.trading.risk.engine import RiskContext, RiskEngine


def git_branch() -> Optional[str]:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(PATHS["ohlcv_panel"].parents[2]),
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=3,
        )
        return out.strip()
    except Exception:
        return None


def _days_since(iso: Optional[str]) -> Optional[float]:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds() / 86400
    except Exception:
        return None


def file_freshness(path: Path, max_days: float) -> Dict[str, Any]:
    mtime = file_mtime_iso(path)
    age = _days_since(mtime)
    stale = age is None or age > max_days
    try:
        rel = str(path.relative_to(PATHS["ohlcv_panel"].parents[2]))
    except ValueError:
        rel = str(path)
    return {
        "path": rel,
        "exists": path.exists(),
        "last_modified": mtime,
        "age_days": round(age, 2) if age is not None else None,
        "stale": stale,
        "max_age_days": max_days,
    }


def load_json_file(path: Path) -> Tuple[Dict[str, Any], Optional[str], bool]:
    if not path.exists():
        return {}, None, True
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        mtime = file_mtime_iso(path)
        return data if isinstance(data, dict) else {}, mtime, False
    except (OSError, json.JSONDecodeError):
        return {}, None, True


@lru_cache(maxsize=1)
def _ohlcv() -> pd.DataFrame:
    df = pd.read_parquet(PATHS["ohlcv_panel"])
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["symbol", "date"])
    med = df.groupby("symbol")["close"].median().median()
    if med < 500:
        for c in ("open", "high", "low", "close"):
            df[c] *= 1000
    df["_adv_vnd"] = df["close"] * df["volume"]
    return df


@lru_cache(maxsize=1)
def _sector_map() -> dict[str, str]:
    sm = pd.read_csv(PATHS["sector_map"])
    return dict(zip(sm["symbol"], sm["primary_sector"]))


def sym_ohlcv(ticker: str) -> Optional[pd.DataFrame]:
    df = _ohlcv()
    sd = df[df["symbol"] == ticker.upper()].reset_index(drop=True)
    return sd if len(sd) >= 20 else None


def strategy_registry() -> Dict[str, Any]:
    if not PATHS["strategy_registry"].exists():
        return {"version": "0", "strategies": {}}
    return yaml.safe_load(PATHS["strategy_registry"].read_text(encoding="utf-8")) or {}


def get_strategy_status(strategy_id: Optional[str] = None) -> Dict[str, Any]:
    reg = strategy_registry()
    strategies = reg.get("strategies", {})
    sid = (strategy_id or "UNKNOWN").upper()
    entry = strategies.get(strategy_id) or strategies.get(sid) or strategies.get("UNKNOWN", {})
    status = str(entry.get("status", "UNKNOWN"))
    capital = bool(entry.get("capital_allowed", False))
    if status in ("RESEARCH_ONLY", "DISCARDED", "UNKNOWN", "WATCHLIST_ONLY"):
        capital = False
    return {
        "strategy_id": strategy_id or "ALL",
        "status": status,
        "capital_allowed": capital,
        "paper_allowed": bool(entry.get("paper_allowed", False)),
        "source_config": entry.get("source_config"),
        "rule_version": reg.get("version", RULE_VERSION),
        "reason": entry.get("reason", ""),
    }


def data_health_snapshot() -> Dict[str, Any]:
    issues: List[str] = []
    stale_inputs: List[str] = []
    checks = {}

    for key, path in (
        ("ohlcv", PATHS["ohlcv_panel"]),
        ("vnindex", PATHS["vnindex"]),
        ("fa_annual", PATHS["fa_annual"]),
        ("fa_quarterly", PATHS["fa_quarterly"]),
    ):
        if not path.exists():
            issues.append(f"missing:{key}")
            checks[key] = {"exists": False}
        else:
            checks[key] = {
                "exists": True,
                "latest_date": parquet_max_date(path),
                "hash": file_sha256(path),
            }

    for key, path, days in (
        ("manual_inputs", PATHS["manual_inputs"], STALE_DAYS["manual_inputs"]),
        ("consensus_pack", PATHS["consensus_pack"], STALE_DAYS["consensus_pack"]),
        ("research_pack", PATHS["research_pack"], STALE_DAYS["research_pack"]),
        ("paper_broker", PATHS["paper_broker_state"], STALE_DAYS["paper_broker"]),
    ):
        fr = file_freshness(path, days)
        checks[key] = fr
        if not fr["exists"]:
            issues.append(f"missing:{key}")
        elif fr["stale"]:
            stale_inputs.append(key)
            issues.append(f"stale:{key}")

    status = "OK"
    if any("missing:ohlcv" in i or "missing:vnindex" in i for i in issues):
        status = "CRITICAL"
    elif issues:
        status = "WARN"

    return {
        "status": status,
        "issues": issues,
        "stale_inputs": stale_inputs,
        "checks": checks,
        "recommended_action": "refresh_data" if status != "OK" else "none",
        "rule_version": RULE_VERSION,
    }


def system_status() -> Dict[str, Any]:
    perms = load_permissions()
    dh = data_health_snapshot()
    council, _, _ = load_json_file(PATHS["council_output"])
    alloc, _, _ = load_json_file(PATHS["allocation_plan"])
    ks, _, _ = load_json_file(PATHS["kill_switch_status"])
    regime, _, _ = load_json_file(PATHS["regime_state"])

    return {
        "repo": "VN Agent System",
        "git_branch": git_branch(),
        "latest_dates": {
            "ohlcv": parquet_max_date(PATHS["ohlcv_panel"]),
            "vnindex": parquet_max_date(PATHS["vnindex"]),
            "fundamentals_annual": parquet_max_date(PATHS["fa_annual"]),
            "manual_inputs_mtime": file_mtime_iso(PATHS["manual_inputs"]),
            "consensus_pack_mtime": file_mtime_iso(PATHS["consensus_pack"]),
            "research_pack_mtime": file_mtime_iso(PATHS["research_pack"]),
        },
        "council_output_timestamp": council.get("meeting_id") or file_mtime_iso(PATHS["council_output"]),
        "allocation_plan_asof": alloc.get("asof_date"),
        "regime": regime.get("regime"),
        "kill_switch_status": ks.get("status", "CLEAR"),
        "permissions": perms.to_dict(),
        "data_health_status": dh["status"],
        "rule_version": RULE_VERSION,
    }


def regime_snapshot(asof: str = "") -> Dict[str, Any]:
    state, mtime, missing = load_json_file(PATHS["regime_state"])
    manual, _, _ = load_json_file(PATHS["manual_inputs"])
    gl = state.get("global_liquidity", "unknown")
    vl = state.get("vn_liquidity", "unknown")
    regime = state.get("regime") or detect_regime(
        LiquiditySignals(gl if gl in ("easing", "tight") else "unknown", vl if vl in ("easing", "tight") else "unknown")
    )
    dist = manual.get("dist_days") or manual.get("distribution_days")
    no_new = bool(manual.get("no_new_buys", False))
    return {
        "asof": asof or state.get("asof_date") or "",
        "regime": regime,
        "explanation": explain_regime(regime),
        "global_liquidity": gl,
        "vn_liquidity": vl,
        "distribution_days": dist,
        "new_buy_allowed": not no_new,
        "T1_allowed": not no_new and regime in ("A", "B"),
        "T2_allowed": regime in ("A", "B"),
        "reasons": [explain_regime(regime)],
        "stale": missing or file_freshness(PATHS["regime_state"], 14)["stale"],
        "source_paths": [str(PATHS["regime_state"])],
        "source_hashes": {str(PATHS["regime_state"]): file_sha256(PATHS["regime_state"])},
        "rule_version": RULE_VERSION,
    }


def council_snapshot(asof: str = "") -> Dict[str, Any]:
    data, mtime, missing = load_json_file(PATHS["council_output"])
    fr = file_freshness(PATHS["council_output"], STALE_DAYS["council_output"])
    return {
        "asof": asof,
        "top_actions": [data.get("chair_decision", data.get("final_recommendation", ""))][:3],
        "top_risks": data.get("conflicts", []),
        "decision_stance": data.get("final_recommendation", ""),
        "constraints": {
            "mechanically_executable": data.get("mechanically_executable"),
            "guardrail_violations": data.get("guardrail_violations", []),
        },
        "timestamp": mtime,
        "stale": fr["stale"] or missing,
        "source_path": str(PATHS["council_output"]),
        "source_hash": file_sha256(PATHS["council_output"]),
    }


def allocation_plan_snapshot(asof: str = "") -> Dict[str, Any]:
    data, mtime, missing = load_json_file(PATHS["allocation_plan"])
    alloc = data.get("allocation", {})
    constraints = alloc.get("constraints", {})
    fr = file_freshness(PATHS["allocation_plan"], STALE_DAYS["allocation_plan"])
    gross = alloc.get("gross_exposure")
    cash = alloc.get("cash_weight")
    return {
        "asof": data.get("asof_date") or asof,
        "regime": data.get("regime"),
        "target_allocation": {"gross_exposure": gross, "cash_weight": cash},
        "allowed_exposure": gross,
        "new_buy_capacity": max(0.0, (gross or 0) - 0) if gross is not None else None,
        "sector_limits": {"max_sector_weight": constraints.get("max_sector_weight")},
        "position_limits": {"max_single_position": constraints.get("max_single_position")},
        "timestamp": mtime,
        "stale": fr["stale"] or missing,
        "source_path": str(PATHS["allocation_plan"]),
        "source_hash": file_sha256(PATHS["allocation_plan"]),
    }


def portfolio_snapshot(asof: str = "") -> Dict[str, Any]:
    state, mtime, missing = load_json_file(PATHS["paper_broker_state"])
    positions = state.get("positions") or {}
    cash = float(state.get("cash_vnd", 0) or 0)
    equity = float(state.get("equity_vnd", 0) or cash)
    pos_list = []
    sector_exp: Dict[str, float] = {}
    smap = _sector_map()
    for sym, p in positions.items():
        if not isinstance(p, dict):
            continue
        w = float(p.get("weight_pct", 0))
        sec = smap.get(sym, "Other")
        sector_exp[sec] = sector_exp.get(sec, 0) + w
        pos_list.append({"symbol": sym, "weight_pct": w, "sector": sec})
    largest = max(pos_list, key=lambda x: x["weight_pct"], default=None)
    return {
        "asof": asof,
        "account_equity": equity,
        "cash": cash,
        "gross_exposure": sum(sector_exp.values()),
        "open_positions_count": len(pos_list),
        "positions_summary": pos_list[:20],
        "sector_exposure": sector_exp,
        "largest_position": largest,
        "drawdown": state.get("drawdown"),
        "stale": file_freshness(PATHS["paper_broker_state"], STALE_DAYS["paper_broker"])["stale"] or missing,
        "source_path": str(PATHS["paper_broker_state"]),
        "source_hash": file_sha256(PATHS["paper_broker_state"]),
    }


def manual_input_status() -> Dict[str, Any]:
    out = {}
    for key, path, council, weekly in (
        ("manual_inputs", PATHS["manual_inputs"], True, True),
        ("consensus_pack", PATHS["consensus_pack"], True, True),
        ("research_engine_pack", PATHS["research_pack"], True, True),
    ):
        data, mtime, missing = load_json_file(path)
        fr = file_freshness(path, STALE_DAYS.get(key.replace("_pack", "").replace("research_engine", "research"), 14))
        out[key] = {
            "exists": path.exists(),
            "last_modified": mtime,
            "asof": data.get("asof") or data.get("asof_date"),
            "stale": fr["stale"] or missing,
            "required_for_weekly": weekly,
            "required_for_council": council,
            "recommended_action": "update_file" if fr["stale"] or missing else "ok",
        }
    return out


def calculate_position_size(order_intent: Dict[str, Any]) -> Dict[str, Any]:
    entry = float(order_intent["entry_price"])
    stop = float(order_intent["stop_price"])
    equity = float(order_intent["account_equity"])
    risk_pct = float(order_intent.get("risk_pct", 0.01))
    adv = float(order_intent.get("adv50_vnd", 0))
    cap = float(order_intent.get("participation_cap", 0.05))
    side = order_intent["side"]

    if side == "BUY":
        risk_per_share = entry - stop
    else:
        risk_per_share = stop - entry

    if risk_per_share <= 0:
        return {
            "allowed": False,
            "invalid_reason": "invalid_stop_distance",
            "risk_per_share": risk_per_share,
        }
    if adv <= 0:
        return {"allowed": False, "invalid_reason": "adv50_missing", "risk_per_share": risk_per_share}

    max_risk_vnd = equity * risk_pct
    shares_by_risk = int(max_risk_vnd // risk_per_share)
    shares_by_adv = int((adv * cap) // entry) if entry > 0 else 0
    shares_by_cash = int(equity // entry) if entry > 0 else 0
    final = max(0, min(shares_by_risk, shares_by_adv, shares_by_cash))
    limiting = "risk"
    if final == shares_by_adv:
        limiting = "adv_participation"
    elif final == shares_by_cash:
        limiting = "cash"

    return {
        "allowed": final > 0,
        "risk_per_share": risk_per_share,
        "max_risk_vnd": max_risk_vnd,
        "shares_by_risk": shares_by_risk,
        "shares_by_adv": shares_by_adv,
        "shares_by_cash": shares_by_cash,
        "final_shares": final,
        "final_notional": final * entry,
        "limiting_factor": limiting,
        "invalid_reason": None if final > 0 else "zero_shares",
    }


def evaluate_kill_switch_snapshot(asof: str = "") -> Dict[str, Any]:
    lcfg = load_live_trading_config()
    dh = data_health_snapshot()
    data_health_for_ks = {
        "status": "CRITICAL_FAIL" if dh["status"] == "CRITICAL" else "OK",
        "checks": [],
        "BLOCK_ORDER_GENERATION": dh["status"] == "CRITICAL",
    }
    ks = evaluate_kill_switch(lcfg, data_health_for_ks, {}, {})
    stored = load_kill_switch(lcfg)
    return {
        "asof": asof,
        "kill_switch_status": ks.status,
        "data_health_status": dh["status"],
        "reconciliation_status": "unknown",
        "block_new_orders": ks.status == "BLOCK",
        "block_adds": ks.status in ("BLOCK", "WARN"),
        "block_live_execution": True,
        "reasons": ks.reasons,
        "source_paths": [str(PATHS["kill_switch_status"]), str(PATHS["live_trading_yaml"])],
        "rule_version": RULE_VERSION,
        "stored_status": stored.get("status"),
    }


def _legacy_enforcer_checks(sym: str, pct: float, state: Dict[str, Any]) -> List[str]:
    """Preserve original mcp_quant_engine hard limits as additional checks."""
    blocks: List[str] = []
    equity = float(state.get("equity_vnd", 0) or state.get("cash_vnd", 0) or 1e9)
    pos = state.get("positions") or {}
    if pct > 8.0:
        blocks.append("SIZE_EXCEEDED:>8pct")
    if len(pos) >= 20 and sym not in pos:
        blocks.append("MAX_POSITIONS:20")
    smap = _sector_map()
    sector = smap.get(sym, "Other")
    sector_pct = sum(
        float(v.get("weight_pct", 0))
        for k, v in pos.items()
        if isinstance(v, dict) and smap.get(k, "Other") == sector
    )
    if sector_pct + pct > 30.0:
        blocks.append("SECTOR_CONCENTRATION:>30pct")
    sd = sym_ohlcv(sym)
    if sd is not None and len(sd) >= 50:
        adv50 = float(sd["_adv_vnd"].iloc[-50:].mean())
        impact = (equity * pct / 100) / adv50 * 100 if adv50 > 0 else 999
        if impact > 5.0:
            blocks.append("LIQUIDITY:>5pct_ADV50")
    return blocks


def enforce_portfolio_constraints_impl(
    order_intent: Optional[Dict[str, Any]] = None,
    ticker: str = "",
    proposed_size_pct: float = 0.0,
) -> Dict[str, Any]:
    perms = load_permissions()
    checks: List[Dict[str, Any]] = []
    hard_blocks: List[str] = []

    # Determine whether this action represents NEW BUY EXPOSURE.
    # Read-only callers (no order_intent and no ticker) are not gated on
    # stale Council / consensus / research packs.
    side_buy = False
    if order_intent and str(order_intent.get("side", "")).upper() == "BUY":
        side_buy = True
    if ticker and proposed_size_pct > 0:
        side_buy = True
    new_buy = side_buy

    if perms.live_execution_allowed():
        hard_blocks.append("live_enabled_requires_human_approval_file")
    if not perms.paper_trading_enabled and (order_intent or ticker):
        hard_blocks.append("paper_trading_disabled")

    dh = data_health_snapshot()
    if dh["status"] == "CRITICAL":
        hard_blocks.append("data_health_critical")
        checks.append({"check": "data_health", "passed": False, "level": "CRITICAL"})

    ks = evaluate_kill_switch_snapshot()
    if ks["kill_switch_status"] == "BLOCK":
        hard_blocks.append("kill_switch_block")
        checks.append({"check": "kill_switch", "passed": False})

    council = council_snapshot()
    if council.get("stale"):
        checks.append({"check": "council_output", "passed": False, "warn": "stale"})
        if new_buy:
            hard_blocks.append("stale_council_output")
    stance = str(council.get("decision_stance", "")).lower()
    if "no new" in stance or "no_new" in stance:
        hard_blocks.append("council_blocks_new_exposure")

    manual = manual_input_status()
    if manual.get("manual_inputs", {}).get("stale"):
        hard_blocks.append("stale_manual_inputs")

    # Stale / missing consensus pack and research engine pack are advisory for
    # read-only callers but a HARD BLOCK on any new BUY exposure.
    consensus = manual.get("consensus_pack", {})
    if consensus.get("stale"):
        checks.append({"check": "consensus_pack", "passed": False, "warn": "stale_or_missing"})
        if new_buy and consensus.get("required_for_council"):
            hard_blocks.append("stale_or_missing_consensus_pack")
    research = manual.get("research_engine_pack", {})
    if research.get("stale"):
        checks.append({"check": "research_engine_pack", "passed": False, "warn": "stale_or_missing"})
        if new_buy and research.get("required_for_council"):
            hard_blocks.append("stale_or_missing_research_pack")

    if order_intent:
        st = get_strategy_status(order_intent.get("strategy_id"))
        if not st["capital_allowed"] and order_intent.get("side") == "BUY":
            hard_blocks.append(f"strategy_status:{st['status']}")
        checks.append({"check": "strategy_status", "passed": st["capital_allowed"], "status": st["status"]})

        valid, normalized, schema_errors = validate_order_intent(order_intent)
        if not valid:
            hard_blocks.append("schema_invalid")
            return {
                "allowed": False,
                "final_permission_state": perms.max_permission,
                "checks": checks,
                "hard_block_reason": ";".join(hard_blocks + schema_errors),
                "schema_errors": schema_errors,
                "required_human_approval": perms.human_approval_required,
                "rule_versions": {"mcp": RULE_VERSION},
            }
        order_intent = normalized

        sizing = calculate_position_size(order_intent)
        if not sizing.get("allowed"):
            hard_blocks.append(sizing.get("invalid_reason", "sizing_failed"))

        sym = order_intent["symbol"]
        pct = (sizing.get("final_notional", 0) / order_intent["account_equity"] * 100) if order_intent["account_equity"] else 0
        state, _, _ = load_json_file(PATHS["paper_broker_state"])
        hard_blocks.extend(_legacy_enforcer_checks(sym, pct, state))

        tcfg = load_trading_config()
        proposal = OrderProposal(
            signal=Signal(
                strategy=order_intent["strategy_id"],
                symbol=sym,
                side=order_intent["side"],
                asof_date=order_intent.get("asof") or utc_now_iso()[:10],
                intended_price=order_intent["entry_price"],
                quantity=int(sizing.get("final_shares", 0)),
                metadata=order_intent.get("metadata") or {},
            ),
            adv50_vnd=order_intent.get("adv50_vnd", 0),
            nav_vnd=order_intent["account_equity"],
        )
        portfolio = PortfolioState(
            asof_date=proposal.signal.asof_date,
            nav_vnd=order_intent["account_equity"],
            cash_vnd=float(state.get("cash_vnd", 0)),
            positions=[
                Position(
                    symbol=k,
                    quantity=int(v.get("quantity", 0)),
                    avg_price=float(v.get("avg_price", 0)),
                    market_value_vnd=float(v.get("market_value_vnd", 0)),
                )
                for k, v in (state.get("positions") or {}).items()
                if isinstance(v, dict)
            ],
        )
        engine = RiskEngine(tcfg)
        lcfg = load_live_trading_config()
        extra = {"data_health": {"status": dh["status"]}, "kill_switch": ks, "reconciliation": {}}
        verdict = engine.evaluate(proposal, RiskContext(portfolio=portfolio), lcfg, extra)
        if not verdict.passed:
            hard_blocks.extend(verdict.reasons)
        checks.append({"check": "risk_engine", "passed": verdict.passed, "rule_ids": verdict.rule_ids})
    elif ticker:
        sym = ticker.upper()
        state, _, _ = load_json_file(PATHS["paper_broker_state"])
        hard_blocks.extend(_legacy_enforcer_checks(sym, proposed_size_pct, state))
        st = get_strategy_status()
        checks.append({"check": "legacy_ticker_mode", "passed": len(hard_blocks) == 0})

    allowed = len(hard_blocks) == 0
    return {
        "allowed": allowed,
        "final_permission_state": perms.max_permission,
        "checks": checks,
        "hard_block_reason": ";".join(hard_blocks) if hard_blocks else None,
        "recommended_action": "proceed_paper" if allowed else "blocked",
        "normalized_order_intent": order_intent,
        "required_human_approval": perms.human_approval_required or not allowed,
        "source_paths": [str(PATHS["council_output"]), str(PATHS["allocation_plan"]), str(PATHS["paper_broker_state"])],
        "source_hashes": {
            str(PATHS["council_output"]): file_sha256(PATHS["council_output"]),
            str(PATHS["allocation_plan"]): file_sha256(PATHS["allocation_plan"]),
        },
        "rule_versions": {"mcp": RULE_VERSION, "risk_engine": "src.trading.risk.engine"},
    }


def _atr(sd: pd.DataFrame, period: int = 14) -> float:
    h, l, c = sd["high"].values, sd["low"].values, sd["close"].values
    tr = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
    return float(np.mean(tr[-period:])) if len(tr) >= period else float(np.mean(tr))


def screen_symbol(ticker: str) -> Dict[str, Any]:
    sym = ticker.upper()
    sd = sym_ohlcv(sym)
    st = get_strategy_status("A3_DP")
    if sd is None:
        return {
            "symbol": sym,
            "setup_status": "no_data",
            "blocked_reason": "insufficient_ohlcv",
            "capital_allowed": False,
            "paper_allowed": st["paper_allowed"],
            "source_path": str(PATHS["ohlcv_panel"]),
            "source_hash": file_sha256(PATHS["ohlcv_panel"]),
            "rule_version": RULE_VERSION,
        }
    n = len(sd)
    close, vol, high, low = sd["close"].values, sd["volume"].values, sd["high"].values, sd["low"].values
    price = float(close[-1])
    adv50 = float(sd["_adv_vnd"].iloc[-50:].mean()) if n >= 50 else float(sd["_adv_vnd"].mean())
    signals = []
    if n >= 11:
        diffs = np.diff(close[-11:])
        dn_vols = vol[-10:][diffs < 0]
        if len(dn_vols) and vol[-1] > float(np.max(dn_vols)) and close[-1] > close[-2]:
            signals.append("PocketPivot")
    if n >= 5 and (np.max(close[-5:]) / np.min(close[-5:]) - 1) * 100 < 1.5:
        signals.append("TightCloses")
    score = len(signals)
    return {
        "symbol": sym,
        "setup_type": "technical_combo",
        "setup_status": "candidate" if signals else "none",
        "score": score,
        "liquidity_summary": {"adv50_vnd": adv50},
        "signal_summary": signals,
        "capital_allowed": st["capital_allowed"] and bool(signals),
        "paper_allowed": st["paper_allowed"],
        "blocked_reason": None if signals else "no_setup",
        "source_path": str(PATHS["ohlcv_panel"]),
        "source_hash": file_sha256(PATHS["ohlcv_panel"]),
        "rule_version": RULE_VERSION,
    }


def signal_evidence(symbol: str, strategy_id: str = "A3_DP", asof: str = "") -> Dict[str, Any]:
    sym = symbol.upper()
    sd = sym_ohlcv(sym)
    stale = not PATHS["ohlcv_panel"].exists()
    if sd is None:
        return {"symbol": sym, "stale": True, "missing_fields": ["ohlcv"], "strategy_id": strategy_id}
    close = sd["close"].values
    n = len(close)
    ema21 = float(pd.Series(close).ewm(span=21).mean().iloc[-1]) if n >= 21 else None
    ema50 = float(np.mean(close[-50:])) if n >= 50 else None
    adv50 = float(sd["_adv_vnd"].iloc[-50:].mean()) if n >= 50 else None
    vol_ratio = float(sd["volume"].iloc[-1] / sd["volume"].iloc[-50:].mean()) if n >= 50 else None
    return {
        "symbol": sym,
        "asof": asof or str(sd["date"].iloc[-1].date()),
        "close": float(close[-1]),
        "ema21": ema21,
        "ema50": ema50,
        "adv50_vnd": adv50,
        "volume_vs_avg": vol_ratio,
        "breakout_status": "unknown",
        "stop_level": None,
        "entry_level": float(close[-1]),
        "setup_phase": screen_symbol(sym).get("setup_status"),
        "stale": stale,
        "source_path": str(PATHS["ohlcv_panel"]),
        "source_hash": file_sha256(PATHS["ohlcv_panel"]),
        "rule_version": RULE_VERSION,
        "strategy_id": strategy_id,
    }


def evaluate_moat(symbol: str) -> Dict[str, Any]:
    sym = symbol.upper()
    fa = pd.read_parquet(PATHS["fa_annual"]) if PATHS["fa_annual"].exists() else pd.DataFrame()
    sd = fa[fa["symbol"] == sym] if not fa.empty else fa
    missing = []
    if sd.empty:
        return {"symbol": sym, "moat_score": None, "missing_fields": ["fa_annual"], "source_path": str(PATHS["fa_annual"])}
    rev_col = "financialValues_TotalRevenue"
    annual = sd.sort_values("year").tail(6)
    rev = pd.to_numeric(annual.get(rev_col, pd.Series(dtype=float)), errors="coerce").dropna().values
    rev_cagr = ((rev[-1] / rev[0]) ** (1 / max(len(rev) - 1, 1)) - 1) * 100 if len(rev) >= 2 and rev[0] > 0 else None
    if rev_cagr is None:
        missing.append("revenue_growth")
    return {
        "symbol": sym,
        "revenue_growth_yoy_proxy": rev_cagr,
        "moat_score": "moderate" if rev_cagr and rev_cagr > 10 else "weak",
        "missing_fields": missing,
        "source_path": str(PATHS["fa_annual"]),
        "source_hash": file_sha256(PATHS["fa_annual"]),
        "rule_version": RULE_VERSION,
    }


def write_decision_log_impl(payload: Dict[str, Any]) -> Dict[str, Any]:
    from src.mcp_server.schemas import validate_decision_payload

    valid, missing = validate_decision_payload(payload)
    if not valid:
        return {"ok": False, "error_code": "SCHEMA_INVALID", "missing": missing}
    log_dir = PATHS["mcp_decision_log_dir"]
    sym = payload.get("symbol", "NA")
    ts = payload.get("created_at", utc_now_iso()).replace(":", "").replace("-", "")[:15]
    path = log_dir / f"{ts}_{sym}.json"
    from src.mcp_server.audit import atomic_write_json

    try:
        atomic_write_json(path, payload)
        return {"ok": True, "decision_log_path": str(path.relative_to(PATHS["ohlcv_panel"].parents[2]))}
    except OSError as e:
        return {"ok": False, "error_code": "LOG_WRITE_FAILED", "message": str(e)}


def recent_decision_logs(limit: int = 10) -> List[Dict[str, Any]]:
    log_dir = PATHS["mcp_decision_log_dir"]
    if not log_dir.exists():
        return []
    files = sorted(log_dir.glob("*.json"), reverse=True)[:limit]
    out = []
    for p in files:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            out.append(
                {
                    "path": str(p.name),
                    "symbol": d.get("symbol"),
                    "final_decision": d.get("final_decision"),
                    "created_at": d.get("created_at"),
                    "tool_name": d.get("tool_name"),
                }
            )
        except (OSError, json.JSONDecodeError):
            continue
    return out


def run_isolated_backtest_impl(strategy_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    supported = {"mean_reversion_252d", "ma_crossover", "breakout_52w"}
    if strategy_name not in supported:
        return {"error": f"unsupported strategy {strategy_name}"}
    df = _ohlcv()
    top_n = int(params.get("top_n", 10))
    cost = float(params.get("cost_bp", 50)) / 10000
    universe = [s.upper() for s in params.get("universe", [])]
    if not universe:
        last = df["date"].max()
        adv = df[df["date"] == last].set_index("symbol")["_adv_vnd"]
        universe = list(adv[adv >= 2e9].index)

    def _score_mean_rev(sym: str) -> Optional[float]:
        c = df[df["symbol"] == sym]["close"].values
        return -(c[-1] / c[-252] - 1) if len(c) >= 252 else None

    def _score_ma(sym: str) -> Optional[float]:
        c = df[df["symbol"] == sym]["close"].values
        return np.mean(c[-50:]) / np.mean(c[-200:]) - 1 if len(c) >= 200 else None

    def _score_bo(sym: str) -> Optional[float]:
        sd = df[df["symbol"] == sym]
        c, h = sd["close"].values, sd["high"].values
        return c[-1] / np.max(h[-min(252, len(h)):]) - 1 if len(c) >= 60 else None

    fns = {
        "mean_reversion_252d": _score_mean_rev,
        "ma_crossover": _score_ma,
        "breakout_52w": _score_bo,
    }
    scored = [(s, fns[strategy_name](s)) for s in universe]
    scored = [(s, sc) for s, sc in scored if sc is not None]
    if not scored:
        return {"error": "no scoreable symbols"}
    reverse = strategy_name == "mean_reversion_252d"
    scored.sort(key=lambda x: x[1], reverse=reverse)
    portfolio = [s for s, _ in scored[:top_n]]
    fwd = []
    for sym in portfolio:
        c = df[df["symbol"] == sym]["close"].values
        h = min(63, len(c) - 1)
        if h >= 5:
            fwd.append((c[-1] / c[-(h + 1)] - 1) * 100 - cost * 100)
    if not fwd:
        return {"error": "insufficient forward data"}
    return {
        "strategy": strategy_name,
        "top_n": top_n,
        "universe_size": len(universe),
        "portfolio": portfolio[:5],
        "is_63d_mean_ret_pct": round(float(np.mean(fwd)), 2),
        "hit_rate_pct": round(float(np.mean([r > 0 for r in fwd]) * 100), 1),
        "note": "IS estimate only — not OOS",
        "rule_version": RULE_VERSION,
    }


def propose_order_intent_impl(symbol: str, strategy_id: str, side: str, asof: str = "") -> Dict[str, Any]:
    ev = signal_evidence(symbol, strategy_id, asof)
    st = get_strategy_status(strategy_id)
    regime = regime_snapshot(asof)
    council = council_snapshot(asof)
    alloc = allocation_plan_snapshot(asof)
    port = portfolio_snapshot(asof)
    intent = {
        "symbol": symbol.upper(),
        "side": side.upper(),
        "strategy_id": strategy_id,
        "setup_type": "proposed",
        "entry_price": ev.get("entry_level") or ev.get("close"),
        "stop_price": (ev.get("entry_level") or ev.get("close", 0)) * 0.93,
        "account_equity": port.get("account_equity") or 1e9,
        "adv50_vnd": ev.get("adv50_vnd") or 0,
        "asof": asof or ev.get("asof", ""),
    }
    sizing = calculate_position_size(intent) if intent.get("adv50_vnd") else {"allowed": False}
    intent["quantity"] = sizing.get("final_shares", 0)
    enf = enforce_portfolio_constraints_impl(order_intent=intent)
    blocked = enf.get("hard_block_reason") or (not st["capital_allowed"] and side.upper() == "BUY")
    return {
        "proposed_order_intent": intent,
        "risk_result": sizing,
        "enforcement": enf,
        "regime_snapshot": regime,
        "council_snapshot": council,
        "allocation_snapshot": alloc,
        "final_decision": "blocked" if blocked else "proposed",
        "blocked_reason": blocked,
        "recommended_action": enf.get("recommended_action"),
    }
