# Full Workflow Engine + Repo Extract — for external review (e.g. ChatGPT)

> **Mục đích:** Tài liệu này mô tả toàn bộ luồng (data → universe → optional ThemePack → signals → regime → entry/exit → ledger → KPI), bề mặt CLI/config, và cấu trúc repo + artifacts. Copy toàn bộ file này gửi ChatGPT để review mà không cần đọc codebase.
>
> **Cập nhật:** Bao gồm ThemePack optional pre-filter (AI_Energy_Overspill_VN); backtest không đổi bar-by-bar logic, gates, hay ledger format.

---

## 1. Tổng quan kiến trúc

```
[Data] VN30 + per-symbol OHLCV (FireAnt or vnstock)
    ↓
[Universe] watchlist | liquidity_topn | (optional) ThemePack candidates CSV
    ↓
[ThemePack Ranker] (optional) Cross-sectional fundamentals + macro tags → data/raw/candidates/<pack>_candidates.csv
    │  Consumed by backtest when --candidates <path> points to a .csv (symbol column = universe). No new gates; pre-filter only.
    ↓
[Market regime] VN30: mkt_dd_count, optional regime_on (MA200), liquidity_on (30d>126d vol), book_regime, meta_trending, lolr_risk_on
    ↓
[Per-symbol] Entry signal: PP | Darvas breakout | Livermore RPP/CPP | U&R | BGU
    ↓
[Entry gates] (optional, applied in order) liquidity → regime_ma200 → meta_v1 → dist_entry → book_regime → above_ma50 → demand_thrust → tightness → right_side → avoid_extended
    ↓
[Backtest loop] Bar-by-bar: entry at next open when entry_signal; exit at next open when exit_signal (or fixed_bars / armed_after / Darvas trailing / Livermore K-bar)
    ↓
[Ledger] One row per trade: entry_date, exit_date, entry_px, exit_px, ret, hold_cal_days, hold_trading_bars, exit_reason, symbol, engine
    ↓
[Outputs] pp_sell_backtest_results.csv (per-symbol stats), pp_trade_ledger.csv (all trades), [aggregate] PF/tail5/maxDD/median_hold_bars
    ↓
[KPI] python -m pp_backtest.kpi_from_ledger <ledger.csv> → trades, PF, hold1_rate, tail5, exit_reason counts, median_hold_bars
```

- **Entry** và **exit** tách bạch: entry = “có được phép mở lệnh không”, exit = “có được phép đóng lệnh không” (bao gồm min_hold_bars).
- **Cost:** fee_bps + slippage_bps áp vào entry (mua) và exit (bán); round-trip = 2×(fee_bps + slippage_bps) bps.

---

## 2. Data

- **Nguồn:** `pp_backtest/data.py` — `fetch_ohlcv_fireant(symbol, start, end)` hoặc `fetch_ohlcv_vnstock(...)`. Chọn qua `--vnstock`.
- **Market:** Luôn fetch VN30 cho `mkt_dd_count` và (nếu bật) regime columns. Merge vào từng symbol theo `date`.
- **Universe:** Mặc định `config/watchlist.txt`; override bằng `--watchlist <path>` (vd. `config/watchlist_80.txt`). Có thể dùng `--universe liquidity_topn --liq-topn N` để top N theo median value 60d theo năm (không forward bias).
- **ThemePack (optional pre-filter):** Ranker cross-sectional fundamentals + macro tags (vd. AI_Energy_Overspill_VN) xuất ra `data/raw/candidates/ai_energy_overspill_candidates.csv` (symbol, tier, total_score, lane, flags) và `data/features/theme_scores/ai_energy_overspill_scores_YYYYMMDD.csv`. Backtest **không** thêm gate mới; khi `--candidates <path>` trỏ tới file `.csv` có cột `symbol`, engine dùng danh sách symbol đó làm universe (ghi đè watchlist/liquidity_topn cho bước chọn symbol). Chạy ranker: `python -m src.theme.run_theme_pack --pack config/theme_packs/ai_energy_theme_pack_v1.json --asof YYYY-MM-DD [--watchlist <path>] [--topk 30]`.

### 2.1 ThemePack (optional) — chi tiết

- **Config:** `config/theme_packs/ai_energy_theme_pack_v1.json` — lanes (GRID_EPC, GRID_EQUIP, POWER_GEN, INDUSTRIAL_PARK, DATA_CENTER_REAL, MATERIALS), weights_by_lane (Q,R,T,V,M), thresholds, missing_policy, flags.
- **Input:** Fundamentals snapshot `data/sources/company/fundamentals_snapshot.csv` (best-effort columns: symbol, roe_5y_median, roic_5y_median, fcf_margin_5y_median, fcf_positive_years_5y, net_debt_to_ebitda, interest_coverage, working_capital_days, capex_to_sales_5y, pe_ttm, pb_ttm, ev_ebitda_ttm, fwd_pe, gross_margin_stability). Universe: `--watchlist` hoặc `--symbols` hoặc mặc định từ config.
- **Scoring:** Q (Quality), R (Resilience), T, V (Valuation), M; rank-percentile 0..100; lane-specific weights; missing_policy=neutral; flags: weak_interest_cover (interest_coverage<2), high_leverage (net_debt_to_ebitda>4), wc_trap (GRID_EPC, working_capital_days>180). Tier1: score≥75 no flags; Tier2: score≥60; Tier3: else.
- **Outputs:** (1) `data/raw/candidates/ai_energy_overspill_candidates.csv` — symbol, tier, total_score, lane, flags. (2) `data/features/theme_scores/ai_energy_overspill_scores_YYYYMMDD.csv` — full scored table.
- **Backtest consumption:** `python -m pp_backtest.run ... --candidates data/raw/candidates/ai_energy_overspill_candidates.csv` → universe = symbols từ cột symbol (không đổi gates/exit/ledger).

### 2.2 FRED ingestion (US macro / US_FISCAL_STRESS)

- **Mục đích:** Lấy chuỗi macro Mỹ từ FRED (yields, SOFR, deficit proxy, term premium, breakeven) cho US Fiscal Stress Regime Pack; cache 24h, không hardcode API key.
- **Env:** `FRED_API_KEY` (bắt buộc).
- **CLI:** `python -m src.macro.fred_fetch_us_fiscal_stress --asof YYYY-MM-DD` (tùy chọn `--force` để bỏ qua cache).
- **Output snapshot:** `data/sources/macro/fred_us_fiscal_stress_snapshot.json` — asof_date (UTC ISO), từng series: series_id, **series_title** (từ FRED series endpoint, để audit), latest_value, observation_date, units, frequency, source_url; lỗi → status="error", run vẫn thành công.
- **Guard term premium:** Nếu series THREEFYTP10 có series_title không chứa "Term Premium" và "10-Year", derived set term_premium = null và flag `term_premium_series_suspect` (tránh silent poison).
- **Output derived:** yields, term_premium (khi guard pass), real_rates.real_10y_proxy_pct (DGS10 − T10YIE), funding_stress.sofr_value, fiscal_path.primary_deficit_pct_gdp, usd.dxy_trend=unknown.
- **Cache:** `data/cache/fred/<series_id>_<end_date>.json`, TTL 24h.
- **Chuỗi FRED:** DGS2, DGS10, DGS30, SOFR, FYFSGDA188S; tùy chọn T10YIE, FEDFUNDS, THREEFYTP10.

### 2.3 Build us_fiscal_inputs (orchestrator, no manual merge)

- **CLI:** `python -m src.macro.build_us_fiscal_inputs --asof YYYY-MM-DD [--force]`
- **Chức năng:** Gọi FRED fetch (hoặc đọc cache) + Treasury auctions fetch, merge vào một file duy nhất `data/features/macro/us_fiscal_inputs.json` (schema ổn định). In `coverage_weight` và `signal_quality_preview` (không chạy scoring).
- **Treasury:** Bỏ TIPS và FRN; snapshot lưu cusip, security_type, auction_date, issue_date để audit. Mapping auctions → inputs.auctions.* (bid_to_cover, indirect_pct) gộp vào merged output.

### 2.4 Geo Hormuz energy shock layer (deterministic, rules-based)

- **Mục đích:** Theo dõi nhanh “Hormuz war layer” theo multi-order thinking:
  - Order 1: Conflict/shipping risk → oil risk premium (Brent, tanker rates, backwardation, volatility).
  - Order 2: Oil → VN inflation & policy constraint (xăng dầu nội địa, CPI proxy, SBV liquidity).
  - Order 3: Policy/FX/liquidity → TTCK (rates/FX stress, duration/leverage names chịu áp lực).
  - Order 4: Sector map (winners/losers; rubber = mixed, không xử lý như energy beta thuần).
- **Inputs (manual/ingest):** `data/raw/geo_hormuz_energy_shock_inputs.json`
  - Schema (`inputs` key): conflict_level 0–5, hormuz_transit_status (`normal|slowed|rerouting|partial_stop`), events_24h (tags), brent_usd_bbl, brent_change_5d_pct, backwardation_1m_6m, tanker_rates_change_5d_pct, oil_volatility_proxy, vn_fuel_price_adjustment, sbv_liquidity_direction (`easing|neutral|tightening|withdrawing|absorbing|unknown`), usd_vnd_pressure (`down|stable|mild|up|pressure|severe|unknown`).
- **CLI:** `python -m src.macro.run_geo_hormuz_energy_shock --input data/raw/geo_hormuz_energy_shock_inputs.json --out data/state/geo_hormuz_energy_shock.json --asof YYYY-MM-DD`
- **Output layer:** `data/state/geo_hormuz_energy_shock.json`
  - `layer`: `"geo_hormuz_energy_shock"`
  - `version`: `"v1.0"`
  - `asof`: ngày chạy (từ `--asof` hoặc `inputs.asof_date`)
  - `inputs`: bản normalize lại các trường input (giữ nguyên events_24h để audit fact)
  - `state`:
    - `risk_state`: `ENERGY_SHOCK_LOW|MED|HIGH` (rule-of-thumb: conflict_level, Brent 5d %, tanker_rates_change_5d_pct, transit_status)
    - `inflation_risk_vn`: `low|medium|high` (kết hợp risk_state + Brent/xăng dầu VN + USD/VND pressure)
    - `sbv_policy_constraint`: `low|medium|high` (inflation risk + SBV liquidity direction)
  - `transmission_map_vn`: winners/losers cho TTCK VN:
    - `beneficiaries`: `["oil_gas_upstream", "oil_gas_services"]`
    - `neutral_mixed`: `["rubber"]` (kênh substitution NR/SR vs. demand lốp/Trung Quốc)
    - `headwinds`: `["airlines", "transport_logistics", "rate_sensitive_real_estate"]`
  - `decision_rules`: `"to_MED"` (`conflict_level>=3`, `brent_change_5d_pct>=5`), `"to_HIGH"` (`conflict_level>=4`, `brent_change_5d_pct>=10`, `hormuz_transit_status in ['partial_stop','rerouting']`)
  - `notes`: facts-first reminders (Hormuz là chokepoint, rubber impact mixed, không assume “oil lên thì cao su luôn lên”).
- **Integration:** Weekly engine:
  - Khi có `data/state/geo_hormuz_energy_shock.json`, `python -m src.report.weekly`:
    - Gắn full layer vào `data/decision/weekly_report.json` dưới key `geo_hormuz_energy_shock`.
    - In một dòng tóm tắt trong `weekly_report.md` (`## Execution & Monitoring`): `risk_state`, `inflation_risk_vn`, `sbv_policy_constraint`.

---

## 3. Entry engines (--entry)

| Engine | Mô tả ngắn | Exit mặc định | Ghi chú |
|--------|------------|----------------|---------|
| **pp** | Pocket Pivot (Gil/Morales–Kacher): vol > max down-day vol, close ≥ prev close, on MA10/20/50 + slope. | Full stack (SELL_V4 + MARKET_DD + STOCK_DD + UglyBar) | Có thể thêm U&R (`--entry-undercut-rally`), BGU (`--entry-bgu`). |
| **darvas** | Darvas box breakout (L=20, touch_high_min=2, touch_low_min=1, vol_k, optional RS filter). | darvas_box (trailing box low − buffer) | Gate tắt (setup_quality là PP-specific). |
| **livermore_rpp** | Livermore reversal pivot (N=10, volume confirm). | livermore_pf (close < trigger trong K bars) | Cần VN30 `lolr_risk_on`. |
| **livermore_cpp** | Livermore continuation pivot (L=20, vol_k, above_ma=20). | livermore_pf | Idem. |

- **PP:** Signals trong `pp_backtest/signals.py`: `pocket_pivot()`, `sell_morales_kacher_v4()`, `distribution_day_count_series()`. Cột `pp` (bool) và `sell_final` = sell_v4 | sell_mkt_dd | sell_stk_dd (hoặc no_sell_v4 thì chỉ DD + ugly_only).
- **Darvas:** `signals_darvas.py` — `darvas_box()`, `entry_darvas_breakout()`, `exit_darvas_box_low()`. Có pyramiding (`--pyramid-darvas`).
- **Livermore:** `signals_livermore.py` — `market_filter_lolr`, `entry_livermore_reversal_pivot` / `entry_livermore_continuation_pivot`, `exit_livermore_pivot_failure`, `exit_livermore_ma20` / `ma50`. Có `--livermore-pf-k 2|3|5`, `--pyramid-livermore`.

---

## 4. Entry gates (chồng lên entry_signal)

Áp dụng tuần tự trong backtest; mỗi gate AND vào tín hiệu trước:

| Gate | CLI | Định nghĩa | Nguồn |
|------|-----|------------|--------|
| Liquidity | `--regime-liquidity` | VN30: 30d vol > 126d vol | Pre-registered |
| MA200 regime | `--regime-ma200` | VN30 close > MA200 | Pre-registered |
| Meta v1 | `--meta-v1` | VN30 close > MA(period), MA slope > 0 (5 bars), ATR14/close < vol_max | docs/META_LAYER_SPEC.md |
| Dist entry | `--dist-entry-max N` | No new entry when VN30 dist days (20d) ≥ N | O'Neil |
| Book regime | `--book-regime` | FTD (close>MA50 & MA50 slope>0) + no_new_positions when dist_days_last_10≥3 | market_regime.py |
| Above MA50 | `--above-ma50` | Stock close > stock MA50 | PP_GIL_V4.2 |
| Demand thrust | `--demand-thrust` | close > close[-1] and close ≥ high − 0.3×(high−low) | PP_GIL_V4.2 |
| Tightness | `--tightness` | ≥ 2 of last 5 bars with volume < MA20(volume) | PP_GIL_V4.2 |
| Right side | `--right-side` | close > midpoint of last 3m range | Gil |
| Avoid extended | `--avoid-extended` | distance from MA10 < 5% | Gil |

- **Exp4 (PP_GIL_V4.2 champion):** liquidity + above_ma50 + demand_thrust + tightness (không bắt buộc right_side / avoid_extended).
- **Setup quality gate:** Khi `gate=True` (mặc định với PP), entry còn cần `setup_quality_score >= 50` (từ `src.signals.setup_quality`). Darvas/Livermore chạy với gate=False.

---

## 5. Exit logic

- **Full stack (mặc định cho PP):** `sell_final` = sell_v4 | sell_mkt_dd | sell_stk_dd. sell_v4 = Morales–Kacher tier (MA10/20/50); sell_mkt_dd khi mkt_dd_count ≥ 5; sell_stk_dd khi stk_dd_count ≥ 3; UglyBar nằm trong sell_v4 hoặc sell_ugly_only khi `--no-sell-v4`.
- **Fixed bars:** `--exit-fixed-bars N` — thoát đúng sau N bars (và ≥ min_hold_bars). Dùng làm “oracle” để test alpha vs exit.
- **Armed after:** `--exit-armed-after N` — bars 1..N-1 chỉ thoát bởi UglyBar (sell_ugly_only); từ bar N trở đi dùng full sell_final. Test delay arming.
- **Darvas:** Exit khi close < trailing(box_low) − buffer (stateful).
- **Livermore:** Exit khi close < trigger_level trong K bars (`--livermore-pf-k`); hoặc exit ma20/ma50 nếu `--exit ma20|ma50`.
- **Min hold:** Mọi exit đều chỉ được thực thi khi `bars_held >= min_hold_bars` (CLI: `--min-hold-bars`, mặc định 0; VN realistic = 3).

---

## 6. Config (code)

- **BacktestConfig** (`pp_backtest/config.py`): start, end, fee_bps, slippage_bps, min_hold_bars, allow_short, use_adjusted.
- **PocketPivotParams:** vol_lookback, ma_touch_tol_pct, slope_bars, slope_tol_pct.
- **SellParams:** enable_ma20_tier, ugly_atr_mult, ugly_closepos, heavy_vol_x_ma50, ride_bars_10/20, ride_tol_10/20, linger_bars_50, porosity_50, confirmation_closes (1 = baseline, 2 = SOFT_SELL).

Override từ CLI: `--start`, `--end`, `--fee-bps`, `--slip-bps`, `--min-hold-bars`.

---

## 7. Bề mặt CLI chính (run.py)

- **Universe / data:** `--watchlist`, `--symbols`, `--start`, `--end`, `--vnstock`, `--universe`, `--liq-topn`, `--candidates` (txt = pool cho liquidity_topn; .csv có cột symbol = ThemePack universe, bỏ qua liquidity_topn).
- **Entry:** `--entry pp|darvas|livermore_rpp|livermore_cpp`, `--entry-undercut-rally`, `--entry-bgu`, `--no-gate`, `--soft-sell`, `--no-sell-v4`.
- **Gates:** `--regime-liquidity`, `--regime-ma200`, `--above-ma50`, `--demand-thrust`, `--tightness`, `--right-side`, `--avoid-extended`, `--book-regime`, `--meta-v1`, `--dist-entry-max`.
- **Exit:** `--exit-fixed-bars`, `--exit-armed-after`, `--exit darvas_box|livermore_pf|ma20|ma50`, `--livermore-pf-k`.
- **Cost / VN:** `--fee-bps`, `--slip-bps`, `--min-hold-bars`.
- **Darvas/Livermore:** `--darvas-relaxed`, `--darvas-tol`, `--darvas-stability-bars`, `--darvas-touch-gap`, `--darvas-max-range-pct`, `--darvas-no-new-high`, `--darvas-no-confirm`, `--darvas-vol-k`, `--rs-filter`, `--pyramid-darvas`, `--pyramid-livermore`.

Mỗi run in ra dòng `[run]` với config_hash, commit, start, end, symbols, entry, exit, entry_gates, min_hold_bars, fee_bps, slip_bps, exit_mode; sau đó bảng per-symbol và `[aggregate]` / `[summary]`.

---

## 8. Outputs

- **pp_backtest/pp_sell_backtest_results.csv:** Mỗi symbol một dòng — trades, win_rate, avg_ret, expectancy, median_ret, avg_win, avg_loss, profit_factor, max_drawdown, avg_hold_days, (optional) tail5, median_hold_bars, skipped_due_to_*, filtered_by_*.
- **pp_backtest/pp_trade_ledger.csv:** Mỗi trade một dòng — entry_date, exit_signal_date, exit_date, entry_px, exit_px, ret, hold_cal_days, hold_trading_bars, exit_reason, symbol, engine, (optional) entry_bar_index, …
- **KPI từ ledger:** `python -m pp_backtest.kpi_from_ledger [path]` → trades, PF, hold1_rate, tail5_loss, sell_v4_exits, market_dd_exits, stock_dd_exits, ugly_bar_exits, avg_hold_days, median_hold_days, median_hold_bars.

---

## 9. File quan trọng

| File | Vai trò |
|------|--------|
| `pp_backtest/run.py` | Điều phối: load tickers, fetch VN30, build regime, loop symbol → fetch → entry/exit prep → run_single_symbol_with_ledger → gộp ledger, ghi CSV, in aggregate. |
| `pp_backtest/backtest.py` | `run_single_symbol_with_ledger`: áp dụng gates (e0..e6), entry_signal, exit_signal; loop bar-by-bar entry/exit, min_hold, fixed/armed/Darvas/Livermore; trả về stats + ledger DataFrame. |
| `pp_backtest/signals.py` | pocket_pivot(), sell_morales_kacher_v4(), distribution_day_count_series(); above_ma50, demand_thrust, tightness_ok; U&R, BGU, right_side, avoid_extended. |
| `pp_backtest/signals_darvas.py` | darvas_box(), entry_darvas_breakout(), exit_darvas_box_low(). |
| `pp_backtest/signals_livermore.py` | market_filter_lolr, entry_livermore_*_pivot, exit_livermore_pivot_failure, exit_livermore_ma20/ma50. |
| `pp_backtest/config.py` | BacktestConfig, PocketPivotParams, SellParams. |
| `pp_backtest/data.py` | fetch_ohlcv_fireant, fetch_ohlcv_vnstock. |
| `pp_backtest/market_regime.py` | add_book_regime_columns (FTD, no_new_positions). |
| `pp_backtest/kpi_from_ledger.py` | Đọc ledger CSV, in trades, PF, tail5, hold metrics, exit_reason counts. |

---

## 10. Decision / research context (tóm tắt)

- **Exp4 (PP_GIL_V4.2):** Entry = PP + liquidity + above_ma50 + demand_thrust + tightness. Đã lock là “champion” research; với 30 bps + min_hold=3, PF < 1 trên hold-out realistic → không deploy cơ học.
- **Exit:** Fixed 10-bar cho thấy alpha ở entry (PF tăng khi tắt SELL_V4/DD); delay arming (`--exit-armed-after N`) là hướng đã pre-register để giữ risk control nhưng giảm cắt trend sớm.
- **Chi tiết quy trình test, red flags, bảng robustness, final test:** `docs/EXIT_DIAGNOSIS.md`. Lệnh nhanh: `docs/commands.md`.

---

## 11. Cấu trúc thư mục repo + nơi lưu artifacts

### Thư mục cấp cao (chính)

```
0. VN Agent System/
├── config/                 # Watchlist, universe, thresholds (watchlist.txt, watchlist_80.txt, universe_186.txt, thresholds.yaml)
├── data/                   # Input/state/output của weekly + intake + decisions (xem dưới)
├── decision_log/           # Council / decision log (audit, blockers)
├── docs/                   # Tài liệu (EXIT_DIAGNOSIS, commands, WORKFLOW_ENGINE_EXTRACT, BACKTEST_WORKFLOW, …)
├── knowledge/              # Backtest JSON, weekly notes, logs (publish_knowledge, render_weekly_note)
├── logs/                   # Runtime logs (tùy script)
├── minervini_backtest/     # Minervini funnel/WF/decision (scripts, outputs, data/raw)
├── pp_backtest/            # PP/Gil/Darvas/Livermore engine (run, backtest, signals, config, data, rulecards)
├── prompts/                # Prompt templates (council, research, consensus, …)
├── scripts/                # PowerShell / helper scripts (pipeline, pivot)
├── src/                    # Weekly report, intake, regime, signals, alloc, smart_money, theme (ThemePack), …
├── trade_logs/             # Template + manual trade log (Phase 2)
├── agents/                 # Agent-related config
└── .cursor/, .venv/        # IDE, venv (không commit artifacts)
```

### data/ — Input, cache, state, decisions

| Thư mục / file | Nội dung / artifacts |
|----------------|----------------------|
| **data/alerts/** | market_flags.json, sell_signals.json (output weekly) |
| **data/cache/** | data/cache/fireant/ — cache OHLCV FireAnt (XML theo symbol+hash) |
| **data/canslim_features/** | CSV theo ngày (features CANSLIM) |
| **data/decision/** | weekly_report.md, allocation_plan.json, regime_state.json, trade_diagnostic_*.json, lesson_learned_*.md, council_audit_monthly.md |
| **data/features/** | Features đã build |
| **data/features/theme_scores/** | ThemePack full scored table: ai_energy_overspill_scores_YYYYMMDD.csv |
| **data/history/** | Lịch sử theo ngày (2026-02-20, …) |
| **data/intake/** | inbox/, processed/, rejected/ — Research machine intake |
| **data/raw/** | consensus_pack, research_engine_pack, trades, current_pos_preview.csv |
| **data/raw/candidates/** | ThemePack output: ai_energy_overspill_candidates.csv (symbol, tier, total_score, lane, flags) — backtest dùng với --candidates |
| **data/smart_money/** | smart_money weekly (input cho consensus pack) |
| **data/sources/** | company, macro, policy, sector (nguồn dữ liệu) |
| **data/sources/macro/** | fred_us_fiscal_stress_snapshot.json (FRED fetch cho US_FISCAL_STRESS) |
| **data/features/macro/** | us_fiscal_inputs.json (derived từ FRED snapshot, input cho fiscal stress pack) |
| **data/cache/fred/** | Cache response FRED theo series_id và end_date, TTL 24h |
| **data/state/** | regime_state.json, us_fiscal_stress.json, geo_hormuz_energy_shock.json (macro/state layers) |
| **data/summaries/** | company, macro, policy, sector (tóm tắt) |

### pp_backtest/ — Artifacts backtest PP/Gil

| File / thư mục | Nội dung |
|----------------|----------|
| **pp_backtest/pp_sell_backtest_results.csv** | Kết quả per-symbol (trades, PF, avg_ret, max_drawdown, …) — ghi đè mỗi run |
| **pp_backtest/pp_trade_ledger.csv** | Ledger tổng hợp tất cả trades — ghi đè mỗi run |
| **pp_backtest/pp_weekly_ledger.csv** | Ledger backtest weekly (run_weekly) |
| **pp_backtest/pp_trade_ledger_baseline.csv** | Copy tay sau run baseline (A/B) |
| **pp_backtest/pp_trade_ledger_train.csv** | Copy tay nếu tách train |
| **pp_backtest/rulecards/** | Rule cards Gil (PP, CPP, BGU, MARKET_CONTEXT, …) |
| **pp_backtest/audit_*.csv** | Audit Darvas/Livermore (nếu có script ghi) |

### knowledge/ — Publish & weekly notes

| Thư mục / file | Nội dung |
|----------------|----------|
| **knowledge/backtests/** | Thư mục con theo symbol (MBB, SSI, …) chứa PP_GIL_V4.json; index.json |
| **knowledge/logs/** | Logs từ render/publish |
| **knowledge/weekly_notes/** | YYYYMMDD.md (generate từ JSON) |

### minervini_backtest/ — Minervini artifacts

| Thư mục / file | Nội dung |
|----------------|----------|
| **minervini_backtest/data/raw/** | CSV OHLCV theo symbol (curated, raw) |
| **minervini_backtest/outputs/** | 2012_2026/, 2018_2024_liq/, fa_cohort/, fa_hybrid_experiment/, gates/ — funnel, wf_*.csv, decision_matrix_*.csv, summary.md, cohort_returns, yearly_alpha, … |

### Nơi agent / script ghi artifacts (tóm tắt)

- **Backtest (pp_backtest.run):** `pp_backtest/pp_sell_backtest_results.csv`, `pp_backtest/pp_trade_ledger.csv`.
- **Weekly report:** `data/decision/weekly_report.md`, `data/state/regime_state.json`, `data/decision/allocation_plan.json`, `data/alerts/market_flags.json`, `data/alerts/sell_signals.json`.
- **Publish knowledge:** `knowledge/backtests/<SYMBOL>/PP_GIL_V4.json`, `knowledge/backtests/index.json`.
- **Weekly note render:** `knowledge/weekly_notes/YYYYMMDD.md`.
- **Consensus / research pack apply:** Ghi vào data/decision, data/intake (theo Makefile / mapper).
- **Minervini pipeline:** `minervini_backtest/outputs/<experiment>/` (funnel, wf, decision_matrix, summary).
- **Cache OHLCV:** `data/cache/fireant/*.xml` (khi dùng FireAnt fetch).
- **ThemePack:** `data/raw/candidates/<pack>_candidates.csv`, `data/features/theme_scores/<pack>_scores_YYYYMMDD.csv` (khi chạy `python -m src.theme.run_theme_pack`).
- **Build inputs (recommended):** `python -m src.macro.build_us_fiscal_inputs --asof YYYY-MM-DD` → `data/features/macro/us_fiscal_inputs.json` (FRED + Treasury merged). **FRED ingestion:** `python -m src.macro.fred_fetch_us_fiscal_stress --asof YYYY-MM-DD` → snapshot + derived; cache `data/cache/fred/`. **Treasury:** `python -m src.macro.treasury_auctions_fetch` → `data/sources/macro/treasury_auctions_snapshot.json`.

---

*Document: full updated engine + repo for ChatGPT review. Cập nhật khi thay đổi engine/CLI/ThemePack hoặc cấu trúc repo.*
