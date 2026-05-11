import logging
from datetime import datetime, timedelta

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import build_instrument_context, get_language_instruction
from tradingagents.dataflows.interface import route_to_vendor
from tradingagents.dataflows.social_sentiment import get_social_sentiment_data

logger = logging.getLogger(__name__)


def _prefetch_social_data(ticker: str, trade_date: str) -> str:
    """Pre-fetch social sentiment data + ticker news."""
    sections = []

    # Social sentiment (LunarCrush if paid, else CoinGecko + Fear & Greed)
    try:
        sentiment = get_social_sentiment_data(ticker, trade_date)
        sections.append(sentiment)
    except Exception as e:
        logger.warning(f"Social sentiment fetch failed: {e}")
        sections.append(f"[Social sentiment data unavailable: {e}]")

    # Supplement: ticker news for context
    end_date = trade_date
    start_dt = datetime.strptime(trade_date, "%Y-%m-%d") - timedelta(days=7)
    start_date = start_dt.strftime("%Y-%m-%d")
    try:
        news = route_to_vendor("get_news", ticker, start_date, end_date)
        sections.append(news)
    except Exception as e:
        sections.append(f"[News data unavailable: {e}]")

    return "\n\n".join(sections)


def create_social_media_analyst(llm):
    def social_media_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        instrument_context = build_instrument_context(ticker)

        # Pre-fetch news data (eliminates tool-calling loop)
        logger.info("Social Media Analyst: pre-fetching data for %s", ticker)
        social_data = _prefetch_social_data(ticker, current_date)

        system_message = (
            "You are a social media and company specific news researcher/analyst tasked with analyzing social media posts, recent company news, and public sentiment for a specific company over the past week. "
            "Below is the news and social media data already retrieved. "
            "Write a comprehensive long report detailing your analysis, insights, and implications for traders and investors on this company's current state after looking at social media and what people are saying about that company, analyzing sentiment data of what people feel each day about the company, and looking at recent company news. "
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
                    "=== SOCIAL / NEWS DATA ===\n{social_data}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(
            system_message=system_message,
            current_date=current_date,
            instrument_context=instrument_context,
            social_data=social_data,
        )

        chain = prompt | llm

        result = chain.invoke(state["messages"])
        report = result.content

        return {
            "messages": [result],
            "sentiment_report": report,
        }

    return social_media_analyst_node
