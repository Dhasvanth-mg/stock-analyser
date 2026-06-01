"""
NSE Stock Analyser — Streamlit App
Filters: Blue Chip / Large Cap / Mid Cap / Small Cap / All
Sliders: Price range, Revenue range, Market Cap range
AI: Groq llama3-70b analysis per stock
"""

import json
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from dotenv import load_dotenv

from data_fetcher import (
    fetch_stock_batch, fetch_history,
    get_all_symbols, load_universe,
)
from ai_analyst import get_ai_analysis, get_portfolio_summary, compare_stocks
from news_fetcher import get_news_summary, fetch_all_news, score_market_news

load_dotenv()

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="NSE Stock Analyser",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Main gradient header */
    .main-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        border-left: 4px solid #e94560;
    }
    .main-header h1 { color: #fff; margin: 0; font-size: 1.8rem; }
    .main-header p  { color: #a0aec0; margin: 4px 0 0 0; font-size: 0.9rem; }

    /* Metric cards */
    .metric-card {
        background: #1e293b;
        border-radius: 10px;
        padding: 1rem 1.2rem;
        border-left: 3px solid #3b82f6;
        margin-bottom: 0.5rem;
    }
    .metric-card.green { border-left-color: #22c55e; }
    .metric-card.red   { border-left-color: #ef4444; }
    .metric-card.gold  { border-left-color: #f59e0b; }

    /* Signal badges */
    .badge-buy  { background:#166534; color:#bbf7d0; padding:3px 10px; border-radius:20px; font-size:0.8rem; font-weight:600; }
    .badge-sell { background:#7f1d1d; color:#fecaca; padding:3px 10px; border-radius:20px; font-size:0.8rem; font-weight:600; }
    .badge-hold { background:#78350f; color:#fde68a; padding:3px 10px; border-radius:20px; font-size:0.8rem; font-weight:600; }

    /* Cap filter pills */
    div[data-testid="stRadio"] label { cursor: pointer; }

    /* Table tweaks */
    .dataframe thead th { background: #1e293b !important; color: #94a3b8 !important; }

    /* Sidebar */
    section[data-testid="stSidebar"] { background: #0f172a; }
    section[data-testid="stSidebar"] .stMarkdown { color: #94a3b8; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>📈 NSE Stock Analyser</h1>
    <p>Live data from National Stock Exchange · AI-powered insights via Groq</p>
</div>
""", unsafe_allow_html=True)

# ── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔍 Filters")

    # Cap category
    cap_filter = st.radio(
        "Market Cap Category",
        ["All", "Blue Chip", "Large Cap", "Mid Cap", "Small Cap"],
        index=0,
    )

    st.markdown("---")

    # Sector filter (populated after data load)
    sector_placeholder = st.empty()

    st.markdown("---")
    st.markdown("### 📊 Range Sliders")

    price_range = st.slider(
        "Stock Price (₹)",
        min_value=0, max_value=50000,
        value=(0, 50000), step=100,
    )

    rev_range = st.slider(
        "Revenue (₹ Cr)",
        min_value=0, max_value=500000,
        value=(0, 500000), step=1000,
    )

    mktcap_range = st.slider(
        "Market Cap (₹ Cr)",
        min_value=0, max_value=2000000,
        value=(0, 2000000), step=5000,
    )

    pe_range = st.slider(
        "P/E Ratio",
        min_value=0.0, max_value=200.0,
        value=(0.0, 200.0), step=1.0,
    )

    st.markdown("---")
    st.markdown("### ⚙️ Display")
    sort_col = st.selectbox(
        "Sort by",
        ["Mkt Cap (₹Cr)", "Price (₹)", "Change %", "Revenue (₹Cr)", "P/E", "EPS"],
    )
    sort_asc = st.checkbox("Ascending", value=False)
    max_rows  = st.slider("Max rows", 10, 500, 100, step=10)

    st.markdown("---")
    refresh = st.button("🔄 Refresh Data", use_container_width=True)
    if refresh:
        st.cache_data.clear()

# ── Load data ─────────────────────────────────────────────────────────────────
symbols = get_all_symbols(cap_filter)

with st.spinner(f"Loading {len(symbols)} stocks…"):
    df = fetch_stock_batch(symbols)

if df.empty:
    st.error("Could not fetch any stock data. Check your internet connection.")
    st.stop()

# Sector filter (now we have data)
all_sectors = sorted(df["Sector"].dropna().unique().tolist())
selected_sectors = sector_placeholder.multiselect(
    "Sectors", all_sectors, default=all_sectors
)

# ── Apply filters ─────────────────────────────────────────────────────────────
mask = (
    df["Price (₹)"].between(*price_range) &
    df["Revenue (₹Cr)"].between(*rev_range) &
    df["Mkt Cap (₹Cr)"].between(*mktcap_range) &
    df["P/E"].between(*pe_range) &
    df["Sector"].isin(selected_sectors)
)
filtered = df[mask].copy()

# Sort
filtered = filtered.sort_values(sort_col, ascending=sort_asc).head(max_rows)

# ── Summary metrics row ───────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.metric("Stocks shown", len(filtered), f"of {len(df)}")
with c2:
    avg_pe = filtered["P/E"].replace(0, pd.NA).mean()
    st.metric("Avg P/E", f"{avg_pe:.1f}" if pd.notna(avg_pe) else "—")
with c3:
    gainers = (filtered["Change %"] > 0).sum()
    st.metric("Gainers", gainers, f"{gainers/len(filtered)*100:.0f}%" if len(filtered) else "—")
with c4:
    losers = (filtered["Change %"] < 0).sum()
    st.metric("Losers", losers)
with c5:
    total_mcap = filtered["Mkt Cap (₹Cr)"].sum()
    st.metric("Total Mkt Cap", f"₹{total_mcap/1e5:.1f}L Cr" if total_mcap else "—")

st.markdown("---")

# ── Main tabs ─────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📋 Screener", "📈 Chart", "🤖 AI Analysis", "⚖️ Compare", "📰 News & Sentiment", "🗂️ Heatmap"])

# ── TAB 1: Screener table ─────────────────────────────────────────────────────
with tab1:
    st.markdown(f"#### Showing {len(filtered)} stocks · sorted by {sort_col}")

    display_cols = [
        "Symbol", "Name", "Cap Category", "Sector",
        "Price (₹)", "Change %", "Mkt Cap (₹Cr)", "Revenue (₹Cr)",
        "P/E", "P/B", "EPS", "Div Yield %", "Beta",
        "52W High", "52W Low", "Volume",
    ]
    display_df = filtered[display_cols].reset_index(drop=True)

    def color_change(val):
        if isinstance(val, float):
            color = "#22c55e" if val > 0 else ("#ef4444" if val < 0 else "#94a3b8")
            return f"color: {color}; font-weight: 600"
        return ""

    def color_cap(val):
        colors = {
            "Blue Chip": "background-color: #1e3a5f; color: #93c5fd",
            "Large Cap": "background-color: #1e3a2e; color: #86efac",
            "Mid Cap":   "background-color: #3b2d1f; color: #fcd34d",
            "Small Cap": "background-color: #3b1f1f; color: #fca5a5",
        }
        return colors.get(val, "")

    styled = (
        display_df.style
        .applymap(color_change, subset=["Change %"])
        .applymap(color_cap, subset=["Cap Category"])
        .format({
            "Price (₹)":     "₹{:.2f}",
            "Change %":      "{:+.2f}%",
            "Mkt Cap (₹Cr)": "₹{:,.0f}",
            "Revenue (₹Cr)": "₹{:,.0f}",
            "P/E":           "{:.1f}",
            "P/B":           "{:.2f}",
            "EPS":           "₹{:.2f}",
            "Div Yield %":   "{:.2f}%",
            "52W High":      "₹{:.2f}",
            "52W Low":       "₹{:.2f}",
            "Volume":        "{:,}",
        })
        .set_properties(**{"background-color": "#0f172a", "color": "#e2e8f0"})
    )

    st.dataframe(styled, use_container_width=True, height=520)

    csv = display_df.to_csv(index=False)
    st.download_button("⬇️ Export CSV", csv, "nse_stocks.csv", "text/csv")

# ── TAB 2: Chart ──────────────────────────────────────────────────────────────
with tab2:
    col_a, col_b = st.columns([1, 3])
    with col_a:
        chart_sym = st.selectbox("Select Stock", filtered["Symbol"].tolist())
        chart_period = st.radio("Period", ["1mo", "3mo", "6mo", "1y", "2y"], index=2)

    with col_b:
        with st.spinner(f"Loading {chart_sym} history…"):
            hist = fetch_history(chart_sym, chart_period)

        if not hist.empty:
            fig = go.Figure()

            # Candlestick
            fig.add_trace(go.Candlestick(
                x=hist.index,
                open=hist["Open"], high=hist["High"],
                low=hist["Low"],  close=hist["Close"],
                name=chart_sym,
                increasing_line_color="#22c55e",
                decreasing_line_color="#ef4444",
            ))

            # SMA 20 & 50
            hist["SMA20"] = hist["Close"].rolling(20).mean()
            hist["SMA50"] = hist["Close"].rolling(50).mean()
            fig.add_trace(go.Scatter(x=hist.index, y=hist["SMA20"], name="SMA 20",
                                     line=dict(color="#60a5fa", width=1.5)))
            fig.add_trace(go.Scatter(x=hist.index, y=hist["SMA50"], name="SMA 50",
                                     line=dict(color="#f59e0b", width=1.5)))

            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="#0f172a",
                plot_bgcolor="#0f172a",
                height=480,
                margin=dict(l=0, r=0, t=30, b=0),
                title=f"{chart_sym} · {chart_period}",
                xaxis_rangeslider_visible=False,
                legend=dict(orientation="h", y=1.02),
            )
            st.plotly_chart(fig, use_container_width=True)

            # Volume bar
            fig2 = go.Figure(go.Bar(
                x=hist.index, y=hist["Volume"],
                marker_color="#3b82f6", name="Volume"
            ))
            fig2.update_layout(
                template="plotly_dark", paper_bgcolor="#0f172a",
                plot_bgcolor="#0f172a", height=150,
                margin=dict(l=0, r=0, t=10, b=0),
                showlegend=False,
            )
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.warning(f"No history found for {chart_sym}")

# ── TAB 3: AI Analysis ────────────────────────────────────────────────────────
with tab3:
    st.markdown("#### Groq llama-3.3-70b · Stock Analysis")

    ai_col1, ai_col2 = st.columns([1, 2])

    with ai_col1:
        ai_sym = st.selectbox("Pick a stock", filtered["Symbol"].tolist(), key="ai_sym")
        ai_period = st.radio("Chart period", ["1mo", "3mo", "6mo", "1y"], index=2, horizontal=True)
        run_ai = st.button("🤖 Analyse", use_container_width=True)

        st.markdown("---")
        st.markdown("**Portfolio Summary**")
        watchlist = st.multiselect(
            "Add stocks to watchlist",
            filtered["Symbol"].tolist(),
            default=filtered["Symbol"].tolist()[:5],
        )
        run_portfolio = st.button("📊 Summarise Portfolio", use_container_width=True)

    with ai_col2:
        # Always show the price chart for selected stock
        with st.spinner(f"Loading {ai_sym} chart…"):
            ai_hist = fetch_history(ai_sym, ai_period)

        if not ai_hist.empty:
            ai_hist["SMA20"] = ai_hist["Close"].rolling(20).mean()
            ai_hist["SMA50"] = ai_hist["Close"].rolling(50).mean()

            # RSI
            delta = ai_hist["Close"].diff()
            gain  = delta.where(delta > 0, 0).rolling(14).mean()
            loss  = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs    = gain / loss.replace(0, float("nan"))
            ai_hist["RSI"] = 100 - (100 / (1 + rs))

            from plotly.subplots import make_subplots
            fig_ai = make_subplots(
                rows=2, cols=1,
                shared_xaxes=True,
                row_heights=[0.7, 0.3],
                vertical_spacing=0.04,
            )

            # Price + SMAs
            fig_ai.add_trace(go.Candlestick(
                x=ai_hist.index,
                open=ai_hist["Open"], high=ai_hist["High"],
                low=ai_hist["Low"],  close=ai_hist["Close"],
                name=ai_sym,
                increasing_line_color="#22c55e",
                decreasing_line_color="#ef4444",
            ), row=1, col=1)
            fig_ai.add_trace(go.Scatter(
                x=ai_hist.index, y=ai_hist["SMA20"],
                name="SMA 20", line=dict(color="#60a5fa", width=1.5)
            ), row=1, col=1)
            fig_ai.add_trace(go.Scatter(
                x=ai_hist.index, y=ai_hist["SMA50"],
                name="SMA 50", line=dict(color="#f59e0b", width=1.5)
            ), row=1, col=1)

            # RSI
            fig_ai.add_trace(go.Scatter(
                x=ai_hist.index, y=ai_hist["RSI"],
                name="RSI", line=dict(color="#a78bfa", width=1.5), fill="tozeroy",
                fillcolor="rgba(167,139,250,0.1)"
            ), row=2, col=1)
            fig_ai.add_hline(y=70, line_dash="dash", line_color="#ef4444", line_width=1, row=2, col=1)
            fig_ai.add_hline(y=30, line_dash="dash", line_color="#22c55e", line_width=1, row=2, col=1)

            fig_ai.update_layout(
                template="plotly_dark",
                paper_bgcolor="#0f172a",
                plot_bgcolor="#0f172a",
                height=420,
                margin=dict(l=0, r=0, t=30, b=0),
                xaxis_rangeslider_visible=False,
                legend=dict(orientation="h", y=1.04, font=dict(size=11)),
                title=dict(text=f"{ai_sym} · Price & RSI", font=dict(color="#94a3b8", size=13)),
            )
            fig_ai.update_yaxes(title_text="Price (₹)", row=1, col=1)
            fig_ai.update_yaxes(title_text="RSI", row=2, col=1, range=[0, 100])
            st.plotly_chart(fig_ai, use_container_width=True)

        if run_ai:
            stock_row = filtered[filtered["Symbol"] == ai_sym].iloc[0].to_dict()
            with st.spinner(f"Fetching news & analysing {ai_sym} with Groq…"):
                news_ctx  = get_news_summary(ai_sym)
                analysis  = get_ai_analysis(stock_row, news_summary=news_ctx)

            # Extract signal for badge
            sig = "HOLD"
            if "BUY"  in analysis.upper()[:30]: sig = "BUY"
            if "SELL" in analysis.upper()[:30]: sig = "SELL"
            badge_cls = {"BUY":"badge-buy","SELL":"badge-sell","HOLD":"badge-hold"}[sig]

            # Signal + news sentiment pill side by side
            news_label = news_ctx.get("label", "")
            news_score = news_ctx.get("overall", 0)
            news_count = news_ctx.get("count", 0)
            news_color = {"Positive":"#166534","Negative":"#7f1d1d","Neutral":"#1e3a5f"}.get(news_label, "#1e3a5f")
            news_txt_color = {"Positive":"#bbf7d0","Negative":"#fecaca","Neutral":"#bfdbfe"}.get(news_label, "#bfdbfe")

            col_sig, col_news = st.columns([1, 2])
            with col_sig:
                st.markdown(f'<span class="{badge_cls}">{sig}</span>', unsafe_allow_html=True)
            with col_news:
                if news_count:
                    st.markdown(
                        f'<span style="background:{news_color};color:{news_txt_color};'
                        f'padding:3px 10px;border-radius:20px;font-size:0.8rem;font-weight:600">'
                        f'News: {news_label} ({news_score:+.2f}) · {news_count} articles</span>',
                        unsafe_allow_html=True,
                    )
            st.markdown("")
            st.info(analysis)

            # Quick metrics
            row = filtered[filtered["Symbol"] == ai_sym].iloc[0]
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Price",   f"₹{row['Price (₹)']}", f"{row['Change %']:+.2f}%")
            m2.metric("P/E",     f"{row['P/E']:.1f}")
            m3.metric("Mkt Cap", f"₹{row['Mkt Cap (₹Cr)']:,.0f} Cr")
            m4.metric("Revenue", f"₹{row['Revenue (₹Cr)']:,.0f} Cr")

        if run_portfolio and watchlist:
            rows = filtered[filtered["Symbol"].isin(watchlist)].to_dict("records")
            with st.spinner("Generating portfolio summary…"):
                summary = get_portfolio_summary(rows)
            st.success(summary)

# ── TAB 4: Compare ───────────────────────────────────────────────────────────
with tab4:
    st.markdown("#### ⚖️ Stock Comparison & AI Picker")

    cmp_left, cmp_right = st.columns([1, 2])

    with cmp_left:
        st.markdown("**Pick stocks to compare**")
        cmp_stocks = st.multiselect(
            "Select 2–6 stocks",
            filtered["Symbol"].tolist(),
            default=filtered["Symbol"].tolist()[:4],
            max_selections=6,
        )

        st.markdown("**Your investment priority**")
        priorities = st.multiselect(
            "What matters most?",
            ["Value (low P/E)", "Growth (revenue)", "Dividend income",
             "Low risk (beta)", "Momentum (52W performance)", "Large market cap"],
            default=["Value (low P/E)", "Growth (revenue)"],
        )

        run_compare = st.button("🤖 AI Pick the Best", use_container_width=True, type="primary")

    with cmp_right:
        if len(cmp_stocks) < 2:
            st.info("Select at least 2 stocks to compare.")
        else:
            cmp_df = filtered[filtered["Symbol"].isin(cmp_stocks)].copy()

            # ── Side-by-side metric cards ─────────────────────────────────
            st.markdown("**Metrics at a glance**")
            cols = st.columns(len(cmp_stocks))
            for i, sym in enumerate(cmp_stocks):
                row = cmp_df[cmp_df["Symbol"] == sym]
                if row.empty:
                    continue
                r = row.iloc[0]
                chg_color = "#22c55e" if r["Change %"] >= 0 else "#ef4444"
                with cols[i]:
                    st.markdown(f"""
                    <div style="background:#1e293b;border-radius:10px;padding:12px;
                                border-top:3px solid #3b82f6;text-align:center">
                        <div style="font-size:1.1rem;font-weight:700;color:#f1f5f9">{sym}</div>
                        <div style="font-size:0.75rem;color:#64748b;margin-bottom:6px">
                            {r['Cap Category']} · {r['Sector']}
                        </div>
                        <div style="font-size:1.4rem;font-weight:700;color:#f1f5f9">₹{r['Price (₹)']:,.2f}</div>
                        <div style="color:{chg_color};font-size:0.85rem;font-weight:600">
                            {r['Change %']:+.2f}%
                        </div>
                        <hr style="border-color:#334155;margin:8px 0">
                        <div style="font-size:0.8rem;color:#94a3b8">
                            P/E <b style="color:#f1f5f9">{r['P/E']:.1f}</b> &nbsp;|&nbsp;
                            P/B <b style="color:#f1f5f9">{r['P/B']:.2f}</b><br>
                            EPS <b style="color:#f1f5f9">₹{r['EPS']:.2f}</b><br>
                            Rev <b style="color:#f1f5f9">₹{r['Revenue (₹Cr)']:,.0f}Cr</b><br>
                            Div <b style="color:#f1f5f9">{r['Div Yield %']:.2f}%</b> &nbsp;|&nbsp;
                            β <b style="color:#f1f5f9">{r['Beta']:.2f}</b>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

            st.markdown("")

            # ── Radar chart ───────────────────────────────────────────────
            st.markdown("**Multi-dimensional radar**")

            radar_metrics = ["Value", "Revenue", "Dividend", "Stability", "Momentum"]

            def normalize(series):
                mn, mx = series.min(), series.max()
                if mx == mn:
                    return pd.Series([50.0] * len(series), index=series.index)
                return (series - mn) / (mx - mn) * 100

            # Value = inverse P/E (lower P/E → higher score)
            inv_pe = cmp_df["P/E"].replace(0, float("nan")).apply(lambda x: 1/x if x else 0)
            cmp_df["_value"]    = normalize(inv_pe)
            cmp_df["_revenue"]  = normalize(cmp_df["Revenue (₹Cr)"])
            cmp_df["_dividend"] = normalize(cmp_df["Div Yield %"])
            # Stability = inverse beta
            inv_beta = cmp_df["Beta"].replace(0, float("nan")).apply(lambda x: 1/x if x else 0)
            cmp_df["_stability"] = normalize(inv_beta)
            # Momentum = position in 52W range
            hi, lo = cmp_df["52W High"], cmp_df["52W Low"]
            cmp_df["_momentum"] = normalize(
                (cmp_df["Price (₹)"] - lo) / (hi - lo).replace(0, float("nan")) * 100
            )

            fig_radar = go.Figure()
            colors = ["#3b82f6","#22c55e","#f59e0b","#ef4444","#a78bfa","#ec4899"]

            for i, sym in enumerate(cmp_stocks):
                row = cmp_df[cmp_df["Symbol"] == sym]
                if row.empty:
                    continue
                r = row.iloc[0]
                vals = [
                    r["_value"], r["_revenue"], r["_dividend"],
                    r["_stability"], r["_momentum"]
                ]
                fig_radar.add_trace(go.Scatterpolar(
                    r=vals + [vals[0]],
                    theta=radar_metrics + [radar_metrics[0]],
                    name=sym,
                    fill="toself",
                    fillcolor=f"rgba({int(colors[i][1:3],16)},{int(colors[i][3:5],16)},{int(colors[i][5:7],16)},0.15)",
                    line=dict(color=colors[i], width=2),
                ))

            fig_radar.update_layout(
                polar=dict(
                    radialaxis=dict(visible=True, range=[0, 100],
                                    gridcolor="#334155", tickfont=dict(color="#64748b")),
                    angularaxis=dict(gridcolor="#334155", tickfont=dict(color="#94a3b8")),
                    bgcolor="#0f172a",
                ),
                paper_bgcolor="#0f172a",
                template="plotly_dark",
                height=380,
                margin=dict(l=40, r=40, t=40, b=20),
                legend=dict(orientation="h", y=-0.05),
                showlegend=True,
            )
            st.plotly_chart(fig_radar, use_container_width=True)

            # ── AI Comparison ─────────────────────────────────────────────
            if run_compare and priorities:
                cmp_rows = cmp_df[cmp_df["Symbol"].isin(cmp_stocks)].to_dict("records")
                with st.spinner("Groq is picking the best stock…"):
                    verdict = compare_stocks(cmp_rows, priorities)

                st.markdown("---")
                st.markdown("**🤖 AI Verdict**")

                # Highlight winner
                winner = ""
                for sym in cmp_stocks:
                    if sym in verdict[:60]:
                        winner = sym
                        break

                if winner:
                    st.markdown(
                        f"<div style='background:#166534;border-radius:8px;padding:10px 16px;"
                        f"font-size:1.1rem;font-weight:700;color:#bbf7d0;margin-bottom:10px'>"
                        f"🏆 Best Pick: {winner}</div>",
                        unsafe_allow_html=True,
                    )
                st.info(verdict)

            elif run_compare:
                st.warning("Please select at least one investment priority.")


# ── TAB 5: News & Sentiment ───────────────────────────────────────────────────
with tab5:
    st.markdown("#### 📰 News Sentiment — Groww · Google News · ET · Moneycontrol · BS · LiveMint")

    _SENT_BADGE = {
        "positive": ('<span style="background:#166534;color:#bbf7d0;padding:2px 8px;'
                     'border-radius:12px;font-size:0.75rem;font-weight:600">POSITIVE</span>'),
        "negative": ('<span style="background:#7f1d1d;color:#fecaca;padding:2px 8px;'
                     'border-radius:12px;font-size:0.75rem;font-weight:600">NEGATIVE</span>'),
        "neutral":  ('<span style="background:#1e3a5f;color:#bfdbfe;padding:2px 8px;'
                     'border-radius:12px;font-size:0.75rem;font-weight:600">NEUTRAL</span>'),
    }
    _SOURCE_COLORS = {
        "Groww":            "#f59e0b",
        "Google News":      "#3b82f6",
        "Economic Times":   "#ef4444",
        "Moneycontrol":     "#8b5cf6",
        "Business Standard":"#06b6d4",
        "LiveMint":         "#22c55e",
    }
    _EMO_COLORS = {
        "optimism":"#22c55e","greed":"#f59e0b","confidence":"#3b82f6",
        "fear":"#ef4444","panic":"#dc2626","uncertainty":"#94a3b8",
    }

    ns_left, ns_right = st.columns([1, 2])

    with ns_left:
        news_sym     = st.selectbox("Stock", filtered["Symbol"].tolist(), key="news_sym")
        # Get company name for better Google News search
        news_name_row = filtered[filtered["Symbol"] == news_sym]
        news_company  = news_name_row["Name"].iloc[0] if not news_name_row.empty else ""
        run_news     = st.button("🔍 Fetch & Analyse News", use_container_width=True, type="primary")
        st.markdown("---")
        st.markdown("**Market-wide sentiment**")
        st.caption("Scores all stocks in recent news with positive/negative breakdown")
        run_market   = st.button("🌐 Scan & Score Market News", use_container_width=True)

    with ns_right:
        # ── Per-stock news ────────────────────────────────────────────────
        if run_news:
            with st.spinner(f"Fetching news for {news_sym} from all sources…"):
                ns = get_news_summary(news_sym, news_company)

            if ns["count"] == 0:
                st.warning(f"No recent news found for **{news_sym}** across any source.")
            else:
                arts = ns["articles"]

                # Summary banner
                ov_color = "#22c55e" if ns["overall"] > 0.15 else ("#ef4444" if ns["overall"] < -0.15 else "#3b82f6")
                st.markdown(
                    f"<div style='background:#1e293b;border-radius:10px;padding:14px 18px;"
                    f"border-left:4px solid {ov_color};margin-bottom:12px'>"
                    f"<span style='font-size:1.2rem;font-weight:700;color:{ov_color}'>"
                    f"{ns['label']} Sentiment</span>"
                    f"<span style='color:#94a3b8;font-size:0.9rem;margin-left:10px'>"
                    f"score {ns['overall']:+.3f} · {ns['count']} articles</span></div>",
                    unsafe_allow_html=True,
                )

                sc1, sc2, sc3 = st.columns(3)
                sc1.metric("Positive", ns["positive"])
                sc2.metric("Neutral",  ns["neutral"])
                sc3.metric("Negative", ns["negative"])

                ch1, ch2 = st.columns(2)

                # Donut
                with ch1:
                    donut = go.Figure(go.Pie(
                        labels=["Positive", "Neutral", "Negative"],
                        values=[ns["positive"], ns["neutral"], ns["negative"]],
                        hole=0.55,
                        marker_colors=["#22c55e", "#3b82f6", "#ef4444"],
                        textinfo="label+percent",
                    ))
                    donut.update_layout(
                        template="plotly_dark", paper_bgcolor="#0f172a",
                        height=230, margin=dict(l=0, r=0, t=10, b=0),
                        showlegend=False,
                        title=dict(text="Sentiment split", font=dict(color="#94a3b8", size=12)),
                    )
                    st.plotly_chart(donut, use_container_width=True)

                # Source breakdown
                with ch2:
                    if "source" in arts.columns:
                        src_counts = arts["source"].value_counts().reset_index()
                        src_counts.columns = ["Source", "Count"]
                        src_counts["color"] = src_counts["Source"].map(
                            lambda s: _SOURCE_COLORS.get(s, "#64748b")
                        )
                        fig_src = go.Figure(go.Bar(
                            x=src_counts["Source"], y=src_counts["Count"],
                            marker_color=src_counts["color"],
                        ))
                        fig_src.update_layout(
                            template="plotly_dark", paper_bgcolor="#0f172a",
                            plot_bgcolor="#0f172a", height=230,
                            margin=dict(l=0, r=0, t=10, b=0),
                            title=dict(text="Articles by source", font=dict(color="#94a3b8", size=12)),
                            xaxis=dict(tickangle=-30, tickfont=dict(color="#94a3b8", size=10)),
                            yaxis=dict(tickfont=dict(color="#94a3b8")),
                        )
                        st.plotly_chart(fig_src, use_container_width=True)

                # Emotion bar
                if "emotion" in arts.columns:
                    emo_counts = arts["emotion"].value_counts().reset_index()
                    emo_counts.columns = ["Emotion", "Count"]
                    emo_counts["color"] = emo_counts["Emotion"].map(
                        lambda e: _EMO_COLORS.get(e, "#64748b")
                    )
                    fig_emo = go.Figure(go.Bar(
                        x=emo_counts["Emotion"], y=emo_counts["Count"],
                        marker_color=emo_counts["color"],
                    ))
                    fig_emo.update_layout(
                        template="plotly_dark", paper_bgcolor="#0f172a",
                        plot_bgcolor="#0f172a", height=200,
                        margin=dict(l=0, r=0, t=10, b=0),
                        title=dict(text="Emotion distribution", font=dict(color="#94a3b8", size=12)),
                        xaxis=dict(tickfont=dict(color="#94a3b8")),
                        yaxis=dict(tickfont=dict(color="#94a3b8")),
                    )
                    st.plotly_chart(fig_emo, use_container_width=True)

                # Article list
                st.markdown(f"**{ns['count']} articles**")
                for _, row_a in arts.iterrows():
                    badge      = _SENT_BADGE.get(row_a.get("sentiment", "neutral"), _SENT_BADGE["neutral"])
                    src        = row_a.get("source", "")
                    src_color  = _SOURCE_COLORS.get(src, "#64748b")
                    src_pill   = (f'<span style="background:{src_color}22;color:{src_color};'
                                  f'padding:1px 7px;border-radius:10px;font-size:0.72rem;'
                                  f'border:1px solid {src_color}55">{src}</span>')
                    url        = row_a.get("url", "")
                    title_text = row_a.get("title", "")[:220]
                    title_html = (f'<a href="{url}" target="_blank" style="color:#e2e8f0;'
                                  f'text-decoration:none">{title_text}</a>' if url else
                                  f'<span style="color:#e2e8f0">{title_text}</span>')

                    st.markdown(
                        f"<div style='background:#1e293b;border-radius:8px;padding:10px 14px;"
                        f"margin-bottom:6px'>"
                        f"{badge} {src_pill} &nbsp;"
                        f"<span style='color:#64748b;font-size:0.78rem'>"
                        f"{row_a.get('date','')} · {str(row_a.get('emotion','')).capitalize()}</span><br>"
                        f"<span style='font-size:0.88rem'>{title_html}</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

        # ── Market-wide sentiment ─────────────────────────────────────────
        if run_market:
            prog = st.progress(0, text="Fetching news from all sources…")
            with st.spinner("Scoring sentiment across all stocks…"):
                prog.progress(30, text="Fetching articles…")
                scored_all = score_market_news(pages=6)
                prog.progress(100, text="Done")
                prog.empty()

            if scored_all.empty:
                st.warning("Could not reach news sources.")
            else:
                # Only keep stocks with ≥2 articles for a meaningful chart
                counts = scored_all["ticker"].value_counts()
                top_tickers = counts[counts >= 2].head(25).index.tolist()
                chart_df = scored_all[scored_all["ticker"].isin(top_tickers)]

                sent_agg = (chart_df.groupby(["ticker", "sentiment"])
                            .size().unstack(fill_value=0).reset_index())
                for col in ["positive", "neutral", "negative"]:
                    if col not in sent_agg.columns:
                        sent_agg[col] = 0

                # Sort by (positive - negative)
                sent_agg["net"] = sent_agg["positive"] - sent_agg["negative"]
                sent_agg = sent_agg.sort_values("net", ascending=False)

                fig_mkt = go.Figure()
                fig_mkt.add_trace(go.Bar(
                    x=sent_agg["ticker"], y=sent_agg["positive"],
                    name="Positive", marker_color="#22c55e",
                ))
                fig_mkt.add_trace(go.Bar(
                    x=sent_agg["ticker"], y=sent_agg["neutral"],
                    name="Neutral", marker_color="#3b82f6",
                ))
                fig_mkt.add_trace(go.Bar(
                    x=sent_agg["ticker"], y=sent_agg["negative"],
                    name="Negative", marker_color="#ef4444",
                ))
                fig_mkt.update_layout(
                    barmode="stack",
                    template="plotly_dark", paper_bgcolor="#0f172a",
                    plot_bgcolor="#0f172a", height=420,
                    margin=dict(l=0, r=0, t=30, b=0),
                    title=dict(text="Market Sentiment by Stock (sorted by net positive)",
                               font=dict(color="#94a3b8")),
                    xaxis=dict(tickangle=-40, tickfont=dict(color="#94a3b8")),
                    yaxis=dict(title="Articles", tickfont=dict(color="#94a3b8")),
                    legend=dict(orientation="h", y=1.08),
                )
                st.plotly_chart(fig_mkt, use_container_width=True)

                # Source breakdown for market scan
                src_agg = scored_all["source"].value_counts().reset_index()
                src_agg.columns = ["Source", "Articles"]
                src_agg["color"] = src_agg["Source"].map(lambda s: _SOURCE_COLORS.get(s, "#64748b"))
                fig_src2 = go.Figure(go.Bar(
                    x=src_agg["Source"], y=src_agg["Articles"],
                    marker_color=src_agg["color"],
                ))
                fig_src2.update_layout(
                    template="plotly_dark", paper_bgcolor="#0f172a",
                    plot_bgcolor="#0f172a", height=220,
                    margin=dict(l=0, r=0, t=30, b=0),
                    title=dict(text="Articles by Source", font=dict(color="#94a3b8")),
                    xaxis=dict(tickfont=dict(color="#94a3b8")),
                    yaxis=dict(tickfont=dict(color="#94a3b8")),
                )
                st.plotly_chart(fig_src2, use_container_width=True)

                n_arts    = len(scored_all)
                n_stocks  = scored_all["ticker"].nunique()
                n_sources = scored_all["source"].nunique()
                st.caption(f"{n_arts} articles · {n_stocks} stocks · {n_sources} sources")


# ── TAB 6: Heatmap ────────────────────────────────────────────────────────────
with tab6:
    st.markdown("#### Market Cap Heatmap — hover any tile for aggregated or per-stock stats")

    hm_data = filtered[filtered["Mkt Cap (₹Cr)"] > 0].copy()

    if hm_data.empty:
        st.info("No data available for heatmap with current filters.")
    else:
        # ── Build ECharts tree ────────────────────────────────────────────
        def _safe(v, fmt="{:.1f}", fallback="—"):
            try:
                return fmt.format(float(v)) if v and float(v) != 0 else fallback
            except Exception:
                return fallback

        def _agg_node(df, name, level):
            avg_pe  = df["P/E"].replace(0, float("nan")).mean()
            avg_pb  = df["P/B"].replace(0, float("nan")).mean()
            avg_eps = df["EPS"].replace(0, float("nan")).mean()
            avg_bet = df["Beta"].replace(0, float("nan")).mean()
            avg_chg = df["Change %"].mean()
            return {
                "name":      name,
                "value":     [round(df["Mkt Cap (₹Cr)"].sum(), 1), round(avg_chg, 2)],
                "level":     level,
                "totalMcap": f"₹{df['Mkt Cap (₹Cr)'].sum():,.0f} Cr",
                "avgPE":     _safe(avg_pe,  "{:.1f}"),
                "avgPB":     _safe(avg_pb,  "{:.2f}"),
                "avgEPS":    "₹" + _safe(avg_eps, "{:.2f}"),
                "totalRev":  f"₹{df['Revenue (₹Cr)'].sum():,.0f} Cr",
                "totalNI":   f"₹{df['Net Inc (₹Cr)'].sum():,.0f} Cr",
                "avgDiv":    f"{df['Div Yield %'].mean():.2f}%",
                "avgChg":    f"{avg_chg:+.2f}%",
                "avgBeta":   _safe(avg_bet, "{:.2f}"),
                "nStocks":   str(len(df)),
            }

        tree = []
        for cap in hm_data["Cap Category"].unique():
            cap_df   = hm_data[hm_data["Cap Category"] == cap]
            cap_node = _agg_node(cap_df, cap, "cap")
            sectors  = []

            for sector in cap_df["Sector"].unique():
                sec_df   = cap_df[cap_df["Sector"] == sector]
                sec_node = _agg_node(sec_df, sector, "sector")
                stocks   = []

                for _, s in sec_df.iterrows():
                    stocks.append({
                        "name":     s["Symbol"],
                        "value":    [round(s["Mkt Cap (₹Cr)"], 1), round(s["Change %"], 2)],
                        "level":    "stock",
                        "fullName": s["Name"],
                        "price":    f"₹{s['Price (₹)']:,.2f}",
                        "chgRaw":   round(s["Change %"], 2),
                        "chg":      f"{s['Change %']:+.2f}%",
                        "mcap":     f"₹{s['Mkt Cap (₹Cr)']:,.0f} Cr",
                        "pe":       _safe(s["P/E"],  "{:.1f}"),
                        "pb":       _safe(s["P/B"],  "{:.2f}"),
                        "eps":      "₹" + _safe(s["EPS"], "{:.2f}"),
                        "rev":      f"₹{s['Revenue (₹Cr)']:,.0f} Cr",
                        "ni":       f"₹{s['Net Inc (₹Cr)']:,.0f} Cr",
                        "div":      f"{s['Div Yield %']:.2f}%",
                        "beta":     _safe(s["Beta"], "{:.2f}"),
                        "sector":   s["Sector"],
                    })

                sec_node["children"] = stocks
                sectors.append(sec_node)

            cap_node["children"] = sectors
            tree.append(cap_node)

        tree_json = json.dumps(tree)

        # ── ECharts HTML (CDN, no package required) ───────────────────────
        html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
<style>
  body {{ margin:0; padding:0; background:#0f172a; overflow:hidden; }}
  #chart {{ width:100%; height:610px; }}
</style>
</head>
<body>
<div id="chart"></div>
<script>
var chart = echarts.init(document.getElementById('chart'), 'dark', {{renderer:'canvas'}});
var treeData = {tree_json};

var option = {{
  backgroundColor: '#0f172a',
  tooltip: {{
    trigger: 'item',
    backgroundColor: '#1e293b',
    borderColor: '#334155',
    borderWidth: 1,
    padding: 12,
    extraCssText: 'border-radius:8px;box-shadow:0 4px 24px rgba(0,0,0,0.6);font-family:monospace',
    formatter: function(params) {{
      var d = params.data;
      if (!d) return '';
      function row(label, val) {{
        return '<tr><td style="color:#94a3b8;padding:2px 12px 2px 0">' + label + '</td>'
             + '<td style="color:#f1f5f9;text-align:right">' + val + '</td></tr>';
      }}
      var html = '<div style="min-width:230px">';
      html += '<div style="font-weight:700;font-size:13px;color:#f1f5f9;margin-bottom:6px">' + d.name + '</div>';

      if (d.level === 'stock') {{
        html += '<div style="color:#94a3b8;font-size:11px;margin-bottom:8px">' + (d.fullName||'') + ' &bull; ' + (d.sector||'') + '</div>';
        var chgColor = d.chgRaw >= 0 ? '#22c55e' : '#ef4444';
        html += '<table style="width:100%;border-collapse:collapse;font-size:12px">';
        html += row('Price',     d.price);
        html += row('Change',    '<span style="color:' + chgColor + ';font-weight:600">' + d.chg + '</span>');
        html += row('Mkt Cap',   d.mcap);
        html += row('P/E',       d.pe);
        html += row('P/B',       d.pb);
        html += row('EPS',       d.eps);
        html += row('Revenue',   d.rev);
        html += row('Net Inc',   d.ni);
        html += row('Div Yield', d.div);
        html += row('Beta',      d.beta);
        html += '</table>';
      }} else {{
        var icon = d.level === 'cap' ? '🏦' : '🏭';
        html += '<div style="color:#94a3b8;font-size:11px;margin-bottom:8px">' + icon + ' ' + d.nStocks + ' stocks</div>';
        var chgColor = (d.avgChg||'').startsWith('+') ? '#22c55e' : '#ef4444';
        html += '<table style="width:100%;border-collapse:collapse;font-size:12px">';
        html += row('Total Mkt Cap', d.totalMcap);
        html += row('Avg P/E',       d.avgPE);
        html += row('Avg P/B',       d.avgPB);
        html += row('Avg EPS',       d.avgEPS);
        html += row('Total Revenue', d.totalRev);
        html += row('Total Net Inc', d.totalNI);
        html += row('Avg Div Yield', d.avgDiv);
        html += row('Avg Change',    '<span style="color:' + chgColor + ';font-weight:600">' + d.avgChg + '</span>');
        html += row('Avg Beta',      d.avgBeta);
        html += '</table>';
      }}
      html += '</div>';
      return html;
    }}
  }},
  visualMap: {{
    type: 'continuous',
    min: -5,
    max: 5,
    dimension: 1,
    inRange: {{ color: ['#ef4444','#1e293b','#22c55e'] }},
    show: true,
    orient: 'vertical',
    right: 8,
    top: 'center',
    itemHeight: 180,
    text: ['+5%', '-5%'],
    textStyle: {{ color: '#94a3b8', fontSize: 11 }},
    calculable: true
  }},
  series: [{{
    type: 'treemap',
    data: treeData,
    roam: false,
    nodeClick: 'zoomToNode',
    width: '94%',
    height: '94%',
    top: '2%',
    left: '2%',
    squareRatio: 0.7,
    visualDimension: 1,
    breadcrumb: {{
      show: true,
      bottom: 4,
      height: 24,
      itemStyle: {{
        color: '#1e293b',
        textStyle: {{ color: '#94a3b8', fontSize: 11 }}
      }}
    }},
    label: {{
      show: true,
      formatter: '{{b}}',
      color: '#f1f5f9',
      fontSize: 11,
      fontWeight: 'bold',
      overflow: 'truncate'
    }},
    upperLabel: {{
      show: true,
      height: 26,
      color: '#f1f5f9',
      fontSize: 12,
      fontWeight: 'bold',
      backgroundColor: 'rgba(0,0,0,0.35)',
      padding: [4, 8]
    }},
    itemStyle: {{
      borderColor: '#0f172a',
      borderWidth: 2,
      gapWidth: 2
    }},
    levels: [
      {{ itemStyle: {{ borderWidth: 0, gapWidth: 6 }} }},
      {{ itemStyle: {{ borderWidth: 3, borderColor: '#334155', gapWidth: 4 }},
         upperLabel: {{ show: true }} }},
      {{ itemStyle: {{ borderWidth: 2, borderColor: '#1e293b', gapWidth: 2 }},
         upperLabel: {{ show: true }} }},
      {{ itemStyle: {{ borderWidth: 1, borderColor: '#0f172a', gapWidth: 1 }} }}
    ]
  }}]
}};

chart.setOption(option);
window.addEventListener('resize', function() {{ chart.resize(); }});
</script>
</body>
</html>
"""
        components.html(html, height=630, scrolling=False)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<div style='text-align:center;color:#475569;font-size:0.8rem'>"
    "Data via Yahoo Finance (NSE) · AI via Groq llama3-70b · "
    "Not financial advice"
    "</div>",
    unsafe_allow_html=True,
)
