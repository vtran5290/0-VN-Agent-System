"""
Derive current open positions from full trade history OR from Current positions.xlsx.
When Current positions.xlsx is provided, it prevails (source of truth).
Outputs: current_positions_derived.json, current_positions_digest.md (overwrite-safe).
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from . import RAW_DIR
from .trade_import_excel import FULL_JSON

logger = logging.getLogger(__name__)

REVIEW_POLICY_PATH = Path(__file__).resolve().parents[2] / "data" / "decision" / "review_policy.json"

CURRENT_POSITIONS_JSON = RAW_DIR / "current_positions_derived.json"
CURRENT_POSITIONS_DIGEST_MD = RAW_DIR / "current_positions_digest.md"
CURRENT_POSITIONS_PROVENANCE_JSON = RAW_DIR / "current_positions_provenance.json"
CURRENT_POSITIONS_WARNINGS_JSON = RAW_DIR / "current_positions_warnings.json"
CURRENT_POSITIONS_SKIP_REPORT_JSON = RAW_DIR / "current_positions_skip_report.json"

# Skip reason keys for reconcile report.
SKIP_AGGREGATE_TICKER = "skip_aggregate_ticker"
SKIP_BLACKLISTED_TOKEN = "skip_blacklisted_token"
SKIP_NUMERIC_ONLY = "skip_numeric_only"
SKIP_INVALID_TICKER_FORMAT = "skip_invalid_ticker_format"
SKIP_MISSING_TICKER = "skip_missing_ticker"
SKIP_LOTS_LE_0 = "skip_lots_le_0"
SKIP_PARSE_ERROR = "skip_parse_error"
MAX_EXAMPLES_PER_REASON = 5

# Non-stock labels to skip (case-insensitive). Includes exchanges, indices, aggregates.
NON_TICKER_TOKENS = frozenset({
    "HNX", "HOSE", "UPCOM", "HOS", "VNI", "VNINDEX", "VN30",
    "MAXBUY", "HOLIDAYS", "SUMMARY", "TOTAL", "ALL", "TONG",
})

# Default path for "Current positions.xlsx" (user's self-updated file); override via --excel or config.
DEFAULT_CURRENT_POSITIONS_EXCEL = Path(r"C:\Users\LOLII\Downloads\Current positions.xlsx")


def _parse_date(val: Any) -> Optional[str]:
    """Return YYYY-MM-DD or None."""
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(val, "strftime"):
        try:
            return val.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            return None
    if isinstance(val, str):
        s = val.strip()[:10]
        if len(s) >= 10 and s[4] == "-" and s[7] == "-":
            return s
        return None
    return None


def _safe_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    try:
        s = str(val).strip().replace(",", "").replace(" ", "")
        return float(s) if s else None
    except (ValueError, TypeError):
        return None


def _safe_int(val: Any) -> Optional[int]:
    f = _safe_float(val)
    if f is None:
        return None
    try:
        return int(round(f))
    except (ValueError, OverflowError):
        return None


# Suffixes to strip from quantity strings (shares, cp, cổ phiếu, etc.)
LOTS_STRING_SUFFIXES = re.compile(
    r"\s*(shares?|cp|cổ\s*phiếu|co\s*phieu|lot|lots)\s*$",
    re.IGNORECASE,
)


def _parse_lots_robust(val: Any) -> Optional[int]:
    """
    Parse Quantity to int. Number -> OK. String: strip, remove thousands comma,
    remove suffix (shares, cp, cổ phiếu, ...); if digits remain -> int.
    Empty/NaN/NaT -> None (missing lots; no parse_error).
    """
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(val, (int, float)):
        try:
            n = int(round(float(val)))
            return n if n >= 0 else None
        except (ValueError, OverflowError):
            return None
    s = str(val).strip()
    if not s:
        return None
    s = LOTS_STRING_SUFFIXES.sub("", s).strip()
    s = s.replace(",", "").replace(" ", "")
    if not s or not s.replace(".", "").replace("-", "").isdigit():
        return None
    try:
        n = int(round(float(s)))
        return n if n >= 0 else None
    except (ValueError, TypeError, OverflowError):
        return None


def _normalize_col(name: str) -> str:
    s = str(name).strip().lower().replace(" ", "_").replace(".", "_")
    return re.sub(r"_+", "_", s)


def _find_column(df: pd.DataFrame, *candidates: str) -> Optional[str]:
    """Return first column name in df whose normalized form matches any normalized candidate."""
    cand_norm = [_normalize_col(c) for c in candidates]
    for c in df.columns:
        n = _normalize_col(str(c))
        for cn in cand_norm:
            if n == cn or (len(cn) >= 2 and cn in n):
                return str(c)
    return None


# Aggregate/summary row tickers (subset of NON_TICKER_TOKENS; kept for skip-report backward compat).
AGGREGATE_TICKERS = frozenset({"ALL", "TOTAL", "TONG", "SUMMARY"})
# After normalization (strip, upper, A-Z0-9 only): allow 2–8 chars (VN tickers + digits, ETFs).
TICKER_VALID_REGEX = re.compile(r"^[A-Z0-9]{2,8}$")
LOTS_EXTREME_THRESHOLD = 5_000_000
POSITIONS_HIGH_THRESHOLD = 100


def _normalize_ticker_for_validation(s: str) -> str:
    """Strip, upper, keep only A-Z0-9 for validation."""
    if not s:
        return ""
    t = str(s).strip().upper()
    t = "".join(c for c in t if c.isalnum())
    return t


def _extract_ticker_from_stock_cell(val: Any) -> Optional[str]:
    """Extract ticker from 'HOSE:SSI' or 'HNX:MBS' or plain 'SSI'. Normalize for validation (strip, A-Z0-9)."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip().upper()
    if ":" in s:
        s = s.split(":")[-1].strip()
    s = _normalize_ticker_for_validation(s)
    if s and TICKER_VALID_REGEX.match(s):
        return s
    return None


def _load_current_positions_policy() -> Dict[str, Any]:
    """Load review_policy.current_positions with safe defaults."""
    if not REVIEW_POLICY_PATH.exists():
        return {"default_lots_if_missing": False}
    try:
        data = json.loads(REVIEW_POLICY_PATH.read_text(encoding="utf-8"))
        cfg = data.get("current_positions") or {}
        return {"default_lots_if_missing": bool(cfg.get("default_lots_if_missing", False))}
    except Exception:
        return {"default_lots_if_missing": False}


def _parse_ticker_raw(val: Any) -> Tuple[Optional[str], str, str]:
    """Return (normalized_ticker_or_none, raw_stock_str, note). For skip report."""
    raw = "" if val is None or (isinstance(val, float) and pd.isna(val)) else str(val).strip()
    if not raw:
        return None, raw, "empty"
    s = raw.upper()
    if ":" in s:
        s = s.split(":")[-1].strip()
    normalized = _normalize_ticker_for_validation(s)
    if not normalized:
        return None, raw, "no alphanumeric"
    if normalized in AGGREGATE_TICKERS:
        return normalized, raw, "aggregate"
    if not TICKER_VALID_REGEX.match(normalized):
        note = "format" if len(normalized) < 2 or len(normalized) > 8 else "invalid chars"
        return normalized, raw, note
    return normalized, raw, "ok"


def load_from_current_positions_excel(
    excel_path: Path, asof: str
) -> Tuple[List[Dict[str, Any]], Dict[str, Any], int]:
    """
    Read Current positions.xlsx (source of truth). Returns (positions, skip_report, row_count_raw).
    skip_report: { skip_counts: {...}, examples: {...} } for reconcile.
    """
    excel_path = Path(excel_path).resolve()
    if not excel_path.exists():
        raise FileNotFoundError(f"Current positions Excel not found: {excel_path}")

    df = pd.read_excel(excel_path, sheet_name=0, engine="openpyxl")
    if df.empty:
        return [], {"skip_counts": {}, "examples": {}}, 0

    col_ticker = _find_column(df, "ticker", "symbol", "mã", "code", "stock")
    if not col_ticker:
        df_alt = pd.read_excel(excel_path, sheet_name=0, header=3, engine="openpyxl")
        if not df_alt.empty and _find_column(df_alt, "stock", "ticker", "symbol"):
            df = df_alt
    col_ticker = col_ticker or _find_column(df, "stock", "ticker", "symbol", "mã")
    col_lots = _find_column(df, "lots", "số_lot", "quantity", "sl", "kl")
    col_entry_date = _find_column(df, "entry_date", "ngày_vào", "entry", "date", "ngày_mua")
    col_entry_price = _find_column(df, "entry_price", "giá_vào", "price_bought", "price", "giá", "price bought")
    col_stop = _find_column(df, "stop_price", "stop", "dừng_lỗ", "stop_price_at_entry")
    col_reason = _find_column(df, "reason_tag", "reason", "lý_do", "tag")

    skip_counts: Dict[str, int] = {
        SKIP_AGGREGATE_TICKER: 0,
        SKIP_BLACKLISTED_TOKEN: 0,
        SKIP_NUMERIC_ONLY: 0,
        SKIP_INVALID_TICKER_FORMAT: 0,
        SKIP_MISSING_TICKER: 0,
        SKIP_LOTS_LE_0: 0,
        SKIP_PARSE_ERROR: 0,
    }
    examples: Dict[str, List[Dict[str, Any]]] = {k: [] for k in skip_counts}

    open_positions: List[Dict[str, Any]] = []
    row_count_raw = len(df)
    for row_idx, (_, row) in enumerate(df.iterrows()):
        raw = row.to_dict()
        raw_stock = str(raw.get(col_ticker, "")) if col_ticker else ""
        ticker_parsed, raw_stock_str, note = _parse_ticker_raw(raw.get(col_ticker) if col_ticker else None)

        if ticker_parsed is None:
            reason = SKIP_MISSING_TICKER
            skip_counts[reason] += 1
            if len(examples[reason]) < MAX_EXAMPLES_PER_REASON:
                examples[reason].append({"row": row_idx, "raw_stock": raw_stock_str or raw_stock, "parsed": note, "note": note})
            continue
        if ticker_parsed in NON_TICKER_TOKENS:
            skip_counts[SKIP_BLACKLISTED_TOKEN] += 1
            if len(examples[SKIP_BLACKLISTED_TOKEN]) < MAX_EXAMPLES_PER_REASON:
                examples[SKIP_BLACKLISTED_TOKEN].append({"row": row_idx, "raw_stock": raw_stock_str or raw_stock, "parsed": ticker_parsed, "note": "blacklisted"})
            continue
        if ticker_parsed.isdigit():
            skip_counts[SKIP_NUMERIC_ONLY] += 1
            if len(examples[SKIP_NUMERIC_ONLY]) < MAX_EXAMPLES_PER_REASON:
                examples[SKIP_NUMERIC_ONLY].append({"row": row_idx, "raw_stock": raw_stock_str or raw_stock, "parsed": ticker_parsed, "note": "numeric_only"})
            continue
        if len(ticker_parsed) < 2:
            skip_counts[SKIP_INVALID_TICKER_FORMAT] += 1
            if len(examples[SKIP_INVALID_TICKER_FORMAT]) < MAX_EXAMPLES_PER_REASON:
                examples[SKIP_INVALID_TICKER_FORMAT].append({"row": row_idx, "raw_stock": raw_stock_str or raw_stock, "parsed": ticker_parsed or "", "note": "length<2"})
            continue
        if note != "ok":
            skip_counts[SKIP_INVALID_TICKER_FORMAT] += 1
            if len(examples[SKIP_INVALID_TICKER_FORMAT]) < MAX_EXAMPLES_PER_REASON:
                examples[SKIP_INVALID_TICKER_FORMAT].append({"row": row_idx, "raw_stock": raw_stock_str or raw_stock, "parsed": ticker_parsed or "", "note": note})
            continue
        ticker = ticker_parsed

        lots = None
        if col_lots:
            v = raw.get(col_lots)
            lots = _parse_lots_robust(v)
            # Never skip for missing/unparseable lots: keep row with lots=None (digest will flag "missing lots")
        if lots is not None and lots < 1:
            skip_counts[SKIP_LOTS_LE_0] += 1
            if len(examples[SKIP_LOTS_LE_0]) < MAX_EXAMPLES_PER_REASON:
                examples[SKIP_LOTS_LE_0].append({"row": row_idx, "raw_stock": raw_stock_str, "parsed": str(lots), "note": "lots<=0"})
            continue
        policy = _load_current_positions_policy()
        if lots is None and policy.get("default_lots_if_missing"):
            lots = 1

        entry_d = None
        if col_entry_date:
            v = raw.get(col_entry_date)
            if v is not None and not (isinstance(v, float) and pd.isna(v)):
                entry_d = _parse_date(v)
                if not entry_d and hasattr(v, "strftime"):
                    entry_d = v.strftime("%Y-%m-%d")

        entry_p = None
        if col_entry_price:
            v = raw.get(col_entry_price)
            if v is not None and not (isinstance(v, float) and pd.isna(v)):
                entry_p = _safe_float(v)
                if entry_p is not None and entry_p < 0:
                    entry_p = abs(entry_p)

        stop_p = None
        if col_stop:
            v = raw.get(col_stop)
            if v is not None and not (isinstance(v, float) and pd.isna(v)):
                stop_p = _safe_float(v)

        reason_tag = "unknown"
        if col_reason:
            v = raw.get(col_reason)
            if v is not None and not (isinstance(v, float) and pd.isna(v)):
                reason_tag = str(v).strip() or "unknown"

        holding_days = None
        if entry_d:
            try:
                e = datetime.strptime(entry_d[:10], "%Y-%m-%d").date()
                a = datetime.strptime(asof[:10], "%Y-%m-%d").date()
                holding_days = max(0, (a - e).days)
            except (ValueError, TypeError):
                pass

        open_positions.append({
            "ticker": ticker,
            "entry_date": entry_d,
            "entry_price": entry_p,
            "lots": lots,
            "stop_price_at_entry": stop_p,
            "reason_tag": reason_tag,
            "holding_days": holding_days,
        })
    skip_report = {"skip_counts": skip_counts, "examples": examples}
    return open_positions, skip_report, row_count_raw


def _consolidate_duplicate_tickers(positions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Group by ticker: sum lots (None preserved when all missing), weighted avg entry_price. Keep first entry_date, reason_tag; max holding_days."""
    by_ticker: Dict[str, Dict[str, Any]] = {}
    lot_lists: Dict[str, List[Optional[int]]] = {}  # track raw lots per ticker for None handling
    for p in positions:
        t = (p.get("ticker") or "").strip().upper()
        if not t:
            continue
        lot_val = p.get("lots")
        if t not in by_ticker:
            by_ticker[t] = {
                "ticker": t,
                "entry_date": p.get("entry_date"),
                "entry_price": p.get("entry_price"),
                "lots": lot_val,
                "stop_price_at_entry": p.get("stop_price_at_entry"),
                "reason_tag": p.get("reason_tag") or "unknown",
                "holding_days": p.get("holding_days"),
            }
            lot_lists[t] = [lot_val] if lot_val is not None else [None]
            continue
        cur = by_ticker[t]
        lot_lists[t].append(lot_val)
        cur_lots_num = (cur.get("lots") or 0) + (lot_val or 0)
        ep_cur = cur.get("entry_price")
        ep_new = p.get("entry_price")
        if ep_cur is not None and ep_new is not None and cur_lots_num > 0:
            lots_cur = cur.get("lots") or 0
            lots_new = lot_val or 0
            cur["entry_price"] = (ep_cur * lots_cur + ep_new * lots_new) / cur_lots_num
        elif ep_new is not None and ep_cur is None:
            cur["entry_price"] = ep_new
        cur["lots"] = cur_lots_num
        if p.get("holding_days") is not None and (cur.get("holding_days") is None or (p["holding_days"] or 0) > (cur.get("holding_days") or 0)):
            cur["holding_days"] = p["holding_days"]
    # Only set lots=None when ALL component rows had lots None; otherwise keep summed lots
    for t, vals in lot_lists.items():
        if t in by_ticker and all(v is None for v in vals):
            by_ticker[t]["lots"] = None
    return list(by_ticker.values())


def _compute_sanity_warnings(positions: List[Dict[str, Any]]) -> List[str]:
    """Warn-only: duplicate tickers, entry_price <= 0, lots > 5e6, positions > 100. Does not block."""
    warnings: List[str] = []
    if len(positions) > POSITIONS_HIGH_THRESHOLD:
        warnings.append(f"Unusually high number of positions ({len(positions)} > {POSITIONS_HIGH_THRESHOLD})")
    seen: Dict[str, int] = {}
    for p in positions:
        t = (p.get("ticker") or "").strip().upper()
        if t:
            seen[t] = seen.get(t, 0) + 1
    dups = [t for t, c in seen.items() if c > 1]
    if dups:
        warnings.append(f"Duplicate tickers: {', '.join(sorted(dups)[:10])}{' ...' if len(dups) > 10 else ''}")
    for p in positions:
        ep = p.get("entry_price")
        if ep is not None and ep <= 0:
            warnings.append(f"entry_price <= 0 for ticker {p.get('ticker')}")
            break
        lots = p.get("lots")
        if lots is not None and lots > LOTS_EXTREME_THRESHOLD:
            warnings.append(f"lots extremely large ({lots} > {LOTS_EXTREME_THRESHOLD}) for ticker {p.get('ticker')}")
            break
    return warnings


def _write_provenance(
    source: str,
    source_file: str,
    source_file_mtime: Optional[str],
    row_count: int,
    row_count_raw: Optional[int] = None,
    row_count_skipped: Optional[int] = None,
) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    payload: Dict[str, Any] = {
        "source": source,
        "source_file": source_file,
        "source_file_mtime": source_file_mtime,
        "row_count": row_count,
    }
    if row_count_raw is not None:
        payload["row_count_raw"] = row_count_raw
    if row_count_skipped is not None:
        payload["row_count_skipped"] = row_count_skipped
    CURRENT_POSITIONS_PROVENANCE_JSON.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _write_warnings(warnings: List[str]) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    CURRENT_POSITIONS_WARNINGS_JSON.write_text(
        json.dumps(warnings, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _is_open_row(row: Dict[str, Any]) -> bool:
    """True if exit_date is null, empty, or missing."""
    exit_d = row.get("exit_date")
    if exit_d is None:
        return True
    if isinstance(exit_d, str) and not exit_d.strip():
        return True
    return False


def _canonicalize_open_position(row: Dict[str, Any], asof: str) -> Optional[Dict[str, Any]]:
    entry_d = _parse_date(row.get("entry_date"))
    entry_p = _safe_float(row.get("entry_price"))
    lots = _safe_int(row.get("lots"))
    if lots is None or lots < 1:
        lots = 1
    ticker = (row.get("ticker") or row.get("symbol") or "").strip().upper()
    if not ticker:
        return None
    stop_p = _safe_float(row.get("stop_price_at_entry") or row.get("stop_price") or row.get("initial_stop"))
    reason_tag = row.get("reason_tag") if row.get("reason_tag") is not None else "unknown"
    if reason_tag is None:
        reason_tag = "unknown"
    # holding_days from asof - entry_date
    holding_days = None
    if entry_d:
        try:
            e = datetime.strptime(entry_d[:10], "%Y-%m-%d").date()
            a = datetime.strptime(asof[:10], "%Y-%m-%d").date()
            holding_days = (a - e).days
            if holding_days < 0:
                holding_days = 0
        except (ValueError, TypeError):
            pass
    return {
        "ticker": ticker,
        "entry_date": entry_d,
        "entry_price": entry_p,
        "lots": lots,
        "stop_price_at_entry": stop_p,
        "reason_tag": reason_tag,
        "holding_days": holding_days,
    }


def derive(
    asof: Optional[str] = None,
    full_json_path: Optional[Path] = None,
    current_positions_excel_path: Optional[Path] = None,
) -> Path:
    """
    Build current open positions and write JSON + digest.
    When current_positions_excel_path is provided and exists, it prevails (source of truth).
    Otherwise derive from full trade history (requires trade_history_full.json).
    Idempotent and overwrite-safe. Returns path to current_positions_derived.json.
    """
    if asof is None:
        asof = datetime.now().strftime("%Y-%m-%d")

    source_note = "trade_history_full.json"
    skipped_missing_ticker = 0
    skip_report: Dict[str, Any] = {"skip_counts": {}, "examples": {}}
    row_count_raw: Optional[int] = None
    row_count_skipped: Optional[int] = None
    consolidated = False
    provenance_source = "trade_history_full"
    provenance_file = str(FULL_JSON)
    provenance_mtime: Optional[str] = None
    excel_path = Path(current_positions_excel_path) if current_positions_excel_path else None
    if excel_path and excel_path.exists():
        open_positions, skip_report, row_count_raw = load_from_current_positions_excel(excel_path, asof)
        row_count_skipped = sum(skip_report.get("skip_counts", {}).values())
        open_positions = _consolidate_duplicate_tickers(open_positions)
        consolidated = True
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        CURRENT_POSITIONS_SKIP_REPORT_JSON.write_text(
            json.dumps(skip_report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        source_note = f"Current positions.xlsx ({excel_path.name})"
        provenance_source = "current_positions_excel"
        provenance_file = str(excel_path.resolve())
        try:
            provenance_mtime = datetime.fromtimestamp(excel_path.stat().st_mtime).isoformat() + "Z"
        except OSError:
            pass
        logger.info("Loaded %d open positions from %s (prevails); skipped %d rows; consolidated to unique tickers", len(open_positions), excel_path.name, row_count_skipped or 0)
    else:
        path = full_json_path or FULL_JSON
        if not path.exists():
            raise FileNotFoundError(
                "Full trade history not imported and no Current positions.xlsx provided.\n"
                "  Option A: python -m src.review.cli import-full --excel \"<Trade History.xlsx>\"\n"
                "  Option B: python -m src.review.cli derive-current --excel \"<Current positions.xlsx>\""
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("trade_history_full.json must be a list of trade objects")
        open_positions = []
        skipped_missing_ticker = 0
        for row in data:
            if not isinstance(row, dict):
                continue
            if not _is_open_row(row):
                continue
            canon = _canonicalize_open_position(row, asof)
            if canon is not None:
                open_positions.append(canon)
            else:
                skipped_missing_ticker += 1
        if skipped_missing_ticker:
            logger.warning("Skipped %d open rows missing ticker", skipped_missing_ticker)
        try:
            provenance_mtime = datetime.fromtimestamp(path.stat().st_mtime).isoformat() + "Z"
        except (OSError, NameError):
            pass

    # Provenance (row_count = final usable; raw/skipped when from Excel)
    _write_provenance(
        provenance_source,
        provenance_file,
        provenance_mtime,
        len(open_positions),
        row_count_raw=row_count_raw,
        row_count_skipped=row_count_skipped,
    )

    # Sanity warnings (warn-only) + missing lots
    sanity_warnings = list(_compute_sanity_warnings(open_positions))
    missing_lots_tickers = [p["ticker"] for p in open_positions if p.get("lots") is None]
    missing_lots_count = len(missing_lots_tickers)
    if missing_lots_count > 0:
        sanity_warnings.append(f"Missing lots for tickers: {', '.join(sorted(missing_lots_tickers)[:20])}{' ...' if len(missing_lots_tickers) > 20 else ''}")
    if sanity_warnings:
        _write_warnings(sanity_warnings)
        for w in sanity_warnings:
            logger.warning("Position sanity: %s", w)
    else:
        if CURRENT_POSITIONS_WARNINGS_JSON.exists():
            CURRENT_POSITIONS_WARNINGS_JSON.write_text("[]", encoding="utf-8")

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    # A) JSON
    CURRENT_POSITIONS_JSON.write_text(
        json.dumps(open_positions, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # B) Digest Markdown — table with Symbol | Lots first so parse_open_positions_from_md can read it
    lines = [
        "# Current Positions (Auto-derived)",
        "",
        f"As of: {asof}",
        "",
        f"Total positions: {len(open_positions)}",
        "",
        "| Symbol | Lots | Entry Date | Entry Price | Holding Days | Reason Tag |",
        "|--------|------|------------|-------------|--------------|------------|",
    ]
    for p in open_positions:
        entry_d = p.get("entry_date") or ""
        entry_p = p.get("entry_price")
        entry_p_str = f"{entry_p:.0f}" if entry_p is not None else ""
        holding = p.get("holding_days")
        holding_str = str(holding) if holding is not None else ""
        reason = p.get("reason_tag") or "unknown"
        lots_str = str(p["lots"]) if p.get("lots") is not None else "—"
        lines.append(f"| {p['ticker']} | {lots_str} | {entry_d} | {entry_p_str} | {holding_str} | {reason} |")
    footer_lines = [
        "",
        "---",
        "**Sanity check:**",
        f"- Open positions count = {len(open_positions)}",
        f"- Source: {source_note}",
    ]
    if consolidated:
        footer_lines.append("- Duplicates consolidated (by ticker: sum lots, weighted avg entry_price).")
    missing_lots_count = sum(1 for p in open_positions if p.get("lots") is None)
    if missing_lots_count > 0:
        footer_lines.append(f"- Missing lots: {missing_lots_count} positions (lots=null).")
    if skipped_missing_ticker > 0:
        footer_lines.append(f"- Skipped {skipped_missing_ticker} rows missing ticker (from trade_history_full).")
    sc = skip_report.get("skip_counts", {})
    if sc and any(v > 0 for v in sc.values()):
        total_skip = sum(sc.values())
        parts = [f"{k.replace('skip_', '')}={v}" for k, v in sc.items() if v > 0]
        footer_lines.append(f"- Skipped {total_skip} rows: {', '.join(parts)}.")
        footer_lines.append("- See current_positions_skip_report.json for examples.")
    if sanity_warnings:
        footer_lines.append("**Warnings (non-blocking):**")
        for w in sanity_warnings:
            footer_lines.append(f"- {w}")
    lines.extend(footer_lines)
    CURRENT_POSITIONS_DIGEST_MD.write_text("\n".join(lines), encoding="utf-8")

    logger.info("Wrote %d open positions -> %s, %s (source: %s)", len(open_positions), CURRENT_POSITIONS_JSON.name, CURRENT_POSITIONS_DIGEST_MD.name, source_note)
    return CURRENT_POSITIONS_JSON
