from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import json
import re
from Agent.Global_Agent import web_agent, judge_agent, llm_only_agent  # Import your LLM-only agents
from Agent.LocalFile_agent import local_search_agent  # Import your local file agent

router = APIRouter()


def extract_sources(answer_text: str):
    # Fixed regex pattern without excessive escaping
    pattern = r"- \[(.*?)\]\((https?://[^\s)]+)\)"
    matches = re.findall(pattern, answer_text)
    return [{"title": title, "url": url} for title, url in matches] if matches else []


@router.post("/app/judge/stream")
async def judge_endpoint_stream(request: Request):
    data = await request.json()
    question = data.get("message", "")

    full_answer_web = ""
    full_answer_llm = ""
    full_answer_local = ""

    async def event_generator():
        nonlocal full_answer_web, full_answer_llm, full_answer_local

        # Stream web_agent answer
        web_stream = await web_agent.arun(question, stream=True)
        async for chunk in web_stream:
            if isinstance(chunk, str):
                content = chunk
            elif hasattr(chunk, "text"):
                content = chunk.text
            elif hasattr(chunk, "content"):
                content = chunk.content
            elif hasattr(chunk, "data"):
                content = chunk.data
            else:
                content = str(chunk)

            full_answer_web += content or ""
            yield f"data: {json.dumps({'type': 'answer1', 'content': content})}\n\n"

        # Stream llm_only_agent answer
        llm_stream = await llm_only_agent.arun(question, stream=True)
        async for chunk in llm_stream:
            if isinstance(chunk, str):
                content = chunk
            elif hasattr(chunk, "text"):
                content = chunk.text
            elif hasattr(chunk, "content"):
                content = chunk.content
            elif hasattr(chunk, "data"):
                content = chunk.data
            else:
                content = str(chunk)

            full_answer_llm += content or ""
            yield f"data: {json.dumps({'type': 'answer2', 'content': content})}\n\n"

        # Stream local_file_agent answer
        local_stream = await local_search_agent.arun(question, stream=True)
        async for chunk in local_stream:
            if isinstance(chunk, str):
                content = chunk
            elif hasattr(chunk, "text"):
                content = chunk.text
            elif hasattr(chunk, "content"):
                content = chunk.content
            elif hasattr(chunk, "data"):
                content = chunk.data
            else:
                content = str(chunk)

            full_answer_local += content or ""
            yield f"data: {json.dumps({'type': 'answer3', 'content': content})}\n\n"

        # Prepare judge prompt using all three answers
        cleaned_web = re.sub(r"\n- \[.*?\]\(.*?\)", "", full_answer_web)
        cleaned_web = re.split(r"Sources:", cleaned_web, flags=re.IGNORECASE)[0].strip()

        cleaned_llm = full_answer_llm.strip()  # No sources expected here
        cleaned_local = full_answer_local.strip()  # No sources expected here (or add if any)

        sources = extract_sources(full_answer_web)

        judge_prompt = f"""
Question: {question}

Answer 1 (Web Agent):
{cleaned_web}

Answer 2 (LLM Only Agent):
{cleaned_llm}

Answer 3 (Local File Agent):
{cleaned_local}

Please evaluate all three answers and provide suggestions for improvement in JSON format.
"""

        # Stream judge_agent evaluation
        judge_stream = await judge_agent.arun(judge_prompt, stream=True)
        async for chunk in judge_stream:
            if isinstance(chunk, str):
                content = chunk
            elif hasattr(chunk, "text"):
                content = chunk.text
            elif hasattr(chunk, "content"):
                content = chunk.content
            elif hasattr(chunk, "data"):
                content = chunk.data
            else:
                content = str(chunk)

            yield f"data: {json.dumps({'type': 'judgment', 'content': content, 'sources': sources})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
# from fastapi import FastAPI
# from fastapi.responses import StreamingResponse
# from pydantic import BaseModel
# from Agent.LocalFile_agent import local_search_agent
# from agent_backend.Agent.Global_Agent import web_agent
# from Agent.base_llm import baseLLM
# from Agent.Judge_agent import judge_agent
# import asyncio
# import json
# from langfuse_client import lf_client

# app = FastAPI()

# class QueryRequest(BaseModel):
#     query: str

# # --- helper functions ---
# async def _async_iterate(agen):
#     """Consume async generator into a queue for merging."""
#     queue = asyncio.Queue()

#     async def worker():
#         async for item in agen:
#             await queue.put(item)
#         await queue.put(None)

#     asyncio.create_task(worker())
#     return queue


# async def _merge_streams(queues):
#     """Merge outputs from multiple async generators concurrently."""
#     active = len(queues)
#     while active:
#         done, _ = await asyncio.wait(
#             [q.get() for q in queues], return_when=asyncio.FIRST_COMPLETED
#         )
#         for task in done:
#             item = task.result()
#             if item is None:
#                 active -= 1
#             else:
#                 yield item

# # --- streaming wrapper for each agent ---
# async def stream_output(name, agent, query, results: dict, trace):
#     """Stream agent output and store final result, tracked in Langfuse."""
#     collected = []

#     # Start Langfuse span for this agent
#     span = trace.span(name=f"{name}-agent")

#     async for chunk in agent.stream(query):
#         collected.append(chunk)
#         # Log each chunk to Langfuse
#         span.log_event("chunk", chunk)
#         yield f"data: {json.dumps({'agent': name, 'text': chunk})}\n\n"

#     final_answer = "".join(collected)
#     results[name] = final_answer
#     # End agent span with final output
#     span.end(output=final_answer)
#     yield f"data: {json.dumps({'agent': name, 'done': True})}\n\n"

# # --- main streaming route ---
# @app.post("/query/judge")
# async def query_stream(request: QueryRequest):
#     user_query = request.query
#     results = {}

#     # Start a Langfuse trace for the full pipeline
#     trace = lf_client.trace(name="judge-pipeline", user_id="user-123")

#     async def event_generator():
#         # Start streaming all 3 agents
#         tasks = [
#             stream_output("Local", local_search_agent, user_query, results, trace),
#             stream_output("Web", web_agent, user_query, results, trace),
#             stream_output("BaseLLM", baseLLM, user_query, results, trace),
#         ]

#         # Merge streams concurrently
#         agents_done = asyncio.as_completed([_async_iterate(t) for t in tasks])
#         async for chunk in _merge_streams(agents_done):
#             yield chunk

#         # After all agents finish, run Judge agent
#         judge_span = trace.span(name="judge")
#         judge_answer = await judge_agent.run({
#             "user_query": user_query,
#             "candidates": results
#         })
#         judge_span.end(output=judge_answer)

#         # End the full pipeline trace
#         trace.end()

#         # Yield Judge answer to frontend
#         yield f"data: {json.dumps({'agent': 'Judge', 'text': judge_answer, 'done': True})}\n\n"

#     return StreamingResponse(event_generator(), media_type="text/event-stream")

