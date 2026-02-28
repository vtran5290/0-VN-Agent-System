"""
Parse trade history open positions from md; load closed trades from optional JSON.
K–M rule: open = no input in closed-position columns; closed = has input.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import RAW_DIR, TRADE_HISTORY_MD, POSITIONS_DIGEST_MD

logger = logging.getLogger(__name__)

TRADE_HISTORY_CLOSED_JSON = RAW_DIR / "trade_history_closed.json"


def _parse_md_table_symbol_lots(content: str) -> List[Tuple[str, Optional[int]]]:
    """Parse markdown table with Symbol and Lots columns. Returns [(symbol, lots or None), ...]. Accepts '—' for missing lots."""
    pairs: List[Tuple[str, Optional[int]]] = []
    lines = content.splitlines()
    in_table = False
    for line in lines:
        stripped = line.strip()
        if "| Symbol |" in stripped or "| Lots |" in stripped:
            in_table = True
            continue
        if in_table and stripped.startswith("|") and "---" not in stripped:
            parts = [p.strip() for p in stripped.split("|") if p.strip()]
            if len(parts) >= 2:
                sym = parts[0].upper()
                raw = parts[1].replace(",", "").strip()
                if raw in ("—", "-", "", "n/a", "N/A"):
                    lots = None
                else:
                    try:
                        lots = int(raw)
                    except (ValueError, TypeError):
                        continue
                if sym and sym != "SYMBOL" and not sym.isdigit():
                    pairs.append((sym, lots))
            continue
        if in_table and stripped.startswith("|") and "---" in stripped:
            continue
        if in_table and not stripped.startswith("|"):
            break
    return pairs


def _load_derived_open_positions() -> Optional[List[Dict[str, Any]]]:
    """If current_positions_derived.json exists (from derive-current), load and return [{ticker, lots}, ...]."""
    derived = RAW_DIR / "current_positions_derived.json"
    if not derived.exists():
        return None
    try:
        data = json.loads(derived.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return None
        out: List[Dict[str, Any]] = []
        for row in data:
            if not isinstance(row, dict):
                continue
            ticker = (row.get("ticker") or "").strip().upper()
            if not ticker:
                continue
            lots = row.get("lots")
            if lots is not None:
                try:
                    lots = int(lots)
                except (TypeError, ValueError):
                    lots = None
            out.append({"ticker": ticker, "lots": lots})
        return out
    except Exception:
        return None


def parse_open_positions_from_md(
    trade_history_path: Optional[Path] = None,
    positions_digest_path: Optional[Path] = None,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Parse open positions. Prefers current_positions_derived.json (from derive-current) when present;
    else trade_history_open_positions.md or current_positions_digest.md.
    Returns (list of {ticker, lots}, parser_warnings).
    """
    warnings: List[str] = []
    derived = _load_derived_open_positions()
    if derived is not None:
        return derived, warnings

    path = trade_history_path or TRADE_HISTORY_MD
    if not path.exists():
        path = positions_digest_path or POSITIONS_DIGEST_MD
    if not path.exists():
        warnings.append(f"Neither {TRADE_HISTORY_MD.name} nor {POSITIONS_DIGEST_MD.name} found")
        return [], warnings

    content = path.read_text(encoding="utf-8")
    pairs = _parse_md_table_symbol_lots(content)
    if not pairs and "Danh sách symbol:" in content:
        # Fallback: parse "DCM, GMD, HAH, ..."
        for m in re.finditer(r"Danh sách symbol:\s*([A-Z0-9,\s]+)", content, re.I):
            syms = [s.strip() for s in m.group(1).split(",") if s.strip()]
            pairs = [(s, 1) for s in syms]

    positions: List[Dict[str, Any]] = []
    for symbol, lots in pairs:
        positions.append({"ticker": symbol, "lots": lots})  # lots may be None
    return positions, warnings


def load_closed_trades(path: Optional[Path] = None) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Load closed trades from optional JSON. Schema: list of {
      ticker, entry_date, exit_date,
      entry_price?, exit_price?, lots?,
      stop_price_at_entry? (aka initial_stop/stop_price),
      reason_tag?, exit_tag?
    }
    Returns (trades, parser_warnings).
    """
    warnings: List[str] = []
    p = path or TRADE_HISTORY_CLOSED_JSON
    if not p.exists():
        logger.debug("No closed trades file at %s", p)
        return [], warnings

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        warnings.append(f"Failed to load {p.name}: {e}")
        return [], warnings

    if not isinstance(data, list):
        warnings.append("trade_history_closed.json must be a list of trade objects")
        return [], warnings

    trades: List[Dict[str, Any]] = []
    for i, row in enumerate(data):
        if not isinstance(row, dict):
            continue

        stop = row.get("stop_price_at_entry")
        if stop is None:
            stop = row.get("initial_stop")
        if stop is None:
            stop = row.get("stop_price")

        stop_source = (row.get("stop_source") or "").strip().lower()
        if stop_source not in ("manual", "system_default"):
            stop_source = "unknown"

        t = {
            "ticker": (row.get("ticker") or row.get("symbol") or "").upper(),
            "entry_date": row.get("entry_date"),
            "exit_date": row.get("exit_date"),
            "entry_price": row.get("entry_price"),
            "exit_price": row.get("exit_price"),
            "lots": row.get("lots", 1),
            "stop_price_at_entry": stop,
            "stop_source": stop_source,
            # Keep explicit marker if missing; downstream treats "unknown" as missing for compliance metrics.
            "reason_tag": row.get("reason_tag") if row.get("reason_tag") is not None else "unknown",
            "exit_tag": row.get("exit_tag") if row.get("exit_tag") is not None else "unknown",
        }
        if not t["ticker"]:
            continue
        if t["entry_date"] or t["exit_date"]:
            trades.append(t)
    return trades, warnings
