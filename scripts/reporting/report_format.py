"""Shared number formatting for weekly report (HTML + JSON display fields)."""
from __future__ import annotations

import math
import re
from typing import Any, Optional, Tuple, Union

Number = Union[int, float]

_MISSING_STRINGS = frozenset({"", "none", "nan", "null", "na", "n/a", "undefined"})


def is_missing(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return True
    if isinstance(v, str) and v.strip().lower() in _MISSING_STRINGS:
        return True
    return False


def coerce_display(v: Any) -> Any:
    """Normalize missing sentinels; return 'Missing' string or original value for formatting."""
    if is_missing(v):
        return "Missing"
    return v


def scan_price_kVND_to_vnd(v: Any) -> Optional[float]:
    """Phase36 scan prices (trail/tp1/pb) are in kVND; FireAnt holdings marks are VND."""
    if is_missing(v):
        return None
    try:
        return float(v) * 1000.0
    except (TypeError, ValueError):
        return None


def price_or_missing(v: Any) -> str:
    c = coerce_display(v)
    if c == "Missing":
        return "Missing"
    try:
        return f"{float(c):,.2f}"
    except (TypeError, ValueError):
        s = str(c).strip()
        return "Missing" if s.lower() in _MISSING_STRINGS else s


def cloud_label(v: Any) -> str:
    if is_missing(v):
        return "Missing"
    s = str(v).strip().lower()
    if s == "true":
        return "Bull"
    if s == "false":
        return "Bear"
    return "Missing"


def fmt_index(v: Any) -> str:
    if is_missing(v):
        return "Missing"
    return f"{float(v):,.1f}"


def fmt_pct(v: Any, decimals: int = 1) -> str:
    if is_missing(v):
        return "Missing"
    x = float(v)
    if -1.5 <= x <= 1.5 and abs(x) <= 1.0:
        x *= 100.0
    return f"{x:.{decimals}f}%"


def fmt_credit_growth(v: Any, decimals: int = 1) -> Tuple[str, Optional[str]]:
    """
    Format credit growth YoY with scale sanity.
    Returns (display, warning_or_none).
    """
    if is_missing(v):
        return "Missing", None
    x = float(v)
    warning = None
    if x > 50:
        disp = f"{x:.{decimals}f}%"
        warning = "Credit growth unusually high — verify manual_inputs scale"
    elif x >= 5:
        disp = f"{x:.{decimals}f}%"
    elif x > 0.35:
        disp = f"{x * 100:.{decimals}f}%"
        warning = "Credit growth >35% — verify if input is ratio vs percent"
    elif -1.5 <= x <= 1.5:
        disp = f"{x * 100:.{decimals}f}%"
        if x >= 0.99:
            warning = "Credit growth ~100% — verify manual_inputs scale (use percent e.g. 12.5 or ratio e.g. 0.125)"
    else:
        disp = f"{x:.{decimals}f}%"
    return disp, warning


def fmt_rate(v: Any) -> str:
    if is_missing(v):
        return "Missing"
    x = float(v)
    if -1.5 <= x <= 1.5 and abs(x) <= 1.0:
        x *= 100.0
    return f"{x:.2f}%"


def fmt_bps(v: Any) -> str:
    if is_missing(v):
        return "Missing"
    x = float(v)
    sign = "+" if x > 0 else ""
    return f"{sign}{x:.0f} bps"


def fmt_prob(v: Any, decimals: int = 0) -> str:
    if is_missing(v):
        return "Missing"
    x = float(v)
    if 0 <= x <= 1.0:
        x *= 100.0
    return f"{x:.{decimals}f}%"


def fmt_weight_pct(v: Any, decimals: int = 1) -> str:
    if is_missing(v):
        return "Missing"
    return f"{float(v):.{decimals}f}"


def fmt_score(v: Any, decimals: int = 1) -> str:
    if is_missing(v):
        return "Missing"
    return f"{float(v):.{decimals}f}"


def fmt_multiple(v: Any, decimals: int = 1) -> str:
    if is_missing(v):
        return "Missing"
    return f"{float(v):.{decimals}f}"


def fmt_omo_bn(v: Any) -> str:
    if is_missing(v):
        return "Missing"
    return f"{float(v):,.1f} bn"


def fmt_delta_display(v: Any, metric_id: str) -> str:
    if is_missing(v):
        return "Missing"
    x = float(v)
    mid = metric_id.upper()
    if "UST" in mid or "YIELD" in mid or "INTERBANK" in mid:
        return fmt_bps(x * 100 if abs(x) < 1 else x)
    if mid in ("VNINDEX", "VN30"):
        return fmt_index(x)
    if mid == "DXY":
        s = f"{x:+.2f}"
        return s
    if "DIST" in mid:
        return f"{x:+.0f}"
    if "CREDIT" in mid:
        return f"{x:+.2f} pp"
    return f"{x:+.2f}"


def direction_arrow(delta: Any) -> str:
    if is_missing(delta):
        return "—"
    x = float(delta)
    if x > 0:
        return "↑"
    if x < 0:
        return "↓"
    return "→"


def html_has_literal_none(html: str) -> bool:
    """Detect unsafe literal None/null/nan in visible table cells."""
    bad = re.compile(
        r'class="mono">(?:None|null|nan|NaN)</|>None</|>null</|>nan</',
        re.I,
    )
    return bool(bad.search(html))
