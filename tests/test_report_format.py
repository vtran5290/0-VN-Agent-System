"""Tests for scripts.reporting.report_format."""
from scripts.reporting import report_format as rf


def test_fmt_index():
    assert rf.fmt_index(1921.6) == "1,921.6"
    assert rf.fmt_index(None) == "Missing"


def test_fmt_rate():
    assert rf.fmt_rate(4.47) == "4.47%"
    assert rf.fmt_rate(0.0605) == "6.05%"


def test_fmt_bps():
    assert rf.fmt_bps(20) == "+20 bps"
    assert rf.fmt_bps(-5) == "-5 bps"


def test_fmt_pct_decimal():
    assert rf.fmt_pct(0.55, 1) == "55.0%"


def test_fmt_prob():
    assert rf.fmt_prob(0.35, 0) == "35%"
