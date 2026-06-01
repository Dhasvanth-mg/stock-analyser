"""
News fetcher + sentiment analyser for NSE stocks.
- Source: Groww public news feed (no API key required)
- Sentiment: Groq llama-3.3-70b (fast, no local model download)
"""

import json
import os
import requests
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

_EMPTY = pd.DataFrame(columns=["ticker", "name", "date", "title"])


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_all_news(pages: int = 10) -> pd.DataFrame:
    """Pull up to `pages` × 50 articles from Groww's stock news feed."""
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
                        })
        except Exception:
            break

    return pd.DataFrame(rows) if rows else _EMPTY.copy()


def fetch_news_for_symbol(symbol: str, pages: int = 10) -> pd.DataFrame:
    df = fetch_all_news(pages)
    if df.empty:
        return _EMPTY.copy()
    return df[df["ticker"] == symbol.upper()].reset_index(drop=True)


@st.cache_data(ttl=1800, show_spinner=False)
def analyze_sentiment(articles_json: str) -> pd.DataFrame:
    """
    Score each article via Groq. Accepts JSON string so Streamlit can cache it.
    Returns the same rows with sentiment/score/emotion/compound columns added.
    """
    articles = pd.read_json(articles_json)
    if articles.empty:
        return articles

    client  = Groq(api_key=os.getenv("GROQ_API_KEY", ""))
    heads   = articles["title"].str[:300].tolist()
    n       = len(heads)

    prompt = f"""You are a financial sentiment analyst specialising in Indian stock markets.
Analyse each headline and return ONLY a valid JSON array with exactly {n} objects.
Each object must have:
  "sentiment": "positive" | "neutral" | "negative"
  "score": confidence 0.0–1.0
  "emotion": one of "optimism" | "greed" | "fear" | "panic" | "confidence" | "uncertainty"

Headlines:
{chr(10).join(f"{i+1}. {h}" for i, h in enumerate(heads))}

Return ONLY the JSON array. No markdown, no explanation."""

    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.1,
        )
        raw   = resp.choices[0].message.content.strip()
        start = raw.find("[")
        end   = raw.rfind("]") + 1
        parsed = json.loads(raw[start:end])

        out = articles.copy()
        out["sentiment"] = [p.get("sentiment", "neutral") for p in parsed][:n]
        out["score"]     = [float(p.get("score", 0.5)) for p in parsed][:n]
        out["emotion"]   = [p.get("emotion", "uncertainty") for p in parsed][:n]
        sm = {"positive": 1, "neutral": 0, "negative": -1}
        out["compound"]  = out["sentiment"].map(sm) * out["score"]
        return out

    except Exception:
        out = articles.copy()
        out["sentiment"] = "neutral"
        out["score"]     = 0.5
        out["emotion"]   = "uncertainty"
        out["compound"]  = 0.0
        return out


def get_news_summary(symbol: str) -> dict:
    """
    Convenience wrapper: fetch + score news for one symbol.
    Returns a dict with 'articles' (DataFrame) and summary stats.
    """
    arts = fetch_news_for_symbol(symbol)
    if arts.empty:
        return {"articles": arts, "overall": 0.0, "label": "No news found",
                "positive": 0, "neutral": 0, "negative": 0, "count": 0}

    scored = analyze_sentiment(arts.to_json())
    overall = scored["compound"].mean() if not scored.empty else 0.0
    counts  = scored["sentiment"].value_counts().to_dict()

    if overall > 0.15:
        label = "Positive"
    elif overall < -0.15:
        label = "Negative"
    else:
        label = "Neutral"

    return {
        "articles": scored,
        "overall":  round(overall, 3),
        "label":    label,
        "positive": counts.get("positive", 0),
        "neutral":  counts.get("neutral",  0),
        "negative": counts.get("negative", 0),
        "count":    len(scored),
    }
