"""S3 Combo paper ledger — PAPER TRADE ONLY, no live routing.

Classification: PRODUCTION_CANDIDATE_PENDING_PAPER
Config: TP=10%, Trail=3.5×ATR14, max_hold=60, mom20≥0%, a3_breadth≥35%

Capacity: ~5B VND max. ADV≥10B floor collapses MAR to 0.21.
Paper gate: 30 decisions, 10 exits, 3 months before any real-capital consideration.

NEVER: route to DNSE, mix P&L with A3, allow live orders.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import pandas as pd

from src.trading.live.paper_ledger import PaperLedger, TRADES_COLS, POSITIONS_COLS

STRATEGY_TAG = "S3_COMBO_PAPER"
DATA_DIR = Path("data/trading")

S3_COMBO_TRADES_PATH    = DATA_DIR / "s3_combo_paper_trades.csv"
S3_COMBO_POSITIONS_PATH = DATA_DIR / "s3_combo_paper_positions.csv"

# Hard rules — never override these in calling code
_MAX_CAPITAL_VND   = 5_000_000_000   # 5B VND absolute ceiling
_LIVE_ORDER_ALLOWED = False           # never True until paper gate met
_DNSE_ALLOWED       = False           # never True


def _guard_no_live_order() -> None:
    """Raise if anything attempts live order routing through this ledger."""
    if _LIVE_ORDER_ALLOWED:
        raise RuntimeError(
            "S3 combo paper ledger: live orders are not permitted. "
            "Paper gate (30 decisions / 10 exits / 3 months) has not been met."
        )


def _guard_no_dnse() -> None:
    if _DNSE_ALLOWED:
        raise RuntimeError("S3 combo paper ledger: DNSE routing not permitted.")


class S3ComboPaperLedger:
    """Thin ledger for S3 combo paper tracking, isolated from A3 production book.

    Uses the same PaperLedger CSV interface but with dedicated file paths and
    the S3_COMBO_PAPER strategy tag so P&L never mixes with A3.
    """

    def __init__(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._trades_path    = S3_COMBO_TRADES_PATH
        self._positions_path = S3_COMBO_POSITIONS_PATH

    # ── internal helpers ─────────────────────────────────────────────────────

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

    # ── paper trade actions ──────────────────────────────────────────────────

    def record_entry(
        self,
        symbol: str,
        signal_date: str,
        fill_price: float,
        value_vnd: float,
        quantity: int,
        **kwargs: Any,
    ) -> str:
        """Record a paper entry.  Raises if live routing is attempted."""
        _guard_no_live_order()
        _guard_no_dnse()

        if value_vnd > _MAX_CAPITAL_VND:
            raise ValueError(
                f"S3 combo paper: value_vnd {value_vnd/1e9:.2f}B exceeds "
                f"capacity ceiling {_MAX_CAPITAL_VND/1e9:.0f}B VND. "
                "Re-run capacity backtest before increasing scale."
            )

        trades = self._load_trades()
        trade_id = f"S3P-{symbol}-{signal_date}"
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
            "notes":         "S3_COMBO_PAPER: TP10/Trail3.5/MaxHold60. " + kwargs.get("notes", ""),
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
        """Record paper exit (TP1_HIT, TRAIL_EXIT, or FORCE_EXIT_MAX60)."""
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

    # ── gate progress ────────────────────────────────────────────────────────

    def paper_gate_status(self) -> dict:
        """Return progress toward the 3-month paper gate (30 dec / 10 exits)."""
        trades = self._load_trades()
        total = len(trades)
        closed = int((trades["state"] == "CLOSED").sum()) if not trades.empty else 0
        first_date = pd.to_datetime(trades["signal_date"].min()) if total > 0 else None
        last_date  = pd.to_datetime(trades["signal_date"].max()) if total > 0 else None
        days_elapsed = (last_date - first_date).days if (first_date and last_date) else 0
        return {
            "decisions":      total,
            "decisions_gate": 30,
            "exits":          closed,
            "exits_gate":     10,
            "days_elapsed":   days_elapsed,
            "days_gate":      90,
            "gate_met": total >= 30 and closed >= 10 and days_elapsed >= 90,
        }

    # ── positions ────────────────────────────────────────────────────────────

    def _reconcile(self) -> pd.DataFrame:
        trades = self._load_trades()
        open_states = {"PAPER_T1", "TP1_HIT"}
        open_trades = trades[trades["state"].isin(open_states)] if not trades.empty else trades
        rows = []
        for _, t in open_trades.iterrows():
            qty = int(t.get("t1_quantity") or 0)
            entry = float(t.get("blended_entry") or t.get("t1_fill_price") or 0)
            rows.append({
                "symbol":          t["symbol"],
                "strategy":        STRATEGY_TAG,
                "state":           t["state"],
                "quantity":        qty,
                "blended_entry":   entry,
                "market_value_VND": qty * entry,
                "unrealized_pnl":  0.0,
                "tp1_hit":         t["state"] == "TP1_HIT",
                "signal_date":     t.get("signal_date"),
            })
        pos = pd.DataFrame(rows, columns=POSITIONS_COLS) if rows else pd.DataFrame(columns=POSITIONS_COLS)
        self._save_positions(pos)
        return pos

    def export_equity_curve(self, out_dir: Optional[Path] = None) -> Path:
        """Export closed-trade equity curve for dashboard Panel 10."""
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
                out / "s3_combo_paper_equity_curve.csv", index=False
            )
        return out
