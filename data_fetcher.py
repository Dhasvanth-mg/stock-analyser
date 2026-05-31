"""
NSE Stock Data Fetcher
- Cap categories via NSE index membership (NIFTY 50 / 100 / 500)
- Financial data via yfinance
- Fallback-safe with caching
"""

import yfinance as yf
import pandas as pd
import numpy as np
import requests
import time
import streamlit as st

# ── Index constituent lists ──────────────────────────────────────────────────
# Blue Chip = NIFTY 50
NIFTY50 = [
    "RELIANCE","TCS","HDFCBANK","BHARTIARTL","ICICIBANK","INFOSYS","SBIN",
    "HINDUNILVR","ITC","LT","KOTAKBANK","AXISBANK","BAJFINANCE","MARUTI",
    "HCLTECH","SUNPHARMA","WIPRO","ULTRACEMCO","ADANIENT","NTPC","ONGC",
    "POWERGRID","TITAN","BAJAJFINSV","TATAMOTORS","NESTLEIND","TECHM",
    "ADANIPORTS","COALINDIA","TATASTEEL","JSWSTEEL","HINDALCO","GRASIM",
    "DIVISLAB","BPCL","CIPLA","DRREDDY","ASIANPAINT","EICHERMOT","INDUSINDBK",
    "BRITANNIA","HEROMOTOCO","SHRIRAMFIN","TATACONSUM","APOLLOHOSP",
    "BAJAJ-AUTO","SBILIFE","HDFCLIFE","M&M","LTIM"
]

# Large Cap = NIFTY 100 extras (beyond NIFTY 50)
NIFTY100_EXTRA = [
    "PIDILITIND","SIEMENS","HAVELLS","DABUR","MARICO","BERGEPAINT","COLPAL",
    "GODREJCP","MUTHOOTFIN","LUPIN","TORNTPHARM","BIOCON","ZOMATO","NYKAA",
    "PAYTM","DMART","IRCTC","PFC","RECLTD","CANBK","BANKBARODA","PNBHOUSING",
    "IOC","GAIL","HINDPETRO","TATAPOWER","ADANIGREEN","ADANITRANS","VEDL",
    "NMDC","SAIL","NATIONALUM","CONCOR","GLAND","ALKEM","AUROPHARMA","IPCALAB",
    "ABBOTINDIA","PFIZER","SANOFI","GLAXO","CHOLAFIN","MANAPPURAM","LICHSGFIN"
]

# Mid Cap sample (NIFTY Midcap 100 selection)
MIDCAP = [
    "PERSISTENT","LTTS","COFORGE","MPHASIS","KPITTECH","ZEEL","PVRINOX",
    "INDHOTEL","LEMONTREE","CHALET","LAURUS","NATCO","JBCHEPHARM",
    "SUDARSCHEM","ALKYLAMINE","FINEORG","VINATIORGA","ROSSARI","GALAXYSURF",
    "ROUTE","CARTRADE","EASEMYTRIP","NUVOCO","RAMCOCEM","JKCEMENT",
    "HEIDELBERG","ORIENTCEM","GPPL","ESAB","GRINDWELL","TIMKEN","SCHAEFFLER",
    "SKFINDIA","ELGIEQUIP","GREENPANEL","CENTURYPLY","APOLLOTYRE","MRF",
    "BALKRISIND","CEATLTD","SUNDARMFIN","REPCO","HOMEFIRST","AAVAS",
    "CANFINHOME","APTUS","EDELWEISS","MOTILALOFS","ANGELONE"
]

# Small Cap sample (NIFTY Smallcap 100 selection)
SMALLCAP = [
    "HAPPYFORGE","IRFC","RVNL","RAILVIKAS","NBCC","HUDCO","SJVN",
    "NHPC","PGHL","GLAXO","JYOTHYLAB","ZYDUSWELL","EMAMILTD","MAMAEARTH",
    "HONASA","NYKAA","SAPPHIRE","SIGNATUREGLO","TRIDENT","WELSPUNLIV",
    "RUPA","DOLLAR","PAGEIND","KEWAL","SPORTKING","HIMATSEIDE","VARDHMAN",
    "NIITLTD","CYIENT","TATAELXSI","BIRLASOFT","MASTEK","HEXAWARE",
    "SONATSOFTW","TANLA","NAZARA","HBLPOWER","GRAVITA","TATACHEM",
    "GNFC","DFMFOODS","KRBL","LT FOODS","VENKYS","AVANTIFEED","WATERBASE"
]

CAP_LABELS = {s: "Blue Chip" for s in NIFTY50}
CAP_LABELS.update({s: "Large Cap" for s in NIFTY100_EXTRA})
CAP_LABELS.update({s: "Mid Cap" for s in MIDCAP})
CAP_LABELS.update({s: "Small Cap" for s in SMALLCAP})

ALL_SYMBOLS = list(dict.fromkeys(NIFTY50 + NIFTY100_EXTRA + MIDCAP + SMALLCAP))

SECTORS = {
    "RELIANCE":"Energy","TCS":"IT","HDFCBANK":"Banking","BHARTIARTL":"Telecom",
    "ICICIBANK":"Banking","INFOSYS":"IT","SBIN":"Banking","HINDUNILVR":"FMCG",
    "ITC":"FMCG","LT":"Infrastructure","KOTAKBANK":"Banking","AXISBANK":"Banking",
    "BAJFINANCE":"Finance","MARUTI":"Auto","HCLTECH":"IT","SUNPHARMA":"Pharma",
    "WIPRO":"IT","ULTRACEMCO":"Cement","ADANIENT":"Conglomerate","NTPC":"Power",
    "ONGC":"Energy","POWERGRID":"Power","TITAN":"Consumer","BAJAJFINSV":"Finance",
    "TATAMOTORS":"Auto","NESTLEIND":"FMCG","TECHM":"IT","ADANIPORTS":"Logistics",
    "COALINDIA":"Mining","TATASTEEL":"Metal","JSWSTEEL":"Metal","HINDALCO":"Metal",
    "GRASIM":"Diversified","DIVISLAB":"Pharma","BPCL":"Energy","CIPLA":"Pharma",
    "DRREDDY":"Pharma","ASIANPAINT":"Consumer","EICHERMOT":"Auto","INDUSINDBK":"Banking",
    "BRITANNIA":"FMCG","HEROMOTOCO":"Auto","SHRIRAMFIN":"Finance","TATACONSUM":"FMCG",
    "APOLLOHOSP":"Healthcare","BAJAJ-AUTO":"Auto","SBILIFE":"Insurance",
    "HDFCLIFE":"Insurance","M&M":"Auto","LTIM":"IT",
}


def _yf_symbol(sym: str) -> str:
    return f"{sym}.NS"


@st.cache_data(ttl=900, show_spinner=False)
def fetch_stock_batch(symbols: list[str]) -> pd.DataFrame:
    """Fetch price + fundamentals for a list of symbols via yfinance."""
    rows = []
    for sym in symbols:
        try:
            ticker = yf.Ticker(_yf_symbol(sym))
            info = ticker.info or {}

            price       = info.get("currentPrice") or info.get("regularMarketPrice") or 0
            prev_close  = info.get("previousClose") or price
            day_high    = info.get("dayHigh") or price
            day_low     = info.get("dayLow") or price
            volume      = info.get("volume") or info.get("regularMarketVolume") or 0
            market_cap  = (info.get("marketCap") or 0) / 1e7          # convert to ₹ Cr
            revenue     = (info.get("totalRevenue") or 0) / 1e7       # ₹ Cr
            net_income  = (info.get("netIncomeToCommon") or 0) / 1e7  # ₹ Cr
            pe_ratio    = info.get("trailingPE") or 0
            pb_ratio    = info.get("priceToBook") or 0
            eps         = info.get("trailingEps") or 0
            dividend    = info.get("dividendYield") or 0
            week52_high = info.get("fiftyTwoWeekHigh") or 0
            week52_low  = info.get("fiftyTwoWeekLow") or 0
            beta        = info.get("beta") or 0
            sector      = SECTORS.get(sym, info.get("sector", "—"))
            name        = info.get("longName") or info.get("shortName") or sym
            change_pct  = ((price - prev_close) / prev_close * 100) if prev_close else 0

            rows.append({
                "Symbol":        sym,
                "Name":          name,
                "Sector":        sector,
                "Cap Category":  CAP_LABELS.get(sym, "Small Cap"),
                "Price (₹)":     round(price, 2),
                "Change %":      round(change_pct, 2),
                "Day High":      round(day_high, 2),
                "Day Low":       round(day_low, 2),
                "52W High":      round(week52_high, 2),
                "52W Low":       round(week52_low, 2),
                "Volume":        int(volume),
                "Mkt Cap (₹Cr)": round(market_cap, 1),
                "Revenue (₹Cr)": round(revenue, 1),
                "Net Inc (₹Cr)": round(net_income, 1),
                "P/E":           round(pe_ratio, 2),
                "P/B":           round(pb_ratio, 2),
                "EPS":           round(eps, 2),
                "Div Yield %":   round(dividend * 100, 2),
                "Beta":          round(beta, 2),
            })
        except Exception:
            pass  # skip bad symbols silently

    return pd.DataFrame(rows)


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_history(symbol: str, period: str = "6mo") -> pd.DataFrame:
    """Return OHLCV history for a single symbol."""
    try:
        df = yf.Ticker(_yf_symbol(symbol)).history(period=period)
        df.index = pd.to_datetime(df.index)
        return df
    except Exception:
        return pd.DataFrame()


def get_symbols_by_cap(cap: str) -> list[str]:
    if cap == "All":
        return ALL_SYMBOLS
    return [s for s, c in CAP_LABELS.items() if c == cap]
