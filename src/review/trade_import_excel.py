"""
Import full trade history from Excel → raw snapshot (no-loss).
Header detection, canonical column mapping (VN/EN), robust number/date parsing.
Outputs: trade_history_full.csv, trade_history_full.json, trade_history_full.meta.json.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from . import RAW_DIR

logger = logging.getLogger(__name__)

TRADES_DIR = RAW_DIR / "trades"
FULL_CSV = TRADES_DIR / "trade_history_full.csv"
FULL_JSON = TRADES_DIR / "trade_history_full.json"
FULL_META = TRADES_DIR / "trade_history_full.meta.json"

# Header-likeness: tokens (case-insensitive, strip accents) that identify a header cell for each canonical key.
HEADER_TOKENS: Dict[str, List[str]] = {
    "ticker": ["ticker", "symbol", "stock", "ma ck", "mã ck", "stock code", "code", "ma", "mã"],
    "entry_date": ["entry date", "entry", "b date", "ngay mua", "ngay vao", "ngày mua", "ngày vào", "buy date", "open date"],
    "exit_date": ["exit date", "exit", "s date", "closed", "sell", "ngay ban", "ngay ra", "ngày bán", "ngày ra", "sell date", "close date"],
    "entry_price": ["entry price", "gia mua", "giá mua", "gia vao", "giá vào", "buy price", "open price", "price bought"],
    "exit_price": ["exit price", "gia ban", "giá bán", "gia ra", "giá ra", "sell price", "close price"],
    "lots": ["lots", "qty", "quantity", "khoi luong", "khối lượng", "so luong", "số lượng", "shares"],
}
MIN_HEADER_SCORE = 2

# Canonical key -> synonyms for column mapping (normalized: lowercase, strip accents).
CANONICAL_SYNONYMS: Dict[str, List[str]] = {
    "ticker": ["ticker", "symbol", "stock", "ma", "mã", "ma ck", "mã ck", "stock code", "code"],
    "entry_date": ["entry date", "entry", "b date", "ngay mua", "ngay vao", "ngày mua", "ngày vào", "buy date", "open date"],
    "exit_date": ["exit date", "exit", "s date", "closed", "sell", "ngay ban", "ngay ra", "ngày bán", "ngày ra", "sell date", "close date"],
    "entry_price": ["entry price", "gia mua", "giá mua", "gia vao", "giá vào", "buy price", "open price", "price bought"],
    "exit_price": ["exit price", "gia ban", "giá bán", "gia ra", "giá ra", "sell price", "close price"],
    "lots": ["lots", "qty", "quantity", "khoi luong", "khối lượng", "so luong", "số lượng", "shares"],
}


def _strip_accents(s: str) -> str:
    """Normalize for comparison: NFD and remove combining characters."""
    n = unicodedata.normalize("NFD", s)
    return "".join(c for c in n if unicodedata.category(c) != "Mn")


def _normalize_cell_for_header(s: Any) -> str:
    """Lowercase, strip accents, collapse spaces; for header scoring."""
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    t = str(s).strip().lower()
    t = _strip_accents(t)
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def _score_header_row(cells: List[Any]) -> int:
    """Count how many canonical keys have a matching token in this row (deterministic)."""
    score = 0
    row_text = " ".join(_normalize_cell_for_header(c) for c in cells)
    for canonical_key, tokens in HEADER_TOKENS.items():
        for token in tokens:
            norm_token = _normalize_cell_for_header(token)
            if norm_token and norm_token in row_text:
                score += 1
                break
    return score


def _detect_header_row(excel_path: Path, sheet_name: int = 0, max_rows: int = 30) -> int:
    """Read raw, scan top max_rows, return 0-based row index with highest header-likeness; require score >= MIN_HEADER_SCORE."""
    df_raw = pd.read_excel(excel_path, sheet_name=sheet_name, header=None, engine="openpyxl")
    if df_raw.empty:
        raise ValueError("Excel sheet is empty")
    n_scan = min(max_rows, len(df_raw))
    best_row, best_score = 0, 0
    for r in range(n_scan):
        row_cells = df_raw.iloc[r].tolist()
        sc = _score_header_row(row_cells)
        if sc > best_score:
            best_score = sc
            best_row = r
    if best_score < MIN_HEADER_SCORE:
        raise ValueError(
            f"Could not detect header row (best score={best_score} at row {best_row}, need >= {MIN_HEADER_SCORE}). "
            "Check that the sheet has column headers like Ticker/Symbol, Entry date, Exit date, Lots."
        )
    logger.info("Detected header at row %d (score=%d)", best_row, best_score)
    return best_row


def _normalize_key_for_mapping(name: str) -> str:
    """Lowercase, strip accents, remove punctuation/extra spaces for column mapping."""
    s = str(name).strip().lower()
    s = _strip_accents(s)
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _map_columns_to_canonical(header_row: int, excel_path: Path) -> Tuple[pd.DataFrame, Dict[str, str]]:
    """
    Use header row to build original_col -> canonical_key. Rename columns; keep unmapped as-is.
    Returns (df with renamed columns where mapped, canonical_column_map).
    """
    df_header = pd.read_excel(excel_path, sheet_name=0, header=header_row, engine="openpyxl")
    if df_header.empty:
        raise ValueError("Sheet has no data after header row")
    canonical_map: Dict[str, str] = {}
    rename: Dict[str, str] = {}
    for orig in df_header.columns:
        orig_str = str(orig).strip()
        norm = _normalize_key_for_mapping(orig_str)
        for canon_key, synonyms in CANONICAL_SYNONYMS.items():
            matched = False
            norm_syns = [_normalize_key_for_mapping(syn) for syn in synonyms]
            for ns in norm_syns:
                if ns and (ns == norm or ns in norm or norm in ns):
                    rename[orig_str] = canon_key
                    canonical_map[orig_str] = canon_key
                    matched = True
                    break
            if matched:
                break
    # Avoid duplicate canonical names: keep first occurrence
    seen: Dict[str, str] = {}
    for orig, canon in list(rename.items()):
        if canon in seen:
            del rename[orig]
        else:
            seen[canon] = orig
    df_renamed = df_header.rename(columns=rename)
    return df_renamed, canonical_map


def _safe_float(val: Any) -> Optional[float]:
    """
    Parse number. VN/EN: "92,730" => thousands separator => 92730;
    "39,092.24" => dot decimal, comma thousands => 39092.24.
    """
    val = _to_native(val)
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace(" ", "")
    if not s:
        return None
    # Thousands separator: 92,730 or 1,234,567.89
    if re.match(r"^\d{1,3}(,\d{3})*(\.\d+)?$", s):
        s = s.replace(",", "")
    # Else comma might be decimal (locale); try remove comma and parse
    elif "," in s and "." not in s and re.match(r"^\d+,\d+$", s):
        s = s.replace(",", ".")
    else:
        s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def _safe_int(val: Any) -> Optional[int]:
    f = _safe_float(val)
    if f is None:
        return None
    try:
        return int(round(f))
    except (ValueError, OverflowError):
        return None


def _to_native(val: Any) -> Any:
    """Coerce pandas NA/NaT/NaN to None; Timestamp/datetime to ISO string for JSON."""
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(val, "strftime"):
        try:
            return val.strftime("%Y-%m-%d") if getattr(val, "hour", 0) == 0 and getattr(val, "minute", 0) == 0 else val.strftime("%Y-%m-%dT%H:%M:%S")
        except Exception:
            return str(val)
    return val


def _parse_date(val: Any) -> Optional[str]:
    """
    Parse date: pandas Timestamp/date, ISO YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY.
    Return canonical YYYY-MM-DD or None.
    """
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
        s = val.strip()[:20]
        # ISO YYYY-MM-DD
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        # DD/MM/YYYY or DD-MM-YYYY
        parts = re.split(r"[/\-.\s]+", s)
        if len(parts) >= 3:
            try:
                a, b, c = int(parts[0]), int(parts[1]), int(parts[2])
                if c >= 1000:  # year in third
                    d, m, y = a, b, c
                elif a >= 1000:  # year first
                    y, m, d = a, b, c
                else:
                    d, m, y = a, b, c
                if y < 100:
                    y += 2000
                if 1 <= m <= 12 and 1 <= d <= 31:
                    return f"{y:04d}-{m:02d}-{d:02d}"
            except (ValueError, IndexError):
                pass
    return None


CANONICAL_KEYS = ("ticker", "entry_date", "exit_date", "entry_price", "exit_price", "lots")


def _canonicalize_row(raw: Dict[str, Any], columns: List[str]) -> Dict[str, Any]:
    """One row: canonicalize types for canonical keys; keep unknown columns as-is or null."""
    out: Dict[str, Any] = {}
    for col in columns:
        val = raw.get(col)
        val = _to_native(val)
        if col == "ticker":
            out[col] = str(val).strip().upper() if val else None
        elif col == "entry_date" or col == "exit_date":
            out[col] = _parse_date(val)
        elif col == "entry_price" or col == "exit_price":
            out[col] = _safe_float(val)
        elif col == "lots":
            out[col] = _safe_int(val)
        else:
            if val is not None and not (isinstance(val, float) and pd.isna(val)):
                out[col] = _to_native(val)
            else:
                out[col] = None
    return out


def _dataframe_to_canonical_list(df: pd.DataFrame) -> List[Dict[str, Any]]:
    columns = list(df.columns)
    rows: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        raw = {c: row.get(c) for c in columns}
        rows.append(_canonicalize_row(raw, columns))
    return rows


def run_import_full(excel_path: Path) -> Path:
    """
    Read Trade History.xlsx: detect header row, map to canonical columns, canonicalize types.
    Write full snapshot to data/raw/trades/. Returns path to trade_history_full.json.
    """
    excel_path = Path(excel_path).resolve()
    if not excel_path.exists():
        raise FileNotFoundError(f"Excel file not found: {excel_path}")

    source_mtime = excel_path.stat().st_mtime
    source_mtime_iso = datetime.fromtimestamp(source_mtime).isoformat() + "Z"

    header_row = _detect_header_row(excel_path, sheet_name=0, max_rows=30)
    df, canonical_column_map = _map_columns_to_canonical(header_row, excel_path)
    if df.empty:
        raise ValueError("Excel sheet has no data rows after header")

    columns = list(df.columns)
    canonical = _dataframe_to_canonical_list(df)
    row_count = len(canonical)

    TRADES_DIR.mkdir(parents=True, exist_ok=True)

    # CSV: canonical + extra columns
    df_out = pd.DataFrame(canonical)
    df_out.to_csv(FULL_CSV, index=False, encoding="utf-8")

    # JSON: array with canonical keys (ticker, entry_date, exit_date, entry_price, exit_price, lots) + extras
    json_text = json.dumps(canonical, ensure_ascii=False, separators=(",", ":"))
    FULL_JSON.write_text(json_text, encoding="utf-8")
    json_hash = hashlib.sha256(json_text.encode()).hexdigest()[:16]

    meta = {
        "source_file_path": str(excel_path),
        "source_file_mtime": source_mtime_iso,
        "imported_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "row_count": row_count,
        "columns": columns,
        "sha256_16": json_hash,
        "detected_header_row_index": header_row,
        "canonical_column_map": canonical_column_map,
    }
    FULL_META.write_text(
        json.dumps(meta, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    logger.info("Imported %d rows from %s (header row %d) -> %s", row_count, excel_path.name, header_row, TRADES_DIR)
    return FULL_JSON


def run_export_month(month: str, full_json_path: Optional[Path] = None) -> Path:
    """
    Filter full trade history by exit_date in month; write data/raw/trade_history_closed.json.
    Uses canonical keys only. Strict: exit_date must be present and within month window.
    """
    from .trade_parse import TRADE_HISTORY_CLOSED_JSON

    path = full_json_path or FULL_JSON
    if not path.exists():
        raise FileNotFoundError(
            "Full trade history not imported. Run import-full first."
        )

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("trade_history_full.json must be a list of trade objects")

    # Require exit_date column: at least one row must have key "exit_date" (canonical)
    if data and isinstance(data[0], dict) and "exit_date" not in data[0]:
        has_exit_date = any(isinstance(r, dict) and "exit_date" in r for r in data)
        if not has_exit_date:
            raise ValueError(
                "exit_date not found after canonical mapping; check header detection/mapping. "
                "Re-run import-full with Trade History.xlsx that has an exit date column (e.g. Exit date, Ngày bán)."
            )

    try:
        y, m = int(month[:4]), int(month[5:7])
    except (ValueError, IndexError):
        raise ValueError(f"Invalid month format: {month} (use YYYY-MM)")

    from calendar import monthrange
    start = f"{month}-01"
    end = f"{month}-{monthrange(y, m)[1]:02d}"

    out: List[Dict[str, Any]] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        exit_d = _parse_date(row.get("exit_date"))
        if not exit_d or not (start <= exit_d <= end):
            continue
        ticker = (row.get("ticker") or row.get("symbol") or "").strip().upper()
        if not ticker:
            continue
        out.append({
            "ticker": ticker,
            "entry_date": _parse_date(row.get("entry_date")),
            "exit_date": exit_d,
            "entry_price": _safe_float(row.get("entry_price")),
            "exit_price": _safe_float(row.get("exit_price")),
            "lots": _safe_int(row.get("lots")),
            "reason_tag": row.get("reason_tag"),
            "exit_tag": row.get("exit_tag"),
        })

    TRADE_HISTORY_CLOSED_JSON.parent.mkdir(parents=True, exist_ok=True)
    TRADE_HISTORY_CLOSED_JSON.write_text(
        json.dumps(out, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Exported %d trades for %s -> %s", len(out), month, TRADE_HISTORY_CLOSED_JSON.name)
    return TRADE_HISTORY_CLOSED_JSON
