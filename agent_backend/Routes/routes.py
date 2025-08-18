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
