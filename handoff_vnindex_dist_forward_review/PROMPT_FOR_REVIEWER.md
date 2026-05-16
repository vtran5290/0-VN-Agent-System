# Prompt for external AI — VNINDEX distribution regime & forward returns (methodology review)

**Role:** You are a quantitative / market-microstructure reviewer. Your job is to **critique, improve, and if possible replace** the methodology below so that any reported “probabilities” or expectations are **as predictive and statistically honest as the data allows** (walk-forward, proper baselines, uncertainty, leakage checks).

**Language:** Reply in the same language as the repo owner (Vietnamese or English); technical content may stay English.

---

## 1. Business question (owner intent)

On the Vietnam market:

1. **Count** O’Neil-style **distribution days** on **VNINDEX** and on a **synthetic “ex-Vin”** index (basket **VIC, VHM, VRE**; **VPL excluded** per research baseline) over a fixed calendar window (**2026-03-23 → 2026-05-14**, inclusive last bar).
2. From **2012** to as-of, characterize **forward returns** at horizons **25, 50, 100, 150, 200, 250 trading days** after episodes that are **“similar”** to the current regime:
   - Same rolling window length **L** as the current window (here **L = 36** trading days).
   - Regime defined by **count of distribution days** inside that trailing window (original study used **≤ 1**; current window has **3**, so a relaxed **≤ 3** was used for comparability — **flag this as a methodological fork**).
3. Compare **with Vin** (cap-weight VNINDEX) vs **ex-Vin synthetic** (derived level).

The owner wants **better predictive quality** than raw historical win-rates from a heavily filtered, overlapping sample.

---

## 2. Facts you must preserve (do not “improve away” without stating it)

- **Primary price source in scripts:** merged **local CSV** `minervini_backtest/data/raw/VNINDEX.csv` + optional extension via `src/intake/fireant_historical.fetch_historical` (FireAnt web `HistoricalQuotes` JSON/XML; responses cached under `data/cache/fireant`).
- **Distribution day (as implemented in research scripts):**  
  `close_t <= close_{t-1} * (1 - 0.002)` **and** `volume_t > volume_{t-1}`; require strictly positive volumes for validity.
- **ex-VIN synthetic (see `vnindex_low_dist_ex_vin.py`):**  
  Approximate cap-weight decomposition: implied full cap `~ D * VNINDEX`, Vin basket cap from **close × quarterly shares** (forward-filled), `w_VIN = cap_VIN / cap_full_implied`, then `close_ex = VNINDEX * (1 - w_VIN)`, `vol_ex = vol_VNINDEX - sum(vol_VIN names)`. Calibrated to `artifacts/vnindex_ex_vin_result.json` snapshot.
- **Vin basket for this bundle:** **VIC, VHM, VRE** only (VPL excluded by project baseline doc).

Read `docs/research/VIN_EMA_CLOUD_BASELINE.md` for **disclosure rules** (VNINDEX cap-weight distortion 2025–2026, dual reporting).

---

## 3. Delivered baseline numbers (for you to validate / supersede)

See **`RESULTS_BASELINE.json`** in this folder. Summary:

- In window **2026-03-23 … 2026-05-14** (**L=36**): **3** distribution days on **both** full VNINDEX and ex-VIN rule (same dates: 2026-03-23, 2026-04-29, 2026-05-11).
- Under **≤ 1** dist / 36d on **full** VNINDEX: **no** sparse anchors in history (n=0) in the assistant’s run — **current regime is not in that bucket**.
- Under **≤ 3** dist / 36d (match observed density), sparse decorrelation 20 TD, exclude today as anchor: empirical **win-rates** (not calibrated P) are tabulated in JSON for horizons 25–250d for (full regime→full forward) and (ex-VIN regime→ex-VIN forward).

---

## 4. Known statistical / methodology weaknesses (you must address)

1. **Overlapping windows:** trailing-L regime labels are highly serially correlated; sparse subsampling is ad hoc.
2. **Regime threshold mismatch:** switching from ≤1 to ≤3 to match today **changes the hypothesis**; need explicit **hierarchical** reporting or **density matching** (e.g. match empirical dist-count distribution).
3. **No baseline:** win-rates vs unconditional or vs random-date control with same **horizon survival** (censoring at dataset end).
4. **Leakage risk:** any use of full-sample z-scores, tuned thresholds, or MA filters fit on the same 2012–asof slice without time-split.
5. **Multiple horizons / multiple specs:** multiplicity; report FDR or hold out a pure OOS period.
6. **ex-VIN is not traded:** forward returns on synthetic level ≠ implementable PnL; consider **breadth** or **equal-weight ex-VIN** robustness.
7. **Volume definition:** mixing index volume with stock sum-of-volume may not be strictly comparable.

---

## 5. What we want you to produce

1. **Replication checklist:** exact steps to reproduce baseline from this ZIP (or flag missing pieces).
2. **Methodology proposal v2:** e.g. marked point process for dist clusters, **hazard** / survival view for hitting ±X% by H, **conformal** or **block bootstrap** by year, **walk-forward** train/test for any tuned rule.
3. **Honest predictive summary:** point estimates + intervals; separate **in-sample descriptive** vs **OOS** claims.
4. **Minimal code diff:** patch files in `scripts/research/` or add one new module + tests; avoid duplicating entire repo.
5. **Optional:** if FireAnt is unavailable, document **fully offline** path using only CSVs in the bundle.

---

## 6. Files in this bundle (see `MANIFEST.md`)

Essential: `scripts/research/*.py`, `src/intake/fireant_historical.py`, `src/features/distribution_days.py`, `VNINDEX.csv`, `VIC/VHM/VRE` CSVs, `vin_basket_quarterly_shares.parquet`, `vnindex_ex_vin_result.json`, baseline doc, **`PROMPT_FOR_REVIEWER.md`** (this file), **`RESULTS_BASELINE.json`**.

---

## 7. Optional one-liner the owner can paste to start the other AI

> “Review the ZIP `vnindex_dist_methodology_handoff_2026-05-14.zip`: read `PROMPT_FOR_REVIEWER.md`, validate `RESULTS_BASELINE.json` against the code, then redesign the event-study + forward-return pipeline for VNINDEX and ex-VIN synthetic (VIC/VHM/VRE) with proper OOS, baselines, and uncertainty. Deliver patched Python and a short methods note.”

---

## 8. Phần tiếng Việt (tóm tắt cho chủ repo)

Gói này gồm **prompt đầy đủ** (mục 1–7), **kết quả baseline** (`RESULTS_BASELINE.json`), **mã nguồn** và **dữ liệu tối thiểu** để AI khác: (a) tái hiện, (b) chỉ ra lỗi thống kê / leakage, (c) đề xuất pipeline **dự báo / OOS** tốt hơn thay vì chỉ win-rate mô tả. File `vnindex_low_dist_ex_vin.py` trong ZIP đã trỏ `QUARTERLY_FA` tới parquet nhỏ `vin_basket_quarterly_shares.parquet` để không cần file FA 90MB.
