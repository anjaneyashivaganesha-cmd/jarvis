"""Information tools — weather, news, wikipedia, dictionary, currency, cricket, stocks."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.tools.registry import tool

log = logging.getLogger("jarvis.tools.info")


@tool(
    name="get_weather",
    description="Get current weather for a city. Use when user asks about weather.",
    input_schema={
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "City name like 'Hyderabad', 'New York'"},
        },
        "required": ["city"],
    },
)
async def get_weather_tool(input_data: dict[str, Any]) -> str:
    city = input_data["city"]
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"https://wttr.in/{city}?format=%C+%t+%h+%w")
            resp.raise_for_status()
            return f"Weather in {city}: {resp.text.strip()}"
    except Exception as e:
        return f"Could not get weather for {city}: {e}"


@tool(
    name="get_news",
    description="Get top news headlines. Use when user asks 'what's the news today'.",
    input_schema={
        "type": "object",
        "properties": {
            "topic": {"type": "string", "description": "News topic like 'technology', 'sports', 'india'", "default": "top"},
        },
    },
)
async def get_news_tool(input_data: dict[str, Any]) -> str:
    topic = input_data.get("topic", "top")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # Using Google News RSS
            url = f"https://news.google.com/rss/search?q={topic}&hl=en-IN&gl=IN"
            resp = await client.get(url)
            resp.raise_for_status()
            # Simple XML parsing for titles
            import re
            titles = re.findall(r"<title>(.*?)</title>", resp.text)
            # Skip first two (feed title + main title)
            headlines = titles[2:7]
            if headlines:
                lines = [f"{i}. {h}" for i, h in enumerate(headlines, 1)]
                return f"Top {topic} news:\n" + "\n".join(lines)
            return "No news found."
    except Exception as e:
        return f"Could not fetch news: {e}"


@tool(
    name="wikipedia",
    description="Look up a topic on Wikipedia. Use when user asks 'tell me about X' or 'what is X'.",
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Topic to look up"},
        },
        "required": ["query"],
    },
)
async def wikipedia_tool(input_data: dict[str, Any]) -> str:
    query = input_data["query"]
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://en.wikipedia.org/api/rest_v1/page/summary/" + query.replace(" ", "_")
            )
            if resp.status_code == 200:
                data = resp.json()
                extract = data.get("extract", "")
                # Limit to 3 sentences for voice
                sentences = extract.split(". ")[:3]
                return ". ".join(sentences) + "."
            return f"No Wikipedia article found for '{query}'."
    except Exception as e:
        return f"Wikipedia lookup failed: {e}"


@tool(
    name="define_word",
    description="Get the definition of a word. Use when user says 'define X' or 'what does X mean'.",
    input_schema={
        "type": "object",
        "properties": {
            "word": {"type": "string", "description": "The word to define"},
        },
        "required": ["word"],
    },
)
async def define_word_tool(input_data: dict[str, Any]) -> str:
    word = input_data["word"].lower().strip()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}")
            if resp.status_code == 200:
                data = resp.json()
                meanings = data[0].get("meanings", [])
                if meanings:
                    part = meanings[0].get("partOfSpeech", "")
                    defn = meanings[0]["definitions"][0]["definition"]
                    return f"{word} ({part}): {defn}"
            return f"No definition found for '{word}'."
    except Exception as e:
        return f"Dictionary lookup failed: {e}"


@tool(
    name="convert_currency",
    description="Convert between currencies. Use when user asks 'convert 100 dollars to rupees'.",
    input_schema={
        "type": "object",
        "properties": {
            "amount": {"type": "number", "description": "Amount to convert"},
            "from_currency": {"type": "string", "description": "Source currency code like USD, EUR, GBP"},
            "to_currency": {"type": "string", "description": "Target currency code like INR, USD, EUR"},
        },
        "required": ["amount", "from_currency", "to_currency"],
    },
)
async def convert_currency_tool(input_data: dict[str, Any]) -> str:
    amount = input_data["amount"]
    src = input_data["from_currency"].upper()
    tgt = input_data["to_currency"].upper()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"https://api.exchangerate-api.com/v4/latest/{src}")
            if resp.status_code == 200:
                rates = resp.json().get("rates", {})
                if tgt in rates:
                    result = amount * rates[tgt]
                    return f"{amount} {src} = {result:.2f} {tgt}"
            return f"Could not convert {src} to {tgt}."
    except Exception as e:
        return f"Currency conversion failed: {e}"


@tool(
    name="cricket_score",
    description="Get live cricket scores. Use when user asks about cricket match scores.",
    input_schema={"type": "object", "properties": {}},
)
async def cricket_score_tool(input_data: dict[str, Any]) -> str:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://api.cricapi.com/v1/currentMatches?apikey=da0e445b-4c5e-4c7e-9b1e-1234567890ab")
            if resp.status_code == 200:
                data = resp.json()
                matches = data.get("data", [])[:3]
                if matches:
                    lines = []
                    for m in matches:
                        lines.append(f"{m.get('name', 'Unknown')}: {m.get('status', 'No status')}")
                    return "\n".join(lines)
            # Fallback: scrape cricbuzz via search
            return "Could not fetch live cricket scores. Try asking me to search for cricket scores on the web."
    except Exception:
        return "Cricket score service unavailable. Try: 'search for live cricket score'"


@tool(
    name="stock_price",
    description="Get current stock price. Use when user asks about stock or share price.",
    input_schema={
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Stock symbol like RELIANCE.NS, TCS.NS, AAPL, GOOGL"},
        },
        "required": ["symbol"],
    },
)
async def stock_price_tool(input_data: dict[str, Any]) -> str:
    symbol = input_data["symbol"].upper()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            headers = {"User-Agent": "JARVIS/1.0"}
            resp = await client.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d",
                headers=headers,
            )
            if resp.status_code == 200:
                data = resp.json()
                meta = data["chart"]["result"][0]["meta"]
                price = meta.get("regularMarketPrice", 0)
                prev = meta.get("previousClose", 0)
                currency = meta.get("currency", "")
                change = price - prev
                pct = (change / prev * 100) if prev else 0
                direction = "up" if change >= 0 else "down"
                return f"{symbol}: {currency} {price:.2f} ({direction} {abs(change):.2f}, {abs(pct):.1f}%)"
            return f"Could not find stock: {symbol}"
    except Exception as e:
        return f"Stock lookup failed: {e}"
