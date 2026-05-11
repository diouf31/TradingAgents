import logging
from datetime import datetime, timedelta

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_language_instruction,
)
from tradingagents.dataflows.interface import route_to_vendor

logger = logging.getLogger(__name__)

# Standard set of indicators providing diverse, complementary insights
_DEFAULT_INDICATORS = ["rsi", "macd", "macds", "macdh", "boll", "boll_ub", "boll_lb", "atr"]


def _prefetch_market_data(ticker: str, trade_date: str) -> str:
    """Pre-fetch OHLCV + indicators and return as a single text block."""
    end_date = trade_date
    start_dt = datetime.strptime(trade_date, "%Y-%m-%d") - timedelta(days=35)
    start_date = start_dt.strftime("%Y-%m-%d")

    sections = []

    # OHLCV data
    try:
        ohlcv = route_to_vendor("get_stock_data", ticker, start_date, end_date)
        sections.append(ohlcv)
    except Exception as e:
        sections.append(f"[OHLCV data unavailable: {e}]")

    # Technical indicators
    for ind in _DEFAULT_INDICATORS:
        try:
            result = route_to_vendor("get_indicators", ticker, ind, trade_date, 30)
            sections.append(result)
        except Exception as e:
            sections.append(f"[{ind} unavailable: {e}]")

    return "\n\n".join(sections)


def create_market_analyst(llm):

    def market_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        instrument_context = build_instrument_context(ticker)

        # Pre-fetch all market data (eliminates tool-calling loop / multiple LLM round-trips)
        logger.info("Market Analyst: pre-fetching data for %s", ticker)
        market_data = _prefetch_market_data(ticker, current_date)

        system_message = (
            """You are a trading assistant tasked with analyzing financial markets. Below is the OHLCV price data and technical indicators already retrieved for the instrument. Analyze them and write a detailed report.

Indicator Reference:
- close_50_sma / close_200_sma / close_10_ema: Moving averages (trend direction, support/resistance)
- macd / macds / macdh: MACD family (momentum, crossovers, divergence)
- rsi: Relative Strength Index (overbought >70, oversold <30)
- boll / boll_ub / boll_lb: Bollinger Bands (volatility, breakouts)
- atr: Average True Range (volatility, stop-loss sizing)

Instructions:
- Write a detailed and nuanced report of the trends you observe.
- Provide specific, actionable insights with supporting evidence.
- Append a Markdown table at the end summarizing key findings."""
            + get_language_instruction()
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
                    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop.\n"
                    "{system_message}\n"
                    "Current date: {current_date}. {instrument_context}\n\n"
                    "=== MARKET DATA ===\n{market_data}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(
            system_message=system_message,
            current_date=current_date,
            instrument_context=instrument_context,
            market_data=market_data,
        )

        chain = prompt | llm

        result = chain.invoke(state["messages"])
        report = result.content

        return {
            "messages": [result],
            "market_report": report,
        }

    return market_analyst_node
