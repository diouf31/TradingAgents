"""
Free social sentiment data aggregator for crypto assets.

Combines:
1. Alternative.me Fear & Greed Index (free, no key) - market-wide sentiment
2. CoinGecko community data (free) - per-coin social stats & sentiment votes
3. LunarCrush (optional, paid) - detailed per-platform social metrics
"""
import logging
import os
import time
import json
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

_SESSION = requests.Session()
_CACHE: dict = {}
_CACHE_TTL = 600  # 10 minutes


def _cached_get(url: str, params: dict | None = None, headers: dict | None = None) -> dict:
    """GET with simple in-memory cache."""
    cache_key = f"{url}|{json.dumps(params or {}, sort_keys=True)}"
    now = time.time()
    if cache_key in _CACHE:
        ts, data = _CACHE[cache_key]
        if now - ts < _CACHE_TTL:
            return data

    for attempt in range(3):
        try:
            resp = _SESSION.get(url, params=params, headers=headers, timeout=15)
            if resp.status_code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            resp.raise_for_status()
            data = resp.json()
            _CACHE[cache_key] = (now, data)
            return data
        except requests.RequestException as e:
            if attempt < 2:
                time.sleep(3)
            else:
                raise RuntimeError(f"API error: {e}") from e
    return {}


# ---------------------------------------------------------------------------
# 1. Alternative.me Fear & Greed Index
# ---------------------------------------------------------------------------

def get_fear_greed_index(days: int = 7) -> str:
    """Fetch crypto Fear & Greed Index (free, no API key).

    Data sources: volatility (25%), market momentum/volume (25%),
    social media (15%), surveys (15%), BTC dominance (10%), trends (10%).
    """
    try:
        data = _cached_get(
            "https://api.alternative.me/fng/",
            params={"limit": days},
        )
    except RuntimeError as e:
        return f"[Fear & Greed Index unavailable: {e}]"

    if not data or "data" not in data:
        return "[No Fear & Greed data available]"

    entries = data["data"]
    lines = [
        "# Crypto Fear & Greed Index",
        "Source: Alternative.me (includes social media, volatility, momentum, dominance)",
        "Scale: 0=Extreme Fear, 25=Fear, 50=Neutral, 75=Greed, 100=Extreme Greed",
        "",
        "| Date | Value | Classification |",
        "|------|-------|----------------|",
    ]

    for entry in entries:
        ts = int(entry.get("timestamp", 0))
        date_str = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d") if ts else "N/A"
        value = entry.get("value", "N/A")
        classification = entry.get("value_classification", "N/A")
        lines.append(f"| {date_str} | {value} | {classification} |")

    lines.append("")

    # Trend analysis
    if len(entries) >= 2:
        current = int(entries[0].get("value", 50))
        previous = int(entries[-1].get("value", 50))
        diff = current - previous
        trend = "rising" if diff > 5 else "falling" if diff < -5 else "stable"
        lines.append(f"Trend over {days} days: {trend} (current={current}, {days}d ago={previous}, change={diff:+d})")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 2. CoinGecko Community & Sentiment Data
# ---------------------------------------------------------------------------

_TICKER_TO_COINGECKO = {
    "BTC": "bitcoin", "ETH": "ethereum", "BNB": "binancecoin",
    "SOL": "solana", "XRP": "ripple", "ADA": "cardano",
    "DOGE": "dogecoin", "DOT": "polkadot", "AVAX": "avalanche-2",
    "MATIC": "matic-network", "LINK": "chainlink", "UNI": "uniswap",
    "ATOM": "cosmos", "LTC": "litecoin", "FIL": "filecoin",
    "APT": "aptos", "ARB": "arbitrum", "OP": "optimism",
    "NEAR": "near", "SHIB": "shiba-inu", "TRX": "tron",
    "SUI": "sui", "PEPE": "pepe", "INJ": "injective-protocol",
    "TIA": "celestia", "RENDER": "render-token",
}


def _ticker_to_cg_id(ticker: str) -> str:
    """Convert yfinance-style ticker to CoinGecko ID."""
    symbol = ticker.split("-")[0].upper()
    return _TICKER_TO_COINGECKO.get(symbol, symbol.lower())


def get_coingecko_social(ticker: str) -> str:
    """Fetch CoinGecko community data and sentiment votes for a crypto asset."""
    cg_id = _ticker_to_cg_id(ticker)

    try:
        data = _cached_get(
            f"https://api.coingecko.com/api/v3/coins/{cg_id}",
            params={
                "localization": "false",
                "tickers": "false",
                "market_data": "false",
                "community_data": "true",
                "developer_data": "false",
            },
        )
    except RuntimeError as e:
        return f"[CoinGecko social data unavailable: {e}]"

    if not data:
        return f"[No CoinGecko data for {ticker}]"

    name = data.get("name", ticker)
    symbol = data.get("symbol", "").upper()
    community = data.get("community_data", {})
    sent_up = data.get("sentiment_votes_up_percentage")
    sent_down = data.get("sentiment_votes_down_percentage")
    watchlist = data.get("watchlist_portfolio_users")

    lines = [
        f"# CoinGecko Community Data for {name} ({symbol})",
        "",
    ]

    # Sentiment votes
    if sent_up is not None:
        lines.append("## Community Sentiment Votes")
        lines.append(f"- Bullish: {sent_up:.1f}%")
        lines.append(f"- Bearish: {sent_down:.1f}%" if sent_down else "- Bearish: N/A")
        if watchlist:
            lines.append(f"- Watchlist Users: {watchlist:,}")
        lines.append("")

    # Community stats
    if community:
        lines.append("## Social Platform Stats")
        reddit_subs = community.get("reddit_subscribers")
        reddit_active = community.get("reddit_accounts_active_48h")
        reddit_posts = community.get("reddit_average_posts_48h")
        reddit_comments = community.get("reddit_average_comments_48h")
        telegram = community.get("telegram_channel_user_count")
        twitter = community.get("twitter_followers")

        if reddit_subs:
            lines.append(f"- Reddit Subscribers: {reddit_subs:,}")
        if reddit_active:
            lines.append(f"- Reddit Active Users (48h): {reddit_active:,}")
        if reddit_posts:
            lines.append(f"- Reddit Avg Posts (48h): {reddit_posts:.1f}")
        if reddit_comments:
            lines.append(f"- Reddit Avg Comments (48h): {reddit_comments:.1f}")
        if telegram:
            lines.append(f"- Telegram Users: {telegram:,}")
        if twitter:
            lines.append(f"- Twitter Followers: {twitter:,}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 3. LunarCrush (optional, requires paid subscription)
# ---------------------------------------------------------------------------

def get_lunarcrush_social(ticker: str, trade_date: str) -> str | None:
    """Try LunarCrush if API key is available. Returns None if unavailable."""
    if not os.environ.get("LUNARCRUSH_API_KEY"):
        return None
    try:
        from tradingagents.dataflows.lunarcrush import get_social_data
        return get_social_data(ticker, trade_date)
    except Exception as e:
        logger.warning(f"LunarCrush fetch failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Combined social sentiment data
# ---------------------------------------------------------------------------

def get_social_sentiment_data(ticker: str, trade_date: str) -> str:
    """Aggregate social sentiment data from all available free sources.

    Priority: LunarCrush (if paid key) > CoinGecko + Fear & Greed (free)
    """
    sections = []

    # Try LunarCrush first (paid, most detailed)
    lc_data = get_lunarcrush_social(ticker, trade_date)
    if lc_data:
        sections.append(lc_data)
    else:
        # Free fallback: CoinGecko community + sentiment
        cg_social = get_coingecko_social(ticker)
        sections.append(cg_social)

    # Always include Fear & Greed Index (free, market-wide context)
    fng = get_fear_greed_index(days=7)
    sections.append(fng)

    return "\n\n".join(sections)
