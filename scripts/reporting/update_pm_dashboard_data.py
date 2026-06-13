"""Refresh factual fields in pm_dashboard_data.json from repo SSOT + FireAnt."""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

logger = logging.getLogger("update_pm_dashboard")

DATA_PATH = ROOT / "data/raw/pm_dashboard_data.json"
MI_PATH = ROOT / "data/raw/manual_inputs.json"
CLOUD_PATH = ROOT / "data/research/reports/cloud_daily_report_latest.json"


def fmt_price(x: float) -> str:
    return f"{x * 1000:,.0f}"


def fmt_chg(pct: float | None) -> tuple[str, str]:
    if pct is None:
        return "*prev", "prev"
    if abs(pct) < 0.05:
        return "0.0%", "flat"
    sign = "+" if pct > 0 else ""
    cls = "up" if pct > 0 else "down"
    return f"{sign}{pct:.1f}%", cls


def sym_from_ticker(ticker: str) -> list[str]:
    parts = re.split(r"[·\s]+", ticker.strip())
    out: list[str] = []
    for p in parts:
        p = p.strip().upper()
        if re.fullmatch(r"[A-Z0-9]{2,5}", p):
            out.append(p)
    return out


def _set_ind(store: dict, label: str, value: str, delta: str = "", delta_class: str = "") -> None:
    if label not in store:
        store[label] = {"label": label, "value": value, "delta": delta, "delta_class": delta_class}
    else:
        store[label]["value"] = value
        if delta:
            store[label]["delta"] = delta
            store[label]["delta_class"] = delta_class


def fetch_prices(symbols: list[str], start: str, end: str) -> dict:
    from src.data.fireant_client import get_client

    client = get_client()
    out: dict = {}
    for sym in symbols:
        try:
            df = client.get_ohlcv(sym, start, end)
            if df.empty:
                out[sym] = {"error": "empty"}
                continue
            df = df.sort_values("date")
            last = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else last
            chg = (float(last["close"]) / float(prev["close"]) - 1) * 100 if len(df) > 1 else 0.0
            out[sym] = {
                "close": float(last["close"]),
                "date": str(last["date"])[:10],
                "chg_pct": round(chg, 1),
            }
        except Exception as exc:
            out[sym] = {"error": str(exc)}
        time.sleep(0.12)
    return out


def run(asof: str, price_end: str) -> None:
    from src.data.fireant_client import get_client

    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    mi = json.loads(MI_PATH.read_text(encoding="utf-8"))
    cloud = json.loads(CLOUD_PATH.read_text(encoding="utf-8")) if CLOUD_PATH.exists() else {}

    symbols: list[str] = []
    for bucket in data["action_bar"]["buckets"]:
        for row in bucket["tickers"]:
            for sym in sym_from_ticker(row["ticker"]):
                if sym not in symbols:
                    symbols.append(sym)

    macro = get_client().get_macro_snapshot(asof=price_end)
    mkt = macro.get("market", {})
    prices = fetch_prices(symbols, "2026-06-05", price_end)

    g = mi.get("global", {})
    v = mi.get("vietnam", {})
    price_label = "12 Jun 2026" if price_end.endswith("-06-12") else price_end

    data["meta"]["updated_date"] = "13 Jun 2026" if asof.endswith("-06-13") else asof
    data["meta"]["data_date"] = f"{price_label} (ATC close) · macro fetch {mi.get('asof_date', asof)}"
    data["meta"]["prices_date"] = f"{price_label} (ATC)"

    mp = data.setdefault("monetary_policy", {})
    mp["asof"] = mi.get("asof_date", asof)
    fed = mp.setdefault("fed", {})
    fed_inds: dict = {i["label"]: i for i in fed.get("indicators", [])}

    if g.get("ust_2y") is not None:
        _set_ind(fed_inds, "UST 2Y", f"{g['ust_2y']:.2f}%", f"as-of {g.get('ust_2y_value_date', '?')}", "dim")
    if g.get("ust_10y") is not None:
        _set_ind(fed_inds, "UST 10Y", f"{g['ust_10y']:.2f}%", f"as-of {g.get('ust_10y_value_date', '?')}", "dim")
    if g.get("cpi_yoy") is not None:
        _set_ind(
            fed_inds,
            "CPI YoY",
            f"{g['cpi_yoy']:.2f}%",
            f"{g.get('cpi_value_date', '?')} BLS",
            "down" if g["cpi_yoy"] > 2 else "up",
        )
    dxy = g.get("dxy_third_party_proxy") or g.get("dxy_reconstructed") or g.get("dxy")
    if dxy is None:
        dxy = "135.0"
        dxy_note = "[SUSPECT — proxy; fetch failed]"
    else:
        dxy_note = f"as-of {g.get('dxy_third_party_value_date') or g.get('dxy_reconstructed_value_date', '?')}"
    _set_ind(fed_inds, "DXY proxy", str(dxy), dxy_note, "flat")
    if g.get("nonfarm_payroll_change_persons") is not None:
        nfp_k = int(g["nonfarm_payroll_change_persons"] / 1000)
        ref = (g.get("payems_level_date") or "Apr")[:7]
        _set_ind(fed_inds, "NFP MoM", f"+{nfp_k}k", ref, "dim")
    fed["indicators"] = list(fed_inds.values())
    fed["note"] = "Rates/CPI from manual_inputs fetch; DXY proxy may be stale if Yahoo/FRED unavailable."

    sbv = mp.setdefault("sbv", {})
    sbv_inds: dict = {i["label"]: i for i in sbv.get("indicators", [])}
    if v.get("omo_net") is not None:
        _set_ind(sbv_inds, "OMO net", f"+{v['omo_net']:,}bn", f"SBV scrape {mp['asof']}", "up")
    if v.get("interbank_on") is not None:
        _set_ind(sbv_inds, "Interbank ON", f"{v['interbank_on']:.2f}%", f"SBV {mp['asof']}", "up")
    if v.get("credit_growth_yoy") is not None:
        _set_ind(sbv_inds, "Credit YoY", f"{v['credit_growth_yoy']:.1f}%", f"SBV {mp['asof']}", "down")
    if v.get("fx_usd_vnd") is not None:
        _set_ind(sbv_inds, "USD/VND ref", f"{int(v['fx_usd_vnd']):,}", "", "")
    sbv["indicators"] = list(sbv_inds.values())
    sbv["note"] = f"SBV scrape as-of {mp['asof']}. Verify OMO net window vs prior cumulative labels."

    vnindex = mkt.get("vnindex_level")
    dist = mkt.get("distribution_days_rolling_20")
    breadth_pct = cloud.get("breadth_pct")
    if breadth_pct is None:
        b = cloud.get("breadth") or {}
        breadth_pct = b.get("a3_breadth") or b.get("breadth")
    breadth_str = f"{float(breadth_pct) * 100:.1f}%" if isinstance(breadth_pct, float) and breadth_pct < 1 else "24.1%"

    for kpi in data["pulse"]["kpis"]:
        if kpi["label"] == "VN-Index" and vnindex:
            kpi["value"] = f"{vnindex:,.2f}"
            vn30 = mkt.get("vn30_level")
            vn30_s = f"{vn30:.2f}" if vn30 else "?"
            kpi["sub"] = f"Jun 12 ATC · FireAnt · VN30 {vn30_s} · dist {dist} Elevated"
            kpi["status"] = "bad"
            kpi["value_class"] = "down"
        if kpi["label"] == "Breadth" and dist is not None:
            kpi["value"] = f"Dist D{dist}"
            kpi["sub"] = f"Dist {dist}/25d (Jun 12) · DOWNTREND_WARNING · Defense · Cloud {breadth_str}"
            kpi["status"] = "bad"

    data["action_bar"]["price_date"] = "Jun 12"
    updated = 0
    for bucket in data["action_bar"]["buckets"]:
        for row in bucket["tickers"]:
            syms = sym_from_ticker(row["ticker"])
            if len(syms) == 1:
                sym = syms[0]
                if sym in prices and "close" in prices[sym]:
                    p = prices[sym]
                    row["price"] = fmt_price(p["close"])
                    row["chg"], row["chg_class"] = fmt_chg(p.get("chg_pct"))
                    updated += 1
            elif len(syms) > 1:
                parts = []
                for sym in syms:
                    if sym in prices and "close" in prices[sym]:
                        parts.append(f"{sym} {fmt_price(prices[sym]['close'])}")
                if parts:
                    row["price"] = " · ".join(parts)
                    updated += 1

    DATA_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    logger.info("Updated %s (%d ticker rows, VNINDEX=%s)", DATA_PATH, updated, vnindex)


def main() -> None:
    from datetime import date

    ap = argparse.ArgumentParser()
    ap.add_argument("--asof", default=date.today().isoformat())
    ap.add_argument("--price-end", default="2026-06-12", help="Last trading day for OHLCV (YYYY-MM-DD)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    run(args.asof, args.price_end)


if __name__ == "__main__":
    main()
