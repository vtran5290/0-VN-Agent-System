from __future__ import annotations
from datetime import date, timedelta
from typing import Dict, Any, Tuple, List
from src.intake.fireant_historical import fetch_historical
from src.features.distribution_days import Bar, BarOHLC, DD_LB_DEFAULT, distribution_days_rolling_lb_refined

PROXIES = ["VN30", "VN30INDEX", "FUEVFVND", "E1VFVN30", "VN30F1M"]
HNX_SYMBOLS = ["HNXINDEX", "HNX", "HNINDEX"]
UPCOM_SYMBOLS = ["UPCOMINDEX", "UPINDEX", "UPCOM"]

def _volume_completeness(ohlc: list, n: int = 21) -> bool:
    """True if last n bars all have volume."""
    return len(ohlc) >= n and all(getattr(x, "v", None) is not None for x in ohlc[-n:])

def _ohlc_to_bar_ohlc(ohlc: list) -> List[BarOHLC]:
    return [BarOHLC(d=x.d, o=x.o, h=x.h, l=x.l, c=x.c, v=x.v) for x in ohlc]

def first_proxy_with_volume(symbols: List[str], start: str, end: str) -> Tuple[str | None, List]:
    need = DD_LB_DEFAULT + 1  # 26 bars for LB=25
    for sym in symbols:
        try:
            ohlc = fetch_historical(sym, start, end)
            if len(ohlc) >= need and _volume_completeness(ohlc, need):
                return sym, ohlc
        except Exception:
            pass
    return None, []

def _index_level_and_trend(symbols: List[str], start: str, end: str, ma_period: int = 20) -> Tuple[float | None, bool | None, str | None]:
    """Fetch first symbol with >= ma_period bars; return (last_close, close > MA, symbol)."""
    for sym in symbols:
        try:
            ohlc = fetch_historical(sym, start, end)
            if len(ohlc) < ma_period:
                continue
            closes = [x.c for x in ohlc[-ma_period:] if x.c is not None]
            if len(closes) != ma_period:
                continue
            last_c = closes[-1]
            ma = sum(closes) / ma_period
            trend_ok = last_c > ma
            return (last_c, trend_ok, sym)
        except Exception:
            pass
    return (None, None, None)

def build_auto_inputs(asof: str | None = None) -> Dict[str, Any]:
    if asof is None:
        asof = date.today().isoformat()

    end = date.fromisoformat(asof)
    start = end - timedelta(days=60)
    start_s, end_s = start.isoformat(), end.isoformat()

    VNINDEX_SYMBOL = "VNI"

    # VNIndex level from VNI (index thường không có volume có nghĩa → dist-days dùng proxy VN30)
    ohlc_vni = []
    try:
        ohlc_vni = fetch_historical(VNINDEX_SYMBOL, start_s, end_s)
    except Exception:
        pass
    bars_vni = [Bar(d=x.d, c=x.c, v=x.v) for x in ohlc_vni]
    vnindex = bars_vni[-1].c if bars_vni else None
    vni_vol_ok = _volume_completeness(ohlc_vni, 21) if ohlc_vni else False
    print(f"VNIndex (VNI) last 21 bars volume completeness: {vni_vol_ok}")

    # Sanity: VNIndex hợp lý ~500–3000
    if vnindex is not None:
        if vnindex < 300 or vnindex > 3000:
            vnindex = None

    print(f"[fireant] VNI latest_close={vnindex} ({start_s} -> {end_s})")

    # Distribution days: multi-proxy (VN30, HNX, UPCOM where volume available)
    proxy_sym, proxy_ohlc = first_proxy_with_volume(PROXIES, start_s, end_s)
    bars_ohlc = _ohlc_to_bar_ohlc(proxy_ohlc) if proxy_ohlc else []
    dist_vn30 = distribution_days_rolling_lb_refined(bars_ohlc, lb=DD_LB_DEFAULT) if bars_ohlc else None

    # VN30 level + trend_ok(>MA20)
    vn30_level = None
    vn30_trend_ok = None
    if proxy_sym and proxy_ohlc and proxy_sym in ("VN30", "VN30INDEX"):
        vn30_level = proxy_ohlc[-1].c
        if len(proxy_ohlc) >= 20:
            closes = [x.c for x in proxy_ohlc[-20:]]
            vn30_trend_ok = vn30_level > (sum(closes) / 20)
    if vn30_level is None:
        for sym in ("VN30", "VN30INDEX"):
            try:
                o = fetch_historical(sym, start_s, end_s)
                if o and o[-1].c is not None:
                    vn30_level = o[-1].c
                    if len(o) >= 20:
                        vn30_trend_ok = o[-1].c > (sum(x.c for x in o[-20:]) / 20)
                    break
            except Exception:
                pass

    need_lb = DD_LB_DEFAULT + 1  # 26 bars for LB=25

    # HNX dist-days (only if volume available); else set reason for facts-first
    dist_hnx = None
    dist_hnx_reason = None
    hnx_sym_used = None
    hnx_vol_checked = False
    for sym in HNX_SYMBOLS:
        try:
            ohlc = fetch_historical(sym, start_s, end_s)
            if len(ohlc) >= need_lb:
                hnx_vol_ok = _volume_completeness(ohlc, need_lb)
                if not hnx_vol_checked:
                    print(f"HNX last {need_lb} bars volume completeness: {hnx_vol_ok}")
                    hnx_vol_checked = True
                if hnx_vol_ok:
                    dist_hnx = distribution_days_rolling_lb_refined(_ohlc_to_bar_ohlc(ohlc), lb=DD_LB_DEFAULT)
                    hnx_sym_used = sym
                break
        except Exception:
            pass
    if not hnx_vol_checked:
        print(f"HNX last {need_lb} bars volume completeness: False")
    dist_hnx_reason = "no_volume" if dist_hnx is None else None

    # UPCOM dist-days (only if volume available); else set reason for facts-first
    dist_upcom = None
    dist_upcom_reason = None
    upcom_sym_used = None
    upcom_vol_checked = False
    for sym in UPCOM_SYMBOLS:
        try:
            ohlc = fetch_historical(sym, start_s, end_s)
            if len(ohlc) >= need_lb:
                upcom_vol_ok = _volume_completeness(ohlc, need_lb)
                if not upcom_vol_checked:
                    print(f"UPCOM last {need_lb} bars volume completeness: {upcom_vol_ok}")
                    upcom_vol_checked = True
                if upcom_vol_ok:
                    dist_upcom = distribution_days_rolling_lb_refined(_ohlc_to_bar_ohlc(ohlc), lb=DD_LB_DEFAULT)
                    upcom_sym_used = sym
                break
        except Exception:
            pass
    if not upcom_vol_checked:
        print(f"UPCOM last {need_lb} bars volume completeness: False")
    dist_upcom_reason = "no_volume" if dist_upcom is None else None

    # Composite risk: High if max>=6 AND >=2 series with dist>=4 (breadth confirmation); Elevated if max>=4; leading = argmax
    distribution_days = {"vn30": dist_vn30, "hnx": dist_hnx, "upcom": dist_upcom}
    counts = [(dist_vn30, "vn30", proxy_sym), (dist_hnx, "hnx", hnx_sym_used), (dist_upcom, "upcom", upcom_sym_used)]
    valid = [(c, key, sym) for c, key, sym in counts if c is not None]
    max_d = max((c for c, _, _ in valid), default=None)
    series_ge4 = sum(1 for c, _, _ in valid if c is not None and c >= 4)
    if valid:
        leading = max(valid, key=lambda x: x[0])
        dist_leading_symbol = leading[2] if leading[2] else leading[1].upper()
    else:
        dist_leading_symbol = proxy_sym
    if max_d is None:
        dist_risk_composite = "Unknown"
    elif max_d >= 6 and series_ge4 >= 2:
        dist_risk_composite = "High"
    elif max_d >= 4:
        dist_risk_composite = "Elevated"
    else:
        dist_risk_composite = "Normal"

    if proxy_sym:
        print(f"[fireant] dist_days proxy={proxy_sym}, dist_vn30={dist_vn30}, dist_hnx={dist_hnx}, dist_upcom={dist_upcom}, composite={dist_risk_composite}, leading={dist_leading_symbol}")
    if vn30_level is not None:
        print(f"[fireant] vn30_level={vn30_level}, vn30_trend_ok={vn30_trend_ok}")

    # HNX / UPCOM breadth (close + MA20 trend)
    hnx_level, hnx_trend_ok, hnx_sym = _index_level_and_trend(HNX_SYMBOLS, start_s, end_s)
    upcom_level, upcom_trend_ok, upcom_sym = _index_level_and_trend(UPCOM_SYMBOLS, start_s, end_s)
    if hnx_level is not None:
        print(f"[fireant] HNX level={hnx_level}, trend_ok(>MA20)={hnx_trend_ok} ({hnx_sym})")
    if upcom_level is not None:
        print(f"[fireant] UPCOM level={upcom_level}, trend_ok(>MA20)={upcom_trend_ok} ({upcom_sym})")

    return {
        "asof_date": asof,
        "market": {
            "vnindex_level": vnindex,
            "vn30_level": vn30_level,
            "vn30_trend_ok": vn30_trend_ok,
            "distribution_days_rolling_20": max_d if max_d is not None else dist_vn30,
            "distribution_days": distribution_days,
            "dist_risk_composite": dist_risk_composite,
            "dist_proxy_symbol": dist_leading_symbol,
            "hnx_level": hnx_level,
            "hnx_trend_ok": hnx_trend_ok,
            "upcom_level": upcom_level,
            "upcom_trend_ok": upcom_trend_ok,
            "dist_hnx_reason": dist_hnx_reason,
            "dist_upcom_reason": dist_upcom_reason,
        }
    }
