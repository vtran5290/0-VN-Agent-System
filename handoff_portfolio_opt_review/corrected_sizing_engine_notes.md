# Corrected Sizing Engine — Design Notes
**Date:** 2026-05-16

---

## 1. Equal-weight (corrected)

```
position_weight = min(1 / max_open_positions, max_position_pct)
max_slots_from_pct = floor(max_total_exposure / position_weight)
effective_max_positions = min(max_open_positions, max_slots_from_pct)
```

Rules:
- position_weight is fixed per config, not dynamic
- Cash is idle if effective_max_positions × position_weight < max_total_exposure
- New entries accepted only if active_count < effective_max_positions

---

## 2. Rank-based sizing (corrected)

Step 1: Compute raw weight per position in the batch:
```
raw_w[i] = f(rank_pct[i])  # linear / top_heavy / sqrt
```

Step 2: Scale batch so sum ≤ max_total_exposure / max_open_positions × batch_size:
```
target_sum = min(1.0, batch_size / max_open_positions) * max_total_exposure
scale = min(1.0, target_sum / sum(raw_w)) if sum(raw_w) > 0 else 1.0
scaled_w[i] = raw_w[i] * scale
```

Step 3: Cap per position:
```
capped_w[i] = min(scaled_w[i], max_position_pct)
```

Step 4: Verify sum after capping:
```
assert sum(capped_w) <= max_total_exposure + 1e-9
```

This ensures no implicit leverage regardless of rank distribution or batch size.

---

## 3. Risk-per-trade (production design)

Phase 1D implements proper stop execution. Design:

```
weight = min(risk_pct / stop_distance, max_position_pct)

# Stop exit with T+5 lock:
for bar in range(entry_bar + 1, entry_bar + max_hold):
    if close[bar] <= entry_price * (1 - stop_distance):
        # Stop breached — record event
        if bar - entry_bar >= min_sell_lock_bars:
            exit at close[bar]  # execute immediately
        else:
            # Cannot exit yet — continue holding
            # Record: blocked_stop_event, locked_loss_increment
            # Re-check on each subsequent bar
            if close[bar] <= entry_price * (1 - stop_distance):
                continue  # still below stop
            else:
                # Price recovered; stop no longer breached
                pass  # continue normal exit logic
```

Two sub-modes:
- `stop_hard`: exit at first bar after min_sell_lock where stop is still breached
- `stop_soft`: re-exit only if stop still breached after sell-lock, else revert to TP/trail

---

## 4. max_total_exposure parameter

Add `max_total_exposure` (default 1.0) to all sizing functions.

Effect:
- equal_weight: reduces effective max positions if max_position_pct × max_open > max_total_exposure
- rank sizing: scale target_sum by max_total_exposure
- risk per trade: sum of active weights capped at max_total_exposure

Test grid values: 0.70, 0.85, 1.00

---

## 5. Drawdown guard (Phase 1C)

```
# At each bar, compute current portfolio drawdown from peak:
peak = max(equity_history)
current_dd = equity[bar] / peak - 1.0

# Adjust new-trade weight:
if current_dd <= -0.10:
    size_mult = 0.50
elif current_dd <= -0.15:
    size_mult = 0.25
elif current_dd <= -0.20:
    size_mult = 0.00  # block new entries
else:
    size_mult = 1.00

effective_weight = base_weight * size_mult
```

Tracking: record dd_guard_events count and bars blocked.
