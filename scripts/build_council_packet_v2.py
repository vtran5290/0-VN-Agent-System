"""Build artifacts/council_packet_weekly.json from council_output + weekly_report + config (Earnings → Regime bridge)."""
from __future__ import annotations
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
COUNCIL = REPO / "data" / "decision" / "council_output.json"
WEEKLY_JSON = REPO / "data" / "decision" / "weekly_report.json"
ONE_OFF_CFG = REPO / "data" / "config" / "one_off_watchlist.yaml"
HEATMAP_PACK = REPO / "data" / "raw" / "earnings_heatmap_pack.json"
OUT = REPO / "artifacts" / "council_packet_weekly.json"


def _week_label(asof_date: str) -> str:
    """e.g. 2026-02-28 -> 2026-W09."""
    if not asof_date or len(asof_date) < 10:
        return asof_date or "unknown"
    from datetime import datetime
    try:
        d = datetime.strptime(asof_date[:10], "%Y-%m-%d")
        iso = d.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    except Exception:
        return asof_date[:7]


def main() -> None:
    packet = {
        "asof_week": None,
        "earnings_regime": {"status": "constructive", "leaders": [], "laggards": []},
        "top10_focus": [],
        "invalidators": [],
        "one_off_watchlist": [],
    }
    if COUNCIL.exists():
        council = json.loads(COUNCIL.read_text(encoding="utf-8"))
        packet["final_recommendation"] = council.get("final_recommendation")
        packet["conflicts"] = council.get("conflicts", [])
        packet["chair_decision"] = council.get("chair_decision")
        mid = council.get("meeting_id", "")
        if mid and "weekly" in mid:
            packet["asof_week"] = _week_label(mid.split("_")[0])
    if WEEKLY_JSON.exists():
        wr = json.loads(WEEKLY_JSON.read_text(encoding="utf-8"))
        packet["asof_week"] = packet["asof_week"] or _week_label(wr.get("asof_date", ""))
    if ONE_OFF_CFG.exists():
        import yaml
        with open(ONE_OFF_CFG, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        packet["one_off_watchlist"] = cfg.get("one_off_watchlist") or []
    if HEATMAP_PACK.exists():
        hm = json.loads(HEATMAP_PACK.read_text(encoding="utf-8"))
        heatmap = hm.get("heatmap", [])
        packet["earnings_regime"]["leaders"] = [r["sector"] for r in heatmap if (r.get("score") or 0) >= 4]
        packet["earnings_regime"]["laggards"] = [r["sector"] for r in heatmap if (r.get("score") or 5) < 3]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(packet, f, ensure_ascii=False, indent=2)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
