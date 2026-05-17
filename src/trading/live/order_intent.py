"""Convert daily scan CSV to order intents (adapter only — no strategy recompute)."""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from src.trading.config import LiveTradingConfig
from src.trading.live.paper_ledger import PaperLedger
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
}

INTENT_COLS = [
    "order_intent_id", "date", "symbol", "side", "action", "strategy", "tier",
    "quantity_estimate", "value_VND", "limit_price", "reason_code", "risk_flags",
    "requires_manual_review", "approved", "broker_order_id", "source_scan_file",
    "source_scan_row_id", "breadth_zone", "sector_l4", "pts_tag", "s3_tag",
    "macro_tag", "afl_tag", "adv50_B_VND",
    "s3_shadow_action", "s3_no_real_order_flag",
]

# S3 shadow actions — paper-only, never tradeable
_S3_SHADOW_ACTIONS = {"PAPER_S3_SHADOW", "PAPER_S3_RESEARCH_MONITOR"}


def _effective_t1_vnd(row: pd.Series, participation: float) -> float:
    """target_T1_M in M VND; adv50_B_VND in B VND; cap at 10% ADV."""
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


def build_order_intents(
    config: LiveTradingConfig,
    asof_date: str,
    health_status: Dict[str, Any],
    scan_path: Optional[Path] = None,
    ledger: Optional[PaperLedger] = None,
    latest_panel_date: str = "",
) -> pd.DataFrame:
    if health_status.get("BLOCK_ORDER_GENERATION"):
        return pd.DataFrame(columns=INTENT_COLS)

    path = scan_path or config.scan_csv_path
    if not path.exists():
        return pd.DataFrame(columns=INTENT_COLS)

    scan = pd.read_csv(path)
    scan["as_of_date"] = pd.to_datetime(scan["as_of_date"]).dt.strftime("%Y-%m-%d")
    day = scan[scan["as_of_date"] == asof_date[:10]].copy()
    if day.empty:
        return pd.DataFrame(columns=INTENT_COLS)

    open_syms = set(ledger.get_open_symbols()) if ledger else set()
    rows: List[Dict[str, Any]] = []

    for idx, row in day.iterrows():
        sym = str(row["symbol"]).upper()
        classification = str(row.get("strategy_classification", ""))
        final_action = str(row.get("final_action", "WATCH_ONLY"))

        pts_tag = "shadow" if "PTS" in classification else ""
        s3_tag = "research_only" if classification == "S3_RESEARCH_ONLY" or "S3" in classification else ""
        macro_tag = "pending_external_data"
        afl_tag = "visual_only"

        # Phase35: S3 shadow routing — paper only, never live orders.
        # Guard: only intercept when A3 is NOT also active. If both a3_active and
        # s3_active are True (common — S3 EMA21/55 fires more often than A3 EMA20/100),
        # fall through so the A3 production intent is generated instead.
        # S3 paper tracking for dual-active symbols is handled by the operator ledger.
        s3_shadow_action = str(row.get("s3_shadow_action", ""))
        a3_active_in_row = bool(row.get("a3_active", False))
        if s3_shadow_action in _S3_SHADOW_ACTIONS and not a3_active_in_row:
            rows.append(_s3_shadow_row(asof_date, sym, s3_shadow_action, row, path, idx))
            continue

        if classification == "S3_RESEARCH_ONLY" or (s3_tag and not config.allow_s3_capital):
            rows.append(_watch_row(asof_date, sym, "WATCH_S3_RESEARCH_ONLY", row, path, idx, s3_tag, macro_tag, afl_tag))
            continue

        if "PTS" in classification and not config.allow_pts_shadow:
            rows.append(_watch_row(asof_date, sym, "WATCH_PTS_SHADOW", row, path, idx, pts_tag, macro_tag, afl_tag))
            continue

        if classification not in ("A3_PRODUCTION", "") and "A3" not in classification:
            if final_action == "WATCH_ONLY":
                rows.append(_watch_row(asof_date, sym, "WATCH_ONLY", row, path, idx, pts_tag, s3_tag, macro_tag, afl_tag))
            continue

        if not bool(row.get("in_a3_universe", True)):
            continue

        mapped = ACTION_MAP.get(final_action, ("WATCH_ONLY", "WATCH", "", False))
        action, tier, side, tradeable = mapped

        liq = str(row.get("liq_warn_T1", "OK"))
        if liq == "CRITICAL":
            rows.append(_skip_row(asof_date, sym, "SKIP_LIQUIDITY", row, path, idx, liq))
            continue

        if final_action == "SKIP_VNINDEX_BEAR" or (config.require_regime_bull and not bool(row.get("regime_bull", True))):
            rows.append(_skip_row(asof_date, sym, "SKIP_VNINDEX_BEAR", row, path, idx, "regime"))
            continue

        requires_manual = final_action == "NEW_T1_MANUAL_REVIEW_BREADTH"
        risk_flags = []
        if str(row.get("breadth_zone", "")) == "defense":
            risk_flags.append("breadth_defense")
        if str(row.get("sector_l4_stress_flag", "")) in ("WARN", "STRESS"):
            risk_flags.append("sector_l4_warning")

        if not tradeable:
            rows.append(_watch_row(asof_date, sym, action, row, path, idx, pts_tag, s3_tag, macro_tag, afl_tag))
            continue

        close_kvnd = float(row.get("close_kVND") or 0)
        limit_price = close_kvnd * 1000  # kVND -> VND per share
        value_vnd = _effective_t1_vnd(row, config.adv_participation)
        if tier == "T2":
            value_vnd = value_vnd  # T2 sizing from scan when ADD_T2
        qty = int(value_vnd / limit_price) if limit_price > 0 else 0

        rows.append({
            "order_intent_id": str(uuid.uuid4())[:12],
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
            "broker_order_id": "",
            "source_scan_file": str(path),
            "source_scan_row_id": idx,
            "breadth_zone": row.get("breadth_zone", ""),
            "sector_l4": row.get("sector_l4", ""),
            "pts_tag": pts_tag,
            "s3_tag": s3_tag,
            "macro_tag": macro_tag,
            "afl_tag": afl_tag,
            "adv50_B_VND": float(row.get("adv50_B_VND") or 0),
            "_regime_bull": bool(row.get("regime_bull", True)),
            "_latest_panel_date": latest_panel_date,
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.drop(columns=[c for c in df.columns if c.startswith("_")], errors="ignore")
    return df


def _watch_row(date, sym, action, row, path, idx, pts_tag="", s3_tag="", macro_tag="pending_external_data", afl_tag="visual_only"):
    return {
        "order_intent_id": str(uuid.uuid4())[:12],
        "date": date, "symbol": sym, "side": "", "action": action,
        "strategy": "A3_DP", "tier": "WATCH", "quantity_estimate": 0, "value_VND": 0,
        "limit_price": 0, "reason_code": row.get("final_action", ""), "risk_flags": "",
        "requires_manual_review": False, "approved": False, "broker_order_id": "",
        "source_scan_file": str(path), "source_scan_row_id": idx,
        "breadth_zone": row.get("breadth_zone", ""), "sector_l4": row.get("sector_l4", ""),
        "pts_tag": pts_tag, "s3_tag": s3_tag, "macro_tag": macro_tag, "afl_tag": afl_tag,
    }


def _s3_shadow_row(date, sym, action, row, path, idx):
    """Paper-only S3 shadow intent.  tradeable=False, no live order, no DNSE."""
    return {
        "order_intent_id": str(uuid.uuid4())[:12],
        "date": date, "symbol": sym, "side": "", "action": action,
        "strategy": "S3_SHADOW_MAX60", "tier": "PAPER", "quantity_estimate": 0, "value_VND": 0,
        "limit_price": 0, "reason_code": str(row.get("s3_shadow_reason", "")),
        "risk_flags": "NO_REAL_ORDER|NO_DNSE", "requires_manual_review": False,
        "approved": False, "broker_order_id": "",
        "source_scan_file": str(path), "source_scan_row_id": idx,
        "breadth_zone": row.get("breadth_zone", ""), "sector_l4": row.get("sector_l4", ""),
        "pts_tag": "", "s3_tag": "shadow", "macro_tag": "pending_external_data", "afl_tag": "visual_only",
        "adv50_B_VND": float(row.get("adv50_B_VND") or 0),
        "s3_shadow_action": action,
        "s3_no_real_order_flag": True,
    }


def _skip_row(date, sym, action, row, path, idx, flag):
    return {
        "order_intent_id": str(uuid.uuid4())[:12],
        "date": date, "symbol": sym, "side": "", "action": action,
        "strategy": "A3_DP", "tier": "WATCH", "quantity_estimate": 0, "value_VND": 0,
        "limit_price": 0, "reason_code": row.get("final_action", ""), "risk_flags": flag,
        "requires_manual_review": False, "approved": False, "broker_order_id": "",
        "source_scan_file": str(path), "source_scan_row_id": idx,
        "breadth_zone": row.get("breadth_zone", ""), "sector_l4": row.get("sector_l4", ""),
        "pts_tag": "", "s3_tag": "", "macro_tag": "pending_external_data", "afl_tag": "visual_only",
    }


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
) -> List[OrderProposal]:
    """Bridge tradeable intents to OrderProposal for OMS."""
    proposals: List[OrderProposal] = []
    tradeable_actions = {"BUY_T1", "BUY_T1_MANUAL_REVIEW", "BUY_T2", "SELL_TP1", "SELL_EXIT"}
    for _, row in intents.iterrows():
        action = str(row.get("action", ""))
        if action not in tradeable_actions:
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
                "breadth_zone": row.get("breadth_zone"),
                "sector_l4": row.get("sector_l4"),
                "regime_bull": row.get("_regime_bull", True),
            },
        )
        proposals.append(OrderProposal(signal=sig, adv50_vnd=adv_vnd, nav_vnd=nav_vnd))
    return proposals
