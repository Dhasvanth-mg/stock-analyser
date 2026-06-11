"""Deep Search — Screener.in financials, charts, live data, sentiment."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv
from utils import inject_css, render_header, page_cfg, render_nav, candle_with_rsi, _CHART_BG

from screener_search import search_screener, fetch_company_data, fetch_bse_announcements, get_bse_code
from data_fetcher import fetch_single_stock, resolve_and_fetch_history, fetch_financials_yf
from news_fetcher import get_news_summary
from ai_analyst import get_ai_analysis

load_dotenv()
page_cfg("Deep Search · NSE")
inject_css()
render_header("🔍 Deep Search", "Screener.in financials · Live chart · AI signal · News sentiment")
render_nav("pages/6_Deep_Search.py")

# Prefill from home page if coming from search
_default_q = st.session_state.get("home_search", "")

# ── Search bar ────────────────────────────────────────────────────────────────
sc1, sc2 = st.columns([5, 1])
with sc1:
    query = st.text_input("", placeholder="Search company name or symbol…",
                          value=_default_q, label_visibility="collapsed")
with sc2:
    do_search = st.button("Search →", use_container_width=True, type="primary")

results = search_screener(query) if query else []

left, right = st.columns([1, 2])

with left:
    if results:
        opts = {r["name"]: r["url"] for r in results if r.get("type") == "equity"}
        if not opts:
            opts = {r["name"]: r["url"] for r in results}

        chosen_name = st.selectbox("Results", list(opts.keys()),
                                   label_visibility="collapsed")
        chosen_url  = opts[chosen_name]
        consolidated = st.checkbox("Consolidated financials", value=True)
        if consolidated and not chosen_url.endswith("consolidated/"):
            chosen_url = chosen_url.rstrip("/") + "/consolidated/"

        symbol_guess = chosen_url.split("/company/")[-1].split("/")[0]

        load_btn = st.button("📊 Load Financials", use_container_width=True, type="primary")

        st.markdown("---")
        st.markdown('<div class="section-hd">BSE Announcements</div>',
                    unsafe_allow_html=True)
        ann_days = st.slider("Days back", 7, 90, 30)
        load_ann = st.button("📢 Load Announcements", use_container_width=True)
    elif query:
        st.info("No results — try a different name or ticker.")
        load_btn = load_ann = False
        chosen_url = symbol_guess = ""; ann_days = 30
    else:
        st.markdown(
            "<div style='color:#1e3450;font-size:.82rem;padding:30px 0'>"
            "Type a company name or NSE symbol to search Screener.in</div>",
            unsafe_allow_html=True)
        load_btn = load_ann = False
        chosen_url = symbol_guess = ""; ann_days = 30

with right:
    if load_btn and chosen_url:
        with st.spinner("Fetching from Screener.in…"):
            data = fetch_company_data(chosen_url)

        if not data:
            st.error("Could not load data from Screener.in."); st.stop()

        # Determine NSE symbol early (needed by multiple sections)
        _nse = data.get("nse_code", "").strip()
        _sym = _nse or symbol_guess

        # Company banner
        st.markdown(
            f"<div class='card card-accent-blue'>"
            f"<span style='font-size:1.15rem;font-weight:700;color:#e2e8f0'>{data.get('name','')}</span>"
            f"<span style='color:#64748b;font-size:.8rem;margin-left:10px'>"
            f"<a href='https://www.screener.in{chosen_url}' target='_blank' "
            f"style='color:#60a5fa'>Open on Screener.in ↗</a></span></div>",
            unsafe_allow_html=True)

        # Key ratios (from Screener.in static HTML — usually loads fine)
        ratios = data.get("ratios", {})
        if ratios:
            st.markdown('<div class="section-hd">Key Ratios</div>', unsafe_allow_html=True)
            rcols = st.columns(4)
            for i, (k, v) in enumerate(list(ratios.items())[:12]):
                rcols[i % 4].metric(k, v)

        # Pros & Cons (from Screener.in static HTML)
        pros, cons = data.get("pros", []), data.get("cons", [])
        if pros or cons:
            pc1, pc2 = st.columns(2)
            with pc1:
                if pros:
                    st.markdown("**✅ Strengths**")
                    for p in pros[:5]:
                        st.markdown(
                            f"<div style='background:rgba(16,185,129,.08);border:1px solid "
                            f"rgba(16,185,129,.2);border-radius:7px;padding:6px 10px;"
                            f"margin-bottom:4px;font-size:.82rem;color:#34d399'>{p}</div>",
                            unsafe_allow_html=True)
            with pc2:
                if cons:
                    st.markdown("**⚠️ Weaknesses**")
                    for c in cons[:5]:
                        st.markdown(
                            f"<div style='background:rgba(239,68,68,.08);border:1px solid "
                            f"rgba(239,68,68,.2);border-radius:7px;padding:6px 10px;"
                            f"margin-bottom:4px;font-size:.82rem;color:#f87171'>{c}</div>",
                            unsafe_allow_html=True)

        # ── Financial tables (yfinance — works on all environments) ───────────
        st.markdown('<div class="section-hd">📊 Financials <span style="font-size:.72rem;color:#475569;font-weight:400">via yfinance · ₹ Cr</span></div>',
                    unsafe_allow_html=True)

        with st.spinner(f"Loading financials for {_sym}…"):
            fin = fetch_financials_yf(_sym)

        ft = st.tabs(["Quarterly","P&L","Balance Sheet","Cash Flow","Ratios","Shareholding"])

        def _tbl(df, label="data"):
            if isinstance(df, pd.DataFrame) and not df.empty:
                st.dataframe(
                    df.style.set_properties(**{"background-color":"#07111d","color":"#e2e8f0"}),
                    use_container_width=True)
            else:
                st.info(f"No {label} available for {_sym}.")

        with ft[0]: _tbl(fin.get("quarterly", pd.DataFrame()), "quarterly results")
        with ft[1]: _tbl(fin.get("pnl",       pd.DataFrame()), "P&L data")
        with ft[2]: _tbl(fin.get("balance_sheet", pd.DataFrame()), "balance sheet")
        with ft[3]: _tbl(fin.get("cash_flow",  pd.DataFrame()), "cash flow")
        with ft[4]: _tbl(fin.get("fin_ratios", pd.DataFrame()), "ratio data")
        with ft[5]:
            sh = fin.get("shareholding", pd.DataFrame())
            _tbl(sh, "shareholding")
            # yfinance major_holders gives % insider / institutional — show as bar
            if not sh.empty and "Value" in sh.columns:
                try:
                    vals = sh["Value"].astype(str).str.replace("%", "").str.strip()
                    nums = pd.to_numeric(vals, errors="coerce").dropna()
                    cats = sh.loc[nums.index, "Category"].astype(str)
                    if not nums.empty:
                        fig_sh = go.Figure(go.Bar(
                            x=cats.tolist(), y=nums.tolist(),
                            marker_color=["#3b82f6","#10b981","#f59e0b","#ef4444"],
                            text=[f"{v:.1f}%" for v in nums.tolist()],
                            textposition="outside"))
                        fig_sh.update_layout(
                            paper_bgcolor="#07111d", plot_bgcolor="#07111d",
                            template="plotly_dark", height=280,
                            margin=dict(l=0, r=0, t=20, b=0),
                            yaxis=dict(showgrid=False),
                            font=dict(color="#94a3b8"))
                        st.plotly_chart(fig_sh, use_container_width=True)
                except Exception:
                    pass

        # Price chart
        st.markdown('<div class="section-hd">📈 Price Chart</div>', unsafe_allow_html=True)
        dp = st.radio("Period", ["1mo","3mo","6mo","1y","2y"], index=2,
                      horizontal=True, key="ds_per")
        with st.spinner(f"Loading chart for {_sym}…"):
            hist, ticker = resolve_and_fetch_history(_sym, dp)
        if hist.empty and _sym != symbol_guess:
            with st.spinner(f"Trying {symbol_guess}…"):
                hist, ticker = resolve_and_fetch_history(symbol_guess, dp)
        if not hist.empty:
            st.caption(f"Ticker: `{ticker}`")
            st.plotly_chart(candle_with_rsi(hist, ticker, dp), use_container_width=True)
        else:
            st.warning(f"No price history found for {_sym}. May be delisted or have a different ticker.")

        # Live metrics
        st.markdown('<div class="section-hd">📡 Live Market Data</div>', unsafe_allow_html=True)
        live = fetch_single_stock(_nse or symbol_guess)
        if not live and (_nse or symbol_guess) != symbol_guess:
            live = fetch_single_stock(symbol_guess)
        if live:
            r1c = st.columns(4)
            r1c[0].metric("Price",   f"₹{live['Price (₹)']:,.2f}", f"{live['Change %']:+.2f}%")
            r1c[1].metric("Mkt Cap", f"₹{live['Mkt Cap (₹Cr)']:,.0f} Cr")
            r1c[2].metric("P/E",     f"{live['P/E']:.1f}")
            r1c[3].metric("Revenue", f"₹{live['Revenue (₹Cr)']:,.0f} Cr")
            r2c = st.columns(4)
            r2c[0].metric("P/B",      f"{live['P/B']:.2f}")
            r2c[1].metric("EPS",      f"₹{live['EPS']:.2f}")
            r2c[2].metric("Div Yield",f"{live['Div Yield %']:.2f}%")
            r2c[3].metric("Beta",     f"{live['Beta']:.2f}")
        else:
            st.info("Live data not available via yfinance for this stock.")

        # AI signal
        st.markdown('<div class="section-hd">🤖 AI Signal (Groq)</div>', unsafe_allow_html=True)
        if st.button("Run AI Analysis", type="primary"):
            row = live or {}
            if not row:
                row = {"Symbol": symbol_guess, "Name": data.get("name",""),
                       "Sector":"—","Cap Category":"—","Price (₹)":0,"Change %":0,
                       "P/E":0,"P/B":0,"EPS":0,"Mkt Cap (₹Cr)":0,"Revenue (₹Cr)":0,
                       "Net Inc (₹Cr)":0,"Div Yield %":0,"Beta":0,
                       "52W High":0,"52W Low":0}
            with st.spinner("Analysing…"):
                ns  = get_news_summary(symbol_guess, data.get("name",""))
                sig = get_ai_analysis(row, news_summary=ns)
            if sig.startswith("AI analysis unavailable"):
                st.error(f"Groq error: {sig.split(':', 1)[-1].strip()}\n\n"
                         "Check that **GROQ_API_KEY** is set in Streamlit Secrets "
                         "(app settings → Secrets) or in your local `.env`.")
            else:
                label = ("BUY" if "BUY" in sig.upper()[:30]
                         else "SELL" if "SELL" in sig.upper()[:30] else "HOLD")
                bc = {"BUY":"badge-buy","SELL":"badge-sell","HOLD":"badge-hold"}[label]
                st.markdown(f'<span class="badge {bc}">{label}</span>', unsafe_allow_html=True)
                st.info(sig)

        # News sentiment
        st.markdown('<div class="section-hd">📰 News Sentiment</div>', unsafe_allow_html=True)
        with st.spinner(f"Fetching news for {symbol_guess}…"):
            ns = get_news_summary(symbol_guess, data.get("name",""))
        if ns["count"]:
            ov = ns["overall"]
            oc = "#10b981" if ov>.15 else ("#ef4444" if ov<-.15 else "#3b82f6")
            st.markdown(
                f"<div class='card' style='border-left:3px solid {oc}'>"
                f"<span style='font-weight:700;color:{oc}'>{ns['label']}</span>"
                f"<span style='color:#64748b;font-size:.8rem;margin-left:8px'>"
                f"{ov:+.3f} · {ns['count']} articles · "
                f"✅ {ns['positive']} · ❌ {ns['negative']}</span></div>",
                unsafe_allow_html=True)
            _SC = {"Groww":"#f59e0b","Google News":"#3b82f6","Economic Times":"#ef4444",
                   "Moneycontrol":"#8b5cf6","Business Standard":"#06b6d4","LiveMint":"#10b981"}
            _SB = {"positive":'<span class="badge badge-pos">POS</span>',
                   "negative":'<span class="badge badge-neg">NEG</span>',
                   "neutral": '<span class="badge badge-neu">NEU</span>'}
            for _, a in ns["articles"].head(8).iterrows():
                src = a.get("source",""); sc = _SC.get(src,"#64748b")
                url = a.get("url",""); txt = a.get("title","")[:200]
                t_html = (f'<a href="{url}" target="_blank" style="color:#e2e8f0;text-decoration:none">{txt}</a>'
                          if url else f'<span style="color:#e2e8f0">{txt}</span>')
                st.markdown(
                    f"<div class='article-card'>"
                    f"{_SB.get(a.get('sentiment','neutral'),_SB['neutral'])} "
                    f"<span class='src-pill' style='background:{sc}22;color:{sc};border-color:{sc}44'>{src}</span> "
                    f"<span style='color:#64748b;font-size:.74rem'>{a.get('date','')} · "
                    f"{str(a.get('emotion','')).capitalize()}</span><br>"
                    f"<span style='font-size:.84rem'>{t_html}</span></div>",
                    unsafe_allow_html=True)
        else:
            st.info("No recent news found for this stock.")

    if load_ann and symbol_guess:
        with st.spinner(f"Loading BSE announcements for {symbol_guess}…"):
            bse_code = get_bse_code(symbol_guess)
            if bse_code:
                ann = fetch_bse_announcements(bse_code, ann_days)
                if ann.empty:
                    st.info("No announcements found.")
                else:
                    st.markdown(f'<div class="section-hd">{len(ann)} Announcements</div>',
                                unsafe_allow_html=True)
                    for _, r in ann.head(20).iterrows():
                        st.markdown(
                            f"<div class='article-card'>"
                            f"<span style='color:#64748b;font-size:.76rem'>{r.get('Date','')} · "
                            f"{r.get('Category','')}</span><br>"
                            f"<span style='color:#e2e8f0;font-size:.86rem'>{r.get('Headline','')}</span></div>",
                            unsafe_allow_html=True)
            else:
                st.warning(f"BSE code not found for {symbol_guess}.")

    if not load_btn and not load_ann:
        st.markdown(
            "<div style='text-align:center;color:#1e3450;padding:100px 0'>"
            "Search for a company on the left to load detailed financials"
            "</div>", unsafe_allow_html=True)

