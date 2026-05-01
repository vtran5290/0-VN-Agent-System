"""
RS 100-day percentile for liquid universe (ADV50 >= 4 tỷ VND/ngày).

- Universe: tất cả mã có liquidity trung bình 50 ngày gần nhất (ADV50) >= 4e9 VND/ngày.
- RS: hiệu suất 100 phiên gần nhất (close[-1]/close[-101] - 1), xếp hạng theo percentile 0–100.

Usage (từ repo root):
  python scripts/rs100_adv50_universe.py [--end YYYY-MM-DD] [--out path] [--delay 0.12]
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.data.fireant_client import get_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

ADV50_MIN_VND = 4_000_000_000
RS_LOOKBACK_TRADING_DAYS = 100
CALENDAR_DAYS_FETCH = 220  # đủ cho ~150 phiên


def _load_symbols(client) -> list[str]:
    symbols: list[str] = []
    for exchange in ("HOSE", "HNX", "UPCOM"):
        try:
            syms = client.get_symbols(exchange)
            symbols.extend(syms or [])
        except Exception as e:
            logger.warning("get_symbols(%s): %s", exchange, e)
    symbols = sorted(set(s.upper() for s in symbols if s))
    if symbols:
        return symbols
    # Fallback: file coverage từ lần fetch financials
    cov_path = REPO_ROOT / "data" / "fireant_exports" / "financials" / "financial_symbol_coverage.csv"
    if cov_path.exists():
        df = pd.read_csv(cov_path)
        if "symbol" in df.columns:
            symbols = df["symbol"].dropna().astype(str).str.upper().unique().tolist()
            logger.info("Loaded %s symbols from %s", len(symbols), cov_path)
            return symbols
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description="RS 100d percentile, universe ADV50 >= 4 tỷ VND")
    parser.add_argument("--end", default=None, help="Ngày cuối (YYYY-MM-DD), mặc định hôm nay")
    parser.add_argument("--out", default=None, help="Đường dẫn CSV output")
    parser.add_argument("--delay", type=float, default=0.12, help="Giữa mỗi request (giây)")
    args = parser.parse_args()

    end_date = args.end or datetime.today().strftime("%Y-%m-%d")
    start_date = (
        datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=CALENDAR_DAYS_FETCH)
    ).strftime("%Y-%m-%d")

    client = get_client(timeout=60)
    if not getattr(client, "_token", None):
        logger.error("FIREANT_TOKEN chưa set. Đặt env FIREANT_TOKEN=<jwt> hoặc thêm vào .env.")
        return 1
    symbols = _load_symbols(client)
    if not symbols:
        logger.error("Không có danh sách mã. Cần FIREANT_TOKEN và symbols/filter hoặc file financial_symbol_coverage.csv.")
        return 1

    logger.info("Universe candidate: %s symbols. Fetch OHLCV %s -> %s", len(symbols), start_date, end_date)

    rows: list[dict] = []
    need_bars = RS_LOOKBACK_TRADING_DAYS + 1  # 101 bars
    n_with_data = 0
    n_liquid = 0
    for i, sym in enumerate(symbols):
        try:
            df = client.get_ohlcv(sym, start_date, end_date)
        except Exception as e:
            logger.debug("%s: %s", sym, e)
            time.sleep(args.delay)
            continue
        if df is None or df.empty:
            time.sleep(args.delay)
            continue
        if len(df) < need_bars:
            time.sleep(args.delay)
            continue
        n_with_data += 1
        df = df.sort_values("date").reset_index(drop=True)
        close = df["close"].astype(float)
        vol = df["volume"].astype(float)
        adv50 = (close * vol).rolling(50, min_periods=50).mean().iloc[-1]
        if adv50 < ADV50_MIN_VND:
            time.sleep(args.delay)
            continue
        n_liquid += 1
        ret_100 = float(close.iloc[-1] / close.iloc[-need_bars] - 1.0)
        last_close = float(close.iloc[-1])
        rows.append({
            "symbol": sym,
            "adv50_vnd": adv50,
            "last_close": last_close,
            "ret_100d": ret_100,
        })
        if (i + 1) % 100 == 0:
            logger.info("Progress: %s/%s, with_data=%s, liquid=%s", i + 1, len(symbols), n_with_data, n_liquid)
        time.sleep(args.delay)

    if not rows:
        logger.warning(
            "Không có mã nào thỏa ADV50 >= %s và đủ 100 phiên. (with_data=%s, liquid=%s). Kiểm tra FIREANT_TOKEN.",
            ADV50_MIN_VND, n_with_data, n_liquid,
        )
        out_path = Path(args.out or REPO_ROOT / "data" / "decision" / f"rs100_adv50_{end_date}.csv")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=["symbol", "adv50_vnd", "last_close", "ret_100d", "rs_percentile_100"]).to_csv(
            out_path, index=False
        )
        return 0

    out = pd.DataFrame(rows)
    out["rs_percentile_100"] = out["ret_100d"].rank(pct=True).mul(100).round(2)
    out = out.sort_values("rs_percentile_100", ascending=False).reset_index(drop=True)

    out_path = Path(args.out or REPO_ROOT / "data" / "decision" / f"rs100_adv50_{end_date}.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False)

    logger.info("Universe ADV50>=4e9: %s mã. RS 100d percentile -> %s", len(out), out_path)
    print(out.head(15).to_string())
    print("\n... (bottom 5)")
    print(out.tail(5).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
