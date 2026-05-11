import logging
from datetime import datetime, timedelta

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_language_instruction,
)
from tradingagents.dataflows.interface import route_to_vendor

logger = logging.getLogger(__name__)


def _prefetch_news_data(ticker: str, trade_date: str) -> str:
    """Pre-fetch ticker news + global news and return as a single text block."""
    end_date = trade_date
    start_dt = datetime.strptime(trade_date, "%Y-%m-%d") - timedelta(days=7)
    start_date = start_dt.strftime("%Y-%m-%d")

    sections = []

    # Ticker-specific news
    try:
        news = route_to_vendor("get_news", ticker, start_date, end_date)
        sections.append(news)
    except Exception as e:
        sections.append(f"[Ticker news unavailable: {e}]")

    # Global / macro news
    try:
        global_news = route_to_vendor("get_global_news", trade_date, 7, 10)
        sections.append(global_news)
    except Exception as e:
        sections.append(f"[Global news unavailable: {e}]")

    return "\n\n".join(sections)


def create_news_analyst(llm):
    def news_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        instrument_context = build_instrument_context(ticker)

        # Pre-fetch all news data (eliminates tool-calling loop)
        logger.info("News Analyst: pre-fetching news for %s", ticker)
        news_data = _prefetch_news_data(ticker, current_date)

        system_message = (
            "You are a news researcher tasked with analyzing recent news and trends over the past week. "
            "Below is the ticker-specific news and global macroeconomic news already retrieved. "
            "Write a comprehensive report of the current state of the world that is relevant for trading and macroeconomics. "
            "Provide specific, actionable insights with supporting evidence to help traders make informed decisions."
            + """ Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."""
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
                    "=== NEWS DATA ===\n{news_data}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(
            system_message=system_message,
            current_date=current_date,
            instrument_context=instrument_context,
            news_data=news_data,
        )

        chain = prompt | llm
        result = chain.invoke(state["messages"])
        report = result.content

        return {
            "messages": [result],
            "news_report": report,
        }

    return news_analyst_node
