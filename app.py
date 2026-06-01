"""
NSE Stock Analyser — Dashboard Home
"""

import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv
from utils import inject_css, render_header, _CHART_BG

load_dotenv()

st.set_page_config(
    page_title="NSE Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_css()
st.markdown("""
<style>
/* ── Kill ALL the Streamlit chrome ──────────────────────── */
.main .block-container        { padding-top:.3rem !important; }
header[data-testid="stHeader"]{ display:none !important; }
#MainMenu                     { display:none !important; }
.stDeployButton               { display:none !important; }
/* Sidebar + its toggle arrow */
section[data-testid="stSidebar"]          { display:none !important; }
[data-testid="collapsedControl"]          { display:none !important; }
button[data-testid="stBaseButton-minimal"]{ display:none !important; }

/* ── Nav bar ────────────────────────────────────────────── */
.nav-bar{display:flex;gap:5px;background:#0d1e30;border:1px solid #1e3450;
  border-radius:12px;padding:5px 8px;margin-bottom:.6rem;flex-wrap:nowrap;
  align-items:center;overflow-x:auto}
.nav-bar .stButton>button{
  border-radius:8px!important;font-size:.75rem!important;font-weight:600!important;
  padding:4px 12px!important;border:none!important;background:transparent!important;
  color:#64748b!important;transition:all .15s!important;white-space:nowrap!important}
.nav-bar .stButton>button:hover{background:#142438!important;color:#e2e8f0!important}
.nav-active .stButton>button{background:#142438!important;color:#60a5fa!important;
  border:1px solid #1e3450!important}

/* ── Period selector ────────────────────────────────────── */
div[data-testid="stRadio"]>div[role="radiogroup"]{
  display:flex;gap:4px;flex-wrap:nowrap}
div[data-testid="stRadio"]>div[role="radiogroup"]>label{
  background:#0d1e30;border:1px solid #1e3450;border-radius:6px;
  padding:3px 10px;cursor:pointer;color:#64748b;font-size:.73rem;
  font-weight:600;transition:all .15s}
div[data-testid="stRadio"]>div[role="radiogroup"]>label:hover{
  background:#142438;color:#e2e8f0;border-color:#3b82f6}
div[data-testid="stRadio"]>div[role="radiogroup"]>label[data-checked="true"]{
  background:#142438;color:#60a5fa;border-color:#3b82f6}
div[data-testid="stRadio"] p{display:none}

/* ── Mover hover tooltip ────────────────────────────────── */
.mover-wrap{position:relative}
.mover-tip{display:none;position:absolute;left:0;top:calc(100% + 4px);
  background:#0d1e30;border:1px solid #1e3450;border-radius:9px;
  padding:10px 14px;z-index:9999;min-width:210px;font-size:.74rem;
  color:#e2e8f0;box-shadow:0 8px 32px rgba(0,0,0,.7)}
.mover-wrap:hover .mover-tip{display:block}
.tip-row{display:flex;justify-content:space-between;padding:2px 0;gap:12px}
.tip-label{color:#64748b}.tip-val{color:#e2e8f0;font-weight:600}

/* ── Index number no-wrap ───────────────────────────────── */
.idx-val{white-space:nowrap!important;overflow:hidden;text-overflow:ellipsis}

/* ── Intraday card ──────────────────────────────────────── */
.idx-mini{background:#0d1e30;border:1px solid #1e3450;border-radius:9px;
  padding:7px 10px 2px}
</style>
""", unsafe_allow_html=True)

render_header("📈 NSE Stock Analyser", "Live dashboard · AI-powered · NSE · BSE")

# ── Nav bar (replaces sidebar) ────────────────────────────────────────────────
_PAGES = [
    ("🏠 Dashboard",   None),
    ("📋 Screener",    "pages/1_Screener.py"),
    ("🤖 AI Analysis", "pages/2_AI_Analysis.py"),
    ("⚖️ Compare",     "pages/3_Compare.py"),
    ("📰 News",        "pages/4_News.py"),
    ("🔍 Deep Search", "pages/6_Deep_Search.py"),
    ("🗂️ Heatmap",     "pages/5_Heatmap.py"),
]
st.markdown('<div class="nav-bar">', unsafe_allow_html=True)
_nc = st.columns(len(_PAGES))
for i, (label, path) in enumerate(_PAGES):
    with _nc[i]:
        st.markdown(f'<div class="{"nav-active" if not path else ""}">',
                    unsafe_allow_html=True)
        if st.button(label, key=f"nav_{i}", use_container_width=True):
            if path: st.switch_page(path)
        st.markdown('</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# ── Search bar ────────────────────────────────────────────────────────────────
_s1, _s2 = st.columns([6, 1])
with _s1:
    search_q = st.text_input("", placeholder="🔍  Search any stock — Reliance, HDFC Bank, Infosys…",
                              label_visibility="collapsed", key="home_search")
with _s2:
    if st.button("Search →", use_container_width=True, type="primary") and search_q:
        st.switch_page("pages/6_Deep_Search.py")

# ── Index definitions ─────────────────────────────────────────────────────────
INDICES = [
    ("NIFTY 50",    "^NSEI"),
    ("SENSEX",      "^BSESN"),
    ("NIFTY Bank",  "^NSEBANK"),
    ("NIFTY IT",    "^CNXIT"),
    ("Pharma",      "^CNXPHARMA"),
    ("Midcap",      "^CNXMDCP100"),
    ("Smallcap",    "^CNXSC"),
    ("Auto",        "^CNXAUTO"),
]

PERIOD_MAP = {
    "1D":  ("1d",   "5m"),
    "1W":  ("5d",   "30m"),
    "1M":  ("1mo",  "1d"),
    "3M":  ("3mo",  "1d"),
    "6M":  ("6mo",  "1d"),
    "YTD": ("ytd",  "1d"),
    "1Y":  ("1y",   "1d"),
    "All": ("max",  "1wk"),
}

# ── Data helpers ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def _quote(ticker):
    try:
        info = yf.Ticker(ticker).info
        p  = info.get("regularMarketPrice") or info.get("currentPrice") or 0
        pc = info.get("regularMarketPreviousClose") or info.get("previousClose") or p
        return round(p, 2), round(((p - pc) / pc * 100) if pc else 0, 2)
    except Exception:
        return 0.0, 0.0

@st.cache_data(ttl=300, show_spinner=False)
def _nifty50(period="3mo", interval="1d"):
    try:
        df = yf.Ticker("^NSEI").history(period=period, interval=interval)
        df.index = pd.to_datetime(df.index)
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=300, show_spinner=False)
def _intraday(ticker):
    try:
        df = yf.Ticker(ticker).history(period="5d", interval="5m")
        if df.empty: return pd.DataFrame()
        df.index = pd.to_datetime(df.index)
        today = df.index.max().date()
        d = df[df.index.date == today]
        return d if not d.empty else df.tail(78)
    except Exception:
        return pd.DataFrame()

# Fetch all quotes upfront
quotes = {t: _quote(t) for _, t in INDICES}

# ── Index strip ───────────────────────────────────────────────────────────────
st.markdown('<div class="section-hd">Major Indices</div>', unsafe_allow_html=True)
_ic = st.columns(len(INDICES))
for (name, ticker), col in zip(INDICES, _ic):
    p, chg = quotes[ticker]
    cc = "#10b981" if chg >= 0 else "#ef4444"
    # Format large numbers compactly
    fp = (f"{p/1000:.1f}K" if p >= 10000 else f"{p:,.1f}") if p else "—"
    with col:
        st.markdown(
            f"<div class='idx-card'>"
            f"<div class='idx-name'>{name}</div>"
            f"<div class='idx-val'>{fp}</div>"
            f"<div class='idx-chg' style='color:{cc}'>{'▲' if chg>=0 else '▼'} {abs(chg):.2f}%</div>"
            f"</div>", unsafe_allow_html=True)

st.markdown("")

# ── Main layout: Chart+Intraday (left) | Movers (right) ──────────────────────
col_left, col_right = st.columns([3, 1], gap="medium")

with col_left:
    # Period selector
    st.markdown('<div class="section-hd">NIFTY 50</div>', unsafe_allow_html=True)
    period_sel = st.radio("", list(PERIOD_MAP.keys()), index=2,
                          horizontal=True, key="nifty_period",
                          label_visibility="collapsed")
    yf_period, yf_interval = PERIOD_MAP[period_sel]

    df_n50 = _nifty50(yf_period, yf_interval)
    p50, c50 = quotes.get("^NSEI", (0, 0))

    if not df_n50.empty:
        df_n50["SMA20"] = df_n50["Close"].rolling(20).mean()
        df_n50["SMA50"] = df_n50["Close"].rolling(50).mean()

        fig = go.Figure()
        # Intraday (1D/1W) → area line; multi-day → candlestick
        if period_sel in ("1D", "1W"):
            cc_line = "#10b981" if c50 >= 0 else "#ef4444"
            fig.add_trace(go.Scatter(
                x=df_n50.index, y=df_n50["Close"], mode="lines",
                name="NIFTY 50", line=dict(color=cc_line, width=2),
                fill="tozeroy", fillcolor=f"rgba({'16,185,129' if c50>=0 else '239,68,68'},.06)",
                hovertemplate="%{x}<br><b>%{y:,.2f}</b><extra></extra>",
            ))
        else:
            fig.add_trace(go.Candlestick(
                x=df_n50.index, open=df_n50["Open"], high=df_n50["High"],
                low=df_n50["Low"], close=df_n50["Close"], name="NIFTY 50",
                increasing_line_color="#10b981", decreasing_line_color="#ef4444",
                increasing_fillcolor="#10b981", decreasing_fillcolor="#ef4444",
            ))
            fig.add_trace(go.Scatter(x=df_n50.index, y=df_n50["SMA20"],
                name="SMA 20", line=dict(color="#60a5fa", width=1.4)))
            fig.add_trace(go.Scatter(x=df_n50.index, y=df_n50["SMA50"],
                name="SMA 50", line=dict(color="#f59e0b", width=1.4)))

        fig.update_layout(
            template="plotly_dark", paper_bgcolor=_CHART_BG, plot_bgcolor=_CHART_BG,
            height=360, margin=dict(l=0, r=0, t=10, b=0),
            xaxis_rangeslider_visible=False,
            xaxis=dict(gridcolor="#0d1e30", zerolinecolor="#0d1e30"),
            yaxis=dict(gridcolor="#0d1e30", zerolinecolor="#0d1e30",
                       tickformat=",.0f"),
            legend=dict(orientation="h", y=1.04, font=dict(size=10)),
            hoverlabel=dict(bgcolor="#0d1e30", bordercolor="#1e3450", font_size=12),
            annotations=[dict(
                x=0.01, y=0.97, xref="paper", yref="paper",
                text=f"<b>{p50:,.2f}</b>  "
                     f"<span style='color:{'#10b981' if c50>=0 else '#ef4444'}'>"
                     f"{c50:+.2f}%</span>",
                showarrow=False, font=dict(size=13, color="#e2e8f0"),
                bgcolor="rgba(13,30,48,.85)", bordercolor="#1e3450",
                borderwidth=1, borderpad=5,
            )],
        )
        st.plotly_chart(fig, use_container_width=True,
                        config={"displayModeBar": False})

    # ── Intraday charts — 4-wide grid ──────────────────────────────────────
    st.markdown('<div class="section-hd">Intraday (5-min · Today)</div>',
                unsafe_allow_html=True)

    def _spark(df, chg):
        is_up = chg >= 0
        color = "#10b981" if is_up else "#ef4444"
        fill  = "rgba(16,185,129,.07)" if is_up else "rgba(239,68,68,.07)"
        fig2  = go.Figure()
        if not df.empty:
            fig2.add_trace(go.Scatter(
                x=df.index, y=df["Close"], mode="lines",
                line=dict(color=color, width=1.6),
                fill="tozeroy", fillcolor=fill,
                hovertemplate="%{x|%H:%M}  %{y:,.2f}<extra></extra>",
            ))
        fig2.update_layout(
            paper_bgcolor="#0d1e30", plot_bgcolor="#0d1e30",
            height=110, margin=dict(l=2, r=2, t=2, b=2),
            xaxis=dict(showgrid=False, showticklabels=True,
                       tickfont=dict(size=8, color="#475569"),
                       tickformat="%H:%M", showline=False),
            yaxis=dict(showgrid=True, gridcolor="#142438",
                       showticklabels=True,
                       tickfont=dict(size=8, color="#475569"),
                       tickformat=",.0f", showline=False),
            showlegend=False,
            hoverlabel=dict(bgcolor="#0d1e30", font_size=10),
        )
        return fig2

    for row_indices in [INDICES[:4], INDICES[4:]]:
        _sc = st.columns(4)
        for (name, ticker), col in zip(row_indices, _sc):
            p_i, chg_i = quotes.get(ticker, (0, 0))
            df_i = _intraday(ticker)
            cc_i = "#10b981" if chg_i >= 0 else "#ef4444"
            with col:
                st.markdown(
                    f"<div class='idx-mini'>"
                    f"<div style='display:flex;justify-content:space-between'>"
                    f"<span style='font-size:.66rem;font-weight:700;color:#475569;text-transform:uppercase'>{name}</span>"
                    f"<span style='font-size:.75rem;font-weight:700;color:{cc_i}'>{'▲' if chg_i>=0 else '▼'}{abs(chg_i):.2f}%</span>"
                    f"</div>"
                    f"<div style='font-size:.85rem;font-weight:700;color:#e2e8f0'>{p_i:,.2f}</div>"
                    f"</div>", unsafe_allow_html=True)
                if not df_i.empty:
                    st.plotly_chart(_spark(df_i, chg_i), use_container_width=True,
                                    config={"displayModeBar": False})
                else:
                    st.markdown(
                        "<div style='height:70px;display:flex;align-items:center;"
                        "justify-content:center;color:#1e3450;font-size:.72rem'>"
                        "No intraday data</div>", unsafe_allow_html=True)

# ── Right column: movers ──────────────────────────────────────────────────────
with col_right:
    from data_fetcher import fetch_stock_batch, get_all_symbols
    with st.spinner("Loading movers…"):
        mdf = fetch_stock_batch(get_all_symbols("Blue Chip"))

    if not mdf.empty:
        gainers = (mdf[mdf["Change %"] > 0]
                   .sort_values("Change %", ascending=False).head(7))
        losers  = (mdf[mdf["Change %"] < 0]
                   .sort_values("Change %").head(7))

        def _card(r, is_gain):
            cc  = "#10b981" if is_gain else "#ef4444"
            chg = f"+{r['Change %']:.2f}%" if is_gain else f"{r['Change %']:.2f}%"
            pe  = f"{r['P/E']:.1f}"  if r["P/E"]  else "—"
            pb  = f"{r['P/B']:.2f}"  if r["P/B"]  else "—"
            bt  = f"{r['Beta']:.2f}" if r["Beta"] else "—"
            eps = f"₹{r['EPS']:.2f}" if r["EPS"]  else "—"
            mc  = f"₹{r['Mkt Cap (₹Cr)']:,.0f} Cr"
            hi  = f"₹{r['52W High']:,.0f}"
            lo  = f"₹{r['52W Low']:,.0f}"
            vol = f"{r['Volume']:,}"
            return f"""
<div class="mover-wrap">
  <div class="mover-card">
    <div>
      <div class="mover-sym">{r['Symbol']}</div>
      <div class="mover-name">{r['Name'][:22]}</div>
    </div>
    <div style="text-align:right">
      <div class="mover-chg" style="color:{cc}">{chg}</div>
      <div style="font-size:.7rem;color:#64748b">₹{r['Price (₹)']:,.0f}</div>
    </div>
  </div>
  <div class="mover-tip">
    <div style="font-weight:700;color:#e2e8f0;margin-bottom:6px;font-size:.8rem">{r['Symbol']}</div>
    <div style="color:#64748b;font-size:.68rem;margin-bottom:6px">{r['Name'][:32]}</div>
    <div class="tip-row"><span class="tip-label">Price</span><span class="tip-val">₹{r['Price (₹)']:,.2f}</span></div>
    <div class="tip-row"><span class="tip-label">Change</span><span class="tip-val" style="color:{cc}">{chg}</span></div>
    <div class="tip-row"><span class="tip-label">Mkt Cap</span><span class="tip-val">{mc}</span></div>
    <div class="tip-row"><span class="tip-label">P/E</span><span class="tip-val">{pe}</span></div>
    <div class="tip-row"><span class="tip-label">P/B</span><span class="tip-val">{pb}</span></div>
    <div class="tip-row"><span class="tip-label">EPS</span><span class="tip-val">{eps}</span></div>
    <div class="tip-row"><span class="tip-label">Beta</span><span class="tip-val">{bt}</span></div>
    <div class="tip-row"><span class="tip-label">52W H/L</span><span class="tip-val">{hi} / {lo}</span></div>
    <div class="tip-row"><span class="tip-label">Volume</span><span class="tip-val">{vol}</span></div>
  </div>
</div>"""

        st.markdown(
            '<div class="section-hd" style="margin-top:4px">Biggest Movers · NIFTY 50</div>',
            unsafe_allow_html=True)
        st.markdown(
            '<div style="font-size:.72rem;font-weight:700;color:#34d399;margin-bottom:5px">▲ TOP GAINERS</div>',
            unsafe_allow_html=True)
        for _, r in gainers.iterrows():
            st.markdown(_card(r, True), unsafe_allow_html=True)

        st.markdown(
            '<div style="font-size:.72rem;font-weight:700;color:#f87171;margin:10px 0 5px">▼ TOP LOSERS</div>',
            unsafe_allow_html=True)
        for _, r in losers.iterrows():
            st.markdown(_card(r, False), unsafe_allow_html=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(
    "<div style='text-align:center;color:#1e3450;font-size:.65rem;"
    "padding:10px 0;border-top:1px solid #0d1e30;margin-top:10px'>"
    "Yahoo Finance (~15min) · Groq · Groww/ET/Moneycontrol · Screener.in · Not financial advice"
    "</div>", unsafe_allow_html=True)
