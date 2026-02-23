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
