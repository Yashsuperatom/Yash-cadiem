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
        
        try:
            # Stream Answer 1 (Web Agent)
            yield f"data: {json.dumps({'type': 'answer1_start', 'content': ''})}\n\n"
            
            web_stream = await web_agent.arun(question, stream=True)
            async for chunk in web_stream:
                content = extract_content(chunk)
                full_answer_web += content or ""
                yield f"data: {json.dumps({'type': 'answer1', 'content': content})}\n\n"
            
            # Extract sources from web answer
            sources1 = extract_sources(full_answer_web)
            yield f"data: {json.dumps({'type': 'answer1_complete', 'sources': sources1})}\n\n"
            
            # Stream Answer 2 (LLM Only)
            yield f"data: {json.dumps({'type': 'answer2_start', 'content': ''})}\n\n"
            
            llm_stream = await llm_only_agent.arun(question, stream=True)
            async for chunk in llm_stream:
                content = extract_content(chunk)
                full_answer_llm += content or ""
                yield f"data: {json.dumps({'type': 'answer2', 'content': content})}\n\n"
            
            yield f"data: {json.dumps({'type': 'answer2_complete', 'sources': []})}\n\n"
            
            # Stream Answer 3 (Local File)
            yield f"data: {json.dumps({'type': 'answer3_start', 'content': ''})}\n\n"
            
            local_stream = await local_search_agent.arun(question, stream=True)
            async for chunk in local_stream:
                content = extract_content(chunk)
                full_answer_local += content or ""
                yield f"data: {json.dumps({'type': 'answer3', 'content': content})}\n\n"
            
            # Extract sources from local answer
            sources3 = extract_local_sources(full_answer_local)
            yield f"data: {json.dumps({'type': 'answer3_complete', 'sources': sources3})}\n\n"
            
            # Stream Final Judgment
            yield f"data: {json.dumps({'type': 'judgment_start', 'content': ''})}\n\n"
            
            judge_prompt = f"""
Question: {question}

Answer 1 (Web Agent): {clean_answer(full_answer_web)}
Answer 2 (LLM Only Agent): {clean_answer(full_answer_llm)}
Answer 3 (Local File Agent): {clean_answer(full_answer_local)}

Please evaluate all three answers and provide your final selected answer followed by suggestions for improvement.
"""
            
            judge_stream = await judge_agent.arun(judge_prompt, stream=True)
            async for chunk in judge_stream:
                content = extract_content(chunk)
                yield f"data: {json.dumps({'type': 'judgment', 'content': content})}\n\n"
            
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"
            
        except Exception as e:
            # Handle any errors during streaming
            yield f"data: {json.dumps({'type': 'error', 'content': f'Error: {str(e)}'})}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")

def extract_content(chunk):
    if isinstance(chunk, str):
        return chunk
    elif hasattr(chunk, "text"):
        return chunk.text
    elif hasattr(chunk, "content"):
        return chunk.content
    elif hasattr(chunk, "data"):
        return chunk.data
    else:
        return str(chunk)

def clean_answer(answer: str) -> str:
    # Remove JSON formatting if present
    try:
        parsed = json.loads(answer)
        return parsed.get("answer", answer)
    except:
        return answer

def extract_local_sources(answer: str):
    # Extract sources from local file format
    sources = []
    lines = answer.split('\n')
    for line in lines:
        if line.strip().startswith('- ') and '(' in line:
            # Extract file name and page
            source_text = line.strip()[2:]  # Remove '- '
            sources.append({"title": source_text, "url": "#"})
    return sources
