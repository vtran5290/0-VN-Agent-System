"""S3 EMA21/55 max_hold=60 paper ledger — PAPER TRADE ONLY, no live routing.

Classification: PAPER_TRADE_SHADOW (Phase35 base)
Config: TP=18%, Trail=3.5×ATR14, max_hold=60, full universe (272 symbols)

Paper gate for any reclassification: 12 months live evidence.
Real capital requires separate decision review — this ledger is NEVER a gate to live orders.

NEVER: route to DNSE, mix P&L with A3 or S3 combo, allow live orders.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import pandas as pd

from src.trading.live.paper_ledger import PaperLedger, TRADES_COLS, POSITIONS_COLS

STRATEGY_TAG = "S3_SHADOW_MAX60"
DATA_DIR = Path("data/trading")

S3_SHADOW_TRADES_PATH    = DATA_DIR / "s3_shadow_paper_trades.csv"
S3_SHADOW_POSITIONS_PATH = DATA_DIR / "s3_shadow_paper_positions.csv"

# Hard rules — S3 shadow Phase35 base config
_MAX_HOLD_BARS      = 60      # HARD RULE: never change to 250
_TP1_PCT            = 0.18    # +18% take-profit
_TRAIL_ATR_MULT     = 3.5     # 3.5×ATR14 trailing stop
_LIVE_ORDER_ALLOWED = False   # never True
_DNSE_ALLOWED       = False   # never True


def _guard_no_live_order() -> None:
    if _LIVE_ORDER_ALLOWED:
        raise RuntimeError(
            "S3 shadow paper ledger: live orders are not permitted. "
            "12 months live paper evidence required before any production discussion."
        )


def _guard_no_dnse() -> None:
    if _DNSE_ALLOWED:
        raise RuntimeError("S3 shadow paper ledger: DNSE routing not permitted.")


class S3ShadowPaperLedger:
    """Phase35 base S3 paper ledger — S3_SHADOW_MAX60, TP=18%, max_hold=60.

    Isolated from A3 production book and from S3 combo (s3_combo_paper_ledger.py).
    CSV files: s3_shadow_paper_trades.csv / s3_shadow_paper_positions.csv
    """

    def __init__(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._trades_path    = S3_SHADOW_TRADES_PATH
        self._positions_path = S3_SHADOW_POSITIONS_PATH

    def _load_trades(self) -> pd.DataFrame:
        if self._trades_path.exists() and self._trades_path.stat().st_size > 0:
            return pd.read_csv(self._trades_path, dtype=object)
        return pd.DataFrame({c: pd.Series(dtype=object) for c in TRADES_COLS})

    def _save_trades(self, df: pd.DataFrame) -> None:
        df.to_csv(self._trades_path, index=False)

    def _load_positions(self) -> pd.DataFrame:
        if self._positions_path.exists() and self._positions_path.stat().st_size > 0:
            return pd.read_csv(self._positions_path)
        return pd.DataFrame(columns=POSITIONS_COLS)

    def _save_positions(self, df: pd.DataFrame) -> None:
        df.to_csv(self._positions_path, index=False)

    def record_entry(
        self,
        symbol: str,
        signal_date: str,
        fill_price: float,
        value_vnd: float,
        quantity: int,
        **kwargs: Any,
    ) -> str:
        """Record a paper entry. Raises if live routing or DNSE is attempted."""
        _guard_no_live_order()
        _guard_no_dnse()

        trades = self._load_trades()
        trade_id = f"S3SH-{symbol}-{signal_date}"
        row = {c: None for c in TRADES_COLS}
        row.update({
            "trade_id":      trade_id,
            "symbol":        symbol,
            "strategy":      STRATEGY_TAG,
            "state":         "PAPER_T1",
            "signal_date":   signal_date,
            "t1_order_date": signal_date,
            "t1_fill_price": fill_price,
            "t1_value_VND":  value_vnd,
            "t1_quantity":   quantity,
            "blended_entry": fill_price,
            "notes":         f"S3_SHADOW_MAX60: TP{int(_TP1_PCT*100)}%/Trail{_TRAIL_ATR_MULT}x/MaxHold{_MAX_HOLD_BARS}. "
                             + kwargs.get("notes", ""),
        })
        row.update({k: v for k, v in kwargs.items() if k in TRADES_COLS})
        trades = pd.concat([trades, pd.DataFrame([row])], ignore_index=True)
        self._save_trades(trades)
        self._reconcile()
        return trade_id

    def record_exit(
        self,
        trade_id: str,
        exit_date: str,
        exit_price: float,
        reason: str = "",
    ) -> None:
        """Record paper exit: TP1_HIT, TRAIL_EXIT, or FORCE_EXIT_MAX60."""
        _guard_no_live_order()
        trades = self._load_trades()
        idx = trades.index[trades["trade_id"] == trade_id]
        if idx.empty:
            return
        i = idx[0]
        entry = float(trades.at[i, "blended_entry"] or trades.at[i, "t1_fill_price"] or 0)
        qty   = float(trades.at[i, "t1_quantity"] or 0)
        pnl   = (exit_price - entry) * qty if entry else 0
        trades.at[i, "state"]        = "CLOSED"
        trades.at[i, "exit_date"]    = exit_date
        trades.at[i, "exit_price"]   = exit_price
        trades.at[i, "realized_pnl"] = pnl
        trades.at[i, "notes"]        = (trades.at[i, "notes"] or "") + f" | exit:{reason}"
        self._save_trades(trades)
        self._reconcile()

    def paper_gate_status(self) -> dict:
        """Return progress toward 12-month evidence requirement."""
        trades = self._load_trades()
        total = len(trades)
        closed = int((trades["state"] == "CLOSED").sum()) if not trades.empty else 0
        first_date = pd.to_datetime(trades["signal_date"].min()) if total > 0 else None
        last_date  = pd.to_datetime(trades["signal_date"].max()) if total > 0 else None
        days_elapsed = (last_date - first_date).days if (first_date and last_date) else 0
        return {
            "decisions":    total,
            "exits":        closed,
            "days_elapsed": days_elapsed,
            "days_gate":    365,
            "gate_met":     days_elapsed >= 365,
            "note":         "12 months live evidence required. No capital until gate met.",
        }

    def _reconcile(self) -> pd.DataFrame:
        trades = self._load_trades()
        open_states = {"PAPER_T1", "TP1_HIT"}
        open_trades = trades[trades["state"].isin(open_states)] if not trades.empty else trades
        rows = []
        for _, t in open_trades.iterrows():
            qty   = int(t.get("t1_quantity") or 0)
            entry = float(t.get("blended_entry") or t.get("t1_fill_price") or 0)
            rows.append({
                "symbol":           t["symbol"],
                "strategy":         STRATEGY_TAG,
                "state":            t["state"],
                "quantity":         qty,
                "blended_entry":    entry,
                "market_value_VND": qty * entry,
                "unrealized_pnl":   0.0,
                "tp1_hit":          t["state"] == "TP1_HIT",
                "signal_date":      t.get("signal_date"),
            })
        pos = pd.DataFrame(rows, columns=POSITIONS_COLS) if rows else pd.DataFrame(columns=POSITIONS_COLS)
        self._save_positions(pos)
        return pos

    def export_equity_curve(self, out_dir: Optional[Path] = None) -> Path:
        """Export closed-trade equity curve for dashboard tracking."""
        out = out_dir or DATA_DIR
        out.mkdir(parents=True, exist_ok=True)
        trades = self._load_trades()
        if trades.empty or "exit_date" not in trades.columns:
            return out
        closed = trades[trades["state"] == "CLOSED"].copy()
        if not closed.empty:
            closed = closed.sort_values("exit_date")
            closed["cum_pnl"] = closed["realized_pnl"].fillna(0).astype(float).cumsum()
            closed[["exit_date", "symbol", "realized_pnl", "cum_pnl"]].to_csv(
                out / "s3_shadow_paper_equity_curve.csv", index=False
            )
        return out
