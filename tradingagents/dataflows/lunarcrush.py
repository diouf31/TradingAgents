"""
LunarCrush API v4 integration for social media sentiment data.

Provides crypto social metrics from Twitter/X, Reddit, YouTube, TikTok, and News.
API Docs: https://github.com/lunarcrush/api
"""
import logging
import os
import time
import json
import requests
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

_BASE_URL = "https://lunarcrush.com/api4/public"
_SESSION = requests.Session()

# Cache to avoid repeated calls
_CACHE: dict = {}
_CACHE_TTL = 600  # 10 minutes

# Mapping from yfinance-style tickers to LunarCrush topics
_TICKER_TO_TOPIC = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "BNB": "bnb",
    "SOL": "solana",
    "XRP": "xrp",
    "ADA": "cardano",
    "DOGE": "dogecoin",
    "DOT": "polkadot",
    "AVAX": "avalanche",
    "MATIC": "polygon",
    "LINK": "chainlink",
    "UNI": "uniswap",
    "ATOM": "cosmos",
    "LTC": "litecoin",
    "FIL": "filecoin",
    "APT": "aptos",
    "ARB": "arbitrum",
    "OP": "optimism",
    "NEAR": "near protocol",
    "SHIB": "shiba inu",
    "TRX": "tron",
    "SUI": "sui",
    "PEPE": "pepe",
    "FET": "fetch ai",
    "RENDER": "render",
    "INJ": "injective",
    "TIA": "celestia",
}


def _get_api_key() -> str:
    """Get LunarCrush API key from environment."""
    return os.environ.get("LUNARCRUSH_API_KEY", "")


def _ticker_to_topic(ticker: str) -> str:
    """Convert yfinance-style ticker (e.g. BTC-USD) to LunarCrush topic."""
    symbol = ticker.split("-")[0].upper()
    if symbol in _TICKER_TO_TOPIC:
        return _TICKER_TO_TOPIC[symbol]
    # Fallback: use lowercase symbol as topic
    return symbol.lower()


def _lc_get(endpoint: str, params: dict | None = None) -> dict:
    """Make authenticated GET request to LunarCrush API with caching."""
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("LUNARCRUSH_API_KEY not set")

    cache_key = f"{endpoint}|{json.dumps(params or {}, sort_keys=True)}"
    now = time.time()
    if cache_key in _CACHE:
        ts, data = _CACHE[cache_key]
        if now - ts < _CACHE_TTL:
            return data

    url = f"{_BASE_URL}{endpoint}"
    headers = {"Authorization": f"Bearer {api_key}"}

    for attempt in range(3):
        try:
            resp = _SESSION.get(url, headers=headers, params=params, timeout=15)
            if resp.status_code == 429:
                delay = 10 * (attempt + 1)
                logger.warning(f"LunarCrush rate limited, retrying in {delay}s")
                time.sleep(delay)
                continue
            if resp.status_code == 401:
                raise RuntimeError("LunarCrush API key invalid (401 Unauthorized)")
            resp.raise_for_status()
            data = resp.json()
            _CACHE[cache_key] = (now, data)
            return data
        except requests.RequestException as e:
            if attempt < 2:
                time.sleep(3)
            else:
                raise RuntimeError(f"LunarCrush API error: {e}") from e
    return {}


def get_social_summary(ticker: str) -> str:
    """Get 24h social media summary for a crypto asset.

    Returns formatted text with sentiment breakdown by platform,
    interaction counts, contributor counts, and trend direction.
    """
    topic = _ticker_to_topic(ticker)

    try:
        data = _lc_get(f"/topic/{topic}/v1")
    except RuntimeError as e:
        return f"[LunarCrush social summary unavailable: {e}]"

    if not data or "data" not in data:
        return f"[No LunarCrush data available for {ticker}]"

    d = data["data"]
    config = data.get("config", {})

    lines = [
        f"# Social Media Summary for {config.get('name', topic)} ({config.get('symbol', ticker)})",
        f"Source: LunarCrush (24h aggregation)",
        f"",
        f"## Overview",
        f"- Topic Rank: #{d.get('topic_rank', 'N/A')}",
        f"- Total Posts (24h): {d.get('num_posts', 'N/A'):,}" if isinstance(d.get('num_posts'), int) else f"- Total Posts (24h): {d.get('num_posts', 'N/A')}",
        f"- Unique Contributors: {d.get('num_contributors', 'N/A'):,}" if isinstance(d.get('num_contributors'), int) else f"- Unique Contributors: {d.get('num_contributors', 'N/A')}",
        f"- Total Interactions (24h): {d.get('interactions_24h', 'N/A'):,}" if isinstance(d.get('interactions_24h'), int) else f"- Total Interactions (24h): {d.get('interactions_24h', 'N/A')}",
        f"- Trend: {d.get('trend', 'N/A')}",
        f"",
    ]

    # Sentiment by platform
    types_sentiment = d.get("types_sentiment", {})
    types_count = d.get("types_count", {})
    types_interactions = d.get("types_interactions", {})

    if types_sentiment:
        lines.append("## Sentiment by Platform (0%=negative, 50%=neutral, 100%=positive)")
        for platform in ["tweet", "reddit-post", "youtube-video", "tiktok-video", "news"]:
            if platform in types_sentiment:
                sentiment = types_sentiment[platform]
                count = types_count.get(platform, 0)
                interactions = types_interactions.get(platform, 0)
                platform_name = {
                    "tweet": "Twitter/X",
                    "reddit-post": "Reddit",
                    "youtube-video": "YouTube",
                    "tiktok-video": "TikTok",
                    "news": "News",
                }.get(platform, platform)
                lines.append(
                    f"- {platform_name}: Sentiment={sentiment}%, "
                    f"Posts={count:,}, Interactions={interactions:,}"
                )
        lines.append("")

    # Sentiment detail
    types_detail = d.get("types_sentiment_detail", {})
    if types_detail:
        lines.append("## Sentiment Breakdown (by interaction weight)")
        for platform, detail in types_detail.items():
            pos = detail.get("positive", 0)
            neu = detail.get("neutral", 0)
            neg = detail.get("negative", 0)
            total = pos + neu + neg
            if total > 0:
                platform_name = {
                    "tweet": "Twitter/X",
                    "reddit-post": "Reddit",
                    "youtube-video": "YouTube",
                    "tiktok-video": "TikTok",
                    "news": "News",
                }.get(platform, platform)
                lines.append(
                    f"- {platform_name}: "
                    f"Positive={pos:,} ({pos*100//total}%), "
                    f"Neutral={neu:,} ({neu*100//total}%), "
                    f"Negative={neg:,} ({neg*100//total}%)"
                )
        lines.append("")

    # Related topics
    related = d.get("related_topics", [])
    if related:
        lines.append(f"## Related Topics: {', '.join(related[:10])}")
        lines.append("")

    return "\n".join(lines)


def get_social_time_series(ticker: str, days: int = 7) -> str:
    """Get social metrics time series for a crypto asset.

    Returns daily sentiment, interactions, posts, and contributors over time.
    """
    topic = _ticker_to_topic(ticker)
    symbol = ticker.split("-")[0].upper()

    # Use coin time series endpoint with daily buckets
    end_ts = int(time.time())
    start_ts = end_ts - (days * 86400)

    try:
        data = _lc_get(f"/coins/{symbol}/time-series/v2", params={
            "bucket": "day",
            "start": start_ts,
            "end": end_ts,
        })
    except RuntimeError as e:
        return f"[LunarCrush time series unavailable: {e}]"

    if not data or "data" not in data:
        return f"[No LunarCrush time series for {ticker}]"

    series = data["data"]
    if not series:
        return f"[Empty LunarCrush time series for {ticker}]"

    config = data.get("config", {})
    lines = [
        f"# Social Media Time Series for {config.get('name', topic)} ({config.get('symbol', symbol)})",
        f"Source: LunarCrush | Period: {days} days | Bucket: daily",
        f"",
        "Date,Sentiment,Posts_Created,Posts_Active,Contributors,Interactions,Galaxy_Score,Social_Dominance",
    ]

    for point in series:
        ts = point.get("time", 0)
        date_str = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d") if ts else "N/A"
        lines.append(
            f"{date_str},"
            f"{point.get('sentiment', 'N/A')},"
            f"{point.get('posts_created', 'N/A')},"
            f"{point.get('posts_active', 'N/A')},"
            f"{point.get('contributors_active', 'N/A')},"
            f"{point.get('interactions', 'N/A')},"
            f"{point.get('galaxy_score', 'N/A')},"
            f"{point.get('social_dominance', 'N/A')}"
        )

    lines.append("")
    return "\n".join(lines)


def get_top_posts(ticker: str, limit: int = 10) -> str:
    """Get top social media posts for a crypto asset in the last 24h.

    Returns the most interacted posts with sentiment, creator info, and platform.
    """
    topic = _ticker_to_topic(ticker)

    try:
        data = _lc_get(f"/topic/{topic}/posts/v1")
    except RuntimeError as e:
        return f"[LunarCrush top posts unavailable: {e}]"

    if not data or "data" not in data:
        return f"[No LunarCrush posts for {ticker}]"

    posts = data["data"][:limit]
    if not posts:
        return f"[No recent posts found for {ticker}]"

    config = data.get("config", {})
    lines = [
        f"# Top Social Media Posts for {config.get('name', topic)} ({config.get('symbol', ticker.split('-')[0])})",
        f"Source: LunarCrush | Top {len(posts)} posts by interactions (24h)",
        f"",
    ]

    for i, post in enumerate(posts, 1):
        sentiment_score = post.get("post_sentiment", 3.0)
        sentiment_label = (
            "Very Negative" if sentiment_score < 1.5 else
            "Negative" if sentiment_score < 2.5 else
            "Neutral" if sentiment_score < 3.5 else
            "Positive" if sentiment_score < 4.5 else
            "Very Positive"
        )
        platform = {
            "tweet": "Twitter/X",
            "reddit-post": "Reddit",
            "youtube-video": "YouTube",
            "tiktok-video": "TikTok",
            "news": "News",
        }.get(post.get("post_type", ""), post.get("post_type", "unknown"))

        created = post.get("post_created", 0)
        date_str = datetime.utcfromtimestamp(created).strftime("%Y-%m-%d %H:%M") if created else "N/A"

        title = post.get("post_title", "")
        if len(title) > 200:
            title = title[:200] + "..."

        lines.append(f"## Post #{i} [{platform}] - {sentiment_label} ({sentiment_score:.1f}/5)")
        lines.append(f"- Creator: {post.get('creator_display_name', 'Unknown')} (@{post.get('creator_name', 'N/A')}) | Followers: {post.get('creator_followers', 0):,}")
        lines.append(f"- Time: {date_str}")
        lines.append(f"- Interactions: {post.get('interactions_24h', 0):,}")
        lines.append(f"- Content: {title}")
        lines.append(f"- Link: {post.get('post_link', 'N/A')}")
        lines.append("")

    return "\n".join(lines)


def get_social_data(ticker: str, trade_date: str) -> str:
    """Get comprehensive social media data for the social media analyst.

    Combines: social summary + time series + top posts.
    """
    sections = []

    # 1. Social summary (24h sentiment by platform)
    summary = get_social_summary(ticker)
    sections.append(summary)

    # 2. Social time series (7-day trend)
    time_series = get_social_time_series(ticker, days=7)
    sections.append(time_series)

    # 3. Top posts (most influential)
    top_posts = get_top_posts(ticker, limit=8)
    sections.append(top_posts)

    return "\n\n".join(sections)
