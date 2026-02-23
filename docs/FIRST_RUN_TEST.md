# First Real Run Test (Backtest → Publish → Inject)

Chạy lần đầu để verify determinism, auditability, reset mechanism, self-consistency.

## Test 1 — Backtest → Publish → Inject

### Bước A

```powershell
python -m pp_backtest.run
.\.venv\Scripts\python.exe -m pp_backtest.publish_knowledge --strategy PP_GIL_V4 --start 2018-01-01 --end 2026-02-21
```

**Verify:**

- [ ] `knowledge/backtests/MBB/PP_GIL_V4.json` tồn tại (hoặc symbol khác trong watchlist)
- [ ] `knowledge/backtests/index.json` đã update
- [ ] Trong record JSON: `params_hash` tồn tại
- [ ] Trong record JSON: `inputs.results_csv_mtime`, `inputs.ledger_csv_mtime` tồn tại

### Bước B

```powershell
python -m src.report.weekly
```

Mở `data/decision/weekly_report.md`. **Verify:**

- [ ] Block "Backtest edge (knowledge)" xuất hiện cho MBB (hoặc ticker có trong watchlist + index)
- [ ] Relevance hiển thị đúng (Unknown nếu thiếu context)
- [ ] **Knowledge used: Yes**
- [ ] **Records queried: N** (N > 0)
- [ ] **Stale warnings: 0** (sau lần publish vừa chạy)

### Bước C — Fake stale test

1. Sửa/touch file ledger (ví dụ mở `pp_backtest/pp_trade_ledger.csv` và save, hoặc append 1 dòng rồi xóa).
2. **Không** chạy publish lại.
3. Chạy: `python -m src.report.weekly`

**Verify:**

- [ ] Trong report xuất hiện: **"Backtest data newer than knowledge record — re-publish recommended."**
- **Lưu ý:** Mặc định `staleness.grace_period_hours: 24` trong `knowledge/resolver_rules.yml` — cảnh báo chỉ hiện khi data đã "mới hơn" record **quá 24h**. Để thấy warning ngay khi test: tạm đặt `grace_period_hours: 0`, chạy weekly lại; sau khi pass test có thể đặt lại 24.
- Nếu không thấy (và đã set 0) → mtime logic chưa hook đúng.

### Bước D — Fake regime break test

1. Sửa `knowledge/regime_break.json`: `"active": true`, `"expires_at": "YYYY-MM-DD"` (chọn ngày **hôm qua**).
2. Chạy: `python -m src.report.weekly`

**Verify:**

- [ ] Xuất hiện: **"Regime break expired — manual review recommended."**
- [ ] Relevance **không** bị downgrade (vì expired → treat as inactive).

---

Nếu 4 bước pass → hệ thống có: determinism, auditability, reset mechanism, self-consistency.

---

## Sau khi FIRST_RUN_TEST pass — Test behavioral (1 case thực tế)

Chạy một case thực tế: backtest MBB 2018–2026 → publish knowledge → chạy weekly decision. Tự trả lời 3 câu:

1. Phần **"Backtest edge"** có giúp mình ra quyết định không, hay chỉ là thông tin thêm?
2. **Relevance score** có hợp lý khi market risk-off?
3. Mình có xu hướng **override system** khi thấy số liệu không?

Đây là test behavioral, không phải technical.
