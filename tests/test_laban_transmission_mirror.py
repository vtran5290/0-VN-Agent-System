import json
from pathlib import Path

from scripts.reporting.rate_pivot_transmission import normalize_transmission_contract

REPO = Path(__file__).resolve().parents[1]


def _contract() -> dict:
    monitor = json.loads((REPO / "data/research/rate_pivot_monitor.json").read_text(encoding="utf-8"))
    return normalize_transmission_contract(monitor)


def test_laban_mirror_renders_state_asof_hash():
    from scripts.reporting.laban_render import render_fx_transmission_mirror
    contract = _contract()
    html = render_fx_transmission_mirror(contract)
    assert "State 1" in html
    assert "Not confirmed" in html
    assert contract["as_of"] in html
    assert contract["evidence_hash"] in html
    assert "GT1 impact: monitoring only" in html


def test_builder_loads_transmission_after_engine_call():
    source = (REPO / "scripts/reporting/build_vn_structural_signals.py").read_text(encoding="utf-8")
    assert source.index("snapshot = run_engine(") < source.index("normalize_transmission_contract(")


def test_contract_never_enters_engine_inputs_or_decision_files():
    source = (REPO / "scripts/reporting/build_vn_structural_signals.py").read_text(encoding="utf-8")
    call = source.split("snapshot = run_engine(", 1)[1].split(")", 1)[0]
    assert "transmission" not in call
    for name in (
        "data/decision/laban_axis_state.json",
        "data/decision/vn_structural_signals.json",
        "data/decision/laban_scenarios.json",
    ):
        assert "fx_reserve_deposit_transmission" not in (REPO / name).read_text(encoding="utf-8")
