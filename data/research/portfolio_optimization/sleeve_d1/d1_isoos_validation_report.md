# D1 IS/OOS Validation

**Label:** RESEARCH_ONLY_NOT_PRODUCTION
**Verdict:** FAIL (2/6 combos all-check pass; decision-band 1/4)

## Confirmation checks (IS/OOS/ex-2021/ex-2021+2022 MAR > 0)

### N2_slip0.005 (display-only optimistic)
- IS MAR > 0: PASS (0.0530)
- OOS MAR > 0: PASS (0.5758)
- Ex-2021 MAR > 0: PASS (0.2415)
- Ex-2021/2022 MAR > 0: PASS (0.1224)

### N2_slip0.010 (decision band)
- IS MAR > 0: PASS (0.0154)
- OOS MAR > 0: PASS (0.4858)
- Ex-2021 MAR > 0: PASS (0.1909)
- Ex-2021/2022 MAR > 0: PASS (0.0764)

### N2_slip0.015 (decision band)
- IS MAR > 0: FAIL (-0.0164)
- OOS MAR > 0: PASS (0.4002)
- Ex-2021 MAR > 0: PASS (0.1385)
- Ex-2021/2022 MAR > 0: PASS (0.0382)

### N3_slip0.005 (display-only optimistic)
- IS MAR > 0: FAIL (-0.1152)
- OOS MAR > 0: PASS (0.4519)
- Ex-2021 MAR > 0: PASS (0.0983)
- Ex-2021/2022 MAR > 0: FAIL (-0.0575)

### N3_slip0.010 (decision band)
- IS MAR > 0: FAIL (-0.1181)
- OOS MAR > 0: PASS (0.3911)
- Ex-2021 MAR > 0: PASS (0.0752)
- Ex-2021/2022 MAR > 0: FAIL (-0.0600)

### N3_slip0.015 (decision band)
- IS MAR > 0: FAIL (-0.1206)
- OOS MAR > 0: PASS (0.3366)
- Ex-2021 MAR > 0: PASS (0.0547)
- Ex-2021/2022 MAR > 0: FAIL (-0.0621)

## Window results

        window     mar    cagr  max_dd  n_trades  win_rate  n_floor  entry_slippage     slippage_label               research_label
  IS_2013_2019  0.0530  0.0042 -0.0792       309    0.6181        2          0.0050 display_optimistic RESEARCH_ONLY_NOT_PRODUCTION
 OOS_2020_2026  0.5758  0.0536 -0.0931       522    0.6628        2          0.0050 display_optimistic RESEARCH_ONLY_NOT_PRODUCTION
roll_2013_2017  0.1428  0.0087 -0.0611       203    0.6305        2          0.0050 display_optimistic RESEARCH_ONLY_NOT_PRODUCTION
roll_2018_2021  0.4999  0.0167 -0.0334       245    0.6571        2          0.0050 display_optimistic RESEARCH_ONLY_NOT_PRODUCTION
roll_2022_2026  0.6416  0.0597 -0.0931       383    0.6475        2          0.0050 display_optimistic RESEARCH_ONLY_NOT_PRODUCTION
       ex_2021  0.2415  0.0225 -0.0931       785    0.6331        2          0.0050 display_optimistic RESEARCH_ONLY_NOT_PRODUCTION
  ex_2021_2022  0.1224  0.0098 -0.0804       575    0.6226        2          0.0050 display_optimistic RESEARCH_ONLY_NOT_PRODUCTION
  IS_2013_2019  0.0154  0.0013 -0.0848       309    0.6084        2          0.0100      decision_band RESEARCH_ONLY_NOT_PRODUCTION
 OOS_2020_2026  0.4858  0.0460 -0.0947       522    0.6475        2          0.0100      decision_band RESEARCH_ONLY_NOT_PRODUCTION
roll_2013_2017  0.0959  0.0060 -0.0629       203    0.6207        2          0.0100      decision_band RESEARCH_ONLY_NOT_PRODUCTION
roll_2018_2021  0.3058  0.0121 -0.0395       245    0.6367        2          0.0100      decision_band RESEARCH_ONLY_NOT_PRODUCTION
roll_2022_2026  0.5410  0.0512 -0.0947       383    0.6371        2          0.0100      decision_band RESEARCH_ONLY_NOT_PRODUCTION
       ex_2021  0.1909  0.0181 -0.0947       785    0.6204        2          0.0100      decision_band RESEARCH_ONLY_NOT_PRODUCTION
  ex_2021_2022  0.0764  0.0068 -0.0888       575    0.6070        2          0.0100      decision_band RESEARCH_ONLY_NOT_PRODUCTION
  IS_2013_2019 -0.0164 -0.0015 -0.0943       309    0.5955        2          0.0150      decision_band RESEARCH_ONLY_NOT_PRODUCTION
 OOS_2020_2026  0.4002  0.0385 -0.0962       522    0.6360        2          0.0150      decision_band RESEARCH_ONLY_NOT_PRODUCTION
roll_2013_2017  0.0506  0.0034 -0.0667       203    0.6059        2          0.0150      decision_band RESEARCH_ONLY_NOT_PRODUCTION
roll_2018_2021  0.1657  0.0076 -0.0456       245    0.6286        2          0.0150      decision_band RESEARCH_ONLY_NOT_PRODUCTION
roll_2022_2026  0.4454  0.0429 -0.0962       383    0.6240        2          0.0150      decision_band RESEARCH_ONLY_NOT_PRODUCTION
       ex_2021  0.1385  0.0137 -0.0990       785    0.6076        2          0.0150      decision_band RESEARCH_ONLY_NOT_PRODUCTION
  ex_2021_2022  0.0382  0.0038 -0.0990       575    0.5896        2          0.0150      decision_band RESEARCH_ONLY_NOT_PRODUCTION
  IS_2013_2019 -0.1152 -0.0098 -0.0852        71    0.4789        3          0.0050 display_optimistic RESEARCH_ONLY_NOT_PRODUCTION
 OOS_2020_2026  0.4519  0.0301 -0.0666       151    0.7020        3          0.0050 display_optimistic RESEARCH_ONLY_NOT_PRODUCTION
roll_2013_2017 -0.1552 -0.0119 -0.0769        49    0.5102        3          0.0050 display_optimistic RESEARCH_ONLY_NOT_PRODUCTION
roll_2018_2021  0.2854  0.0063 -0.0222        55    0.5818        3          0.0050 display_optimistic RESEARCH_ONLY_NOT_PRODUCTION
roll_2022_2026  0.5474  0.0365 -0.0666       118    0.7034        3          0.0050 display_optimistic RESEARCH_ONLY_NOT_PRODUCTION
       ex_2021  0.0983  0.0084 -0.0857       215    0.6233        3          0.0050 display_optimistic RESEARCH_ONLY_NOT_PRODUCTION
  ex_2021_2022 -0.0575 -0.0053 -0.0926       128    0.5156        3          0.0050 display_optimistic RESEARCH_ONLY_NOT_PRODUCTION
  IS_2013_2019 -0.1181 -0.0106 -0.0900        71    0.4789        3          0.0100      decision_band RESEARCH_ONLY_NOT_PRODUCTION
 OOS_2020_2026  0.3911  0.0274 -0.0701       151    0.6887        3          0.0100      decision_band RESEARCH_ONLY_NOT_PRODUCTION
roll_2013_2017 -0.1588 -0.0128 -0.0804        49    0.5102        3          0.0100      decision_band RESEARCH_ONLY_NOT_PRODUCTION
roll_2018_2021  0.2229  0.0050 -0.0223        55    0.5636        3          0.0100      decision_band RESEARCH_ONLY_NOT_PRODUCTION
roll_2022_2026  0.4764  0.0334 -0.0701       118    0.6949        3          0.0100      decision_band RESEARCH_ONLY_NOT_PRODUCTION
       ex_2021  0.0752  0.0068 -0.0907       215    0.6140        3          0.0100      decision_band RESEARCH_ONLY_NOT_PRODUCTION
  ex_2021_2022 -0.0600 -0.0062 -0.1026       128    0.5078        3          0.0100      decision_band RESEARCH_ONLY_NOT_PRODUCTION
  IS_2013_2019 -0.1206 -0.0114 -0.0948        71    0.4648        3          0.0150      decision_band RESEARCH_ONLY_NOT_PRODUCTION
 OOS_2020_2026  0.3366  0.0247 -0.0734       151    0.6755        3          0.0150      decision_band RESEARCH_ONLY_NOT_PRODUCTION
roll_2013_2017 -0.1622 -0.0136 -0.0839        49    0.4898        3          0.0150      decision_band RESEARCH_ONLY_NOT_PRODUCTION
roll_2018_2021  0.1598  0.0036 -0.0227        55    0.5636        3          0.0150      decision_band RESEARCH_ONLY_NOT_PRODUCTION
roll_2022_2026  0.4127  0.0303 -0.0734       118    0.6780        3          0.0150      decision_band RESEARCH_ONLY_NOT_PRODUCTION
       ex_2021  0.0547  0.0052 -0.0956       215    0.6000        3          0.0150      decision_band RESEARCH_ONLY_NOT_PRODUCTION
  ex_2021_2022 -0.0621 -0.0070 -0.1124       128    0.4844        3          0.0150      decision_band RESEARCH_ONLY_NOT_PRODUCTION

## Interpretation
- 0.5% entry slippage is display-only optimistic; verdicts reference 1.0% and 1.5% decision bands.
- D1 checks replace RS vs FIFO with positive MAR across IS/OOS and ex-bull-year windows.
- N=3 IS window with <30 trades should be treated as underpowered.