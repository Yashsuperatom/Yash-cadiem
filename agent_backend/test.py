from agno.agent import Agent
from agno.models.openrouter import OpenRouter
from agno.tools.reasoning import ReasoningTools
from agno.tools.yfinance import YFinanceTools
from config import openrouter_api_key

agent = Agent(
    model=OpenRouter(id="gpt-4o",api_key=openrouter_api_key),
    tools=[
        ReasoningTools(add_instructions=True),
        YFinanceTools(stock_price=True, analyst_recommendations=True, company_info=True, company_news=True),
    ],
    instructions="Use tables to display data",
    markdown=True,
)
print(openrouter_api_key,"key")