"""
NSE Stock Analyser — Dashboard Home
· Nav tabs under header (no sidebar)
· NIFTY 50 full chart on the right
· Index intraday sparklines
· Movers with hover tooltips (P/E, P/B, Beta etc.)
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

# ── CSS: remove top gap, hide sidebar nav & deploy button ─────────────────────
inject_css()
st.markdown("""
<style>
/* Kill the white/dark gap Streamlit adds above the page */
.main .block-container { padding-top: 0.4rem !important; }
header[data-testid="stHeader"]         { display:none !important; }
section[data-testid="stSidebarNavItems"]{ display:none !important; }
.stDeployButton                        { display:none !important; }
#MainMenu                              { display:none !important; }

/* Nav bar */
.nav-bar {
  display:flex; gap:6px; background:#0d1e30;
  border:1px solid #1e3450; border-radius:12px;
  padding:6px 10px; margin-bottom:.8rem; flex-wrap:wrap;
}
.nav-bar .stButton>button {
  border-radius:8px !important; font-size:.77rem !important;
  font-weight:600 !important; padding:4px 14px !important;
  border:none !important; background:transparent !important;
  color:#64748b !important; transition:all .15s !important;
}
.nav-bar .stButton>button:hover {
  background:#142438 !important; color:#e2e8f0 !important;
}
.nav-active .stButton>button {
  background:#142438 !important; color:#60a5fa !important;
  border:1px solid #1e3450 !important;
}

/* Mover card hover tooltip */
.mover-wrap { position:relative; }
.mover-tip {
  display:none; position:absolute; left:0; top:calc(100% + 4px);
  background:#0d1e30; border:1px solid #1e3450; border-radius:9px;
  padding:10px 14px; z-index:9999; min-width:220px;
  font-size:.76rem; color:#e2e8f0; white-space:nowrap;
  box-shadow:0 8px 32px rgba(0,0,0,.6);
}
.mover-wrap:hover .mover-tip { display:block; }
.tip-row { display:flex; justify-content:space-between; padding:2px 0; }
.tip-label { color:#64748b; }
.tip-val   { color:#e2e8f0; font-weight:600; }

/* Index mini card */
.idx-mini {
  background:#0d1e30; border:1px solid #1e3450; border-radius:10px;
  padding:9px 12px 4px; margin-bottom:0;
}
</style>
""", unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────────────────────────────
render_header("📈 NSE Stock Analyser", "Live dashboard · AI-powered · NSE · BSE")

# ── Navigation tabs ────────────────────────────────────────────────────────────
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
_nav_cols = st.columns(len(_PAGES))
for i, (label, path) in enumerate(_PAGES):
    with _nav_cols[i]:
        _cls = "nav-active" if path is None else ""
        st.markdown(f'<div class="{_cls}">', unsafe_allow_html=True)
        if st.button(label, key=f"nav_{i}", use_container_width=True):
            if path:
                st.switch_page(path)
        st.markdown('</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# ── Search bar ─────────────────────────────────────────────────────────────────
_sq1, _sq2 = st.columns([6, 1])
with _sq1:
    search_q = st.text_input("", placeholder="🔍  Search any stock — Reliance, HDFC Bank, Infosys…",
                              label_visibility="collapsed", key="home_search")
with _sq2:
    if st.button("Search →", use_container_width=True, type="primary"):
        if search_q:
            st.switch_page("pages/6_Deep_Search.py")

# ── Data helpers ───────────────────────────────────────────────────────────────
INDICES = [
    ("NIFTY 50",       "^NSEI"),
    ("SENSEX",         "^BSESN"),
    ("NIFTY Bank",     "^NSEBANK"),
    ("NIFTY IT",       "^CNXIT"),
    ("NIFTY Pharma",   "^CNXPHARMA"),
    ("NIFTY Midcap",   "^CNXMDCP100"),
    ("NIFTY Smallcap", "^CNXSC"),
    ("NIFTY Auto",     "^CNXAUTO"),
]

@st.cache_data(ttl=300, show_spinner=False)
def _quote(ticker):
    try:
        info = yf.Ticker(ticker).info
        p = info.get("regularMarketPrice") or info.get("currentPrice") or 0
        c = info.get("regularMarketPreviousClose") or info.get("previousClose") or p
        chg = ((p - c) / c * 100) if c else 0
        return round(p, 2), round(chg, 2)
    except Exception:
        return 0.0, 0.0

@st.cache_data(ttl=300, show_spinner=False)
def _intraday(ticker):
    try:
        df = yf.Ticker(ticker).history(period="5d", interval="5m")
        if df.empty: return pd.DataFrame()
        df.index = pd.to_datetime(df.index)
        today = df.index.max().date()
        d = df[df.index.date == today]
        return d if not d.empty else df.tail(78)  # fallback: last trading session
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=900, show_spinner=False)
def _nifty50_history():
    try:
        df = yf.Ticker("^NSEI").history(period="3mo", interval="1d")
        df.index = pd.to_datetime(df.index)
        return df
    except Exception:
        return pd.DataFrame()

# ── Fetch quotes ───────────────────────────────────────────────────────────────
quotes = {t: _quote(t) for _, t in INDICES}

# ── Index strip ────────────────────────────────────────────────────────────────
st.markdown('<div class="section-hd">Major Indices</div>', unsafe_allow_html=True)
_idx_cols = st.columns(len(INDICES))
for (name, ticker), col in zip(INDICES, _idx_cols):
    p, chg = quotes[ticker]
    cc = "#10b981" if chg >= 0 else "#ef4444"
    ar = "▲" if chg >= 0 else "▼"
    fp = f"{p:,.2f}" if p > 100 else f"{p:.2f}"
    with col:
        st.markdown(
            f"<div class='idx-card'>"
            f"<div class='idx-name'>{name}</div>"
            f"<div class='idx-val'>{fp}</div>"
            f"<div class='idx-chg' style='color:{cc}'>{ar} {abs(chg):.2f}%</div>"
            f"</div>", unsafe_allow_html=True)

st.markdown("")

# ── Main section: NIFTY 50 chart (left) + movers (right) ─────────────────────
col_chart, col_movers = st.columns([3, 1])

with col_chart:
    st.markdown('<div class="section-hd">NIFTY 50 — 3 Month</div>', unsafe_allow_html=True)
    n50 = _nifty50_history()
    if not n50.empty:
        n50["SMA20"] = n50["Close"].rolling(20).mean()
        n50["SMA50"] = n50["Close"].rolling(50).mean()
        fig_n50 = go.Figure()
        fig_n50.add_trace(go.Candlestick(
            x=n50.index, open=n50["Open"], high=n50["High"],
            low=n50["Low"], close=n50["Close"], name="NIFTY 50",
            increasing_line_color="#10b981", decreasing_line_color="#ef4444",
            increasing_fillcolor="#10b981", decreasing_fillcolor="#ef4444",
        ))
        fig_n50.add_trace(go.Scatter(x=n50.index, y=n50["SMA20"], name="SMA 20",
                                     line=dict(color="#60a5fa", width=1.5)))
        fig_n50.add_trace(go.Scatter(x=n50.index, y=n50["SMA50"], name="SMA 50",
                                     line=dict(color="#f59e0b", width=1.5)))
        p50, c50 = quotes.get("^NSEI", (0, 0))
        cc50 = "#10b981" if c50 >= 0 else "#ef4444"
        fig_n50.update_layout(
            template="plotly_dark", paper_bgcolor=_CHART_BG, plot_bgcolor=_CHART_BG,
            height=380, margin=dict(l=0, r=0, t=10, b=0),
            xaxis_rangeslider_visible=False,
            xaxis=dict(gridcolor="#0d1e30", zerolinecolor="#0d1e30"),
            yaxis=dict(gridcolor="#0d1e30", zerolinecolor="#0d1e30"),
            legend=dict(orientation="h", y=1.04, font=dict(size=11)),
            annotations=[dict(
                x=0.01, y=0.97, xref="paper", yref="paper",
                text=f"<b>{p50:,.2f}</b>  <span style='color:{cc50}'>{c50:+.2f}%</span>",
                showarrow=False, font=dict(size=14, color="#e2e8f0"),
                bgcolor="rgba(13,30,48,.8)", bordercolor="#1e3450",
                borderwidth=1, borderpad=6,
            )],
        )
        st.plotly_chart(fig_n50, use_container_width=True)

with col_movers:
    from data_fetcher import fetch_stock_batch, get_all_symbols
    with st.spinner("Loading movers…"):
        mdf = fetch_stock_batch(get_all_symbols("Blue Chip"))

    if not mdf.empty:
        gainers = mdf[mdf["Change %"] > 0].sort_values("Change %", ascending=False).head(6)
        losers  = mdf[mdf["Change %"] < 0].sort_values("Change %").head(6)

        def _mover_html(r, is_gain):
            chg_c = "#10b981" if is_gain else "#ef4444"
            chg_s = f"+{r['Change %']:.2f}%" if is_gain else f"{r['Change %']:.2f}%"
            pe    = f"{r['P/E']:.1f}"  if r['P/E']  else "—"
            pb    = f"{r['P/B']:.2f}"  if r['P/B']  else "—"
            beta  = f"{r['Beta']:.2f}" if r['Beta'] else "—"
            eps   = f"₹{r['EPS']:.2f}" if r['EPS'] else "—"
            mcap  = f"₹{r['Mkt Cap (₹Cr)']:,.0f} Cr"
            vol   = f"{r['Volume']:,}"
            return f"""
<div class="mover-wrap">
  <div class="mover-card">
    <div>
      <div class="mover-sym">{r['Symbol']}</div>
      <div class="mover-name">{r['Name'][:22]}</div>
    </div>
    <div style="text-align:right">
      <div class="mover-chg" style="color:{chg_c}">{chg_s}</div>
      <div style="font-size:.7rem;color:#64748b">₹{r['Price (₹)']:,.0f}</div>
    </div>
  </div>
  <div class="mover-tip">
    <div style="font-weight:700;color:#e2e8f0;margin-bottom:6px">{r['Symbol']} — {r['Name'][:28]}</div>
    <div class="tip-row"><span class="tip-label">Price</span><span class="tip-val">₹{r['Price (₹)']:,.2f}</span></div>
    <div class="tip-row"><span class="tip-label">Change</span><span class="tip-val" style="color:{chg_c}">{chg_s}</span></div>
    <div class="tip-row"><span class="tip-label">Mkt Cap</span><span class="tip-val">{mcap}</span></div>
    <div class="tip-row"><span class="tip-label">P/E</span><span class="tip-val">{pe}</span></div>
    <div class="tip-row"><span class="tip-label">P/B</span><span class="tip-val">{pb}</span></div>
    <div class="tip-row"><span class="tip-label">EPS</span><span class="tip-val">{eps}</span></div>
    <div class="tip-row"><span class="tip-label">Beta</span><span class="tip-val">{beta}</span></div>
    <div class="tip-row"><span class="tip-label">52W H/L</span><span class="tip-val">₹{r['52W High']:,.0f} / ₹{r['52W Low']:,.0f}</span></div>
    <div class="tip-row"><span class="tip-label">Volume</span><span class="tip-val">{vol}</span></div>
  </div>
</div>"""

        st.markdown('<div style="font-size:.72rem;font-weight:700;color:#34d399;margin-bottom:6px">▲ TOP GAINERS</div>',
                    unsafe_allow_html=True)
        for _, r in gainers.iterrows():
            st.markdown(_mover_html(r, True), unsafe_allow_html=True)

        st.markdown('<div style="font-size:.72rem;font-weight:700;color:#f87171;margin:10px 0 6px">▼ TOP LOSERS</div>',
                    unsafe_allow_html=True)
        for _, r in losers.iterrows():
            st.markdown(_mover_html(r, False), unsafe_allow_html=True)

# ── Intraday charts grid ───────────────────────────────────────────────────────
st.markdown('<div class="section-hd">Intraday Charts (5-min · Today)</div>', unsafe_allow_html=True)

def _spark(df, name, chg):
    is_up = chg >= 0
    color = "#10b981" if is_up else "#ef4444"
    fill  = "rgba(16,185,129,.08)" if is_up else "rgba(239,68,68,.08)"
    fig = go.Figure()
    if not df.empty:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["Close"], mode="lines",
            line=dict(color=color, width=1.8),
            fill="tozeroy", fillcolor=fill,
            hovertemplate="<b>%{x|%H:%M}</b><br>%{y:,.2f}<extra></extra>",
        ))
    fig.update_layout(
        paper_bgcolor="#0d1e30", plot_bgcolor="#0d1e30",
        height=120, margin=dict(l=4, r=4, t=4, b=4),
        xaxis=dict(showgrid=False, showticklabels=True, tickfont=dict(size=8, color="#64748b"),
                   showline=False, tickformat="%H:%M"),
        yaxis=dict(showgrid=True, gridcolor="#142438", showticklabels=True,
                   tickfont=dict(size=8, color="#64748b"), showline=False, tickformat=",.0f"),
        showlegend=False,
        hoverlabel=dict(bgcolor="#0d1e30", bordercolor="#1e3450", font_size=11),
    )
    return fig

_all_rows = [INDICES[:4], INDICES[4:]]
for _row in _all_rows:
    _cols = st.columns(4)
    for (name, ticker), col in zip(_row, _cols):
        p, chg = quotes.get(ticker, (0, 0))
        df_i   = _intraday(ticker)
        is_up  = chg >= 0
        with col:
            st.markdown(
                f"<div class='idx-mini'>"
                f"<div style='display:flex;justify-content:space-between;align-items:center'>"
                f"<span style='font-size:.68rem;font-weight:700;color:#64748b;text-transform:uppercase'>{name}</span>"
                f"<span style='font-size:.78rem;font-weight:700;color:{'#10b981' if is_up else '#ef4444'}'>"
                f"{'▲' if is_up else '▼'} {abs(chg):.2f}%</span>"
                f"</div>"
                f"<div style='font-size:.9rem;font-weight:700;color:#e2e8f0;margin:1px 0'>{p:,.2f}</div>"
                f"</div>", unsafe_allow_html=True)
            if not df_i.empty:
                st.plotly_chart(_spark(df_i, name, chg), use_container_width=True,
                                config={"displayModeBar": False})
            else:
                st.markdown(
                    "<div style='height:80px;display:flex;align-items:center;justify-content:center;"
                    "color:#1e3450;font-size:.75rem'>No intraday data</div>",
                    unsafe_allow_html=True)

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown(
    "<div style='text-align:center;color:#1e3450;font-size:.68rem;"
    "padding:12px 0;border-top:1px solid #0d1e30;margin-top:12px'>"
    "Yahoo Finance (~15min delay) · Groq AI · Groww / ET / Moneycontrol · Screener.in · Not financial advice"
    "</div>", unsafe_allow_html=True)
