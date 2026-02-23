# Future Phases (out of MVP)

Các tính năng chủ đích đưa ra khỏi MVP để engineer không bị distracted.

## Semi-auto execution

- **Scheduled backtest:** Tự chạy backtest theo lịch (cron / Task Scheduler) — không nằm trong MVP. Hiện tại: manual run `python -m pp_backtest.run` khi cần.
- **Auto-publish knowledge:** Sau backtest tự gọi `publish_knowledge` — không nằm trong MVP. Hiện tại: manual run sau khi backtest xong.
- **Auto weekly report:** Tự generate weekly report theo ngày — không nằm trong MVP. Hiện tại: manual `python -m src.report.weekly`.

Khi triển khai phase này: cấu hình lịch rõ ràng, log output, và vẫn cho phép manual override.

## Phase 2 (đã nêu ở spec knowledge)

- **analyze_trades.py** → `knowledge/personal_improvement/profile.json` (leaks + strengths).
- **get_personal_reminders()** inject vào Decision & Swing Engine.
- Inject resolver vào **swing_engine** (tickers_with_entry_signal) và **hold_review** (tickers_held_or_exit_pressure).

## Khác (sau này)

- Setup quality config hóa (weights từ file thay vì hard-code).
- Regime snapshots JSON theo ngày (nếu cần query lịch sử regime).
- Probability / setup quality tích hợp vào watchlist scoring.
