from __future__ import annotations
from typing_extensions import TypedDict
from typing import List, Dict, Any

from langgraph.graph import StateGraph, START, END

from agent_app.embedding import Embedder
from agent_app.vectorstore import get_collection
from agent_app.config import SETTINGS
from agent_app.db import init_db

class QueryState(TypedDict, total=False):
    user_id: str
    query: str
    top_k: int
    filters: dict | None
    query_vec: list[float]
    candidates: list[dict]
    hits: list[dict]
    answer: str | None
    model: str | None

async def embed_query(s: QueryState) -> QueryState:
    emb = await Embedder().embed_texts([s["query"]])
    s["query_vec"] = emb[0]
    return s

def ann_search(s: QueryState) -> QueryState:
    col = get_collection()
    res = col.query(query_embeddings=[s["query_vec"]], n_results=int(s.get("top_k", 10)))
    ids = res.get("ids") or []
    if not ids or not ids[0]:
        s["candidates"] = []
        s["hits"] = []
        return s
    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]
    out = []
    for i in range(len(ids[0])):
        out.append({
            "id": ids[0][i],
            "text": docs[i] if i < len(docs) else "",
            "score": dists[i] if i < len(dists) else None,
            "meta": metas[i] if i < len(metas) else {},
        })
    s["candidates"] = out
    s["hits"] = out
    return s

def finalize(s: QueryState) -> QueryState:
    return s

def build_graph(*, checkpointer=None):
    """Compile the graph with an optional checkpointer (injected by FastAPI at runtime)."""
    init_db()
    g = StateGraph(QueryState)
    g.add_node("embed_query", embed_query)
    g.add_node("ann_search", ann_search)
    g.add_node("finalize", finalize)

    g.add_edge(START, "embed_query")
    g.add_edge("embed_query", "ann_search")
    g.add_edge("ann_search", "finalize")
    g.add_edge("finalize", END)

    return g.compile(checkpointer=checkpointer)

# Expose only NO-checkpointer graph at import (for Studio)
query_graph_api = build_graph(checkpointer=None)
