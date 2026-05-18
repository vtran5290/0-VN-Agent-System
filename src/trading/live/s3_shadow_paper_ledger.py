"""S3 EMA21/55 max_hold=60 paper ledger — PAPER_TRADE_SHADOW only, never live/DNSE."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import pandas as pd

from src.trading.config import LiveTradingConfig, REPO_ROOT
from src.trading.live.paper_ledger import TRADES_COLS, POSITIONS_COLS

STRATEGY_TAG = "S3_SHADOW_MAX60"
_MAX_HOLD_BARS = 60
_TP1_PCT = 0.18
_TRAIL_ATR_MULT = 3.5

DATA_DIR = REPO_ROOT / "data" / "trading" / "live" / "s3_shadow"
S3_SHADOW_TRADES_PATH = DATA_DIR / "s3_shadow_trades.csv"

_LIVE_ORDER_ALLOWED = False
_DNSE_ALLOWED = False


def _guard_no_live_order() -> None:
    """Raise if anything attempts live order routing through S3 shadow ledger."""
    if _LIVE_ORDER_ALLOWED:
        raise RuntimeError(
            "S3 shadow paper ledger: live orders are not permitted. "
            "S3 max60 is paper-shadow only."
        )


def _guard_no_dnse() -> None:
    if _DNSE_ALLOWED:
        raise RuntimeError("S3 shadow paper ledger: DNSE routing not permitted.")


def _guard_no_live() -> None:
    _guard_no_live_order()


class S3ShadowPaperLedger:
    """Isolated S3 shadow book under data/trading/live/s3_shadow/."""

    def __init__(self, config: Optional[LiveTradingConfig] = None) -> None:
        from src.trading.config import REPO_ROOT

        if config and config.account_root and getattr(config, "account_id", "") == "S3_MAX60_SHADOW_PAPER":
            base = config.account_root
        else:
            base = REPO_ROOT / "data" / "trading" / "live" / "s3_shadow"
        base.mkdir(parents=True, exist_ok=True)
        self.root = base
        self._trades_path = base / "s3_shadow_trades.csv"
        if not self._trades_path.exists() and (base / "s3_shadow_paper_trades.csv").exists():
            self._trades_path = base / "s3_shadow_paper_trades.csv"
        self._positions_path = base / "s3_shadow_positions.csv"
        if not self._positions_path.exists() and (base / "s3_shadow_paper_positions.csv").exists():
            self._positions_path = base / "s3_shadow_paper_positions.csv"

    def _load_trades(self) -> pd.DataFrame:
        if self._trades_path.exists() and self._trades_path.stat().st_size > 0:
            return pd.read_csv(self._trades_path, dtype=object)
        return pd.DataFrame({c: pd.Series(dtype=object) for c in TRADES_COLS})

    def _save_trades(self, df: pd.DataFrame) -> None:
        df.to_csv(self._trades_path, index=False)

    def record_shadow_intent(self, row: dict) -> None:
        """Track paper-shadow row from scan — never affects A3 production ledger."""
        _guard_no_live()
        from src.trading.live.s3_flag import s3_shadow_block_reason

        if s3_shadow_block_reason(row.get("s3_no_real_order_flag")):
            raise ValueError("S3 shadow row requires explicit s3_no_real_order_flag=true")
        action = str(row.get("s3_shadow_action") or row.get("action", ""))
        if action not in ("PAPER_S3_SHADOW", "PAPER_S3_RESEARCH_MONITOR"):
            return
        trades = self._load_trades()
        sym = str(row.get("symbol", ""))
        date = str(row.get("date", ""))[:10]
        trade_id = f"S3SH-{sym}-{date}-{action}"
        if not trades.empty and (trades["trade_id"] == trade_id).any():
            return
        note = (
            f"S3_SHADOW_MAX60 paper-only TP{int(_TP1_PCT*100)}% "
            f"Trail{_TRAIL_ATR_MULT}x MaxHold{_MAX_HOLD_BARS} | {row.get('reason_code', '')}"
        )
        r = {c: None for c in TRADES_COLS}
        r.update({
            "trade_id": trade_id,
            "symbol": sym,
            "strategy": STRATEGY_TAG,
            "state": "PAPER_MONITOR",
            "signal_date": date,
            "notes": note,
        })
        self._save_trades(pd.concat([trades, pd.DataFrame([r])], ignore_index=True))

    def record_entry(
        self,
        symbol: str,
        signal_date: str,
        fill_price: float,
        value_vnd: float,
        quantity: int,
        **kwargs: Any,
    ) -> str:
        """Record a paper-shadow entry. Never routes live or DNSE."""
        _guard_no_live_order()
        _guard_no_dnse()
        trades = self._load_trades()
        trade_id = f"S3SH-{symbol}-{signal_date}"
        row = {c: None for c in TRADES_COLS}
        row.update({
            "trade_id": trade_id,
            "symbol": symbol,
            "strategy": STRATEGY_TAG,
            "state": "PAPER_T1",
            "signal_date": signal_date,
            "t1_order_date": signal_date,
            "t1_fill_price": fill_price,
            "t1_value_VND": value_vnd,
            "t1_quantity": quantity,
            "blended_entry": fill_price,
            "notes": (
                f"S3_SHADOW_MAX60 paper-only TP{int(_TP1_PCT * 100)}% "
                f"Trail{_TRAIL_ATR_MULT}x MaxHold{_MAX_HOLD_BARS} | "
                + str(kwargs.get("notes", ""))
            ),
        })
        row.update({k: v for k, v in kwargs.items() if k in TRADES_COLS})
        self._save_trades(pd.concat([trades, pd.DataFrame([row])], ignore_index=True))
        return trade_id
