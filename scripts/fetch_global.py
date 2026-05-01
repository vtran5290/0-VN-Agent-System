"""
Fetch global macro with explicit semantics and a machine-readable metric audit.

Rules (verified):
- Never map FRED DTWEXBGS to ICE DXY. DTWEXBGS → `usd_broad_index_fred` only.
- `dxy_reconstructed`: FRED H.10 FX (6 series) + ICE geometric weights (derived; not licensed ICE print).
- `dxy_third_party`: optional Yahoo DX-Y.NYB quote/chart proxy (not official ICE; not substituted for reconstructed).
- `dxy_ice_official`: only when env/manual licensed feed supplies it; never silently filled from broad or reconstructed.
- Legacy `global.dxy` = `dxy_reconstructed` if present else `dxy_third_party_proxy` (never DTWEXBGS).
- CPI YoY: prefer official BLS CPI-U SA (CUUR0000SA0); includes cpi_reference_month.
- PAYEMS: expose level (thousands) and month-over-month change (persons); do not use level as "NFP change".
- UST: FRED DGS2/DGS10 with observation date (Treasury/FRED daily series).
"""
from __future__ import annotations

import logging
import os
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

REPO_ROOT = str(__import__("pathlib").Path(__file__).resolve().parent.parent)


def _ice_official_from_env() -> Tuple[Optional[float], Optional[str]]:
    """Optional licensed ICE/NYSE-style print supplied by operator (never auto-filled)."""
    raw = (os.getenv("ICE_DXY_OFFICIAL_VALUE") or "").strip()
    vd = (os.getenv("ICE_DXY_OFFICIAL_VALUE_DATE") or "").strip()
    if not raw or not vd:
        return None, None
    try:
        return float(raw), vd[:10]
    except ValueError:
        return None, None


def _fred_series_with_date(series_id: str, api_key: str, end: str, days_back: int = 45) -> Optional[Tuple[str, float]]:
    try:
        import sys
        if REPO_ROOT not in sys.path:
            sys.path.insert(0, REPO_ROOT)
        from src.intake.fred_api import latest_observation_with_date

        return latest_observation_with_date(series_id, api_key, end, days_back=days_back)
    except Exception as e:
        logger.warning("FRED %s: %s", series_id, e)
        return None


def _payems(api_key: str, end: str) -> Optional[Dict[str, Any]]:
    try:
        import sys
        if REPO_ROOT not in sys.path:
            sys.path.insert(0, REPO_ROOT)
        from src.intake.fred_api import payems_level_and_mom_change_persons

        return payems_level_and_mom_change_persons(api_key, end)
    except Exception as e:
        logger.warning("FRED PAYEMS: %s", e)
        return None


def _dxy_yahoo_quote_html() -> Tuple[Optional[float], Optional[str], str]:
    """Yahoo Finance quote page for DX-Y.NYB (regex + fin-streamer); 429 retry per macro agent."""
    try:
        import sys

        if REPO_ROOT not in sys.path:
            sys.path.insert(0, REPO_ROOT)
        from src.intake.yahoo_dxy_quote import fetch_dxy_yahoo_quote_page

        p, _prev, vd, logs = fetch_dxy_yahoo_quote_page()
        if p is not None:
            return round(float(p), 4), vd, "ok"
        if any("yahoo_429" in x for x in logs):
            return None, None, "yahoo_429"
        return None, None, "yahoo_quote_failed"
    except Exception as e:
        logger.warning("Yahoo quote DXY: %s", e)
        return None, None, "yahoo_quote_failed"


def _dxy_yahoo_ice(end: str) -> Tuple[Optional[float], Optional[str], str]:
    try:
        import requests

        url = "https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        j = r.json()
        chart = j.get("chart", {}).get("result", [{}])[0]
        regular = chart.get("indicators", {}).get("quote", [{}])[0]
        closes = regular.get("close", [])
        if not closes:
            return None, None, "yahoo_empty"
        last = [c for c in closes if c is not None]
        if not last:
            return None, None, "yahoo_empty"
        # Yahoo returns last bar date in meta
        meta = chart.get("meta", {}) or {}
        ts = meta.get("regularMarketTime") or meta.get("chartPreviousClose")
        vd = None
        if isinstance(ts, (int, float)):
            from datetime import datetime, timezone

            vd = datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")
        return round(float(last[-1]), 4), vd, "ok"
    except Exception as e:
        logger.warning("Yahoo ICE DXY: %s", e)
        return None, None, "yahoo_failed"


def _sanitize_dxy_third_party(v: Optional[float]) -> Tuple[Optional[float], Optional[str]]:
    """
    Guard against malformed Yahoo parse outliers.
    DX-Y.NYB should usually be around DXY-like magnitudes, not hundreds/thousands.
    """
    if v is None:
        return None, None
    fv = float(v)
    if not (60.0 <= fv <= 140.0):
        return None, "yahoo_outlier_rejected"
    return round(fv, 4), None


def _metric(
    *,
    metric_key: str,
    semantic_label: str,
    source_name: str,
    source_series_code_or_page: str,
    source_type: str,
    units: str,
    value: Any,
    value_date: Optional[str],
    release_date: Optional[str],
    as_of_date: str,
    fetch_status: str,
    verification_status: str,
    stale_policy: str = "fail_closed_if_wrong_semantics",
    notes: str = "",
    previous_value: Any = None,
) -> Dict[str, Any]:
    return {
        "metric_key": metric_key,
        "semantic_label": semantic_label,
        "source_name": source_name,
        "source_series_code_or_page": source_series_code_or_page,
        "source_type": source_type,
        "units": units,
        "value": value,
        "previous_value": previous_value,
        "value_date": value_date,
        "release_date": release_date,
        "as_of_date": as_of_date,
        "fetch_status": fetch_status,
        "verification_status": verification_status,
        "stale_policy": stale_policy,
        "notes": notes,
    }


def fetch_global(asof: str | None = None) -> Dict[str, Any]:
    """
    Return {"global": {...values...}, "global_metrics_audit": [MetricRecord-like dicts, ...]}.
    Legacy keys in global kept where still used by weekly; new explicit keys added.
    """
    if asof is None:
        asof = date.today().isoformat()
    key = os.getenv("FRED_API_KEY")
    audit: List[Dict[str, Any]] = []
    g: Dict[str, Any] = {}

    # --- UST (FRED daily; value_date = observation date) ---
    if key:
        u2 = _fred_series_with_date("DGS2", key, asof)
        u10 = _fred_series_with_date("DGS10", key, asof)
        if u2:
            g["ust_2y"], g["ust_2y_value_date"] = u2[1], u2[0]
            g["ust_yield_basis"] = "fred_dgs_daily_observation"
            audit.append(
                _metric(
                    metric_key="ust_2y",
                    semantic_label="US Treasury 2Y yield (FRED DGS2, daily observation)",
                    source_name="FRED",
                    source_series_code_or_page="DGS2",
                    source_type="official_release",
                    units="percent",
                    value=u2[1],
                    value_date=u2[0],
                    release_date=None,
                    as_of_date=asof,
                    fetch_status="ok",
                    verification_status="parsed",
                    notes="FRED business-day series; value_date is observation date, not market session label.",
                )
            )
        if u10:
            g["ust_10y"], g["ust_10y_value_date"] = u10[1], u10[0]
            if "ust_yield_basis" not in g:
                g["ust_yield_basis"] = "fred_dgs_daily_observation"
            audit.append(
                _metric(
                    metric_key="ust_10y",
                    semantic_label="US Treasury 10Y yield (FRED DGS10, daily observation)",
                    source_name="FRED",
                    source_series_code_or_page="DGS10",
                    source_type="official_release",
                    units="percent",
                    value=u10[1],
                    value_date=u10[0],
                    release_date=None,
                    as_of_date=asof,
                    fetch_status="ok",
                    verification_status="parsed",
                )
            )

        # --- Nominal broad dollar (NOT ICE DXY) ---
        broad = _fred_series_with_date("DTWEXBGS", key, asof, days_back=60)
        if broad:
            g["usd_broad_index_fred"] = broad[1]
            g["usd_broad_index_fred_value_date"] = broad[0]
            audit.append(
                _metric(
                    metric_key="usd_broad_index_fred",
                    semantic_label="Nominal Broad U.S. Dollar Index (FRED DTWEXBGS)",
                    source_name="FRED",
                    source_series_code_or_page="DTWEXBGS",
                    source_type="official_release",
                    units="index",
                    value=broad[1],
                    value_date=broad[0],
                    release_date=None,
                    as_of_date=asof,
                    fetch_status="ok",
                    verification_status="parsed",
                    notes="NOT the ICE US Dollar Index (DXY). Do not display as DXY.",
                )
            )

        # --- PAYEMS: level + MoM change ---
        pe = _payems(key, asof)
        if pe:
            g["nonfarm_payroll_level_thousands"] = pe["nonfarm_payroll_level_thousands"]
            g["nonfarm_payroll_change_persons"] = pe["nonfarm_payroll_change_persons"]
            g["payems_level_date"] = pe["payems_level_date"]
            g["payems_prior_level_date"] = pe["payems_prior_level_date"]
            audit.append(
                _metric(
                    metric_key="nonfarm_payroll_level_thousands",
                    semantic_label="Nonfarm payroll employment level (PAYEMS, thousands of persons)",
                    source_name="FRED",
                    source_series_code_or_page="PAYEMS",
                    source_type="official_release",
                    units="thousands_of_persons",
                    value=pe["nonfarm_payroll_level_thousands"],
                    value_date=pe["payems_level_date"],
                    release_date=None,
                    as_of_date=asof,
                    fetch_status="ok",
                    verification_status="parsed",
                )
            )
            audit.append(
                _metric(
                    metric_key="nonfarm_payroll_change_persons",
                    semantic_label="Nonfarm payroll month-over-month change (derived from PAYEMS levels)",
                    source_name="FRED",
                    source_series_code_or_page="PAYEMS",
                    source_type="derived",
                    units="persons",
                    value=pe["nonfarm_payroll_change_persons"],
                    value_date=pe["payems_level_date"],
                    release_date=None,
                    as_of_date=asof,
                    fetch_status="ok",
                    verification_status="parsed",
                    notes="(L_t - L_{t-1}) * 1000; PAYEMS stored in thousands.",
                )
            )
    else:
        logger.warning("FRED_API_KEY not set; UST/broad/PAYEMS/CPI(FRED fallback) unavailable")

    # Explicit: legacy `nfp` must not carry PAYEMS level as if it were monthly change
    g["nfp"] = None

    # --- CPI YoY: BLS official ---
    try:
        import sys
        if REPO_ROOT not in sys.path:
            sys.path.insert(0, REPO_ROOT)
        from src.intake.bls_cpi import fetch_cpi_u_yoy_official

        bls = fetch_cpi_u_yoy_official(end_year=date.fromisoformat(asof[:10]).year)
    except Exception as e:
        logger.warning("BLS CPI: %s", e)
        bls = None

    if bls and bls.get("fetch_status") == "ok" and bls.get("cpi_yoy") is not None:
        g["cpi_yoy"] = bls["cpi_yoy"]
        g["cpi_reference_month"] = bls.get("cpi_reference_month")
        g["cpi_source"] = "bls"
        g["cpi_value_date"] = bls.get("value_date")
        audit.append(
            _metric(
                metric_key="cpi_yoy",
                semantic_label="CPI-U All Items YoY % (BLS official series, SA)",
                source_name="BLS",
                source_series_code_or_page=str(bls.get("source_series") or "CUUR0000SA0"),
                source_type="official_release",
                units="percent_yoy",
                value=bls["cpi_yoy"],
                value_date=str(bls.get("value_date") or bls.get("cpi_reference_month") or ""),
                release_date=bls.get("release_date"),
                as_of_date=asof,
                fetch_status="ok",
                verification_status="parsed",
                notes="YoY from latest BLS index vs same month prior year. value_date is index reference month (YYYY-MM).",
            )
        )
    elif key:
        # Fail-closed: do not silently use FRED-derived CPI if BLS path failed, unless explicitly needed
        import sys
        if REPO_ROOT not in sys.path:
            sys.path.insert(0, REPO_ROOT)
        from src.intake.fred_api import cpi_yoy as _fred_cpi_yoy

        fv = _fred_cpi_yoy(key, asof)
        if fv is not None:
            g["cpi_yoy"] = fv
            g["cpi_source"] = "fred_cpiau_derived"
            g["cpi_reference_month"] = None
            audit.append(
                _metric(
                    metric_key="cpi_yoy",
                    semantic_label="CPI YoY derived from FRED CPIAUCSL (NOT BLS press release table)",
                    source_name="FRED",
                    source_series_code_or_page="CPIAUCSL",
                    source_type="derived",
                    units="percent_yoy",
                    value=fv,
                    value_date=None,
                    release_date=None,
                    as_of_date=asof,
                    fetch_status="fallback_used",
                    verification_status="unverified_official_month",
                    notes="BLS API failed or returned incomplete; using FRED index YoY — label must not be called official BLS release.",
                )
            )

    # --- DXY reconstructed: FRED H.10 FX × ICE geometric weights (derived; not licensed ICE print) ---
    g["dxy_reconstructed"] = None
    g["dxy_reconstructed_value_date"] = None
    if key:
        try:
            import sys

            if REPO_ROOT not in sys.path:
                sys.path.insert(0, REPO_ROOT)
            from src.intake.dxy_reconstructed import fetch_dxy_reconstructed_fred

            rec = fetch_dxy_reconstructed_fred(key, asof)
        except Exception as e:
            logger.warning("dxy_reconstructed fetch: %s", e)
            rec = None
        if rec:
            g["dxy_reconstructed"] = rec["dxy_reconstructed"]
            g["dxy_reconstructed_value_date"] = rec["dxy_reconstructed_value_date"]
            audit.append(
                _metric(
                    metric_key="dxy_reconstructed",
                    semantic_label="US Dollar Index reconstructed from 6 FX spots (ICE-style weights; FRED H.10)",
                    source_name="FRED",
                    source_series_code_or_page="DEXUSEU+DEXJPUS+DEXUSUK+DEXCAUS+DEXSDUS+DEXSZUS",
                    source_type="derived",
                    units="index",
                    value=rec["dxy_reconstructed"],
                    value_date=rec["dxy_reconstructed_value_date"],
                    release_date=None,
                    as_of_date=asof,
                    fetch_status="ok",
                    verification_status="parsed",
                    notes="Derived from public methodology (geometric weighted product + 50.14348112). Not a licensed ICE/NYSE official closing level.",
                )
            )
        else:
            audit.append(
                _metric(
                    metric_key="dxy_reconstructed",
                    semantic_label="US Dollar Index reconstructed from 6 FX spots (ICE-style weights; FRED H.10)",
                    source_name="FRED",
                    source_series_code_or_page="DEXUSEU+DEXJPUS+DEXUSUK+DEXCAUS+DEXSDUS+DEXSZUS",
                    source_type="derived",
                    units="index",
                    value=None,
                    value_date=None,
                    release_date=None,
                    as_of_date=asof,
                    fetch_status="failed",
                    verification_status="fail_closed",
                    notes="Could not align all 6 FRED H.10 series on a common date.",
                )
            )
    else:
        audit.append(
            _metric(
                metric_key="dxy_reconstructed",
                semantic_label="US Dollar Index reconstructed from 6 FX spots (ICE-style weights; FRED H.10)",
                source_name="FRED",
                source_series_code_or_page="DEXUSEU+DEXJPUS+DEXUSUK+DEXCAUS+DEXSDUS+DEXSZUS",
                source_type="derived",
                units="index",
                value=None,
                value_date=None,
                release_date=None,
                as_of_date=asof,
                fetch_status="skipped",
                verification_status="no_api_key",
                notes="FRED_API_KEY missing.",
            )
        )

    # --- Optional: operator-supplied licensed / official ICE print (never auto-derived) ---
    g["dxy_ice_official"] = None
    g["dxy_ice_official_value_date"] = None
    off_v, off_d = _ice_official_from_env()
    if off_v is not None and off_d:
        g["dxy_ice_official"] = float(off_v)
        g["dxy_ice_official_value_date"] = off_d
        audit.append(
            _metric(
                metric_key="dxy_ice_official",
                semantic_label="ICE U.S. Dollar Index — operator-supplied official/closing level (not auto-filled)",
                source_name="env",
                source_series_code_or_page="ICE_DXY_OFFICIAL_VALUE",
                source_type="official_release",
                units="index",
                value=float(off_v),
                value_date=off_d,
                release_date=None,
                as_of_date=asof,
                fetch_status="ok",
                verification_status="manual_or_licensed",
                notes="Set ICE_DXY_OFFICIAL_VALUE and ICE_DXY_OFFICIAL_VALUE_DATE; pipeline does not fetch licensed ICE feeds.",
            )
        )

    # --- Third-party market proxy (Yahoo DX-Y.NYB): cross-check only; not ICE official ---
    dxy_val, dxy_vd, y_status = _dxy_yahoo_quote_html()
    dxy_source = "Yahoo"
    dxy_page = "DX-Y.NYB"
    if dxy_val is None:
        dxy_val, dxy_vd, y_status = _dxy_yahoo_ice(asof)

    dxy_val, dxy_reject_reason = _sanitize_dxy_third_party(dxy_val)
    if dxy_reject_reason:
        y_status = dxy_reject_reason
    g["dxy_third_party_proxy"] = float(dxy_val) if dxy_val is not None else None
    g["dxy_third_party_value_date"] = dxy_vd
    g["dxy_ice_value_date"] = dxy_vd  # backward compat: was third-party quote date

    if dxy_val is not None:
        audit.append(
            _metric(
                metric_key="dxy_third_party",
                semantic_label="Third-party DXY futures proxy (Yahoo DX-Y.NYB; not licensed ICE index)",
                source_name=dxy_source,
                source_series_code_or_page=dxy_page,
                source_type="market_close",
                units="index",
                value=float(dxy_val),
                value_date=dxy_vd,
                release_date=None,
                as_of_date=asof,
                fetch_status="ok" if y_status == "ok" else y_status,
                verification_status="parsed",
                notes="Cross-check only. Not substituted for dxy_reconstructed or usd_broad_index_fred.",
            )
        )
    else:
        audit.append(
            _metric(
                metric_key="dxy_third_party",
                semantic_label="Third-party DXY proxy (Yahoo DX-Y.NYB)",
                source_name="none",
                source_series_code_or_page="DX-Y.NYB",
                source_type="market_close",
                units="index",
                value=None,
                value_date=None,
                release_date=None,
                as_of_date=asof,
                fetch_status="failed",
                verification_status="fail_closed",
                notes="Yahoo quote/chart unavailable; use dxy_reconstructed (FRED FX) or optional ICE_DXY_OFFICIAL_* env.",
            )
        )

    # Legacy `global.dxy`: primary display driver for WoW — reconstructed first, then third-party; never DTWEXBGS.
    if g.get("dxy_reconstructed") is not None:
        g["dxy"] = float(g["dxy_reconstructed"])
    elif g.get("dxy_third_party_proxy") is not None:
        g["dxy"] = float(g["dxy_third_party_proxy"])
    else:
        g["dxy"] = None

    # Runtime semantic guards on audit we control
    try:
        import sys
        if REPO_ROOT not in sys.path:
            sys.path.insert(0, REPO_ROOT)
        from src.metrics.registry import assert_no_dtwexbgs_labeled_dxy, assert_payroll_level_not_labeled_nfp_change

        assert_no_dtwexbgs_labeled_dxy(audit)
        assert_payroll_level_not_labeled_nfp_change(audit)
    except ValueError as e:
        logger.error("Metric audit semantic validation failed: %s", e)
        raise

    return {"global": g, "global_metrics_audit": audit}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    r = fetch_global()
    for k, v in r.get("global", {}).items():
        print(f"  {k}: {v}")
    print("audit rows:", len(r.get("global_metrics_audit") or []))
