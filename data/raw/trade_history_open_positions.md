# Trade History — Vị thế đang hold (chưa có action bán)

Nguồn: **Trade History.xlsx** (sheet **Port Analysis**).

**Quy tắc:** S Date trống **không** có nghĩa là chưa bán. **Đã có action bán** = cột **K, L, M** (Closed position: Vol, Price, Amount) có input.  
→ **Still holding** = các dòng mà cột K, L, M đều không có input (trống/0).

---

## Tóm tắt (theo quy tắc K–M)

| Mục | Giá trị |
|-----|--------|
| **Tổng số lot đang hold** | 65 |
| **Số mã đang hold** | 18 |

---

## 18 mã đang hold (theo số lot)

| Symbol | Số lot |
|--------|-------|
| MBB | 12 |
| MWG | 10 |
| VCI | 9 |
| SSI | 7 |
| TCX | 4 |
| SHS | 3 |
| DCM | 3 |
| HAH | 3 |
| PC1 | 2 |
| VSC | 2 |
| STB | 2 |
| SCS | 2 |
| MBS | 1 |
| PVD | 1 |
| GMD | 1 |
| HPG | 1 |
| VHC | 1 |
| NKG | 1 |

**Danh sách symbol:** DCM, GMD, HAH, HPG, MBB, MBS, MWG, NKG, PC1, PVD, SCS, SHS, SSI, STB, TCX, VCI, VHC, VSC.

---

## Sanity check vs Current positions.xlsx

- **Current positions.xlsx** (sheet Open): **18 mã**.
- **Trade History (still holding = K–M không có input):** **18 mã**.
- **Giao khớp:** 18/18 — danh sách trùng nhau.

→ Trade History (theo quy tắc K–M) và Current positions **nhất quán**.

---

*Cập nhật: dùng cột K–M có input = đã bán; không dùng S Date trống.*
