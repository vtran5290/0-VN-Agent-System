"""Single source of truth loader for current portfolio NAV and positions.

NAV and current holdings are user-updated independently.
Port = current stock holdings / open positions only — excludes cash.
NAV is a separate user-updated reference number; never inferred from positions + cash.

Update data/trading/live/portfolio_state.json when NAV or positions change.
Every workflow reads from this file; no other code should hardcode NAV.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import pandas as pd

log = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parents[2]

# Source priority for portfolio state
PORTFOLIO_STATE_PATH = REPO / "data/trading/live/portfolio_state.json"

# Fallback position sources (in priority order after portfolio_state.json)
_POSITIONS_FALLBACK_CSV = REPO / "data/trading/live/current_positions.csv"
_POSITIONS_DERIVED_JSON = REPO / "data/raw/current_positions_derived.json"
_HOLDINGS_TXT = REPO / "data/trading/holdings.txt"


def load_portfolio_state(path: Optional[Path] = None) -> dict:
    """Load portfolio_state.json. Returns {} with a log warning if missing."""
    p = Path(path) if path else PORTFOLIO_STATE_PATH
    if not p.exists():
        log.warning("Portfolio state file missing — NAV/current port context not available: %s", p)
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("Failed to read portfolio state %s: %s", p, e)
        return {}


def get_current_nav_vnd(state: Optional[dict] = None) -> Optional[float]:
    """Return nav_vnd from portfolio state. Returns None if missing or invalid.

    Never infers NAV from cash + positions.
    """
    if state is None:
        state = load_portfolio_state()
    raw = state.get("nav_vnd")
    if raw is None:
        log.warning("NAV missing or invalid in portfolio state.")
        return None
    try:
        v = float(raw)
        if v <= 0:
            log.warning("NAV missing or invalid in portfolio state (value <= 0).")
            return None
        return v
    except (TypeError, ValueError):
        log.warning("NAV missing or invalid in portfolio state: %r", raw)
        return None


def get_positions_path(state: Optional[dict] = None) -> Optional[Path]:
    """Return the resolved positions_path from portfolio state. None if not set."""
    if state is None:
        state = load_portfolio_state()
    raw = state.get("positions_path")
    if not raw:
        return None
    p = Path(raw)
    if not p.is_absolute():
        p = REPO / p
    return p


def load_current_positions(state: Optional[dict] = None) -> tuple[pd.DataFrame, str]:
    """Load current stock positions. Returns (DataFrame, source_label).

    Source priority:
    1. positions_path defined in portfolio_state.json
    2. data/trading/live/current_positions.csv
    3. data/raw/current_positions_derived.json
    4. data/trading/holdings.txt (symbol list only — no position detail)
    5. Empty DataFrame if nothing found

    Port excludes cash. Cash is NOT a position row.
    Returns (empty_df, "missing") with a warning if nothing found.
    """
    if state is None:
        state = load_portfolio_state()

    # Priority 1: positions_path from portfolio_state.json
    pos_path = get_positions_path(state)
    if pos_path and pos_path.exists():
        df = _read_positions_file(pos_path)
        if df is not None:
            return df, str(pos_path.relative_to(REPO) if pos_path.is_relative_to(REPO) else pos_path)

    # Priority 2: data/trading/live/current_positions.csv
    if _POSITIONS_FALLBACK_CSV.exists():
        df = _read_positions_file(_POSITIONS_FALLBACK_CSV)
        if df is not None:
            return df, str(_POSITIONS_FALLBACK_CSV.relative_to(REPO))

    # Priority 3: data/raw/current_positions_derived.json
    if _POSITIONS_DERIVED_JSON.exists():
        df = _read_positions_file(_POSITIONS_DERIVED_JSON)
        if df is not None:
            return df, str(_POSITIONS_DERIVED_JSON.relative_to(REPO))

    # Priority 4: data/trading/holdings.txt (symbols only)
    if _HOLDINGS_TXT.exists():
        syms = []
        for line in _HOLDINGS_TXT.read_text(encoding="utf-8").splitlines():
            s = line.strip().upper()
            if s and not s.startswith("#"):
                syms.append(s)
        if syms:
            log.warning(
                "Using legacy holdings.txt fallback — consider updating "
                "portfolio_state.json positions_path."
            )
            return pd.DataFrame({"symbol": syms}), str(_HOLDINGS_TXT.relative_to(REPO))

    log.warning("Current positions file missing — duplicate-position check not performed.")
    return pd.DataFrame(), "missing"


def _read_positions_file(path: Path) -> Optional[pd.DataFrame]:
    """Read a positions file (CSV or JSON). Returns None on error."""
    try:
        if path.suffix.lower() == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                df = pd.DataFrame(data)
            elif isinstance(data, dict):
                # Single position or wrapper dict
                df = pd.DataFrame([data])
            else:
                return None
            # Normalize ticker → symbol
            if "ticker" in df.columns and "symbol" not in df.columns:
                df = df.rename(columns={"ticker": "symbol"})
            if "symbol" in df.columns:
                df["symbol"] = df["symbol"].astype(str).str.upper().str.strip()
            return df
        else:
            df = pd.read_csv(path)
            if "symbol" not in df.columns:
                # Try common alternatives
                for alt in ("ticker", "Ticker", "Symbol", "SYMBOL"):
                    if alt in df.columns:
                        df = df.rename(columns={alt: "symbol"})
                        break
            if "symbol" in df.columns:
                df["symbol"] = df["symbol"].astype(str).str.upper().str.strip()
            return df
    except Exception as e:
        log.warning("Failed to read positions file %s: %s", path, e)
        return None
