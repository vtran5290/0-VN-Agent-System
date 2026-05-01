# Repo maintenance — sanitize & compact

Dùng khi folder repo quá nặng (cache, export CSV, backtest outputs).

## Financial data: Parquet = cùng data, không mất

Financials **không bị xóa**. Đã chuyển từ CSV sang **Parquet** (cùng số dòng, cột, chỉ nén nhỏ hơn). Không cần tải lại.

- **Đọc trong Python** (giống CSV):
  ```python
  import pandas as pd
  q = pd.read_parquet("data/fireant_exports/financials/all_financial_data_quarterly_2016Q1_2025Q4.parquet")
  a = pd.read_parquet("data/fireant_exports/financials/all_financial_data_annual_2016_2025.parquet")
  ```
- **Xuất lại CSV** (mở bằng Excel): chạy `python scripts/export_fireant_financials_to_csv.py` → tạo file CSV trong `data/fireant_exports/financials/` (giữ nguyên Parquet).

## Lệnh nhanh

```bash
make sanitize
```

- Xóa toàn bộ `data/cache/fireant/` (cache FireAnt, có thể tải lại).
- Nếu có CSV financials trong `data/fireant_exports/financials/`, chuyển sang Parquet rồi xóa CSV (tiết kiệm ~50–70% dung lượng).

## Thủ công

1. **Xóa cache** (giải phóng ~1–2 GB nếu đã cache nhiều symbol):
   - `data/cache/fireant/*` — cache OHLCV/financials FireAnt.

2. **Compact financials** (đã có CSV export):
   ```bash
   python scripts/compact_fireant_financials_to_parquet.py
   ```
   - Đọc `summary.json` → convert 2 file CSV quarterly/annual sang `.parquet`, cập nhật `summary.json`, xóa CSV gốc.

3. **Không commit dữ liệu nặng** (đã cấu hình trong `.gitignore`):
   - `data/fireant_exports/`
   - `data/cache/`
   - `minervini_backtest/outputs/`
   - Một số file CSV log trong `pp_backtest/`, `artifacts/`.

## Regenerate sau khi sanitize

- **FireAnt cache**: tự tạo lại khi chạy intake / fetch (FireAnt client ghi lại cache).
- **FireAnt exports**: chạy `scripts/fetch_fireant_full_coverage.py` (ghi Parquet từ bản mới).
- **Backtest outputs**: chạy lại script backtest tương ứng.
