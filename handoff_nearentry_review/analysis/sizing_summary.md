# Sizing Optimization Summary
Generated: 2026-05-15

> Step 3 — sizing/exposure sweep on OOS-validated configs.
> PRIMARY: A3 (ema_dist + 18%/2.5 + ex_vin3) | SHADOW: S3 (mom20 + 18%/3.5 + full)

## A3_primary

### Equal-weight / Full-exposure baseline

| candidate   |   max_positions | sizing_mode   |   gross_exposure |   cagr |   sharpe |   max_dd |    mar |   fill_util |
|:------------|----------------:|:--------------|-----------------:|-------:|---------:|---------:|-------:|------------:|
| A3_primary  |              10 | equal         |           1.0000 | 0.1292 |   0.9363 |  -0.3502 | 0.3689 |      0.0193 |
| A3_primary  |              12 | equal         |           1.0000 | 0.1175 |   0.9116 |  -0.3494 | 0.3362 |      0.0228 |
| A3_primary  |              16 | equal         |           1.0000 | 0.1403 |   1.1675 |  -0.2568 | 0.5465 |      0.0304 |
| A3_primary  |              20 | equal         |           1.0000 | 0.1361 |   1.1828 |  -0.2651 | 0.5134 |      0.0371 |
| A3_primary  |              24 | equal         |           1.0000 | 0.1315 |   1.2344 |  -0.2614 | 0.5030 |      0.0445 |

### Top 10 by Sharpe

| candidate   |   max_positions | sizing_mode        |   gross_exposure |   cagr |   sharpe |   max_dd |    mar |   fill_util |
|:------------|----------------:|:-------------------|-----------------:|-------:|---------:|---------:|-------:|------------:|
| A3_primary  |              24 | conv_mom60         |           1.0000 | 0.1350 |   1.2383 |  -0.2727 | 0.4950 |      0.0445 |
| A3_primary  |              24 | conv_mom60         |           0.8500 | 0.1140 |   1.2356 |  -0.2366 | 0.4820 |      0.0445 |
| A3_primary  |              24 | equal              |           1.0000 | 0.1315 |   1.2344 |  -0.2614 | 0.5030 |      0.0445 |
| A3_primary  |              24 | conv_mom60         |           0.7000 | 0.0934 |   1.2329 |  -0.1989 | 0.4693 |      0.0445 |
| A3_primary  |              24 | equal              |           0.8500 | 0.1111 |   1.2319 |  -0.2266 | 0.4903 |      0.0445 |
| A3_primary  |              24 | equal              |           0.7000 | 0.0910 |   1.2294 |  -0.1904 | 0.4778 |      0.0445 |
| A3_primary  |              24 | inv_atr_conv_mom60 |           1.0000 | 0.1256 |   1.1846 |  -0.2686 | 0.4674 |      0.0445 |
| A3_primary  |              20 | equal              |           1.0000 | 0.1361 |   1.1828 |  -0.2651 | 0.5134 |      0.0371 |
| A3_primary  |              24 | inv_atr_conv_mom60 |           0.8500 | 0.1062 |   1.1818 |  -0.2330 | 0.4557 |      0.0445 |
| A3_primary  |              20 | equal              |           0.8500 | 0.1151 |   1.1805 |  -0.2299 | 0.5006 |      0.0371 |

### Top 8 by MAR

| candidate   |   max_positions | sizing_mode        |   gross_exposure |   cagr |   sharpe |   max_dd |    mar |   fill_util |
|:------------|----------------:|:-------------------|-----------------:|-------:|---------:|---------:|-------:|------------:|
| A3_primary  |              16 | conv_mom60         |           1.0000 | 0.1428 |   1.1621 |  -0.2505 | 0.5701 |      0.0304 |
| A3_primary  |              16 | conv_mom60         |           0.8500 | 0.1208 |   1.1606 |  -0.2166 | 0.5575 |      0.0304 |
| A3_primary  |              16 | equal              |           1.0000 | 0.1403 |   1.1675 |  -0.2568 | 0.5465 |      0.0304 |
| A3_primary  |              16 | conv_mom60         |           0.7000 | 0.0990 |   1.1590 |  -0.1815 | 0.5452 |      0.0304 |
| A3_primary  |              16 | equal              |           0.8500 | 0.1187 |   1.1662 |  -0.2220 | 0.5347 |      0.0304 |
| A3_primary  |              16 | equal              |           0.7000 | 0.0973 |   1.1649 |  -0.1860 | 0.5230 |      0.0304 |
| A3_primary  |              16 | inv_atr_conv_mom60 |           1.0000 | 0.1335 |   1.1127 |  -0.2596 | 0.5141 |      0.0304 |
| A3_primary  |              20 | equal              |           1.0000 | 0.1361 |   1.1828 |  -0.2651 | 0.5134 |      0.0371 |

### Verdict

Anchor (equal/max_pos=20/gross=1.00): Sharpe=1.183  maxDD=-26.5%

Best by Sharpe: `sizing_mode=conv_mom60` `max_positions=24` `gross_exposure=1.00`  Sharpe=1.238 (+0.055 vs anchor)  maxDD=-27.3% (-0.8% vs anchor)

> **PASS** — sizing upgrade survives: Sharpe improves without DD regression.

## S3_shadow

### Equal-weight / Full-exposure baseline

| candidate   |   max_positions | sizing_mode   |   gross_exposure |   cagr |   sharpe |   max_dd |    mar |   fill_util |
|:------------|----------------:|:--------------|-----------------:|-------:|---------:|---------:|-------:|------------:|
| S3_shadow   |              10 | equal         |           1.0000 | 0.0962 |   0.7107 |  -0.2976 | 0.3233 |      0.0132 |
| S3_shadow   |              12 | equal         |           1.0000 | 0.1119 |   0.8941 |  -0.2284 | 0.4899 |      0.0162 |
| S3_shadow   |              16 | equal         |           1.0000 | 0.1120 |   0.8965 |  -0.2758 | 0.4062 |      0.0212 |
| S3_shadow   |              20 | equal         |           1.0000 | 0.1191 |   1.0437 |  -0.2736 | 0.4352 |      0.0268 |
| S3_shadow   |              24 | equal         |           1.0000 | 0.1181 |   1.1546 |  -0.2724 | 0.4336 |      0.0319 |

### Top 10 by Sharpe

| candidate   |   max_positions | sizing_mode        |   gross_exposure |   cagr |   sharpe |   max_dd |    mar |   fill_util |
|:------------|----------------:|:-------------------|-----------------:|-------:|---------:|---------:|-------:|------------:|
| S3_shadow   |              24 | equal              |           1.0000 | 0.1181 |   1.1546 |  -0.2724 | 0.4336 |      0.0319 |
| S3_shadow   |              24 | equal              |           0.8500 | 0.1000 |   1.1538 |  -0.2364 | 0.4229 |      0.0319 |
| S3_shadow   |              24 | equal              |           0.7000 | 0.0820 |   1.1530 |  -0.1988 | 0.4125 |      0.0319 |
| S3_shadow   |              24 | inv_atr            |           1.0000 | 0.1176 |   1.1176 |  -0.2846 | 0.4133 |      0.0319 |
| S3_shadow   |              24 | inv_atr            |           0.8500 | 0.0996 |   1.1175 |  -0.2472 | 0.4029 |      0.0319 |
| S3_shadow   |              24 | inv_atr            |           0.7000 | 0.0817 |   1.1175 |  -0.2081 | 0.3926 |      0.0319 |
| S3_shadow   |              24 | conv_mom60         |           1.0000 | 0.1166 |   1.0973 |  -0.2653 | 0.4397 |      0.0319 |
| S3_shadow   |              24 | conv_mom60         |           0.8500 | 0.0988 |   1.0973 |  -0.2301 | 0.4294 |      0.0319 |
| S3_shadow   |              24 | conv_mom60         |           0.7000 | 0.0811 |   1.0972 |  -0.1933 | 0.4193 |      0.0319 |
| S3_shadow   |              24 | inv_atr_conv_mom60 |           0.7000 | 0.0804 |   1.0637 |  -0.2032 | 0.3957 |      0.0319 |

### Top 8 by MAR

| candidate   |   max_positions | sizing_mode        |   gross_exposure |   cagr |   sharpe |   max_dd |    mar |   fill_util |
|:------------|----------------:|:-------------------|-----------------:|-------:|---------:|---------:|-------:|------------:|
| S3_shadow   |              12 | inv_atr            |           1.0000 | 0.1126 |   0.8895 |  -0.2284 | 0.4930 |      0.0162 |
| S3_shadow   |              12 | conv_mom60         |           1.0000 | 0.1125 |   0.8746 |  -0.2284 | 0.4927 |      0.0162 |
| S3_shadow   |              12 | inv_atr_conv_mom60 |           1.0000 | 0.1125 |   0.8663 |  -0.2284 | 0.4925 |      0.0162 |
| S3_shadow   |              12 | equal              |           1.0000 | 0.1119 |   0.8941 |  -0.2284 | 0.4899 |      0.0162 |
| S3_shadow   |              12 | inv_atr            |           0.8500 | 0.0958 |   0.8891 |  -0.1970 | 0.4861 |      0.0162 |
| S3_shadow   |              12 | conv_mom60         |           0.8500 | 0.0957 |   0.8743 |  -0.1970 | 0.4859 |      0.0162 |
| S3_shadow   |              12 | inv_atr_conv_mom60 |           0.8500 | 0.0957 |   0.8662 |  -0.1970 | 0.4857 |      0.0162 |
| S3_shadow   |              12 | equal              |           0.8500 | 0.0952 |   0.8935 |  -0.1970 | 0.4830 |      0.0162 |

### Verdict

Anchor (equal/max_pos=20/gross=1.00): Sharpe=1.044  maxDD=-27.4%

Best by Sharpe: `sizing_mode=equal` `max_positions=24` `gross_exposure=1.00`  Sharpe=1.155 (+0.111 vs anchor)  maxDD=-27.2% (+0.1% vs anchor)

> **PASS** — sizing upgrade survives: Sharpe improves without DD regression.

---

*End of Sizing Summary*
