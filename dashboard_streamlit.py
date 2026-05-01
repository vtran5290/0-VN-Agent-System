"""Streamlit dashboard for VN Agent System artifacts.

Run:
    streamlit run dashboard_streamlit.py

Shows:
- Earnings sector heatmap (score 1–5)
- Council packet weekly summary
- Core weekly triggers/actions/risks
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

REPO = Path(__file__).resolve().parent
ARTIFACTS = REPO / "artifacts"
DATA_DECISION = REPO / "data" / "decision"
DATA_RESEARCH = REPO / "data" / "research"


def load_earnings_heatmap() -> pd.DataFrame:
    path = ARTIFACTS / "earnings_heatmap.csv"
    if not path.exists():
        return pd.DataFrame(columns=["sector", "score", "evidence", "watch"])
    return pd.read_csv(path)


def load_council_packet() -> dict:
    path = ARTIFACTS / "council_packet_weekly.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_weekly_core() -> dict:
    path = DATA_DECISION / "weekly_report.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_daily_top20_p20() -> pd.DataFrame:
    xlsx = DATA_RESEARCH / "daily_top20_stock_p20_2025-03_to_07_adv2bn.xlsx"
    csv = DATA_RESEARCH / "daily_top20_stock_p20_2025-03_to_07_adv2bn.csv"
    if xlsx.exists():
        df = pd.read_excel(xlsx)
    elif csv.exists():
        df = pd.read_csv(csv)
    else:
        return pd.DataFrame(
            columns=[
                "date",
                "symbol",
                "name",
                "exchange",
                "industryCode",
                "stock_p20",
                "p_now",
                "p_hist",
                "adv50_vnd",
                "close",
                "rank",
            ]
        )
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for c in ["stock_p20", "p_now", "p_hist", "adv50_vnd", "close", "rank"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["date", "symbol"]).sort_values(["date", "rank"]).reset_index(drop=True)


def render_p20_dashboard() -> None:
    st.subheader("Daily Top-20 Stock p20 (ADV50 >= 2B)")
    df = load_daily_top20_p20()
    if df.empty:
        st.info("No daily_top20_stock_p20_2025-03_to_07_adv2bn file found in data/research.")
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        min_d = df["date"].min().date()
        max_d = df["date"].max().date()
        start_d, end_d = st.date_input(
            "Date range",
            value=(min_d, max_d),
            min_value=min_d,
            max_value=max_d,
        )
    with c2:
        exchanges = ["All"] + sorted([x for x in df["exchange"].dropna().unique().tolist() if str(x).strip()])
        exchange = st.selectbox("Exchange", exchanges, index=0)
    with c3:
        symbols = sorted(df["symbol"].dropna().unique().tolist())
        sel_symbols = st.multiselect("Symbols (optional)", symbols, default=[])

    view = df[(df["date"] >= pd.Timestamp(start_d)) & (df["date"] <= pd.Timestamp(end_d))].copy()
    if exchange != "All":
        view = view[view["exchange"] == exchange]
    if sel_symbols:
        view = view[view["symbol"].isin(sel_symbols)]

    if view.empty:
        st.warning("No rows after filters.")
        return

    st.caption(f"Rows: {len(view):,} | Days: {view['date'].nunique()} | Symbols: {view['symbol'].nunique()}")
    st.dataframe(
        view.sort_values(["date", "rank"]),
        use_container_width=True,
        height=420,
    )

    left, right = st.columns(2)
    with left:
        st.markdown("**Average p20 by Date**")
        by_date = view.groupby("date", as_index=True)["stock_p20"].mean().sort_index()
        st.line_chart(by_date)
    with right:
        st.markdown("**Most Frequent Symbols in Top-20**")
        freq = (
            view.groupby("symbol", as_index=False)
            .size()
            .sort_values("size", ascending=False)
            .head(20)
            .rename(columns={"size": "appearances"})
        )
        st.dataframe(freq, use_container_width=True, height=360)

    st.markdown("**Top Symbols by Mean p20 (Filtered Window)**")
    top_mean = (
        view.groupby(["symbol", "exchange"], as_index=False)
        .agg(mean_p20=("stock_p20", "mean"), mean_rank=("rank", "mean"), n=("symbol", "size"))
        .sort_values(["mean_p20", "n"], ascending=[False, False])
        .head(30)
    )
    st.dataframe(top_mean, use_container_width=True, height=360)


def main() -> None:
    st.set_page_config(page_title="VN Agent Dashboard", layout="wide")
    st.title("VN Agent System — Weekly Dashboard")

    tab_weekly, tab_p20 = st.tabs(["Weekly Core", "Daily p20 Scanner"])

    with tab_weekly:
        col1, col2 = st.columns(2)

        # Earnings heatmap
        with col1:
            st.subheader("Earnings Heatmap (Sectors)")
            df = load_earnings_heatmap()
            if df.empty:
                st.info("No earnings_heatmap.csv yet. Run: make earnings-heatmap-apply")
            else:
                df_view = df.copy()
                df_view["score"] = df_view["score"].astype(float)
                st.dataframe(df_view, use_container_width=True)
                st.bar_chart(df_view.set_index("sector")["score"])

        # Council packet
        with col2:
            st.subheader("Council Packet — Weekly")
            cp = load_council_packet()
            if not cp:
                st.info("No council_packet_weekly.json yet. Run: make council-packet-v2")
            else:
                st.markdown(f"**As of week:** {cp.get('asof_week', 'unknown')}")
                er = cp.get("earnings_regime", {}) or {}
                st.markdown(f"**Earnings regime status:** {er.get('status', 'unknown')}")
                col21, col22 = st.columns(2)
                with col21:
                    st.markdown("**Leaders**")
                    st.write(er.get("leaders", []))
                with col22:
                    st.markdown("**Laggards**")
                    st.write(er.get("laggards", []))
                if cp.get("one_off_watchlist"):
                    st.markdown("**One-off / earnings-quality watchlist**")
                    st.write(cp["one_off_watchlist"])
                if cp.get("final_recommendation"):
                    st.markdown("**Final recommendation (Council)**")
                    st.write(cp["final_recommendation"])
                if cp.get("chair_decision"):
                    st.markdown("**Chair decision (executed)**")
                    st.write(cp["chair_decision"])
                if cp.get("conflicts"):
                    st.markdown("**Conflicts**")
                    st.write(cp["conflicts"])

        st.markdown("---")
        st.subheader("Core Weekly Triggers / Actions / Risks")
        core = load_weekly_core()
        if not core:
            st.info("No weekly_report.json yet. Run: make weekly")
        else:
            cols = st.columns(3)
            with cols[0]:
                st.markdown("**Triggers fired**")
                st.write(core.get("triggers_fired", []))
            with cols[1]:
                st.markdown("**Top actions**")
                st.write(core.get("actions", []))
            with cols[2]:
                st.markdown("**Top risks**")
                st.write(core.get("risks", []))

    with tab_p20:
        render_p20_dashboard()


if __name__ == "__main__":
    main()

