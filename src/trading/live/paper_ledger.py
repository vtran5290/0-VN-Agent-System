"""Execution paper ledger (separate from data/paper_trade research ledger)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from src.trading.config import LiveTradingConfig
from src.trading.util.timeutil import utc_now_iso

TRADES_COLS = [
    "trade_id", "symbol", "strategy", "state", "signal_date", "t1_order_date",
    "t1_fill_price", "t1_value_VND", "t1_quantity", "t2_trigger_date", "t2_fill_price",
    "t2_value_VND", "t2_quantity", "blended_entry", "tp1_price", "trail_price",
    "max_hold_date", "exit_date", "exit_price", "realized_pnl", "unrealized_pnl",
    "gk10", "adv50_B_VND", "liq_warning", "breadth_zone", "sector_l4", "notes",
]

POSITIONS_COLS = [
    "symbol", "strategy", "state", "quantity", "blended_entry", "market_value_VND",
    "unrealized_pnl", "tp1_hit", "signal_date",
]


class PaperLedger:
    def __init__(self, config: LiveTradingConfig):
        self.config = config
        self.trades_path = config.paper_trades_path
        self.positions_path = config.paper_positions_path

    def _load_trades(self) -> pd.DataFrame:
        if self.trades_path.exists() and self.trades_path.stat().st_size > 0:
            return pd.read_csv(self.trades_path, dtype=object)
        return pd.DataFrame({c: pd.Series(dtype=object) for c in TRADES_COLS})

    def _load_positions(self) -> pd.DataFrame:
        if self.positions_path.exists() and self.positions_path.stat().st_size > 0:
            return pd.read_csv(self.positions_path)
        return pd.DataFrame(columns=POSITIONS_COLS)

    def _save_trades(self, df: pd.DataFrame) -> None:
        self.trades_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(self.trades_path, index=False)

    def _save_positions(self, df: pd.DataFrame) -> None:
        self.positions_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(self.positions_path, index=False)

    def open_T1(
        self,
        symbol: str,
        signal_date: str,
        fill_price: float,
        value_vnd: float,
        quantity: int,
        **kwargs: Any,
    ) -> str:
        trades = self._load_trades()
        trade_id = f"T1-{symbol}-{signal_date}"
        row = {c: None for c in TRADES_COLS}
        row.update({
            "trade_id": trade_id,
            "symbol": symbol,
            "strategy": self.config.production_strategy,
            "state": "NEW_T1",
            "signal_date": signal_date,
            "t1_order_date": signal_date,
            "t1_fill_price": fill_price,
            "t1_value_VND": value_vnd,
            "t1_quantity": quantity,
            "blended_entry": fill_price,
            "gk10": kwargs.get("gk10", False),
            "adv50_B_VND": kwargs.get("adv50_B_VND"),
            "liq_warning": kwargs.get("liq_warning", ""),
            "breadth_zone": kwargs.get("breadth_zone", ""),
            "sector_l4": kwargs.get("sector_l4", ""),
            "notes": kwargs.get("notes", ""),
        })
        trades = pd.concat([trades, pd.DataFrame([row])], ignore_index=True)
        self._save_trades(trades)
        self.reconcile_open_positions()
        return trade_id

    def add_T2(self, trade_id: str, fill_date: str, fill_price: float, value_vnd: float, quantity: int) -> None:
        trades = self._load_trades()
        idx = trades.index[trades["trade_id"] == trade_id]
        if idx.empty:
            return
        i = idx[0]
        t1q = float(trades.at[i, "t1_quantity"] or 0)
        t1p = float(trades.at[i, "t1_fill_price"] or 0)
        total_q = t1q + quantity
        blended = (t1p * t1q + fill_price * quantity) / total_q if total_q else fill_price
        trades.at[i, "state"] = "T2_ADDED"
        trades.at[i, "t2_trigger_date"] = fill_date
        trades.at[i, "t2_fill_price"] = fill_price
        trades.at[i, "t2_value_VND"] = value_vnd
        trades.at[i, "t2_quantity"] = quantity
        trades.at[i, "blended_entry"] = blended
        self._save_trades(trades)
        self.reconcile_open_positions()

    def mark_TP1(self, trade_id: str, tp1_price: float) -> None:
        trades = self._load_trades()
        idx = trades.index[trades["trade_id"] == trade_id]
        if not idx.empty:
            trades.at[idx[0], "state"] = "TP1_HIT"
            trades.at[idx[0], "tp1_price"] = tp1_price
            self._save_trades(trades)

    def update_trail(self, trade_id: str, trail_price: float) -> None:
        trades = self._load_trades()
        idx = trades.index[trades["trade_id"] == trade_id]
        if not idx.empty:
            trades.at[idx[0], "trail_price"] = trail_price
            self._save_trades(trades)

    def close_trade(self, trade_id: str, exit_date: str, exit_price: float, reason: str = "") -> None:
        trades = self._load_trades()
        idx = trades.index[trades["trade_id"] == trade_id]
        if idx.empty:
            return
        i = idx[0]
        entry = float(trades.at[i, "blended_entry"] or trades.at[i, "t1_fill_price"] or 0)
        qty = float(trades.at[i, "t1_quantity"] or 0) + float(trades.at[i, "t2_quantity"] or 0)
        pnl = (exit_price - entry) * qty if entry else 0
        trades.at[i, "state"] = "CLOSED"
        trades.at[i, "exit_date"] = exit_date
        trades.at[i, "exit_price"] = exit_price
        trades.at[i, "realized_pnl"] = pnl
        trades.at[i, "notes"] = (trades.at[i, "notes"] or "") + f" | exit:{reason}"
        self._save_trades(trades)
        self.reconcile_open_positions()

    def reconcile_open_positions(self) -> pd.DataFrame:
        trades = self._load_trades()
        open_states = {"NEW_T1", "PB_WAIT", "T2_ADDED", "HOLD_T1_ONLY", "TP1_HIT", "TRAIL_EXIT"}
        open_trades = trades[trades["state"].isin(open_states)] if not trades.empty else trades
        rows = []
        for _, t in open_trades.iterrows():
            t1q = 0 if pd.isna(t.get("t1_quantity")) else int(t.get("t1_quantity") or 0)
            t2q = 0 if pd.isna(t.get("t2_quantity")) else int(t.get("t2_quantity") or 0)
            qty = t1q + t2q
            entry = float(t.get("blended_entry") or t.get("t1_fill_price") or 0)
            rows.append({
                "symbol": t["symbol"],
                "strategy": t["strategy"],
                "state": t["state"],
                "quantity": qty,
                "blended_entry": entry,
                "market_value_VND": qty * entry,
                "unrealized_pnl": 0.0,
                "tp1_hit": t["state"] == "TP1_HIT",
                "signal_date": t.get("signal_date"),
            })
        pos = pd.DataFrame(rows, columns=POSITIONS_COLS) if rows else pd.DataFrame(columns=POSITIONS_COLS)
        self._save_positions(pos)
        return pos

    def export_dashboard(self, out_dir: Optional[Path] = None) -> Path:
        out = out_dir or self.config.dashboard_dir
        out.mkdir(parents=True, exist_ok=True)
        pos = self._load_positions()
        pos.to_csv(out / "active_positions.csv", index=False)
        trades = self._load_trades()
        if not trades.empty and "exit_date" in trades.columns:
            closed = trades[trades["state"] == "CLOSED"].copy()
            if not closed.empty:
                closed["cum_pnl"] = closed["realized_pnl"].fillna(0).cumsum()
                closed[["exit_date", "cum_pnl"]].to_csv(out / "paper_equity_curve.csv", index=False)
        return out

    def get_open_symbols(self) -> List[str]:
        pos = self._load_positions()
        if pos.empty:
            return []
        return pos["symbol"].astype(str).tolist()
