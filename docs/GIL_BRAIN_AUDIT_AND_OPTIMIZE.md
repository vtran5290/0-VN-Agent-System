# Gil Brain — Re-test kết quả Gil backtest + workflow optimize returns (trong guardrails)

Dùng **brain** (rule cards, EXPERIMENT_SPACE_GIL.yaml, BOOK_TEST_LADDER, IC Scorecard) để audit lại kết quả từ chat "Gil Mor backtest" và từ BOOK_TEST_LADDER; sau đó đề xuất workflow có thể **tối ưu returns** mà **không** vi phạm guardrails (no grid search, no invent rule, max 3/session, human hypothesis).

---

## 1. Re-test kết quả qua Brain (audit)

### Nguồn số liệu

- **BOOK_TEST_LADDER** (ablation 2023–2024): C1 m0/m1/m2, C2 m0/m1/m2; C2 m0 tốt nhất (PF 1.69, 638 trades) → **Case A** (alpha tự thân); C1 m2 204 trades PF 1.65.
- **Chat session này (validation + final):** C1 m2 val 204 / 1.65; C2 m2 val 323 / 1.59; C1 final 54 / 3.53; C2 final 191 / 3.75; C2 final Top 5 = 26.14%.

### Đọc qua IC Scorecard (brain)

| Kiểm tra | Kết quả |
|----------|---------|
| **Gate 1** (PF) | C1/C2 final đều > 1.05 ✅ |
| **Gate 2** (trades) | C2 final 191 ≥ 40 ✅; C1 final 54 ≥ 40 ✅ nhưng… |
| **Gate 3** (Top 5 < 60%) | C2 final 26.14% ✅ |
| **Gate 4** (stability) | C2 final: trades 323→191 (−41%) ✅; C1 final: 204→54 (−73%) ❌ |

**Kết luận audit:** C2 (Weekly 3WT, m2) **pass** đủ 4 gate. C1 final **fail Gate 4** (trades sụt >50%) → không dùng C1 làm backbone deploy; có thể conditional hoặc theo dõi thêm.

### So với ablation trong BOOK_TEST_LADDER

- Ablation nói **C2 m0** tốt hơn C2 m2 (1.69 vs 1.59, nhiều trades hơn) → **Case A: deploy m0**.
- Trong session này ta chạy **C2 m2** final (book-faithful), **chưa** chạy **C2 m0** final.
- **Gap:** Để “optimize” đúng với insight từ ladder: cần **C2 m0 final** (no market filter) và so sánh C2 m0 final vs C2 m2 final (returns + tail + trades). Nếu C2 m0 final vẫn pass Gate 1–4 và PF/return tốt hơn → deploy C2 m0 thay vì C2 m2.

---

## 2. Workflow có thể optimize returns (trong guardrails)

Các cách dưới đây **không** thêm combo mới ngoài YAML, **không** grid search, **không** invent rule; hypothesis vẫn do bạn quyết định, Cursor chỉ encode/chạy.

### A. Chạy C2 m0 final và so với C2 m2 (1 run)

- **Lý do:** Ablation đã chỉ ra C2 m0 tốt nhất (alpha tự thân). Final chưa chạy cho m0.
- **Hành động:** Chạy **1 lần** final cho **C2 m0** (Weekly 3WT, no market filter). So với C2 m2 final (PF 3.75, 191 trades, Top 5 26.14%).
- **Nếu C2 m0 final** PF ≥ 1.05, trades ≥ 40, Top 5 < 60%, stability OK → có thể **deploy C2 m0** thay vì m2 để tăng returns (ít filter hơn, nhiều trades hơn trong validation).
- **Lệnh:** `python -m pp_backtest.run_weekly --watchlist config/watchlist_80.txt --entry-3wt --no-entry-weekly-pp --market-mode 0 --start 2025-01-01 --end 2026-02-21`
- **Đã chạy (2026-02-22):** Raw: trades=322, PF=2.8931, tail5=-8.61%, max_drawdown=-97.48%, avg_ret=4.70%, win_rate=40.68%. Portfolio_sim K=5: MDD=-11.49%, total return=12.88%, CAGR=12.62%, 78 trades (sau K limit), exposure 71.3%. So với C2 m2 final (PF 3.75, 191 trades): m0 nhiều trades hơn, PF thấp hơn; portfolio layer giảm MDD mạnh (raw −97% → K=5 −11.5%).

### B. Position sizing (K=5, equal weight)

- **Đã có:** `pp_backtest/portfolio_sim.py` (ledger → portfolio MDD, return, CAGR với K=5).
- **Tác dụng:** Giảm MDD (từ ~−70% full capital xuống ~−18% như đã đo với C2 m0 val); **returns** có thể giảm chút nhưng **risk-adjusted** tốt hơn, dễ deploy thực tế.
- **Workflow:** Sau mỗi lần chạy final, chạy `python -m pp_backtest.portfolio_sim pp_backtest/pp_weekly_ledger.csv` và ghi nhận MDD/return/CAGR → đây là “optimize” theo nghĩa risk-adjusted, không phải chỉnh rule.

### C. Conditional policy (regime)

- **Brain cho phép:** “Nếu regime X → setup A; regime Y → không trade” (không phải 1 combo universal).
- **Áp dụng:** Nếu sau này có data breadth/regime: chỉ bật C2 (hoặc C2 m2) khi **market breadth > ngưỡng** hoặc **regime = expansion**; khi distribution nặng thì giảm size hoặc không vào mới. Đây là layer **trên** backtest, không đổi rule trong YAML.
- **Cursor:** Có thể encode policy dạng “if regime_state == X then allow C2” trong decision layer; **không** tự invent ngưỡng — bạn đặt hypothesis (vd. “chỉ trade khi breadth > 40%”), Cursor implement.

### D. Block D (pattern filters) trên C2 — tối đa 1–2 run

- **Trong YAML:** pattern_filters_allowed: right_side, avoid_extended; max depth = 2 (entry + 1 filter).
- **Workflow:** Chọn **1** filter (vd. avoid_extended), chạy **1** run validation: C2 + avoid_extended, so với C2 baseline. Nếu PF tăng **và** trades không sụt quá **và** tail không xấu hơn → giữ filter; nếu không thì bỏ. **Không** test cả right_side lẫn avoid_extended cùng lúc trong một run (tránh combo sâu).
- **Lệnh (ví dụ):** Cần flag `--avoid-extended` trong run_weekly nếu đã có; nếu chưa thì chỉ thêm khi bạn approve (human_approval_required).

### E. C3 (Weekly PP + 3WT) — 1 run nếu muốn đa dạng entry

- **Trong YAML:** entries_allowed có weekly_pp_3wt (C3).
- **Ý nghĩa:** Entry = PP **hoặc** 3WT; có thể tăng số trades so với chỉ 3WT. Chạy **1** lần validation C3 (m2 hoặc m0), so với C2. Nếu C3 pass Gate 1–2 và ổn Gate 3–4 → thêm option deploy; không thì giữ C2.
- **Lệnh:** `python -m pp_backtest.run_weekly --watchlist config/watchlist_80.txt --start 2023-01-01 --end 2024-12-31` (mặc định đã là PP+3WT nếu không --entry-3wt --no-entry-weekly-pp; cần kiểm tra run_weekly có hỗ trợ C3).

---

## 3. Tóm tắt: workflow optimize returns (theo thứ tự ưu tiên)

| # | Workflow | Mục đích | Guardrails |
|---|----------|----------|------------|
| 1 | **C2 m0 final** (1 run) + so với C2 m2 final | Align với ablation (Case A); có thể tăng returns bằng cách deploy m0 thay m2 | 1 experiment; không invent rule |
| 2 | **Position sizing** (portfolio_sim) trên ledger đã có | Giảm MDD, cải thiện risk-adjusted return | Không đổi rule backtest |
| 3 | **Conditional policy** (regime/breadth) | Chỉ trade khi market phù hợp → giảm drawdown thực tế | Hypothesis do bạn; Cursor encode |
| 4 | **D-block** (1 filter trên C2) | Xem filter có cải thiện PF/tail không | 1 run, max depth 2 |
| 5 | **C3** (PP+3WT) validation | Thêm option entry nếu C3 tốt | 1 run trong entries_allowed |

---

## 4. Không làm (theo brain)

- **Không** grid search (vol_mult, stop_pct, N bars…).
- **Không** thêm entry/mode/exit mới ngoài EXPERIMENT_SPACE_GIL.yaml.
- **Không** chỉnh threshold sau khi thấy số (vd. đổi 3% tight 3WT thành 2.5% để PF đẹp).
- **Không** chạy final nhiều lần cho cùng một model (one-shot only).
- **Không** để Cursor tự generate hypothesis mới; Cursor chỉ encode hypothesis bạn chọn.

---

**Ref:** `docs/BOOK_TEST_LADDER.md`, `docs/EXPERIMENT_SPACE_GIL.yaml`, `docs/GIL_BRAIN_WORKFLOW.md`, `prompts/research_auditor.md`.
