"""
NSE Stock Data Fetcher
- Live NIFTY 500 constituent lists from NSE archives
- Batch quote fetching via Yahoo Finance v7 API (~5 requests for 500 stocks)
- Streamlit cache: index lists 24h, prices 15min
"""

import io
import time
import requests
import yfinance as yf
import pandas as pd
import numpy as np
import streamlit as st
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Yahoo Finance batch quote session (curl_cffi for browser impersonation) ────

@st.cache_resource
def _yf_session():
    """
    Shared curl_cffi session + crumb for Yahoo Finance v7 API.
    fc.yahoo.com sets the auth cookie (its 404 response is expected);
    the crumb must match that cookie or v7 returns 401 Invalid Crumb.
    """
    try:
        from curl_cffi import requests as cffi
        s = cffi.Session(impersonate="chrome120")
    except Exception:
        return None, ""

    def _get_crumb() -> str:
        try:
            c = s.get("https://query2.finance.yahoo.com/v1/test/getcrumb",
                      timeout=10).text.strip()
            # A real crumb is ~11 chars; error responses are JSON or empty
            return c if c and len(c) <= 16 and "{" not in c else ""
        except Exception:
            return ""

    try:
        s.get("https://fc.yahoo.com/", timeout=10)
    except Exception:
        pass
    crumb = _get_crumb()
    if not crumb:
        try:
            s.get("https://finance.yahoo.com/", timeout=15)
        except Exception:
            pass
        crumb = _get_crumb()
    return s, crumb


def _bulk_quote(symbols: list[str]) -> dict:
    """
    Fetch quote data for all symbols via Yahoo Finance v7 batch API.
    Uses 50-stock batches with retry + inter-batch delay to avoid cloud rate limiting.
    Returns {SYMBOL.NS: quote_dict}.
    """
    session, crumb = _yf_session()
    if not session or not crumb:
        return {}  # v7 without a valid crumb is a guaranteed 401

    results = {}
    tickers = [f"{s}.NS" for s in symbols]

    for i in range(0, len(tickers), 50):
        batch = tickers[i : i + 50]
        params = {
            "symbols":    ",".join(batch),
            "formatted":  "false",
            "corsDomain": "finance.yahoo.com",
        }
        if crumb:
            params["crumb"] = crumb

        for attempt in range(2):  # retry once on failure
            try:
                r = session.get(
                    "https://query2.finance.yahoo.com/v7/finance/quote",
                    params=params, timeout=30,
                )
                for q in r.json().get("quoteResponse", {}).get("result", []):
                    results[q.get("symbol", "")] = q
                break  # success — no retry needed
            except Exception:
                if attempt == 0:
                    time.sleep(0.5)  # brief pause before retry

        if i + 50 < len(tickers):
            time.sleep(0.15)  # rate-limit buffer between batches

    return results


_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}


def _spark_batch(tickers: list[str]) -> dict:
    """
    Crumb-free price + change via Yahoo spark API (same backend as charts,
    which work even when v7/quoteSummary are blocked on datacenter IPs).
    Returns {ticker: (price, change_pct)}.
    """
    session, _ = _yf_session()
    out = {}
    for i in range(0, len(tickers), 40):
        batch = tickers[i : i + 40]
        params = {"symbols": ",".join(batch), "range": "5d", "interval": "1d"}
        try:
            if session:
                r = session.get("https://query1.finance.yahoo.com/v7/finance/spark",
                                params=params, timeout=25)
            else:
                r = requests.get("https://query1.finance.yahoo.com/v7/finance/spark",
                                 params=params, headers=_BROWSER_HEADERS, timeout=25)
            for res in r.json().get("spark", {}).get("result", []) or []:
                sym  = res.get("symbol", "")
                resp = (res.get("response") or [{}])[0]
                meta = resp.get("meta", {}) or {}
                q      = (resp.get("indicators", {}).get("quote") or [{}])[0]
                closes = [c for c in (q.get("close") or []) if c is not None]
                price = meta.get("regularMarketPrice") or (closes[-1] if closes else 0)
                prev  = closes[-2] if len(closes) >= 2 else (meta.get("chartPreviousClose") or price)
                if price:
                    chg = ((price - prev) / prev * 100) if prev else 0
                    out[sym] = (round(float(price), 2), round(float(chg), 2))
        except Exception:
            continue
        if i + 40 < len(tickers):
            time.sleep(0.1)
    return out

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
    """
    Fetch all symbols via Yahoo Finance v7 batch API (fast path: ~5 requests).
    Falls back to per-ticker ThreadPoolExecutor if batch API is unavailable.
    """
    cap_labels, sector_map = load_universe()

    quotes = _bulk_quote(symbols)

    if quotes:
        rows = []
        for sym in symbols:
            q = quotes.get(f"{sym}.NS", {})
            price = q.get("regularMarketPrice") or 0
            if not price:
                continue
            rows.append({
                "Symbol":        sym,
                "Name":          q.get("longName") or q.get("shortName") or sym,
                "Sector":        sector_map.get(sym) or q.get("sectorDisp") or "—",
                "Cap Category":  cap_labels.get(sym, "Small Cap"),
                "Price (₹)":     round(price, 2),
                "Change %":      round(q.get("regularMarketChangePercent") or 0, 2),
                "Day High":      round(q.get("regularMarketDayHigh") or price, 2),
                "Day Low":       round(q.get("regularMarketDayLow") or price, 2),
                "52W High":      round(q.get("fiftyTwoWeekHigh") or 0, 2),
                "52W Low":       round(q.get("fiftyTwoWeekLow") or 0, 2),
                "Volume":        int(q.get("regularMarketVolume") or 0),
                "Mkt Cap (₹Cr)": round((q.get("marketCap") or 0) / 1e7, 1),
                "Revenue (₹Cr)": 0,
                "Net Inc (₹Cr)": 0,
                "P/E":           round(q.get("trailingPE") or 0, 2),
                "P/B":           round(q.get("priceToBook") or 0, 2),
                "EPS":           round(q.get("epsTrailingTwelveMonths") or 0, 2),
                "Div Yield %":   round((q.get("trailingAnnualDividendYield") or 0) * 100, 2),
                "Beta":          round(q.get("beta") or 0, 2),
            })
        if rows:
            return pd.DataFrame(rows)

    # Fallback 2: crumb-free spark API — price/change only, fundamentals stay 0
    spark = _spark_batch([f"{s}.NS" for s in symbols])
    if spark:
        rows = []
        for sym in symbols:
            price, chg = spark.get(f"{sym}.NS", (0.0, 0.0))
            if not price:
                continue
            rows.append({
                "Symbol":        sym,
                "Name":          sym,
                "Sector":        sector_map.get(sym, "—"),
                "Cap Category":  cap_labels.get(sym, "Small Cap"),
                "Price (₹)":     price,
                "Change %":      chg,
                "Day High":      price,
                "Day Low":       price,
                "52W High":      0,
                "52W Low":       0,
                "Volume":        0,
                "Mkt Cap (₹Cr)": 0,
                "Revenue (₹Cr)": 0,
                "Net Inc (₹Cr)": 0,
                "P/E":           0,
                "P/B":           0,
                "EPS":           0,
                "Div Yield %":   0,
                "Beta":          0,
            })
        if rows:
            return pd.DataFrame(rows)

    # Last resort: per-ticker .info via ThreadPool. Probe one symbol first —
    # if .info is blocked (401 from datacenter IP), don't hammer Yahoo with
    # hundreds of doomed requests.
    if not symbols:
        return pd.DataFrame()
    probe = _fetch_one(symbols[0], cap_labels, sector_map)
    if probe is None and len(symbols) > 1:
        probe = _fetch_one(symbols[1], cap_labels, sector_map)
        if probe is None:
            return pd.DataFrame()
        done = {symbols[0], symbols[1]}
    else:
        if probe is None:
            return pd.DataFrame()
        done = {symbols[0]}

    rows = [probe]
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(_fetch_one, sym, cap_labels, sector_map): sym
                   for sym in symbols if sym not in done}
        for future in as_completed(futures):
            result = future.result()
            if result:
                rows.append(result)
    return pd.DataFrame(rows)


@st.cache_data(ttl=900, show_spinner=False)
def fetch_single_stock(symbol: str) -> dict | None:
    """Fetch live data for one symbol — used by Deep Search. v7 batch first."""
    cap_labels, sector_map = load_universe()
    sym = symbol.upper()

    q = _bulk_quote([sym]).get(f"{sym}.NS")
    if q:
        price = q.get("regularMarketPrice") or 0
        if price:
            return {
                "Symbol":        sym,
                "Name":          q.get("longName") or q.get("shortName") or sym,
                "Sector":        sector_map.get(sym) or "—",
                "Cap Category":  cap_labels.get(sym, "Small Cap"),
                "Price (₹)":     round(price, 2),
                "Change %":      round(q.get("regularMarketChangePercent") or 0, 2),
                "Day High":      round(q.get("regularMarketDayHigh") or price, 2),
                "Day Low":       round(q.get("regularMarketDayLow") or price, 2),
                "52W High":      round(q.get("fiftyTwoWeekHigh") or 0, 2),
                "52W Low":       round(q.get("fiftyTwoWeekLow") or 0, 2),
                "Volume":        int(q.get("regularMarketVolume") or 0),
                "Mkt Cap (₹Cr)": round((q.get("marketCap") or 0) / 1e7, 1),
                "Revenue (₹Cr)": 0,
                "Net Inc (₹Cr)": 0,
                "P/E":           round(q.get("trailingPE") or 0, 2),
                "P/B":           round(q.get("priceToBook") or 0, 2),
                "EPS":           round(q.get("epsTrailingTwelveMonths") or 0, 2),
                "Div Yield %":   round((q.get("trailingAnnualDividendYield") or 0) * 100, 2),
                "Beta":          round(q.get("beta") or 0, 2),
            }
    return _fetch_one(sym, cap_labels, sector_map)


@st.cache_data(ttl=1800, show_spinner=False)
def resolve_and_fetch_history(symbol: str, period: str = "6mo") -> tuple[pd.DataFrame, str]:
    """
    Try multiple ticker variants until we get price history.
    Returns (DataFrame, resolved_ticker) — DataFrame is empty if all fail.
    """
    sym = symbol.upper().strip()
    candidates = [
        f"{sym}.NS",                        # NSE first
        f"{sym}.BO",                        # BSE fallback
        f"{sym.replace('-','')}.NS",           # strip hyphens
        f"{sym.replace(' ','')}.NS",        # strip spaces
    ]
    for ticker_str in candidates:
        ticker_str = ticker_str.strip()
        try:
            df = yf.Ticker(ticker_str).history(period=period)
            if not df.empty:
                df.index = pd.to_datetime(df.index)
                return df, ticker_str
        except Exception:
            continue

    # Last resort: yfinance search
    try:
        import yfinance as _yf
        results = _yf.Search(sym, max_results=8).quotes
        for q in results:
            if q.get("exchange") in ("NSI", "BSE", "NSE", "NMS"):
                t = q.get("symbol", "")
                df = yf.Ticker(t).history(period=period)
                if not df.empty:
                    df.index = pd.to_datetime(df.index)
                    return df, t
    except Exception:
        pass

    return pd.DataFrame(), ""


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_history(symbol: str, period: str = "6mo") -> pd.DataFrame:
    try:
        df = yf.Ticker(f"{symbol}.NS").history(period=period)
        df.index = pd.to_datetime(df.index)
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_financials_yf(symbol: str) -> dict:
    """
    Financial statements + key ratios for an NSE symbol via yfinance.
    Returns the same dict shape expected by Deep Search tabs.
    All monetary values in ₹ Cr.
    """
    t = yf.Ticker(f"{symbol}.NS")

    def _to_cr(df) -> pd.DataFrame:
        if df is None or (hasattr(df, "empty") and df.empty):
            return pd.DataFrame()
        try:
            out = df.T.copy()
            out = out.sort_index(ascending=False)
            # Friendly period labels
            out.index = pd.to_datetime(out.index).strftime("%b %Y")
            out = out.reset_index().rename(columns={"index": "Period"})
            # Convert full INR → ₹ Cr  (1 Cr = 10^7)
            num = out.select_dtypes(include="number").columns
            out[num] = (out[num] / 1e7).round(1)
            # Clean up column names
            out.columns = [
                c if c == "Period" else str(c).replace("_", " ").strip()
                for c in out.columns
            ]
            return out
        except Exception:
            return pd.DataFrame()

    def _attr(primary, fallback=None):
        try:
            df = getattr(t, primary, None)
            if (df is None or df.empty) and fallback:
                df = getattr(t, fallback, None)
            return df
        except Exception:
            return None

    quarterly  = _to_cr(_attr("quarterly_income_stmt", "quarterly_financials"))
    pnl        = _to_cr(_attr("income_stmt",           "financials"))
    bal        = _to_cr(_attr("quarterly_balance_sheet","balance_sheet"))
    cf         = _to_cr(_attr("quarterly_cashflow",    "cashflow"))

    # Shareholding from major_holders
    sh = pd.DataFrame()
    try:
        mh = t.major_holders
        if mh is not None and not mh.empty:
            mh = mh.copy()
            mh.columns = ["Value", "Category"]
            sh = mh[["Category", "Value"]].reset_index(drop=True)
    except Exception:
        pass

    # Key ratios from .info
    fin_ratios = pd.DataFrame()
    try:
        info = t.info or {}

        def _f(key, mult=1.0, fmt="{:.2f}", suffix=""):
            v = info.get(key)
            if v is None:
                return "—"
            try:
                return fmt.format(float(v) * mult) + suffix
            except Exception:
                return str(v)

        rows = [
            ("P/E (TTM)",       _f("trailingPE",       fmt="{:.1f}")),
            ("P/B",             _f("priceToBook")),
            ("EPS (TTM)",       _f("trailingEps",       fmt="₹{:.2f}")),
            ("ROE",             _f("returnOnEquity",    100, "{:.1f}", "%")),
            ("ROA",             _f("returnOnAssets",    100, "{:.1f}", "%")),
            ("Profit Margin",   _f("profitMargins",     100, "{:.1f}", "%")),
            ("Debt / Equity",   _f("debtToEquity")),
            ("Current Ratio",   _f("currentRatio")),
            ("Div Yield",       _f("dividendYield",     100, "{:.2f}", "%")),
            ("Beta",            _f("beta")),
            ("52W High",        _f("fiftyTwoWeekHigh",  fmt="₹{:.2f}")),
            ("52W Low",         _f("fiftyTwoWeekLow",   fmt="₹{:.2f}")),
            ("Revenue (₹ Cr)",  _f("totalRevenue",      1/1e7, "₹{:,.0f}")),
            ("Mkt Cap (₹ Cr)",  _f("marketCap",         1/1e7, "₹{:,.0f}")),
        ]
        fin_ratios = pd.DataFrame(rows, columns=["Metric", "Value"])
    except Exception:
        pass

    return {
        "quarterly":     quarterly,
        "pnl":           pnl,
        "balance_sheet": bal,
        "cash_flow":     cf,
        "fin_ratios":    fin_ratios,
        "shareholding":  sh,
    }
