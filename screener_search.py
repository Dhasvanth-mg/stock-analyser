"""
Screener.in search + financial data scraper.
- Search: screener.in autocomplete API (no auth)
- Financials: HTML scraping of company pages
- Announcements: BSE public API
"""

import re
import time
import requests
import pandas as pd
import streamlit as st
from bs4 import BeautifulSoup
from datetime import date, timedelta

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.screener.in/",
}
_JSON_HEADERS = {**_HEADERS, "Accept": "application/json, text/plain, */*"}
_BSE_HEADERS  = {
    "User-Agent": _HEADERS["User-Agent"],
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.bseindia.com",
    "Referer": "https://www.bseindia.com/",
}
_BASE = "https://www.screener.in"


# ── Search ────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def search_screener(query: str) -> list[dict]:
    """
    Returns list of {name, url, type} from screener.in autocomplete.
    Example: [{"name": "Reliance Industries", "url": "/company/RELIANCE/", "type": "equity"}]
    """
    if not query or len(query) < 2:
        return []
    try:
        r = requests.get(
            f"{_BASE}/api/company/search/",
            params={"q": query, "v": "3"},
            headers=_JSON_HEADERS,
            timeout=10,
        )
        return r.json() if r.ok else []
    except Exception:
        return []


# ── Company page scraping ─────────────────────────────────────────────────────

def _get_soup(url: str) -> BeautifulSoup | None:
    try:
        r = requests.get(url, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        return BeautifulSoup(r.text, "lxml")
    except Exception:
        return None


def _parse_table(section: BeautifulSoup) -> pd.DataFrame:
    """Parse the first <table> in a section into a DataFrame."""
    if not section:
        return pd.DataFrame()
    table = section.find("table")
    if not table:
        return pd.DataFrame()
    try:
        return pd.read_html(str(table))[0]
    except Exception:
        return pd.DataFrame()


def _clean_num(s: str) -> str:
    """Strip % signs and whitespace for display."""
    return str(s).replace(",", "").strip()


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_company_data(screener_url: str) -> dict:
    """
    Scrape a screener.in company page and return structured data.
    screener_url: e.g. "/company/RELIANCE/" or "/company/RELIANCE/consolidated/"
    """
    full_url = _BASE + screener_url
    soup     = _get_soup(full_url)
    if not soup:
        return {}

    result = {}

    # ── Company name & basic info ─────────────────────────────────────────
    h1 = soup.find("h1", class_="h2")
    result["name"] = h1.get_text(strip=True) if h1 else screener_url

    # ── Key ratios (the top metrics bar) ─────────────────────────────────
    ratios = {}
    for li in soup.select("ul.company-ratios li"):
        name_el  = li.find("span", class_="name")
        value_el = li.find("span", class_="number") or li.find("span", class_="value")
        if name_el and value_el:
            ratios[name_el.get_text(strip=True)] = value_el.get_text(strip=True)
    result["ratios"] = ratios

    # ── About / description ───────────────────────────────────────────────
    about = soup.find("div", {"id": "company-info"})
    result["about"] = about.get_text(" ", strip=True)[:500] if about else ""

    # ── NSE / BSE codes (scraped from page header) ────────────────────────
    result["nse_code"] = ""
    result["bse_code"] = ""
    for a in soup.select("a[href*='nseindia'], a[href*='bseindia'], .company-links a"):
        txt = a.get_text(strip=True).upper()
        href = a.get("href", "")
        if "nseindia" in href or "NSE" in a.get_text():
            # Try to pull the ticker from text or href
            import re as _re
            m = _re.search(r'symbol=([A-Z0-9&\-]+)', href)
            if m:
                result["nse_code"] = m.group(1)
    # Fallback: look for NSE: TICKER pattern in page text
    import re as _re
    page_text = soup.get_text(" ")
    m_nse = _re.search(r'NSE[:\s]+([A-Z0-9&\-]{2,20})', page_text)
    m_bse = _re.search(r'BSE[:\s]+([0-9]{5,6})', page_text)
    if m_nse and not result["nse_code"]:
        result["nse_code"] = m_nse.group(1).strip()
    if m_bse:
        result["bse_code"] = m_bse.group(1).strip()

    # ── Quarterly results ─────────────────────────────────────────────────
    qr_sec = soup.find("section", {"id": "quarters"})
    result["quarterly"] = _parse_table(qr_sec)

    # ── Profit & Loss (annual) ────────────────────────────────────────────
    pl_sec = soup.find("section", {"id": "profit-loss"})
    result["pnl"] = _parse_table(pl_sec)

    # ── Balance Sheet ─────────────────────────────────────────────────────
    bs_sec = soup.find("section", {"id": "balance-sheet"})
    result["balance_sheet"] = _parse_table(bs_sec)

    # ── Cash Flow ─────────────────────────────────────────────────────────
    cf_sec = soup.find("section", {"id": "cash-flow"})
    result["cash_flow"] = _parse_table(cf_sec)

    # ── Financial Ratios (annual) ─────────────────────────────────────────
    r_sec = soup.find("section", {"id": "ratios"})
    result["fin_ratios"] = _parse_table(r_sec)

    # ── Shareholding ──────────────────────────────────────────────────────
    sh_sec = soup.find("section", {"id": "shareholding"})
    result["shareholding"] = _parse_table(sh_sec)

    # ── Pros & Cons — try multiple selector patterns ──────────────────────
    def _get_list(selectors):
        for sel in selectors:
            items = soup.select(sel)
            if items:
                return [li.get_text(strip=True) for li in items if li.get_text(strip=True)]
        return []

    result["pros"] = _get_list([
        "div.pros li", "#analysis .pros li", "section#analysis div:first-child li",
        ".strengths li", ".positive li", "[class*='pro'] li",
    ])
    result["cons"] = _get_list([
        "div.cons li", "#analysis .cons li", "section#analysis div:last-child li",
        ".weaknesses li", ".negative li", "[class*='con'] li",
    ])

    # Last resort: grab both lists from #analysis and split at midpoint
    if not result["pros"] and not result["cons"]:
        analysis = soup.find(id="analysis") or soup.find("section", {"id": "analysis"})
        if analysis:
            all_lists = analysis.find_all("ul")
            if len(all_lists) >= 2:
                result["pros"] = [li.get_text(strip=True) for li in all_lists[0].find_all("li")]
                result["cons"] = [li.get_text(strip=True) for li in all_lists[1].find_all("li")]
            elif len(all_lists) == 1:
                items = [li.get_text(strip=True) for li in all_lists[0].find_all("li")]
                mid = len(items) // 2
                result["pros"] = items[:mid]
                result["cons"] = items[mid:]

    return result


# ── BSE announcements ─────────────────────────────────────────────────────────

@st.cache_data(ttl=900, show_spinner=False)
def fetch_bse_announcements(bse_code: str, days: int = 30) -> pd.DataFrame:
    """Fetch recent announcements from BSE API for a given BSE stock code."""
    to_date   = date.today()
    from_date = to_date - timedelta(days=days)

    url = (
        f"https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w"
        f"?pageno=1&strCat=-1"
        f"&strPrevDate={from_date.strftime('%Y%m%d')}"
        f"&strScrip={bse_code}"
        f"&strSearch=P"
        f"&strToDate={to_date.strftime('%Y%m%d')}"
        f"&strType=C&subcategory=-1"
    )
    try:
        r = requests.get(url, headers=_BSE_HEADERS, timeout=12)
        data = r.json()
        rows = data.get("Table", [])
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        keep = ["ANNOUNCEMENT_DATE", "CATEGORYNAME", "HEADLINE", "ATTACHMENTNAME"]
        keep = [c for c in keep if c in df.columns]
        return df[keep].rename(columns={
            "ANNOUNCEMENT_DATE": "Date",
            "CATEGORYNAME":      "Category",
            "HEADLINE":          "Headline",
            "ATTACHMENTNAME":    "Attachment",
        })
    except Exception:
        return pd.DataFrame()


# ── Angel Broking token map (for BSE code lookup) ────────────────────────────

@st.cache_data(ttl=86400, show_spinner=False)
def _load_angel_tokens() -> pd.DataFrame:
    url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
    try:
        data = requests.get(url, headers=_HEADERS, timeout=20).json()
        df   = pd.DataFrame(data)
        # Keep BSE equities only
        bse  = df[df["exch_seg"] == "BSE"][["symbol", "name", "token"]].copy()
        bse["symbol_clean"] = bse["symbol"].str.replace(r"-.*", "", regex=True).str.strip()
        return bse
    except Exception:
        return pd.DataFrame()


def get_bse_code(symbol: str) -> str:
    """Map NSE symbol → BSE token/code."""
    df = _load_angel_tokens()
    if df.empty:
        return ""
    sym = symbol.upper().strip()
    match = df[df["symbol_clean"] == sym]
    if not match.empty:
        return str(match.iloc[0]["token"])
    # Fuzzy: symbol contains
    match2 = df[df["symbol_clean"].str.startswith(sym)]
    if not match2.empty:
        return str(match2.iloc[0]["token"])
    return ""
