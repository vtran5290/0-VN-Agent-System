# Nguồn dữ liệu SBV cho Vietnam liquidity (OMO, interbank, credit, FX)

Tài liệu tham chiếu để implement fetcher tự động. Tất cả từ SBV — không có API JSON; dùng **requests + BeautifulSoup**, header User-Agent giả trình duyệt, xử lý timeout/lỗi.

---

## 1. OMO Net (Nghiệp vụ thị trường mở ròng)

| | |
|---|---|
| **URL** | https://www.sbv.gov.vn/vi/web/sbv_portal/nghi%E1%BB%87p-v%E1%BB%A5-th%E1%BB%8B-tr%C6%B0%E1%BB%9Dng-m%E1%BB%9F |
| **Format** | HTML table: Loại hình giao dịch \| Số thành viên \| Khối lượng trúng thầu (Tỷ đồng) \| Lãi suất trúng thầu (%/năm) |
| **Tần suất** | Hàng ngày (chỉ phiên mới nhất) |
| **Lưu ý** | Trang chỉ hiển thị phiên mới nhất, không có lịch sử. OMO net = Σ(Mua kỳ hạn) − Σ(Bán/đáo hạn). Để có net cả tuần cần cộng dồn từng ngày hoặc dùng PDF Thông cáo báo chí tuần (thứ Ba–Tư). |

**Quan trọng:** Bảng kết quả đấu thầu OMO trên SBV **có thể được load bằng JavaScript**. Khi fetch bằng `requests` + BeautifulSoup, HTML trả về thường **không chứa bảng** → `omo_net` hay trả về null. Cách xử lý: (1) Điền tay vào `manual_inputs.json` → `vietnam.omo_net` (tỷ đồng), hoặc (2) Dùng trình duyệt headless (Selenium/Playwright) để lấy HTML đã render, hoặc (3) Parse từ PDF "Thông tin về hoạt động ngân hàng trong tuần" (link trong trang Thông cáo báo chí).

**Parse (khi có bảng):** Section "Mua kỳ hạn" → dòng "Tổng cộng" = bơm (tỷ đồng); section Bán/Tín phiếu → Tổng cộng = hút. Số VN: 3.000,00 = 3000 (dấu chấm nghìn, phẩy thập phân).

**Fallback:** Thông cáo báo chí tuần https://www.sbv.gov.vn/thong-cao-bao-chi — PDF "Diễn biến thị trường ngoại tệ và thị trường liên ngân hàng tuần từ DD–DD.MM.YYYY" (parse bằng pdfplumber).

---

## 2. Lãi suất liên ngân hàng qua đêm (interbank_on)

| | |
|---|---|
| **URL** | https://www.sbv.gov.vn/vi/l%C3%A3i-su%E1%BA%A5t1 (hoặc https://www.sbv.gov.vn/lãi-suất1) |
| **Format** | HTML table 2 cột: Thời hạn \| Lãi suất BQ liên Ngân hàng (%/năm) \| Doanh số (Tỷ đồng). **Dòng đầu = "Qua đêm"** = overnight. |
| **Tần suất** | Hàng ngày; cập nhật T+1. Có "Ngày áp dụng". |

**Parse:** Tables[1] (hoặc bảng chứa "Qua đêm"); hàng "Qua đêm" → cột lãi suất (%); lấy thêm "Ngày áp dụng" để kiểm tra freshness.

**Output:** Số thập phân (ví dụ 4.24).

---

## 3. Tăng trưởng tín dụng (credit_growth)

| | |
|---|---|
| **URL** | https://www.sbv.gov.vn/vi/du-no-tin-dung-doi-voi-nen-kt-dttktt |
| **Format** | HTML table: STT \| Chỉ tiêu \| Số dư (Tỷ đồng) \| Tốc độ tăng (Giảm) so với cuối năm trước (%) |
| **Tần suất** | Hàng tháng (lag 1–2 tháng). |

**Quan trọng:** SBV công bố **YTD** (so với cuối năm trước), **không phải YoY** (so với cùng kỳ năm ngoái). Trong pipeline vẫn dùng key `credit_growth_yoy`; giá trị lấy từ SBV thực tế là YTD — ghi chú trong code và doc. YoY thật cần số dư tháng tương ứng năm trước (cache hoặc nguồn khác).

**Parse:** Hàng "TỔNG CỘNG" → cột "Tốc độ tăng" (%).

---

## 4. Tỷ giá USD/VND (fx_usd_vnd)

| | |
|---|---|
| **URL** | https://www.sbv.gov.vn/vi/t%E1%BB%B7-gi%C3%A1 |
| **Format** | HTML table; dòng "1 Đô la Mỹ =" → cột tỷ giá (số, ví dụ 25065). Ngày ban hành ghi rõ. Cập nhật hàng ngày buổi sáng. |

**Parse:** Bảng đầu; hàng "1 Đô la Mỹ" (hoặc tương đương) → cột tỷ giá. Loại bỏ dấu chấm/phẩy nếu có.

**Alternate:** Vietcombank XML/JSON (tỷ giá thực tế): `https://portal.vietcombank.com.vn/Usercontrols/TVPortal.TyGia/pXml.aspx?b=68` — dùng SBV cho nhất quán báo cáo chính thức.

---

## Bảng tóm tắt implement

| Chỉ số | URL (SBV) | Format | Tần suất | Độ khó |
|--------|-----------|--------|----------|--------|
| omo_net | .../nghiep-vu-thi-truong-mo | HTML table | Hàng ngày | Trung bình (net = Mua − Bán) |
| interbank_on | .../lãi-suất1 | HTML table | Hàng ngày | Dễ |
| credit_growth_yoy | .../du-no-tin-dung-doi-voi-nen-kt-dttktt | HTML table | Hàng tháng | Dễ (giá trị là YTD) |
| fx_usd_vnd | .../tỷ-giá | HTML table | Hàng ngày | Rất dễ |

---

## Code contract

Fetcher trả về dict merge được vào `manual_inputs.json` → `vietnam`:

```python
{"vietnam": {"omo_net": int|None, "interbank_on": float|None, "credit_growth_yoy": float|None, "fx_usd_vnd": int|None}}
```

- `omo_net`: tỷ đồng (số nguyên) hoặc None nếu không parse được.
- `interbank_on`: % (số thập phân).
- `credit_growth_yoy`: % (SBV thực tế là YTD).
- `fx_usd_vnd`: số nguyên (ví dụ 25065).

Script: `scripts/fetch_vietnam_liquidity.py`. Gọi từ `scripts/update_manual_inputs.py` khi merge; dùng `--force-vn-liquidity` để ghi đè từ SBV.
