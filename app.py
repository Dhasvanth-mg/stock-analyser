"""
NSE Stock Analyser — Streamlit App
Filters: Blue Chip / Large Cap / Mid Cap / Small Cap / All
Sliders: Price range, Revenue range, Market Cap range
AI: Groq llama3-70b analysis per stock
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from dotenv import load_dotenv

from data_fetcher import (
    fetch_stock_batch, fetch_history,
    get_all_symbols, load_universe,
)
from ai_analyst import get_ai_analysis, get_portfolio_summary, compare_stocks

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
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📋 Screener", "📈 Chart", "🤖 AI Analysis", "⚖️ Compare", "🗂️ Heatmap"])

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
            with st.spinner(f"Analysing {ai_sym} with Groq…"):
                analysis = get_ai_analysis(stock_row)

            # Extract signal for badge
            sig = "HOLD"
            if "BUY"  in analysis.upper()[:30]: sig = "BUY"
            if "SELL" in analysis.upper()[:30]: sig = "SELL"
            badge_cls = {"BUY":"badge-buy","SELL":"badge-sell","HOLD":"badge-hold"}[sig]

            st.markdown(f'<span class="{badge_cls}">{sig}</span>', unsafe_allow_html=True)
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


# ── TAB 5: Heatmap ────────────────────────────────────────────────────────────
with tab5:
    st.markdown("#### Market Cap Heatmap by Sector")

    hm_data = filtered[filtered["Mkt Cap (₹Cr)"] > 0].copy()
    if not hm_data.empty:
        fig3 = px.treemap(
            hm_data,
            path=["Cap Category", "Sector", "Symbol"],
            values="Mkt Cap (₹Cr)",
            color="Change %",
            color_continuous_scale=["#ef4444", "#1e293b", "#22c55e"],
            color_continuous_midpoint=0,
            custom_data=["Name", "Price (₹)", "P/E"],
            title="",
        )
        fig3.update_traces(
            textinfo="label+value",
            hovertemplate="<b>%{label}</b><br>%{customdata[0]}<br>₹%{customdata[1]}<br>P/E: %{customdata[2]}<extra></extra>"
        )
        fig3.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0f172a",
            height=580,
            margin=dict(l=0, r=0, t=10, b=0),
            coloraxis_colorbar=dict(title="Change %"),
        )
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("No data available for heatmap with current filters.")

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<div style='text-align:center;color:#475569;font-size:0.8rem'>"
    "Data via Yahoo Finance (NSE) · AI via Groq llama3-70b · "
    "Not financial advice"
    "</div>",
    unsafe_allow_html=True,
)
