import logging

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_language_instruction,
)
from tradingagents.dataflows.interface import route_to_vendor
from tradingagents.dataflows.crypto_utils import is_crypto_ticker

logger = logging.getLogger(__name__)

_STOCK_SYSTEM = (
    "You are a researcher tasked with analyzing fundamental information over the past week about a company. Please write a comprehensive report of the company's fundamental information such as financial documents, company profile, basic company financials, and company financial history to gain a full view of the company's fundamental information to inform traders. Make sure to include as much detail as possible. Provide specific, actionable insights with supporting evidence to help traders make informed decisions."
    " Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."
)

_CRYPTO_SYSTEM = (
    "You are a researcher tasked with analyzing fundamental information about a cryptocurrency. Please write a comprehensive report covering: market overview (market cap, rank, fully diluted valuation), tokenomics (circulating supply, total supply, max supply, inflation schedule), price performance (multi-timeframe returns, distance from ATH/ATL), market activity (24h volume, volume/market cap ratio, liquidity score), and community/ecosystem health. Make sure to include as much detail as possible. Provide specific, actionable insights with supporting evidence to help traders make informed decisions."
    " Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."
)


def _prefetch_fundamentals_data(ticker: str, trade_date: str) -> str:
    """Pre-fetch all fundamental data and return as a single text block."""
    sections = []

    for method in ["get_fundamentals", "get_balance_sheet", "get_cashflow", "get_income_statement"]:
        try:
            result = route_to_vendor(method, ticker, trade_date)
            sections.append(result)
        except Exception as e:
            sections.append(f"[{method} unavailable: {e}]")

    return "\n\n".join(sections)


def create_fundamentals_analyst(llm):
    def fundamentals_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        instrument_context = build_instrument_context(ticker)

        # Pre-fetch all fundamental data (eliminates tool-calling loop)
        logger.info("Fundamentals Analyst: pre-fetching data for %s", ticker)
        fundamentals_data = _prefetch_fundamentals_data(ticker, current_date)

        base_msg = _CRYPTO_SYSTEM if is_crypto_ticker(ticker) else _STOCK_SYSTEM
        system_message = base_msg + get_language_instruction()

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
                    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop.\n"
                    "{system_message}\n"
                    "Current date: {current_date}. {instrument_context}\n\n"
                    "=== FUNDAMENTALS DATA ===\n{fundamentals_data}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(
            system_message=system_message,
            current_date=current_date,
            instrument_context=instrument_context,
            fundamentals_data=fundamentals_data,
        )

        chain = prompt | llm

        result = chain.invoke(state["messages"])
        report = result.content

        return {
            "messages": [result],
            "fundamentals_report": report,
        }

    return fundamentals_analyst_node
