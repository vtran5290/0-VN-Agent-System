# Failure Modes & Deploy Candidate Selection

**Khung đầy đủ (core thesis, deploy gates, iterate, two-tier):** `docs/CORE_THESIS_AND_DEPLOY_FRAMEWORK.md`

## 1) Failure modes (đọc từ ledger để sửa đúng chỗ)

Với Minervini, 3 kiểu “chết” phổ biến:

| Failure mode | Triệu chứng | Hướng xử lý |
|--------------|-------------|-------------|
| **Too many small stop-outs** | loss_rate cao, payoff_ratio không đủ bù | Thử M7 (ATR stop); hoặc nới chase_cap; hoặc VDU strong hơn (setup vcp_strong). |
| **Few giant winners, còn lại flat** | top10_pct_pnl quá cao | Cần regime gate (M11) + walk-forward strict; kiểm tra survivorship / regime dependency. |
| **Winrate ok nhưng expectancy_r thấp** | avg win nhỏ do exit sớm / trailing chặt / min_hold kill | Chỉnh take_partial, trail_ma, time_stop; hoặc retest entry (M4) để nâng R-multiple. |

**Cách đọc nhanh:**

- Ledger: xem cột `exit_reason`, `hold_bars`, `ret`, `entry_px`, `stop_px`.
- Nếu phần lớn exit_reason = HARD_STOP và hold_bars ngắn → stop quá chặt hoặc entry extended (thử M7, M6).
- Nếu top 10 lệnh chiếm >55–60% PnL → profit concentration cao (regime / survivorship).
- Nếu win_rate ~50% nhưng expectancy_r < 0.1 → thắng nhỏ, thua đủ (exit / sizing).

---

## 2) Deploy Gates D1/D2/D3 (khóa deploy)

- **D1:** Walk-forward: 2023 val & 2024 holdout đều expectancy_r > 0.
- **D2:** Holdout top10_pct_pnl < 60%.
- **D3:** fee=30 + min_hold=3: PF ≥ 1.05 và expectancy_r ≥ 0.10.

Chạy: `walk_forward.py --realism --versions M3 M4` → `deploy_gates_check.py`. Nếu fail → không deploy, iterate.

---

## 3) Decision Matrix (không nhìn mỗi PF)

- Chạy: `python minervini_backtest/scripts/decision_matrix.py [--fetch]`
- Realism: **fee_bps 20 & 30**, **min_hold_bars = 3**.
- Metrics: expectancy_r, PF, MaxDD, trades/year, pct_hit_1r/2r, top10_pct_pnl.
- Rule-of-thumb:
  - expectancy_r > 0.10
  - PF > 1.10 @ fee=30 & min_hold=3
  - trades/year đủ (ví dụ ≥ 10)
  - top10_pct_pnl < 55–60%
- Nhóm: **Survivors** (đạt realism) | **Gross-only** (đẹp fee=0, chết realism) | **Noise**.

---

## 4) Deploy candidate selection (M4 vs M3)

- Chạy: `python minervini_backtest/scripts/deploy_candidate_selection.py [--matrix-csv path] [--fetch]`
- Logic:
  - Nếu **M4** pass realism (fee=30, min_hold=3) và tốt hơn hoặc ngang M3 → **M4 làm core** (retest giảm false breakout).
  - Nếu **M3** pass, M4 không → **M3 làm core**, M4 dùng như confirmation khi break-fail nhiều.
  - Nếu cả hai không pass → xem Gross-only / Noise; thử regime gate (M11), tune exit/sizing.

---

## 5) Gate attribution (waterfall)

- Chạy: `python minervini_backtest/scripts/gate_attribution.py --universe both [--fetch]`
- Hai universe: A (VN30/top liquidity), B (broad).
- Waterfall: G0 → G1 → … → G5 với **delta expectancy_r**, **delta PF**, **delta trades**.
- Ý nghĩa:
  - Delta lớn nhất ở **TT (G0)** → edge chủ yếu trend following, không hẳn VCP.
  - Delta lớn nhất ở **retest (G5)** → cấu trúc “break-fail” VN là vấn đề chính; retest là giải.
  - VDU/CS không giúp hoặc làm xấu → proxy VCP có thể mis-specified.

---

## 6) Versions M9–M11 (orthogonal)

| Version | Ý tưởng |
|--------|--------|
| **M9** | Pivot = high of tight range (15 bar), không dùng HH lookback dài. |
| **M10** | Gap filter: TR > 2.5×ATR thì chờ bar sau giữ trên pivot mới vào. |
| **M11** | Regime gate: VN30 vol_30 > vol_126 hoặc close > MA200. |

Nếu M3/M4 sống mà M1/M2 chết → có thể regime gate (M11) là missing piece.
