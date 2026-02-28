# Tóm tắt Backtest “kiểu Minervini” — dễ hiểu

## Chúng ta đã làm gì?

Thử **một cách mua cổ phiếu tự động** theo ý tưởng của Mark Minervini (Mỹ): **Mua khi giá “phá vỡ” vùng tích lũy** (breakout), với vài bộ lọc (xu hướng, volume, v.v.). Mục tiêu: tìm xem **cách đó có “ăn” ổn định trên thị trường VN không**, nếu có thì mới nghĩ deploy (chạy thật tiền).

---

## Một số từ chuyên môn → nghĩa bình thường

| Jargon | Nghĩa đơn giản |
|--------|-----------------|
| **Breakout** | Giá vượt lên trên mức cao gần đây (tín hiệu “mua”). |
| **TT (Trend Template)** | Bộ lọc “chỉ mua khi cổ phiếu đang trong uptrend” (ví dụ giá > đường trung bình 50/200 ngày). |
| **VCP** | Giai đoạn giá co lại, volume giảm (coi như “tích lũy” trước khi breakout). |
| **Pullback** | Giá tăng rồi hồi một chút, rồi lại tăng — mua ở lần “hồi” đó. |
| **U&R (Undercut & Rally)** | Giá đâm xuống dưới đáy gần đây rồi đóng cửa lại trên đáy (kiểu “rửa” rồi bật). |
| **Walk-forward / split** | Chia thời gian: dùng 2020–2022 để “học”, 2023 để “kiểm tra”, 2024 để “giữ lại” — không nhìn tương lai khi thiết kế. |
| **Split stability** | Cách làm có lãi **cả** ở giai đoạn “học” **và** “kiểm tra” **và** “giữ” — không chỉ ăn một đoạn rồi sau đó lỗ. |
| **Expectancy_r** | Trung bình mỗi trade lãi/ lỗ bao nhiêu (đã chuẩn hóa theo rủi ro). Dương = có edge. |
| **PF (Profit Factor)** | Tổng lãi / tổng lỗ. > 1 = lãi nhiều hơn lỗ. |
| **Fee 30 bps / min_hold 3** | Giả định phí giao dịch 0,3% mỗi vòng (mua+bán) và tối thiểu giữ 3 phiên — gần với thực tế VN. |
| **Breadth** | “Rộng” thị trường: bao nhiêu % mã đang trên đường trung bình (MA50/MA20) — thị trường “khỏe” hay chỉ vài mã kéo. |
| **Persistence** | Sau khi breakout, giá **có tiếp tục đi lên** vài tuần hay nhanh chóng tụt lại — môi trường có “theo trend” hay không. |
| **Regime gate** | Chỉ cho hệ thống mua khi thị trường ở trạng thái “thuận” (ví dụ index trên MA200, volume tăng…). |
| **MHC (Market Health Composite)** | Chỉ số “sức khỏe” thị trường (phân bố volume, breadth, v.v.) để lọc thời điểm vào lệnh. |

---

## Kết quả ngắn gọn

Đã test **4 nhóm chiến lược** (breakout thuần, breakout + retest, pullback, U&R), mỗi nhóm nhiều config (regime on/off, volume filter, v.v.) — tức là **tìm kiếm khá exhaust**, không phải chỉ thử 1–2 lần rồi bỏ. Trên toàn bộ các variant đó:

- **Giai đoạn “học” (2020–2022):** Nhiều phiên bản (breakout thuần, breakout + retest, pullback, U&R) **đều lãi tốt** — code và logic không sai, trong giai đoạn đó chiến lược “ăn” được.
- **Giai đoạn “kiểm tra” và “giữ” (2023, 2024):** **Hầu hết đều lỗ hoặc không ổn định** — cùng một bộ rule, sang năm khác thì không còn edge.
- Thử thêm **regime gate** (chỉ mua khi thị trường “đẹp”) **vẫn không cứu** được 2023/2024.
- Đo **breadth** (bao nhiêu % mã trên MA50) trên ~80 mã: **2023 không “yếu”** — tức vấn đề **không phải** “ít mã tham gia”, mà là **sau khi breakout, giá không đi tiếp** (persistence thấp).

**Kết luận một câu:** Cách “mua khi breakout” (và pullback, U&R) **trong quá khứ 2020–2022 thì có lãi**, nhưng **2023–2024 không còn hiệu quả**; thêm lọc “thị trường khỏe” (breadth) cũng không sửa được. **Nguyên nhân chính: môi trường VN gần đây không còn “giữ trend” đủ lâu sau breakout** — đây là **sự không khớp mang tính cấu trúc** (structural mismatch), không phải thiếu data hay thiếu một module nhỏ.

---

## Ví dụ so sánh

- **Minervini (Mỹ):** Giá breakout → thường đi tiếp vài tuần → cắt lỗ ít, giữ winner lâu → có edge.
- **VN 2023–2024:** Giá breakout → hay quay đầu, rửa, không đi tiếp → cùng rule thì lỗ nhiều hơn lãi.

Nói nôm na: **động cơ (rule) thiết kế cho xăng (môi trường trend kéo dài), nhưng VN gần đây giống nhiên liệu khác (trend ngắn, rửa nhiều)** — nên không deploy hệ “breakout kiểu Minervini” ở dạng mechanical; có thể dùng làm **scanner / tham khảo** cho discretionary, không dùng làm **hệ tự động chạy tiền**.

---

## Trạng thái hiện tại (lab)

| Hạng mục | Trạng thái |
|----------|------------|
| Hệ “Minervini” mechanical (breakout/pullback/U&R) | **Đóng** — không deploy; chỉ research / scanner. |
| MHC (chỉ số sức khỏe thị trường) | Đã chạy diagnostic; **không** làm composite gate để “cứu” Minervini. |
| PP C2 m0 (hệ 3WT weekly khác) | **Đang pilot** — hệ đã qua stress test, deploy có kiểm soát. |

**Reopen Minervini mechanical** chỉ khi có **chỉ số persistence** rõ ràng (ví dụ: % lệnh breakout vẫn còn trên giá vào lệnh sau 10 phiên) chứng minh môi trường đã chuyển sang “giữ trend” lại — không reopen chỉ vì “cảm giác” hay chỉ vì breadth/level.
