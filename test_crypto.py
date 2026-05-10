"""Quick smoke test for crypto data layer."""
from tradingagents.dataflows.crypto_utils import is_crypto_ticker, ticker_to_coingecko_id
from tradingagents.dataflows.coingecko import get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement, get_insider_transactions

# 1. Test crypto ticker detection
print("=== Crypto Ticker Detection ===")
for t in ["BTC-USD", "ETH-USD", "AAPL", "NVDA", "SOL-USDT", "DOGE-USD"]:
    print(f"  {t:12s} -> is_crypto={is_crypto_ticker(t)}")

# 2. Test CoinGecko ID mapping
print("\n=== CoinGecko ID Mapping ===")
for t in ["BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD"]:
    print(f"  {t:12s} -> {ticker_to_coingecko_id(t)}")

# 3. Test data fetching
print("\n=== get_fundamentals('BTC-USD') ===")
result = get_fundamentals("BTC-USD")
print(result[:500])

print("\n=== get_balance_sheet('ETH-USD') ===")
result = get_balance_sheet("ETH-USD")
print(result[:500])

print("\n=== get_cashflow('BTC-USD') ===")
result = get_cashflow("BTC-USD")
print(result[:500])

print("\n=== get_income_statement('BTC-USD') ===")
result = get_income_statement("BTC-USD")
print(result[:500])

print("\n=== get_insider_transactions('BTC-USD') ===")
result = get_insider_transactions("BTC-USD")
print(result)

# 4. Test routing (crypto ticker auto-routes to coingecko)
print("\n=== Route-to-vendor test ===")
from tradingagents.dataflows.interface import route_to_vendor
result = route_to_vendor("get_fundamentals", "BTC-USD")
print(result[:300])
print("\n...OK! Routing works for crypto.")

# 5. Verify stock still works
result = route_to_vendor("get_fundamentals", "AAPL")
print(f"\n=== Stock routing (AAPL) ===")
print(result[:300])
print("\n...OK! Stock routing unaffected.")
