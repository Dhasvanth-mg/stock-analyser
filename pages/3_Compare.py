"""Stock Comparison — radar chart, metric cards, AI verdict."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv
from utils import inject_css, render_header, page_cfg, _CHART_BG

from data_fetcher import fetch_stock_batch, get_all_symbols
from ai_analyst import compare_stocks

load_dotenv()
page_cfg("Compare · NSE")
inject_css()
render_header("⚖️ Stock Comparison", "Multi-stock radar · AI picks the best")

with st.spinner("Loading stocks…"):
    df = fetch_stock_batch(get_all_symbols("All"))

if df.empty:
    st.error("No data."); st.stop()

left, right = st.columns([1, 2])

with left:
    st.markdown('<div class="section-hd">Pick Stocks (2–6)</div>', unsafe_allow_html=True)
    picks = st.multiselect("Stocks", df["Symbol"].tolist(),
                           default=df["Symbol"].tolist()[:4], max_selections=6,
                           label_visibility="collapsed")
    st.markdown('<div class="section-hd">Your Priority</div>', unsafe_allow_html=True)
    priorities = st.multiselect("Priority", ["Value (low P/E)","Growth (revenue)",
        "Dividend income","Low risk (beta)","Momentum (52W performance)","Large market cap"],
        default=["Value (low P/E)","Growth (revenue)"], label_visibility="collapsed")
    run_cmp = st.button("🤖 AI Pick the Best", use_container_width=True, type="primary")

with right:
    if len(picks) < 2:
        st.info("Select at least 2 stocks on the left."); st.stop()

    cmp_df = df[df["Symbol"].isin(picks)].copy()

    # Metric cards
    st.markdown('<div class="section-hd">At a Glance</div>', unsafe_allow_html=True)
    cols = st.columns(len(picks))
    _COLORS = ["#3b82f6","#10b981","#f59e0b","#ef4444","#8b5cf6","#ec4899"]
    for i, sym in enumerate(picks):
        r = cmp_df[cmp_df["Symbol"] == sym]
        if r.empty: continue
        r = r.iloc[0]
        chg_c = "#10b981" if r["Change %"] >= 0 else "#ef4444"
        with cols[i]:
            st.markdown(
                f"<div class='cmp-card' style='border-top-color:{_COLORS[i]}'>"
                f"<div class='cmp-sym'>{sym}</div>"
                f"<div class='cmp-cat'>{r['Cap Category']} · {r['Sector']}</div>"
                f"<div class='cmp-price'>₹{r['Price (₹)']:,.2f}</div>"
                f"<div style='color:{chg_c};font-size:.8rem;font-weight:700'>{r['Change %']:+.2f}%</div>"
                f"<hr style='border-color:#1e3450;margin:7px 0'>"
                f"<div class='cmp-row'>P/E <b>{r['P/E']:.1f}</b> · P/B <b>{r['P/B']:.2f}</b></div>"
                f"<div class='cmp-row'>EPS <b>₹{r['EPS']:.2f}</b></div>"
                f"<div class='cmp-row'>Rev <b>₹{r['Revenue (₹Cr)']:,.0f} Cr</b></div>"
                f"<div class='cmp-row'>Div <b>{r['Div Yield %']:.2f}%</b> · β <b>{r['Beta']:.2f}</b></div>"
                f"</div>", unsafe_allow_html=True)

    # Radar
    st.markdown('<div class="section-hd">Radar — 5 Dimensions</div>', unsafe_allow_html=True)

    def _norm(s):
        mn,mx=s.min(),s.max()
        return (s-mn)/(mx-mn)*100 if mx!=mn else pd.Series([50.0]*len(s), index=s.index)

    inv_pe  = cmp_df["P/E"].replace(0,float("nan")).apply(lambda x: 1/x if x else 0)
    inv_bet = cmp_df["Beta"].replace(0,float("nan")).apply(lambda x: 1/x if x else 0)
    hi,lo   = cmp_df["52W High"], cmp_df["52W Low"]
    mom     = (cmp_df["Price (₹)"]-lo)/((hi-lo).replace(0,float("nan")))*100

    cmp_df["_val"]  = _norm(inv_pe)
    cmp_df["_rev"]  = _norm(cmp_df["Revenue (₹Cr)"])
    cmp_df["_div"]  = _norm(cmp_df["Div Yield %"])
    cmp_df["_stab"] = _norm(inv_bet)
    cmp_df["_mom"]  = _norm(mom)
    DIM = ["Value","Revenue","Dividend","Stability","Momentum"]

    fig = go.Figure()
    for i, sym in enumerate(picks):
        r = cmp_df[cmp_df["Symbol"]==sym]
        if r.empty: continue
        r = r.iloc[0]
        vs = [r["_val"],r["_rev"],r["_div"],r["_stab"],r["_mom"]]
        rgb = f"{int(_COLORS[i][1:3],16)},{int(_COLORS[i][3:5],16)},{int(_COLORS[i][5:7],16)}"
        fig.add_trace(go.Scatterpolar(
            r=vs+[vs[0]], theta=DIM+[DIM[0]], name=sym, fill="toself",
            fillcolor=f"rgba({rgb},.12)", line=dict(color=_COLORS[i],width=2)))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True,range=[0,100],gridcolor="#1e3450",
                                   tickfont=dict(color="#64748b")),
                   angularaxis=dict(gridcolor="#1e3450",tickfont=dict(color="#94a3b8")),
                   bgcolor="#07111d"),
        paper_bgcolor="#07111d", template="plotly_dark", height=380,
        margin=dict(l=40,r=40,t=30,b=10),
        legend=dict(orientation="h",y=-0.05,font=dict(size=11)))
    st.plotly_chart(fig, use_container_width=True)

    # AI verdict
    if run_cmp and priorities:
        rows = cmp_df[cmp_df["Symbol"].isin(picks)].to_dict("records")
        with st.spinner("Groq is analysing…"):
            verdict = compare_stocks(rows, priorities)
        winner = next((s for s in picks if s in verdict[:70]), "")
        if winner:
            st.markdown(
                f"<div style='background:rgba(16,185,129,.12);border:1px solid rgba(16,185,129,.3);"
                f"border-radius:9px;padding:10px 16px;font-weight:700;color:#34d399;margin-bottom:10px'>"
                f"🏆 Best Pick: {winner}</div>", unsafe_allow_html=True)
        st.info(verdict)
