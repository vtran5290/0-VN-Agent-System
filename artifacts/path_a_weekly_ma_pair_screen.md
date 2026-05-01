# Path A Weekly MA-pair – Screen stage

Periods: **2018-2021**, **2024-2026Q1** (recent period for current conditions). Early-stop: if 2018-2021 has n_trades < 5 or MAR < -0.5, 2024-2026Q1 skipped for that config.

## Top configs for confirm stage

- support_ma=20, short_ma=10, long_ma=20 (score=0.7817, avg_mar=0.7817)
- support_ma=20, short_ma=5, long_ma=20 (score=0.6866, avg_mar=0.6866)
- support_ma=20, short_ma=10, long_ma=50 (score=0.6697, avg_mar=0.6697)
- support_ma=10, short_ma=10, long_ma=20 (score=0.6196, avg_mar=0.6196)
- support_ma=20, short_ma=10, long_ma=40 (score=0.5831, avg_mar=0.5831)
- support_ma=10, short_ma=10, long_ma=40 (score=0.5668, avg_mar=0.5668)
- support_ma=20, short_ma=10, long_ma=30 (score=0.5191, avg_mar=0.5191)
- support_ma=20, short_ma=20, long_ma=40 (score=0.5045, avg_mar=0.5045)

## Shortlist (use for --stage confirm)

- 20,10,20
- 20,5,20
- 20,10,50
- 10,10,20
- 20,10,40
- 10,10,40
- 20,10,30
- 20,20,40
