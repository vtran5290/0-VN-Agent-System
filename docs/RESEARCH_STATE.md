# Research State (Anchor)

**Cập nhật sau mỗi decision lớn. Paste file này (hoặc nội dung dưới) vào đầu mỗi conversation mới để AI thấy full map.**

→ Nhắc mỗi session: xem **`docs/SESSION_START_NOTE.md`** (paste RESEARCH_STATE vào đầu chat mới).

---

## 1. Open questions (chưa có answer)

- **Persistence metric:** Chưa implement. Hướng duy nhất đáng quay lại Minervini mechanical — e.g. % breakouts still above entry after 10 bars; avg forward 10-day return of NH20 stocks. Chỉ làm sau khi có live data từ pilot (optional).
- **FA Cohort Study (Phase 2):** ĐANG CHẠY (active research). Mục tiêu: build FA filter (earnings/sales/margins/ROE/debt, leadership) theo quý, tạo cohort “high growth” và test xem cohort này có outperform ổn định qua splits hay không. Pass = cohort outperform rõ ràng vs index trong nhiều giai đoạn; Fail = không outperform → đóng luôn hướng “full Mark (SEPA + VCP)” để khỏi quay lại. Hiện tại thiếu chuỗi shares/EPS theo quý nên Phase 2 đang dùng **earnings_yoy / earnings_qoq_accel_flag (từ net_profit)** như proxy cho EPS accel; khi có endpoint shares/EPS-by-quarter thì nâng cấp lại filter sang EPS thật.

---

## 2. Decisions made (đã đóng, không reopen)

- **Minervini mechanical:** CLOSED. Structural persistence mismatch (VN 2023–2024). Không phải thiếu macro/breadth/data. Reopen chỉ khi có persistence metric chứng minh môi trường đã đổi (xem POSTMORTEM).
- **MHC composite gate:** Không build. Breadth không tách rõ 2023; nh20_pct gap nhỏ. Build gate = overfit / illusion control.
- **Liquidity gate + MH overlay v1:** Đã test trên 2012–2026 (fee=30, min_hold=3). Liquidity gate không thay đổi verdict; MH overlay NH-heavy v1 không cứu được 2023 và làm mòn edge 2024. Overlay thesis CLOSED, không optimise threshold.
- **PP C2 m0:** Pilot approved. Deploy under kill-switch và review rules (docs/PILOT_C2_M0_APPROVED.md).

---

## 3. Priorities

- **Ưu tiên 1 — Bắt đầu pilot PP C2 m0.** Đây là việc quan trọng nhất; mọi research khác phụ thuộc vào live data này.
- **Ưu tiên 2 — FA Cohort Study (Phase 2)**: chạy khi có thời gian, theo pipeline:
  1) `minervini_backtest/scripts/fetch_fundamentals_raw.py` → build `data/fundamentals_raw.csv` từ FireAnt  
  2) `minervini_backtest/scripts/build_fa_minervini_csv.py` → build `data/fa_minervini.csv`  
  3) `minervini_backtest/scripts/run_fa_cohort.py` **hoặc** end-to-end runner `minervini_backtest/scripts/run_fa_cohort_end_to_end.py`. Không đụng pilot.

## 4. Current focus

- **Deploy:** PP C2 m0 pilot (4 tuần, K=5, 20%/slot). Track PF_live, exposure_tw, execution slippage, Top5%.
- **Research:** Không reopen Minervini mechanical; không build MHC composite; MH overlay v1 đã đóng. FA Cohort Study = active Phase 2 (không ảnh hưởng pilot). Step 1: fetch `fundamentals_raw.csv` via `fetch_fundamentals_raw.py`; Step 2: build `fa_minervini.csv` via `build_fa_minervini_csv.py`; Step 3: chạy `run_fa_cohort.py` **hoặc** `run_fa_cohort_end_to_end.py`. Persistence study chỉ optional, sau pilot.
- **FA Cohort caveat (Phase 2):** Current PASS result for Mark-tight FA growth + earnings accel (2015–2024, vs VNINDEX) is based on `watchlist_80` universe as of 2024. Survivorship bias is likely present; results should be treated as an **upper bound** on true deployable edge until a historical (pre‑2017) universe with delisted names is wired in.
- **Lab status:** Minervini = Closed (mechanical); Liquidity/MH overlay = Closed; FA Cohort = Active research; PP C2 m0 = Pilot live; Operating Manual = Frozen.

---

*Cập nhật lần cuối: ưu tiên 1 = pilot PP C2 m0, ưu tiên 2 = 2012 extension (not urgent).*
