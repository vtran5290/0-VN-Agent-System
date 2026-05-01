# FireAnt Index Resolution Logic

## Native index symbols that exist
Vietnam:
- VNINDEX
- VN30
- HNXINDEX
- HNX30
- UPINDEX

Global:
- ^DJI
- ^IXIC
- ^GSPC
- ^NYA
- ^RUT
- ^FTSE
- ^GDAXI
- ^FCHI
- ^N225
- ^SSEC
- ^HSI
- ^KS11
- US.VFS

## Common logical names absent as native index symbols
- VN100
- VNMID
- VNSML
- VNALL
- VNDIAMOND
- VNFINLEAD
- VNFINSELECT
- VNX50
- VNXALL
- VNSI
- VNDIVIDEND
- VN50GROWTH
- VNMITECH

## ETF proxies
VN100:
- FUEVN100
- FUEIP100

VNMID:
- FUEDCMID

VNDIAMOND:
- FUEVFVND
- FUEMAVND
- FUEBFVND
- FUEKIVND
- FUEABVND
- FUETPVND

VNFINLEAD:
- FUESSVFL

VNFINSELECT:
- FUEKIVFS

VNX50:
- FUESSV50
- FUEFCV50
- FUETCC50

VN30:
- E1VFVN30
- FUEKIV30
- FUEMAV30
- FUESSV30

## Important caveat
ETF proxies are correlated with indices but are not identical index levels.

## Sector proxies via /industries
0001 -> Dầu khí
1000 -> Vật liệu cơ bản
2000 -> Công nghiệp
3000 -> Hàng tiêu dùng
4000 -> Y tế
6000 -> Viễn thông
7000 -> Hạ tầng
8000 -> Tài chính
9000 -> Công nghệ

## Resolution order
1. Try native index
2. Else ETF proxy
3. Else /industries historical stats
4. Else /icb historical index
5. Else unavailable

