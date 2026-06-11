"""
Multi-source news fetcher + Groq sentiment analyser for NSE stocks.

Sources:
  1. Groww public feed        — stock-tagged articles, no API key
  2. Google News RSS          — per-stock search
  3. Economic Times RSS       — Indian market news
  4. Moneycontrol RSS         — Indian market news
  5. Business Standard RSS    — Indian market news
  6. LiveMint RSS             — Indian market news
"""

import json
import os
import time
import urllib.parse
import requests
import feedparser
import pandas as pd
import streamlit as st
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

_GROWW_HEADERS = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://groww.in/",
}

_EMPTY = pd.DataFrame(columns=["ticker", "name", "date", "title", "url", "source"])

# RSS feeds that carry broad Indian market news (we match to tickers by keyword)
_MARKET_RSS = [
    ("https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms", "Economic Times"),
    ("https://www.moneycontrol.com/rss/marketsnews.xml",                          "Moneycontrol"),
    ("https://www.business-standard.com/rss/markets-106.rss",                    "Business Standard"),
    ("https://www.livemint.com/rss/markets",                                      "LiveMint"),
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_date(entry) -> str:
    """Best-effort date string YYYY-MM-DD from a feedparser entry."""
    try:
        t = entry.get("published_parsed") or entry.get("updated_parsed")
        if t:
            return f"{t.tm_year}-{t.tm_mon:02d}-{t.tm_mday:02d}"
    except Exception:
        pass
    raw = entry.get("published") or entry.get("updated") or ""
    return raw[:10] if raw else ""


def _rss_source(entry, fallback: str) -> str:
    """Extract publisher name from a feedparser entry."""
    src = getattr(entry, "source", None)
    if src and hasattr(src, "title"):
        return src.title
    tags = entry.get("tags", [])
    if tags:
        return tags[0].get("term", fallback)
    return fallback


# ── Source 1: Groww public feed ───────────────────────────────────────────────

@st.cache_data(ttl=1800, show_spinner=False)
def _fetch_groww(pages: int = 10) -> list[dict]:
    base = "https://groww.in/v2/api/feed/public?page={}&publisherId=stocknewssummary&size=50"
    rows = []
    for page in range(pages):
        try:
            r = requests.get(base.format(page), headers=_GROWW_HEADERS, timeout=12)
            r.raise_for_status()
            data = r.json()
            if not data.get("feed"):
                break
            for item in data["feed"]:
                d    = item.get("data", {})
                body = (d.get("body") or "").split("Source")[0].replace("\n", " ").strip()
                title = ((d.get("title") or "") + " " + body).strip()
                date  = item.get("publishedAt", "")[:10]
                cta   = d.get("cta") or []
                if cta:
                    nse  = cta[0].get("meta", {}).get("nseScriptCode", "")
                    name = cta[0].get("ctaText", "")
                    if nse:
                        rows.append({
                            "ticker": nse.strip().upper(),
                            "name":   name,
                            "date":   date,
                            "title":  title,
                            "url":    "",
                            "source": "Groww",
                        })
        except Exception:
            break
    return rows


# ── Source 2: Google News RSS per stock ───────────────────────────────────────

@st.cache_data(ttl=1800, show_spinner=False)
def _fetch_google_news(symbol: str, company_name: str = "", max_results: int = 20) -> list[dict]:
    query = f'"{company_name or symbol}" NSE OR "{symbol}" stock India'
    url   = (f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}"
             f"&hl=en-IN&gl=IN&ceid=IN:en")
    try:
        feed = feedparser.parse(url)
        rows = []
        for entry in feed.entries[:max_results]:
            rows.append({
                "ticker": symbol.upper(),
                "name":   company_name or symbol,
                "date":   _parse_date(entry),
                "title":  entry.get("title", ""),
                "url":    entry.get("link", ""),
                "source": _rss_source(entry, "Google News"),
            })
        return rows
    except Exception:
        return []


# ── Source 3–6: Market-wide RSS (matched to tickers by keyword) ───────────────

@st.cache_data(ttl=1800, show_spinner=False)
def _fetch_market_rss() -> list[dict]:
    rows = []
    for feed_url, source_name in _MARKET_RSS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:60]:
                rows.append({
                    "ticker": "",          # filled in by _match_ticker
                    "name":   "",
                    "date":   _parse_date(entry),
                    "title":  entry.get("title", ""),
                    "url":    entry.get("link", ""),
                    "source": source_name,
                })
        except Exception:
            continue
    return rows


def _match_ticker(title: str, symbol: str, company_name: str) -> bool:
    """Return True if this headline likely refers to the given stock."""
    t = title.upper()
    sym_clean = symbol.upper().replace("-", " ").replace("&", " ")
    if sym_clean in t or symbol.upper() in t:
        return True
    if company_name:
        # Match first meaningful word of company name (≥4 chars)
        words = [w for w in company_name.upper().split() if len(w) >= 4
                 and w not in {"LIMITED","LTD","INDIA","INDUSTRIES","CORPORATION"}]
        if words and words[0] in t:
            return True
    return False


# ── Public API ────────────────────────────────────────────────────────────────

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_all_news(pages: int = 10) -> pd.DataFrame:
    """All news from Groww + market RSS feeds (no per-stock Google search)."""
    rows = _fetch_groww(pages)
    market = _fetch_market_rss()
    # market RSS rows have no ticker — label them as multi-stock news
    for r in market:
        r["ticker"] = r["ticker"] or "MARKET"
    rows.extend(market)
    if not rows:
        return _EMPTY.copy()
    return pd.DataFrame(rows)


def fetch_news_for_symbol(symbol: str, company_name: str = "", pages: int = 10) -> pd.DataFrame:
    """Fetch + merge news from all sources for one NSE symbol."""
    groww_all = _fetch_groww(pages)
    groww_sym = [r for r in groww_all if r["ticker"] == symbol.upper()]

    google    = _fetch_google_news(symbol, company_name)

    market_rss = _fetch_market_rss()
    matched    = [r for r in market_rss
                  if _match_ticker(r["title"], symbol, company_name)]
    for r in matched:
        r["ticker"] = symbol.upper()
        r["name"]   = company_name or symbol

    all_rows = groww_sym + google + matched
    if not all_rows:
        return _EMPTY.copy()

    df = pd.DataFrame(all_rows).drop_duplicates(subset=["title"]).reset_index(drop=True)
    df = df.sort_values("date", ascending=False).reset_index(drop=True)
    return df


# ── Sentiment via Groq ────────────────────────────────────────────────────────

def _score_chunk(client: Groq, headlines: list[str]) -> list[dict]:
    """Score one chunk of headlines. Returns list of dicts."""
    n      = len(headlines)
    prompt = f"""You are a financial sentiment analyst for Indian stock markets.
Analyse each headline. Return ONLY a valid JSON array of exactly {n} objects, each with:
  "sentiment": "positive" | "neutral" | "negative"
  "score": confidence float 0.0–1.0
  "emotion": one of "optimism" | "greed" | "fear" | "panic" | "confidence" | "uncertainty"

Headlines:
{chr(10).join(f"{i+1}. {h}" for i, h in enumerate(headlines))}

ONLY the JSON array. No markdown, no explanation."""

    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1200,
            temperature=0.1,
        )
        raw    = resp.choices[0].message.content.strip()
        start  = raw.find("[")
        end    = raw.rfind("]") + 1
        parsed = json.loads(raw[start:end])
        # Pad if model returned fewer
        while len(parsed) < n:
            parsed.append({"sentiment": "neutral", "score": 0.5, "emotion": "uncertainty"})
        return parsed[:n]
    except Exception:
        return [{"sentiment": "neutral", "score": 0.5, "emotion": "uncertainty"}] * n


@st.cache_data(ttl=1800, show_spinner=False)
def analyze_sentiment(articles_json: str, chunk_size: int = 20) -> pd.DataFrame:
    """
    Batch-score articles through Groq in chunks of `chunk_size`.
    Accepts JSON string so Streamlit can cache it.
    """
    articles = pd.read_json(articles_json)
    if articles.empty:
        return articles

    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        try:
            key = st.secrets.get("GROQ_API_KEY", "")
        except Exception:
            pass
    if not key:
        return articles  # return unscored rather than crash
    client   = Groq(api_key=key)
    heads    = articles["title"].str[:300].tolist()
    results  = []

    for i in range(0, len(heads), chunk_size):
        chunk = heads[i: i + chunk_size]
        results.extend(_score_chunk(client, chunk))
        if i + chunk_size < len(heads):
            time.sleep(0.3)   # gentle rate-limit buffer

    out = articles.copy()
    out["sentiment"] = [r.get("sentiment", "neutral") for r in results]
    out["score"]     = [float(r.get("score", 0.5))    for r in results]
    out["emotion"]   = [r.get("emotion", "uncertainty") for r in results]
    sm = {"positive": 1, "neutral": 0, "negative": -1}
    out["compound"]  = out["sentiment"].map(sm) * out["score"]
    return out


# ── Convenience wrapper ───────────────────────────────────────────────────────

def get_news_summary(symbol: str, company_name: str = "") -> dict:
    arts = fetch_news_for_symbol(symbol, company_name)
    if arts.empty:
        return {"articles": arts, "overall": 0.0, "label": "No news found",
                "positive": 0, "neutral": 0, "negative": 0, "count": 0}

    scored  = analyze_sentiment(arts.to_json())
    overall = scored["compound"].mean() if not scored.empty else 0.0
    counts  = scored["sentiment"].value_counts().to_dict()
    label   = "Positive" if overall > 0.15 else ("Negative" if overall < -0.15 else "Neutral")

    return {
        "articles": scored,
        "overall":  round(overall, 3),
        "label":    label,
        "positive": counts.get("positive", 0),
        "neutral":  counts.get("neutral",  0),
        "negative": counts.get("negative", 0),
        "count":    len(scored),
    }


def score_market_news(pages: int = 8) -> pd.DataFrame:
    """
    Fetch all Groww news + market RSS, score sentiment, return full DataFrame.
    Used for the market-wide sentiment chart.
    """
    df = fetch_all_news(pages)
    if df.empty:
        return df
    # Only score articles that have a proper ticker
    scoreable = df[df["ticker"].str.len() > 1].copy().reset_index(drop=True)
    if scoreable.empty:
        return scoreable
    return analyze_sentiment(scoreable.to_json())
