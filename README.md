## VN Relative Strength Engine (Vietnam Equities)

This project computes O'Neil/Minervini-style **benchmark-relative Relative Strength (RS)** for the Vietnam stock universe based on local CSV files, and exports ranked tables and watchlists for further discretionary work.

The focus is **leadership vs the VN market**, not just absolute price momentum.

---

### Folder structure

- **`data/stocks/`**: one CSV per ticker (e.g. `AAA.csv`, `ACB.csv`, `HPG.csv`, …)
- **`data/benchmark/`**: benchmark CSV (default `VNINDEX.csv`)
- **`output/`**: generated outputs (ranked tables, watchlists, RS time-series)
- **`src/`**:
  - `config.py`: central configuration object
  - `data_loader.py`: CSV loading, normalization, basic cleaning
  - `indicators.py`: moving averages, liquidity stats, 52-week stats
  - `filters.py`: VN-specific liquidity/price/history filters + trend flags
  - `rs_engine.py`: RS line, RS scores, cross-sectional ranking, leadership flags
  - `exporter.py`: writes CSV/Parquet outputs
  - `main.py`: CLI entrypoint (`python -m src.main`)

---

### Expected CSV schema

Assumed base format (per ticker in `data/stocks/` and benchmark in `data/benchmark/`):

- `date` (YYYY-MM-DD or similar, parsed with `pandas.to_datetime`)
- `open`
- `high`
- `low`
- `close`
- `volume`
- optionally `value` (traded value in VND)
- optionally adjusted close columns (`adj_close`, `adjusted_close`, or `adjclose`)

Rules:

- Column names are **normalized to lowercase**.
- `date` is parsed safely and rows with invalid dates are dropped.
- Data is sorted ascending by `date`, and duplicate dates are dropped.
- Missing `value` is back-filled as `close * volume`.
- If an adjusted close column is present it is preferred; otherwise `close` is used.

You can adapt to slightly different schemas by editing `data_loader.py`.

---

### How RS is defined

1. **Benchmark-relative RS line**

- For each stock and each aligned trading day:
  - \( \text{rs\_line} = \frac{\text{stock\_close}}{\text{benchmark\_close}} \)
- Only **overlapping dates** between stock and benchmark are used.

2. **Weighted RS score (from RS line, not price)**

- For lookback period \( n \) days:
  - \( \text{ROC}_n = \left(\frac{\text{rs\_line}}{\text{rs\_line}_{-n}} - 1\right) \times 100 \)
- RS score is a **weighted sum of these ROC values**.

#### Scoring modes

- **`tactical_vn`** (shorter-term focus)
  - 21d weight = 0.35
  - 63d weight = 0.35
  - 126d weight = 0.20
  - 189d weight = 0.10

- **`position_vn`** (longer-term focus)
  - 63d weight = 0.40
  - 126d weight = 0.25
  - 189d weight = 0.20
  - 252d weight = 0.15

3. **Cross-sectional RS percentile**

- On each date, across all stocks with a valid RS score:
  - `rs_percentile` = **percentile rank** of `rs_score` (0–100 scale).
- This is a **leadership ranking**, not a buy/sell signal.

---

### VN-specific filters and flags

Configured in `config.RSEngineConfig`:

- **Liquidity / price / history**
  - `min_price`: minimum last close price
  - `min_median_value_20d`: minimum 20-day median traded value (VND)
  - `min_avg_value_50d`: minimum 50-day average traded value (VND)
  - `min_history_days`: minimum history length (trading days)
  - `exclude_tickers`: optional list of tickers to skip

Derived flags (on latest date per stock):

- `liquidity_pass`
- `price_pass`
- `history_pass`
- `quality_universe_pass` = all the above pass and ticker not excluded

#### Trend / leadership template

Indicators:

- Simple moving averages:
  - `sma50`, `sma150`, `sma200` on close
- 52-week stats:
  - `high_252`, `low_252` on close

Flags:

- `above_sma50`, `above_sma150`, `above_sma200`
- `sma50_gt_sma150`, `sma150_gt_sma200`
- `sma200_rising_20d` (sma200 today > sma200 20 days ago)
- `near_52w_high` (close ≥ `near_high_threshold` × `high_252`, default 0.80)
- `off_52w_low` (close ≥ `off_low_threshold` × `low_252`, default 1.30)

Trend template:

- `trend_template` is `True` when **all** of:
  - close > sma50
  - close > sma150
  - close > sma200
  - sma50 > sma150
  - sma150 > sma200
  - sma200_rising_20d
  - near_52w_high
  - off_52w_low

RS leadership flags:

- `rs_new_high_252`: RS line at new 252-day high
- `rs_top_decile`: `rs_percentile` ≥ 90
- `leader_flag`:
  - `quality_universe_pass` **AND**
  - `trend_template` **AND**
  - `rs_top_decile`

---

### Configuration: where to edit first

Core settings live in `src/config.py` (`RSEngineConfig`):

- `benchmark_ticker`: e.g. `"VNINDEX"`
- `scoring_mode`: `"tactical_vn"` or `"position_vn"`
- `min_price`
- `min_median_value_20d`
- `min_avg_value_50d`
- `min_history_days`
- `near_high_threshold`
- `off_low_threshold`
- `exclude_tickers`
- directory paths are derived from the project root:
  - `data_stocks_dir = project_root / "data" / "stocks"`
  - `data_benchmark_dir = project_root / "data" / "benchmark"`
  - `output_dir = project_root / "output"`

You can either:

- edit these defaults in `config.py`, or
- override some of them via CLI flags (see below).

---

### How to install and run

From the project root:

```bash
pip install -r requirements.txt
```

Ensure your data directories are populated:

- `data/stocks/*.csv` for all VN tickers
- `data/benchmark/VNINDEX.csv` (or your chosen benchmark)

Then run:

```bash
python -m src.main
```

By default this uses:

- `benchmark_ticker="VNINDEX"`
- `scoring_mode="tactical_vn"`
- filter thresholds as defined in `config.py`.

#### CLI arguments

Examples:

```bash
python -m src.main --mode tactical_vn
python -m src.main --mode position_vn
python -m src.main --benchmark VNINDEX
python -m src.main --min-price 10000
python -m src.main --min-avg-value-50d 5000000000
python -m src.main --min-median-value-20d 2000000000
python -m src.main --min-history-days 260
```

CLI flags override the defaults from `config.py` **for that run only**.

---

### Outputs

All outputs are written to `output/`:

1. **`rs_full_latest.csv`**
   - One row per stock (latest date).
   - Key fields:
     - `ticker`, `date`, `close`, `volume`, `value`
     - `avg_value_20`, `avg_value_50`, `median_value_20`
     - `rs_line`, `rs_score`, `rs_percentile`
     - trend flags: `above_sma50`, `above_sma150`, `above_sma200`, `sma50_gt_sma150`,
       `sma150_gt_sma200`, `sma200_rising_20d`, `near_52w_high`, `off_52w_low`,
       `trend_template`
     - universe flags: `liquidity_pass`, `price_pass`, `history_pass`,
       `quality_universe_pass`
     - leadership flags: `rs_new_high_252`, `rs_top_decile`, `leader_flag`

2. **`rs_leaders_latest.csv`**
   - Subset of `rs_full_latest`:
     - `quality_universe_pass == True`
     - `rs_percentile >= 80`
   - Sorted by `rs_percentile` (desc), then `rs_score` (desc).
   - Use as a **broader RS leadership list**.

3. **`rs_top_decile_trend_template.csv`**
   - Subset where:
     - `quality_universe_pass == True`
     - `trend_template == True`
     - `rs_percentile >= 90`
   - This is a tighter **trend + RS leadership** focus list.

4. **`rs_timeseries.parquet`** (preferred; falls back to `rs_timeseries.csv` if Parquet fails)
   - Long-format RS panel:
     - `date`
     - `ticker`
     - `close`
     - `value`
     - `rs_line`
     - `rs_score`
     - `rs_percentile`
   - Use this for custom analytics, plotting, or additional screening.

---

### Conceptual guardrails

- **RS is a ranking / leadership measure**, not a trading signal by itself.
- RS is always computed **relative to the benchmark** via `rs_line`, not as raw price momentum.
- The pipeline keeps:
  - RS ranking logic (`rs_engine.py`)
  - trend/quality filters (`filters.py`, `indicators.py`)
  **separate**, so you can later layer:
  - sector-relative RS
  - pocket pivots
  - VCP patterns
  - earnings/fundamental overlays

No backtesting or entry/exit logic is included here; this is an **RS and leadership ranking tool** for the Vietnam market.

