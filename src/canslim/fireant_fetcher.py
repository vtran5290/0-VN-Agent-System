"""
fireant_fetcher.py
==================
Fetch OHLCV + fundamental data từ FireAnt API.
Không cần auth token cho các endpoint public.
Nếu cần token (private account), set FIREANT_TOKEN trong .env
"""
from __future__ import annotations

import os
import time
import logging
from datetime import datetime
from typing import Optional

import requests
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_URL = "https://restv2.fireant.vn"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
}
# Nếu bạn có token FireAnt (lấy từ browser DevTools -> Network -> Bearer token)
_TOKEN = os.getenv("FIREANT_TOKEN", "")
if _TOKEN:
    HEADERS["Authorization"] = f"Bearer {_TOKEN}"

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def _get(url: str, params: dict | None = None, retries: int = 3) -> dict | list:
    """GET với retry đơn giản."""
    for attempt in range(retries):
        try:
            r = SESSION.get(url, params=params, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == retries - 1:
                raise
            logger.warning(f"Retry {attempt+1}/{retries} for {url}: {e}")
            time.sleep(1.5 * (attempt + 1))


# ---------------------------------------------------------------------------
# 1. OHLCV (daily / weekly)
# ---------------------------------------------------------------------------
def fetch_ohlcv(
    symbol: str,
    start: str,          # "YYYY-MM-DD"
    end: str,            # "YYYY-MM-DD"
    resolution: str = "D",   # "D" daily | "W" weekly
) -> pd.DataFrame:
    """
    Trả về DataFrame: date, open, high, low, close, volume
    resolution: "D" = daily, "W" = weekly
    """
    url = f"{BASE_URL}/symbols/{symbol}/historical-quotes"
    params = {
        "startDate": start,
        "endDate": end,
        "offset": 0,
        "limit": 5000,
    }
    data = _get(url, params)
    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)
    # FireAnt trả về: date, priceOpen, priceHigh, priceLow, priceClose, totalVolume
    rename = {
        "date": "date",
        "priceOpen": "open",
        "priceHigh": "high",
        "priceLow": "low",
        "priceClose": "close",
        "totalVolume": "volume",
    }
    df = df.rename(columns=rename)[list(rename.values())]
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    if resolution == "W":
        df = _resample_weekly(df)

    return df


def _resample_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """Resample daily OHLCV -> weekly (tuần kết thúc thứ Sáu)."""
    df = df.set_index("date")
    weekly = df.resample("W-FRI").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).dropna()
    return weekly.reset_index()


# ---------------------------------------------------------------------------
# 2. Fundamental (Financial Statements theo quý)
# ---------------------------------------------------------------------------
def fetch_financial_statements(
    symbol: str,
    year: int,
    quarter: int,
    limit: int = 10,
    report_type: int = 2,
) -> list:
    """
    Fetch income statement (full-financial-reports) cho nhiều quý gần nhất.

    Endpoint FireAnt:
      /symbols/{symbol}/full-financial-reports?type=2&year=YYYY&quarter=Q&limit=N

    type:
      2 = Income statement (đúng payload bạn đã dump)
    """
    url = f"{BASE_URL}/symbols/{symbol}/full-financial-reports"
    params = {
        "type": report_type,
        "year": year,
        "quarter": quarter,
        "limit": limit,
    }
    data = _get(url, params)
    return data if isinstance(data, list) else []


def fetch_multi_quarters(symbol: str, n_quarters: int = 6) -> pd.DataFrame:
    """
    Fetch n_quarters gần nhất (+ buffer để tính YoY) từ full-financial-reports (type=2).

    Trả về DataFrame với các cột:
      year, quarter, revenue, net_income, eps, gross_margin,
      revenue_yoy, eps_yoy, revenue_accel, margin_yoy
    """
    today = datetime.today()
    cur_q = (today.month - 1) // 3 + 1

    # +4 để chắc chắn có cùng kỳ năm trước cho YoY
    limit = n_quarters + 4

    try:
        raw = fetch_financial_statements(symbol, today.year, cur_q, limit=limit, report_type=2)
    except Exception as e:
        logger.warning(f"Cannot fetch full-financial-reports for {symbol}: {e}")
        return pd.DataFrame()

    records = _parse_financials(raw)
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records).sort_values(["year", "quarter"]).reset_index(drop=True)
    df = _compute_yoy(df)
    df = _compute_accel(df)

    # Gross margin YoY (nếu có)
    if "gross_margin" in df.columns:
        df["margin_yoy"] = None
        for i, row in df.iterrows():
            prev = df[(df["year"] == row["year"] - 1) & (df["quarter"] == row["quarter"])]
            if not prev.empty:
                p = prev.iloc[0]
                gm_prev = p.get("gross_margin")
                gm_cur = row.get("gross_margin")
                if gm_prev is not None and gm_cur is not None:
                    df.at[i, "margin_yoy"] = gm_cur - gm_prev
        df["margin_yoy"] = pd.to_numeric(df["margin_yoy"], errors="coerce")

    return df


def fetch_annual_CA(symbol: str, n_years: int = 4) -> pd.DataFrame:
    """
    Fetch annual C/A metrics (CANSLIM C & A) từ full-financial-reports (type=2, quarter=0).

    Trả về DataFrame:
      year, revenue, net_income, eps, gross_margin,
      revenue_yoy, eps_yoy, margin_yoy
    """
    today = datetime.today()
    cur_year = today.year
    limit = n_years + 1  # +1 để tính YoY cho năm mới nhất

    try:
        raw = fetch_financial_statements(
            symbol=symbol,
            year=cur_year,
            quarter=0,        # 0 = annual reports
            limit=limit,
            report_type=2,
        )
    except Exception as e:
        logger.warning(f"Cannot fetch annual full-financial-reports for {symbol}: {e}")
        return pd.DataFrame()

    records = _parse_financials(raw)
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    # chỉ giữ annual rows (quarter == 0)
    df = df[df["quarter"] == 0].copy()
    if df.empty:
        return pd.DataFrame()

    df = df.sort_values(["year", "quarter"]).reset_index(drop=True)
    df = _compute_yoy(df)

    # only keep last n_years if available
    if len(df) > n_years:
        df = df.iloc[-n_years:].reset_index(drop=True)

    return df


def _last_n_quarters(cur_year: int, cur_month: int, n: int) -> list[tuple[int, int]]:
    """Trả về list (year, quarter) từ gần nhất về quá khứ."""
    cur_q = (cur_month - 1) // 3 + 1
    results = []
    year, q = cur_year, cur_q
    for _ in range(n):
        results.append((year, q))
        q -= 1
        if q == 0:
            q = 4
            year -= 1
    return results


def _parse_financials(raw: list) -> list[dict]:
    """
    Parse FireAnt full-financial-reports (type=2 income statement).

    raw là list các dòng chỉ tiêu:
      {
        "name": "...",
        "values": [
            {"year": 2025, "quarter": 4, "value": ...},
            ...
        ]
      }

    Trích xuất:
      - net sales: \"Doanh thu thuần\"
      - gross profit: \"Lợi nhuận gộp\"
      - profit attributable to parent: \"Lợi nhuận sau thuế ... công ty mẹ\"
        (fallback: \"Lợi nhuận sau thuế thu nhập doanh nghiệp\" nếu thiếu dòng công ty mẹ)
    """
    if not raw or not isinstance(raw, list):
        return []

    def _match(name: str, patterns: list[str]) -> bool:
        n = (name or "").lower()
        return any(p in n for p in patterns)

    def _to_series(item: dict) -> dict[tuple[int, int], float]:
        out: dict[tuple[int, int], float] = {}
        for v in item.get("values", []) or []:
            y = v.get("year")
            q = v.get("quarter")
            val = v.get("value")
            if y is None or q is None or val is None:
                continue
            out[(int(y), int(q))] = float(val)
        return out

    net_sales: dict[tuple[int, int], float] = {}
    gross_profit: dict[tuple[int, int], float] = {}
    pat_parent: dict[tuple[int, int], float] = {}
    pat_company: dict[tuple[int, int], float] = {}

    for item in raw:
        name = item.get("name", "")
        if _match(name, ["doanh thu thuần", "3. doanh thu thuần"]):
            net_sales = _to_series(item)
        elif _match(name, ["lợi nhuận gộp", "5. lợi nhuận gộp"]):
            gross_profit = _to_series(item)
        elif _match(name, ["lợi nhuận sau thuế của cổ đông của công ty mẹ", "21. lợi nhuận sau thuế"]):
            pat_parent = _to_series(item)
        elif _match(name, ["lợi nhuận sau thuế thu nhập doanh nghiệp", "19. lợi nhuận sau thuế thu nhập doanh nghiệp"]):
            pat_company = _to_series(item)

    # Chọn PAT: ưu tiên cổ đông công ty mẹ, fallback toàn công ty
    pat = pat_parent if pat_parent else pat_company

    # Build unified key set
    keys = sorted(set(net_sales.keys()) | set(pat.keys()) | set(gross_profit.keys()))
    if not keys:
        return []

    records: list[dict] = []
    for (y, q) in keys:
        rev = net_sales.get((y, q))
        ni = pat.get((y, q))
        gp = gross_profit.get((y, q))

        # Cần ít nhất revenue hoặc net income
        if rev is None and ni is None:
            continue

        gross_margin = None
        if rev is not None and rev != 0 and gp is not None:
            gross_margin = gp / rev

        # EPS proxy: dùng PAT (scale cancel trong YoY)
        eps_proxy = float(ni) if ni is not None else None

        records.append({
            "year": y,
            "quarter": q,
            "revenue": float(rev) if rev is not None else None,
            "net_income": float(ni) if ni is not None else None,
            "eps": eps_proxy,
            "gross_margin": gross_margin,
        })

    return records


def _compute_yoy(df: pd.DataFrame) -> pd.DataFrame:
    """Tính YoY cho revenue và eps (so cùng quý năm trước)."""
    df = df.copy()
    df["revenue_yoy"] = None
    df["eps_yoy"] = None

    for i, row in df.iterrows():
        prev = df[(df["year"] == row["year"] - 1) & (df["quarter"] == row["quarter"])]
        if not prev.empty:
            p = prev.iloc[0]
            if p["revenue"] and p["revenue"] != 0:
                df.at[i, "revenue_yoy"] = (row["revenue"] - p["revenue"]) / abs(p["revenue"])
            if p["eps"] and p["eps"] != 0:
                df.at[i, "eps_yoy"] = (row["eps"] - p["eps"]) / abs(p["eps"])

    df["revenue_yoy"] = pd.to_numeric(df["revenue_yoy"], errors="coerce")
    df["eps_yoy"] = pd.to_numeric(df["eps_yoy"], errors="coerce")
    return df


def _compute_accel(df: pd.DataFrame) -> pd.DataFrame:
    """
    sales_accel = True nếu revenue_yoy tăng qua 3 quý liên tiếp gần nhất.
    Dùng rolling diff để detect acceleration.
    """
    df = df.copy()
    df["revenue_accel"] = False

    yoy_series = df["revenue_yoy"].dropna()
    if len(yoy_series) >= 3:
        # Lấy 3 giá trị gần nhất
        last3 = yoy_series.iloc[-3:].values
        # Accel nếu mỗi quý cao hơn quý trước
        is_accel = all(last3[i] < last3[i + 1] for i in range(len(last3) - 1))
        # Gán cho record mới nhất
        df.loc[df.index[-1], "revenue_accel"] = is_accel

    return df


# ---------------------------------------------------------------------------
# 3. RS Rating (tự tính, IBD-style)
# ---------------------------------------------------------------------------
def compute_rs_ratings(
    symbols: list[str],
    end_date: str,
    lookback_days: int = 252,  # ~12 tháng
    skip_recent_days: int = 21,  # bỏ 1 tháng gần nhất (IBD standard)
) -> pd.Series:
    """
    Tính RS Rating cho list symbols, trả về pd.Series index=symbol, value=RS (1-99).

    Công thức IBD-style:
        - Tính % thay đổi giá trong 12 tháng trừ 1 tháng gần nhất
        - Map percentile -> thang điểm 1–99
    """
    start_dt = datetime.strptime(end_date, "%Y-%m-%d") - pd.Timedelta(days=lookback_days)
    start = start_dt.strftime("%Y-%m-%d")

    returns = {}
    for sym in symbols:
        try:
            df = fetch_ohlcv(sym, start=start, end=end_date, resolution="D")
            if df.empty or len(df) < skip_recent_days + 20:
                continue
            df = df.copy()
            df = df.iloc[:-skip_recent_days]  # bỏ 1 tháng gần nhất
            if len(df) < 20:
                continue
            p0 = df.iloc[0]["close"]
            p1 = df.iloc[-1]["close"]
            if p0 and p0 != 0:
                ret = (p1 - p0) / p0
                returns[sym] = ret
        except Exception as e:
            logger.warning(f"RS calc failed for {sym}: {e}")

    if not returns:
        return pd.Series(dtype=float)

    ser = pd.Series(returns)
    rank = ser.rank(method="min")  # 1..N
    rs = (rank / rank.max() * 98 + 1).round().astype(int)  # 1..99
    return rs


# ---------------------------------------------------------------------------
# 4. Symbol universe helper
# ---------------------------------------------------------------------------
def fetch_all_symbols(exchange: str = "HOSE") -> list[str]:
    """
    Fetch toàn bộ mã trên 1 sàn (HOSE/HNX/UPCOM).
    Điều chỉnh endpoint nếu FireAnt đổi schema.
    """
    url = f"{BASE_URL}/symbols"
    params = {"exchange": exchange}
    data = _get(url, params)
    if not data:
        return []

    df = pd.DataFrame(data)
    # Thường có field "symbol" hoặc "ticker"
    symbol_col = "symbol" if "symbol" in df.columns else "ticker"
    symbols = sorted(df[symbol_col].dropna().unique().tolist())
    return symbols

