# CPP — Continuation Pocket Pivot

## Name

CPP (Continuation Pocket Pivot).

## Book references

- Gil 2010, Gil 2012 — PP trong uptrend đã establish.
- GIL_RULE_TAGS.md: CPP requires uptrend established.

## Intent

Entry: Pocket Pivot khi stock đã trong uptrend (đã có breakout/PP trước đó); tránh PP trong base chưa confirm.

## Inputs needed

- Same as PP + prior trend state (e.g. close > MA50, or prior breakout/PP flag).

## Binary logic (testable)

- PP conditions AND (uptrend established: e.g. `close > MA50` and/or `MA50_slope > 0`).
- "Uptrend established" cần định nghĩa cố định (pre-register).

## Default params

- Adaptation: "uptrend" = close > MA50 and MA50 slope > 0 (VN encode).

## Do NOTs

- Không invent thêm điều kiện uptrend ngoài sách (vd. không thêm RSI).

## Dependencies

- Depends on PP. Implement after PP weekly tested; code path: `signals_weekly.py` or daily `signals.py`.
