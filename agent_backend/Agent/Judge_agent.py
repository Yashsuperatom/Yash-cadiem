import re
import json
from typing import List, Dict, Any
from Agent.Global_Agent import judge_agent, web_agent, llm_only_agent  # Existing agents
from Agent.LocalFile_agent import local_search_agent  # Your local LLM agent
# from agno.agent import Agent
# from agno.models.openrouter import OpenRouter
# from agno.storage.postgres import PostgresStorage
# from config import database_url,openrouter_api_key
# from Agent.web_Agent import web_agent
# from Agent.base_llm import baseLLM
# from Agent.LocalFile_agent import local_search_agent



def extract_sources(answer_text: str) -> List[Dict[str, str]]:
    """
    Extract markdown links from a 'Sources:' section in the answer.
    Returns a list of dicts: [{"title": ..., "url": ...}, ...]
    """
    pattern = r"- \[(.*?)\]\((https?://[^\s)]+)\)"
    matches = re.findall(pattern, answer_text)
    return [{"title": title, "url": url} for title, url in matches] if matches else []


async def get_answer_and_judgment(question: str) -> Dict[str, Any]:
    """
    1. Get answer from web_agent
    2. Get answer from llm_only_agent
    3. Get answer from local_file_agent (new)
    4. Extract sources
    5. Clean main answer texts
    6. Query judge_agent for evaluation
    7. Return structured result with all three answers
    """
    # Query web_agent
    web_resp = await web_agent.arun(question, stream=False)
    web_raw = web_resp.content
    try:
        web_json = json.loads(web_raw)
    except Exception:
        web_json = {"answer": web_raw, "sources": []}
    web_sources = extract_sources(web_json.get("answer", ""))
    web_answer = re.sub(r"\n- \[.*?\]\(.*?\)", "", web_json.get("answer", ""))
    web_answer = re.split(r"Sources:", web_answer, flags=re.IGNORECASE)[0].strip()

    # Query llm_only_agent
    llm_resp = await llm_only_agent.arun(question, stream=False)
    llm_raw = llm_resp.content
    try:
        llm_json = json.loads(llm_raw)
    except Exception:
        llm_json = {"answer": llm_raw}
    llm_answer = llm_json.get("answer", llm_raw)
    llm_sources = []

    # Query local_file_agent (local LLM)
    local_resp = await local_search_agent.arun(question, stream=False)
    local_raw = local_resp.content
    try:
        local_json = json.loads(local_raw)
    except Exception:
        local_json = {"answer": local_raw}
    local_answer = local_json.get("answer", local_raw)
    local_sources = []  # Add extraction if your local agent returns sources

    # Prepare judge prompt including all three answers
    judge_prompt = f"""
Question: {question}

Answer 1 (Web Agent):
{web_answer}

Answer 2 (LLM Only Agent):
{llm_answer}

Answer 3 (Local File Agent):
{local_answer}

Please evaluate all three answers and provide judgments and suggestions for improvement in JSON format.
"""

    # Query judge_agent
    judge_resp = await judge_agent.arun(judge_prompt, stream=False)
    judge_raw = judge_resp.content if judge_resp else "{}"
    try:
        judgment_json = json.loads(judge_raw)
    except Exception:
        judgment_json = {"judgment": "", "improvements": ""}

    return {
        "answer1": web_answer,
        "sources1": web_sources,
        "answer2": llm_answer,
        "sources2": llm_sources,
        "answer3": local_answer,
        "sources3": local_sources,
        "judgment": judgment_json.get("judgment", ""),
        "improvements": judgment_json.get("improvements", ""),
    }

# store = PostgresStorage(
#     table_name="judge_agent",
#     db_url=database_url
# )
# # Instead of AgentGroup, run sub-agents manually
# local_answer = local_search_agent.run("some query")
# web_answer = web_agent.run("some query")
# base_answer = baseLLM.run("some query")

# candidates = f"""
# Agent 1 (Local File Agent): {local_answer}

# Agent 2 (Web Agent): {web_answer}

# Agent 3 (Base LLM): {base_answer}
# """

# judge_agent = Agent(
#     model=OpenRouter(id="gpt-5", api_key=openrouter_api_key),
#     name="judge_agent",
#     role="Answer Evaluator",
#     instructions=[
#         "You are the Judge Agent. Your job is to evaluate multiple candidate answers for a given user query and select the single best answer.",
#         "Rules:",
#         "1. Prefer the Local File Agent if it is relevant.",
#         "2. Otherwise, select the most accurate, clear, and complete answer.",
#         "Only return ONE final answer with a short justification."
#     ],
#     markdown=True,
#     stream=True,
# )
