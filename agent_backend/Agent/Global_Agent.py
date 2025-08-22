from agno.agent import Agent
from agno.models.openrouter import OpenRouter
from config import openrouter_api_key, database_url
from Tools.serper_agent import SerperTool
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
    tools=[SerperTool()],
    instructions=[
        "You are a professional web research assistant. Answer the question using web research. "
        "Always include sources in your response if available. "
        "Format sources as markdown links at the end: [Title](URL)"
    ],
    markdown=True,  # Enable markdown
    storage=storage,
    stream=True
)

judge_agent = Agent(
    model=OpenRouter(id="gpt-4.1", api_key=openrouter_api_key),
    name="judge_agent",
    role="Evaluate and select the best answer from multiple candidates",
    instructions=[
        "You are an impartial judge and answer selector.",
        "Your task is to evaluate the candidate answers (Local, Web, and BaseLLM) against the given query.",
        "Follow this priority strictly:",
        "1. If the Local answer contains query-specific information, prefer it over others.",
        "2. If the Local answer is incomplete, combine it with Web results if available.",
        "3. If neither Local nor Web provide sufficient coverage, fall back to BaseLLM.",
        "Provide your final selected answer clearly, then add a section titled 'Suggestions for Improvement' with brief recommendations."
    ],
    markdown=True,
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
