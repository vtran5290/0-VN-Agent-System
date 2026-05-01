from __future__ import annotations
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


logger = logging.getLogger(__name__)


RESTV2_BASE = "https://restv2.fireant.vn"

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "Origin": "https://fireant.vn",
    "Referer": "https://fireant.vn/",
}

INDEX_PROXIES: Dict[str, List[str]] = {
    "VNINDEX": ["VNINDEX", "VNI"],
    "VN30": ["VN30", "VN30INDEX", "FUEVFVND", "E1VFVN30", "VN30F1M"],
    "HNX": ["HNXINDEX", "HNX", "HNINDEX"],
    "UPCOM": ["UPCOMINDEX", "UPINDEX", "UPCOM"],
}

OHLCV_COLS = ["date", "open", "high", "low", "close", "volume"]
_FUND_COLS = [
    "year",
    "quarter",
    "revenue",
    "net_income",
    "eps",
    "gross_margin",
    "equity",
    "total_debt",
    "shares_outstanding",
    "cfo",
    "cfi",
    "cff",
    "net_cf",
    "revenue_yoy",
    "eps_yoy",
    "revenue_accel",
    "margin_yoy",
]


def _empty_ohlcv(warnings: Optional[List[str]] = None) -> pd.DataFrame:
    df = pd.DataFrame(columns=OHLCV_COLS)
    df.attrs["warnings"] = warnings or []
    df.attrs["data_integrity"] = "empty"
    return df


def _empty_fund(warnings: Optional[List[str]] = None) -> pd.DataFrame:
    df = pd.DataFrame(columns=_FUND_COLS)
    df.attrs["warnings"] = warnings or []
    df.attrs["data_integrity"] = "empty"
    return df


def _flag_integrity(df: pd.DataFrame) -> pd.DataFrame:
    issues: List[str] = []
    dates = pd.to_datetime(df["date"]).sort_values()
    gaps = dates.diff().dropna()
    if (gaps > pd.Timedelta(days=7)).any():
        issues.append("missing_bars")
    if "volume" in df.columns and (df["volume"] == 0).sum() > len(df) * 0.1:
        issues.append("high_zero_volume")
    df.attrs["data_integrity"] = "ok" if not issues else ",".join(issues)
    df.attrs["warnings"] = issues
    return df


def _load_token(explicit: Optional[str]) -> Optional[str]:
    """
    Load FIREANT_TOKEN from (in order):
      1) explicit argument
      2) environment variable FIREANT_TOKEN
      3) .env file at repo root (FIREANT_TOKEN=...)
    """
    if explicit:
        return explicit

    env_tok = os.environ.get("FIREANT_TOKEN")
    if env_tok:
        return env_tok

    try:
        repo_root = Path(__file__).resolve().parents[2]
        env_path = repo_root / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("FIREANT_TOKEN="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        pass

    return None


def _build_session(token: Optional[str]) -> requests.Session:
    session = requests.Session()
    headers = dict(_BROWSER_HEADERS)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    session.headers.update(headers)

    retry = Retry(
        total=3,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


class FireAntClient:
    def __init__(
        self,
        token: Optional[str] = None,
        timeout: int = 30,
        cache_ttl: int = 3600,
    ) -> None:
        self._token = _load_token(token)
        self._timeout = timeout
        self._ttl = cache_ttl
        self._session = _build_session(self._token)
        self._cache: Dict[str, Tuple[float, Any]] = {}

        if not self._token:
            logger.warning(
                "[FireAntClient] FIREANT_TOKEN not set — authenticated endpoints may fail. "
                "Set FIREANT_TOKEN=<jwt> to enable full access."
            )

    def _get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Any:
        r = self._session.get(url, params=params, timeout=self._timeout)
        r.raise_for_status()
        return r.json()

    def _cached(self, key: str) -> Any | None:
        hit = self._cache.get(key)
        if hit and (time.time() - hit[0]) < self._ttl:
            return hit[1]
        return None

    def _store(self, key: str, val: Any) -> None:
        self._cache[key] = (time.time(), val)

    def get_ohlcv(
        self,
        symbol: str,
        start: str,
        end: str,
        timeframe: str = "D",
    ) -> pd.DataFrame:
        cache_key = f"ohlcv|{symbol}|{start}|{end}|{timeframe}"
        cached = self._cached(cache_key)
        if cached is not None:
            return cached

        url = f"{RESTV2_BASE}/symbols/{symbol}/historical-quotes"
        params = {"startDate": start, "endDate": end, "offset": 0, "limit": 5000}
        try:
            data = self._get(url, params)
        except Exception as exc:
            logger.error("get_ohlcv(%s): %s", symbol, exc)
            return _empty_ohlcv([str(exc)])

        if not data:
            return _empty_ohlcv([f"No data returned for {symbol} [{start},{end}]"])

        try:
            df = _parse_ohlcv(data)
        except Exception as exc:
            logger.error("get_ohlcv(%s) parse error: %s", symbol, exc)
            return _empty_ohlcv([f"Parse error: {exc}"])

        if df.empty:
            return _empty_ohlcv([f"Empty after parsing for {symbol}"])

        df = _flag_integrity(df)
        if timeframe.upper() == "W":
            df = _resample_weekly(df)

        self._store(cache_key, df)
        return df

    def get_ohlcv_multi(
        self,
        symbols: List[str],
        start: str,
        end: str,
        timeframe: str = "D",
        delay: float = 0.15,
    ) -> Dict[str, pd.DataFrame]:
        out: Dict[str, pd.DataFrame] = {}
        for sym in symbols:
            out[sym] = self.get_ohlcv(sym, start, end, timeframe)
            time.sleep(delay)
        return out

    def _raw_financials(
        self,
        symbol: str,
        year: int,
        quarter: int,
        limit: int,
        report_type: int = 2,
    ) -> list:
        url = f"{RESTV2_BASE}/symbols/{symbol}/full-financial-reports"
        params = {"type": report_type, "year": year, "quarter": quarter, "limit": limit}
        try:
            data = self._get(url, params)
            return data if isinstance(data, list) else []
        except Exception as exc:
            logger.error("_raw_financials(%s %sQ%s): %s", symbol, year, quarter, exc)
            return []

    def get_fundamentals_quarterly(self, symbol: str, n_quarters: int = 6) -> pd.DataFrame:
        """
        Quarterly PL + BS snapshot for last n_quarters:
          year, quarter, revenue, net_income, eps, gross_margin,
          equity, total_debt, shares_outstanding,
          revenue_yoy, eps_yoy, revenue_accel, margin_yoy
        """
        today = datetime.today()
        current_quarter = (today.month - 1) // 3 + 1
        limit = n_quarters + 8

        raw_is = self._raw_financials(
            symbol, today.year, current_quarter, limit=limit, report_type=2
        )
        raw_bs = self._raw_financials(
            symbol, today.year, current_quarter, limit=limit, report_type=1
        )
        raw_cf = self._raw_financials(
            symbol, today.year, current_quarter, limit=limit, report_type=4
        )
        inc_records = _parse_financials(raw_is)
        bs_records = _parse_balance_sheet(raw_bs)
        cf_records = _parse_cash_flow(raw_cf)

        if not inc_records and not bs_records:
            return _empty_fund([f"No quarterly data for {symbol}"])

        inc_df = (
            pd.DataFrame(inc_records)
            if inc_records
            else pd.DataFrame(columns=["year", "quarter"])
        )
        bs_df = (
            pd.DataFrame(bs_records)
            if bs_records
            else pd.DataFrame(columns=["year", "quarter", "equity", "total_debt", "shares_outstanding"])
        )
        cf_df = (
            pd.DataFrame(cf_records)
            if cf_records
            else pd.DataFrame(columns=["year", "quarter", "cfo", "cfi", "cff", "net_cf"])
        )

        if inc_df.empty and bs_df.empty and cf_df.empty:
            return _empty_fund([f"No quarterly data for {symbol}"])

        merged = (
            inc_df.merge(bs_df, on=["year", "quarter"], how="outer")
            .merge(cf_df, on=["year", "quarter"], how="outer")
        )
        merged = merged[merged["quarter"].astype(int).between(1, 4)]
        if merged.empty:
            return _empty_fund([f"No quarterly data for {symbol}"])

        merged = merged.sort_values(["year", "quarter"]).reset_index(drop=True)
        merged = _add_yoy_quarterly(merged)
        return merged.tail(n_quarters).reset_index(drop=True)

    def get_fundamentals_annual(self, symbol: str, n_years: int = 4) -> pd.DataFrame:
        """
        Annual snapshot derived from quarterly data:
        take last available quarter in each year, then compute YoY on revenue/eps/margin.
        """
        # Use more quarters than needed to ensure enough history for YoY
        q_df = self.get_fundamentals_quarterly(symbol, n_quarters=n_years * 4 + 4)
        if q_df.empty:
            return _empty_fund([f"No annual data for {symbol}"])

        # Take last quarter per year
        grp = q_df.groupby("year", as_index=False).tail(1)
        grp = grp.sort_values("year").reset_index(drop=True)
        if grp.empty:
            return _empty_fund([f"No annual data for {symbol}"])

        cols = ["year", "equity", "total_debt", "shares_outstanding"]
        pl_cols = ["revenue", "net_income", "eps", "gross_margin"]
        if set(pl_cols).issubset(grp.columns):
            cols = ["year"] + pl_cols + ["equity", "total_debt", "shares_outstanding"]

        annual = grp[cols].copy()
        annual = _add_yoy_annual(annual)
        if len(annual) > n_years:
            annual = annual.tail(n_years).reset_index(drop=True)
        return annual

    def get_symbols(self, exchange: str = "HOSE") -> List[str]:
        cache_key = f"symbols|{exchange}"
        cached = self._cached(cache_key)
        if cached is not None:
            return cached

        url = f"{RESTV2_BASE}/symbols/filter"
        params = {"exchange": exchange, "offset": 0, "limit": 2000}
        try:
            data = self._get(url, params)
        except Exception as exc:
            logger.error("get_symbols(%s): %s", exchange, exc)
            return []

        symbols = sorted(
            {
                str(
                    item.get("symbol") or item.get("ticker") or item.get("code") or ""
                ).upper()
                for item in (data or [])
                if item.get("symbol") or item.get("ticker") or item.get("code")
            }
        )
        self._store(cache_key, symbols)
        return symbols

    def search_symbols(
        self,
        keywords: str,
        exchange: Optional[str] = None,
        symbol_type: Optional[str] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        cache_key = (
            f"symbols_search|{keywords}|{exchange or ''}|{symbol_type or ''}|{offset}|{limit}"
        )
        cached = self._cached(cache_key)
        if cached is not None:
            return cached

        url = f"{RESTV2_BASE}/symbols/search"
        params: Dict[str, Any] = {"keywords": keywords, "offset": offset, "limit": limit}
        if exchange:
            params["exchange"] = exchange
        if symbol_type:
            params["type"] = symbol_type

        try:
            data = self._get(url, params)
        except Exception as exc:
            logger.error("search_symbols(%s): %s", keywords, exc)
            return []

        items = data if isinstance(data, list) else []
        self._store(cache_key, items)
        return items

    def get_all_financial_data(
        self,
        period_type: str,
        count: int,
    ) -> List[Dict[str, Any]]:
        period_type = period_type.upper()
        cache_key = f"all_financial_data|{period_type}|{count}"
        cached = self._cached(cache_key)
        if cached is not None:
            return cached

        url = f"{RESTV2_BASE}/symbols/all-financial-data"
        params = {"type": period_type, "count": count}
        try:
            data = self._get(url, params)
        except Exception as exc:
            logger.error("get_all_financial_data(%s, %s): %s", period_type, count, exc)
            return []

        items = data if isinstance(data, list) else []
        self._store(cache_key, items)
        return items

    def get_icb_latest_index(self) -> List[Dict[str, Any]]:
        cache_key = "icb_latest_index"
        cached = self._cached(cache_key)
        if cached is not None:
            return cached

        url = f"{RESTV2_BASE}/icb/latest-index"
        try:
            data = self._get(url)
        except Exception as exc:
            logger.error("get_icb_latest_index(): %s", exc)
            return []

        items = data if isinstance(data, list) else []
        self._store(cache_key, items)
        return items

    def get_icb_historical_index(
        self,
        industry_code: str,
        start: str,
        end: str,
    ) -> pd.DataFrame:
        cache_key = f"icb_historical_index|{industry_code}|{start}|{end}"
        cached = self._cached(cache_key)
        if cached is not None:
            return cached

        url = f"{RESTV2_BASE}/icb/{industry_code}/historical-index"
        params = {"startDate": start, "endDate": end}
        try:
            data = self._get(url, params)
        except Exception as exc:
            logger.error("get_icb_historical_index(%s): %s", industry_code, exc)
            return _empty_ohlcv([str(exc)])

        if not data:
            return _empty_ohlcv([f"No industry index data for {industry_code} [{start},{end}]"])

        try:
            df = _parse_icb_index_history(data)
        except Exception as exc:
            logger.error("get_icb_historical_index(%s) parse error: %s", industry_code, exc)
            return _empty_ohlcv([f"Parse error: {exc}"])

        if df.empty:
            return _empty_ohlcv([f"Empty after parsing for industry index {industry_code}"])

        df = _flag_integrity(df)
        self._store(cache_key, df)
        return df

    def get_adv20(
        self,
        symbols: List[str],
        start: str,
        end: str,
        adv20_min: float = 5_000_000_000,
        lookback: int = 40,
        adv_window: int = 20,
        delay: float = 0.15,
    ) -> pd.DataFrame:
        rows: List[Dict[str, Any]] = []
        for sym in symbols:
            df = self.get_ohlcv(sym, start, end)
            if df.empty or len(df) < adv_window:
                time.sleep(delay)
                continue
            tail = df.sort_values("date").tail(lookback).tail(adv_window)
            adv = (tail["close"] * tail["volume"]).mean()
            if adv >= adv20_min:
                rows.append(
                    {
                        "symbol": sym,
                        "adv20": float(adv),
                        "last_close": float(df.iloc[-1]["close"]),
                        "last_volume": float(df.iloc[-1]["volume"]),
                    }
                )
            time.sleep(delay)

        if not rows:
            return pd.DataFrame(columns=["symbol", "adv20", "last_close", "last_volume"])

        return (
            pd.DataFrame(rows)
            .sort_values("adv20", ascending=False)
            .reset_index(drop=True)
        )

    def build_universe(
        self,
        exchanges: Optional[List[str]] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        adv20_min: float = 5_000_000_000,
        delay: float = 0.15,
    ) -> pd.DataFrame:
        exchanges = exchanges or ["HOSE", "HNX", "UPCOM"]
        end = end or datetime.today().strftime("%Y-%m-%d")
        start = start or (datetime.today() - timedelta(days=90)).strftime("%Y-%m-%d")

        parts: List[pd.DataFrame] = []
        for exch in exchanges:
            syms = self.get_symbols(exch)
            logger.info("Exchange %s: %d symbols found", exch, len(syms))
            df = self.get_adv20(syms, start, end, adv20_min=adv20_min, delay=delay)
            if not df.empty:
                df["exchange"] = exch
                parts.append(df)

        if not parts:
            return pd.DataFrame(
                columns=["symbol", "exchange", "adv20", "last_close", "last_volume"]
            )

        return pd.concat(parts, ignore_index=True)

    def compute_rs_ratings(
        self,
        symbols: List[str],
        end_date: str,
        lookback_days: int = 252,
        skip_recent_days: int = 21,
        delay: float = 0.1,
    ) -> pd.Series:
        start = (
            datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=lookback_days + 30)
        ).strftime("%Y-%m-%d")
        perf: Dict[str, float] = {}
        for sym in symbols:
            df = self.get_ohlcv(sym, start, end_date)
            if df.empty or len(df) < skip_recent_days + 2:
                time.sleep(delay)
                continue
            p_end = float(df.iloc[-(skip_recent_days + 1)]["close"])
            p_start = float(df.iloc[0]["close"])
            if p_start > 0:
                perf[sym] = p_end / p_start - 1.0
            time.sleep(delay)

        if not perf:
            return pd.Series(dtype=float, name="rs_rating")

        return (
            pd.Series(perf)
            .rank(pct=True)
            .mul(98)
            .add(1)
            .round()
            .astype(int)
            .rename("rs_rating")
        )

    def get_index_ohlcv(
        self,
        index_name: str = "VNINDEX",
        start: Optional[str] = None,
        end: Optional[str] = None,
        lookback_days: int = 60,
    ) -> pd.DataFrame:
        end = end or datetime.today().strftime("%Y-%m-%d")
        start = start or (
            datetime.today() - timedelta(days=lookback_days)
        ).strftime("%Y-%m-%d")
        candidates = INDEX_PROXIES.get(index_name.upper(), [index_name])
        for sym in candidates:
            df = self.get_ohlcv(sym, start, end)
            if not df.empty and "volume" in df.columns and df["volume"].sum() > 0:
                df.attrs["index_symbol"] = sym
                return df
        return _empty_ohlcv([f"No data for index {index_name} from any proxy"])

    def get_macro_snapshot(self, asof: Optional[str] = None) -> Dict[str, Any]:
        asof = asof or datetime.today().strftime("%Y-%m-%d")
        end = asof
        start = (
            datetime.strptime(asof, "%Y-%m-%d") - timedelta(days=60)
        ).strftime("%Y-%m-%d")
        warnings: List[str] = []

        def _lv_trend(label: str, df: pd.DataFrame) -> Tuple[Optional[float], Optional[bool]]:
            if df.empty:
                warnings.append(f"no_data:{label}")
                return None, None
            last = float(df.iloc[-1]["close"])
            trend = None
            if len(df) >= 20:
                trend = last > float(df["close"].tail(20).mean())
            return last, trend

        def _dist(df: pd.DataFrame, lb: int = 25) -> Optional[int]:
            if df.empty or len(df) < 5:
                return None
            try:
                from src.features.distribution_days import BarOHLC, distribution_days_rolling_20_refined

                bars: List[BarOHLC] = []
                for r in df.itertuples():
                    bars.append(
                        BarOHLC(
                            d=str(r.date)[:10],
                            o=float(r.open),
                            h=float(r.high),
                            l=float(r.low),
                            c=float(r.close),
                            v=float(r.volume),
                        )
                    )
                refined = distribution_days_rolling_20_refined(bars)
                if refined is not None:
                    return int(refined)
            except Exception as e:
                warnings.append(f"dist_refined_fallback:{e}")
            # Fallback: previous basic rule
            w = df.tail(lb).copy()
            avg = w["volume"].mean()
            return int(((w["close"].diff() < 0) & (w["volume"] > avg)).sum())

        df_vni = self.get_index_ohlcv("VNINDEX", start, end)
        time.sleep(0.1)
        df_vn30 = self.get_index_ohlcv("VN30", start, end)
        time.sleep(0.1)
        df_hnx = self.get_index_ohlcv("HNX", start, end)
        time.sleep(0.1)
        df_upcom = self.get_index_ohlcv("UPCOM", start, end)

        vni_level, _ = _lv_trend("VNINDEX", df_vni)
        vn30_level, vn30_trend = _lv_trend("VN30", df_vn30)
        hnx_level, hnx_trend = _lv_trend("HNX", df_hnx)
        upcom_level, upcom_trend = _lv_trend("UPCOM", df_upcom)

        if vni_level is not None and not (300 < vni_level < 3000):
            warnings.append(f"vnindex_sanity_fail:{vni_level}")
            vni_level = None

        dist_vn30 = _dist(df_vn30)
        dist_hnx = _dist(df_hnx)
        dist_upcom = _dist(df_upcom)

        dist_hnx_reason = (
            None if (not df_hnx.empty and df_hnx["volume"].sum() > 0) else "no_volume"
        )
        dist_upcom_reason = (
            None if (not df_upcom.empty and df_upcom["volume"].sum() > 0) else "no_volume"
        )

        vn30_proxy = df_vn30.attrs.get("index_symbol")

        dvals = [d for d in [dist_vn30, dist_hnx, dist_upcom] if d is not None]
        if not dvals:
            composite = "Unknown"
        elif max(dvals) >= 6 and sum(1 for d in dvals if d >= 4) >= 2:
            composite = "High"
        elif max(dvals) >= 4:
            composite = "Elevated"
        else:
            composite = "Normal"

        return {
            "asof_date": asof,
            "warnings": warnings,
            "market": {
                "vnindex_level": vni_level,
                "vn30_level": vn30_level,
                "vn30_trend_ok": vn30_trend,
                "distribution_days_rolling_20": dist_vn30,
                "distribution_days": {
                    "vn30": dist_vn30,
                    "hnx": dist_hnx,
                    "upcom": dist_upcom,
                },
                "dist_risk_composite": composite,
                "dist_proxy_symbol": vn30_proxy,
                "hnx_level": hnx_level,
                "hnx_trend_ok": hnx_trend,
                "upcom_level": upcom_level,
                "upcom_trend_ok": upcom_trend,
                "dist_hnx_reason": dist_hnx_reason,
                "dist_upcom_reason": dist_upcom_reason,
            },
        }


def _parse_ohlcv(data: List[Dict[str, Any]]) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for item in data:
        date_val = (
            item.get("date")
            or item.get("Date")
            or item.get("tradingDate")
            or item.get("TradingDate")
        )
        if not date_val:
            continue

        def _f(keys: List[str], default: float = 0.0) -> float:
            for k in keys:
                v = item.get(k)
                if v is not None:
                    try:
                        return float(v)
                    except (TypeError, ValueError):
                        continue
            return default

        rows.append(
            {
                "date": str(date_val)[:10],
                "open": _f(["priceOpen", "open", "Open"]),
                "high": _f(["priceHigh", "high", "High"]),
                "low": _f(["priceLow", "low", "Low"]),
                "close": _f(["priceClose", "close", "Close", "priceAverage"]),
                "volume": _f(["dealVolume", "volume", "Volume", "Vol"]),
            }
        )

    if not rows:
        return pd.DataFrame(columns=OHLCV_COLS)

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def _resample_weekly(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy().set_index("date")
    weekly = (
        df.resample("W-FRI")
        .agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
        )
        .dropna(subset=["close"])
    )
    weekly = weekly[weekly["close"] > 0]
    return weekly.reset_index()


def _parse_icb_index_history(data: List[Dict[str, Any]]) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for item in data:
        idx = item.get("indexValues") or {}
        date_val = item.get("date") or idx.get("Date")
        if not date_val:
            continue

        def _num(key: str) -> float:
            val = idx.get(key)
            try:
                return float(val) if val is not None else 0.0
            except (TypeError, ValueError):
                return 0.0

        rows.append(
            {
                "date": str(date_val)[:10],
                "open": _num("IndexOpen"),
                "high": _num("IndexHigh"),
                "low": _num("IndexLow"),
                "close": _num("IndexClose"),
                "volume": _num("Volume"),
                "value": _num("Value"),
                "industry_code": str(
                    item.get("industryCode") or idx.get("ICBCode") or ""
                ),
                "industry_name": idx.get("ICBName"),
            }
        )

    if not rows:
        return pd.DataFrame(columns=OHLCV_COLS + ["value", "industry_code", "industry_name"])

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def _parse_financials(raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Parse FireAnt full-financial-reports (type=2 income statement) into
    year/quarter-level revenue, net_income, eps, gross_margin.

    raw is a list of line items:
      {
        "name": "...",
        "values": [
            {"year": 2025, "quarter": 4, "value": ...},
            ...
        ]
      }
    """
    if not raw or not isinstance(raw, list):
        return []

    def _match(name: str, patterns: List[str]) -> bool:
        n = (name or "").lower()
        return any(p in n for p in patterns)

    def _to_series(item: Dict[str, Any]) -> Dict[Tuple[int, int], float]:
        out: Dict[Tuple[int, int], float] = {}
        for v in item.get("values", []) or []:
            y = v.get("year")
            q = v.get("quarter")
            val = v.get("value")
            if y is None or q is None or val is None:
                continue
            try:
                out[(int(y), int(q))] = float(val)
            except (TypeError, ValueError):
                continue
        return out

    net_sales: Dict[Tuple[int, int], float] = {}
    gross_profit: Dict[Tuple[int, int], float] = {}
    pat_parent: Dict[Tuple[int, int], float] = {}
    pat_company: Dict[Tuple[int, int], float] = {}

    for item in raw:
        name = item.get("name", "")
        if _match(name, ["doanh thu thuần", "3. doanh thu thuần"]):
            net_sales = _to_series(item)
        elif _match(name, ["lợi nhuận gộp", "5. lợi nhuận gộp"]):
            gross_profit = _to_series(item)
        elif _match(
            name,
            [
                "lợi nhuận sau thuế của cổ đông của công ty mẹ",
                "21. lợi nhuận sau thuế",
            ],
        ):
            pat_parent = _to_series(item)
        elif _match(
            name,
            [
                "lợi nhuận sau thuế thu nhập doanh nghiệp",
                "19. lợi nhuận sau thuế thu nhập doanh nghiệp",
            ],
        ):
            pat_company = _to_series(item)

    pat = pat_parent if pat_parent else pat_company
    keys = sorted(set(net_sales.keys()) | set(pat.keys()) | set(gross_profit.keys()))
    if not keys:
        return []

    records: List[Dict[str, Any]] = []
    for (y, q) in keys:
        rev = net_sales.get((y, q))
        ni = pat.get((y, q))
        gp = gross_profit.get((y, q))

        if rev is None and ni is None:
            continue

        gross_margin = None
        if rev is not None and rev != 0 and gp is not None:
            gross_margin = gp / rev

        eps_proxy = float(ni) if ni is not None else None

        records.append(
            {
                "year": y,
                "quarter": q,
                "revenue": float(rev) if rev is not None else None,
                "net_income": float(ni) if ni is not None else None,
                "eps": eps_proxy,
                "gross_margin": gross_margin,
            }
        )

    return records


def _parse_balance_sheet(raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Parse FireAnt full-financial-reports (type=1 balance sheet) into
    year/quarter-level equity, total_debt, shares_outstanding (approx).
    """
    if not raw or not isinstance(raw, list):
        return []

    def _match(name: str, patterns: List[str]) -> bool:
        n = (name or "").lower()
        return any(p in n for p in patterns)

    def _series(item: Dict[str, Any]) -> Dict[Tuple[int, int], float]:
        out: Dict[Tuple[int, int], float] = {}
        for v in item.get("values", []) or []:
            y = v.get("year")
            q = v.get("quarter")
            val = v.get("value")
            if y is None or q is None or val is None:
                continue
            try:
                out[(int(y), int(q))] = float(val)
            except (TypeError, ValueError):
                continue
        return out

    total_liab: Dict[Tuple[int, int], float] = {}
    equity_owner: Dict[Tuple[int, int], float] = {}
    equity_total: Dict[Tuple[int, int], float] = {}
    capital_owner: Dict[Tuple[int, int], float] = {}

    for item in raw:
        name = item.get("name", "")
        if _match(name, ["a. nợ phải trả", "nợ phải trả"]):
            total_liab = _series(item)
        elif _match(name, ["i. vốn chủ sở hữu"]):
            equity_owner = _series(item)
        elif _match(name, ["b. nguồn vốn chủ sở hữu", "nguồn vốn chủ sở hữu"]):
            equity_total = _series(item)
        elif _match(name, ["vốn đầu tư của chủ sở hữu"]):
            capital_owner = _series(item)

    equity = equity_owner if equity_owner else equity_total
    keys = sorted(set(total_liab.keys()) | set(equity.keys()) | set(capital_owner.keys()))
    if not keys:
        return []

    records: List[Dict[str, Any]] = []
    for (y, q) in keys:
        eq_val = equity.get((y, q))
        debt_val = total_liab.get((y, q))
        cap_val = capital_owner.get((y, q))

        shares_val: Optional[float]
        if cap_val is not None:
            try:
                shares_val = float(cap_val) / 10000.0
            except (TypeError, ValueError):
                shares_val = None
        else:
            shares_val = None

        records.append(
            {
                "year": y,
                "quarter": q,
                "equity": float(eq_val) if eq_val is not None else None,
                "total_debt": float(debt_val) if debt_val is not None else None,
                "shares_outstanding": float(shares_val) if shares_val is not None else None,
            }
        )

    return records


def _parse_cash_flow(raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Parse FireAnt full-financial-reports (type=4 cash-flow) into
    year/quarter-level:
      cfo  = Lưu chuyển tiền thuần từ hoạt động kinh doanh
      cfi  = Lưu chuyển tiền thuần từ hoạt động đầu tư
      cff  = Lưu chuyển tiền thuần từ hoạt động tài chính
      net_cf = Lưu chuyển tiền thuần trong kỳ
    """
    if not raw or not isinstance(raw, list):
        return []

    def _series_for_names(patterns: List[str]) -> Dict[Tuple[int, int], float]:
        out: Dict[Tuple[int, int], float] = {}
        for item in raw:
            name = (item.get("name") or "").lower()
            if not any(p in name for p in patterns):
                continue
            for v in item.get("values") or []:
                y = v.get("year")
                q = v.get("quarter")
                val = v.get("value")
                if y is None or q is None or val is None:
                    continue
                try:
                    out[(int(y), int(q))] = float(val)
                except (TypeError, ValueError):
                    continue
        return out

    cfo_map = _series_for_names(
        ["lưu chuyển tiền thuần từ hoạt động kinh doanh"]
    )
    cfi_map = _series_for_names(
        ["lưu chuyển tiền thuần từ hoạt động đầu tư"]
    )
    cff_map = _series_for_names(
        ["lưu chuyển tiền thuần từ hoạt động tài chính"]
    )
    net_map = _series_for_names(
        ["lưu chuyển tiền thuần trong kỳ"]
    )

    keys = sorted(
        set(cfo_map.keys())
        | set(cfi_map.keys())
        | set(cff_map.keys())
        | set(net_map.keys())
    )
    if not keys:
        return []

    records: List[Dict[str, Any]] = []
    for (y, q) in keys:
        records.append(
            {
                "year": y,
                "quarter": q,
                "cfo": cfo_map.get((y, q)),
                "cfi": cfi_map.get((y, q)),
                "cff": cff_map.get((y, q)),
                "net_cf": net_map.get((y, q)),
            }
        )

    return records


def _add_yoy_quarterly(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # If PL fields are missing (e.g. only BS available), just add empty YoY columns.
    if not {"revenue", "eps", "gross_margin"}.issubset(df.columns):
        df["revenue_yoy"] = pd.NA
        df["eps_yoy"] = pd.NA
        df["margin_yoy"] = pd.NA
        df["revenue_accel"] = pd.NA
        return df

    df["revenue_yoy"] = df["revenue"].pct_change(4)
    df["eps_yoy"] = df["eps"].pct_change(4)
    df["margin_yoy"] = df["gross_margin"].diff(4)
    df["revenue_accel"] = df["revenue_yoy"].diff()
    return df


def _add_yoy_annual(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if not {"revenue", "eps", "gross_margin"}.issubset(df.columns):
        df["revenue_yoy"] = pd.NA
        df["eps_yoy"] = pd.NA
        df["margin_yoy"] = pd.NA
        df["revenue_accel"] = pd.NA
        return df

    df["revenue_yoy"] = df["revenue"].pct_change()
    df["eps_yoy"] = df["eps"].pct_change()
    df["margin_yoy"] = df["gross_margin"].diff()
    df["revenue_accel"] = df["revenue_yoy"].diff()
    return df


_client: Optional[FireAntClient] = None


def get_client(
    token: Optional[str] = None,
    timeout: int = 30,
    cache_ttl: int = 3600,
) -> FireAntClient:
    global _client
    if _client is None:
        _client = FireAntClient(token=token, timeout=timeout, cache_ttl=cache_ttl)
    return _client


def reset_client() -> None:
    global _client
    _client = None

