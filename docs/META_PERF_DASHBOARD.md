# Meta Performance Dashboard — Process × R × Regime

**Purpose:** Provide a compact, facts-first view of how well the trading process is executed, how the R-multiple edge behaves, and how it interacts with regimes — without changing core engine rules.

Outputs:

- `data/decision/meta_perf_YYYY-MM.json`
- `data/decision/meta_perf_latest.json`
- `data/decision/meta_perf_YYYY-MM.md` (when `--render`)
- `data/decision/meta_perf_latest.md` (when `--render`)

## Inputs

- `data/decision/trade_diagnostic_YYYY-MM.json` — summary_stats + patterns.
- `data/decision/trade_review_input.json` — per-trade risk + context.
- `data/decision/review_policy.json` — thresholds (min_sample_to_act, process_gate, meta_perf config).

If context fields are missing, dashboard still runs; affected buckets show under `"unknown"` and warnings are populated.

## data_quality

```json
"data_quality": {
  "process_gate_on": true,
  "manual_stop_gate_on": false,
  "interpret_with_caution": true,
  "r_coverage_rate": 0.75,
  "r_manual_share": 0.3,
  "caution_reasons": ["process_gate_on", "low_manual_stop_share"]
}
```

- `process_gate_on`: primary process gate from thresholds in `review_policy.process_gate`:
  - `stop_present_rate < stop_present_min` **hoặc**
  - `reason_tag_present_rate < reason_tag_present_min`.
- `manual_stop_gate_on`: secondary gate — bật khi stop_present & reason_tag đủ nhưng `stop_manual_rate < stop_manual_min`.
- `interpret_with_caution`: true nếu:
  - `process_gate_on` **hoặc**
  - `manual_stop_gate_on` **hoặc**
  - `r_coverage_rate < meta_perf.r_coverage_min` **hoặc**
  - `n_closed < min_sample_to_act`.
- `r_coverage_rate`: fraction of closed trades with non-null `r_multiple`.
- `r_manual_share`: share of R-trades whose `stop_source == "manual"`.
- `caution_reasons`: structured enums (subset của):
  - `"process_gate_on"`, `"manual_stop_gate_on"`,
  - `"low_r_coverage"`, `"low_sample"`, `"low_manual_stop_share"`.

## process_compliance

```json
"process_compliance": {
  "stop_present_rate": 0.9,
  "stop_manual_rate": 0.4,
  "reason_tag_present_rate": 0.7,
  "compliance_score": 78.5,
  "labels": {
    "stop_present": "GREEN",
    "stop_manual": "YELLOW",
    "reason_tag": "YELLOW",
    "overall": "YELLOW"
  }
}
```

- `stop_present_rate`: fraction of trades with a stop (manual or system_default).
- `stop_manual_rate`: fraction of trades with `stop_source == "manual"`.
- `reason_tag_present_rate`: fraction of trades where `reason_tag` is **not** `"unknown"`.
- `compliance_score`: weighted present-rate, default weights from `review_policy.meta_perf.weights`:
  - `stop_present`: 0.4
  - `stop_manual`: 0.2
  - `reason_tag`: 0.4

### Labels (RED/YELLOW/GREEN)

For each dimension:

- `missing_rate = 1 - present_rate`
- `RED` if `missing_rate ≥ missing_thresholds.red` (default 0.50)
- `YELLOW` if `missing_rate ≥ missing_thresholds.yellow` (default 0.20)
- `GREEN` otherwise.

`labels.overall` = worst of the three.

## edge_r_distribution

Computed over trades with non-null `risk.r_multiple`:

```json
"edge_r_distribution": {
  "n_closed": 20,
  "n_with_r": 18,
  "win_rate": 0.45,
  "avg_R": -0.12,
  "median_R": -0.08,
  "p25_R": -0.3,
  "p75_R": 0.2,
  "tail_R_min": -2.1,
  "tail_3_avg": -1.4
}
```

If `n_with_r` is small, warnings highlight limited R coverage.

### Dual edge: manual-only

```json
"edge_r_distribution_manual_only": {
  "note": "manual_only",
  "n_closed": 20,
  "n_with_r": 5,
  "win_rate": 0.4,
  "avg_R": 0.2,
  "median_R": 0.1,
  "p25_R": -0.1,
  "p75_R": 0.4,
  "tail_R_min": -0.8,
  "tail_3_avg": -0.5
}
```

- Chỉ tính trên trades có `stop_source == "manual"`.
- Nếu `n_with_r < 3` ⇒ các stats (win_rate, avg_R, tail…) để `null` và warnings chứa `"manual_only_edge_low_sample"`.

## regime_interaction

```json
"regime_interaction": {
  "by_regime_at_entry": {
    "B": {"n": 10, "n_with_r": 9, "avg_R": 0.1, "win_rate": 0.6},
    "unknown": {"n": 2, "n_with_r": 1, "avg_R": -0.5, "win_rate": 0.0}
  },
  "by_regime_at_entry_norm": { ... same as by_regime_at_entry ... },
  "by_regime_at_entry_raw": {
    "B": {"n": 12, "n_with_r": 11, "avg_R": 0.05, "win_rate": 0.5},
    "X": {"n": 1, "n_with_r": 1, "avg_R": -0.8, "win_rate": 0.0}
  },
  "by_risk_flag_at_entry": {
    "Normal": {"n": 11, "n_with_r": 10, "avg_R": 0.05, "win_rate": 0.5},
    "High": {"n": 1, "n_with_r": 1, "avg_R": -0.8, "win_rate": 0.0}
  },
  "by_dist_days_bucket_at_entry": {
    "0-2": {"n": 8, "n_with_r": 7, "avg_R": 0.12, "win_rate": 0.6},
    "3-4": {"n": 3, "n_with_r": 3, "avg_R": -0.3, "win_rate": 0.33},
    "5+": {"n": 1, "n_with_r": 1, "avg_R": -0.7, "win_rate": 0.0},
    "unknown": {"n": 1, "n_with_r": 1, "avg_R": 0.0, "win_rate": 0.0}
  }
}
```

Each group:

```json
"group_key": {
  "n": int,
  "n_with_r": int,
  "avg_R": number or null,
  "win_rate": number or null
}
```

## Top actions & watch_items

- `top_actions` (max 3): short, deterministic, facts-derived **objects**:

```json
{
  "priority": "P0",
  "type": "process",
  "metric": "reason_tag_present_rate",
  "current": 0.0,
  "target": 0.8,
  "deadline": "2026-03",
  "action": "Raise reason_tag_present_rate to ≥ 80% with controlled tags."
}
```

- Khi `process_gate_on` hoặc `manual_stop_gate_on` hoặc bất kỳ label RED/YELLOW:
  - Actions **chỉ** thuộc loại `type="process"` (stop/tag/compliance).
  - Có `current`, `target`, `deadline` (mặc định là **tháng kế tiếp** so với dashboard).
- Ngược lại:
  - 1 process action + 1 execution action + 1 risk action (facts-only).

- `top_actions_text`: mảng string (chỉ `action`), hỗ trợ backward-compat nếu cần đọc dạng text.
- `watch_items` (max 3):
  - Nhắc structured reasons (`caution_reasons`).
  - Cảnh báo khi `interpret_with_caution` true.
  - Cảnh báo khi `r_manual_share` thấp (R chủ yếu từ system_default stops).
  - Chỉ ra regime buckets có avg_R rất âm.

## Missing-data behavior

- Nếu `n_closed == 0`:
  - R metrics là null; `warnings` ghi rõ.
- Nếu `n_with_r == 0` nhưng `n_closed > 0`:
  - `edge_r_distribution` vẫn có, với coverage 0; warnings giải thích.
- Context thiếu:
  - Được bucket vào `"unknown"`; không crash.

