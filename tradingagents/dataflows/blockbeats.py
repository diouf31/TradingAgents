"""BlockBeats API — crypto news data source.

Provides real-time crypto news (newsflash) and articles via BlockBeats API.
API docs: https://www.theblockbeats.info/apiDoc

Environment variable:
    BLOCKBEATS_API_KEY  – API key for authentication (required).
"""

import logging
import os
import re
import time
from datetime import datetime, timedelta
from typing import Annotated

import requests

logger = logging.getLogger(__name__)

_BASE_URL = "http://api-pro.theblockbeats.info"
_SESSION = requests.Session()

# Simple in-memory cache: key -> (timestamp, data)
_CACHE: dict[str, tuple[float, any]] = {}
_CACHE_TTL = 300  # 5 minutes


def _get_api_key() -> str:
    """Get BlockBeats API key from environment."""
    return os.environ.get("BLOCKBEATS_API_KEY", "")


def _bb_get(endpoint: str, params: dict | None = None) -> dict:
    """GET from BlockBeats API with caching."""
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("BLOCKBEATS_API_KEY not set")

    cache_key = f"{endpoint}|{params}"
    now = time.time()
    if cache_key in _CACHE:
        ts, data = _CACHE[cache_key]
        if now - ts < _CACHE_TTL:
            return data

    headers = {"api-key": api_key}
    url = f"{_BASE_URL}{endpoint}"

    for attempt in range(3):
        try:
            resp = _SESSION.get(url, params=params, headers=headers, timeout=15)
            if resp.status_code == 429:
                time.sleep(3 * (attempt + 1))
                continue
            resp.raise_for_status()
            data = resp.json()
            _CACHE[cache_key] = (now, data)
            return data
        except requests.RequestException as e:
            if attempt < 2:
                time.sleep(2)
            else:
                raise RuntimeError(f"BlockBeats API error: {e}") from e
    return {}


def _strip_html(text: str) -> str:
    """Remove HTML tags from content."""
    return re.sub(r"<[^>]+>", "", text).strip()


def _parse_crypto_symbol(ticker: str) -> str:
    """Extract base symbol from ticker like 'BTC-USD' -> 'BTC'."""
    if "-" in ticker:
        return ticker.split("-")[0].upper()
    return ticker.upper()


def get_news(
    ticker: Annotated[str, "crypto ticker, e.g. BTC-USD"],
    start_date: Annotated[str, "Start date yyyy-mm-dd"],
    end_date: Annotated[str, "End date yyyy-mm-dd"],
) -> str:
    """Fetch crypto news from BlockBeats search API for a specific ticker."""
    try:
        symbol = _parse_crypto_symbol(ticker)

        # Use search endpoint to find ticker-specific news
        params = {
            "name": symbol,
            "page": 1,
            "size": 20,
            "lang": "en",
        }
        data = _bb_get("/v1/search", params)

        items = data.get("data", {}).get("data", [])
        if not items:
            # Fallback: try Chinese
            params["lang"] = "cn"
            data = _bb_get("/v1/search", params)
            items = data.get("data", {}).get("data", [])

        if not items:
            return f"No BlockBeats news found for {ticker}"

        # Filter by date range
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)

        lines = [f"## {symbol} News (BlockBeats), {start_date} to {end_date}\n"]
        count = 0

        for item in items:
            create_time = item.get("create_time", "")
            if create_time:
                try:
                    item_dt = datetime.strptime(create_time, "%Y-%m-%d %H:%M:%S")
                    if item_dt < start_dt or item_dt >= end_dt:
                        continue
                except ValueError:
                    pass

            title = item.get("title", "").strip()
            content = _strip_html(item.get("content", "") or item.get("abstract", ""))
            # Truncate long content
            if len(content) > 300:
                content = content[:300] + "..."

            lines.append(f"### {title}")
            if content:
                lines.append(content)
            if create_time:
                lines.append(f"_Published: {create_time}_")
            lines.append("")
            count += 1

            if count >= 15:
                break

        if count == 0:
            # If date filtering removed all, show most recent without filter
            lines = [f"## {symbol} Latest News (BlockBeats)\n"]
            for item in items[:10]:
                title = item.get("title", "").strip()
                content = _strip_html(item.get("content", "") or item.get("abstract", ""))
                if len(content) > 300:
                    content = content[:300] + "..."
                create_time = item.get("create_time", "")
                lines.append(f"### {title}")
                if content:
                    lines.append(content)
                if create_time:
                    lines.append(f"_Published: {create_time}_")
                lines.append("")

        return "\n".join(lines)

    except Exception as e:
        return f"Error fetching BlockBeats news for {ticker}: {e}"


def get_global_news(
    curr_date: Annotated[str, "Current date yyyy-mm-dd"],
    look_back_days: Annotated[int, "Days to look back"] = 7,
    limit: Annotated[int, "Max articles"] = 10,
) -> str:
    """Fetch global crypto news from BlockBeats important newsflash + articles."""
    try:
        lines = [f"## Global Crypto News (BlockBeats), as of {curr_date}\n"]

        # Important newsflash
        params = {"page": 1, "size": min(limit, 20), "lang": "en"}
        data = _bb_get("/v1/newsflash/important", params)
        items = data.get("data", {}).get("data", [])

        if not items:
            # Fallback to Chinese
            params["lang"] = "cn"
            data = _bb_get("/v1/newsflash/important", params)
            items = data.get("data", {}).get("data", [])

        if items:
            lines.append("### Important Newsflash\n")
            for item in items[:limit]:
                title = item.get("title", "").strip()
                content = _strip_html(item.get("content", ""))
                if len(content) > 200:
                    content = content[:200] + "..."
                create_time = item.get("create_time", "")
                lines.append(f"- **{title}**")
                if content:
                    lines.append(f"  {content}")
                if create_time:
                    lines.append(f"  _{create_time}_")
                lines.append("")

        # Also fetch recent articles for deeper context
        art_params = {"page": 1, "size": 5, "lang": "en"}
        art_data = _bb_get("/v1/article", art_params)
        articles = art_data.get("data", {}).get("data", [])

        if not articles:
            art_params["lang"] = "cn"
            art_data = _bb_get("/v1/article", art_params)
            articles = art_data.get("data", {}).get("data", [])

        if articles:
            lines.append("\n### Recent Articles\n")
            for art in articles[:5]:
                title = art.get("title", "").strip()
                desc = art.get("description", "") or ""
                create_time = art.get("create_time", "")
                lines.append(f"- **{title}**")
                if desc:
                    lines.append(f"  {desc[:200]}")
                if create_time:
                    lines.append(f"  _{create_time}_")
                lines.append("")

        return "\n".join(lines)

    except Exception as e:
        return f"Error fetching BlockBeats global news: {e}"
