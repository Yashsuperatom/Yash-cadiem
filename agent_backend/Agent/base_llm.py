# from agno.agent import Agent
# from agno.storage.postgres import PostgresStorage
# from agno.models.openrouter import OpenRouter
# from config import openrouter_api_key,database_url


# store = PostgresStorage(
#     table_name="base_llm",
#     db_url=database_url

# )

# baseLLM = Agent(
#     name= "LLM Base",
#     model= OpenRouter(id="gpt-5", api_key=openrouter_api_key),
#     role=["You are a helpful and knowledgeable assistant. "
#     "Your role is to provide clear, accurate, and well-structured answers "
#     "based entirely on your own internal knowledge and reasoning. "
#     "Do NOT perform any web searches, use external tools, or rely on outside data. "
#     "Focus on giving complete, thoughtful, and easy-to-understand responses "
#     "that directly address the user's question."],
#     storage=store,
#     stream=True,
#     instructions = [
#     "Answer all questions using only your internal knowledge and reasoning.",
#     "Do not use web searches, external tools, or outside resources.",
#     "Provide clear, accurate, and complete responses that directly address the user's query."
# ],
# markdown=True,
# add_datetime_to_instructions=True,
# )
