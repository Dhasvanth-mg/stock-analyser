"""
NSE Stock Analyser — Dashboard Home
"""

import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv
from utils import inject_css, render_header, render_nav, _CHART_BG
from user_data import load_watchlist, save_watchlist

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
/* ── Kill ALL Streamlit chrome + dead space ─────────────── */
.main .block-container         { padding-top:.2rem !important; }
header[data-testid="stHeader"] { display:none !important; }
#MainMenu                      { display:none !important; }
.stDeployButton                { display:none !important; }
/* Sidebar + toggle arrow */
section[data-testid="stSidebar"]           { display:none !important; }
[data-testid="collapsedControl"]           { display:none !important; }
button[data-testid="stBaseButton-minimal"] { display:none !important; }
/* Status bar / spinner strip under header */
[data-testid="stStatusWidget"]             { display:none !important; }
.stAppViewBlockContainer > div:first-child > div[data-testid="stVerticalBlock"]
  > div[style*="height: 0"]               { display:none !important; }
/* Kill the thin progress bar Streamlit injects */
.stApp > div:first-child                   { padding-top:0 !important; }
iframe[title="streamlit_app_bar"]          { display:none !important; }

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

render_nav("app.py")

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
def _batch_index_quotes(tickers: tuple) -> dict:
    """One v7 batch request for all index tickers; crumb-free spark fallback."""
    from data_fetcher import _yf_session, _spark_batch
    session, crumb = _yf_session()
    out = {}
    if session and crumb:
        params = {
            "symbols":    ",".join(tickers),
            "formatted":  "false",
            "corsDomain": "finance.yahoo.com",
            "crumb":      crumb,
        }
        try:
            r = session.get(
                "https://query2.finance.yahoo.com/v7/finance/quote",
                params=params, timeout=20,
            )
            for q in r.json().get("quoteResponse", {}).get("result", []):
                sym = q.get("symbol", "")
                p   = q.get("regularMarketPrice") or 0
                pc  = q.get("regularMarketPreviousClose") or p
                out[sym] = (round(p, 2), round(((p - pc) / pc * 100) if pc else 0, 2))
        except Exception:
            pass
    missing = [t for t in tickers if t not in out]
    if missing:
        out.update(_spark_batch(missing))
    for t in tickers:
        out.setdefault(t, (0.0, 0.0))
    return out

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

# Fetch all index quotes in one batch request
_idx_tickers = tuple(t for _, t in INDICES)
quotes = _batch_index_quotes(_idx_tickers)

# ── Watchlist (up to 4 favourites) ───────────────────────────────────────────
@st.cache_data(ttl=120, show_spinner=False)
def _wl_quote(sym: str):
    """Fast price + change + sparkline for a watchlist symbol."""
    from data_fetcher import _yf_session, _spark_batch
    price, chg, name = 0.0, 0.0, sym

    # v7 batch API first (needs valid crumb)
    session, crumb = _yf_session()
    if session and crumb:
        params = {"symbols": f"{sym}.NS", "formatted": "false",
                  "corsDomain": "finance.yahoo.com", "crumb": crumb}
        try:
            r  = session.get("https://query2.finance.yahoo.com/v7/finance/quote",
                             params=params, timeout=10)
            qs = r.json().get("quoteResponse", {}).get("result", [])
            if qs:
                q     = qs[0]
                price = q.get("regularMarketPrice") or 0
                pc    = q.get("regularMarketPreviousClose") or price
                chg   = ((price - pc) / pc * 100) if pc else 0
                name  = q.get("longName") or q.get("shortName") or sym
        except Exception:
            pass

    # Fallback: crumb-free spark API
    if not price:
        sp = _spark_batch([f"{sym}.NS"])
        price, chg = sp.get(f"{sym}.NS", (0.0, 0.0))

    # Sparkline via history (separate call, less blocked)
    intra = pd.DataFrame()
    try:
        hist = yf.Ticker(f"{sym}.NS").history(period="5d", interval="5m")
        hist.index = pd.to_datetime(hist.index)
        today = hist.index.max().date() if not hist.empty else None
        intra = hist[hist.index.date == today] if today else pd.DataFrame()
    except Exception:
        pass

    return {"sym": sym, "name": (name or sym)[:22],
            "price": round(price, 2), "chg": round(chg, 2), "hist": intra}

if "watchlist" not in st.session_state:
    st.session_state["watchlist"] = load_watchlist()

# ── Index strip ───────────────────────────────────────────────────────────────
st.markdown('<div class="section-hd">Major Indices</div>', unsafe_allow_html=True)
_ic = st.columns(len(INDICES))
for (name, ticker), col in zip(INDICES, _ic):
    p, chg = quotes[ticker]
    cc = "#10b981" if chg >= 0 else "#ef4444"
    fp = (f"{p/1000:.1f}K" if p >= 10000 else f"{p:,.1f}") if p else "—"
    chg_html = (f"{'▲' if chg>=0 else '▼'} {abs(chg):.2f}%") if p else "—"
    chg_color = cc if p else "#64748b"
    with col:
        st.markdown(
            f"<div class='idx-card'>"
            f"<div class='idx-name'>{name}</div>"
            f"<div class='idx-val'>{fp}</div>"
            f"<div class='idx-chg' style='color:{chg_color}'>{chg_html}</div>"
            f"</div>", unsafe_allow_html=True)

st.markdown("")

# ── Main layout: Chart+Intraday (left) | Movers (right) ──────────────────────
col_left, col_right = st.columns([3, 1], gap="medium")

with col_left:
    # Section heading + period picker inline
    _ph1, _ph2 = st.columns([3, 1])
    _ph1.markdown('<div class="section-hd" style="margin-top:6px">NIFTY 50</div>',
                  unsafe_allow_html=True)
    period_sel = _ph2.selectbox(
        "Period", list(PERIOD_MAP.keys()), index=2,
        key="nifty_period", label_visibility="collapsed"
    )
    yf_period, yf_interval = PERIOD_MAP[period_sel]

    with st.spinner("Loading chart…"):
        df_n50 = _nifty50(yf_period, yf_interval)
    p50, c50 = quotes.get("^NSEI", (0, 0))

    if not df_n50.empty:
        df_n50["SMA20"] = df_n50["Close"].rolling(20).mean()
        df_n50["SMA50"] = df_n50["Close"].rolling(50).mean()

        fig = go.Figure()
        # Intraday (1D/1W) → area line; multi-day → candlestick
        if period_sel in ("1D", "1W"):
            cc_line = "#10b981" if c50 >= 0 else "#ef4444"
            _lo  = df_n50["Close"].min(); _hi = df_n50["Close"].max()
            _pad = max((_hi - _lo) * 0.2, _lo * 0.001)
            _fc  = f"rgba({'16,185,129' if c50>=0 else '239,68,68'},.07)"
            # Invisible baseline
            fig.add_trace(go.Scatter(
                x=df_n50.index, y=[_lo - _pad * 0.5] * len(df_n50),
                mode="lines", line=dict(width=0, color="rgba(0,0,0,0)"),
                showlegend=False, hoverinfo="skip",
            ))
            fig.add_trace(go.Scatter(
                x=df_n50.index, y=df_n50["Close"], mode="lines",
                name="NIFTY 50", line=dict(color=cc_line, width=2),
                fill="tonexty", fillcolor=_fc,
                hovertemplate="<b>%{y:,.2f}</b><br>%{x}<extra></extra>",
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

        _yaxis_cfg = dict(gridcolor="#0d1e30", zerolinecolor="#0d1e30", tickformat=",.0f")
        if period_sel in ("1D", "1W"):
            _yaxis_cfg["range"] = [_lo - _pad, _hi + _pad]

        fig.update_layout(
            template="plotly_dark", paper_bgcolor=_CHART_BG, plot_bgcolor=_CHART_BG,
            height=360, margin=dict(l=0, r=0, t=10, b=0),
            xaxis_rangeslider_visible=False,
            xaxis=dict(gridcolor="#0d1e30", zerolinecolor="#0d1e30"),
            yaxis=_yaxis_cfg,
            legend=dict(orientation="h", y=1.04, font=dict(size=10)),
            hovermode="x unified",
            hoverlabel=dict(bgcolor="#0d1e30", bordercolor="#1e3450",
                            font=dict(size=12, color="#e2e8f0")),
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
        fill  = "rgba(16,185,129,.10)" if is_up else "rgba(239,68,68,.10)"
        fig2  = go.Figure()
        y_range = None
        if not df.empty:
            lo  = df["Close"].min()
            hi  = df["Close"].max()
            pad = max((hi - lo) * 0.25, lo * 0.001)
            y_range = [lo - pad, hi + pad]
            # Invisible baseline so fill stays near the data, not going to 0
            fig2.add_trace(go.Scatter(
                x=df.index, y=[lo - pad * 0.5] * len(df),
                mode="lines", line=dict(width=0, color="rgba(0,0,0,0)"),
                showlegend=False, hoverinfo="skip",
            ))
            # Actual price line — fills to the baseline above
            fig2.add_trace(go.Scatter(
                x=df.index, y=df["Close"],
                mode="lines",
                line=dict(color=color, width=1.8),
                fill="tonexty", fillcolor=fill,
                showlegend=False,
                name="",
                hovertemplate="<b>%{y:,.2f}</b><br>%{x}<extra></extra>",
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
                       tickformat=",.0f", showline=False,
                       range=y_range),
            showlegend=False,
            hoverlabel=dict(bgcolor="#0d1e30", bordercolor="#1e3450",
                            font=dict(size=11, color="#e2e8f0")),
            hovermode="x unified",
        )
        return fig2

    for row_indices in [INDICES[:4], INDICES[4:]]:
        _sc = st.columns(4)
        for (name, ticker), col in zip(row_indices, _sc):
            p_i, chg_i = quotes.get(ticker, (0, 0))
            df_i = _intraday(ticker)
            cc_i = "#10b981" if chg_i >= 0 else "#ef4444"
            price_str  = f"{p_i:,.2f}" if p_i else "—"
            chg_str    = f"{'▲' if chg_i>=0 else '▼'}{abs(chg_i):.2f}%" if p_i else "—"
            chg_color_i = cc_i if p_i else "#64748b"
            with col:
                st.markdown(
                    f"<div class='idx-mini'>"
                    f"<div style='display:flex;justify-content:space-between'>"
                    f"<span style='font-size:.66rem;font-weight:700;color:#475569;text-transform:uppercase'>{name}</span>"
                    f"<span style='font-size:.75rem;font-weight:700;color:{chg_color_i}'>{chg_str}</span>"
                    f"</div>"
                    f"<div style='font-size:.85rem;font-weight:700;color:#e2e8f0'>{price_str}</div>"
                    f"</div>", unsafe_allow_html=True)
                if not df_i.empty and p_i:
                    st.plotly_chart(_spark(df_i, chg_i), use_container_width=True,
                                    config={"displayModeBar": False})
                else:
                    st.markdown(
                        "<div style='height:70px;display:flex;align-items:center;"
                        "justify-content:center;color:#1e3450;font-size:.72rem'>"
                        "No data</div>", unsafe_allow_html=True)

    # ── Watchlist — below intraday charts ─────────────────────────────────
    wl = st.session_state["watchlist"]
    _wh1, _wh2 = st.columns([2, 1])
    _wh1.markdown('<div class="section-hd">⭐ Watchlist</div>', unsafe_allow_html=True)
    with _wh2.popover("✏️ Edit", use_container_width=True):
        st.markdown("**Add stock (NSE symbol)**")
        _new = st.text_input("", placeholder="e.g. WIPRO", key="wl_add",
                              label_visibility="collapsed").upper().strip()
        if st.button("➕ Add", use_container_width=True) and _new:
            if _new not in wl and len(wl) < 4:
                st.session_state["watchlist"].append(_new)
                save_watchlist(st.session_state["watchlist"])
                st.cache_data.clear(); st.rerun()
            elif len(wl) >= 4:
                st.warning("Max 4 stocks")
        if wl:
            st.markdown("**Remove**")
            for _s in list(wl):
                if st.button(f"✕ {_s}", key=f"rm_{_s}", use_container_width=True):
                    st.session_state["watchlist"].remove(_s)
                    save_watchlist(st.session_state["watchlist"])
                    st.rerun()

    # 4 watchlist cards in a single row
    _wl_cols = st.columns(4)
    for i, _sym in enumerate(wl):
        _d  = _wl_quote(_sym)
        _cc = "#10b981" if _d["chg"] >= 0 else "#ef4444"
        _ar = "▲" if _d["chg"] >= 0 else "▼"
        with _wl_cols[i]:
            st.markdown(
                f"<div style='background:#0d1e30;border:1px solid #1e3450;"
                f"border-radius:9px;padding:8px 10px'>"
                f"<div style='font-size:.85rem;font-weight:700;color:#e2e8f0'>{_d['sym']}</div>"
                f"<div style='font-size:.65rem;color:#64748b;margin-bottom:3px'>{_d['name']}</div>"
                f"<div style='font-size:.9rem;font-weight:700;color:#e2e8f0'>₹{_d['price']:,.0f}</div>"
                f"<div style='font-size:.75rem;font-weight:700;color:{_cc}'>{_ar}{abs(_d['chg']):.2f}%</div>"
                f"</div>", unsafe_allow_html=True)
            if not _d["hist"].empty:
                _lo = _d["hist"]["Close"].min(); _hi = _d["hist"]["Close"].max()
                _pd = max((_hi-_lo)*.3, _lo*.001)
                _fw = go.Figure()
                _fw.add_trace(go.Scatter(
                    x=_d["hist"].index, y=[_lo-_pd*.5]*len(_d["hist"]),
                    mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"))
                _lc = "#10b981" if _d["chg"]>=0 else "#ef4444"
                _fw.add_trace(go.Scatter(
                    x=_d["hist"].index, y=_d["hist"]["Close"], mode="lines",
                    line=dict(color=_lc, width=1.4),
                    fill="tonexty", fillcolor=f"rgba({'16,185,129' if _d['chg']>=0 else '239,68,68'},.08)",
                    showlegend=False, name="",
                    hovertemplate="<b>%{y:,.2f}</b> %{x}<extra></extra>"))
                _fw.update_layout(
                    paper_bgcolor="#0d1e30", plot_bgcolor="#0d1e30",
                    height=65, margin=dict(l=0,r=0,t=2,b=0),
                    xaxis=dict(visible=False),
                    yaxis=dict(visible=False, range=[_lo-_pd, _hi+_pd]),
                    showlegend=False, hovermode="x unified",
                    hoverlabel=dict(bgcolor="#0d1e30", font=dict(size=10, color="#e2e8f0")))
                st.plotly_chart(_fw, use_container_width=True,
                                config={"displayModeBar": False})

# ── Movers (right column) ─────────────────────────────────────────────────────
with col_right:
    from data_fetcher import fetch_stock_batch, get_all_symbols
    with st.spinner("Loading movers…"):
        mdf = fetch_stock_batch(get_all_symbols("Blue Chip"))

    if not mdf.empty:
        gainers = mdf[mdf["Change %"] > 0].sort_values("Change %", ascending=False).head(6)
        losers  = mdf[mdf["Change %"] < 0].sort_values("Change %").head(6)

        def _card(r, is_gain):
            cc  = "#10b981" if is_gain else "#ef4444"
            chg = f"+{r['Change %']:.2f}%" if is_gain else f"{r['Change %']:.2f}%"
            pe  = f"{r['P/E']:.1f}"  if r["P/E"]  else "—"
            pb  = f"{r['P/B']:.2f}"  if r["P/B"]  else "—"
            bt  = f"{r['Beta']:.2f}" if r["Beta"] else "—"
            eps = f"₹{r['EPS']:.2f}" if r["EPS"]  else "—"
            return f"""
<div class="mover-wrap">
  <div class="mover-card">
    <div><div class="mover-sym">{r['Symbol']}</div>
    <div class="mover-name">{r['Name'][:22]}</div></div>
    <div style="text-align:right">
      <div class="mover-chg" style="color:{cc}">{chg}</div>
      <div style="font-size:.7rem;color:#64748b">₹{r['Price (₹)']:,.0f}</div>
    </div>
  </div>
  <div class="mover-tip">
    <div style="font-weight:700;color:#e2e8f0;margin-bottom:6px;font-size:.8rem">{r['Symbol']}</div>
    <div style="color:#64748b;font-size:.68rem;margin-bottom:5px">{r['Name'][:32]}</div>
    <div class="tip-row"><span class="tip-label">Price</span><span class="tip-val">₹{r['Price (₹)']:,.2f}</span></div>
    <div class="tip-row"><span class="tip-label">Change</span><span class="tip-val" style="color:{cc}">{chg}</span></div>
    <div class="tip-row"><span class="tip-label">Mkt Cap</span><span class="tip-val">₹{r['Mkt Cap (₹Cr)']:,.0f} Cr</span></div>
    <div class="tip-row"><span class="tip-label">P/E</span><span class="tip-val">{pe}</span></div>
    <div class="tip-row"><span class="tip-label">P/B</span><span class="tip-val">{pb}</span></div>
    <div class="tip-row"><span class="tip-label">EPS</span><span class="tip-val">{eps}</span></div>
    <div class="tip-row"><span class="tip-label">Beta</span><span class="tip-val">{bt}</span></div>
    <div class="tip-row"><span class="tip-label">52W H/L</span>
      <span class="tip-val">₹{r['52W High']:,.0f} / ₹{r['52W Low']:,.0f}</span></div>
    <div class="tip-row"><span class="tip-label">Volume</span><span class="tip-val">{r['Volume']:,}</span></div>
  </div>
</div>"""

        st.markdown(
            '<div style="font-size:.72rem;font-weight:700;color:#34d399;margin-bottom:4px">▲ TOP GAINERS</div>',
            unsafe_allow_html=True)
        for _, r in gainers.iterrows():
            st.markdown(_card(r, True), unsafe_allow_html=True)

        st.markdown(
            '<div style="font-size:.72rem;font-weight:700;color:#f87171;margin:8px 0 4px">▼ TOP LOSERS</div>',
            unsafe_allow_html=True)
        for _, r in losers.iterrows():
            st.markdown(_card(r, False), unsafe_allow_html=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(
    "<div style='text-align:center;color:#1e3450;font-size:.65rem;"
    "padding:10px 0;border-top:1px solid #0d1e30;margin-top:10px'>"
    "Yahoo Finance (~15min) · Groq · Groww/ET/Moneycontrol · Screener.in · Not financial advice"
    "</div>", unsafe_allow_html=True)
