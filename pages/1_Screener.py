"""Stock Screener — filters, sliders, sortable table, CSV export."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv
from utils import inject_css, render_header, page_cfg, render_nav

from data_fetcher import fetch_stock_batch, get_all_symbols

load_dotenv()
page_cfg("Screener · NSE")
inject_css()
render_header("📋 Stock Screener", "Filter · Sort · Export")
render_nav("pages/1_Screener.py")

# ── Session state ─────────────────────────────────────────────────────────────
if "cap_filter" not in st.session_state:
    st.session_state["cap_filter"] = "Blue Chip"

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### FILTERS")
    sector_ph = st.empty()
    st.markdown("### PRICE (₹)")
    price_range = st.slider("Price", 0, 50000, (0, 50000), step=100, label_visibility="collapsed")
    st.markdown("### REVENUE (₹ Cr)")
    rev_range = st.slider("Revenue", 0, 500000, (0, 500000), step=1000, label_visibility="collapsed")
    st.markdown("### MARKET CAP (₹ Cr)")
    mc_range = st.slider("MktCap", 0, 2000000, (0, 2000000), step=5000, label_visibility="collapsed")
    st.markdown("### P/E RATIO")
    pe_range = st.slider("PE", 0.0, 200.0, (0.0, 200.0), step=1.0, label_visibility="collapsed")
    st.markdown("### DISPLAY")
    sort_col = st.selectbox("Sort by", ["Mkt Cap (₹Cr)", "Price (₹)", "Change %", "Revenue (₹Cr)", "P/E", "EPS"])
    sort_asc = st.checkbox("Ascending", value=False)
    max_rows = st.slider("Max rows", 10, 500, 50, step=10)
    st.markdown("---")
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear(); st.rerun()

# ── Cap filter pills ──────────────────────────────────────────────────────────
_CAPS  = ["All", "Blue Chip", "Large Cap", "Mid Cap", "Small Cap"]
_ICONS = {"All":"🌐","Blue Chip":"🔵","Large Cap":"🟢","Mid Cap":"🟡","Small Cap":"🔴"}
st.markdown('<div class="cap-bar"><span class="cap-label">Cap Filter</span>',
            unsafe_allow_html=True)
for cap, col in zip(_CAPS, st.columns(len(_CAPS))):
    with col:
        if st.button(f"{_ICONS[cap]} {cap}", use_container_width=True,
                     type="primary" if st.session_state["cap_filter"] == cap else "secondary",
                     key=f"scr_cap_{cap}"):
            st.session_state["cap_filter"] = cap; st.rerun()
st.markdown('</div>', unsafe_allow_html=True)
cap_filter = st.session_state["cap_filter"]

# ── Load + filter ─────────────────────────────────────────────────────────────
symbols = get_all_symbols(cap_filter)
_prog = st.progress(0, text=f"Loading {len(symbols)} stocks…")
df = fetch_stock_batch(symbols)
_prog.empty()

if df.empty:
    st.error("No data. Check connection."); st.stop()

all_sectors      = sorted(df["Sector"].dropna().unique().tolist())
selected_sectors = sector_ph.multiselect("Sectors", all_sectors, default=all_sectors)

mask = (
    df["Price (₹)"].between(*price_range) &
    df["Revenue (₹Cr)"].between(*rev_range) &
    df["Mkt Cap (₹Cr)"].between(*mc_range) &
    df["P/E"].between(*pe_range) &
    df["Sector"].isin(selected_sectors)
)
filtered = df[mask].sort_values(sort_col, ascending=sort_asc).head(max_rows)

# ── Stats bar ─────────────────────────────────────────────────────────────────
_g = int((filtered["Change %"] > 0).sum())
_l = int((filtered["Change %"] < 0).sum())
_pe = filtered["P/E"].replace(0, pd.NA).mean()
_mc = filtered["Mkt Cap (₹Cr)"].sum()
_ac = filtered["Change %"].mean()
_cc = "sc-green" if _ac >= 0 else "sc-red"

st.markdown(f"""
<div class="stats-bar">
  <div class="stat-chip card-accent-blue">
    <div class="sc-label">Stocks</div>
    <div class="sc-value sc-blue">{len(filtered)}</div>
    <div class="sc-sub">of {len(df)} loaded</div>
  </div>
  <div class="stat-chip card-accent-green">
    <div class="sc-label">Gainers</div>
    <div class="sc-value sc-green">{_g}</div>
    <div class="sc-sub">{_g/max(len(filtered),1)*100:.0f}% of shown</div>
  </div>
  <div class="stat-chip card-accent-red">
    <div class="sc-label">Losers</div>
    <div class="sc-value sc-red">{_l}</div>
    <div class="sc-sub">{len(filtered)-_g-_l} flat</div>
  </div>
  <div class="stat-chip card-accent-amber">
    <div class="sc-label">Avg P/E</div>
    <div class="sc-value sc-amber">{f"{_pe:.1f}" if pd.notna(_pe) else "—"}</div>
    <div class="sc-sub">valuation</div>
  </div>
  <div class="stat-chip">
    <div class="sc-label">Avg Change</div>
    <div class="sc-value {_cc}">{_ac:+.2f}%</div>
    <div class="sc-sub">today</div>
  </div>
  <div class="stat-chip">
    <div class="sc-label">Total Mkt Cap</div>
    <div class="sc-value">₹{_mc/1e5:.1f}L Cr</div>
    <div class="sc-sub">combined</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Table ─────────────────────────────────────────────────────────────────────
st.markdown(f'<div class="section-hd">{len(filtered)} stocks · sorted by {sort_col}</div>',
            unsafe_allow_html=True)

display_cols = ["Symbol","Name","Cap Category","Sector","Price (₹)","Change %",
                "Mkt Cap (₹Cr)","Revenue (₹Cr)","P/E","P/B","EPS","Div Yield %",
                "Beta","52W High","52W Low","Volume"]
disp = filtered[display_cols].reset_index(drop=True)

def _chg(v):
    if isinstance(v, float):
        return f"color:{'#10b981' if v>0 else ('#ef4444' if v<0 else '#64748b')};font-weight:600"
    return ""

def _cap(v):
    return {"Blue Chip":"background:rgba(59,130,246,.12);color:#60a5fa",
            "Large Cap": "background:rgba(16,185,129,.12);color:#34d399",
            "Mid Cap":   "background:rgba(245,158,11,.12);color:#fbbf24",
            "Small Cap": "background:rgba(239,68,68,.12);color:#f87171",
            }.get(v, "")

_fmt = {"Price (₹)":"₹{:.2f}","Change %":"{:+.2f}%",
        "Mkt Cap (₹Cr)":"₹{:,.0f}","Revenue (₹Cr)":"₹{:,.0f}",
        "P/E":"{:.1f}","P/B":"{:.2f}","EPS":"₹{:.2f}",
        "Div Yield %":"{:.2f}%","52W High":"₹{:.2f}",
        "52W Low":"₹{:.2f}","Volume":"{:,}"}
_s = disp.style.format(_fmt).set_properties(**{"background-color":"#07111d","color":"#e2e8f0"})
# pandas ≥2.1 renamed applymap → map; support both
_cell = "map" if hasattr(_s, "map") else "applymap"
styled = getattr(_s, _cell)(_chg, subset=["Change %"])
styled = getattr(styled, _cell)(_cap, subset=["Cap Category"])

st.dataframe(styled, use_container_width=True, height=540)
st.download_button("⬇️ Export CSV", disp.to_csv(index=False), "nse_stocks.csv", "text/csv")

