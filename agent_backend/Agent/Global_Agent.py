from agno.agent import Agent
from agno.models.openrouter import OpenRouter
from config import openrouter_api_key, database_url
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.storage.postgres import PostgresStorage

# Storage backend
storage = PostgresStorage(
    table_name="agent_sessions",
    db_url=database_url
)

web_agent = Agent(
    model=OpenRouter(id="gpt-4.1", api_key=openrouter_api_key),
    name="web_agent",
    role="Handle web search requests and general research",
    tools=[DuckDuckGoTools()],
    instructions=[
        "You are a professional web research assistant. Answer the question using web research. "
        "Always include sources in your response if available. "
        "Return your response in JSON format as follows:\n"
        "{\n"
        '  "answer": "<Your answer here>",\n'
        '  "sources": [{"title": "<source title>", "url": "<source URL>"}]\n'
        "}\n"
        "If no sources are found, return an empty list for sources."
    ],
    markdown=False,
    storage=storage,
    stream=True
)

judge_agent = Agent(
    model=OpenRouter(id="gpt-4.1", api_key=openrouter_api_key),
    name="judge_agent",
    role="Evaluate and select the best answer from multiple candidates",
    instructions=[
        "You are an impartial judge. Review the question and answer(s) provided. "
        "Always respond in JSON format with the following keys:\n"
        "{\n"
        '  "judgment": "<Your evaluation or recommendation>",\n'
        '  "improvements": "<Suggestions to improve the answer>"\n'
        "}\n"
        "Do not include any text outside the JSON."
    ],
    markdown=False,
    stream=True,
)

# New LLM-only agent with no external tools, answering based on own knowledge
llm_only_agent = Agent(
    model=OpenRouter(id="gpt-4.1", api_key=openrouter_api_key),
    name="llm_only_agent",
    role=(
        "You are a helpful assistant that answers questions based solely "
        "on your internal knowledge and reasoning. Do NOT perform any web searches or use external tools. "
        "Answer clearly and completely based on your own understanding."
    ),
    tools=[],  # No tools attached
    instructions=[
        "Answer the questions to the best of your knowledge without using web research or any external resources."
    ],
    markdown=False,
    storage=storage,
    stream=True,
)
