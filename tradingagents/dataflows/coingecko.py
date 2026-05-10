"""CoinGecko data provider for cryptocurrency fundamental analysis.

Provides the same function signatures as y_finance.py fundamental functions
so the vendor routing in interface.py can swap them transparently.
Uses the free CoinGecko API (no key required, ~30 req/min).
"""

import logging
import time
import os
import json
from datetime import datetime, timedelta
from typing import Annotated

import pandas as pd
import requests

from .crypto_utils import ticker_to_coingecko_id, parse_crypto_ticker, ticker_to_binance_symbol
from .config import get_config

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.coingecko.com/api/v3"
_SESSION = requests.Session()
_SESSION.headers.update({"Accept": "application/json"})

# Optional free demo key (get one at https://www.coingecko.com/en/api)
_CG_API_KEY = os.environ.get("COINGECKO_API_KEY", "")
if _CG_API_KEY:
    _SESSION.headers.update({"x-cg-demo-api-key": _CG_API_KEY})

# Simple in-memory cache: {cache_key: (timestamp, data)}
_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 300  # 5 minutes


def _cg_get(endpoint: str, params: dict | None = None, max_retries: int = 5) -> dict:
    """GET from CoinGecko with retry + simple cache."""
    cache_key = f"{endpoint}|{json.dumps(params or {}, sort_keys=True)}"
    now = time.time()
    if cache_key in _CACHE:
        ts, data = _CACHE[cache_key]
        if now - ts < _CACHE_TTL:
            return data

    url = f"{_BASE_URL}{endpoint}"
    for attempt in range(max_retries):
        try:
            resp = _SESSION.get(url, params=params, timeout=15)
            if resp.status_code == 429:
                delay = 5 * (2 ** attempt)  # 5, 10, 20, 40, 80s
                logger.warning(f"CoinGecko rate limited, retrying in {delay}s (attempt {attempt+1}/{max_retries})")
                time.sleep(delay)
                continue
            resp.raise_for_status()
            data = resp.json()
            _CACHE[cache_key] = (now, data)
            return data
        except requests.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(3)
            else:
                raise RuntimeError(f"CoinGecko API error: {e}") from e
    return {}


def _get_coin_data(ticker: str) -> dict:
    """Fetch comprehensive coin data from /coins/{id}."""
    coin_id = ticker_to_coingecko_id(ticker)
    return _cg_get(
        f"/coins/{coin_id}",
        {
            "localization": "false",
            "tickers": "false",
            "market_data": "true",
            "community_data": "true",
            "developer_data": "false",
            "sparkline": "false",
        },
    )


def _fmt(value, prefix="", suffix="", decimals=2):
    """Format a numeric value for display, handling None."""
    if value is None:
        return "N/A"
    if isinstance(value, (int, float)):
        if abs(value) >= 1e9:
            return f"{prefix}{value / 1e9:,.{decimals}f}B{suffix}"
        if abs(value) >= 1e6:
            return f"{prefix}{value / 1e6:,.{decimals}f}M{suffix}"
        return f"{prefix}{value:,.{decimals}f}{suffix}"
    return str(value)


# ---------------------------------------------------------------------------
# Public functions – signatures match the yfinance counterparts in y_finance.py
# ---------------------------------------------------------------------------

def get_fundamentals(
    ticker: Annotated[str, "crypto ticker, e.g. BTC-USD"],
    curr_date: Annotated[str, "current date (informational)"] = None,
) -> str:
    """Cryptocurrency market overview – replaces company fundamentals."""
    try:
        coin = _get_coin_data(ticker)
        md = coin.get("market_data", {})
        symbol_upper = coin.get("symbol", "").upper()
        name = coin.get("name", ticker)

        categories = ", ".join(coin.get("categories", []) or [])
        description = (coin.get("description", {}) or {}).get("en", "")
        if len(description) > 600:
            description = description[:600] + "…"

        lines = [
            f"# Cryptocurrency Fundamentals for {name} ({symbol_upper})",
            f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"Name: {name}",
            f"Symbol: {symbol_upper}",
            f"Categories: {categories or 'N/A'}",
            "",
            "## Market Data",
            f"Current Price (USD): {_fmt(md.get('current_price', {}).get('usd'), prefix='$')}",
            f"Market Cap (USD): {_fmt(md.get('market_cap', {}).get('usd'), prefix='$')}",
            f"Market Cap Rank: #{md.get('market_cap_rank', 'N/A')}",
            f"Fully Diluted Valuation: {_fmt(md.get('fully_diluted_valuation', {}).get('usd'), prefix='$')}",
            f"24h Trading Volume: {_fmt(md.get('total_volume', {}).get('usd'), prefix='$')}",
            "",
            "## Supply",
            f"Circulating Supply: {_fmt(md.get('circulating_supply'))}",
            f"Total Supply: {_fmt(md.get('total_supply'))}",
            f"Max Supply: {_fmt(md.get('max_supply'))}",
            "",
            "## Price Performance",
            f"24h Change: {_fmt(md.get('price_change_percentage_24h'), suffix='%')}",
            f"7d Change: {_fmt(md.get('price_change_percentage_7d'), suffix='%')}",
            f"14d Change: {_fmt(md.get('price_change_percentage_14d'), suffix='%')}",
            f"30d Change: {_fmt(md.get('price_change_percentage_30d'), suffix='%')}",
            f"60d Change: {_fmt(md.get('price_change_percentage_60d'), suffix='%')}",
            f"200d Change: {_fmt(md.get('price_change_percentage_200d'), suffix='%')}",
            f"1y Change: {_fmt(md.get('price_change_percentage_1y'), suffix='%')}",
            "",
            "## All-Time Records",
            f"All-Time High: {_fmt(md.get('ath', {}).get('usd'), prefix='$')}",
            f"ATH Date: {md.get('ath_date', {}).get('usd', 'N/A')}",
            f"ATH Change %: {_fmt(md.get('ath_change_percentage', {}).get('usd'), suffix='%')}",
            f"All-Time Low: {_fmt(md.get('atl', {}).get('usd'), prefix='$')}",
            f"ATL Date: {md.get('atl_date', {}).get('usd', 'N/A')}",
            f"ATL Change %: {_fmt(md.get('atl_change_percentage', {}).get('usd'), suffix='%')}",
            "",
            "## Community",
            f"CoinGecko Score: {coin.get('coingecko_score', 'N/A')}",
            f"Community Score: {coin.get('community_score', 'N/A')}",
            f"Liquidity Score: {coin.get('liquidity_score', 'N/A')}",
        ]

        if description:
            lines += ["", "## Description", description]

        return "\n".join(lines)

    except Exception as e:
        return f"Error fetching crypto fundamentals for {ticker}: {e}"


def get_balance_sheet(
    ticker: Annotated[str, "crypto ticker"],
    freq: Annotated[str, "not used for crypto"] = "quarterly",
    curr_date: Annotated[str, "current date"] = None,
) -> str:
    """Tokenomics & supply data – replaces company balance sheet."""
    try:
        coin = _get_coin_data(ticker)
        md = coin.get("market_data", {})
        name = coin.get("name", ticker)
        symbol = coin.get("symbol", "").upper()

        lines = [
            f"# Tokenomics & Supply for {name} ({symbol})",
            f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Supply Metrics",
            f"Circulating Supply: {_fmt(md.get('circulating_supply'))}",
            f"Total Supply: {_fmt(md.get('total_supply'))}",
            f"Max Supply: {_fmt(md.get('max_supply'))}",
        ]

        circ = md.get("circulating_supply")
        total = md.get("total_supply")
        if circ and total and total > 0:
            lines.append(f"Circulating / Total Ratio: {circ / total * 100:.1f}%")

        max_s = md.get("max_supply")
        if circ and max_s and max_s > 0:
            lines.append(f"Circulating / Max Ratio: {circ / max_s * 100:.1f}%")

        mcap = md.get("market_cap", {}).get("usd")
        fdv = md.get("fully_diluted_valuation", {}).get("usd")
        lines += [
            "",
            "## Valuation",
            f"Market Cap: {_fmt(mcap, prefix='$')}",
            f"Fully Diluted Valuation: {_fmt(fdv, prefix='$')}",
        ]
        if mcap and fdv and fdv > 0:
            lines.append(f"Market Cap / FDV Ratio: {mcap / fdv * 100:.1f}%")

        vol = md.get("total_volume", {}).get("usd")
        lines += [
            "",
            "## Liquidity",
            f"24h Volume: {_fmt(vol, prefix='$')}",
        ]
        if mcap and vol and mcap > 0:
            lines.append(f"Volume / Market Cap Ratio: {vol / mcap * 100:.2f}%")

        return "\n".join(lines)

    except Exception as e:
        return f"Error fetching crypto tokenomics for {ticker}: {e}"


def get_cashflow(
    ticker: Annotated[str, "crypto ticker"],
    freq: Annotated[str, "not used for crypto"] = "quarterly",
    curr_date: Annotated[str, "current date"] = None,
) -> str:
    """On-chain activity & volume metrics – replaces company cash flow."""
    try:
        coin = _get_coin_data(ticker)
        md = coin.get("market_data", {})
        name = coin.get("name", ticker)
        symbol = coin.get("symbol", "").upper()

        vol_usd = md.get("total_volume", {}).get("usd")
        mcap = md.get("market_cap", {}).get("usd")

        lines = [
            f"# Market Activity for {name} ({symbol})",
            f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Volume",
            f"24h Trading Volume (USD): {_fmt(vol_usd, prefix='$')}",
        ]
        if mcap and vol_usd and mcap > 0:
            lines.append(f"Volume / Market Cap: {vol_usd / mcap * 100:.2f}%")

        lines += [
            "",
            "## Price Momentum",
            f"24h Price Change: {_fmt(md.get('price_change_percentage_24h'), suffix='%')}",
            f"7d Price Change: {_fmt(md.get('price_change_percentage_7d'), suffix='%')}",
            f"30d Price Change: {_fmt(md.get('price_change_percentage_30d'), suffix='%')}",
            "",
            "## Market Sentiment Indicators",
            f"High 24h: {_fmt(md.get('high_24h', {}).get('usd'), prefix='$')}",
            f"Low 24h: {_fmt(md.get('low_24h', {}).get('usd'), prefix='$')}",
        ]

        high = md.get("high_24h", {}).get("usd")
        low = md.get("low_24h", {}).get("usd")
        if high and low and low > 0:
            lines.append(f"24h Range Spread: {(high - low) / low * 100:.2f}%")

        community = coin.get("community_data", {})
        if community:
            lines += [
                "",
                "## Community Activity",
                f"Twitter Followers: {_fmt(community.get('twitter_followers'))}",
                f"Reddit Subscribers: {_fmt(community.get('reddit_subscribers'))}",
                f"Reddit Active Accounts (48h): {_fmt(community.get('reddit_accounts_active_48h'))}",
            ]

        return "\n".join(lines)

    except Exception as e:
        return f"Error fetching crypto market activity for {ticker}: {e}"


def get_income_statement(
    ticker: Annotated[str, "crypto ticker"],
    freq: Annotated[str, "not used for crypto"] = "quarterly",
    curr_date: Annotated[str, "current date"] = None,
) -> str:
    """Price performance & returns – replaces company income statement."""
    try:
        coin = _get_coin_data(ticker)
        md = coin.get("market_data", {})
        name = coin.get("name", ticker)
        symbol = coin.get("symbol", "").upper()

        lines = [
            f"# Price Performance & Returns for {name} ({symbol})",
            f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Current Price",
            f"USD: {_fmt(md.get('current_price', {}).get('usd'), prefix='$')}",
            f"BTC: {md.get('current_price', {}).get('btc', 'N/A')}",
            f"ETH: {md.get('current_price', {}).get('eth', 'N/A')}",
            "",
            "## Returns",
            f"24h: {_fmt(md.get('price_change_percentage_24h'), suffix='%')}",
            f"7d: {_fmt(md.get('price_change_percentage_7d'), suffix='%')}",
            f"14d: {_fmt(md.get('price_change_percentage_14d'), suffix='%')}",
            f"30d: {_fmt(md.get('price_change_percentage_30d'), suffix='%')}",
            f"60d: {_fmt(md.get('price_change_percentage_60d'), suffix='%')}",
            f"200d: {_fmt(md.get('price_change_percentage_200d'), suffix='%')}",
            f"1y: {_fmt(md.get('price_change_percentage_1y'), suffix='%')}",
            "",
            "## All-Time Benchmarks",
            f"ATH: {_fmt(md.get('ath', {}).get('usd'), prefix='$')} (on {md.get('ath_date', {}).get('usd', 'N/A')})",
            f"Distance from ATH: {_fmt(md.get('ath_change_percentage', {}).get('usd'), suffix='%')}",
            f"ATL: {_fmt(md.get('atl', {}).get('usd'), prefix='$')} (on {md.get('atl_date', {}).get('usd', 'N/A')})",
            f"Distance from ATL: {_fmt(md.get('atl_change_percentage', {}).get('usd'), suffix='%')}",
            "",
            "## Market Position",
            f"Market Cap Rank: #{md.get('market_cap_rank', 'N/A')}",
            f"CoinGecko Score: {coin.get('coingecko_score', 'N/A')}",
            f"Liquidity Score: {coin.get('liquidity_score', 'N/A')}",
        ]

        return "\n".join(lines)

    except Exception as e:
        return f"Error fetching crypto performance for {ticker}: {e}"


def get_insider_transactions(
    ticker: Annotated[str, "crypto ticker"],
) -> str:
    """Cryptocurrency does not have insider transactions in the traditional sense."""
    symbol, _ = parse_crypto_ticker(ticker)
    return (
        f"# Insider Transactions for {symbol}\n\n"
        "Insider transaction data is not applicable for cryptocurrencies. "
        "Unlike publicly traded companies, crypto projects do not have SEC-mandated "
        "insider transaction disclosures.\n\n"
        "For on-chain whale activity and large holder movements, "
        "consider monitoring blockchain explorers or on-chain analytics platforms."
    )


# ---------------------------------------------------------------------------
# OHLCV & Technical Indicators — bypass yfinance for crypto
# ---------------------------------------------------------------------------

_BINANCE_BASE = "https://api.binance.com"


def _fetch_market_chart(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch daily OHLCV data from Binance public klines API (free, no key).

    Returns a DataFrame with columns: Date, Open, High, Low, Close, Volume
    compatible with yfinance / stockstats expectations.
    """
    binance_symbol = ticker_to_binance_symbol(ticker)
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int((end_dt + timedelta(days=1)).timestamp() * 1000) - 1  # inclusive

    all_rows = []
    cursor = start_ms
    while cursor <= end_ms:
        params = {
            "symbol": binance_symbol,
            "interval": "1d",
            "startTime": cursor,
            "endTime": end_ms,
            "limit": 1000,
        }
        for attempt in range(3):
            try:
                resp = requests.get(f"{_BINANCE_BASE}/api/v3/klines", params=params, timeout=15)
                if resp.status_code == 429:
                    time.sleep(5 * (attempt + 1))
                    continue
                resp.raise_for_status()
                rows = resp.json()
                break
            except requests.RequestException as e:
                if attempt == 2:
                    raise RuntimeError(f"Binance API error: {e}") from e
                time.sleep(2)
                rows = []
        else:
            rows = []

        if not rows:
            break
        all_rows.extend(rows)
        # Next batch starts after the last candle's close time
        cursor = rows[-1][6] + 1
        if len(rows) < 1000:
            break

    if not all_rows:
        return pd.DataFrame()

    # Binance kline format: [openTime, open, high, low, close, volume, closeTime, ...]
    df = pd.DataFrame(all_rows, columns=[
        "openTime", "Open", "High", "Low", "Close", "Volume",
        "closeTime", "quoteVolume", "trades", "takerBase", "takerQuote", "ignore",
    ])
    df["Date"] = pd.to_datetime(df["openTime"], unit="ms").dt.normalize()
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df[["Date", "Open", "High", "Low", "Close", "Volume"]]
    df = df.sort_values("Date").reset_index(drop=True)
    return df


def get_stock_data(
    symbol: Annotated[str, "crypto ticker, e.g. BTC-USD"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """Fetch OHLCV price data for a crypto asset via CoinGecko."""
    try:
        df = _fetch_market_chart(symbol, start_date, end_date)
        if df.empty:
            return f"No data found for symbol '{symbol}' between {start_date} and {end_date}"

        # Round for cleaner display
        for col in ["Open", "High", "Low", "Close"]:
            df[col] = df[col].round(2)

        df.index = df["Date"]
        csv_string = df[["Open", "High", "Low", "Close", "Volume"]].to_csv()

        header = f"# Crypto price data for {symbol.upper()} from {start_date} to {end_date}\n"
        header += f"# Source: CoinGecko (no yfinance dependency)\n"
        header += f"# Total records: {len(df)}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        return header + csv_string

    except Exception as e:
        return f"Error fetching CoinGecko OHLCV for {symbol}: {e}"


def get_indicators(
    symbol: Annotated[str, "crypto ticker, e.g. BTC-USD"],
    indicator: Annotated[str, "technical indicator to compute"],
    curr_date: Annotated[str, "current trading date, YYYY-mm-dd"],
    look_back_days: Annotated[int, "how many days to look back"],
) -> str:
    """Compute technical indicators for a crypto asset using CoinGecko OHLCV data."""
    from stockstats import wrap
    from dateutil.relativedelta import relativedelta

    best_ind_params = {
        "close_50_sma": "50 SMA: Medium-term trend indicator.",
        "close_200_sma": "200 SMA: Long-term trend benchmark.",
        "close_10_ema": "10 EMA: Short-term momentum.",
        "macd": "MACD: Momentum via EMA differences.",
        "macds": "MACD Signal: Smoothed MACD line.",
        "macdh": "MACD Histogram: Gap between MACD and signal.",
        "rsi": "RSI: Overbought/oversold momentum.",
        "boll": "Bollinger Middle: 20 SMA base.",
        "boll_ub": "Bollinger Upper Band: Overbought zone.",
        "boll_lb": "Bollinger Lower Band: Oversold zone.",
        "atr": "ATR: Average true range volatility.",
        "vwma": "VWMA: Volume-weighted moving average.",
        "mfi": "MFI: Money Flow Index (price + volume).",
    }

    if indicator not in best_ind_params:
        raise ValueError(
            f"Indicator {indicator} is not supported. Choose from: {list(best_ind_params.keys())}"
        )

    try:
        curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
        # Fetch enough history for 200-day indicators
        fetch_start = (curr_dt - timedelta(days=look_back_days + 250)).strftime("%Y-%m-%d")
        fetch_end = curr_date

        df = _fetch_market_chart(symbol, fetch_start, fetch_end)
        if df.empty:
            return f"No price data available for {symbol} to compute {indicator}"

        # stockstats needs these columns
        sdf = wrap(df.copy())
        sdf[indicator]  # trigger computation

        # Filter to look-back window
        before = curr_dt - relativedelta(days=look_back_days)
        sdf["Date_str"] = sdf["Date"].dt.strftime("%Y-%m-%d")

        ind_string = ""
        check_dt = curr_dt
        while check_dt >= before:
            ds = check_dt.strftime("%Y-%m-%d")
            row = sdf[sdf["Date_str"] == ds]
            if not row.empty:
                val = row[indicator].iloc[0]
                ind_string += f"{ds}: {'N/A' if pd.isna(val) else val}\n"
            else:
                ind_string += f"{ds}: N/A: No data for this date\n"
            check_dt -= timedelta(days=1)

        result_str = (
            f"## {indicator} values from {before.strftime('%Y-%m-%d')} to {curr_date}:\n\n"
            + ind_string + "\n\n"
            + best_ind_params.get(indicator, "")
        )
        return result_str

    except Exception as e:
        return f"Error computing {indicator} for {symbol}: {e}"
