# Decision layer template (điền bằng outputs)

**Cách dùng:** Chạy playbook (1A+1B+1C) → có 4 file. Paste 4 cụm (10–20 dòng mỗi cụm) vào chat → điền các chỗ `_____` bên dưới. Không cần đoán: dùng số từ decision_matrix + gate waterfall + walk_forward.

---

## 1) Survivors (realism: fee=30 bps, min_hold=3)

**Core (deploy):** _____

- Lý do: PF _____, expectancy_r _____, trades/year _____, MaxDD _____
- D1 (WF): 2023 _____ (expectancy_r), 2024 _____ (expectancy_r)
- D2 (Top10%PnL holdout): _____%
- **Thesis:** T1 / T2 / T3 (từ gate waterfall)

**Backup (deploy candidate #2):** _____

- Lý do: PF _____, expectancy_r _____, trades/year _____
- Điều kiện dùng: _____ (vd. chỉ khi regime_on / chỉ VN30 / chỉ market risk-on)

**Experimental (paper / iterate):** _____

- Lý do: gross edge có nhưng realism chưa pass / hoặc pass nhưng unstable
- Iterate plan: I2 / I1 / I3 + param sweep nhỏ _____

---

## 2) Top 3 actions (tuần này)

1. _____ (Deploy core scanner + weekly run + ledger spot-check)
2. _____ (Freeze config + enable regime gate / fill mode / etc.)
3. _____ (Run iterate I2/I1/I3 nếu fail gates – chỉ 1 vòng)

---

## 3) Top 3 risks (cần kiểm soát)

- **Regime dependency:** A-universe sống nhưng B chết → rủi ro overfit liquidity
- **Concentration risk:** top10_pct_pnl > 60% trên holdout → “few trades carry all”
- **Execution realism:** next-open-fill vs close-fill khác mạnh → edge phụ thuộc fill

---

## 4) Watchlist update (weekly scan rules)

- **Weekly scan universe:** VN30 + top value traded (hoặc broad)
- **Use engine:** Core version _____ để ra list ứng viên
- **Confirmation:** Backup _____ như filter (vd. M4 retest only)
- **Do not trade** nếu regime_off (nếu thesis T1/T2 cần)

---

## 5) Signals to monitor next week

- expectancy_r và PF của core ở fee=30/min_hold=3 có giữ được khi chạy walk-forward không.
- Gate waterfall: gate nào tạo delta expectancy_r lớn nhất trên cả A và B.

---

## 6) If X happens → do Y

- **Nếu thesis = T2 (retest)** → do: khóa core = M4/M10 (+M11 nếu broad noisy), chỉ sweep retest 1–7 và undercut 2–3%.
- **Nếu thesis = T1 (TT/regime)** → do: core = M11 + M9 + M6, VCP chỉ soft.
- **Nếu fail D1/D2 nhưng pass D3** → do: giảm universe về VN30/top liquidity + bật regime + next-open-fill test, rồi chạy iterate I2.

---

# Interpret nhanh (nhìn 10 dòng là biết thesis + core)

## A) Nhìn decision_matrix.csv (fee30, min_hold3)

| Nhìn | Ý nghĩa |
|------|--------|
| **Expectancy_r** | Ưu tiên số này trước PF. |
| **trades/year** | < 10 → coi như non-deploy (variance quá lớn). |
| **top10_pct_pnl** | > 60% → cần regime gate hoặc pivot/rules lại. |

- Chỉ **M4/M10** còn expectancy_r ≥ 0.10 trong realism → thesis thường **T2**.
- **M11** làm mọi thứ “sống lại” → thesis thường **T1**.
- **M2/M9** thắng ổn ở cả A và B → thesis có thể **T3**.

## B) Nhìn gate waterfall (A và B)

| Delta lớn nhất ở | Thesis |
|------------------|--------|
| **G0** | T1 (edge từ TT/regime) |
| **G5** | T2 (edge từ retest) |
| **G3 / G4** | T3 (edge từ VCP/close strength) |

## C) Nhìn walk_forward_results.csv (2023 vs 2024)

- **Cả 2 năm expectancy_r > 0** → pass D1.
- **Một năm âm mạnh** → không deploy, chỉ iterate + tighten regime.

---

# Paste 4 cụm → điền template

Chỉ cần paste đúng **4 cụm** (raw 10–20 dòng mỗi cụm):

1. **decision_matrix.csv** — các dòng fee=30, min_hold=3 cho M3, M4, M9, M10, M11 (hoặc M1–M11).
2. **gate_attribution_A.csv** — các dòng G0..G5.
3. **gate_attribution_B.csv** — các dòng G0..G5.
4. **walk_forward_results.csv** — rows của M3/M4 (2023 validate, 2024 holdout).

→ Sẽ trả 1 message: Survivors (core/backup/experimental) + Top 3 actions + Top 3 risks + Watchlist update + Signals + If X → do Y.
