"""
NSE Stock Analyser — Dashboard (Home Page)
· Search bar → Deep Search
· Major index 1-day charts (NIFTY 50, SENSEX, Bank, IT, Pharma, Midcap, Smallcap, Auto)
· Day's largest movers (gainers + losers)
"""

import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed

from utils import inject_css, render_header, page_cfg, chart_layout, _CHART_BG

load_dotenv()

page_cfg("NSE Dashboard")
inject_css()
render_header("📈 NSE Stock Analyser", "Live dashboard · NSE · BSE · AI-powered")

# ── Prominent search bar ──────────────────────────────────────────────────────
st.markdown('<div class="section-hd">🔍 Quick Search</div>', unsafe_allow_html=True)
_sc1, _sc2 = st.columns([5, 1])
with _sc1:
    search_q = st.text_input("", placeholder="Search any stock — e.g. Reliance, HDFC Bank, Infosys…",
                              label_visibility="collapsed", key="home_search")
with _sc2:
    go_search = st.button("Search →", use_container_width=True, type="primary")

if go_search and search_q:
    st.switch_page("pages/6_Deep_Search.py")

# ── Index definitions ─────────────────────────────────────────────────────────
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
def fetch_index_today(ticker: str):
    try:
        df = yf.Ticker(ticker).history(period="5d", interval="5m")
        if df.empty:
            return pd.DataFrame()
        df.index = pd.to_datetime(df.index)
        # Keep only today's data
        today = df.index.max().date()
        df = df[df.index.date == today]
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=300, show_spinner=False)
def fetch_index_quote(ticker: str):
    try:
        info = yf.Ticker(ticker).info
        price = info.get("regularMarketPrice") or info.get("currentPrice") or 0
        prev  = info.get("regularMarketPreviousClose") or info.get("previousClose") or price
        chg   = ((price - prev) / prev * 100) if prev else 0
        return round(price, 2), round(chg, 2)
    except Exception:
        return 0.0, 0.0


def _mini_line(df: pd.DataFrame, name: str, is_up: bool) -> go.Figure:
    color = "#10b981" if is_up else "#ef4444"
    fig = go.Figure(go.Scatter(
        x=df.index, y=df["Close"],
        mode="lines",
        line=dict(color=color, width=2),
        fill="tozeroy",
        fillcolor=f"rgba({'16,185,129' if is_up else '239,68,68'},.08)",
        hovertemplate="%{x|%H:%M}<br>%{y:,.2f}<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor=_CHART_BG, plot_bgcolor=_CHART_BG,
        height=90, margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        showlegend=False,
    )
    return fig


# ── Index overview strip ──────────────────────────────────────────────────────
st.markdown('<div class="section-hd">Major Indices — Today</div>', unsafe_allow_html=True)

_idx_cols = st.columns(len(INDICES))
_quotes   = {}
for (name, ticker), col in zip(INDICES, _idx_cols):
    price, chg = fetch_index_quote(ticker)
    _quotes[ticker] = (price, chg)
    chg_color = "#10b981" if chg >= 0 else "#ef4444"
    arrow     = "▲" if chg >= 0 else "▼"
    with col:
        fmt_price = f"{price:,.2f}" if price > 100 else f"{price:.2f}"
        st.markdown(
            f"<div class='idx-card'>"
            f"<div class='idx-name'>{name}</div>"
            f"<div class='idx-val'>{fmt_price}</div>"
            f"<div class='idx-chg' style='color:{chg_color}'>{arrow} {abs(chg):.2f}%</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

# ── Index intraday charts ─────────────────────────────────────────────────────
st.markdown('<div class="section-hd">Intraday Charts (5-min)</div>', unsafe_allow_html=True)

_chart_rows = [INDICES[:4], INDICES[4:]]
for _row in _chart_rows:
    _cols = st.columns(4)
    for (name, ticker), col in zip(_row, _cols):
        df_idx = fetch_index_today(ticker)
        price, chg = _quotes.get(ticker, (0, 0))
        is_up = chg >= 0
        with col:
            st.markdown(
                f"<div style='background:var(--bg-card);border:1px solid var(--border);"
                f"border-radius:10px;padding:10px 12px 4px'>"
                f"<div style='font-size:.7rem;font-weight:700;color:var(--muted);"
                f"text-transform:uppercase;letter-spacing:.08em'>{name}</div>"
                f"<div style='font-size:.85rem;font-weight:700;color:var(--text)'>"
                f"{'▲' if is_up else '▼'} {abs(chg):.2f}%</div></div>",
                unsafe_allow_html=True,
            )
            if not df_idx.empty:
                st.plotly_chart(_mini_line(df_idx, name, is_up),
                                use_container_width=True, config={"displayModeBar": False})
            else:
                st.caption("Data unavailable")

# ── Movers: top gainers + losers ──────────────────────────────────────────────
st.markdown('<div class="section-hd">Day\'s Biggest Movers — NIFTY 50</div>',
            unsafe_allow_html=True)

from data_fetcher import fetch_stock_batch, get_all_symbols

with st.spinner("Loading NIFTY 50 movers…"):
    _nifty50_syms = get_all_symbols("Blue Chip")
    _movers_df    = fetch_stock_batch(_nifty50_syms)

if not _movers_df.empty:
    _gainers = (_movers_df[_movers_df["Change %"] > 0]
                .sort_values("Change %", ascending=False).head(7))
    _losers  = (_movers_df[_movers_df["Change %"] < 0]
                .sort_values("Change %").head(7))

    _mc1, _mc2 = st.columns(2)

    with _mc1:
        st.markdown("<div style='font-size:.75rem;font-weight:700;color:#34d399;"
                    "margin-bottom:8px'>🔼 TOP GAINERS</div>", unsafe_allow_html=True)
        for _, r in _gainers.iterrows():
            st.markdown(
                f"<div class='mover-card'>"
                f"<div>"
                f"<div class='mover-sym'>{r['Symbol']}</div>"
                f"<div class='mover-name'>{r['Name'][:28]}</div>"
                f"</div>"
                f"<div style='text-align:right'>"
                f"<div class='mover-chg chg-up'>+{r['Change %']:.2f}%</div>"
                f"<div style='font-size:.72rem;color:var(--muted)'>₹{r['Price (₹)']:,.2f}</div>"
                f"</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    with _mc2:
        st.markdown("<div style='font-size:.75rem;font-weight:700;color:#f87171;"
                    "margin-bottom:8px'>🔽 TOP LOSERS</div>", unsafe_allow_html=True)
        for _, r in _losers.iterrows():
            st.markdown(
                f"<div class='mover-card'>"
                f"<div>"
                f"<div class='mover-sym'>{r['Symbol']}</div>"
                f"<div class='mover-name'>{r['Name'][:28]}</div>"
                f"</div>"
                f"<div style='text-align:right'>"
                f"<div class='mover-chg chg-dn'>{r['Change %']:.2f}%</div>"
                f"<div style='font-size:.72rem;color:var(--muted)'>₹{r['Price (₹)']:,.2f}</div>"
                f"</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(
    "<div style='text-align:center;color:#1e3450;font-size:.7rem;padding:14px 0;"
    "border-top:1px solid #0d1e30;margin-top:16px'>"
    "Data: Yahoo Finance (~15min delay) · AI: Groq · News: Groww / ET / Moneycontrol "
    "· Financials: Screener.in · Not financial advice"
    "</div>",
    unsafe_allow_html=True,
)
