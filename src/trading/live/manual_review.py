"""File-based MANUAL_REVIEW operator queue with row_hash stale approval guard."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from src.trading.config import LiveTradingConfig
from src.trading.live.csv_parse import parse_csv_bool
from src.trading.live.row_hash import compute_row_hash, make_manual_review_key

QUEUE_COLS = [
    "order_intent_id", "manual_review_key", "account_id", "date", "symbol", "action", "side",
    "strategy", "tier", "reason_code", "risk_flags", "requires_manual_review", "approved",
    "rejected", "approval_stale", "previous_row_hash", "reviewer", "reviewed_at", "review_note",
    "source_scan_file", "source_scan_row_id", "scan_hash", "row_hash",
]


def manual_review_queue_path(config: LiveTradingConfig, asof_date: str) -> Path:
    return config.live_dir / f"manual_review_queue_{asof_date.replace('-', '')}.csv"


def sync_queue_from_intents(
    config: LiveTradingConfig,
    asof_date: str,
    intents: pd.DataFrame,
    *,
    scan_hash: str = "",
) -> Path:
    path = manual_review_queue_path(config, asof_date)
    path.parent.mkdir(parents=True, exist_ok=True)
    account_id = getattr(config, "account_id", "") or ""

    if intents.empty or "requires_manual_review" not in intents.columns:
        pd.DataFrame(columns=QUEUE_COLS).to_csv(path, index=False)
        return path

    mr = intents[intents["requires_manual_review"].map(parse_csv_bool)].copy()
    if mr.empty:
        pd.DataFrame(columns=QUEUE_COLS).to_csv(path, index=False)
        return path

    existing = load_queue(config, asof_date)
    existing_by_key: Dict[str, pd.Series] = {}
    if not existing.empty and "manual_review_key" in existing.columns:
        for _, er in existing.iterrows():
            key = str(er.get("manual_review_key", ""))
            if key:
                existing_by_key[key] = er

    rows: List[Dict[str, Any]] = []
    for _, row in mr.iterrows():
        mr_key = str(row.get("manual_review_key", "")) or make_manual_review_key(
            str(row.get("date", asof_date)),
            str(row.get("symbol", "")),
            row.get("source_scan_row_id", ""),
        )
        row_hash = str(row.get("row_hash", "")) or compute_row_hash(row)
        scan_h = str(row.get("scan_hash", "")) or scan_hash
        prev = existing_by_key.get(mr_key)
        approved = False
        rejected = False
        reviewer = ""
        reviewed_at = ""
        review_note = ""
        approval_stale = False
        previous_row_hash = ""
        if prev is not None and not (isinstance(prev, float) and pd.isna(prev)):
            prev_hash = str(prev.get("row_hash", ""))
            previous_row_hash = prev_hash
            if prev_hash and prev_hash == row_hash:
                approved = parse_csv_bool(prev.get("approved"))
                rejected = parse_csv_bool(prev.get("rejected"))
                reviewer = str(prev.get("reviewer", "") or "")
                reviewed_at = str(prev.get("reviewed_at", "") or "")
                review_note = str(prev.get("review_note", "") or "")
            else:
                approval_stale = parse_csv_bool(prev.get("approved")) or parse_csv_bool(prev.get("rejected"))
                approved = False
                rejected = False
        side = str(row.get("side", ""))
        if not side and "SELL" in str(row.get("action", "")):
            side = "SELL"
        elif not side and "BUY" in str(row.get("action", "")):
            side = "BUY"
        rows.append({
            "order_intent_id": str(row.get("order_intent_id", "")),
            "manual_review_key": mr_key,
            "account_id": str(row.get("account_id", account_id)),
            "date": row.get("date", asof_date),
            "symbol": row.get("symbol", ""),
            "action": row.get("action", ""),
            "side": side,
            "strategy": row.get("strategy", ""),
            "tier": row.get("tier", ""),
            "reason_code": row.get("reason_code", ""),
            "risk_flags": row.get("risk_flags", ""),
            "requires_manual_review": True,
            "approved": approved,
            "rejected": rejected,
            "approval_stale": approval_stale,
            "previous_row_hash": previous_row_hash,
            "reviewer": reviewer,
            "reviewed_at": reviewed_at,
            "review_note": review_note,
            "source_scan_file": row.get("source_scan_file", ""),
            "source_scan_row_id": row.get("source_scan_row_id", ""),
            "scan_hash": scan_h,
            "row_hash": row_hash,
        })
    pd.DataFrame(rows, columns=QUEUE_COLS).to_csv(path, index=False)
    return path


def load_queue(config: LiveTradingConfig, asof_date: str) -> pd.DataFrame:
    path = manual_review_queue_path(config, asof_date)
    if not path.exists():
        return pd.DataFrame(columns=QUEUE_COLS)
    return pd.read_csv(path, dtype=object)


def intent_execution_allowed(row: pd.Series, config: LiveTradingConfig) -> tuple[bool, str]:
    if not parse_csv_bool(row.get("requires_manual_review", False)):
        return True, ""
    approved = parse_csv_bool(row.get("approved"))
    rejected = parse_csv_bool(row.get("rejected"))
    stale = parse_csv_bool(row.get("approval_stale"))
    if approved and rejected:
        return False, "manual_review_conflict"
    if rejected:
        return False, "manual_review_rejected"
    if stale:
        return False, "manual_review_stale"
    if config.require_manual_review_approval and not approved:
        return False, "manual_review_pending"
    return True, ""


def apply_queue_to_intents(config: LiveTradingConfig, asof_date: str, intents: pd.DataFrame) -> pd.DataFrame:
    if intents.empty:
        return intents
    queue = load_queue(config, asof_date)
    if queue.empty:
        return intents
    out = intents.copy()
    for col in ("approved", "rejected", "approval_stale"):
        if col not in out.columns:
            out[col] = False
    if "manual_review_key" not in out.columns:
        out["manual_review_key"] = out.apply(
            lambda r: make_manual_review_key(
                str(r.get("date", asof_date)), str(r.get("symbol", "")), r.get("source_scan_row_id", "")
            ),
            axis=1,
        )
    qmap = queue.set_index("manual_review_key") if "manual_review_key" in queue.columns else queue.set_index("order_intent_id")
    for i, row in out.iterrows():
        key = str(row.get("manual_review_key", ""))
        iid = str(row.get("order_intent_id", ""))
        idx_key = key if key in qmap.index else iid
        if idx_key in qmap.index:
            out.at[i, "approved"] = parse_csv_bool(qmap.at[idx_key, "approved"])
            out.at[i, "rejected"] = parse_csv_bool(qmap.at[idx_key, "rejected"])
            if "approval_stale" in qmap.columns:
                out.at[i, "approval_stale"] = parse_csv_bool(qmap.at[idx_key, "approval_stale"])
    return out


def pending_summary(config: LiveTradingConfig, asof_date: str) -> Dict[str, Any]:
    q = load_queue(config, asof_date)
    if q.empty:
        return {"pending": 0, "approved": 0, "rejected": 0, "stale": 0, "rows": []}
    stale_col = q["approval_stale"].map(parse_csv_bool) if "approval_stale" in q.columns else pd.Series([False] * len(q))
    pending = q[
        (q["requires_manual_review"].astype(bool))
        & (~q["approved"].map(parse_csv_bool))
        & (~q["rejected"].map(parse_csv_bool))
        & (~stale_col)
    ]
    return {
        "pending": len(pending),
        "approved": int(q["approved"].map(parse_csv_bool).sum()),
        "rejected": int(q["rejected"].map(parse_csv_bool).sum()),
        "stale": int(stale_col.sum()),
        "account_id": getattr(config, "account_id", ""),
        "rows": pending.to_dict(orient="records"),
    }
