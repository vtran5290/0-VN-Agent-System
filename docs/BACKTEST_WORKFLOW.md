# Backtest Workflow (PP_GIL_V4)

## 0) Chuẩn bị
- Mở PowerShell tại repo root
- Activate venv:
  - `.\.venv\Scripts\Activate.ps1`
- Verify env:
  - `where python`
  - `python -c "import sys; print(sys.executable)"`

## 1) Run backtest
- Full watchlist:
  - `python -m pp_backtest.run`
- Test nhanh 1 mã:
  - `python -m pp_backtest.run --symbols MBB`

Outputs:
- `pp_backtest/pp_sell_backtest_results.csv`
- `pp_backtest/pp_trade_ledger.csv`

## 2) Pivot (tail + MFE MARKET_DD)
- Pivot cơ bản:
  - `.\run_pivot.ps1`
- Tail + MFE:
  - `.\run_pivot.ps1 --tail -0.05 --mfe --mfe-bars 20`

## 3) Publish knowledge
- Full watchlist:
  - `python -m pp_backtest.publish_knowledge --strategy PP_GIL_V4 --start 2018-01-01 --end 2026-02-21`
- 1 mã:
  - `python -m pp_backtest.publish_knowledge --strategy PP_GIL_V4 --symbols MBB --start 2018-01-01 --end 2026-02-21`

Expected:
- `knowledge/backtests/<SYMBOL>/PP_GIL_V4.json`
- `knowledge/backtests/index.json` updated

## 4) Weekly report (Decision injection)
- `python -m src.report.weekly`

Verify:
- Backtest edge block appears
- Relevance label
- Footer counters: Knowledge used / records queried / loaded / stale warnings

## 5) Weekly note (JSON → MD)
- `python knowledge/render_weekly_note.py`
Output:
- `knowledge/weekly_notes/YYYYMMDD.md`

## 6) Quick start (1 command)
- Full:
  - `.\run_backtest_pipeline.ps1`
- 1 mã:
  - `.\run_backtest_pipeline.ps1 -Symbols MBB`
