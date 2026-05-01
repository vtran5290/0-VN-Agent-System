# src/macro/fred_fetch_us_fiscal_stress.py — FRED ingestion for US_FISCAL_STRESS pack
"""
Fetch US macro series from FRED, write snapshot + derived us_fiscal_inputs for the engine.
Requires FRED_API_KEY. Cache: data/cache/fred/<series_id>_<end_date>.json, TTL 24h; use --force to bypass.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from src.macro.fred_client import FREDClient, REPO_ROOT

SNAPSHOT_PATH = REPO_ROOT / "data" / "sources" / "macro" / "fred_us_fiscal_stress_snapshot.json"
DERIVED_PATH = REPO_ROOT / "data" / "features" / "macro" / "us_fiscal_inputs.json"
FRED_SERIES_BASE = "https://fred.stlouisfed.org/series"

# Required + optional series for US fiscal stress
SERIES_REQUIRED = [
    "DGS10",   # 10-Year Treasury Constant Maturity Rate
    "DGS30",   # 30-Year Treasury Constant Maturity Rate
    "DGS2",    # 2-Year Treasury Constant Maturity Rate
    "SOFR",    # Secured Overnight Financing Rate
    "FYFSGDA188S",  # Federal Surplus or Deficit [-] as % of GDP
]
SERIES_OPTIONAL = [
    "T10YIE",       # 10-Year Breakeven Inflation Rate
    "FEDFUNDS",     # Federal Funds Rate
    "THREEFYTP10",  # 10-Year Treasury Term Premium (Kim-Wright, FRED)
]


def _fetch_one(
    client: FREDClient,
    series_id: str,
    end_date: str,
) -> dict:
    """Fetch one series; return record with status 'ok' or 'error'. Sorted keys for determinism. Includes series_title for audit/guards."""
    out: dict = {
        "observation_date": None,
        "series_id": series_id,
        "series_title": None,
        "source_url": f"{FRED_SERIES_BASE}/{series_id}",
        "units": None,
        "frequency": None,
        "latest_value": None,
    }
    try:
        info = client.get_series_info(series_id)
        if info:
            out["units"] = info.get("units")
            out["frequency"] = info.get("frequency")
            out["series_title"] = info.get("title")
        value, obs_date = client.get_latest_observation(series_id, end_date=end_date)
        if value is not None and obs_date:
            out["latest_value"] = round(value, 6)
            out["observation_date"] = obs_date
            out["status"] = "ok"
        else:
            out["status"] = "error"
            out["error"] = "no_valid_observation"
    except Exception as e:
        out["status"] = "error"
        out["error"] = str(e)
    return dict(sorted(out.items()))


def run_fetch(asof: str | None, force: bool) -> dict:
    """Fetch all series, build snapshot dict. asof: YYYY-MM-DD or None for today UTC."""
    if asof:
        end_date = asof
    else:
        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    asof_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat() + "Z"
    try:
        client = FREDClient(force=force)
    except ValueError as e:
        raise SystemExit(f"Config: {e}") from e

    series_ids = SERIES_REQUIRED + SERIES_OPTIONAL
    series_results = []
    for sid in series_ids:
        rec = _fetch_one(client, sid, end_date)
        series_results.append(rec)

    # Policy delta 3m: SOFR (preferred) and FEDFUNDS need value ~90 days ago
    for rec in series_results:
        if rec.get("series_id") not in ("SOFR", "FEDFUNDS"):
            continue
        try:
            val_3m, date_3m = client.get_observation_n_days_ago(rec["series_id"], end_date, n_days=90)
            rec["latest_value_3m_ago"] = round(val_3m, 6) if val_3m is not None else None
            rec["observation_date_3m_ago"] = date_3m
        except Exception:
            rec["latest_value_3m_ago"] = None
            rec["observation_date_3m_ago"] = None

    snapshot = {
        "asof_date": asof_iso,
        "end_date": end_date,
        "series": series_results,
        "source": "FRED",
    }
    return snapshot


def write_snapshot(snapshot: dict, path: Path | None = None) -> None:
    path = path or SNAPSHOT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, sort_keys=True)


def _term_premium_series_ok(rec: dict | None) -> bool:
    """Guard: series_title must suggest 10Y term premium; else do not use for pack."""
    if not rec:
        return False
    title = (rec.get("series_title") or "").lower()
    return "term premium" in title and ("10-year" in title or "10 year" in title)


def _policy_from_series(by_id: dict, prefer_sofr: bool = True) -> tuple[float | None, str, str | None, str | None]:
    """policy_delta_3m_bps, policy_stance, policy_stance_source (SOFR|FEDFUNDS), observation_date_3m_ago."""
    candidates = [("SOFR", "SOFR"), ("FEDFUNDS", "FEDFUNDS")] if prefer_sofr else [("FEDFUNDS", "FEDFUNDS"), ("SOFR", "SOFR")]
    for sid, source in candidates:
        rec = by_id.get(sid)
        if not rec or rec.get("status") != "ok":
            continue
        latest = rec.get("latest_value")
        val_3m = rec.get("latest_value_3m_ago")
        date_3m = rec.get("observation_date_3m_ago")
        if latest is None or val_3m is None:
            continue
        delta_bps = round((float(latest) - float(val_3m)) * 100.0, 1)  # % → bps
        stance = "tightening" if delta_bps > 25 else "easing" if delta_bps < -25 else "neutral"
        return delta_bps, stance, source, date_3m
    return None, "neutral", None, None


def build_derived(snapshot: dict) -> dict:
    """Build us_fiscal_inputs.json compatible with US_FISCAL_STRESS pack. Missing → null.
    Dalio: term_premium guard; real_rates.real_10y_proxy_pct; policy (policy_delta_3m_bps, policy_stance).
    """
    by_id = {r["series_id"]: r for r in snapshot.get("series", [])}
    def _val(sid: str) -> float | None:
        rec = by_id.get(sid)
        if not rec or rec.get("status") != "ok":
            return None
        return rec.get("latest_value")

    dgs10 = _val("DGS10")
    t10yie = _val("T10YIE")
    tp10_rec = by_id.get("THREEFYTP10")
    tp10 = _val("THREEFYTP10")
    real_10y_proxy: float | None = None
    if dgs10 is not None and t10yie is not None:
        real_10y_proxy = round(dgs10 - t10yie, 4)
    term_premium_bps: float | None = None
    term_premium_series_suspect = False
    if tp10 is not None:
        if _term_premium_series_ok(tp10_rec):
            term_premium_bps = round(tp10 * 100.0, 2)
        else:
            term_premium_bps = None
            term_premium_series_suspect = True

    policy_delta_bps, policy_stance, policy_stance_source, obs_date_3m = _policy_from_series(by_id)
    end_date = snapshot.get("end_date")
    days_gap_actual: int | None = None
    policy_3m_window_suspect = False
    if end_date and obs_date_3m:
        try:
            from datetime import datetime as dt
            end_d = dt.strptime(end_date, "%Y-%m-%d").date()
            obs_d = dt.strptime(obs_date_3m, "%Y-%m-%d").date()
            days_gap_actual = (end_d - obs_d).days
            if days_gap_actual < 70 or days_gap_actual > 120:
                policy_3m_window_suspect = True
        except Exception:
            days_gap_actual = None
            policy_3m_window_suspect = True

    out: dict = {
        "asof_date": snapshot.get("asof_date"),
        "source": "fred_fetch_us_fiscal_stress",
        "yields": {
            "ust_2y_yield_pct": _val("DGS2"),
            "ust_10y_yield_pct": dgs10,
            "ust_30y_yield_pct": _val("DGS30"),
        },
        "term_premium": {
            "ust_10y_term_premium_bps": term_premium_bps,
        },
        "funding_stress": {
            "sofr_value": _val("SOFR"),
        },
        "fiscal_path": {
            "primary_deficit_pct_gdp": _val("FYFSGDA188S"),
        },
        "usd": {
            "dxy_trend": "unknown",
        },
        "policy": {
            "policy_stance": policy_stance,
            "policy_delta_3m_bps": policy_delta_bps,
            "policy_stance_source": policy_stance_source,
            "policy_delta_3m_method": "nearest_in_window",
            "days_gap_actual": days_gap_actual,
        },
    }
    if term_premium_series_suspect:
        out["flags"] = out.get("flags", []) + ["term_premium_series_suspect"]
    if policy_3m_window_suspect:
        out["flags"] = out.get("flags", []) + ["policy_3m_window_suspect"]
    if real_10y_proxy is not None:
        out["real_rates"] = {"real_10y_proxy_pct": real_10y_proxy}
    return out


def write_derived(derived: dict, path: Path | None = None) -> None:
    path = path or DERIVED_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(derived, f, indent=2, sort_keys=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch FRED series for US fiscal stress; write snapshot + derived inputs.")
    parser.add_argument("--asof", type=str, default=None, help="End date YYYY-MM-DD (default: today UTC)")
    parser.add_argument("--force", action="store_true", help="Bypass cache TTL")
    parser.add_argument("--snapshot", type=str, default=None, help=f"Override snapshot path (default: {SNAPSHOT_PATH})")
    parser.add_argument("--derived", type=str, default=None, help=f"Override derived path (default: {DERIVED_PATH})")
    args = parser.parse_args()

    snapshot = run_fetch(args.asof, args.force)
    snap_path = Path(args.snapshot) if args.snapshot else SNAPSHOT_PATH
    write_snapshot(snapshot, snap_path)

    derived = build_derived(snapshot)
    der_path = Path(args.derived) if args.derived else DERIVED_PATH
    write_derived(derived, der_path)

    ok = sum(1 for r in snapshot["series"] if r.get("status") == "ok")
    print(f"Wrote {snap_path} ({ok}/{len(snapshot['series'])} series ok)")
    print(f"Wrote {der_path}")
    print(f"asof_date={snapshot['asof_date']} end_date={snapshot['end_date']}")


if __name__ == "__main__":
    main()
