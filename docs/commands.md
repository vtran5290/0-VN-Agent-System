# Commands

> See: docs/BACKTEST_WORKFLOW.md for the end-to-end backtest workflow.

## Quick start
- Full pipeline (watchlist):
  - `.\run_backtest_pipeline.ps1`
- Test fast 1 symbol:
  - `.\run_backtest_pipeline.ps1 -Symbols MBB`

## Run weekly
- `python -m src.report.weekly`
- `make weekly`

**Outputs:**
- data/decision/weekly_report.md
- data/state/regime_state.json
- data/decision/allocation_plan.json
- data/alerts/market_flags.json
- data/alerts/sell_signals.json

## Backtest
- **Baseline (no gate):** `.\.venv\Scripts\python.exe -m pp_backtest.run --no-gate`
- **Gate (default):** `.\.venv\Scripts\python.exe -m pp_backtest.run`
- Full watchlist: `python -m pp_backtest.run` (gate ON) hoặc `--no-gate` cho baseline.
- Sanity nhanh (1–3 symbols): `python -m pp_backtest.run --symbols MBB SSI VCI` — sau đó chạy full watchlist overnight / lúc rảnh (bar-by-bar setup_quality chậm). Tùy chọn: cache setup_quality_score per symbol (parquet/csv keyed by date) để lần sau chỉ merge.
- So baseline vs gate: cùng preset (PP_GIL_V4), cùng date range, cùng watchlist; nếu symbol count lệch do warm-up → xem counters skipped_due_to_warmup / skipped_due_to_gate.
- **A/B baseline vs SOFT_SELL (isolate effect):** Cả hai chạy **--no-gate**. Cùng **--start / --end** (hoặc cùng config), cùng **watchlist.txt** (không đổi symbol giữa hai lần), cùng **fee/slippage** (từ config). Baseline: `python -m pp_backtest.run --no-gate [--start 2018-01-01] [--end 2026-02-21]` → **ngay sau khi chạy** rename/move `pp_trade_ledger.csv` → `pp_trade_ledger_baseline.csv` (tránh ghi đè). Soft sell: `python -m pp_backtest.run --soft-sell --no-gate` (cùng start/end) → `pp_trade_ledger.csv` là bản mới. Không trộn gate vào A/B này.
- **SOFT_SELL:** `python -m pp_backtest.run --soft-sell --no-gate`. KPI: `python -m pp_backtest.kpi_from_ledger <ledger.csv>` (trades, PF, hold1_rate, tail5, sell_v4_exits, avg_hold_days, median_hold_days). Dòng đầu run in config: `confirmation_closes=1` (baseline) hoặc `confirmation_closes=2` (soft_sell) — dùng cho debug Check 1.
- **Checklist 30s:** Baseline → dòng [run] phải `confirmation_closes=1 gate=False`; soft_sell → `confirmation_closes=2 gate=False`. Hai lần chạy identical trừ confirmation_closes; nếu không → dừng. **Decision logic** (sell_v4↓, median_hold↑, PF, tail5) và **kỳ vọng** (PF >1.0 = regime shift): xem `docs/EXIT_DIAGNOSIS.md` mục paste format + decision table.
- **Nếu sell_v4_exits không giảm hoặc median_hold không tăng** — debug: Check 1 (confirmation_closes=2?), Check 2 (label shift?), Check 3 (stratified SELL_V4). Chi tiết trong EXIT_DIAGNOSIS.
- **Baseline VN realistic (đã chốt):** Mọi experiment dùng `python -m pp_backtest.run --no-gate --min-hold-bars 3`. **no_SELL_V4 experiment:** `python -m pp_backtest.run --no-gate --min-hold-bars 3 --no-sell-v4` (giữ STOCK_DD, MARKET_DD, UglyBar; tắt MA-trailing). So baseline_vn vs no_sell_v4; paste format + market_dd_exits/stock_dd_exits trong `docs/EXIT_DIAGNOSIS.md` mục no_SELL_V4. KPI: `python -m pp_backtest.kpi_from_ledger <ledger>` (có market_dd_exits, stock_dd_exits, ugly_bar_exits).
- Pivot (không lệch env): `.\run_pivot.ps1` hoặc `.\run_pivot.ps1 --mfe --mfe-bars 20`
- Publish knowledge (sau backtest): `.\.venv\Scripts\python.exe -m pp_backtest.publish_knowledge --strategy PP_GIL_V4 [--symbols MBB SSI ...] [--start 2018-01-01] [--end 2026-02-21]`
- Exit diagnosis: Test 3 + Test 1 stratified `python -m pp_backtest.exit_diagnosis`; Test 2 MFE/MAE 20 bars `python -m pp_backtest.exit_mfe_mae [--bars 20]` — xem `docs/EXIT_DIAGNOSIS.md`
- **Forward return (pre-registered):** `python -m pp_backtest.forward_return_analysis --ledger pp_backtest/pp_trade_ledger_baseline.csv --use-fetch` — f5/f10/f20 từ entry close; output `knowledge/forward_return_summary.json`.
- **f10 vs realized gap:** `python -m pp_backtest.realized_vs_f10 --ledger pp_backtest/pp_trade_ledger_baseline.csv --use-fetch --fee-bps 30` — diagnoses: EXIT_TIMING / FEE_EROSION / EXIT_SAVING_TAIL. Xem `docs/EXIT_DIAGNOSIS.md` mục f10 vs realized gap.
- **Regime MA200 (pre-registered):** `python -m pp_backtest.run --no-gate --regime-ma200` — trade chỉ khi VN30 close > MA200. Xem `docs/EXIT_DIAGNOSIS.md` mục Regime filter MA200.
- **Regime liquidity:** `python -m pp_backtest.run --no-gate --regime-liquidity` — trade chỉ khi VN30 30d vol > 126d vol. Hold-out PF > 0.924 = meaningful.
- **PP_GIL_V4.2 structural gates:** `--above-ma50` (close > MA50), `--demand-thrust` (close in upper 30% range), `--tightness` (2 of last 5 bars vol < MA20 vol). Test từng bước; spec: `docs/PP_GIL_V4_STRUCTURAL_UPGRADE.md`.
- **Exit experiments (delay arming):** `--exit-fixed-bars 10` = oracle (exit đúng 10 bars, no SELL_V4/DD). `--exit-armed-after N` = Phase 1 (bars 1..N-1) chỉ UglyBar; từ bar N full SELL_V4+DD. Test ladder N=5,10,15. Metrics: PF, tail5, max_drawdown, avg_ret, win_rate, avg_win, avg_loss, median_hold_bars. Chi tiết: `docs/EXIT_DIAGNOSIS.md` mục Delay arming.
- **PP / Buy-Sell tweaks (Gil 2010/2012):** Ưu tiên VN: U&R → Established Uptrend → Vol 10 vs 15. Pre-registered: `docs/PP_TWEAKS_RESEARCH.md`; signals: `pp_backtest/signals.py` (undercut_rally_signal, established_uptrend_filter).
- **Điều kiện sách Gil/Kacher → encode VN:** 5 nhóm (market context, supply-demand, buy setups, sell logic, pattern). Không brute-force; chọn 1 setup + 1 regime + 1 exit. Next recommend: **Weekly PP** (spec pre-registered). `docs/GIL_BOOK_CONDITIONS.md`.
- **Book regime (market luôn bật khi test book):** `--book-regime` = FTD (VN30 close>MA50 & MA50 slope>0) + no new positions khi dist_days_last_10>=3. Dùng cùng bất kỳ entry nào (pp, undercut_rally, bgu). Module: `pp_backtest/market_regime.py`.
- **Entry BGU / pattern filters:** `--entry-bgu` = Buyable Gap-Up (gap≥3%, vol≥1.5×avg). `--right-side` = close > midpoint last 3m range. `--avoid-extended` = distance from MA10 < 5%. Có thể kết hợp với `--book-regime`.
- **Darvas / Livermore (Swing+Position):** `--entry darvas | livermore_rpp | livermore_cpp`, `--exit darvas_box | livermore_pf | ma20 | ma50`. Stateful Darvas trailing; Livermore K-bar failure `--livermore-pf-k 2|3|5`; `--rs-filter` (Darvas RS); `--pyramid-darvas` / `--pyramid-livermore`. Research design: `docs/RESEARCH_DESIGN_DARVAS_LIVERMORE.md`.
- **Weekly backtest (Gil/Kacher):** `python -m pp_backtest.run_weekly [--start 2012-01-01] [--end 2026-02-21] [--watchlist config/watchlist_80.txt] [--entry-3wt] [--fee-bps 30]`. Entry = Weekly PP (mặc định) và/hoặc 3WT breakout; market regime (FTD-style proxy + no_new_positions) **luôn bật**. Exit: close_week < MA10_week hoặc MARKET_DD ≥ 3/10 tuần. Output: `pp_backtest/pp_weekly_ledger.csv`.
- **Exec subset + cost stress (deploy check):** `python -m pp_backtest.portfolio_exec_stats pp_backtest/pp_weekly_ledger.csv` (base). Full stress RT30/40/60: `python -m pp_backtest.portfolio_exec_stats pp_backtest/pp_weekly_ledger.csv --stress`. Báo PF_exec, EV_exec, Median_ret_exec, Exposure_tw (time-weighted). Decision: RT40 PF_exec > 1.15 và EV > 0 → pilot ok; RT60 PF_exec ~1 → không scale. Xem `docs/BOOK_TEST_LADDER.md`.
- **Test Ladder (book conditions):** Ma trận test + **IC Scorecard** (Gate 1–4, trades drop ≤50%, Top 5 >60% = auto fail), **Escape hatch** (nếu không model pass final → dừng pattern research, pivot regime/rotation), **Market modes** m0/m1/m2 (ablation C1/C2: `make book-c1-val-m0` … `book-c2-val-m2`), survivorship bias (static 80). Chi tiết: `docs/BOOK_TEST_LADDER.md`.

**Trade log (Phase 2 — analyze_trades):** Dùng template `trade_logs/my_trades_template.csv` (cột: trade_id, symbol, entry_date, entry_price, exit_date, exit_price, strategy_id, setup_tag, entry_note, exit_note, …).

**Knowledge (JSON → Markdown view):** `python knowledge/render_weekly_note.py [--date YYYYMMDD]` → `knowledge/weekly_notes/YYYYMMDD.md`. Source of truth is JSON; MD is generated only.

**Nguyên tắc:** Claude Code chỉ cần mở repo → đọc CLAUDE.md + ops_for_claude.md → chạy lệnh.

---

## Minervini backtest — đóng vòng (Decision layer)

- **Playbook đầy đủ:** `minervini_backtest/docs/RUN_PLAYBOOK_CLOSED_LOOP.md`
- Bộ 3 output: (A) decision_matrix, (B) gate_attribution A+B, (C) walk_forward realism M3/M4. Sau đó: `decision_layer_from_outputs.py` → draft; `deploy_gates_check.py` → DEPLOY / ITERATE.
- Nếu fail: iterate I2 (M4+M10) → I1 (M9+M6) → I3 (M7+core). Template + interpret nhanh: `minervini_backtest/docs/DECISION_LAYER_TEMPLATE.md`. Paste 4 cụm (matrix fee30 + gate A/B + walk_forward M3/M4) → điền đủ Decision layer (Survivors, actions, risks, Watchlist, Signals, If X→do Y).
