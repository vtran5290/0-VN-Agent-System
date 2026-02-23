# QA + Research Plan — Minervini Backtest

Mục tiêu: **chạy được → tin được → deploy được**. Tránh self-deception qua (1) correctness, (2) data integrity, (3) test protocol, (4) attribution, (5) VN constraints.

---

## 1) QA bắt buộc trước khi tin PF

### A. Data sanity (FireAnt → CSV → parquet)

- **Adjusted vs unadjusted:** Chốt 1 chế độ. Dùng adjusted O/H/L/C khi có corporate actions; volume raw OK. Cần biết FireAnt trả về gì.
- **Split/dividend:** Kiểm tra 5 mã có corporate actions (MWG, FPT, VNM…) xem series có “gap giả”.
- **Missing days:** Thiếu phiên → Highest(High, lookback) và ATR méo.
- **Date:** Trading date VN, không lệch 1 ngày.

**Quick check:**

```bash
python minervini_backtest/scripts/data_sanity.py
# hoặc
python minervini_backtest/scripts/data_sanity.py minervini_backtest/data/curated/*.parquet
```

- Assert: dates tăng, unique; volume ≥ 0; Low ≤ min(O,C) ≤ max(O,C) ≤ High.

### B. Engine correctness (no look-ahead)

- **Highest(High, lookback):** Chỉ dùng các bar **trước** bar hiện tại (đã sửa: `rolling(lookback).max().shift(1)`).
- **ATR/Vol20:** EOD system — bar hiện tại đã đóng, dùng rolling chuẩn là chấp nhận được.
- **Fill:** Entry tại **next open** (realism); exit tại next open.
- **Retest (M4):** Pivot “frozen” lúc breakout; retest chỉ dùng dữ liệu sau đó.

**Unit tests:**

```bash
cd "0. VN Agent System"
PYTHONPATH=minervini_backtest/src python -m pytest minervini_backtest/tests/test_engine_correctness.py -v
# hoặc
cd minervini_backtest && PYTHONPATH=src python -m pytest tests/test_engine_correctness.py -v
```

---

## 2) Min_hold & T+2.5 (VN realism)

- **min_hold_bars = 3** (hoặc 2) phản ánh settlement / thực thi; test **min_hold=0** để đo gross edge.
- Bảng tối thiểu mỗi version: **PF × fee_bps (0/10/20/30/50) × min_hold (0/3)**.

**Chạy sensitivity:**

```bash
python minervini_backtest/scripts/sensitivity_fee_minhold.py --config M1 [--fetch] [--out sensitivity.csv]
```

---

## 3) Phiên bản thêm (M6, M7, M8)

| Version | Mô tả |
|--------|--------|
| **M6** | No-Chase: entry chỉ khi Close ≤ pivot×(1+1.5%). |
| **M7** | Stop = entry - 2×ATR(14) only (bỏ stop_pct). |
| **M8** | Partial at +1.5R + trail MA20. |

Configs: `configs/M6.yaml`, `M7.yaml`, `M8.yaml`. Run: `python minervini_backtest/run.py` (đã gồm M6–M8).

---

## 4) Research protocol (tránh sample luck)

### A. Walk-forward

- **Train:** 2020–2022  
- **Validate:** 2023  
- **Hold-out:** 2024 (hoặc 2025 nếu có data)  
- Không tối ưu trên toàn 2020–2024 rồi báo PF.

```bash
python minervini_backtest/scripts/walk_forward.py --config M1 [--fetch] [--out walk_forward_results.csv]
```

### B. Universe

- Test 2 tập: “liquid leaders” (VN30 + top value traded) vs “broad universe” (80–200 mã).  
- PF chỉ sống ở tập 1 → có thể edge là liquidity premium.

### C. Robustness (perturbation)

- Thử: vol_mult ±0.2, lookback ±10, stop_pct ±1%.  
- Edge biến mất nhanh → strategy mong manh (chỉnh trong config rồi chạy lại).

---

## 5) Metrics bổ sung (R-multiple game)

- **Expectancy in R:** avg(R) per trade  
- **% trades hit +1R / +2R**  
- **Payoff ratio & loss rate**  
- **Profit concentration:** top 10 trades đóng góp bao nhiêu % PnL  

Đã thêm trong `metrics.minervini_r_metrics()` và xuất trong `run.py` (expectancy_r, pct_hit_1r, pct_hit_2r, payoff_ratio, loss_rate, top10_pct_pnl).

---

## 6) Gate attribution (edge từ gate nào)

Chạy từng lớp: TT+breakout → +VDU → +CS → +VCP → +close strength → +retest. Output **delta expectancy** từng gate.

```bash
python minervini_backtest/scripts/gate_attribution.py [--fetch] [--out gate_attribution.csv]
```

---

## 7) Chỗ dễ “leak” trong spec

- **Close strength (top 75% range):** Dùng High–Low của **bar hiện tại**; trigger breakout cũng trên bar đó → OK. Không cho phép “intraday breakout” fill at close khi chưa có tick-level.
- **52w high/low (252 bars):** Data phải đủ dài. Engine dùng **warmup_bars = 252 + lookback_base** (mặc định); nếu ít hơn thì bỏ qua đầu series.
- **Climax proxy:** Dễ overfit; dùng như **optional diagnostic** trước.

---

## 8) Golden test (spot-check ledger)

Chọn 2–3 mã leader (MBB, FPT, MWG hoặc SSI), in ledger đầy đủ 1 năm, **manual spot-check 5 trades:** pivot đúng không, volume condition, stop, exit logic.

```bash
python minervini_backtest/run.py --golden MBB 2021
# Hoặc với data từ FireAnt:
python minervini_backtest/run.py --fetch --golden MBB 2021
```

Output: `minervini_backtest/golden_ledger_MBB_2021.csv`. Kiểm tra pivot, volume, stop, exit_reason.

---

## Decision Matrix & Deploy (facts-first, cost-first)

- Chạy **decision_matrix.py** với realism (fee 20/30, min_hold=3); xem nhóm Survivors / Gross-only / Noise.
- Rule-of-thumb: expectancy_r > 0.10, PF > 1.10 @ fee=30 & min_hold=3, trades/year đủ, top10_pct_pnl < 55–60%.
- **deploy_candidate_selection.py**: nếu M4 tốt hơn M3 @ realism → M4 core; không thì M3 core, M4 confirmation.
- Chi tiết failure modes và logic chọn: `docs/FAILURE_MODES_AND_DEPLOY.md`.

## Checklist trước khi deploy

- [ ] `data_sanity.py` pass  
- [ ] `test_engine_correctness.py` pass  
- [ ] Sensitivity (fee × min_hold) đã chạy; PF @ min_hold=3 vẫn chấp nhận được  
- [ ] **Decision Matrix** đã chạy; ít nhất 1 version ở nhóm Survivors  
- [ ] Walk-forward: val/holdout không sụt thô bạo so với train  
- [ ] Gate attribution (waterfall 2 universe): biết gate nào tạo alpha  
- [ ] Golden ledger: spot-check 5 trades đúng logic  
- [ ] Đã chốt adjusted vs unadjusted và nguồn data (FireAnt)  
