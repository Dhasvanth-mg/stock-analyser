"""News & Sentiment — per-stock and market-wide."""

import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv
from utils import inject_css, render_header, page_cfg, render_nav, _CHART_BG

from data_fetcher import fetch_stock_batch, get_all_symbols
from news_fetcher import get_news_summary, fetch_all_news, score_market_news

load_dotenv()
page_cfg("News & Sentiment · NSE")
inject_css()
render_header("📰 News & Sentiment",
              "Groww · Google News · Economic Times · Moneycontrol · Business Standard · LiveMint")
render_nav("pages/4_News.py")

with st.spinner("Loading stock list…"):
    df = fetch_stock_batch(get_all_symbols("Blue Chip"))

_SB = {
    "positive":'<span class="badge badge-pos">POS</span>',
    "negative":'<span class="badge badge-neg">NEG</span>',
    "neutral": '<span class="badge badge-neu">NEU</span>',
}
_SC = {"Groww":"#f59e0b","Google News":"#3b82f6","Economic Times":"#ef4444",
       "Moneycontrol":"#8b5cf6","Business Standard":"#06b6d4","LiveMint":"#10b981"}
_EC = {"optimism":"#10b981","greed":"#f59e0b","confidence":"#3b82f6",
       "fear":"#ef4444","panic":"#dc2626","uncertainty":"#94a3b8"}

left, right = st.columns([1, 2])

with left:
    st.markdown('<div class="section-hd">Per-Stock News</div>', unsafe_allow_html=True)
    news_sym = st.selectbox("Stock", df["Symbol"].tolist(), label_visibility="collapsed")
    run_news = st.button("🔍 Fetch & Score", use_container_width=True, type="primary")
    st.markdown("---")
    st.markdown('<div class="section-hd">Market-Wide Scan</div>', unsafe_allow_html=True)
    st.caption("Scores all stocks across all sources")
    run_mkt = st.button("🌐 Scan Market News", use_container_width=True)

with right:
    if run_news:
        name_row = df[df["Symbol"] == news_sym]
        cname    = name_row["Name"].iloc[0] if not name_row.empty else ""
        with st.spinner(f"Fetching & scoring news for {news_sym}…"):
            ns = get_news_summary(news_sym, cname)

        if ns["count"] == 0:
            st.warning(f"No recent news found for **{news_sym}**.")
        else:
            arts = ns["articles"]
            ov   = ns["overall"]
            oc   = "#10b981" if ov > .15 else ("#ef4444" if ov < -.15 else "#3b82f6")
            st.markdown(
                f"<div class='card card-accent-{'green' if ov>0 else 'red'}'>"
                f"<span style='font-size:1.1rem;font-weight:700;color:{oc}'>{ns['label']} Sentiment</span>"
                f"<span style='color:#64748b;font-size:.82rem;margin-left:10px'>"
                f"score {ov:+.3f} · {ns['count']} articles</span></div>",
                unsafe_allow_html=True)

            c1,c2,c3 = st.columns(3)
            c1.metric("Positive", ns["positive"])
            c2.metric("Neutral",  ns["neutral"])
            c3.metric("Negative", ns["negative"])

            ch1, ch2 = st.columns(2)
            with ch1:
                fig_d = go.Figure(go.Pie(
                    labels=["Positive","Neutral","Negative"],
                    values=[ns["positive"],ns["neutral"],ns["negative"]],
                    hole=.55, marker_colors=["#10b981","#3b82f6","#ef4444"],
                    textinfo="label+percent"))
                fig_d.update_layout(paper_bgcolor="#07111d",template="plotly_dark",
                    height=220,margin=dict(l=0,r=0,t=10,b=0),showlegend=False,
                    title=dict(text="Sentiment split",font=dict(color="#64748b",size=11)))
                st.plotly_chart(fig_d, use_container_width=True)
            with ch2:
                if "emotion" in arts.columns:
                    ec = arts["emotion"].value_counts().reset_index()
                    ec.columns = ["Emotion","Count"]
                    fig_e = go.Figure(go.Bar(x=ec["Emotion"],y=ec["Count"],
                        marker_color=[_EC.get(e,"#64748b") for e in ec["Emotion"]]))
                    fig_e.update_layout(paper_bgcolor="#07111d",plot_bgcolor="#07111d",
                        template="plotly_dark",height=220,margin=dict(l=0,r=0,t=10,b=0),
                        title=dict(text="Emotion",font=dict(color="#64748b",size=11)))
                    st.plotly_chart(fig_e, use_container_width=True)

            st.markdown(f'<div class="section-hd">{ns["count"]} Articles</div>',
                        unsafe_allow_html=True)
            for _, a in arts.iterrows():
                badge = _SB.get(a.get("sentiment","neutral"), _SB["neutral"])
                src   = a.get("source","")
                sc    = _SC.get(src,"#64748b")
                url   = a.get("url","")
                txt   = a.get("title","")[:220]
                t_html = (f'<a href="{url}" target="_blank" style="color:#e2e8f0;'
                          f'text-decoration:none">{txt}</a>' if url else
                          f'<span style="color:#e2e8f0">{txt}</span>')
                st.markdown(
                    f"<div class='article-card'>{badge} "
                    f"<span class='src-pill' style='background:{sc}22;color:{sc};"
                    f"border-color:{sc}44'>{src}</span> "
                    f"<span style='color:#64748b;font-size:.75rem'>{a.get('date','')} · "
                    f"{str(a.get('emotion','')).capitalize()}</span><br>"
                    f"<span style='font-size:.85rem'>{t_html}</span></div>",
                    unsafe_allow_html=True)

    if run_mkt:
        prog = st.progress(0, "Fetching from all sources…")
        with st.spinner("Scoring market news…"):
            prog.progress(30)
            scored = score_market_news(pages=6)
            prog.progress(100); prog.empty()

        if scored.empty:
            st.warning("Could not reach news sources.")
        else:
            cnts   = scored["ticker"].value_counts()
            top_t  = cnts[cnts >= 2].head(25).index.tolist()
            cdf    = scored[scored["ticker"].isin(top_t)]
            sagg   = cdf.groupby(["ticker","sentiment"]).size().unstack(fill_value=0).reset_index()
            for c in ["positive","neutral","negative"]:
                if c not in sagg.columns: sagg[c] = 0
            sagg   = sagg.sort_values(sagg.get("positive", pd.Series(dtype=int)).name
                                      if "positive" in sagg.columns else "ticker",
                                      ascending=False)

            import pandas as _pd
            sagg["net"] = sagg.get("positive",0) - sagg.get("negative",0)
            sagg = sagg.sort_values("net", ascending=False)

            fig_m = go.Figure()
            for sent, col in [("positive","#10b981"),("neutral","#3b82f6"),("negative","#ef4444")]:
                if sent in sagg.columns:
                    fig_m.add_trace(go.Bar(x=sagg["ticker"],y=sagg[sent],
                                           name=sent.capitalize(),marker_color=col))
            fig_m.update_layout(barmode="stack",template="plotly_dark",
                paper_bgcolor="#07111d",plot_bgcolor="#07111d",height=400,
                margin=dict(l=0,r=0,t=30,b=0),
                title=dict(text="Market Sentiment (sorted by net positive)",
                           font=dict(color="#94a3b8")),
                xaxis=dict(tickangle=-40,tickfont=dict(color="#94a3b8")),
                yaxis=dict(tickfont=dict(color="#94a3b8")),
                legend=dict(orientation="h",y=1.08))
            st.plotly_chart(fig_m, use_container_width=True)
            st.caption(f"{len(scored)} articles · {scored['ticker'].nunique()} stocks "
                       f"· {scored['source'].nunique()} sources")

    if not run_news and not run_mkt:
        st.markdown(
            "<div style='text-align:center;color:#1e3450;padding:80px 0'>"
            "Pick a stock and click Fetch & Score, or scan market-wide news</div>",
            unsafe_allow_html=True)

