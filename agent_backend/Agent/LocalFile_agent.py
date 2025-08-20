# import requests
# import urllib.parse
 
# def query_rag(question, base_url="http://172.16.4.175:8000/api/v1/rag/query"):
#     try:
#         # Encode the question to be safe for URLs
#         encoded_question = urllib.parse.quote(question)
 
#         # Build the full URL
#         url = f"{base_url}?query={encoded_question}"
 
#         # Make the request
#         response = requests.get(url)
#         response.raise_for_status()
 
#         data = response.json()
#         results = data.get("results", [])[:2]  # First 2 only
 
#         # Combine content + metadata
#         combined = []
#         for idx, item in enumerate(results, start=1):
#             content = item.get("content", "").strip()
#             meta = item.get("metadata", {})
#             file_name = meta.get("file_name", "N/A")
#             page = meta.get("page", "N/A")
#             score = item.get("similarity_score", "N/A")
 
#             combined.append(
#                 f"--- Result {idx} ---\n"
#                 f"File: {file_name}\n"
#                 f"Page: {page}\n"
#                 f"Similarity: {score:.4f}\n"
#                 f"Content:\n{content}\n"
#             )
 
#         return "\n".join(combined)
 
#     except requests.exceptions.RequestException as e:
#         return f"Error fetching data: {e}"
#     except ValueError:
#         return "Error parsing JSON response"



# def test():
#     res = query_rag("Marshal")
#     print(res)

# # test()
from agno.agent import Agent
from agno.models.openrouter import OpenRouter
from config import openrouter_api_key, database_url
from agno.storage.postgres import PostgresStorage
import requests
import urllib.parse

# Your query_rag function, unchanged
def query_rag(question: str) -> str:
    base_url = "http://172.16.4.175:8001/api/v1/rag/query"
    try:
        encoded_question = urllib.parse.quote(question)
        url = f"{base_url}?query={encoded_question}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        results = data.get("results", [])[:2]

        combined = []
        for idx, item in enumerate(results, start=1):
            content = item.get("content", "").strip()
            meta = item.get("metadata", {})
            file_name = meta.get("file_name", "N/A")
            page = meta.get("page", "N/A")
            score = item.get("similarity_score", "N/A")

            combined.append(
                f"--- Result {idx} ---\n"
                f"File: {file_name}\n"
                f"Page: {page}\n"
                f"Similarity: {score:.4f}\n"
                f"Content:\n{content}\n"
            )
        return "\n".join(combined)
    except requests.exceptions.RequestException as e:
        return f"Error fetching data: {e}"
    except ValueError:
        return "Error parsing JSON response"


# Setup storage (reuse your config)
storage = PostgresStorage(table_name="agent_sessions", db_url=database_url)

# Create the Agent passing your search function directly in tools list; no Tool() wrapper
local_search_agent = Agent(
    model=OpenRouter(id="gpt-4o", api_key=openrouter_api_key),
    name="local_search_agent",
    role=(
        "You are an assistant that answers questions by searching a local file vector database. "
        "Use the provided search tool to fetch relevant excerpts and generate a helpful summary answer."
    ),
    tools=[query_rag],  # <- pass function directly here (not wrapped in Tool)
    instructions=[
        "First use the local_file_search tool to get relevant content, then answer based on that content."
    ],
    markdown=False,
    storage=storage,
    stream=True,
    add_datetime_to_instructions=True,
)




