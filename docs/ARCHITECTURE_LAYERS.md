# Kiến trúc theo layer — VN Agent System

**Nguyên tắc:** Tách **layer tư duy**, không tách repo. Mỗi layer có vai trò rõ, tránh agent “overfit theo CSV” hay backtest lẫn với quyết định real-time.

## Sơ đồ layer

```
VN Agent System (1 repo)
│
├── 00_Regime_Dashboard   — Macro + regime + data confidence (weekly/daily)
├── 01_Swing_Engine       — Entry/exit rules, allocation, watchlist
├── 02_Position_Engine   — Size, risk, execution (sell/trim)
├── 03_Backtest_Lab       — Research only (PP, sell v4, DD modes, pivot)
└── 04_Knowledge_Base    — Curated insights (KNOWLEDGE.md, memo)
```

## 03_Backtest_Lab

- **Vị trí trong repo:** `pp_backtest/` (+ script pivot, ledger).
- **Chỉ làm research:** chạy backtest, so mode, so tham số, xuất CSV + pivot.
- **Không** ra quyết định real-time, **không** lẫn với weekly macro.
- **Output:** `pp_sell_backtest_results.csv`, `pp_trade_ledger.csv`, pivot theo exit_reason. Có thể thêm file tóm tắt (ví dụ `pp_backtest/KNOWLEDGE.md`) ghi 5–10 dòng learning mỗi lần chạy.

## VN Agent (Regime + Swing + Position)

- **Đọc kết quả đã curate:** ví dụ KNOWLEDGE.md, hoặc 1–2 câu “backtest gần đây cho thấy …” đã được người viết/chọn.
- **Ra stance:** allocation, no_new_buys, block entries khi market DD cao, v.v. dựa trên regime + rules đã định, **không** đọc trực tiếp raw CSV để “học” lung tung.
- **Luồng:** Backtest results → curated insights (con người hoặc script tóm tắt) → agent memory / context → quyết định.

## Tách thread (chat/agent)

- **Backtest Lab** nên chạy trong **thread/agent riêng** (ví dụ “03_Backtest_Lab”) khi:
  - Chạy nhiều mode (1/2/3/4), nhiều tham số, grid test → log dài, dễ ngập decision chat.
  - Muốn chuẩn: mỗi tuần engine auto-run, agent chỉ đọc summary.
- **Agent chính** (weekly report, regime, allocation): giữ 1 thread; đọc curated output của Backtest Lab khi cần.

## Tóm tắt

| | Backtest Lab | VN Agent |
|---|--------------|----------|
| **Làm gì** | Research, so sánh mode/param, pivot | Stance, allocation, weekly report |
| **Đọc** | Raw data, FireAnt, vnstock | Curated insights, config, manual_inputs |
| **Ghi** | CSV, ledger, (option) KNOWLEDGE.md | Report, state, allocation, alerts |
| **Tách thread?** | Nên khi batch/grid nhiều | 1 thread chính |

👉 **Có nên tách backtest thành agent riêng?** — Có, theo nghĩa **tách layer + (khi cần) tách thread**; **không** tách repo. Backtest Lab = research; Agent = đọc curated, ra quyết định.

---

## E&MA Research Module (formalised 2026-06-09)

**Scope:** Per-symbol MA reaction research for book positions + liquid IA-favourite watchlist.
Not a reporting dashboard — a signal feed that informs entry discipline and exit rules.

### Deliverables

| Component | File | Update |
|---|---|---|
| Per-symbol best-MA study (2y) | `data/research/ma_reaction_stocks.json` | On-demand research run |
| VNINDEX MA reaction study | `data/research/ma_reaction_study.json` | On-demand research run |
| Daily MA levels + breach flags | `data/state/ma_levels_daily.json` | Post-market close (same as sell_signals) |
| Breach alerts feed | `data/alerts/market_flags.json` → `ma_breach_alerts` | Post-market close |
| MA200 breadth snapshot | `data/state/ma200_snapshot.json` | Weekly or on-demand |
| DNA profile extension | `data/research/stock_dna/stock_dna_symbol_profiles.json` | On DNA rebuild |

### Scripts

| Script | Purpose |
|---|---|
| `scripts/run_ma_reaction_study.py` | VNINDEX MA reaction across 14 MAs × 6 windows |
| `scripts/run_ma_reaction_stocks.py` | Per-symbol MA reaction for 19 liquid+IA-fav stocks |
| `scripts/run_ma200_snapshot.py` | MA200 breadth snapshot (liquid+IA-fav universe) |
| `scripts/run_ma_levels_daily.py` | Daily MA levels SSOT + breach alerts (P0 — run post-close) |

### Priority chain (per symbol)
1. DNA `primary_support_line` (confidence HIGH or MEDIUM)
2. E&MA Research `best_ma_2y` (from `ma_reaction_stocks.json`)
3. Fallback: EMA10

### Integration points
- **sell_rules.py**: reads `ma_levels_daily.json`, surfaces `primary_ma_breach` → TRIM/TIGHTEN STOP action
- **cloud_daily_report.py**: shows `dist_primary_ma` column in holdings table + `% above SMA200` breadth stat in Section G
- **DNA profiles**: `best_ma_2y`, `best_ma_score_2y`, `best_ma_sr_10d` joined at write time in `reporting.py`
