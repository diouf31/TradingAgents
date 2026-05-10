"""Utilities for detecting cryptocurrency tickers and mapping to CoinGecko IDs."""

import re

# Common yfinance crypto ticker → CoinGecko ID mapping
_TICKER_TO_COINGECKO = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "BNB": "binancecoin",
    "SOL": "solana",
    "XRP": "ripple",
    "ADA": "cardano",
    "DOGE": "dogecoin",
    "DOT": "polkadot",
    "AVAX": "avalanche-2",
    "MATIC": "matic-network",
    "POL": "matic-network",
    "LINK": "chainlink",
    "UNI": "uniswap",
    "ATOM": "cosmos",
    "LTC": "litecoin",
    "ETC": "ethereum-classic",
    "XLM": "stellar",
    "ALGO": "algorand",
    "FIL": "filecoin",
    "NEAR": "near",
    "APT": "aptos",
    "ARB": "arbitrum",
    "OP": "optimism",
    "SUI": "sui",
    "SEI": "sei-network",
    "TIA": "celestia",
    "SHIB": "shiba-inu",
    "PEPE": "pepe",
    "WIF": "dogwifcoin",
    "AAVE": "aave",
    "MKR": "maker",
    "CRV": "curve-dao-token",
    "LDO": "lido-dao",
    "RENDER": "render-token",
    "FET": "artificial-superintelligence-alliance",
    "INJ": "injective-protocol",
    "TRX": "tron",
    "TON": "the-open-network",
    "BCH": "bitcoin-cash",
    "ICP": "internet-computer",
    "HBAR": "hedera-hashgraph",
    "VET": "vechain",
    "FTM": "fantom",
    "SAND": "the-sandbox",
    "MANA": "decentraland",
    "AXS": "axie-infinity",
    "THETA": "theta-token",
    "GRT": "the-graph",
    "ENS": "ethereum-name-service",
}

# Fiat suffixes used in yfinance crypto tickers (e.g. BTC-USD, ETH-EUR)
_FIAT_SUFFIXES = {
    "USD", "EUR", "GBP", "JPY", "KRW", "CNY", "AUD", "CAD",
    "CHF", "HKD", "SGD", "INR", "BRL", "USDT", "USDC", "BUSD",
}

# Regex: <CRYPTO_SYMBOL>-<FIAT>  (e.g. BTC-USD, ETH-USDT)
_CRYPTO_TICKER_RE = re.compile(
    r"^([A-Z0-9]+)-(" + "|".join(_FIAT_SUFFIXES) + r")$",
    re.IGNORECASE,
)


def is_crypto_ticker(ticker: str) -> bool:
    """Return True if *ticker* looks like a yfinance cryptocurrency pair."""
    return bool(_CRYPTO_TICKER_RE.match(ticker.strip().upper()))


def parse_crypto_ticker(ticker: str) -> tuple[str, str]:
    """Split 'BTC-USD' into ('BTC', 'USD'). Raises ValueError if not crypto."""
    m = _CRYPTO_TICKER_RE.match(ticker.strip().upper())
    if not m:
        raise ValueError(f"'{ticker}' is not a recognized crypto ticker")
    return m.group(1), m.group(2)


def ticker_to_coingecko_id(ticker: str) -> str:
    """Map a yfinance-style crypto ticker to a CoinGecko coin ID.

    Falls back to lowercased symbol if not in the known mapping.
    """
    symbol, _ = parse_crypto_ticker(ticker)
    return _TICKER_TO_COINGECKO.get(symbol.upper(), symbol.lower())


# Mapping of yfinance fiat suffixes to Binance quote assets
_FIAT_TO_BINANCE_QUOTE = {
    "USD": "USDT",   # Binance uses USDT for USD pairs
    "USDT": "USDT",
    "USDC": "USDC",
    "BUSD": "BUSD",
    "EUR": "EUR",
    "GBP": "GBP",
    "JPY": "JPY",
    "BRL": "BRL",
}


def ticker_to_binance_symbol(ticker: str) -> str:
    """Convert 'BTC-USD' to 'BTCUSDT' for Binance API.

    Falls back to <SYMBOL>USDT if quote currency is not mapped.
    """
    symbol, fiat = parse_crypto_ticker(ticker)
    quote = _FIAT_TO_BINANCE_QUOTE.get(fiat.upper(), "USDT")
    return f"{symbol.upper()}{quote}"
