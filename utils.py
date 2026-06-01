"""Shared utilities — CSS, theming, market status, chart helpers."""

import datetime as dt
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── Design-system CSS ─────────────────────────────────────────────────────────
CSS = """
<style>
:root {
  --bg:#07111d; --bg-card:#0d1e30; --bg-raised:#142438; --bg-hover:#1a2f45;
  --border:#1e3450; --border-sub:#152130;
  --blue:#3b82f6; --green:#10b981; --red:#ef4444;
  --amber:#f59e0b; --purple:#8b5cf6; --cyan:#06b6d4;
  --text:#e2e8f0; --muted:#64748b; --soft:#94a3b8;
}
.main .block-container{padding:.6rem 1.4rem 2rem;max-width:1600px}
.stApp{background:var(--bg)}

/* Header — compact */
.nse-header{display:flex;align-items:center;justify-content:space-between;
  background:linear-gradient(120deg,#0d1e30 0%,#0f2640 60%,#0d1e30 100%);
  border:1px solid var(--border);border-radius:11px;
  padding:.55rem 1.2rem;margin-bottom:.5rem}
.nse-header h1{margin:0;font-size:1.2rem;font-weight:800;
  background:linear-gradient(90deg,#60a5fa,#34d399);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent}
.nse-header p{margin:1px 0 0;font-size:.72rem;color:var(--muted)}
.mkt-badge{display:flex;align-items:center;gap:5px;background:var(--bg-raised);
  border:1px solid var(--border);border-radius:7px;padding:4px 9px;
  font-size:.72rem;color:var(--soft)}
.dot-open{width:6px;height:6px;border-radius:50%;background:var(--green);
  box-shadow:0 0 5px var(--green);animation:pulse 2s infinite}
.dot-closed{width:6px;height:6px;border-radius:50%;background:var(--muted)}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}

/* Cap pills */
.cap-bar{display:flex;gap:8px;align-items:center;background:var(--bg-card);
  border:1px solid var(--border);border-radius:12px;padding:8px 12px;margin-bottom:.8rem}
.cap-label{font-size:.68rem;color:var(--muted);font-weight:700;
  text-transform:uppercase;letter-spacing:.09em;margin-right:4px;white-space:nowrap}

/* Stats chips */
.stats-bar{display:flex;gap:8px;margin-bottom:.8rem;flex-wrap:wrap}
.stat-chip{background:var(--bg-card);border:1px solid var(--border);
  border-radius:10px;padding:9px 14px;flex:1;min-width:110px}
.stat-chip .sc-label{font-size:.65rem;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}
.stat-chip .sc-value{font-size:1.1rem;font-weight:700;color:var(--text);margin-top:1px}
.stat-chip .sc-sub{font-size:.68rem;color:var(--muted);margin-top:1px}
.sc-green{color:var(--green)!important}.sc-red{color:var(--red)!important}
.sc-blue{color:var(--blue)!important}.sc-amber{color:var(--amber)!important}

/* Cards */
.card{background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:15px 17px;margin-bottom:9px}
.card-accent-blue{border-left:3px solid var(--blue)}
.card-accent-green{border-left:3px solid var(--green)}
.card-accent-red{border-left:3px solid var(--red)}
.card-accent-amber{border-left:3px solid var(--amber)}

/* Badges */
.badge{display:inline-block;padding:2px 10px;border-radius:20px;font-size:.73rem;font-weight:700;letter-spacing:.03em}
.badge-buy{background:rgba(16,185,129,.15);color:#34d399;border:1px solid rgba(16,185,129,.3)}
.badge-sell{background:rgba(239,68,68,.15);color:#f87171;border:1px solid rgba(239,68,68,.3)}
.badge-hold{background:rgba(245,158,11,.15);color:#fbbf24;border:1px solid rgba(245,158,11,.3)}
.badge-pos{background:rgba(16,185,129,.12);color:#34d399;border:1px solid rgba(16,185,129,.25);font-size:.68rem}
.badge-neg{background:rgba(239,68,68,.12);color:#f87171;border:1px solid rgba(239,68,68,.25);font-size:.68rem}
.badge-neu{background:rgba(100,116,139,.12);color:#94a3b8;border:1px solid rgba(100,116,139,.25);font-size:.68rem}

/* Cap colours */
.cap-bc{background:rgba(59,130,246,.12);color:#60a5fa;border:1px solid rgba(59,130,246,.25)}
.cap-lc{background:rgba(16,185,129,.12);color:#34d399;border:1px solid rgba(16,185,129,.25)}
.cap-mc{background:rgba(245,158,11,.12);color:#fbbf24;border:1px solid rgba(245,158,11,.25)}
.cap-sc{background:rgba(239,68,68,.12);color:#f87171;border:1px solid rgba(239,68,68,.25)}

/* Article / movers cards */
.article-card{background:var(--bg-card);border:1px solid var(--border);border-radius:9px;
  padding:10px 14px;margin-bottom:6px;transition:border-color .18s}
.article-card:hover{border-color:var(--blue)}
.mover-card{background:var(--bg-card);border:1px solid var(--border);border-radius:10px;
  padding:10px 14px;margin-bottom:5px;display:flex;align-items:center;
  justify-content:space-between;transition:border-color .18s}
.mover-card:hover{border-color:var(--border)}
.mover-sym{font-size:.95rem;font-weight:700;color:var(--text)}
.mover-name{font-size:.7rem;color:var(--muted);margin-top:1px}
.mover-chg{font-size:1rem;font-weight:700}
.chg-up{color:var(--green)}.chg-dn{color:var(--red)}

/* Index card */
.idx-card{background:var(--bg-card);border:1px solid var(--border);border-radius:11px;
  padding:12px 14px;height:100%}
.idx-name{font-size:.72rem;font-weight:700;color:var(--muted);text-transform:uppercase;
  letter-spacing:.08em;margin-bottom:2px}
.idx-val{font-size:1.15rem;font-weight:800;color:var(--text)}
.idx-chg{font-size:.82rem;font-weight:700;margin-top:2px}

/* Section heading */
.section-hd{font-size:.66rem;font-weight:700;color:var(--muted);text-transform:uppercase;
  letter-spacing:.1em;border-bottom:1px solid var(--border-sub);padding-bottom:5px;margin:14px 0 9px}

/* Compare card */
.cmp-card{background:var(--bg-card);border-radius:10px;padding:12px;
  border-top:3px solid var(--blue);text-align:center;height:100%}
.cmp-sym{font-size:1rem;font-weight:800;color:var(--text)}
.cmp-cat{font-size:.68rem;color:var(--muted);margin:2px 0 7px}
.cmp-price{font-size:1.25rem;font-weight:700;color:var(--text)}
.cmp-row{font-size:.76rem;color:var(--soft);margin-top:3px}
.cmp-row b{color:var(--text)}

/* Tabs */
.stTabs [data-baseweb="tab-list"]{gap:4px;background:var(--bg-card);
  border-radius:10px;padding:4px;border:1px solid var(--border)}
.stTabs [data-baseweb="tab"]{border-radius:8px;padding:5px 13px;
  font-size:.78rem;font-weight:600;color:var(--muted);background:transparent;border:none}
.stTabs [aria-selected="true"]{background:var(--bg-raised)!important;
  color:var(--text)!important;border:1px solid var(--border)!important}
.stTabs [data-baseweb="tab-panel"]{padding-top:14px}

/* Sidebar */
section[data-testid="stSidebar"]{background:#060f1a;border-right:1px solid var(--border)}
section[data-testid="stSidebar"] h3{font-size:.7rem;color:var(--muted);
  text-transform:uppercase;letter-spacing:.1em;margin:16px 0 5px}

/* Table */
.dataframe thead th{background:var(--bg-raised)!important;color:var(--muted)!important;
  font-size:.7rem!important;text-transform:uppercase;letter-spacing:.05em}

/* Scrollbar */
::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:var(--border);border-radius:4px}
::-webkit-scrollbar-thumb:hover{background:var(--blue)}

/* ── Hide Streamlit chrome on all pages ── */
.main .block-container         { padding-top:.2rem !important; }
header[data-testid="stHeader"] { display:none !important; }
#MainMenu                      { display:none !important; }
.stDeployButton                { display:none !important; }
section[data-testid="stSidebar"]           { display:none !important; }
[data-testid="collapsedControl"]           { display:none !important; }
button[data-testid="stBaseButton-minimal"] { display:none !important; }
[data-testid="stStatusWidget"]             { display:none !important; }
.stApp > div:first-child                   { padding-top:0 !important; }

/* ── Nav bar (shared across pages) ── */
.nav-bar{display:flex;gap:5px;background:#0d1e30;border:1px solid #1e3450;
  border-radius:12px;padding:5px 8px;margin-bottom:.6rem;flex-wrap:nowrap;
  align-items:center;overflow-x:auto}
.nav-bar .stButton>button{border-radius:8px!important;font-size:.75rem!important;
  font-weight:600!important;padding:4px 12px!important;border:none!important;
  background:transparent!important;color:#64748b!important;transition:all .15s!important;
  white-space:nowrap!important}
.nav-bar .stButton>button:hover{background:#142438!important;color:#e2e8f0!important}
.nav-active .stButton>button{background:#142438!important;color:#60a5fa!important;
  border:1px solid #1e3450!important}
</style>
"""

_CHART_BG = "#07111d"

# ── Helpers ───────────────────────────────────────────────────────────────────

def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def market_status():
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30)))
    open_t  = now.replace(hour=9,  minute=15, second=0, microsecond=0)
    close_t = now.replace(hour=15, minute=30, second=0, microsecond=0)
    is_open = now.weekday() < 5 and open_t <= now <= close_t
    return is_open, now.strftime("%a %d %b %Y · %H:%M IST")


def render_header(title: str = "📈 NSE Stock Analyser", subtitle: str = ""):
    is_open, ts = market_status()
    sub = subtitle or "Live data · AI via Groq · Screener.in deep dive"
    st.markdown(f"""
<div class="nse-header">
  <div>
    <h1>{title}</h1>
    <p>{sub}</p>
  </div>
  <div style="display:flex;gap:10px;align-items:center">
    <div class="mkt-badge">
      <div class="{'dot-open' if is_open else 'dot-closed'}"></div>
      <span>NSE {'Open' if is_open else 'Closed'}</span>
    </div>
    <div class="mkt-badge">🕐 {ts}</div>
  </div>
</div>
""", unsafe_allow_html=True)


_NAV_PAGES = [
    ("🏠 Dashboard",   "app.py"),
    ("📋 Screener",    "pages/1_Screener.py"),
    ("🤖 AI Analysis", "pages/2_AI_Analysis.py"),
    ("⚖️ Compare",     "pages/3_Compare.py"),
    ("📰 News",        "pages/4_News.py"),
    ("🔍 Deep Search", "pages/6_Deep_Search.py"),
    ("🗂️ Heatmap",     "pages/5_Heatmap.py"),
]

def render_nav(active_path: str = ""):
    """Render horizontal nav bar. active_path = current page file path."""
    st.markdown('<div class="nav-bar">', unsafe_allow_html=True)
    cols = st.columns(len(_NAV_PAGES))
    for i, (label, path) in enumerate(_NAV_PAGES):
        is_active = (path == active_path or
                     (active_path == "" and path == "app.py"))
        with cols[i]:
            st.markdown(f'<div class="{"nav-active" if is_active else ""}">',
                        unsafe_allow_html=True)
            if st.button(label, key=f"nav_{i}_{active_path}", use_container_width=True):
                if not is_active:
                    st.switch_page(path)
            st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


def page_cfg(title: str = "NSE Stock Analyser"):
    st.set_page_config(
        page_title=title,
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="collapsed",
    )


def chart_layout(fig, height=460, title=""):
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=_CHART_BG,
        plot_bgcolor=_CHART_BG,
        height=height,
        margin=dict(l=0, r=0, t=30 if title else 10, b=0),
        title=dict(text=title, font=dict(color="#94a3b8", size=13)) if title else None,
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", y=1.04, font=dict(size=11)),
        xaxis=dict(gridcolor="#0d1e30", zerolinecolor="#0d1e30"),
        yaxis=dict(gridcolor="#0d1e30", zerolinecolor="#0d1e30"),
    )
    return fig


def candle_with_rsi(hist, symbol: str, period_label: str = ""):
    """Build a candlestick + RSI subplot figure."""
    hist = hist.copy()
    hist["SMA20"] = hist["Close"].rolling(20).mean()
    hist["SMA50"] = hist["Close"].rolling(50).mean()
    delta = hist["Close"].diff()
    gain  = delta.where(delta > 0, 0).rolling(14).mean()
    loss  = (-delta.where(delta < 0, 0)).rolling(14).mean()
    hist["RSI"] = 100 - (100 / (1 + gain / loss.replace(0, float("nan"))))

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.7, 0.3], vertical_spacing=0.04)
    fig.add_trace(go.Candlestick(
        x=hist.index, open=hist["Open"], high=hist["High"],
        low=hist["Low"], close=hist["Close"], name=symbol,
        increasing_line_color="#10b981", decreasing_line_color="#ef4444",
    ), row=1, col=1)
    fig.add_trace(go.Scatter(x=hist.index, y=hist["SMA20"], name="SMA20",
                             line=dict(color="#60a5fa", width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=hist.index, y=hist["SMA50"], name="SMA50",
                             line=dict(color="#f59e0b", width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=hist.index, y=hist["RSI"], name="RSI",
                             line=dict(color="#a78bfa", width=1.5),
                             fill="tozeroy", fillcolor="rgba(167,139,250,0.08)"), row=2, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="#ef4444", line_width=1, row=2, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="#10b981", line_width=1, row=2, col=1)

    chart_layout(fig, height=460, title=f"{symbol} · {period_label}")
    fig.update_yaxes(title_text="Price (₹)", row=1, col=1)
    fig.update_yaxes(title_text="RSI", row=2, col=1, range=[0, 100])
    return fig
