"""
backtest.py
===========
Minimal event-driven backtest engine cho CANSLIM VN.

Thiết kế:
  - Không fetch fundamentals trong loop (đọc từ data/canslim_features/*.csv)
  - PnL ảnh hưởng trực tiếp tới cash/equity (mark-to-market)
  - Trim = bán nửa vị thế, Sell = đóng toàn bộ
"""
from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

# Cho phép import từ src/
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))

from canslim.rules import CanslimInputs, canslim_position_management  # type: ignore
from canslim.feature_logger import load_feature_range  # type: ignore
from canslim.fireant_fetcher import fetch_ohlcv  # type: ignore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Portfolio & Position
# ---------------------------------------------------------------------------
@dataclass
class Position:
    symbol: str
    entry_date: str
    entry_price: float
    alloc: float              # tỷ trọng vốn (0–1)
    max_price: float = 0.0
    leader_stock: bool = False


@dataclass
class Trade:
    symbol: str
    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    alloc: float              # tỷ trọng vốn đã đóng
    reason: str

    @property
    def pnl_pct(self) -> float:
        return (self.exit_price - self.entry_price) / self.entry_price


@dataclass
class Portfolio:
    initial_capital: float = 1_000_000_000
    max_positions: int = 6
    position_size: float = 1.0 / 6

    positions: dict[str, Position] = field(default_factory=dict)
    closed_trades: list[Trade] = field(default_factory=list)
    cash: float = field(init=False)

    def __post_init__(self) -> None:
        self.cash = self.initial_capital

    def can_add_position(self) -> bool:
        return len(self.positions) < self.max_positions

    def add_position(self, symbol: str, date: str, price: float, size_factor: float = 1.0) -> None:
        alloc = self.position_size * size_factor
        if alloc <= 0 or alloc > 1:
            return
        self.positions[symbol] = Position(
            symbol=symbol,
            entry_date=date,
            entry_price=price,
            alloc=alloc,
            max_price=price,
        )
        self.cash -= alloc * self.initial_capital
        logger.info(f"  ENTRY {symbol} @ {price:,.0f}  alloc={alloc:.0%}  [{date}]")

    def update_max_price(self, symbol: str, current_price: float) -> None:
        if symbol in self.positions and current_price > self.positions[symbol].max_price:
            self.positions[symbol].max_price = current_price

    def _close_fraction(self, symbol: str, date: str, price: float, fraction: float, reason: str) -> None:
        if symbol not in self.positions or fraction <= 0:
            return
        pos = self.positions[symbol]
        close_alloc = pos.alloc * fraction

        trade = Trade(
            symbol=symbol,
            entry_date=pos.entry_date,
            entry_price=pos.entry_price,
            exit_date=date,
            exit_price=price,
            alloc=close_alloc,
            reason=reason,
        )
        self.closed_trades.append(trade)

        proceeds = close_alloc * self.initial_capital * (price / pos.entry_price if pos.entry_price else 1.0)
        self.cash += proceeds

        remaining_alloc = pos.alloc * (1 - fraction)
        if remaining_alloc <= 0 or fraction >= 1.0 - 1e-8:
            # sell full
            self.positions.pop(symbol)
            logger.info(f"  EXIT {symbol} @ {price:,.0f}  pnl={trade.pnl_pct:+.1%}  [{date}]  reason={reason}")
        else:
            pos.alloc = remaining_alloc
            logger.info(f"  TRIM {symbol} @ {price:,.0f}  frac={fraction:.0%}  pnl={trade.pnl_pct:+.1%}  [{date}]  reason={reason}")

    def close_position(self, symbol: str, date: str, price: float, reason: str) -> None:
        self._close_fraction(symbol, date, price, fraction=1.0, reason=reason)

    def trim_position(self, symbol: str, date: str, price: float, reason: str) -> None:
        self._close_fraction(symbol, date, price, fraction=0.5, reason=reason)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def build_inputs_from_features(
    row: pd.Series,
    current_price: float,
    pos: Optional[Position],
) -> CanslimInputs:
    """Build CanslimInputs từ 1 feature row + thông tin vị thế hiện tại."""

    def f(x):
        try:
            return float(x)
        except Exception:
            return None

    gain = None
    drawdown = None
    weeks = None
    max_gain = None

    if pos:
        gain = (current_price - pos.entry_price) / pos.entry_price
        peak = pos.max_price or pos.entry_price
        drawdown = (current_price - peak) / peak
        entry_dt = datetime.strptime(pos.entry_date, "%Y-%m-%d")
        trade_dt = datetime.strptime(str(row.get("date")), "%Y-%m-%d")
        weeks = (trade_dt - entry_dt).days / 7.0
        max_gain = (peak - pos.entry_price) / pos.entry_price

    rs = None
    if not pd.isna(row.get("rs_rating")):
        try:
            rs = int(row["rs_rating"])
        except Exception:
            rs = None

    return CanslimInputs(
        q_eps_yoy=f(row.get("q_eps_yoy")),
        q_sales_yoy=f(row.get("q_sales_yoy")),
        sales_accel=bool(row.get("sales_accel")) if not pd.isna(row.get("sales_accel")) else None,
        margin_yoy=f(row.get("margin_yoy")),
        rs_rating=rs,
        price=current_price,
        pivot=f(row.get("pivot")),
        breakout_volume_ratio=f(row.get("breakout_vol_ratio")),
        entry_price=pos.entry_price if pos else None,
        weeks_since_entry=weeks,
        gain_from_entry=gain,
        drawdown_from_entry=gain,  # dùng loss-from-entry cho hard stop 7–8%
        max_gain_since_entry=max_gain,
        market_status=str(row.get("market_status")) if row.get("market_status") else None,
        leader_stock=pos.leader_stock if pos else None,
    )


def run_backtest(
    start: str,
    end: str,
    features_dir: Optional[Path] = None,
    initial_capital: float = 1_000_000_000,
    max_positions: int = 6,
    allow_late_buy: bool = True,
) -> dict:
    logger.info(f"=== CANSLIM Backtest | {start} → {end} ===")

    portfolio = Portfolio(initial_capital=initial_capital, max_positions=max_positions)
    equity_curve: list[dict] = []

    all_features = load_feature_range(start, end, features_dir)
    if all_features.empty:
        logger.error("No feature files found; chạy screener + log_features trước.")
        return {}

    dates = sorted(all_features["date"].unique())
    logger.info(f"Backtesting {len(dates)} days, {len(all_features)} symbol-days")

    price_cache: dict[str, pd.Series] = {}

    def get_price(symbol: str, date: str) -> Optional[float]:
        if symbol not in price_cache:
            try:
                df = fetch_ohlcv(symbol, start, end, resolution="D")
                price_cache[symbol] = df.set_index("date")["close"] if not df.empty else pd.Series(dtype=float)
            except Exception:
                price_cache[symbol] = pd.Series(dtype=float)
        series = price_cache[symbol]
        if series.empty:
            return None
        dt = pd.Timestamp(date)
        if dt in series.index:
            return float(series.loc[dt])
        past = series[series.index <= dt]
        return float(past.iloc[-1]) if not past.empty else None

    for date in dates:
        day_features = all_features[all_features["date"] == date]
        logger.info(f"\n--- {date} | positions={len(portfolio.positions)}/{max_positions} ---")

        # 1) Manage existing positions
        actions: list[tuple[str, str, float, str, str]] = []
        for sym, pos in list(portfolio.positions.items()):
            price = get_price(sym, date)
            if price is None:
                continue
            portfolio.update_max_price(sym, price)

            row = day_features[day_features["symbol"] == sym]
            if not row.empty:
                inputs = build_inputs_from_features(row.iloc[0], price, pos)
            else:
                gain = (price - pos.entry_price) / pos.entry_price
                inputs = CanslimInputs(
                    price=price,
                    entry_price=pos.entry_price,
                    gain_from_entry=gain,
                    drawdown_from_entry=gain,
                    weeks_since_entry=None,
                )
            mgmt = canslim_position_management(inputs)
            action = mgmt["action"]
            if action == "sell":
                actions.append((sym, date, price, mgmt["reason"], "sell"))
            elif action == "trim":
                actions.append((sym, date, price, mgmt["reason"], "trim"))

        for sym, dt, px, reason, kind in actions:
            if kind == "sell":
                portfolio.close_position(sym, dt, px, reason)
            else:
                portfolio.trim_position(sym, dt, px, reason)

        # 2) New entries
        candidates = day_features[day_features["allow_buy"] == True].copy()
        if not allow_late_buy:
            candidates = candidates[candidates["buy_zone"] == "ideal"]

        eps_order = {"elite": 0, "preferred": 1, "min_pass": 2, "fail": 3, None: 4}
        candidates["_eps_ord"] = candidates["eps_tier"].map(eps_order)
        candidates = candidates.sort_values(
            ["rs_rating", "_eps_ord"],
            ascending=[False, True],
            na_position="last",
        )

        for _, row in candidates.iterrows():
            if not portfolio.can_add_position():
                break
            sym = row["symbol"]
            if sym in portfolio.positions:
                continue
            price = get_price(sym, date)
            if price is None:
                continue
            size_factor = 0.5 if row.get("buy_zone") == "late" else 1.0
            portfolio.add_position(sym, date, price, size_factor=size_factor)

        # 3) Mark-to-market equity
        total_pos_value = 0.0
        for sym, pos in portfolio.positions.items():
            cur = get_price(sym, date) or pos.entry_price
            total_pos_value += pos.alloc * initial_capital * (cur / pos.entry_price if pos.entry_price else 1.0)
        equity_curve.append({
            "date": date,
            "cash": portfolio.cash,
            "positions_value": total_pos_value,
            "equity": portfolio.cash + total_pos_value,
            "n_positions": len(portfolio.positions),
        })

    trades_df = pd.DataFrame([
        {
            "symbol": t.symbol,
            "entry_date": t.entry_date,
            "entry_price": t.entry_price,
            "exit_date": t.exit_date,
            "exit_price": t.exit_price,
            "alloc": t.alloc,
            "pnl_pct": t.pnl_pct,
            "reason": t.reason,
        }
        for t in portfolio.closed_trades
    ])
    equity_df = pd.DataFrame(equity_curve)

    n_trades = len(trades_df)
    if n_trades:
        winners = trades_df[trades_df["pnl_pct"] > 0]
        losers = trades_df[trades_df["pnl_pct"] <= 0]
        win_rate = len(winners) / n_trades if n_trades else 0
        avg_win = winners["pnl_pct"].mean() if not winners.empty else 0.0
        avg_loss = losers["pnl_pct"].mean() if not losers.empty else 0.0
        if not losers.empty:
            pf = abs((winners["pnl_pct"] * winners["alloc"]).sum()) / abs((losers["pnl_pct"] * losers["alloc"]).sum())
        else:
            pf = float("inf")
    else:
        win_rate = avg_win = avg_loss = pf = 0.0

    final_equity = equity_df["equity"].iloc[-1] if not equity_df.empty else initial_capital
    total_return = (final_equity - initial_capital) / initial_capital

    metrics = {
        "start": start,
        "end": end,
        "n_trades": n_trades,
        "win_rate": round(win_rate, 3),
        "avg_win_pct": round(avg_win * 100, 2),
        "avg_loss_pct": round(avg_loss * 100, 2),
        "profit_factor": round(pf, 2),
        "total_return_pct": round(total_return * 100, 2),
        "final_equity": int(final_equity),
    }

    print("\n" + "=" * 50)
    print("CANSLIM Backtest Results")
    print("=" * 50)
    for k, v in metrics.items():
        print(f"  {k:<20} {v}")
    print("=" * 50)

    return {
        "metrics": metrics,
        "trades": trades_df,
        "equity_curve": equity_df,
        "open_positions": list(portfolio.positions.keys()),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CANSLIM VN Backtest")
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default="2025-12-31")
    parser.add_argument("--capital", type=float, default=1_000_000_000)
    parser.add_argument("--max-pos", type=int, default=6)
    parser.add_argument("--no-late", action="store_true", help="Reject late buy zone")
    parser.add_argument("--features-dir", default=None)
    args = parser.parse_args()

    run_backtest(
        start=args.start,
        end=args.end,
        features_dir=Path(args.features_dir) if args.features_dir else None,
        initial_capital=args.capital,
        max_positions=args.max_pos,
        allow_late_buy=not args.no_late,
    )

