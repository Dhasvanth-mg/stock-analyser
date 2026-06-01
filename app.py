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
from screener_search import search_screener, fetch_company_data, fetch_bse_announcements, get_bse_code
from data_fetcher import fetch_single_stock, fetch_history

load_dotenv()

import datetime as _dt

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="NSE Stock Analyser",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session state ─────────────────────────────────────────────────────────────
if "cap_filter" not in st.session_state:
    st.session_state["cap_filter"] = "All"

# ── Design System CSS ─────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Tokens ────────────────────────────────────────────────── */
:root {
  --bg:          #07111d;
  --bg-card:     #0d1e30;
  --bg-raised:   #142438;
  --bg-hover:    #1a2f45;
  --border:      #1e3450;
  --border-subtle: #152130;
  --blue:   #3b82f6;
  --green:  #10b981;
  --red:    #ef4444;
  --amber:  #f59e0b;
  --purple: #8b5cf6;
  --cyan:   #06b6d4;
  --text:   #e2e8f0;
  --muted:  #64748b;
  --soft:   #94a3b8;
}

/* ── Layout ────────────────────────────────────────────────── */
.main .block-container { padding: 0.75rem 1.5rem 2rem; max-width: 1600px; }
.stApp { background: var(--bg); }

/* ── Header ────────────────────────────────────────────────── */
.nse-header {
  display: flex; align-items: center; justify-content: space-between;
  background: linear-gradient(120deg, #0d1e30 0%, #0f2640 60%, #0d1e30 100%);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 1rem 1.6rem;
  margin-bottom: 1rem;
}
.nse-header-left h1 {
  margin: 0; font-size: 1.55rem; font-weight: 800;
  background: linear-gradient(90deg, #60a5fa, #34d399);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.nse-header-left p { margin: 2px 0 0; font-size: 0.8rem; color: var(--muted); }
.nse-header-right { display: flex; gap: 20px; align-items: center; }
.market-badge {
  display: flex; align-items: center; gap: 6px;
  background: var(--bg-raised); border: 1px solid var(--border);
  border-radius: 8px; padding: 6px 12px;
  font-size: 0.78rem; color: var(--soft);
}
.dot-open  { width: 7px; height: 7px; border-radius: 50%; background: var(--green);
             box-shadow: 0 0 6px var(--green); animation: pulse 2s infinite; }
.dot-closed { width: 7px; height: 7px; border-radius: 50%; background: var(--muted); }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }

/* ── Cap Filter Pills ──────────────────────────────────────── */
.cap-bar {
  display: flex; gap: 8px; align-items: center;
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 12px; padding: 8px 12px; margin-bottom: 1rem;
}
.cap-label { font-size: 0.7rem; color: var(--muted); font-weight: 600;
             text-transform: uppercase; letter-spacing: .08em; margin-right: 4px; }

/* Style Streamlit buttons inside .cap-bar to look like pills */
.cap-bar .stButton > button {
  border-radius: 20px !important; font-size: 0.78rem !important;
  font-weight: 600 !important; padding: 4px 14px !important;
  border: 1px solid var(--border) !important;
  background: transparent !important; color: var(--soft) !important;
  transition: all 0.18s !important;
}
.cap-bar .stButton > button:hover {
  background: var(--bg-hover) !important;
  border-color: var(--blue) !important; color: var(--text) !important;
}

/* ── Stats Bar ─────────────────────────────────────────────── */
.stats-bar {
  display: flex; gap: 10px; margin-bottom: 1rem; flex-wrap: wrap;
}
.stat-chip {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 10px; padding: 10px 16px; flex: 1; min-width: 120px;
}
.stat-chip .sc-label { font-size: 0.68rem; color: var(--muted);
                       text-transform: uppercase; letter-spacing: .08em; }
.stat-chip .sc-value { font-size: 1.15rem; font-weight: 700; color: var(--text); margin-top: 2px; }
.stat-chip .sc-sub   { font-size: 0.72rem; color: var(--muted); margin-top: 1px; }
.sc-green { color: var(--green) !important; }
.sc-red   { color: var(--red)   !important; }
.sc-blue  { color: var(--blue)  !important; }
.sc-amber { color: var(--amber) !important; }

/* ── Cards ─────────────────────────────────────────────────── */
.card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 12px; padding: 16px 18px; margin-bottom: 10px;
}
.card-accent-blue   { border-left: 3px solid var(--blue);  }
.card-accent-green  { border-left: 3px solid var(--green); }
.card-accent-red    { border-left: 3px solid var(--red);   }
.card-accent-amber  { border-left: 3px solid var(--amber); }
.card-accent-purple { border-left: 3px solid var(--purple);}
.card h4 { margin: 0 0 8px; font-size: 0.8rem; color: var(--muted);
           text-transform: uppercase; letter-spacing: .07em; }

/* ── Badges ─────────────────────────────────────────────────── */
.badge {
  display: inline-block; padding: 3px 11px; border-radius: 20px;
  font-size: 0.75rem; font-weight: 700; letter-spacing: .04em;
}
.badge-buy    { background: rgba(16,185,129,.15); color: #34d399;
                border: 1px solid rgba(16,185,129,.3); }
.badge-sell   { background: rgba(239,68,68,.15);  color: #f87171;
                border: 1px solid rgba(239,68,68,.3); }
.badge-hold   { background: rgba(245,158,11,.15); color: #fbbf24;
                border: 1px solid rgba(245,158,11,.3); }
.badge-pos    { background: rgba(16,185,129,.12); color: #34d399;
                border: 1px solid rgba(16,185,129,.25); font-size: 0.7rem; }
.badge-neg    { background: rgba(239,68,68,.12);  color: #f87171;
                border: 1px solid rgba(239,68,68,.25); font-size: 0.7rem; }
.badge-neu    { background: rgba(100,116,139,.12); color: #94a3b8;
                border: 1px solid rgba(100,116,139,.25); font-size: 0.7rem; }

/* ── Cap category colours ───────────────────────────────────── */
.cap-blue-chip { background: rgba(59,130,246,.12); color: #60a5fa;
                 border: 1px solid rgba(59,130,246,.25); }
.cap-large     { background: rgba(16,185,129,.12); color: #34d399;
                 border: 1px solid rgba(16,185,129,.25); }
.cap-mid       { background: rgba(245,158,11,.12); color: #fbbf24;
                 border: 1px solid rgba(245,158,11,.25); }
.cap-small     { background: rgba(239,68,68,.12);  color: #f87171;
                 border: 1px solid rgba(239,68,68,.25); }

/* ── Article cards ──────────────────────────────────────────── */
.article-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 9px; padding: 10px 14px; margin-bottom: 6px;
  transition: border-color .18s;
}
.article-card:hover { border-color: var(--blue); }

/* ── Source pills ───────────────────────────────────────────── */
.src-pill {
  display: inline-block; padding: 1px 7px; border-radius: 10px;
  font-size: 0.68rem; font-weight: 600; border: 1px solid;
}

/* ── Section headings ───────────────────────────────────────── */
.section-hd {
  font-size: 0.68rem; font-weight: 700; color: var(--muted);
  text-transform: uppercase; letter-spacing: .1em;
  border-bottom: 1px solid var(--border-subtle);
  padding-bottom: 6px; margin: 16px 0 10px;
}

/* ── Sidebar ────────────────────────────────────────────────── */
section[data-testid="stSidebar"] {
  background: #060f1a;
  border-right: 1px solid var(--border);
}
section[data-testid="stSidebar"] .stMarkdown p { color: var(--muted); font-size: 0.8rem; }
section[data-testid="stSidebar"] h3 {
  font-size: 0.72rem; color: var(--muted); text-transform: uppercase;
  letter-spacing: .1em; margin-bottom: 6px; margin-top: 18px;
}

/* ── Tabs ────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
  gap: 4px; background: var(--bg-card);
  border-radius: 10px; padding: 4px; border: 1px solid var(--border);
}
.stTabs [data-baseweb="tab"] {
  border-radius: 8px; padding: 6px 14px;
  font-size: 0.8rem; font-weight: 600; color: var(--muted);
  background: transparent; border: none;
}
.stTabs [aria-selected="true"] {
  background: var(--bg-raised) !important; color: var(--text) !important;
  border: 1px solid var(--border) !important;
}
.stTabs [data-baseweb="tab-panel"] { padding-top: 16px; }

/* ── Compare metric cards ───────────────────────────────────── */
.cmp-card {
  background: var(--bg-card); border-radius: 10px;
  padding: 12px; border-top: 3px solid var(--blue);
  text-align: center; height: 100%;
}
.cmp-card .cmp-sym  { font-size: 1.05rem; font-weight: 800; color: var(--text); }
.cmp-card .cmp-cat  { font-size: 0.7rem;  color: var(--muted); margin: 2px 0 8px; }
.cmp-card .cmp-price{ font-size: 1.3rem;  font-weight: 700; color: var(--text); }
.cmp-card .cmp-row  { font-size: 0.78rem; color: var(--soft); margin-top: 4px; }
.cmp-card .cmp-row b{ color: var(--text); }
.cmp-card hr { border-color: var(--border); margin: 8px 0; }

/* ── Table ───────────────────────────────────────────────────── */
.dataframe { border: none !important; }
.dataframe thead th {
  background: var(--bg-raised) !important;
  color: var(--muted) !important;
  font-size: 0.72rem !important;
  text-transform: uppercase;
  letter-spacing: .06em;
}
.dataframe tbody tr:hover td { background: var(--bg-hover) !important; }

/* ── Scrollbar ───────────────────────────────────────────────── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: var(--blue); }
</style>
""", unsafe_allow_html=True)

# ── Market open/close helper ──────────────────────────────────────────────────
def _market_status():
    now = _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=5, minutes=30)))  # IST
    is_weekday = now.weekday() < 5
    open_time  = now.replace(hour=9,  minute=15, second=0, microsecond=0)
    close_time = now.replace(hour=15, minute=30, second=0, microsecond=0)
    is_open    = is_weekday and open_time <= now <= close_time
    return is_open, now.strftime("%a %d %b %Y · %H:%M IST")

_mkt_open, _mkt_time = _market_status()

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="nse-header">
  <div class="nse-header-left">
    <h1>📈 NSE Stock Analyser</h1>
    <p>Live market data · AI analysis via Groq · Screener.in deep dive</p>
  </div>
  <div class="nse-header-right">
    <div class="market-badge">
      <div class="{'dot-open' if _mkt_open else 'dot-closed'}"></div>
      <span>Market {'Open' if _mkt_open else 'Closed'}</span>
    </div>
    <div class="market-badge">🕐 {_mkt_time}</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### FILTERS")
    sector_placeholder = st.empty()

    st.markdown("### PRICE RANGE")
    price_range = st.slider("Stock Price (₹)", 0, 50000, (0, 50000), step=100, label_visibility="collapsed")
    st.caption("₹0 — ₹50,000")

    st.markdown("### REVENUE (₹ Cr)")
    rev_range = st.slider("Revenue", 0, 500000, (0, 500000), step=1000, label_visibility="collapsed")
    st.caption("₹0 — ₹5L Cr")

    st.markdown("### MARKET CAP (₹ Cr)")
    mktcap_range = st.slider("Market Cap", 0, 2000000, (0, 2000000), step=5000, label_visibility="collapsed")
    st.caption("₹0 — ₹20L Cr")

    st.markdown("### P/E RATIO")
    pe_range = st.slider("P/E", 0.0, 200.0, (0.0, 200.0), step=1.0, label_visibility="collapsed")
    st.caption("0 — 200")

    st.markdown("### DISPLAY")
    sort_col = st.selectbox("Sort by", ["Mkt Cap (₹Cr)", "Price (₹)", "Change %", "Revenue (₹Cr)", "P/E", "EPS"])
    c_sort1, c_sort2 = st.columns(2)
    sort_asc = c_sort1.checkbox("Ascending", value=False)
    max_rows  = st.slider("Max rows", 10, 500, 50, step=10)

    st.markdown("---")
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ── Cap filter pills (top of page) ────────────────────────────────────────────
_CAP_OPTS = ["All", "Blue Chip", "Large Cap", "Mid Cap", "Small Cap"]
_CAP_ICONS = {"All":"🌐","Blue Chip":"🔵","Large Cap":"🟢","Mid Cap":"🟡","Small Cap":"🔴"}

st.markdown('<div class="cap-bar">'
            '<span class="cap-label">Cap</span>', unsafe_allow_html=True)
_cap_cols = st.columns(len(_CAP_OPTS))
for _i, _cap in enumerate(_CAP_OPTS):
    with _cap_cols[_i]:
        _label = f"{_CAP_ICONS[_cap]} {_cap}"
        if st.button(_label, use_container_width=True,
                     type="primary" if st.session_state["cap_filter"] == _cap else "secondary",
                     key=f"cap_{_cap}"):
            st.session_state["cap_filter"] = _cap
            st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

cap_filter = st.session_state["cap_filter"]

# ── Load data ─────────────────────────────────────────────────────────────────
symbols = get_all_symbols(cap_filter)

_prog = st.progress(0, text=f"Loading {len(symbols)} stocks…")
df = fetch_stock_batch(symbols)
_prog.empty()

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

# ── Stats bar ─────────────────────────────────────────────────────────────────
_gainers   = int((filtered["Change %"] > 0).sum())
_losers    = int((filtered["Change %"] < 0).sum())
_flat      = len(filtered) - _gainers - _losers
_avg_pe    = filtered["P/E"].replace(0, pd.NA).mean()
_total_mc  = filtered["Mkt Cap (₹Cr)"].sum()
_avg_chg   = filtered["Change %"].mean()
_chg_col   = "sc-green" if _avg_chg >= 0 else "sc-red"

st.markdown(f"""
<div class="stats-bar">
  <div class="stat-chip card-accent-blue">
    <div class="sc-label">Stocks</div>
    <div class="sc-value sc-blue">{len(filtered)}</div>
    <div class="sc-sub">of {len(df)} loaded</div>
  </div>
  <div class="stat-chip card-accent-green">
    <div class="sc-label">Gainers</div>
    <div class="sc-value sc-green">{_gainers}</div>
    <div class="sc-sub">{_gainers/len(filtered)*100:.0f}% of shown</div>
  </div>
  <div class="stat-chip card-accent-red">
    <div class="sc-label">Losers</div>
    <div class="sc-value sc-red">{_losers}</div>
    <div class="sc-sub">{_flat} flat</div>
  </div>
  <div class="stat-chip card-accent-amber">
    <div class="sc-label">Avg P/E</div>
    <div class="sc-value sc-amber">{f"{_avg_pe:.1f}" if pd.notna(_avg_pe) else "—"}</div>
    <div class="sc-sub">market valuation</div>
  </div>
  <div class="stat-chip">
    <div class="sc-label">Avg Change</div>
    <div class="sc-value {_chg_col}">{_avg_chg:+.2f}%</div>
    <div class="sc-sub">today</div>
  </div>
  <div class="stat-chip">
    <div class="sc-label">Total Mkt Cap</div>
    <div class="sc-value">₹{_total_mc/1e5:.1f}L Cr</div>
    <div class="sc-sub">combined</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Main tabs ─────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(["📋 Screener", "📈 Chart", "🤖 AI Analysis", "⚖️ Compare", "📰 News & Sentiment", "🔍 Deep Search", "🗂️ Heatmap"])

# ── TAB 1: Screener table ─────────────────────────────────────────────────────
with tab1:
    st.markdown(f'<div class="section-hd">Showing {len(filtered)} stocks · sorted by {sort_col} · {cap_filter}</div>',
                unsafe_allow_html=True)

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
            "Blue Chip": "background-color: rgba(59,130,246,.12); color: #60a5fa",
            "Large Cap": "background-color: rgba(16,185,129,.12); color: #34d399",
            "Mid Cap":   "background-color: rgba(245,158,11,.12); color: #fbbf24",
            "Small Cap": "background-color: rgba(239,68,68,.12);  color: #f87171",
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
                paper_bgcolor="#07111d",
                plot_bgcolor="#07111d",
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
                template="plotly_dark", paper_bgcolor="#07111d",
                plot_bgcolor="#07111d", height=150,
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
                paper_bgcolor="#07111d",
                plot_bgcolor="#07111d",
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
            badge_cls = {"BUY":"badge badge-buy","SELL":"badge badge-sell","HOLD":"badge badge-hold"}[sig]

            # Signal + news sentiment pill side by side
            news_label = news_ctx.get("label", "")
            news_score = news_ctx.get("overall", 0)
            news_count = news_ctx.get("count", 0)
            news_color = {"Positive":"var(--green)","Negative":"var(--red)","Neutral":"var(--blue)"}.get(news_label, "var(--blue)")
            news_bg    = {"Positive":"rgba(16,185,129,.12)","Negative":"rgba(239,68,68,.12)","Neutral":"rgba(59,130,246,.12)"}.get(news_label, "rgba(59,130,246,.12)")

            col_sig, col_news = st.columns([1, 2])
            with col_sig:
                st.markdown(f'<span class="{badge_cls}">{sig}</span>', unsafe_allow_html=True)
            with col_news:
                if news_count:
                    st.markdown(
                        f'<span style="background:{news_bg};color:{news_color};'
                        f'padding:3px 12px;border-radius:20px;font-size:0.75rem;font-weight:600;'
                        f'border:1px solid {news_color}44">'
                        f'📰 News: {news_label} {news_score:+.2f} · {news_count} articles</span>',
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
                    <div class="cmp-card">
                        <div class="cmp-sym">{sym}</div>
                        <div class="cmp-cat">{r['Cap Category']} · {r['Sector']}</div>
                        <div class="cmp-price">₹{r['Price (₹)']:,.2f}</div>
                        <div style="color:{chg_color};font-size:0.82rem;font-weight:700">
                            {r['Change %']:+.2f}%
                        </div>
                        <hr>
                        <div class="cmp-row">P/E <b>{r['P/E']:.1f}</b> &nbsp;·&nbsp; P/B <b>{r['P/B']:.2f}</b></div>
                        <div class="cmp-row">EPS <b>₹{r['EPS']:.2f}</b></div>
                        <div class="cmp-row">Rev <b>₹{r['Revenue (₹Cr)']:,.0f} Cr</b></div>
                        <div class="cmp-row">Div <b>{r['Div Yield %']:.2f}%</b> &nbsp;·&nbsp; β <b>{r['Beta']:.2f}</b></div>
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
                paper_bgcolor="#07111d",
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
                        template="plotly_dark", paper_bgcolor="#07111d",
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
                            template="plotly_dark", paper_bgcolor="#07111d",
                            plot_bgcolor="#07111d", height=230,
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
                        template="plotly_dark", paper_bgcolor="#07111d",
                        plot_bgcolor="#07111d", height=200,
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
                    template="plotly_dark", paper_bgcolor="#07111d",
                    plot_bgcolor="#07111d", height=420,
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
                    template="plotly_dark", paper_bgcolor="#07111d",
                    plot_bgcolor="#07111d", height=220,
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


# ── TAB 6: Deep Search (Screener.in) ──────────────────────────────────────────
with tab6:
    st.markdown("#### 🔍 Deep Search — powered by Screener.in")

    sr_col1, sr_col2 = st.columns([1, 2])

    with sr_col1:
        query = st.text_input("Search by name or symbol", placeholder="e.g. Reliance, HDFCBANK, Infosys…")
        results = search_screener(query) if query else []

        if results:
            options = {r["name"]: r["url"] for r in results if r.get("type") == "equity"}
            if not options:
                options = {r["name"]: r["url"] for r in results}
            chosen_name = st.selectbox("Select company", list(options.keys()))
            chosen_url  = options[chosen_name]
            load_btn    = st.button("📊 Load Full Financials", use_container_width=True, type="primary")

            # Consolidated toggle
            use_consolidated = st.checkbox("Consolidated financials", value=True)
            if use_consolidated and not chosen_url.endswith("consolidated/"):
                chosen_url = chosen_url.rstrip("/") + "/consolidated/"

            # BSE announcements
            st.markdown("---")
            symbol_guess = chosen_url.split("/company/")[-1].split("/")[0]
            ann_days = st.slider("Announcements (days back)", 7, 90, 30)
            load_ann = st.button("📢 Load Announcements", use_container_width=True)

        elif query:
            st.info("No results found — try a different name or symbol.")
            load_btn, load_ann = False, False
            chosen_url, symbol_guess, ann_days = "", "", 30
        else:
            load_btn, load_ann = False, False
            chosen_url, symbol_guess, ann_days = "", "", 30

    with sr_col2:
        if load_btn and chosen_url:
            with st.spinner(f"Fetching data from Screener.in…"):
                data = fetch_company_data(chosen_url)

            if not data:
                st.error("Could not load data. Screener.in may be temporarily unavailable.")
            else:
                # ── Company name ──────────────────────────────────────────
                st.markdown(
                    f"<div style='background:#1e293b;border-radius:10px;padding:14px 18px;"
                    f"border-left:4px solid #3b82f6;margin-bottom:14px'>"
                    f"<span style='font-size:1.2rem;font-weight:700;color:#f1f5f9'>"
                    f"{data.get('name','')}</span><br>"
                    f"<span style='color:#94a3b8;font-size:0.85rem'>"
                    f"<a href='https://www.screener.in{chosen_url}' target='_blank' "
                    f"style='color:#60a5fa'>View on Screener.in ↗</a></span></div>",
                    unsafe_allow_html=True,
                )

                # ── Key ratios grid ───────────────────────────────────────
                ratios = data.get("ratios", {})
                if ratios:
                    st.markdown("**Key Ratios**")
                    ratio_items = list(ratios.items())
                    cols = st.columns(4)
                    for i, (k, v) in enumerate(ratio_items):
                        cols[i % 4].metric(k, v)

                # ── Pros & Cons ───────────────────────────────────────────
                pros = data.get("pros", [])
                cons = data.get("cons", [])
                if pros or cons:
                    pc1, pc2 = st.columns(2)
                    with pc1:
                        if pros:
                            st.markdown("**✅ Pros**")
                            for p in pros[:5]:
                                st.markdown(f"<div style='background:#166534;color:#bbf7d0;border-radius:6px;"
                                            f"padding:6px 10px;margin-bottom:4px;font-size:0.83rem'>{p}</div>",
                                            unsafe_allow_html=True)
                    with pc2:
                        if cons:
                            st.markdown("**❌ Cons**")
                            for c in cons[:5]:
                                st.markdown(f"<div style='background:#7f1d1d;color:#fecaca;border-radius:6px;"
                                            f"padding:6px 10px;margin-bottom:4px;font-size:0.83rem'>{c}</div>",
                                            unsafe_allow_html=True)

                # ── Tabs for financial tables ──────────────────────────────
                ft1, ft2, ft3, ft4, ft5, ft6 = st.tabs([
                    "Quarterly", "P&L", "Balance Sheet", "Cash Flow", "Ratios", "Shareholding"
                ])

                def _show_table(df: pd.DataFrame):
                    if df.empty:
                        st.info("No data available.")
                        return
                    st.dataframe(
                        df.style.set_properties(**{"background-color": "#0f172a", "color": "#e2e8f0"}),
                        use_container_width=True,
                    )

                with ft1: _show_table(data.get("quarterly", pd.DataFrame()))
                with ft2:
                    pnl = data.get("pnl", pd.DataFrame())
                    _show_table(pnl)
                    # Revenue trend chart
                    if not pnl.empty and "Sales" in pnl.columns:
                        try:
                            sales_row = pnl[pnl.iloc[:, 0].astype(str).str.contains("Sales|Revenue", case=False, na=False)]
                            if not sales_row.empty:
                                years = [c for c in pnl.columns if c not in [pnl.columns[0], "TTM"]]
                                vals  = sales_row.iloc[0][years].astype(str).str.replace(",", "").replace("—", "0")
                                fig_rev = go.Figure(go.Bar(x=years, y=pd.to_numeric(vals, errors="coerce"),
                                                           marker_color="#3b82f6", name="Revenue"))
                                fig_rev.update_layout(template="plotly_dark", paper_bgcolor="#07111d",
                                                      plot_bgcolor="#07111d", height=260,
                                                      margin=dict(l=0, r=0, t=20, b=0),
                                                      title="Revenue trend (₹ Cr)")
                                st.plotly_chart(fig_rev, use_container_width=True)
                        except Exception:
                            pass
                with ft3: _show_table(data.get("balance_sheet", pd.DataFrame()))
                with ft4: _show_table(data.get("cash_flow", pd.DataFrame()))
                with ft5: _show_table(data.get("fin_ratios", pd.DataFrame()))
                with ft6:
                    sh = data.get("shareholding", pd.DataFrame())
                    _show_table(sh)
                    # Shareholding pie — exclude count rows, keep % rows only
                    if not sh.empty:
                        try:
                            latest_col = sh.columns[-1]
                            _EXCLUDE = r"shareholders|no\.\s*of|number of"
                            _INCLUDE = r"promoter|dii|fii|public|govern|mutual|insurance|other"
                            sh_pie = sh[
                                sh.iloc[:, 0].astype(str).str.lower().str.contains(_INCLUDE, na=False) |
                                (
                                    ~sh.iloc[:, 0].astype(str).str.lower().str.contains(_EXCLUDE, na=False) &
                                    sh.iloc[:, 0].astype(str).str.lower().str.contains(r"[a-z]", na=False)
                                )
                            ]
                            # Also drop rows where value looks like a raw count (> 200)
                            sh_pie = sh_pie.copy()
                            sh_pie["_val"] = pd.to_numeric(
                                sh_pie[latest_col].astype(str).str.replace("%","").str.replace(",",""),
                                errors="coerce"
                            )
                            sh_pie = sh_pie[(sh_pie["_val"] > 0) & (sh_pie["_val"] <= 100)]
                            labels = sh_pie.iloc[:, 0].astype(str).tolist()
                            vals   = sh_pie["_val"].tolist()

                            if labels and any(v > 0 for v in vals):
                                fig_sh = go.Figure(go.Pie(
                                    labels=labels, values=vals, hole=0.5,
                                    marker_colors=["#3b82f6","#22c55e","#f59e0b","#ef4444","#a78bfa","#06b6d4"],
                                    textinfo="label+percent",
                                    hovertemplate="<b>%{label}</b><br>%{value:.2f}%<extra></extra>",
                                ))
                                fig_sh.update_layout(
                                    template="plotly_dark", paper_bgcolor="#07111d",
                                    height=340, margin=dict(l=0, r=0, t=30, b=0),
                                    legend=dict(orientation="h", y=-0.1, font=dict(size=11)),
                                    title=dict(text=f"Shareholding — {latest_col}", font=dict(color="#94a3b8")),
                                )
                                st.plotly_chart(fig_sh, use_container_width=True)
                        except Exception:
                            pass

                # ── Price chart ───────────────────────────────────────────
                st.markdown("---")
                st.markdown("**📈 Price Chart**")
                ds_period = st.radio("Period", ["1mo","3mo","6mo","1y","2y"], index=2,
                                     horizontal=True, key="ds_period")
                with st.spinner(f"Loading {symbol_guess} chart…"):
                    ds_hist = fetch_history(symbol_guess, ds_period)

                if not ds_hist.empty:
                    ds_hist["SMA20"] = ds_hist["Close"].rolling(20).mean()
                    ds_hist["SMA50"] = ds_hist["Close"].rolling(50).mean()
                    delta = ds_hist["Close"].diff()
                    gain  = delta.where(delta > 0, 0).rolling(14).mean()
                    loss  = (-delta.where(delta < 0, 0)).rolling(14).mean()
                    ds_hist["RSI"] = 100 - (100 / (1 + gain / loss.replace(0, float("nan"))))

                    from plotly.subplots import make_subplots as _msp
                    fig_ds = _msp(rows=2, cols=1, shared_xaxes=True,
                                  row_heights=[0.7, 0.3], vertical_spacing=0.04)

                    fig_ds.add_trace(go.Candlestick(
                        x=ds_hist.index,
                        open=ds_hist["Open"], high=ds_hist["High"],
                        low=ds_hist["Low"],   close=ds_hist["Close"],
                        name=symbol_guess,
                        increasing_line_color="#22c55e",
                        decreasing_line_color="#ef4444",
                    ), row=1, col=1)
                    fig_ds.add_trace(go.Scatter(x=ds_hist.index, y=ds_hist["SMA20"],
                        name="SMA 20", line=dict(color="#60a5fa", width=1.5)), row=1, col=1)
                    fig_ds.add_trace(go.Scatter(x=ds_hist.index, y=ds_hist["SMA50"],
                        name="SMA 50", line=dict(color="#f59e0b", width=1.5)), row=1, col=1)
                    fig_ds.add_trace(go.Scatter(x=ds_hist.index, y=ds_hist["RSI"],
                        name="RSI", line=dict(color="#a78bfa", width=1.5),
                        fill="tozeroy", fillcolor="rgba(167,139,250,0.1)"), row=2, col=1)
                    fig_ds.add_hline(y=70, line_dash="dash", line_color="#ef4444", line_width=1, row=2, col=1)
                    fig_ds.add_hline(y=30, line_dash="dash", line_color="#22c55e", line_width=1, row=2, col=1)

                    fig_ds.update_layout(
                        template="plotly_dark", paper_bgcolor="#07111d", plot_bgcolor="#07111d",
                        height=460, margin=dict(l=0, r=0, t=10, b=0),
                        xaxis_rangeslider_visible=False,
                        legend=dict(orientation="h", y=1.04, font=dict(size=11)),
                    )
                    fig_ds.update_yaxes(title_text="Price (₹)", row=1, col=1)
                    fig_ds.update_yaxes(title_text="RSI", row=2, col=1, range=[0, 100])
                    st.plotly_chart(fig_ds, use_container_width=True)
                else:
                    st.info(f"No price history available for {symbol_guess} on NSE.")

                # ── Live stock data from yfinance ─────────────────────────
                st.markdown("---")
                st.markdown("**📡 Live Market Data (NSE)**")
                with st.spinner(f"Fetching live data for {symbol_guess}…"):
                    live = fetch_single_stock(symbol_guess)
                if live:
                    lc1, lc2, lc3, lc4 = st.columns(4)
                    lc1.metric("Price",    f"₹{live['Price (₹)']:,.2f}", f"{live['Change %']:+.2f}%")
                    lc2.metric("Mkt Cap",  f"₹{live['Mkt Cap (₹Cr)']:,.0f} Cr")
                    lc3.metric("P/E",      f"{live['P/E']:.1f}")
                    lc4.metric("Revenue",  f"₹{live['Revenue (₹Cr)']:,.0f} Cr")
                    lc5, lc6, lc7, lc8 = st.columns(4)
                    lc5.metric("P/B",      f"{live['P/B']:.2f}")
                    lc6.metric("EPS",      f"₹{live['EPS']:.2f}")
                    lc7.metric("Div Yield",f"{live['Div Yield %']:.2f}%")
                    lc8.metric("Beta",     f"{live['Beta']:.2f}")
                else:
                    st.info(f"{symbol_guess} not found in yfinance — may not be in NSE universe.")

                # ── News sentiment ────────────────────────────────────────
                st.markdown("---")
                st.markdown("**📰 News Sentiment**")
                with st.spinner(f"Fetching & scoring news for {symbol_guess}…"):
                    ns = get_news_summary(symbol_guess, data.get("name", ""))

                if ns["count"] == 0:
                    st.info("No recent news found for this stock.")
                else:
                    ov_color = "#22c55e" if ns["overall"] > 0.15 else ("#ef4444" if ns["overall"] < -0.15 else "#3b82f6")
                    st.markdown(
                        f"<div style='background:#1e293b;border-radius:8px;padding:10px 16px;"
                        f"border-left:3px solid {ov_color};margin-bottom:10px'>"
                        f"<span style='font-weight:700;color:{ov_color}'>{ns['label']}</span>"
                        f"<span style='color:#94a3b8;font-size:0.85rem;margin-left:8px'>"
                        f"score {ns['overall']:+.3f} · {ns['count']} articles · "
                        f"✅ {ns['positive']} positive · ❌ {ns['negative']} negative</span></div>",
                        unsafe_allow_html=True,
                    )
                    arts = ns["articles"]
                    _SB  = {
                        "positive": '<span style="background:#166534;color:#bbf7d0;padding:1px 7px;border-radius:10px;font-size:0.72rem;font-weight:600">POS</span>',
                        "negative": '<span style="background:#7f1d1d;color:#fecaca;padding:1px 7px;border-radius:10px;font-size:0.72rem;font-weight:600">NEG</span>',
                        "neutral":  '<span style="background:#1e3a5f;color:#bfdbfe;padding:1px 7px;border-radius:10px;font-size:0.72rem;font-weight:600">NEU</span>',
                    }
                    _SC  = {"Groww":"#f59e0b","Google News":"#3b82f6","Economic Times":"#ef4444",
                            "Moneycontrol":"#8b5cf6","Business Standard":"#06b6d4","LiveMint":"#22c55e"}
                    for _, row_a in arts.head(8).iterrows():
                        badge = _SB.get(row_a.get("sentiment","neutral"), _SB["neutral"])
                        src   = row_a.get("source","")
                        sc    = _SC.get(src, "#64748b")
                        url   = row_a.get("url","")
                        title = row_a.get("title","")[:200]
                        t_html = (f'<a href="{url}" target="_blank" style="color:#e2e8f0;text-decoration:none">{title}</a>'
                                  if url else f'<span style="color:#e2e8f0">{title}</span>')
                        st.markdown(
                            f"<div style='background:#1e293b;border-radius:7px;padding:8px 12px;margin-bottom:5px'>"
                            f"{badge} <span style='background:{sc}22;color:{sc};padding:1px 6px;"
                            f"border-radius:8px;font-size:0.71rem;border:1px solid {sc}44'>{src}</span> "
                            f"<span style='color:#64748b;font-size:0.76rem'>{row_a.get('date','')}</span><br>"
                            f"<span style='font-size:0.86rem'>{t_html}</span></div>",
                            unsafe_allow_html=True,
                        )

        if load_ann and symbol_guess:
            with st.spinner(f"Fetching BSE announcements for {symbol_guess}…"):
                bse_code = get_bse_code(symbol_guess)
                if bse_code:
                    ann_df = fetch_bse_announcements(bse_code, ann_days)
                    if ann_df.empty:
                        st.info("No announcements found for this period.")
                    else:
                        st.markdown(f"**{len(ann_df)} announcements (last {ann_days} days)**")
                        for _, row in ann_df.head(20).iterrows():
                            st.markdown(
                                f"<div style='background:#1e293b;border-radius:8px;padding:10px 14px;"
                                f"margin-bottom:6px'>"
                                f"<span style='color:#64748b;font-size:0.78rem'>{row.get('Date','')} · "
                                f"{row.get('Category','')}</span><br>"
                                f"<span style='color:#e2e8f0;font-size:0.88rem'>{row.get('Headline','')}</span>"
                                f"</div>",
                                unsafe_allow_html=True,
                            )
                else:
                    st.warning(f"Could not find BSE code for {symbol_guess}.")

        if not load_btn and not load_ann:
            st.markdown(
                "<div style='text-align:center;color:#475569;padding:60px 0'>"
                "Search for a company on the left to load detailed financials from Screener.in"
                "</div>",
                unsafe_allow_html=True,
            )


# ── TAB 7: Heatmap ────────────────────────────────────────────────────────────
with tab7:
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
  body {{ margin:0; padding:0; background:#07111d; overflow:hidden; }}
  #chart {{ width:100%; height:610px; }}
</style>
</head>
<body>
<div id="chart"></div>
<script>
var chart = echarts.init(document.getElementById('chart'), 'dark', {{renderer:'canvas'}});
var treeData = {tree_json};

var option = {{
  backgroundColor: '#07111d',
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
    "<div style='text-align:center;color:#334155;font-size:0.72rem;padding:12px 0;"
    "border-top:1px solid #0d1e30;margin-top:8px'>"
    "📊 Data: Yahoo Finance (NSE, ~15min delay) &nbsp;·&nbsp; "
    "🤖 AI: Groq llama-3.3-70b &nbsp;·&nbsp; "
    "📰 News: Groww · Google News · ET · Moneycontrol &nbsp;·&nbsp; "
    "🔍 Financials: Screener.in &nbsp;·&nbsp; "
    "<b style='color:#1e3a5f'>Not financial advice</b>"
    "</div>",
    unsafe_allow_html=True,
)
