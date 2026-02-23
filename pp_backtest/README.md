# Pocket Pivot + Sell v4 Backtest (03_Backtest_Lab)

Backtest entry (Pocket Pivot) and exit (Morales/Kacher sell rules) with **entry/exit at next open** (no look-ahead).

**Layer:** Research only — không ra quyết định real-time; agent đọc kết quả đã curate. Chi tiết: `docs/ARCHITECTURE_LAYERS.md`.

## Setup & Run

From **repo root**. FireAnt (no token) uses `src.intake.fireant_historical.fetch_historical`.

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r pp_backtest/requirements.txt
$env:PYTHONPATH = (Get-Location).Path
python -m pp_backtest.run
```

**macOS/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r pp_backtest/requirements.txt
export PYTHONPATH=$PWD
python -m pp_backtest.run
```

Use vnstock instead of FireAnt: `pip install vnstock` then `python -m pp_backtest.run --vnstock`.

**Chạy đúng .venv (tránh dùng Python global):** sau khi activate, kiểm tra `where python` hoặc `python -c "import sys; print(sys.executable)"` phải trỏ vào `.venv\Scripts\python.exe`. Hoặc gọi trực tiếp không cần activate:

```powershell
.\.venv\Scripts\python.exe -m pp_backtest.run
```

## Pivot (run đúng env)

Từ repo root, **khuyên dùng** (không lệch env):

```powershell
.\run_pivot.ps1
.\run_pivot.ps1 --tail -0.05 --mfe --mfe-bars 20
```

Hoặc gọi thẳng venv:

```powershell
$env:PYTHONPATH = (Get-Location).Path
.\.venv\Scripts\python.exe -m pp_backtest.pivot_ledger --tail -0.05 --mfe --mfe-bars 20
```

Nếu lỗi module: đảm bảo đã `pip install -r pp_backtest/requirements.txt` trong .venv.

## Data

- **FireAnt**: uses `src.intake.fireant_historical.fetch_historical` (same API/cache as weekly report). No token.
- **vnstock**: optional; `python -m pp_backtest.run --vnstock`.

## Output

- **pp_sell_backtest_results.csv**: stats per symbol (trades, win_rate, avg_ret, expectancy, profit_factor, max_drawdown, avg_hold_days).
- **pp_trade_ledger.csv**: one row per trade with **exit_reason** (SELL_V4 / MARKET_DD / STOCK_DD / EOD_FORCE), mkt_dd_count, stk_dd_count. Pivot by exit_reason to see which filter helps.

**Read order:** profit_factor (>1.2 ok, >1.5 good) → avg_ret → #trades → avg_hold_days → max_drawdown. Don’t rely on win_rate alone; avg_win >> avg_loss matters.

## Config

Edit `config.py`: BacktestConfig (start, end, fee_bps, slippage_bps), PocketPivotParams, SellParams. Tickers from `config/watchlist.txt` if present, else default list in `run.py`.
