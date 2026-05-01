# Weekly Macro/Policy/Decision Packet — as-of 2026-05-01
_Report age: 0 day(s); market snapshot date: 2026-05-01_

**Data confidence:** Medium | missing: vietnam.interbank_on | not_due_yet: — | warnings: —
**Market level source:** VNINDEX | **DistDays proxy:** VN30
## Global Macro + Fed
- FACTS (levels) + source tag:
  - UST 2Y: 3.92 — FRED DGS2, **value_date**=2026-04-29 (fred_dgs_daily_observation; not labeled as broker session close)
  - UST 10Y: 4.42 — FRED DGS10, **value_date**=2026-04-29 (fred_dgs_daily_observation)
  - **DXY reconstructed (FRED H.10, ICE-style):** 98.5373 (value_date=2026-04-24)
  - **DXY third-party proxy (Yahoo DX-Y.NYB):** None (value_date=2026-04-30) — cross-check, not licensed ICE; source=Yahoo Finance DX-Y.NYB
  - **DXY ICE official (env/manual only):** None (value_date=None)
  - **Legacy `global.dxy` (WoW driver):** 98.5373 — reconstructed if available, else third-party
  - **USD broad (FRED DTWEXBGS):** 118.7294 (value_date=2026-04-24)
  - CPI YoY: 3.26 — source=bls, **reference_month**=2026-03, value_date=2026-03
  - Nonfarm payroll **MoM change (persons):** 178000 (PAYEMS level date=2026-03-01)
  - Nonfarm payroll **level (thousands):** 158637.0 (prior level date=2026-02-01)
  - Legacy field `nfp` (intentionally null): None
- WHAT CHANGED (WoW):
  - UST 2Y Δ: 0.16000000000000014
  - UST 10Y Δ: 0.15000000000000036
  - Primary DXY Δ (legacy `dxy`): -20.953699999999998
  - USD broad (DTWEXBGS) Δ: None
  - Payroll MoM Δ persons: None
- INTERPRETATION: TBD when data is filled.
  - _Note:_ `ust_2y` value_date (2026-04-29) is **before** report as-of (2026-05-01).
  - _Note:_ `ust_10y` value_date (2026-04-29) is **before** report as-of (2026-05-01).
  - _Note:_ `usd_broad_index_fred` value_date (2026-04-24) is **before** report as-of (2026-05-01).
  - _Note:_ `nonfarm_payroll_level_thousands` value_date (2026-03-01) is **before** report as-of (2026-05-01).
  - _Note:_ `nonfarm_payroll_change_persons` value_date (2026-03-01) is **before** report as-of (2026-05-01).
  - _Note:_ `dxy_reconstructed` value_date (2026-04-24) is **before** report as-of (2026-05-01).

## Vietnam Policy + Liquidity
- FACTS (levels):
  - OMO net: 9000 (verification=parsed, source=sbv, detail=SBV nghiệp vụ thị trường mở (HTML scrape))
  - OMO breakdown: value_date=2026-04-10, inject=25000, withdraw=0, rate=4.5; note: Mua kỳ hạn: 14ng 5000ty + 35ng 10000ty + 56ng 10000ty, LS 4.5%/nam
  - Interbank ON: None
  - Credit growth YoY: 1.0
  - **SBV reference USD/VND:** 25113
- WHAT CHANGED (WoW):
  - OMO net Δ: -1000
  - Interbank ON Δ: None
  - Credit growth YoY Δ: 0.0
- TRANSMISSION (template): rates → credit → FX → sentiment (fill next).

## Vietnam Policy
- FACTS:
  - 2026-02-01 | Policy referenced in manager commentary | Several fund manager commentaries referenced domestic policy themes and SOE-related measures; details vary by report.
  - 2026-02-28 | Báo cáo tình hình kinh tế – xã hội tháng Hai năm 2026 | IIP 2 tháng +10.4% YoY; CPI 2 tháng +2.94%; Xuất khẩu 76.36 tỷ USD +18.3%; Nhập siêu 2.98 tỷ USD; FDI thực hiện 3.21 tỷ +8.8%; Thu NSNN 601.3T +13.1%; Khách quốc tế 4.7M +18.1%.

## Research Intake This Week
### Macro
  - **Nông, lâm, thủy sản:** Lúa đông xuân cả nước 2.731,4 nghìn ha (giảm 58,0k ha YoY); ĐBSCL 1.234,1k ha. Lúa hè thu ĐBSCL 171,7k ha (-20,1% YoY), năng suất 54,1 tạ/ha (+1,6), sản lượng 909,6k tấn. Chăn nuôi: lợn phục hồi, trâu -4,4%, bò -2,1%, gia cầm +1,9%. Rừng trồng mới 11,8k ha (-1,4% YoY); gỗ khai thác 1.381,9k m³ (+4,1%). Thủy sản 2 tháng 1.279,2k tấn (+2,9% YoY); nuôi trồng 722,6k (+4,4%), khai thác 556,6k (+1,1%).
  - **Công nghiệp:** IIP tháng 2: -18,5% MoM, +1,0% YoY; 2 tháng đầu năm +10,4% YoY (cùng kỳ 2025 +7,5%). Chế biến chế tạo +11,5% (đóng góp 8,9 pp), điện +6,3% (0,6 pp), khai khoáng +5,4% (0,9 pp). Lao động DN công nghiệp 01/02 +0,2% MoM, +4,0% YoY. IIP tăng ở cả 34 tỉnh.
  - **Đăng ký doanh nghiệp:** Tháng 2: 11,3k DN thành lập mới (+11,6% YoY), 6,2k quay lại (-12,6% YoY), 4.257 tạm ngừng (-92,2% MoM, +19,8% YoY), 3.492 chờ giải thể (-52,2%, +17,5%), 3.290 hoàn tất giải thể (-28,6%, +89,4%). 2 tháng: gần 64,5k DN mới + quay lại (+29,4% YoY); 77,0k DN rút lui (+14,9%). Vốn ĐK bổ sung 851,9 nghìn tỷ (+20,1% YoY).
  - **Đầu tư:** Vốn NSNN tháng 2: 38,9 nghìn tỷ (+0,4% YoY); 2 tháng 83,5 nghìn tỷ (9,4% KH năm, +11,5% YoY). FDI đăng ký đến 28/02: 6,03 tỷ USD (-12,6% YoY). FDI thực hiện 2 tháng 3,21 tỷ USD (+8,8% YoY). VN ra nước ngoài 2 tháng: 36 dự án, 540,2 triệu USD (gấp 2,3 lần YoY).
  - **Thu, chi NSNN:** Thu 2 tháng 601,3 nghìn tỷ (23,8% dự toán, +13,1% YoY). Chi 311,0 nghìn tỷ (9,8% dự toán, +11,0% YoY).
  - **Thương mại, giá, vận tải, du lịch:** Bán lẻ & DV tiêu dùng 2 tháng 1.236,6 nghìn tỷ (+7,9% YoY; thực +4,5%). Xuất khẩu 2 tháng 76,36 tỷ USD (+18,3% YoY), nhập khẩu 79,34 tỷ (+26,3% YoY); cán cân nhập siêu 2,98 tỷ USD (cùng kỳ 2025 xuất siêu 1,77 tỷ). Hoa Kỳ lớn nhất XK (23,8 tỷ), Trung Quốc lớn nhất NK (31,9 tỷ). CPI 02/2026: +1,14% MoM, +3,35% YoY; 2 tháng +2,94% YoY; lạm phát cơ bản +3,47%. Giá vàng 2 tháng +82,67% YoY; USD index +2,74% YoY. Vận tải hành khách 2 tháng 1.155,2 triệu lượt (+23,6% YoY); hàng hóa 543,3 triệu tấn (+14,7% YoY). Khách quốc tế 2 tháng gần 4,7 triệu (+18,1% YoY).
  - **Xã hội:** 95,5% hộ đánh giá thu nhập ổn định/tăng; 4,5% giảm. Hỗ trợ gạo cứu đói Tết 15,3k tấn. Chiến dịch Quang Trung: 34.759 nhà sửa xong, 1.597 nhà xây lại hoàn thành. Sốt xuất huyết 32,9k ca (2 tử vong), tay chân miệng 16,6k (2 tử vong). TNGT 2 tháng: 2.932 vụ, 1.780 chết, 1.799 bị thương. Vi phạm môi trường 4.695 vụ, xử lý 3.899 vụ, phạt 66,7 tỷ. Cháy nổ 515 vụ, 23 chết, 27 bị thương.


## Sectors & Companies (Earnings / Broker Notes)
- FACTS:
  - None reported this week.

- MARKET (levels): vnindex_level=1854.1, vn30_level=2022.75, distribution_days_rolling_20=0 (proxy: VN30)
- **Distribution (LB=25, refined):** VN30=0, HNX=3, UPCOM=3 → Composite=Normal (leader=VN30)
- Breadth: VN30 trend_ok(>MA20)=True | HNX close=250.66, trend_ok(>MA20)=False | UPCOM close=127.78, trend_ok(>MA20)=False
- **Broad market weak:** HNX and UPCOM both below MA20.
- **Index holding but breadth weak → breakout failure risk ↑**
- WHAT CHANGED (WoW):
  - VNIndex Δ: 157.8599999999999, Dist days Δ: -4

## Regime Engine
- Regime: STATE B
- Regime shift: None
- Inputs: global_liquidity=tight, vn_liquidity=easing
- **Suggested Regime (advisory):** B (from dist composite, breadth, MA trend)
- **Current Regime:** B
- **Mismatch:** No

## Probability + Allocation
- P(Fed cut within 3m): 0.35000000000000003
- P(VN tightening within 1m): 0.2
- P(VNIndex breakout within 1m): 0.5
- Allocation: {'gross_exposure': 0.55, 'cash_weight': 0.45, 'constraints': {'max_single_position': 0.12, 'max_sector_weight': 0.3, 'max_portfolio_drawdown': 0.08, 'default_stop_loss': 0.07}}

## Portfolio Structure (Hybrid)
- Core allowed: True
- Bucket allocation: {'core': 0.33, 'swing': 0.22, 'cash': 0.45, 'note': 'Core enabled'}

## Current book (Excel-derived)
- **FACTS:** Positions below come from `data/raw/current_positions_derived.json` (ingested from `C:\Users\LOLII\Documents\V\Port Analysis\Analysis - FQuery - 20260504.xlsx`) — not a FireAnt or broker statement; qty = shares from Open!X; avg_cost = abs(Open!W).
- **Open positions:** 9
  - **DXG:** qty 40000, avg cost 14.608 VND/sh | sector/tag: BDS
  - **HAG:** qty 10000, avg cost 15.753 VND/sh | sector/tag: Bán Lẻ / HK
  - **HCM:** qty 5000, avg cost 26.800 VND/sh | sector/tag: Energy / DTC
  - **MWG:** qty 6000, avg cost 83.321 VND/sh | sector/tag: Bán Lẻ / HK
  - **NVL:** qty 49300, avg cost 14.445 VND/sh | sector/tag: BDS
  - **STB:** qty 9000, avg cost 67.144 VND/sh | sector/tag: Ngân hàng
  - **TCH:** qty 35000, avg cost 18.043 VND/sh | sector/tag: BDS
  - **VCG:** qty 3000, avg cost 22.600 VND/sh | sector/tag: Energy / DTC
  - **VCI:** qty 21250, avg cost 26.284 VND/sh | sector/tag: CTCK

## Decision Layer
- Top 3 actions:
  1) Maintain mid exposure per band (gross=0.55, cash=0.45).
  2) Favor leaders with earnings clarity; avoid adding to laggards/high-beta breakouts without confirmation.
  3) Scale exposure only if breakout attempts succeed AND distribution-day risk is not rising.
- Top 3 risks:
  1) Regime B mismatch: global tight can override VN easing quickly (external shock sensitivity).
  2) Data gaps → narrative bias (probabilities become unreliable).
  3) Sudden liquidity shock (global or VN) causing gap-down risk.
- Watchlist updates (regime-fit + risk posture):
  - Posture: Selective / Leader-only
  - Tickers: SSI, VCI, SHS, TCX, MBB, STB, SHB, DCM, PVD, PC1, DXG, VSC, GMD, MWG
  - MVP: no per-ticker scoring yet. Add technical/fundamental signals later.
  - SSI: regime_fit=B, total_score=None
  - VCI: regime_fit=B, total_score=None
  - SHS: regime_fit=B, total_score=None
  - TCX: regime_fit=B, total_score=None
  - MBB: regime_fit=B, total_score=None
  - STB: regime_fit=B, total_score=None
  - SHB: regime_fit=B, total_score=None
  - DCM: regime_fit=B, total_score=None
  - PVD: regime_fit=B, total_score=None
  - PC1: regime_fit=B, total_score=None
  - DXG: regime_fit=B, total_score=None
  - VSC: regime_fit=B, total_score=None
  - GMD: regime_fit=B, total_score=None
  - MWG: regime_fit=B, total_score=None

### Backtest edge (knowledge)
- No backtest records available. Add backtest knowledge (e.g. data/raw/backtest_*.json or knowledge layer) to populate.

## Watchlist Updates
- Top candidates (by total score):
  - MBB: total=3.5 (F=4, T=3, R=4) | placeholder
  - SSI: total=3.0 (F=3, T=3, R=3) | placeholder

## Execution & Monitoring
- Market risk flag (dist days): {'distribution_days_rolling_20': 0, 'distribution_days': {'vn30': 0, 'hnx': 3, 'upcom': 3}, 'dist_risk_composite': 'Normal', 'dist_proxy_symbol': 'VN30', 'risk_flag': 'Normal', 'force_reduce_gross': False}
- Hormuz energy shock layer: ENERGY_SHOCK_LOW | mode=headline | vn_inflation=low | vn_supply=low | checklist=0/6(unknown)

## Execution — Sell/Trim Signals (MVP)
- VCI: SELL / EXIT | Day-2 confirmation breach (tier=None)
- HCM: HOLD | No violation (tier=3)
- STB: HOLD | No violation (tier=3)
- VCG: HOLD | No violation (tier=None)
- DXG: HOLD | No violation (tier=None)
- NVL: HOLD | No violation (tier=None)
- TCH: HOLD | No violation (tier=3)
- HAG: HOLD | No violation (tier=None)
- MWG: SELL / EXIT | Day-2 confirmation breach (tier=None)

## Portfolio Health
- **% positions below MA20:** 22.2% (2/9)
- **% positions with sell/trim active:** 22.2% (2/9)
- **Avg R multiple (open):** — (add r_multiple in tech_status)
- **Risk concentration by sector:**
  - —: 22.2% (2)
  - Real estate: 22.2% (2)
  - Securities: 11.1% (1)
  - Banking: 11.1% (1)
  - Construction/Infra: 11.1% (1)
  - Agriculture: 11.1% (1)
  - Retail: 11.1% (1)

## Council Process Status
- council_output status: stale_meeting_id
- mechanically_executable: True
- chair_decision logged: True
- Next step: run council prompts and save `data/decision/council_output.json`, then re-run weekly.

## Open questions
- WoW Vietnam liquidity
- Dist days trend
- Council execution

## Signals to monitor next week
- Update: UST 2Y/10Y (FRED observation dates), **DXY reconstructed** / third-party proxy, USD broad (DTWEXBGS), CPI (BLS ref month), payroll **MoM change**
- VN: OMO net (SBV/TBNN fallback provenance), interbank ON, credit growth trend, SBV reference USD/VND
- Market: distribution days rolling-20, breadth, failed breakouts

## If X happens → do Y
- If regime shifts to STATE C (tight+tight) → reduce gross, raise cash, tighten stops.
- If distribution days cluster + failed breakout → cut laggards, only hold leaders.
- If policy tailwind + earnings confirm for a sector → overweight with risk limits.