from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Any, Dict, List, Optional, Tuple

from .io import FundRecord
from .scoring import (
    compute_crowding_score,
    compute_policy_alignment_score,
    compute_regime_bias,
    compute_risk_on_score,
)


@dataclass
class TickerStats:
    ticker: str
    n_top5: int
    n_top10: int
    funds_top10: List[str]
    weights_top10: List[float]


@dataclass
class SectorStats:
    sector: str
    weights: List[float]


def _fund_id(fr: FundRecord) -> str:
    return fr.fund_code or fr.fund_name


def _build_ticker_stats(funds: List[FundRecord]) -> Dict[str, TickerStats]:
    tickers: Dict[str, TickerStats] = {}
    for fr in funds:
        fid = _fund_id(fr)
        holdings = fr.raw.get("top_holdings") or []
        for h in holdings:
            ticker = str(h.get("ticker") or "").strip()
            if not ticker:
                continue
            rank = h.get("rank")
            weight_val = h.get("weight")
            weight: Optional[float]
            try:
                weight = float(weight_val) if weight_val is not None else None
            except (TypeError, ValueError):
                weight = None
            ts = tickers.get(ticker)
            if ts is None:
                ts = TickerStats(ticker=ticker, n_top5=0, n_top10=0, funds_top10=[], weights_top10=[])
                tickers[ticker] = ts
            if isinstance(rank, int):
                if rank <= 5:
                    ts.n_top5 += 1
                if rank <= 10:
                    ts.n_top10 += 1
                    if fid not in ts.funds_top10:
                        ts.funds_top10.append(fid)
                    if weight is not None:
                        ts.weights_top10.append(weight)
    return tickers


def _build_sector_stats(funds: List[FundRecord]) -> Dict[str, SectorStats]:
    sectors: Dict[str, SectorStats] = {}
    for fr in funds:
        sector_list = fr.raw.get("sector_weights") or []
        for s in sector_list:
            name = str(s.get("sector") or "").strip()
            if not name:
                continue
            weight_val = s.get("weight")
            try:
                weight = float(weight_val) if weight_val is not None else None
            except (TypeError, ValueError):
                weight = None
            if weight is None:
                continue
            ss = sectors.get(name)
            if ss is None:
                ss = SectorStats(sector=name, weights=[])
                sectors[name] = ss
            ss.weights.append(weight)
    return sectors


def _avg(values: List[float]) -> Optional[float]:
    if not values:
        return None
    return sum(values) / len(values)


def _dispersion(values: List[float]) -> Optional[float]:
    if not values:
        return None
    lo = min(values)
    hi = max(values)
    return hi - lo


def _median(values: List[float]) -> Optional[float]:
    if not values:
        return None
    try:
        return float(median(values))
    except Exception:
        return None


def _collect_cash_equity(funds: List[FundRecord]) -> Tuple[List[float], List[float]]:
    cash_vals: List[float] = []
    eq_vals: List[float] = []
    for fr in funds:
        cw = fr.raw.get("cash_weight")
        ew = fr.raw.get("equity_weight")
        try:
            if cw is not None:
                cash_vals.append(float(cw))
        except (TypeError, ValueError):
            pass
        try:
            if ew is not None:
                eq_vals.append(float(ew))
        except (TypeError, ValueError):
            pass
    return cash_vals, eq_vals


def _collect_themes(funds: List[FundRecord]) -> List[Dict[str, Any]]:
    themes: List[Dict[str, Any]] = []
    for fr in funds:
        for t in fr.raw.get("manager_themes") or []:
            if not isinstance(t, dict):
                continue
            enriched = dict(t)
            enriched.setdefault("fund_code", fr.fund_code)
            enriched.setdefault("fund_name", fr.fund_name)
            themes.append(enriched)
    return themes


def build_monthly_payload(
    month: str,
    funds: List[FundRecord],
    prev_month_funds: Optional[List[FundRecord]] = None,
) -> Dict[str, Any]:
    """
    Aggregate per-fund positioning into monthly consensus JSON payload.
    """
    n_funds = len(funds)
    fund_ids = [_fund_id(fr) for fr in funds]

    ticker_stats = _build_ticker_stats(funds)
    sector_stats = _build_sector_stats(funds)
    cash_vals, eq_vals = _collect_cash_equity(funds)
    themes = _collect_themes(funds)

    # Build ticker_consensus list
    ticker_consensus: List[Dict[str, Any]] = []
    for ts in sorted(ticker_stats.values(), key=lambda x: (-x.n_top10, x.ticker)):
        avg_w = _avg(ts.weights_top10)
        ticker_consensus.append(
            {
                "ticker": ts.ticker,
                "n_top5": ts.n_top5,
                "n_top10": ts.n_top10,
                "funds_top10": ts.funds_top10,
                "avg_weight_top10": round(avg_w, 2) if avg_w is not None else None,
            }
        )

    # Build sector_consensus list
    sector_consensus: List[Dict[str, Any]] = []
    for ss in sorted(sector_stats.values(), key=lambda x: (-_avg(x.weights) if _avg(x.weights) is not None else 0.0, x.sector)):
        avg_w = _avg(ss.weights)
        med_w = _median(ss.weights)
        disp = _dispersion(ss.weights)
        sector_consensus.append(
            {
                "sector": ss.sector,
                "avg_weight": round(avg_w, 2) if avg_w is not None else None,
                "median_weight": round(med_w, 2) if med_w is not None else None,
                "dispersion": round(disp, 2) if disp is not None else None,
            }
        )

    median_cash = _median(cash_vals)
    # Previous-month stats for deltas
    deltas: Dict[str, Any] = {"vs_prev_month": {"ownership_momentum": [], "median_cash_change": None}}
    prev_median_cash: Optional[float] = None
    prev_ticker_map: Dict[str, int] = {}

    if prev_month_funds is not None:
        prev_tickers = _build_ticker_stats(prev_month_funds)
        prev_cash_vals, _ = _collect_cash_equity(prev_month_funds)
        prev_median_cash = _median(prev_cash_vals)
        prev_ticker_map = {k: v.n_top10 for k, v in prev_tickers.items()}

        # Ownership momentum
        momentum: List[Dict[str, Any]] = []
        for t, ts in ticker_stats.items():
            prev_n = prev_ticker_map.get(t, 0)
            delta_n = ts.n_top10 - prev_n
            if delta_n != 0:
                momentum.append({"ticker": t, "delta_n_top10": delta_n})
        # Sort by absolute change desc
        momentum_sorted = sorted(momentum, key=lambda x: -abs(x["delta_n_top10"]))
        deltas["vs_prev_month"]["ownership_momentum"] = momentum_sorted

    if median_cash is not None and prev_median_cash is not None:
        deltas["vs_prev_month"]["median_cash_change"] = round(median_cash - prev_median_cash, 2)

    # Scores & flags
    crowding_score, crowding_flags = compute_crowding_score(ticker_consensus, sector_consensus, n_funds)
    risk_on_score, risk_flags = compute_risk_on_score(median_cash)
    policy_alignment_score, policy_tags_strength = compute_policy_alignment_score(themes, n_funds)
    regime_bias = compute_regime_bias(crowding_score, risk_on_score)

    flags = []
    flags.extend(crowding_flags)
    flags.extend(risk_flags)

    diagnostics: Dict[str, Any] = {
        "missing_funds": [],
        "notes": [],
    }
    if n_funds == 0:
        diagnostics["notes"].append("No fund records loaded for this month.")
    if not ticker_consensus:
        diagnostics["notes"].append("No ticker holdings found in fund_extracted inputs.")
    if not sector_consensus:
        diagnostics["notes"].append("No sector weights found in fund_extracted inputs.")
    if median_cash is None:
        diagnostics["notes"].append("Median cash_weight could not be computed (missing or invalid values).")

    payload: Dict[str, Any] = {
        "month": month,
        "fund_universe": {
            "n_funds": n_funds,
            "funds": fund_ids,
        },
        "ticker_consensus": ticker_consensus,
        "sector_consensus": sector_consensus,
        "scores": {
            "crowding_score": crowding_score,
            "risk_on_score": risk_on_score,
            "policy_alignment_score": policy_alignment_score,
        },
        "regime_bias": regime_bias,
        "policy_tags_strength": policy_tags_strength,
        "flags": flags,
        "deltas": deltas,
        "diagnostics": diagnostics,
    }
    return payload

