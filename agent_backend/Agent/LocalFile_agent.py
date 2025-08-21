from agno.agent import Agent
from agno.models.openrouter import OpenRouter
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.storage.postgres import PostgresStorage
from config import openrouter_api_key, database_url

import httpx
import os
import re

# ---------------- RAG tool ----------------

async def query_rag(question: str) -> str:
    base_url = "http://127.0.0.1:8000/api/v1/file/search"  # routable host
    try:
        url = f"{base_url}?user_id=demo"  # backend expects user_id in query
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                url,
                json={"query": question, "top_k": 5, "filters": None},  # backend expects JSON body
            )
            resp.raise_for_status()
            data = resp.json()

        hits = data.get("hits") or []
        if not hits:
            return "no_answer"

        # Sort by score desc when available, keep top 5
        def _score(x):
            s = x.get("score")
            try:
                return float(s)
            except Exception:
                return -1e9
        hits = sorted(hits, key=_score, reverse=True)[:5]

        texts, sources = [], []
        for h in hits:
            t = (h.get("text") or h.get("content") or "").strip()
            if t:
                texts.append(t)
            meta = h.get("meta") or h.get("metadata") or {}
            file_name = os.path.basename(meta.get("path", "")) or meta.get("file_name", "N/A")
            page = meta.get("chunk_idx", meta.get("page", "N/A"))
            sources.append(f"- {file_name} ({page})")

        # Generic extractive summary (no query heuristics)
        raw = " ".join(texts)
        raw = re.sub(r"\s+", " ", raw).strip()
        # sentence split
        sents = re.split(r"(?<=[.!?])\s+", raw) if raw else []
        seen, picked, total_chars = set(), [], 0
        MAX_SENTS, MAX_CHARS = 6, 900
        for s in sents:
            s = s.strip()
            if not s:
                continue
            k = re.sub(r"\s+", " ", s).lower()
            if k in seen:
                continue
            if total_chars + len(s) + (1 if picked else 0) > MAX_CHARS:
                break
            seen.add(k)
            picked.append(s)
            total_chars += len(s) + (1 if picked else 0)
            if len(picked) >= MAX_SENTS:
                break

        answer = " ".join(picked).strip() if picked else (raw[:MAX_CHARS] if raw else "")
        if not answer:
            return "no_answer"

        return f"Answer: {answer}\nSources:\n" + "\n".join(sources[:3])

    except httpx.RequestError as e:
        return f"Error fetching data: {e}"
    except Exception as e:
        return f"Error: {e}"

# ---------------- Storage ----------------

storage = PostgresStorage(table_name="agent_sessions", db_url=database_url)
# --- agent that MUST use the tool and echo extractive output ---
local_search_agent = Agent(
    model=OpenRouter(id="gpt-4.1", api_key=openrouter_api_key),
    name="local_search_agent",
    role=(
        "Always call query_rag(<user_question>) first. "
        "If the tool returns 'no_answer', output exactly 'no_answer'. "
        "Otherwise, return the tool output verbatim without extra text."
    ),
    tools=[query_rag],
    instructions=[
        "Call query_rag with the raw user question.",
        "Return its output exactly (it already contains 'Answer:' and 'Sources:').",
        "If it returns 'no_answer', output 'no_answer'."
    ],
    markdown=False,
    storage=storage,
    stream=True,
    add_datetime_to_instructions=True,
)