"""
NSE Stock Data Fetcher
- Live NIFTY 500 constituent lists from NSE archives (Blue Chip / Large Cap / Mid Cap / Small Cap)
- Parallel yfinance fetching via ThreadPoolExecutor
- Streamlit cache: index lists 24h, prices 15min
"""

import io
import requests
import yfinance as yf
import pandas as pd
import numpy as np
import streamlit as st
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── NSE archive headers (required to avoid 403) ───────────────────────────────
_NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}

# ── Fallback hardcoded lists (used if NSE archive is unreachable) ─────────────
_FB_NIFTY50 = [
    "RELIANCE","TCS","HDFCBANK","BHARTIARTL","ICICIBANK","INFOSYS","SBIN",
    "HINDUNILVR","ITC","LT","KOTAKBANK","AXISBANK","BAJFINANCE","MARUTI",
    "HCLTECH","SUNPHARMA","WIPRO","ULTRACEMCO","ADANIENT","NTPC","ONGC",
    "POWERGRID","TITAN","BAJAJFINSV","TATAMOTORS","NESTLEIND","TECHM",
    "ADANIPORTS","COALINDIA","TATASTEEL","JSWSTEEL","HINDALCO","GRASIM",
    "DIVISLAB","BPCL","CIPLA","DRREDDY","ASIANPAINT","EICHERMOT","INDUSINDBK",
    "BRITANNIA","HEROMOTOCO","SHRIRAMFIN","TATACONSUM","APOLLOHOSP",
    "BAJAJ-AUTO","SBILIFE","HDFCLIFE","M&M","LTIM",
]
_FB_LARGE = [
    "PIDILITIND","SIEMENS","HAVELLS","DABUR","MARICO","BERGEPAINT","COLPAL",
    "GODREJCP","MUTHOOTFIN","LUPIN","TORNTPHARM","DMART","IRCTC","PFC",
    "RECLTD","CANBK","BANKBARODA","IOC","GAIL","HINDPETRO","TATAPOWER",
    "ADANIGREEN","VEDL","NMDC","CONCOR","ALKEM","AUROPHARMA","IPCALAB",
    "CHOLAFIN","LICHSGFIN","TRENT","SBICARD","AMBUJACEM","SHREECEM","IGL",
    "PETRONET","MCDOWELL-N","UNITDSPR","GUJGASLTD","LODHA","NYKAA","ZOMATO",
    "PAYTM","DELHIVERY","POLICYBZR","JSWENERGY","TATACHEM","JKCEMENT",
    "RAMCOCEM","ACC",
]
_FB_MID = [
    "PERSISTENT","LTTS","COFORGE","MPHASIS","KPITTECH","INDHOTEL","LAURUS",
    "NATCO","JBCHEPHARM","ROUTE","NAZARA","HBLPOWER","GRAVITA","DFMFOODS",
    "KRBL","VENKYS","AVANTIFEED","WATERBASE","SUNDARMFIN","REPCO","HOMEFIRST",
    "AAVAS","CANFINHOME","APTUS","EDELWEISS","MOTILALOFS","ANGELONE",
    "APOLLOTYRE","MRF","BALKRISIND","CEATLTD","GRINDWELL","TIMKEN","SCHAEFFLER",
    "SKFINDIA","ELGIEQUIP","GREENPANEL","CENTURYPLY","PVRINOX","ZEEL",
    "LEMONTREE","CHALET","SUDARSCHEM","ALKYLAMINE","FINEORG","ROSSARI",
    "GALAXYSURF","NUVOCO","HEIDELBERG","ORIENTCEM",
]
_FB_SMALL = [
    "IRFC","RVNL","RAILVIKAS","NBCC","HUDCO","SJVN","NHPC","JYOTHYLAB",
    "ZYDUSWELL","EMAMILTD","HONASA","SAPPHIRE","TRIDENT","WELSPUNLIV",
    "RUPA","DOLLAR","PAGEIND","KEWAL","SPORTKING","HIMATSEIDE","VARDHMAN",
    "NIITLTD","CYIENT","TATAELXSI","BIRLASOFT","MASTEK","SONATSOFTW","TANLA",
    "HBLPOWER","GPPL","ESAB","ORIENTELEC","VOLTAMP","TDPOWERSYS","INGERRAND",
    "NESCO","GREENPANEL","CENTURYPLY","GOKALDAS","NITIRAJ","SHYAMMETL",
    "JINDALSAW","RATNAMANI","WELCORP","GPIL","SSWL","GMRINFRA","IRB",
    "NHAI","ASHOKA",
]

_SECTOR_MAP = {
    "RELIANCE":"Energy","TCS":"IT","HDFCBANK":"Banking","BHARTIARTL":"Telecom",
    "ICICIBANK":"Banking","INFOSYS":"IT","SBIN":"Banking","HINDUNILVR":"FMCG",
    "ITC":"FMCG","LT":"Infrastructure","KOTAKBANK":"Banking","AXISBANK":"Banking",
    "BAJFINANCE":"Finance","MARUTI":"Auto","HCLTECH":"IT","SUNPHARMA":"Pharma",
    "WIPRO":"IT","ULTRACEMCO":"Cement","ADANIENT":"Conglomerate","NTPC":"Power",
    "ONGC":"Energy","POWERGRID":"Power","TITAN":"Consumer","BAJAJFINSV":"Finance",
    "TATAMOTORS":"Auto","NESTLEIND":"FMCG","TECHM":"IT","ADANIPORTS":"Logistics",
    "COALINDIA":"Mining","TATASTEEL":"Metal","JSWSTEEL":"Metal","HINDALCO":"Metal",
    "GRASIM":"Diversified","DIVISLAB":"Pharma","BPCL":"Energy","CIPLA":"Pharma",
    "DRREDDY":"Pharma","ASIANPAINT":"Consumer","EICHERMOT":"Auto",
    "INDUSINDBK":"Banking","BRITANNIA":"FMCG","HEROMOTOCO":"Auto",
    "SHRIRAMFIN":"Finance","TATACONSUM":"FMCG","APOLLOHOSP":"Healthcare",
    "BAJAJ-AUTO":"Auto","SBILIFE":"Insurance","HDFCLIFE":"Insurance",
    "M&M":"Auto","LTIM":"IT","PIDILITIND":"Chemicals","SIEMENS":"Engineering",
    "HAVELLS":"Consumer Elec","DABUR":"FMCG","MARICO":"FMCG",
    "BERGEPAINT":"Consumer","COLPAL":"FMCG","GODREJCP":"FMCG",
    "MUTHOOTFIN":"Finance","LUPIN":"Pharma","TORNTPHARM":"Pharma",
    "DMART":"Retail","IRCTC":"Travel","PFC":"Finance","RECLTD":"Finance",
    "CANBK":"Banking","BANKBARODA":"Banking","IOC":"Energy","GAIL":"Energy",
    "HINDPETRO":"Energy","TATAPOWER":"Power","ADANIGREEN":"Renewable",
    "VEDL":"Metal","NMDC":"Mining","CONCOR":"Logistics","ALKEM":"Pharma",
    "AUROPHARMA":"Pharma","IPCALAB":"Pharma","CHOLAFIN":"Finance",
    "LICHSGFIN":"Finance","TRENT":"Retail","SBICARD":"Finance",
    "AMBUJACEM":"Cement","SHREECEM":"Cement","IGL":"Energy",
    "PETRONET":"Energy","GUJGASLTD":"Energy","LODHA":"Real Estate",
    "NYKAA":"Consumer","ZOMATO":"Consumer Tech","PAYTM":"FinTech",
    "DELHIVERY":"Logistics","POLICYBZR":"Insurance","JSWENERGY":"Power",
    "TATACHEM":"Chemicals","JKCEMENT":"Cement","RAMCOCEM":"Cement","ACC":"Cement",
    "IRFC":"Finance","RVNL":"Infrastructure","NBCC":"Infrastructure",
    "HUDCO":"Finance","SJVN":"Power","NHPC":"Power",
    "PERSISTENT":"IT","LTTS":"IT","COFORGE":"IT","MPHASIS":"IT","KPITTECH":"IT",
    "INDHOTEL":"Hospitality","APOLLOTYRE":"Auto","MRF":"Auto",
    "BALKRISIND":"Auto","CEATLTD":"Auto","PVRINOX":"Media","ZEEL":"Media",
    "TATAELXSI":"IT","CYIENT":"IT","BIRLASOFT":"IT","TANLA":"IT",
}


# ── Dynamic NSE index constituent loader ──────────────────────────────────────
@st.cache_data(ttl=86400, show_spinner=False)
def _load_nse_index_csv(filename: str) -> list[str]:
    """Fetch an NSE index constituent CSV and return list of symbols."""
    url = f"https://archives.nseindia.com/content/indices/{filename}"
    try:
        r = requests.get(url, headers=_NSE_HEADERS, timeout=15)
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text))
        # Column is usually "Symbol"
        col = next((c for c in df.columns if "symbol" in c.lower()), df.columns[0])
        return df[col].str.strip().tolist()
    except Exception:
        return []


@st.cache_data(ttl=86400, show_spinner=False)
def load_universe() -> tuple[dict[str, str], dict[str, str]]:
    """
    Returns:
        cap_labels  : {symbol -> "Blue Chip" | "Large Cap" | "Mid Cap" | "Small Cap"}
        sector_map  : {symbol -> sector string}  (from NSE CSV or fallback map)
    """
    nifty50   = _load_nse_index_csv("ind_nifty50list.csv")
    nifty100  = _load_nse_index_csv("ind_nifty100list.csv")
    nifty500  = _load_nse_index_csv("ind_nifty500list.csv")
    midcap150 = _load_nse_index_csv("ind_niftymidcap150list.csv")

    # Fallback if NSE blocked
    if not nifty50:   nifty50   = _FB_NIFTY50
    if not nifty100:  nifty100  = _FB_NIFTY50 + _FB_LARGE
    if not nifty500:  nifty500  = _FB_NIFTY50 + _FB_LARGE + _FB_MID + _FB_SMALL
    if not midcap150: midcap150 = _FB_MID

    nifty50_set   = set(nifty50)
    nifty100_set  = set(nifty100)
    midcap150_set = set(midcap150)

    cap_labels: dict[str, str] = {}
    for sym in nifty500:
        if sym in nifty50_set:
            cap_labels[sym] = "Blue Chip"
        elif sym in nifty100_set:
            cap_labels[sym] = "Large Cap"
        elif sym in midcap150_set:
            cap_labels[sym] = "Mid Cap"
        else:
            cap_labels[sym] = "Small Cap"

    return cap_labels, _SECTOR_MAP


def get_all_symbols(cap_filter: str = "All") -> list[str]:
    cap_labels, _ = load_universe()
    if cap_filter == "All":
        return list(cap_labels.keys())
    return [s for s, c in cap_labels.items() if c == cap_filter]


# ── Per-symbol fetch (runs in thread pool) ────────────────────────────────────
def _fetch_one(sym: str, cap_labels: dict, sector_map: dict) -> dict | None:
    try:
        ticker = yf.Ticker(f"{sym}.NS")
        info = ticker.info or {}

        price      = info.get("currentPrice") or info.get("regularMarketPrice") or 0
        prev_close = info.get("previousClose") or price
        if not price:
            return None

        change_pct  = ((price - prev_close) / prev_close * 100) if prev_close else 0
        market_cap  = (info.get("marketCap") or 0) / 1e7
        revenue     = (info.get("totalRevenue") or 0) / 1e7
        net_income  = (info.get("netIncomeToCommon") or 0) / 1e7
        pe_ratio    = info.get("trailingPE") or 0
        pb_ratio    = info.get("priceToBook") or 0
        eps         = info.get("trailingEps") or 0
        dividend    = info.get("dividendYield") or 0
        week52_high = info.get("fiftyTwoWeekHigh") or 0
        week52_low  = info.get("fiftyTwoWeekLow") or 0
        beta        = info.get("beta") or 0
        volume      = info.get("volume") or info.get("regularMarketVolume") or 0
        sector      = sector_map.get(sym, info.get("sector") or "—")
        name        = info.get("longName") or info.get("shortName") or sym

        return {
            "Symbol":        sym,
            "Name":          name,
            "Sector":        sector,
            "Cap Category":  cap_labels.get(sym, "Small Cap"),
            "Price (₹)":     round(price, 2),
            "Change %":      round(change_pct, 2),
            "Day High":      round(info.get("dayHigh") or price, 2),
            "Day Low":       round(info.get("dayLow") or price, 2),
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
        }
    except Exception:
        return None


@st.cache_data(ttl=900, show_spinner=False)
def fetch_stock_batch(symbols: list[str]) -> pd.DataFrame:
    """Parallel fetch using ThreadPoolExecutor. No Streamlit UI calls inside."""
    cap_labels, sector_map = load_universe()
    rows = []

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(_fetch_one, sym, cap_labels, sector_map): sym
                   for sym in symbols}
        for future in as_completed(futures):
            result = future.result()
            if result:
                rows.append(result)
    return pd.DataFrame(rows)


@st.cache_data(ttl=900, show_spinner=False)
def fetch_single_stock(symbol: str) -> dict | None:
    """Fetch yfinance data for one symbol — used by Deep Search."""
    cap_labels, sector_map = load_universe()
    return _fetch_one(symbol.upper(), cap_labels, sector_map)


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_history(symbol: str, period: str = "6mo") -> pd.DataFrame:
    try:
        df = yf.Ticker(f"{symbol}.NS").history(period=period)
        df.index = pd.to_datetime(df.index)
        return df
    except Exception:
        return pd.DataFrame()
