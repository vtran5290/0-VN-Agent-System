"""
Legacy-to-normalized adapter: resolve report_snapshot vs latest_market; never derive level from WoW delta.
- report_snapshot_level: market level embedded in the report snapshot (may be stale).
- latest_market_level: freshest available from market data source (KPI uses this when available).
- wow_delta: change metric only; never used to reconstruct level.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parents[2]
DEBUG_SNAPSHOT = REPO / "data" / "decision" / "market_snapshot_debug.json"
LATEST_MARKET_SNAPSHOT = REPO / "data" / "decision" / "latest_market_snapshot.json"
MANUAL_INPUTS = REPO / "data" / "raw" / "manual_inputs.json"
ALERTS = REPO / "data" / "alerts" / "market_flags.json"
REGIME_STATE = REPO / "data" / "state" / "regime_state.json"
DECISION_LOG_DIR = REPO / "decision_log"
SELL_SIGNALS = REPO / "data" / "alerts" / "sell_signals.json"


def _reject_outlier(v: Optional[float], lo: float = 300, hi: float = 3000) -> Optional[float]:
    if v is None or not isinstance(v, (int, float)):
        return v
    f = float(v)
    return None if f > hi or f < lo else f


def _read_json(p: Path) -> Dict[str, Any]:
    from scripts.utils.io import read_json
    return read_json(p)


def resolve_vnindex_level(legacy: Dict[str, Any], asof: str) -> Optional[float]:
    """Current VNINDEX from FireAnt snapshot only; never from delta or manual override when debug exists."""
    dbg = _read_json(DEBUG_SNAPSHOT)
    raw = dbg.get("raw_source") or {}
    mkt = raw.get("market") or {}
    val = mkt.get("vnindex_level")
    if val is not None and isinstance(val, (int, float)):
        return float(val)
    manual = _read_json(MANUAL_INPUTS)
    m = (manual.get("market") or {}) if manual else {}
    val = m.get("vnindex_level")
    if val is not None and isinstance(val, (int, float)):
        return float(val)
    return None


def resolve_vn30_level(legacy: Dict[str, Any], asof: str) -> Optional[float]:
    """Current VN30 from FireAnt snapshot; fallback manual. Never from delta."""
    dbg = _read_json(DEBUG_SNAPSHOT)
    raw = dbg.get("raw_source") or {}
    mkt = raw.get("market") or {}
    val = mkt.get("vn30_level")
    if val is not None and isinstance(val, (int, float)):
        return float(val)
    manual = _read_json(MANUAL_INPUTS)
    m = (manual.get("market") or {}) if manual else {}
    val = m.get("vn30_level")
    if val is not None and isinstance(val, (int, float)):
        return float(val)
    return None


def resolve_distribution_days(legacy: Dict[str, Any], asof: str) -> Optional[int]:
    """Distribution days from FireAnt snapshot or alerts; never from delta."""
    dbg = _read_json(DEBUG_SNAPSHOT)
    raw = dbg.get("raw_source") or {}
    mkt = raw.get("market") or {}
    val = mkt.get("distribution_days_rolling_20")
    if val is not None and isinstance(val, (int, float)):
        return int(val)
    flags = _read_json(ALERTS)
    val = flags.get("distribution_days_rolling_20")
    if val is not None and isinstance(val, (int, float)):
        return int(val)
    manual = _read_json(MANUAL_INPUTS)
    m = (manual.get("market") or {}) if manual else {}
    val = m.get("distribution_days_rolling_20")
    if val is not None and isinstance(val, (int, float)):
        return int(val)
    return None


def resolve_report_snapshot_levels(legacy: Dict[str, Any], asof: str) -> Dict[str, Any]:
    """
    Report snapshot levels: market level embedded in the report snapshot (from market_snapshot_debug).
    May be stale; never labeled as current/latest.
    """
    dbg = _read_json(DEBUG_SNAPSHOT)
    raw = dbg.get("raw_source") or {}
    mkt = raw.get("market") or {}
    manual = _read_json(MANUAL_INPUTS)
    m_manual = (manual.get("market") or {}) if manual else {}
    date_used = dbg.get("asof_date_used") or dbg.get("requested_asof")
    vnindex = mkt.get("vnindex_level") or m_manual.get("vnindex_level")
    vn30 = mkt.get("vn30_level") or m_manual.get("vn30_level")
    dist_days = mkt.get("distribution_days_rolling_20") or _read_json(ALERTS).get("distribution_days_rolling_20") or m_manual.get("distribution_days_rolling_20")
    dist_proxy = mkt.get("dist_proxy_symbol") or m_manual.get("dist_proxy_symbol")
    vnindex = _reject_outlier(float(vnindex) if vnindex is not None else None)
    return {
        "date": date_used,
        "vnindex_level": vnindex,
        "vn30_level": float(vn30) if vn30 is not None else None,
        "distribution_days_rolling_20": int(dist_days) if dist_days is not None else None,
        "dist_proxy_symbol": dist_proxy,
        "source_name": "fireant" if dbg.get("mapped_vnindex_level") is not None else "manual",
    }


def resolve_latest_market_levels(report_snapshot_date: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Latest market levels: freshest available from data/decision/latest_market_snapshot.json.
    Return None when file missing or when latest date is not after report_snapshot_date.
    """
    from scripts.utils.date_utils import is_date_after
    if not LATEST_MARKET_SNAPSHOT.exists():
        return None
    data = _read_json(LATEST_MARKET_SNAPSHOT)
    latest_date = data.get("asof_date") or data.get("date")
    if not latest_date:
        return None
    # Do not gate latest_market on report snapshot date.
    # The KPI selection layer decides whether to display latest vs snapshot and whether it's stale.
    vnindex = data.get("vnindex_level")
    vn30 = data.get("vn30_level")
    vnindex = _reject_outlier(float(vnindex) if vnindex is not None else None)
    return {
        "date": latest_date,
        "vnindex_level": vnindex,
        "vn30_level": float(vn30) if vn30 is not None else None,
        "distribution_days_rolling_20": data.get("distribution_days_rolling_20"),
        "dist_proxy_symbol": data.get("dist_proxy_symbol"),
        "source_name": data.get("source_name", "latest_market_snapshot"),
    }


def _latest_is_fresh_enough(latest_date: Optional[str], report_snapshot_date: Optional[str]) -> bool:
    """
    Only prefer latest_market_snapshot.json when its asof_date is on or after the report snapshot date.
    Otherwise an old file (e.g. 2026-03-13) would override correct FireAnt levels (e.g. 2026-03-28).
    """
    from scripts.utils.date_utils import parse_date
    dl = parse_date(latest_date)
    dr = parse_date(report_snapshot_date)
    if dl is None:
        return False
    if dr is None:
        return True
    return dl >= dr


def resolve_market_levels(legacy: Dict[str, Any], asof: str, report_age_days: Optional[int]) -> Dict[str, Any]:
    """
    Build market_structure with report_snapshot, latest_market, and levels (KPI display).
    KPI uses latest_market when available and not older than report snapshot; otherwise report_snapshot.
    Never derived from what_changed delta.
    """
    report_snapshot = resolve_report_snapshot_levels(legacy, asof)
    report_snapshot_date = report_snapshot.get("date")
    latest_market = resolve_latest_market_levels(report_snapshot_date)

    # KPI display: latest only if fresher/equal to report snapshot date; else FireAnt snapshot wins
    use_latest = (
        latest_market is not None
        and (latest_market.get("vnindex_level") is not None or latest_market.get("vn30_level") is not None)
        and _latest_is_fresh_enough(latest_market.get("date"), report_snapshot_date)
    )
    if use_latest:
        kpi = latest_market.copy()
        kpi_display_source = "latest_market"
        kpi_is_stale = False
        kpi_date = latest_market.get("date")
    else:
        kpi = report_snapshot.copy()
        kpi_display_source = "report_snapshot"
        from scripts.utils.date_utils import report_age_days as days_old
        snap_age = days_old(report_snapshot_date) if report_snapshot_date else None
        kpi_is_stale = (snap_age is not None and snap_age > 3) or (report_age_days is not None and report_age_days > 3)
        kpi_date = report_snapshot_date

    # Dist days: prefer from report_snapshot when latest_market doesn't have it
    dist_days = (kpi.get("distribution_days_rolling_20") if kpi.get("distribution_days_rolling_20") is not None
                 else report_snapshot.get("distribution_days_rolling_20"))

    return {
        "report_snapshot": report_snapshot,
        "latest_market": latest_market,
        "levels": {
            "vnindex_level": kpi.get("vnindex_level"),
            "vn30_level": kpi.get("vn30_level"),
            "distribution_days_rolling_20": dist_days,
            "dist_proxy_symbol": kpi.get("dist_proxy_symbol") or report_snapshot.get("dist_proxy_symbol"),
            "snapshot_date": kpi_date,
            "is_stale": kpi_is_stale,
            "display_mode": "current" if kpi_display_source == "latest_market" else "stale_snapshot",
            "source_name": kpi.get("source_name"),
            "source_confidence": "High" if kpi_display_source == "latest_market" else "Medium",
            "kpi_display_source": kpi_display_source,
            "kpi_is_stale": kpi_is_stale,
        },
    }


def resolve_suggested_regime(legacy: Dict[str, Any], asof: str) -> Optional[str]:
    """From decision_log/{asof}.json; regime_state does not store it."""
    log_path = DECISION_LOG_DIR / f"{asof}.json"
    log = _read_json(log_path)
    return log.get("suggested_regime")


def resolve_mismatch(legacy: Dict[str, Any], asof: str, current_regime: Optional[str]) -> bool:
    """True if suggested_regime != current_regime."""
    suggested = resolve_suggested_regime(legacy, asof)
    if suggested is None or current_regime is None:
        return False
    return suggested != current_regime


def resolve_watchlist_posture(legacy: Dict[str, Any], asof: str) -> str:
    """From risk_flag + regime (same logic as watchlist_updates)."""
    flags = _read_json(ALERTS)
    rf = flags.get("risk_flag", "Unknown")
    rs = _read_json(REGIME_STATE)
    regime = rs.get("regime")
    if rf in ("Elevated", "High"):
        return "Defensive / Reduce new buys"
    if regime == "B":
        return "Selective / Leader-only"
    return "Neutral"


def resolve_sell_trim_signals(legacy: Dict[str, Any], asof: str) -> List[Dict[str, Any]]:
    """From data/alerts/sell_signals.json."""
    data = _read_json(SELL_SIGNALS)
    signals = data.get("signals") or []
    return [s for s in signals if isinstance(s, dict)]


def resolve_portfolio_health(legacy: Dict[str, Any], asof: str) -> Dict[str, Any]:
    """From decision_log/{asof}.json portfolio_health (flat: n_positions, pct_below_ma20, sector_concentration)."""
    log_path = DECISION_LOG_DIR / f"{asof}.json"
    log = _read_json(log_path)
    ph = log.get("portfolio_health") or {}
    if not isinstance(ph, dict):
        return {"summary": {}, "sector_concentration": [], "position_health": []}
    summary = ph.get("summary") if isinstance(ph.get("summary"), dict) else {
        "n_positions": ph.get("n_positions"),
        "pct_below_ma20": ph.get("pct_below_ma20"),
        "pct_sell_trim_active": ph.get("pct_sell_trim_active"),
        "avg_r_multiple_open": ph.get("avg_r_multiple_open"),
    }
    sector_concentration = ph.get("sector_concentration") or []
    return {
        "summary": summary or {},
        "sector_concentration": sector_concentration,
        "position_health": ph.get("position_health") or [],
    }


def resolve_dist_risk_composite(legacy: Dict[str, Any], asof: str) -> Optional[str]:
    """From alerts or FireAnt snapshot."""
    flags = _read_json(ALERTS)
    if flags.get("risk_flag"):
        return flags["risk_flag"]
    dbg = _read_json(DEBUG_SNAPSHOT)
    raw = dbg.get("raw_source") or {}
    mkt = raw.get("market") or {}
    return mkt.get("dist_risk_composite")
