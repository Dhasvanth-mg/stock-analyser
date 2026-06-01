"""AI Analysis — Groq stock signal with chart, RSI, and news context."""

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from utils import inject_css, render_header, page_cfg, render_nav, candle_with_rsi

from data_fetcher import fetch_stock_batch, get_all_symbols, fetch_history
from ai_analyst import get_ai_analysis, get_portfolio_summary
from news_fetcher import get_news_summary

load_dotenv()
page_cfg("AI Analysis · NSE")
inject_css()
render_header("🤖 AI Analysis", "Groq llama-3.3-70b · Fundamentals + News Sentiment")
render_nav("pages/2_AI_Analysis.py")

# ── Sidebar: pick stock ───────────────────────────────────────────────────────
with st.sidebar:
    if "cap_filter" not in st.session_state:
        st.session_state["cap_filter"] = "Blue Chip"
    st.markdown("### CAP FILTER")
    _CAPS  = ["All","Blue Chip","Large Cap","Mid Cap","Small Cap"]
    _ICONS = {"All":"🌐","Blue Chip":"🔵","Large Cap":"🟢","Mid Cap":"🟡","Small Cap":"🔴"}
    for cap in _CAPS:
        if st.button(f"{_ICONS[cap]} {cap}", use_container_width=True,
                     type="primary" if st.session_state["cap_filter"]==cap else "secondary",
                     key=f"ai_cap_{cap}"):
            st.session_state["cap_filter"] = cap; st.rerun()

with st.spinner("Loading stocks…"):
    df = fetch_stock_batch(get_all_symbols(st.session_state["cap_filter"]))

if df.empty:
    st.error("No data."); st.stop()

left, right = st.columns([1, 2])

with left:
    st.markdown('<div class="section-hd">Select Stock</div>', unsafe_allow_html=True)
    ai_sym = st.selectbox("Stock", df["Symbol"].tolist(), label_visibility="collapsed")
    period = st.radio("Chart period", ["1mo","3mo","6mo","1y"], index=2, horizontal=True)
    run_ai = st.button("🤖 Analyse with Groq", use_container_width=True, type="primary")
    st.markdown("---")
    st.markdown('<div class="section-hd">Portfolio Summary</div>', unsafe_allow_html=True)
    watchlist = st.multiselect("Watchlist", df["Symbol"].tolist(),
                               default=df["Symbol"].tolist()[:5])
    run_port  = st.button("📊 Summarise Portfolio", use_container_width=True)

with right:
    # Chart always visible
    hist = fetch_history(ai_sym, period)
    if not hist.empty:
        st.plotly_chart(candle_with_rsi(hist, ai_sym, period),
                        use_container_width=True)

    if run_ai:
        row = df[df["Symbol"] == ai_sym].iloc[0].to_dict()
        with st.spinner(f"Fetching news + analysing {ai_sym}…"):
            ns       = get_news_summary(ai_sym)
            analysis = get_ai_analysis(row, news_summary=ns)

        sig = ("BUY" if "BUY" in analysis.upper()[:30]
               else "SELL" if "SELL" in analysis.upper()[:30] else "HOLD")
        bc  = {"BUY":"badge-buy","SELL":"badge-sell","HOLD":"badge-hold"}[sig]
        oc  = ns.get("overall", 0)
        nl  = ns.get("label", "")
        nc  = {"Positive":"#10b981","Negative":"#ef4444","Neutral":"#3b82f6"}.get(nl,"#3b82f6")
        nbg = {"Positive":"rgba(16,185,129,.12)","Negative":"rgba(239,68,68,.12)",
               "Neutral":"rgba(59,130,246,.12)"}.get(nl,"rgba(59,130,246,.12)")

        pill_row = st.columns([1, 3])
        pill_row[0].markdown(f'<span class="badge {bc}">{sig}</span>', unsafe_allow_html=True)
        if ns.get("count", 0):
            pill_row[1].markdown(
                f'<span style="background:{nbg};color:{nc};padding:3px 11px;border-radius:20px;'
                f'font-size:.73rem;font-weight:600;border:1px solid {nc}44">'
                f'📰 News: {nl} {oc:+.2f} · {ns["count"]} articles</span>',
                unsafe_allow_html=True)

        st.info(analysis)
        r = df[df["Symbol"] == ai_sym].iloc[0]
        m1,m2,m3,m4 = st.columns(4)
        m1.metric("Price",   f"₹{r['Price (₹)']}", f"{r['Change %']:+.2f}%")
        m2.metric("P/E",     f"{r['P/E']:.1f}")
        m3.metric("Mkt Cap", f"₹{r['Mkt Cap (₹Cr)']:,.0f} Cr")
        m4.metric("Revenue", f"₹{r['Revenue (₹Cr)']:,.0f} Cr")

    if run_port and watchlist:
        rows = df[df["Symbol"].isin(watchlist)].to_dict("records")
        with st.spinner("Generating portfolio summary…"):
            st.success(get_portfolio_summary(rows))

