"""Convert daily scan CSV to order intents (adapter only — no strategy recompute)."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from src.trading.config import LiveTradingConfig
from src.trading.live.paper_ledger import PaperLedger
from src.trading.live.row_hash import compute_row_hash, make_manual_review_key
from src.trading.live.scan_resolver import ScanResolveResult, resolve_scan
from src.trading.live.s3_flag import s3_shadow_block_reason
from src.trading.live.sizing_policy import _empty_attribution, apply_execution_sizing
from src.trading.models import OrderProposal, OrderSide, Signal

# final_action -> (action, tier, side, tradeable)
ACTION_MAP = {
    "NEW_T1": ("BUY_T1", "T1", "BUY", True),
    "NEW_T1_MANUAL_REVIEW_BREADTH": ("BUY_T1_MANUAL_REVIEW", "T1", "BUY", True),
    "ADD_T2": ("BUY_T2", "T2", "BUY", True),
    "WAIT_PB": ("WATCH_ONLY", "WATCH", "", False),
    "HOLD_T1_ONLY": ("WATCH_ONLY", "WATCH", "", False),
    "NO_T2_BREADTH": ("WATCH_ONLY", "WATCH", "", False),
    "SKIP_LIQUIDITY": ("SKIP_LIQUIDITY", "WATCH", "", False),
    "SKIP_VNINDEX_BEAR": ("SKIP_VNINDEX_BEAR", "WATCH", "", False),
    "WATCH_ONLY": ("WATCH_ONLY", "WATCH", "", False),
    "TP1_PARTIAL": ("SELL_TP1", "EXIT", "SELL", True),
    "TRAIL_EXIT": ("SELL_EXIT", "EXIT", "SELL", True),
    "MAX_HOLD_EXIT": ("SELL_EXIT", "EXIT", "SELL", True),
}

CAPITAL_FINAL_ACTIONS = frozenset({
    "NEW_T1", "NEW_T1_MANUAL_REVIEW_BREADTH", "ADD_T2",
    "TP1_PARTIAL", "TRAIL_EXIT", "MAX_HOLD_EXIT",
})

INTENT_COLS = [
    "order_intent_id", "date", "symbol", "side", "action", "strategy", "tier",
    "quantity_estimate", "value_VND", "limit_price", "reason_code", "risk_flags",
    "requires_manual_review", "approved", "rejected", "approval_stale", "broker_order_id",
    "source_scan_file", "source_scan_row_id", "intent_sequence", "breadth_zone", "sector_l4",
    "pts_tag", "s3_tag", "macro_tag", "afl_tag", "adv50_B_VND", "strategy_classification",
    "s3_shadow_action", "s3_no_real_order_flag", "s3_shadow_blocked_reason",
    "account_id", "scan_value_VND", "execution_value_VND", "sizing_policy",
    "sizing_adjustment_reason", "capped_by_max_order_value", "capped_by_cash",
    "capped_by_adv_liquidity", "capped_by_scan_value", "manual_review_key", "scan_hash", "row_hash",
]

_S3_SHADOW_ACTIONS = {"PAPER_S3_SHADOW", "PAPER_S3_RESEARCH_MONITOR"}


def make_order_intent_id(
    asof_date: str,
    symbol: str,
    action: str,
    source_scan_row_id: Any,
    final_action: str = "",
) -> str:
    """Deterministic intent id for stable manual-review queue keys."""
    raw = f"{asof_date}|{symbol}|{action}|{final_action}|{source_scan_row_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def _effective_t1_vnd(row: pd.Series, participation: float) -> float:
    target_m = float(row.get("target_T1_M") or 0)
    target_vnd = target_m * 1_000_000
    adv_b = float(row.get("adv50_B_VND") or 0)
    adv_vnd = adv_b * 1_000_000_000
    cap = adv_vnd * participation
    max_10 = float(row.get("max_10pct_M") or 0) * 1_000_000
    if max_10 > 0:
        cap = min(cap, max_10) if cap > 0 else max_10
    if cap <= 0:
        return target_vnd
    return min(target_vnd, cap)


def _exit_price(row: pd.Series, final_action: str) -> float:
    """Use scan-provided prices only; fallback to close_kVND."""
    close_kvnd = float(row.get("close_kVND") or 0)
    close_vnd = close_kvnd * 1000
    if final_action == "TP1_PARTIAL":
        tp1 = row.get("tp1_price")
        if tp1 is not None and not (isinstance(tp1, float) and pd.isna(tp1)) and float(tp1) > 0:
            return float(tp1) * 1000 if float(tp1) < 10000 else float(tp1)
    if final_action == "TRAIL_EXIT":
        trail = row.get("trail_price")
        if trail is not None and not (isinstance(trail, float) and pd.isna(trail)) and float(trail) > 0:
            return float(trail) * 1000 if float(trail) < 10000 else float(trail)
    return close_vnd


def _sell_quantity(
    action: str,
    ledger: Optional[PaperLedger],
    symbol: str,
    row: pd.Series,
) -> tuple[int, str]:
    """Return (qty, skip_reason). OMS does not compute TP1 % — uses ledger position."""
    if ledger is None:
        return 0, "SKIP_NO_POSITION"
    qty_open = ledger.get_a3_position_qty(symbol)
    if qty_open <= 0:
        return 0, "SKIP_NO_POSITION"
    scan_qty = row.get("exit_quantity") or row.get("quantity_estimate")
    if scan_qty is not None and not (isinstance(scan_qty, float) and pd.isna(scan_qty)):
        try:
            q = int(float(scan_qty))
            if q > 0:
                return min(q, qty_open), ""
        except (TypeError, ValueError):
            pass
    if action == "SELL_TP1":
        return max(1, qty_open // 2), ""
    return qty_open, ""


def build_order_intents(
    config: LiveTradingConfig,
    asof_date: str,
    health_status: Dict[str, Any],
    scan_path: Optional[Path] = None,
    scan_resolve: Optional[ScanResolveResult] = None,
    ledger: Optional[PaperLedger] = None,
    latest_panel_date: str = "",
    *,
    test_mode: bool = False,
) -> pd.DataFrame:
    if health_status.get("BLOCK_ORDER_GENERATION"):
        return pd.DataFrame(columns=INTENT_COLS)

    if scan_resolve is None:
        scan_resolve = resolve_scan(
            config, asof_date, cli_scan_path=scan_path, test_mode=test_mode
        )
    if scan_resolve.blocked:
        return pd.DataFrame(columns=INTENT_COLS)

    path = scan_resolve.path
    if not path.exists():
        return pd.DataFrame(columns=INTENT_COLS)

    scan_hash = scan_resolve.scan_hash or ""

    scan = pd.read_csv(path)
    scan["as_of_date"] = pd.to_datetime(scan["as_of_date"]).dt.strftime("%Y-%m-%d")
    day = scan[scan["as_of_date"] == asof_date[:10]].copy()
    if day.empty:
        return pd.DataFrame(columns=INTENT_COLS)

    rows: List[Dict[str, Any]] = []
    intent_seq = 0

    for idx, row in day.iterrows():
        sym = str(row["symbol"]).upper()
        classification = str(row.get("strategy_classification", ""))
        final_action = str(row.get("final_action", "WATCH_ONLY"))

        pts_tag = "shadow" if "PTS" in classification else ""
        s3_tag = "research_only" if classification == "S3_RESEARCH_ONLY" or "S3" in classification else ""
        macro_tag = "pending_external_data"
        afl_tag = "visual_only"

        s3_shadow_action = str(row.get("s3_shadow_action", "")).strip()
        s3_research_action = str(row.get("s3_research_monitor_action", "")).strip()
        a3_active_in_row = bool(row.get("a3_active", False))
        if not a3_active_in_row:
            if s3_shadow_action in _S3_SHADOW_ACTIONS:
                block = s3_shadow_block_reason(row.get("s3_no_real_order_flag"))
                if block:
                    rows.append(_s3_blocked_row(
                        asof_date, sym, s3_shadow_action, row, path, idx, intent_seq, block, scan_hash, config
                    ))
                    intent_seq += 1
                    continue
                rows.append(_s3_shadow_row(asof_date, sym, s3_shadow_action, row, path, idx, intent_seq, scan_hash, config))
                intent_seq += 1
                continue
            if s3_research_action in _S3_SHADOW_ACTIONS:
                block = s3_shadow_block_reason(row.get("s3_no_real_order_flag"))
                if block:
                    rows.append(_s3_blocked_row(
                        asof_date, sym, s3_research_action, row, path, idx, intent_seq, block, scan_hash, config
                    ))
                    intent_seq += 1
                    continue
                rows.append(_s3_shadow_row(asof_date, sym, s3_research_action, row, path, idx, intent_seq, scan_hash, config))
                intent_seq += 1
                continue

        if classification == "S3_RESEARCH_ONLY" or (s3_tag and not config.allow_s3_capital):
            rows.append(_watch_row(asof_date, sym, "WATCH_S3_RESEARCH_ONLY", row, path, idx, intent_seq, s3_tag, macro_tag, afl_tag))
            intent_seq += 1
            continue

        if "PTS" in classification and not config.allow_pts_shadow:
            rows.append(_watch_row(asof_date, sym, "WATCH_PTS_SHADOW", row, path, idx, intent_seq, pts_tag, macro_tag, afl_tag))
            intent_seq += 1
            continue

        mapped = ACTION_MAP.get(final_action, ("WATCH_ONLY", "WATCH", "", False))
        action, tier, side, tradeable = mapped

        if final_action in CAPITAL_FINAL_ACTIONS and tradeable and classification != "A3_PRODUCTION":
            rows.append(_non_production_row(
                asof_date, sym, final_action, row, path, idx, intent_seq, classification, config, scan_hash
            ))
            intent_seq += 1
            continue

        if classification != "A3_PRODUCTION":
            if final_action == "WATCH_ONLY" or not tradeable:
                rows.append(_watch_row(asof_date, sym, "WATCH_ONLY", row, path, idx, intent_seq, pts_tag, s3_tag, macro_tag, afl_tag))
                intent_seq += 1
            continue

        if not bool(row.get("in_a3_universe", True)):
            continue

        liq = str(row.get("liq_warn_T1", "OK"))
        if liq == "CRITICAL" and side == "BUY":
            rows.append(_skip_row(asof_date, sym, "SKIP_LIQUIDITY", row, path, idx, intent_seq, liq, config, scan_hash))
            intent_seq += 1
            continue

        if final_action == "SKIP_VNINDEX_BEAR" or (
            config.require_regime_bull and side == "BUY" and not bool(row.get("regime_bull", True))
        ):
            rows.append(_skip_row(asof_date, sym, "SKIP_VNINDEX_BEAR", row, path, idx, intent_seq, "regime", config, scan_hash))
            intent_seq += 1
            continue

        requires_manual = final_action == "NEW_T1_MANUAL_REVIEW_BREADTH"
        risk_flags: List[str] = []
        if str(row.get("breadth_zone", "")) == "defense":
            risk_flags.append("breadth_defense")
        if str(row.get("sector_l4_stress_flag", "")) in ("WARN", "STRESS"):
            risk_flags.append("sector_l4_warning")

        if not tradeable:
            rows.append(_watch_row(asof_date, sym, action, row, path, idx, intent_seq, pts_tag, s3_tag, macro_tag, afl_tag))
            intent_seq += 1
            continue

        limit_price = _exit_price(row, final_action) if side == "SELL" else float(row.get("close_kVND") or 0) * 1000
        value_vnd = 0.0
        qty = 0
        cap_attr = _empty_attribution()

        if side == "SELL":
            qty, skip_reason = _sell_quantity(action, ledger, sym, row)
            if qty <= 0 or skip_reason:
                rows.append({
                    "order_intent_id": make_order_intent_id(
                        asof_date, sym, skip_reason or "RECON_REQUIRED", idx, final_action
                    ),
                    "date": asof_date,
                    "symbol": sym,
                    "side": "",
                    "action": skip_reason or "RECON_REQUIRED",
                    "strategy": config.production_strategy,
                    "tier": "WATCH",
                    "quantity_estimate": 0,
                    "value_VND": 0,
                    "limit_price": 0,
                    "reason_code": final_action,
                    "risk_flags": skip_reason,
                    "requires_manual_review": skip_reason == "RECON_REQUIRED",
                    "approved": False,
                    "broker_order_id": "",
                    "source_scan_file": str(path),
                    "source_scan_row_id": idx,
                    "intent_sequence": intent_seq,
                    "breadth_zone": row.get("breadth_zone", ""),
                    "sector_l4": row.get("sector_l4", ""),
                    "pts_tag": pts_tag,
                    "s3_tag": s3_tag,
                    "macro_tag": macro_tag,
                    "afl_tag": afl_tag,
                    "adv50_B_VND": float(row.get("adv50_B_VND") or 0),
                    "s3_shadow_action": "",
                    "s3_no_real_order_flag": False,
                })
                intent_seq += 1
                continue
            value_vnd = qty * limit_price
            scan_value_vnd = value_vnd
            execution_value_vnd = value_vnd
            sizing_policy = ""
            sizing_reason = ""
        else:
            scan_value_vnd = _effective_t1_vnd(row, config.adv_participation)
            execution_value_vnd, qty, sizing_policy, sizing_reason, cap_attr = apply_execution_sizing(
                config,
                scan_value_vnd,
                limit_price,
                side,
                row,
                ledger=ledger,
            )
            value_vnd = execution_value_vnd
            if sizing_reason == "below_min_trade_value":
                rows.append(_skip_row(
                    asof_date, sym, "SKIP_BELOW_MIN_TRADE_VALUE", row, path, idx, intent_seq,
                    sizing_reason, config, scan_hash,
                    scan_value_vnd=scan_value_vnd,
                    sizing_policy=sizing_policy,
                ))
                intent_seq += 1
                continue
            if sizing_reason == "scan_size_exceeds_cap":
                rows.append(_skip_row(
                    asof_date, sym, "SKIP_SCAN_SIZE_EXCEEDS_CAP", row, path, idx, intent_seq,
                    sizing_reason, config, scan_hash,
                    scan_value_vnd=scan_value_vnd,
                    sizing_policy=sizing_policy,
                ))
                intent_seq += 1
                continue

        if qty <= 0 or limit_price <= 0:
            rows.append(_watch_row(asof_date, sym, "WATCH_INVALID_SIZE", row, path, idx, intent_seq, pts_tag, s3_tag, macro_tag, afl_tag))
            intent_seq += 1
            continue

        intent_row = {
            "order_intent_id": make_order_intent_id(asof_date, sym, action, idx, final_action),
            "date": asof_date,
            "symbol": sym,
            "side": side,
            "action": action,
            "strategy": config.production_strategy,
            "tier": tier,
            "quantity_estimate": qty,
            "value_VND": value_vnd,
            "limit_price": limit_price,
            "reason_code": final_action,
            "risk_flags": "|".join(risk_flags),
            "requires_manual_review": requires_manual,
            "approved": False,
            "rejected": False,
            "approval_stale": False,
            "broker_order_id": "",
            "strategy_classification": classification,
            "source_scan_file": str(path),
            "source_scan_row_id": idx,
            "intent_sequence": intent_seq,
            "breadth_zone": row.get("breadth_zone", ""),
            "sector_l4": row.get("sector_l4", ""),
            "pts_tag": pts_tag,
            "s3_tag": s3_tag,
            "macro_tag": macro_tag,
            "afl_tag": afl_tag,
            "adv50_B_VND": float(row.get("adv50_B_VND") or 0),
            "s3_shadow_action": "",
            "s3_no_real_order_flag": False,
            "s3_shadow_blocked_reason": "",
            "account_id": getattr(config, "account_id", ""),
            "scan_value_VND": scan_value_vnd,
            "execution_value_VND": execution_value_vnd,
            "sizing_policy": sizing_policy,
            "sizing_adjustment_reason": sizing_reason,
            "capped_by_max_order_value": cap_attr.get("capped_by_max_order_value", False),
            "capped_by_cash": cap_attr.get("capped_by_cash", False),
            "capped_by_adv_liquidity": cap_attr.get("capped_by_adv_liquidity", False),
            "capped_by_scan_value": cap_attr.get("capped_by_scan_value", False),
            "manual_review_key": make_manual_review_key(asof_date, sym, idx),
            "scan_hash": scan_hash,
            "regime_bull": bool(row.get("regime_bull", True)),
        }
        intent_row["row_hash"] = compute_row_hash(intent_row)
        rows.append(intent_row)
        intent_seq += 1

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.drop(columns=[c for c in df.columns if c.startswith("_")], errors="ignore")
    return df


def _base_row(date, sym, path, idx, intent_seq, config: Optional[LiveTradingConfig] = None, scan_hash: str = "", **extra):
    base = {
        "order_intent_id": make_order_intent_id(
            date, sym, extra.get("action", ""), idx, extra.get("reason_code", "")
        ),
        "date": date,
        "symbol": sym,
        "side": "",
        "action": "",
        "strategy": "A3_DP",
        "tier": "WATCH",
        "quantity_estimate": 0,
        "value_VND": 0,
        "limit_price": 0,
        "reason_code": "",
        "risk_flags": "",
        "requires_manual_review": False,
        "approved": False,
        "rejected": False,
        "approval_stale": False,
        "broker_order_id": "",
        "strategy_classification": "",
        "source_scan_file": str(path),
        "source_scan_row_id": idx,
        "intent_sequence": intent_seq,
        "breadth_zone": "",
        "sector_l4": "",
        "pts_tag": "",
        "s3_tag": "",
        "macro_tag": "pending_external_data",
        "afl_tag": "visual_only",
        "adv50_B_VND": 0.0,
        "s3_shadow_action": "",
        "s3_no_real_order_flag": False,
        "s3_shadow_blocked_reason": "",
        "account_id": getattr(config, "account_id", "") if config else "",
        "scan_value_VND": 0.0,
        "execution_value_VND": 0.0,
        "sizing_policy": "",
        "sizing_adjustment_reason": "",
        "manual_review_key": make_manual_review_key(date, sym, idx),
        "scan_hash": scan_hash,
        "row_hash": "",
    }
    base.update(extra)
    if not base.get("row_hash"):
        base["row_hash"] = compute_row_hash(base)
    return base


def _watch_row(date, sym, action, row, path, idx, intent_seq, pts_tag="", s3_tag="", macro_tag="pending_external_data", afl_tag="visual_only"):
    return _base_row(
        date, sym, path, idx, intent_seq,
        action=action,
        reason_code=row.get("final_action", ""),
        breadth_zone=row.get("breadth_zone", ""),
        sector_l4=row.get("sector_l4", ""),
        pts_tag=pts_tag,
        s3_tag=s3_tag,
        macro_tag=macro_tag,
        afl_tag=afl_tag,
        adv50_B_VND=float(row.get("adv50_B_VND") or 0),
    )


def _s3_shadow_row(date, sym, action, row, path, idx, intent_seq, scan_hash: str, config: LiveTradingConfig):
    return _base_row(
        date, sym, path, idx, intent_seq, config=config, scan_hash=scan_hash,
        action=action,
        strategy="S3_SHADOW_MAX60",
        tier="PAPER",
        reason_code=str(row.get("s3_shadow_reason", "") or row.get("final_action", "")),
        risk_flags="NO_REAL_ORDER|NO_DNSE",
        s3_tag="shadow",
        s3_shadow_action=action,
        s3_no_real_order_flag=True,
        adv50_B_VND=float(row.get("adv50_B_VND") or 0),
    )


def _s3_blocked_row(date, sym, action, row, path, idx, intent_seq, block_reason: str, scan_hash: str, config: LiveTradingConfig):
    return _base_row(
        date, sym, path, idx, intent_seq, config=config, scan_hash=scan_hash,
        action="S3_SHADOW_BLOCKED",
        strategy="S3_SHADOW_MAX60",
        tier="WATCH",
        reason_code=str(row.get("final_action", "")),
        risk_flags=block_reason,
        s3_shadow_action=action,
        s3_no_real_order_flag=False,
        s3_shadow_blocked_reason=block_reason,
        adv50_B_VND=float(row.get("adv50_B_VND") or 0),
    )


def _non_production_row(date, sym, final_action, row, path, idx, intent_seq, classification, config, scan_hash: str = ""):
    return _base_row(
        date, sym, path, idx, intent_seq, config=config, scan_hash=scan_hash,
        action="SKIP_NON_PRODUCTION_CLASSIFICATION",
        reason_code=final_action,
        risk_flags="non_a3_production_classification",
        strategy_classification=classification,
        breadth_zone=row.get("breadth_zone", ""),
        sector_l4=row.get("sector_l4", ""),
        adv50_B_VND=float(row.get("adv50_B_VND") or 0),
    )


def _skip_row(
    date,
    sym,
    action,
    row,
    path,
    idx,
    intent_seq,
    flag,
    config: Optional[LiveTradingConfig] = None,
    scan_hash: str = "",
    *,
    scan_value_vnd: float = 0.0,
    sizing_policy: str = "",
):
    return _base_row(
        date, sym, path, idx, intent_seq, config=config, scan_hash=scan_hash,
        action=action,
        reason_code=row.get("final_action", ""),
        risk_flags=flag,
        breadth_zone=row.get("breadth_zone", ""),
        sector_l4=row.get("sector_l4", ""),
        adv50_B_VND=float(row.get("adv50_B_VND") or 0),
        scan_value_VND=scan_value_vnd,
        execution_value_VND=0.0,
        sizing_policy=sizing_policy,
        sizing_adjustment_reason=flag,
    )


def save_order_intents(config: LiveTradingConfig, asof_date: str, df: pd.DataFrame) -> Path:
    path = config.order_intents_path(asof_date)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path


def load_order_intents(config: LiveTradingConfig, asof_date: str) -> pd.DataFrame:
    path = config.order_intents_path(asof_date)
    if not path.exists():
        return pd.DataFrame(columns=INTENT_COLS)
    return pd.read_csv(path)


def intents_to_proposals(
    intents: pd.DataFrame,
    asof_date: str,
    nav_vnd: float,
    latest_panel_date: str = "",
    config: Optional[LiveTradingConfig] = None,
) -> List[OrderProposal]:
    """Bridge tradeable intents to OrderProposal — preserve intent_sequence order."""
    proposals: List[OrderProposal] = []
    tradeable_actions = {"BUY_T1", "BUY_T1_MANUAL_REVIEW", "BUY_T2", "SELL_TP1", "SELL_EXIT"}
    if intents.empty:
        return proposals
    work = intents.copy()
    if "intent_sequence" in work.columns:
        work = work.sort_values("intent_sequence", kind="stable")
    from src.trading.live.manual_review import intent_execution_allowed

    for _, row in work.iterrows():
        action = str(row.get("action", ""))
        if action not in tradeable_actions:
            continue
        cfg = config or LiveTradingConfig()
        allowed, _reason = intent_execution_allowed(row, cfg)
        if not allowed:
            continue
        side = str(row.get("side", "BUY"))
        if not side:
            side = "SELL" if "SELL" in action else "BUY"
        qty = int(row.get("quantity_estimate") or 0)
        price = float(row.get("limit_price") or 0)
        if qty <= 0 or price <= 0:
            continue
        adv_b = float(row.get("adv50_B_VND", 0) or 0)
        adv_vnd = adv_b * 1_000_000_000
        sig = Signal(
            strategy=str(row.get("strategy", "A3_DP")),
            symbol=str(row["symbol"]),
            side=side,
            asof_date=asof_date,
            intended_price=price,
            quantity=qty,
            reason=str(row.get("reason_code", "")),
            metadata={
                "latest_panel_date": latest_panel_date or asof_date,
                "action": action,
                "tier": row.get("tier"),
                "requires_manual_review": bool(row.get("requires_manual_review")),
                "order_intent_id": row.get("order_intent_id"),
                "intent_sequence": int(row.get("intent_sequence") or 0),
                "breadth_zone": row.get("breadth_zone"),
                "sector_l4": row.get("sector_l4"),
                "regime_bull": bool(row.get("regime_bull", True)),
            },
        )
        proposals.append(OrderProposal(signal=sig, adv50_vnd=adv_vnd, nav_vnd=nav_vnd))
    return proposals
