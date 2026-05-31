"""
Groq-powered AI stock analysis using llama3-70b.
"""

import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

_client = None

def _get_client():
    global _client
    if _client is None:
        key = os.getenv("GROQ_API_KEY", "")
        if not key:
            raise ValueError("GROQ_API_KEY not set")
        _client = Groq(api_key=key)
    return _client


def get_ai_analysis(row: dict) -> str:
    """
    Given a stock's metrics dict, return a short AI analysis + signal.
    Returns plain text: signal line + 2-3 sentence reasoning.
    """
    prompt = f"""You are a concise Indian stock market analyst. Analyse this NSE stock and give:
1. Signal: BUY / HOLD / SELL
2. 2–3 sentence reasoning based on the metrics.

Stock: {row.get('Symbol')} ({row.get('Name')})
Sector: {row.get('Sector')} | Category: {row.get('Cap Category')}
Price: ₹{row.get('Price (₹)')} | Change: {row.get('Change %')}%
P/E: {row.get('P/E')} | P/B: {row.get('P/B')} | EPS: ₹{row.get('EPS')}
Market Cap: ₹{row.get('Mkt Cap (₹Cr)')} Cr | Revenue: ₹{row.get('Revenue (₹Cr)')} Cr
Net Income: ₹{row.get('Net Inc (₹Cr)')} Cr | Div Yield: {row.get('Div Yield %')}%
Beta: {row.get('Beta')} | 52W High: ₹{row.get('52W High')} | 52W Low: ₹{row.get('52W Low')}

Be concise. Start with "Signal: BUY/HOLD/SELL".
"""
    try:
        client = _get_client()
        resp = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"AI analysis unavailable: {e}"


def get_portfolio_summary(stocks: list[dict]) -> str:
    """Summarise a list of stocks as a portfolio commentary."""
    if not stocks:
        return "No stocks selected."

    lines = "\n".join(
        f"- {s['Symbol']} ({s['Cap Category']}): ₹{s['Price (₹)']} | P/E {s['P/E']} | {s['Change %']}% today"
        for s in stocks[:10]
    )
    prompt = f"""You are an Indian stock market analyst. Give a brief portfolio summary (4-5 sentences) for these NSE stocks:

{lines}

Mention overall sentiment, sector concentration risk, and one actionable insight.
"""
    try:
        client = _get_client()
        resp = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.4,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"Portfolio summary unavailable: {e}"
