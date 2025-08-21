# from __future__ import annotations
#
# from fastapi import FastAPI, HTTPException, Body, Query
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import Response
# from pydantic import BaseModel
# from typing import Any, Optional, Union, List
# from contextlib import asynccontextmanager
# from bs4 import BeautifulSoup
#
# import traceback, logging, time, json, os, re, httpx
#
# from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
#
#
# from agent_app.db import (
#     init_db, ensure_user, log_query_record, log_query_hits_records,
#     log_api_event, log_web_results, log_web_fetches
# )
#
# from agent_app.config import SETTINGS
# from agent_app.graphs.index_graph import build_graph as build_index_graph
# from agent_app.graphs.query_graph import build_graph as build_query_graph
#
# log = logging.getLogger(__name__)
#
#
# # =========================
# # Models & small utilities
# # =========================
#
# class IndexRequest(BaseModel):
#     roots: Optional[Union[List[str], str]] = None
#     force_reembed: bool = False  # ignored for /api/v1/index-full (we force True)
#     model: Optional[str] = None
#
#
# class SearchBody(BaseModel):
#     query: str
#     top_k: int = 10
#     filters: Optional[dict[str, Any]] = None  # JSON object if provided
#
#
# def _normalize_roots(val, default_roots):
#     if val is None:
#         return list(default_roots)
#     if isinstance(val, str):
#         return [val]
#     return [str(p) for p in val]
#
#
# def _lg_config(*, thread_id: str, run_id: Optional[str] = None) -> dict:
#     cfg = {"configurable": {"thread_id": thread_id}}
#     if run_id:
#         cfg["configurable"]["run_id"] = run_id
#     return cfg
#
#
# # =========================
# # App lifespan
# # =========================
#
# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     # Ensure DB init and checkpoint dir exists
#     init_db()
#     os.makedirs(SETTINGS.checkpoint_dir, exist_ok=True)
#
#     # Absolute sqlite paths for LangGraph AsyncSqliteSaver
#     index_db = os.path.abspath(os.path.join(SETTINGS.checkpoint_dir, "index.sqlite"))
#     query_db = os.path.abspath(os.path.join(SETTINGS.checkpoint_dir, "query.sqlite"))
#
#     # Keep async savers open for the entire app lifetime
#     async with AsyncSqliteSaver.from_conn_string(index_db) as index_cp, \
#             AsyncSqliteSaver.from_conn_string(query_db) as query_cp:
#         app.state.index_graph = build_index_graph(checkpointer=index_cp)
#         app.state.query_graph = build_query_graph(checkpointer=query_cp)
#         yield  # serve
#     # savers close on exit
#
#
# # =========================
# # Web helpers (search/scrape)
# # =========================
#
# VALID_ENGINES = {"exa", "serper"}
#
#
# def _parse_engines(engine_param: str) -> list[str]:
#     """
#     Accepts: "exa", "serper", "exa|serper", "serper,exa".
#     Returns a de-duplicated, validated list IN THE GIVEN ORDER.
#     No implicit fallback—single engine means single attempt.
#     """
#     if not engine_param or not engine_param.strip():
#         raise HTTPException(
#             status_code=400,
#             detail="engine is required (exa, serper, or a list like 'exa|serper')."
#         )
#     parts = [t.strip().lower() for t in re.split(r"[|,]", engine_param) if t.strip()]
#     if not parts:
#         raise HTTPException(status_code=400, detail="engine list is empty")
#
#     engines: list[str] = []
#     for p in parts:
#         if p not in VALID_ENGINES:
#             raise HTTPException(
#                 status_code=400,
#                 detail=f"unknown engine '{p}'. Allowed: {', '.join(sorted(VALID_ENGINES))}"
#             )
#         if p not in engines:  # de-dup preserve order
#             engines.append(p)
#     return engines[:3]  # safety cap; remove if you want unlimited
#
#
# def _pick_query(q: str | None, query: str | None) -> str:
#     qtxt = (q or query or "").strip()
#     if not qtxt:
#         raise HTTPException(status_code=400, detail="Missing query. Pass ?q=... or ?query=...")
#     return qtxt
#
#
# async def _extract_text_from_url(client: httpx.AsyncClient, url: str, timeout: float = 12.0) -> dict:
#     try:
#         r = await client.get(url, timeout=timeout, follow_redirects=True, headers={
#             "User-Agent": "Mozilla/5.0 (compatible; LocalAgent/1.0; +https://localhost)"
#         })
#         r.raise_for_status()
#         html = r.text
#         soup = BeautifulSoup(html, "html.parser")
#         for tag in soup(["script", "style", "noscript"]):
#             tag.decompose()
#         for sel in ["header", "nav", "footer", "aside"]:
#             for t in soup.select(sel):
#                 t.decompose()
#         text = " ".join(soup.get_text(separator=" ").split())
#         return {"ok": True, "text": text[:200000], "length": len(text), "status": r.status_code}
#     except Exception as e:
#         return {"ok": False, "error": str(e), "url": url}
#
#
# async def _exa_search(query_text: str, top_n: int, include_text: bool) -> dict:
#     api_key = os.getenv("EXA_API_KEY", "").strip()
#     if not api_key:
#         raise HTTPException(status_code=400, detail="EXA_API_KEY missing in environment")
#
#     base = "https://api.exa.ai"
#     payload = {"query": query_text, "numResults": max(1, min(top_n, 10))}
#     if include_text:
#         payload["text"] = True  # Exa can inline text
#
#     async with httpx.AsyncClient(timeout=15.0) as client:
#         r = await client.post(f"{base}/search", headers={
#             "x-api-key": api_key, "Content-Type": "application/json",
#         }, json=payload)
#         r.raise_for_status()
#         j = r.json()
#
#         results = []
#         for it in j.get("results", []):
#             results.append({
#                 "title": it.get("title"),
#                 "url": it.get("url"),
#                 "snippet": it.get("text") or it.get("description") or it.get("highlight"),
#                 "publishedDate": it.get("publishedDate"),
#                 "source": "exa",
#                 "text": it.get("text") if include_text else None,
#             })
#         return {"engine": "exa", "query": query_text, "results": results}
#
#
# async def _serper_search(query_text: str, top_n: int) -> dict:
#     api_key = os.getenv("SERPER_API_KEY", "").strip()
#     if not api_key:
#         raise HTTPException(status_code=400, detail="SERPER_API_KEY missing in environment")
#
#     url = "https://google.serper.dev/search"
#     body = {"q": query_text, "num": max(1, min(top_n, 10))}
#     async with httpx.AsyncClient(timeout=15.0) as client:
#         r = await client.post(url, headers={
#             "X-API-KEY": api_key, "Content-Type": "application/json",
#         }, json=body)
#         r.raise_for_status()
#         j = r.json()
#
#         results = []
#         for it in j.get("organic", []):
#             results.append({
#                 "title": it.get("title"),
#                 "url": it.get("link"),
#                 "snippet": it.get("snippet"),
#                 "source": "serper",
#             })
#         return {"engine": "serper", "query": query_text, "results": results}
#
#
# async def _maybe_scrape(results: list[dict], top_n: int) -> tuple[list[dict], list[dict]]:
#     """Fetch & extract text for top-N results; returns (results, scrape_logs)."""
#     if not results:
#         return results, []
#     logs: list[dict] = []
#     top = results[:top_n]
#     async with httpx.AsyncClient(timeout=15.0) as client:
#         for item in top:
#             url = item.get("url")
#             if not url:
#                 continue
#             t0 = time.perf_counter()
#             got = await _extract_text_from_url(client, url)
#             elapsed = int((time.perf_counter() - t0) * 1000)
#             if got.get("ok"):
#                 item["text"] = got["text"]
#                 item["scrape_status"] = got["status"]
#                 item["text_length"] = got["length"]
#                 logs.append({"url": url, "ok": True, "status": got["status"], "text_length": got["length"],
#                              "elapsed_ms": elapsed})
#             else:
#                 item["scrape_error"] = got.get("error")
#                 logs.append({"url": url, "ok": False, "status": None, "text_length": 0, "error": got.get("error"),
#                              "elapsed_ms": elapsed})
#     return results, logs
#
#
# # =========================
# # FastAPI app & middleware
# # =========================
# app = FastAPI(title="Local Agent (SQLite-logged)", lifespan=lifespan)
#
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=[
#         "http://localhost:3000", "http://127.0.0.1:3000",
#         "http://localhost:2024", "http://127.0.0.1:2024"
#     ],
#     allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
# )
#
#
# @app.get("/", include_in_schema=False)
# def root():
#     return {"message": "Welcome to the Local Agent API! Use /docs for documentation."}
#
#
# @app.get("/favicon.ico", include_in_schema=False)
# def favicon():
#     return Response(status_code=204)
#
#
# # =========================
# # Indexing
# # =========================
#
# @app.post("/api/v1/index-full")
# async def index_full(req: Optional[IndexRequest] = Body(None)):
#     """
#     HARD RESET:
#     - Fresh thread_id (avoids checkpoint resume)
#     - force_reembed=True (re-embed/upsert everything)
#     """
#     roots = _normalize_roots(req.roots if req else None, SETTINGS.default_roots)
#     if not roots:
#         raise HTTPException(status_code=400, detail="No roots provided. Pass 'roots' or set INDEX_ROOTS in .env")
#
#     state = {
#         "mode": "full",
#         "roots": roots,
#         "model": (req.model if req else None),
#         "force_reembed": True,
#         "stats": {}, "errors": []
#     }
#
#     tid = f"index:{int(time.time() * 1000)}"
#     cfg = _lg_config(thread_id=tid, run_id="index-full")
#
#     result = await app.state.index_graph.ainvoke(state, config=cfg)
#     return {"stats": result.get("stats", {}), "errors": result.get("errors", [])}
#
#
# @app.post("/api/v1/index")
# async def index_incremental(req: Optional[IndexRequest] = Body(None)):
#     """
#     Incremental:
#     - Fresh thread_id per run (fresh stats)
#     - Only changed/new files are embedded unless force_reembed=True
#     """
#     roots = _normalize_roots(req.roots if req else None, SETTINGS.default_roots)
#     if not roots:
#         raise HTTPException(status_code=400, detail="No roots provided. Pass 'roots' or set INDEX_ROOTS in .env")
#
#     state = {
#         "mode": "incremental",
#         "roots": roots,
#         "model": (req.model if req else None),
#         "force_reembed": bool(getattr(req, "force_reembed", False)),
#         "stats": {}, "errors": []
#     }
#
#     tid = f"index:{int(time.time() * 1000)}"
#     cfg = _lg_config(thread_id=tid, run_id="index-inc")
#
#     result = await app.state.index_graph.ainvoke(state, config=cfg)
#     return {"stats": result.get("stats", {}), "errors": result.get("errors", [])}
#
#
# # =========================
# # File search (POST-only)
# # user_id in QUERY PARAM (not in JSON)
# # =========================
#
# @app.post("/api/v1/file/search")
# async def search_post(
#         user_id: str = Query(..., description="User id for logging (required query param)"),
#         body: SearchBody = Body(...),
# ):
#     """
#     Example:
#       curl -s -X POST "http://127.0.0.1:8000/api/v1/file/search?user_id=demo" \
#         -H "Content-Type: application/json" \
#         -d '{"query":"hello world","top_k":5,"filters":{"mime":"text/plain"}}'
#     """
#     t0 = time.perf_counter()
#     uid = user_id.strip()
#     ensure_user(uid, None)
#
#     qstate = {
#         "user_id": uid,
#         "query": body.query,
#         "top_k": body.top_k,
#         "filters": body.filters,
#     }
#
#     cfg = _lg_config(thread_id=f"query:{uid}", run_id=f"q-{int(time.time() * 1000)}")
#
#     try:
#         result = await app.state.query_graph.ainvoke(qstate, config=cfg)
#         hits = result.get("hits", []) or []
#         latency_ms = int((time.perf_counter() - t0) * 1000)
#
#         qid = log_query_record(
#             user_id=uid, qtext=body.query, top_k=body.top_k,
#             filters_json=json.dumps(body.filters) if body.filters else None,
#             model=None, latency_ms=latency_ms,
#             response_json=json.dumps({"hits": hits}, ensure_ascii=False),
#         )
#         log_query_hits_records(qid, hits)
#
#         return {"query_id": qid, "latency_ms": latency_ms, "hits": hits}
#     except Exception as e:
#         log.exception("Search failed")
#         raise HTTPException(status_code=400, detail={
#             "message": "Search failed",
#             "hint": "Check OPENAI_API_KEY and that the index contains documents.",
#             "error": str(e),
#             "traceback": traceback.format_exc().splitlines()[-3:],
#         })
#
#
# # =========================
# # Web search (GET; ordered fallback across engines)
# # =========================
#
# @app.get("/api/v1/web/search")
# async def web_search(
#         engine: str,  # "exa", "serper", or "exa|serper"
#         q: str | None = None,
#         query: str | None = None,
#         data: bool = False,
#         top_n: int = Query(3, ge=1, le=10),
#         user_id: str | None = None,
# ):
#     """
#     Examples:
#       /api/v1/web/search?engine=exa&q=llm+observability
#       /api/v1/web/search?engine=exa|serper&q=ray+serve&data=true&top_n=2&user_id=demo
#       /api/v1/web/search?engine=serper,exa&query=python%20asyncio&data=true
#     """
#     import time as _time
#     t0 = _time.perf_counter()
#     uid = (user_id or "anonymous").strip()
#     ensure_user(uid, None)
#
#     qtxt = _pick_query(q, query)
#     engines = _parse_engines(engine)
#
#     attempt_errors: list[dict] = []
#     results: list[dict] = []
#     scrape_logs: list[dict] = []
#     scraped = 0
#     engine_used: str | None = None
#
#     for eng in engines:
#         try:
#             if eng == "exa":
#                 pack = await _exa_search(qtxt, top_n, include_text=data)
#                 results = pack["results"]
#                 engine_used = "exa"
#                 scraped = int(bool(data))  # Exa inlines text when data=true
#                 scrape_logs = []
#             elif eng == "serper":
#                 pack = await _serper_search(qtxt, top_n)
#                 results = pack["results"]
#                 engine_used = "serper"
#                 if data:
#                     results, scrape_logs = await _maybe_scrape(results, top_n=top_n)
#                     scraped = min(top_n, len(scrape_logs))
#                 else:
#                     scraped = 0
#                     scrape_logs = []
#             break  # success → stop trying others
#         except Exception as e:
#             attempt_errors.append({"engine": eng, "error": str(e)})
#
#     latency_ms = int((_time.perf_counter() - t0) * 1000)
#
#     if engine_used is None:
#         event_id = log_api_event(
#             user_id=uid, api="/api/v1/web/search",
#             request_obj={"engines": engines, "q": qtxt, "data": data, "top_n": top_n, "user_id": uid},
#             response_obj={"errors": attempt_errors},
#             status="error", latency_ms=latency_ms, notes="all engines failed"
#         )
#         raise HTTPException(
#             status_code=502,
#             detail={"message": "All engines failed", "attempts": attempt_errors, "event_id": event_id},
#         )
#
#     response_summary = {
#         "engine_used": engine_used,
#         "attempted_engines": engines,
#         "results_count": len(results),
#         "scraped": scraped,
#         "first_error": attempt_errors[0] if attempt_errors else None,
#     }
#     event_id = log_api_event(
#         user_id=uid, api="/api/v1/web/search",
#         request_obj={"engines": engines, "q": qtxt, "data": data, "top_n": top_n, "user_id": uid},
#         response_obj=response_summary, status="ok", latency_ms=latency_ms,
#         notes="fallback_ok" if attempt_errors else None,
#     )
#     log_web_results(event_id, results)
#     if data and scrape_logs:
#         log_web_fetches(event_id, scrape_logs)
#
#     return {
#         "engine": engine_used,
#         "attempted_engines": engines,
#         "q": qtxt,
#         "data": data,
#         "top_n": top_n,
#         "results": results,
#         "scraped": scraped,
#         "event_id": event_id,
#         "attempt_errors": attempt_errors,
#     }
#
# # http://localhost:8000/api/v1/web/search?engine=exa|serper&data=true













from __future__ import annotations

from fastapi import FastAPI, HTTPException, Body, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Any, Optional, Union, List
from contextlib import asynccontextmanager
from bs4 import BeautifulSoup

import traceback, logging, time, json, os, re, httpx

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver


from agent_app.db import (
    init_db, ensure_user, log_query_record, log_query_hits_records,
    log_api_event, log_web_results, log_web_fetches
)

from agent_app.config import SETTINGS
from agent_app.graphs.index_graph import build_graph as build_index_graph
from agent_app.graphs.query_graph import build_graph as build_query_graph

log = logging.getLogger(__name__)

# -------------------------
# Observability helpers (NO logic changes to indexing)
# -------------------------
def _log_watching_paths(roots: list[str]) -> None:
    """Log which roots will be scanned. Purely observational."""
    for r in roots:
        abspath = os.path.abspath(r)
        kind = "dir" if os.path.isdir(abspath) else ("file" if os.path.isfile(abspath) else "missing")
        print(f"[index] watching path: {abspath} ({kind})")
        try:
            log.info(f"[index] watching path: {abspath} ({kind})")
        except Exception:
            pass

def _log_discovered_files(roots: list[str]) -> None:
    """
    Log files discovered under the provided roots (non-intrusive; read-only).
    This does not filter by MIME or change what your graphs index.
    """
    for r in roots:
        abspath = os.path.abspath(r)
        if os.path.isfile(abspath):
            try:
                size = os.path.getsize(abspath)
            except Exception:
                size = "?"
            print(f"[index] discovered file: {abspath} ({size} bytes)")
            try:
                log.info(f"[index] discovered file: {abspath} ({size} bytes)")
            except Exception:
                pass
            continue

        if os.path.isdir(abspath):
            for dirpath, dirnames, filenames in os.walk(abspath, followlinks=False):
                for fname in filenames:
                    fpath = os.path.join(dirpath, fname)
                    try:
                        size = os.path.getsize(fpath)
                    except Exception:
                        size = "?"
                    print(f"[index] discovered file: {fpath} ({size} bytes)")
                    try:
                        log.info(f"[index] discovered file: {fpath} ({size} bytes)")
                    except Exception:
                        pass
        else:
            print(f"[index] path not found (skipping): {abspath}")
            try:
                log.warning(f"[index] path not found (skipping): {abspath}")
            except Exception:
                pass


# =========================
# Models & small utilities
# =========================

class IndexRequest(BaseModel):
    roots: Optional[Union[List[str], str]] = None
    force_reembed: bool = False  # ignored for /api/v1/index-full (we force True)
    model: Optional[str] = None


class SearchBody(BaseModel):
    query: str
    top_k: int = 10
    filters: Optional[dict[str, Any]] = None  # JSON object if provided


def _normalize_roots(val, default_roots):
    if val is None:
        return list(default_roots)
    if isinstance(val, str):
        return [val]
    return [str(p) for p in val]


def _lg_config(*, thread_id: str, run_id: Optional[str] = None) -> dict:
    cfg = {"configurable": {"thread_id": thread_id}}
    if run_id:
        cfg["configurable"]["run_id"] = run_id
    return cfg


# =========================
# App lifespan
# =========================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure DB init and checkpoint dir exists
    init_db()
    os.makedirs(SETTINGS.checkpoint_dir, exist_ok=True)

    # Absolute sqlite paths for LangGraph AsyncSqliteSaver
    index_db = os.path.abspath(os.path.join(SETTINGS.checkpoint_dir, "index.sqlite"))
    query_db = os.path.abspath(os.path.join(SETTINGS.checkpoint_dir, "query.sqlite"))

    # Keep async savers open for the entire app lifetime
    async with AsyncSqliteSaver.from_conn_string(index_db) as index_cp, \
            AsyncSqliteSaver.from_conn_string(query_db) as query_cp:
        app.state.index_graph = build_index_graph(checkpointer=index_cp)
        app.state.query_graph = build_query_graph(checkpointer=query_cp)
        yield  # serve
    # savers close on exit


# =========================
# Web helpers (search/scrape)
# =========================

VALID_ENGINES = {"exa", "serper"}


def _parse_engines(engine_param: str) -> list[str]:
    """
    Accepts: "exa", "serper", "exa|serper", "serper,exa".
    Returns a de-duplicated, validated list IN THE GIVEN ORDER.
    No implicit fallback—single engine means single attempt.
    """
    if not engine_param or not engine_param.strip():
        raise HTTPException(
            status_code=400,
            detail="engine is required (exa, serper, or a list like 'exa|serper')."
        )
    parts = [t.strip().lower() for t in re.split(r"[|,]", engine_param) if t.strip()]
    if not parts:
        raise HTTPException(status_code=400, detail="engine list is empty")

    engines: list[str] = []
    for p in parts:
        if p not in VALID_ENGINES:
            raise HTTPException(
                status_code=400,
                detail=f"unknown engine '{p}'. Allowed: {', '.join(sorted(VALID_ENGINES))}"
            )
        if p not in engines:  # de-dup preserve order
            engines.append(p)
    return engines[:3]  # safety cap; remove if you want unlimited


def _pick_query(q: str | None, query: str | None) -> str:
    qtxt = (q or query or "").strip()
    if not qtxt:
        raise HTTPException(status_code=400, detail="Missing query. Pass ?q=... or ?query=...")
    return qtxt


async def _extract_text_from_url(client: httpx.AsyncClient, url: str, timeout: float = 12.0) -> dict:
    try:
        r = await client.get(url, timeout=timeout, follow_redirects=True, headers={
            "User-Agent": "Mozilla/5.0 (compatible; LocalAgent/1.0; +https://localhost)"
        })
        r.raise_for_status()
        html = r.text
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        for sel in ["header", "nav", "footer", "aside"]:
            for t in soup.select(sel):
                t.decompose()
        text = " ".join(soup.get_text(separator=" ").split())
        return {"ok": True, "text": text[:200000], "length": len(text), "status": r.status_code}
    except Exception as e:
        return {"ok": False, "error": str(e), "url": url}


async def _exa_search(query_text: str, top_n: int, include_text: bool) -> dict:
    api_key = os.getenv("EXA_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="EXA_API_KEY missing in environment")

    base = "https://api.exa.ai"
    payload = {"query": query_text, "numResults": max(1, min(top_n, 10))}
    if include_text:
        payload["text"] = True  # Exa can inline text

    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(f"{base}/search", headers={
            "x-api-key": api_key, "Content-Type": "application/json",
        }, json=payload)
        r.raise_for_status()
        j = r.json()

        results = []
        for it in j.get("results", []):
            results.append({
                "title": it.get("title"),
                "url": it.get("url"),
                "snippet": it.get("text") or it.get("description") or it.get("highlight"),
                "publishedDate": it.get("publishedDate"),
                "source": "exa",
                "text": it.get("text") if include_text else None,
            })
        return {"engine": "exa", "query": query_text, "results": results}


async def _serper_search(query_text: str, top_n: int) -> dict:
    api_key = os.getenv("SERPER_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="SERPER_API_KEY missing in environment")

    url = "https://google.serper.dev/search"
    body = {"q": query_text, "num": max(1, min(top_n, 10))}
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(url, headers={
            "X-API-KEY": api_key, "Content-Type": "application/json",
        }, json=body)
        r.raise_for_status()
        j = r.json()

        results = []
        for it in j.get("organic", []):
            results.append({
                "title": it.get("title"),
                "url": it.get("link"),
                "snippet": it.get("snippet"),
                "source": "serper",
            })
        return {"engine": "serper", "query": query_text, "results": results}


async def _maybe_scrape(results: list[dict], top_n: int) -> tuple[list[dict], list[dict]]:
    """Fetch & extract text for top-N results; returns (results, scrape_logs)."""
    if not results:
        return results, []
    logs: list[dict] = []
    top = results[:top_n]
    async with httpx.AsyncClient(timeout=15.0) as client:
        for item in top:
            url = item.get("url")
            if not url:
                continue
            t0 = time.perf_counter()
            got = await _extract_text_from_url(client, url)
            elapsed = int((time.perf_counter() - t0) * 1000)
            if got.get("ok"):
                item["text"] = got["text"]
                item["scrape_status"] = got["status"]
                item["text_length"] = got["length"]
                logs.append({"url": url, "ok": True, "status": got["status"], "text_length": got["length"],
                             "elapsed_ms": elapsed})
            else:
                item["scrape_error"] = got.get("error")
                logs.append({"url": url, "ok": False, "status": None, "text_length": 0, "error": got.get("error"),
                             "elapsed_ms": elapsed})
    return results, logs


# =========================
# FastAPI app & middleware
# =========================
app = FastAPI(title="Local Agent (SQLite-logged)", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", "http://127.0.0.1:3000",
        "http://localhost:2024", "http://127.0.0.1:2024"
    ],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
def root():
    return {"message": "Welcome to the Local Agent API! Use /docs for documentation."}


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)


# =========================
# Indexing
# =========================

@app.post("/api/v1/index-full")
async def index_full(req: Optional[IndexRequest] = Body(None)):
    """
    HARD RESET:
    - Fresh thread_id (avoids checkpoint resume)
    - force_reembed=True (re-embed/upsert everything)
    """
    roots = _normalize_roots(req.roots if req else None, SETTINGS.default_roots)
    if not roots:
        raise HTTPException(status_code=400, detail="No roots provided. Pass 'roots' or set INDEX_ROOTS in .env")

    _log_watching_paths(roots)   # log which roots are being scanned
    _log_discovered_files(roots) # log which files were found under those roots

    state = {
        "mode": "full",
        "roots": roots,
        "model": (req.model if req else None),
        "force_reembed": True,
        "stats": {}, "errors": []
    }

    tid = f"index:{int(time.time() * 1000)}"
    cfg = _lg_config(thread_id=tid, run_id="index-full")

    result = await app.state.index_graph.ainvoke(state, config=cfg)
    return {"stats": result.get("stats", {}), "errors": result.get("errors", [])}


@app.post("/api/v1/index")
async def index_incremental(req: Optional[IndexRequest] = Body(None)):
    """
    Incremental:
    - Fresh thread_id per run (fresh stats)
    - Only changed/new files are embedded unless force_reembed=True
    """
    roots = _normalize_roots(req.roots if req else None, SETTINGS.default_roots)
    if not roots:
        raise HTTPException(status_code=400, detail="No roots provided. Pass 'roots' or set INDEX_ROOTS in .env")

    _log_watching_paths(roots)   # log which roots are being scanned
    _log_discovered_files(roots) # log which files were found under those roots

    state = {
        "mode": "incremental",
        "roots": roots,
        "model": (req.model if req else None),
        "force_reembed": bool(getattr(req, "force_reembed", False)),
        "stats": {}, "errors": []
    }

    tid = f"index:{int(time.time() * 1000)}"
    cfg = _lg_config(thread_id=tid, run_id="index-inc")

    result = await app.state.index_graph.ainvoke(state, config=cfg)
    return {"stats": result.get("stats", {}), "errors": result.get("errors", [])}


# =========================
# File search (POST-only)
# user_id in QUERY PARAM (not in JSON)
# =========================

@app.post("/api/v1/file/search")
async def search_post(
        user_id: str = Query(..., description="User id for logging (required query param)"),
        body: SearchBody = Body(...),
):
    """
    Example:
      curl -s -X POST "http://127.0.0.1:8000/api/v1/file/search?user_id=demo" \
        -H "Content-Type: application/json" \
        -d '{"query":"hello world","top_k":5,"filters":{"mime":"text/plain"}}'
    """
    t0 = time.perf_counter()
    uid = user_id.strip()
    ensure_user(uid, None)

    qstate = {
        "user_id": uid,
        "query": body.query,
        "top_k": body.top_k,
        "filters": body.filters,
    }

    cfg = _lg_config(thread_id=f"query:{uid}", run_id=f"q-{int(time.time() * 1000)}")

    try:
        result = await app.state.query_graph.ainvoke(qstate, config=cfg)
        hits = result.get("hits", []) or []
        latency_ms = int((time.perf_counter() - t0) * 1000)

        qid = log_query_record(
            user_id=uid, qtext=body.query, top_k=body.top_k,
            filters_json=json.dumps(body.filters) if body.filters else None,
            model=None, latency_ms=latency_ms,
            response_json=json.dumps({"hits": hits}, ensure_ascii=False),
        )
        log_query_hits_records(qid, hits)

        return {"query_id": qid, "latency_ms": latency_ms, "hits": hits}
    except Exception as e:
        log.exception("Search failed")
        raise HTTPException(status_code=400, detail={
            "message": "Search failed",
            "hint": "Check OPENAI_API_KEY and that the index contains documents.",
            "error": str(e),
            "traceback": traceback.format_exc().splitlines()[-3:],
        })


# =========================
# Web search (GET; ordered fallback across engines)
# =========================

@app.get("/api/v1/web/search")
async def web_search(
        engine: str,  # "exa", "serper", or "exa|serper"
        q: str | None = None,
        query: str | None = None,
        data: bool = False,
        top_n: int = Query(3, ge=1, le=10),
        user_id: str | None = None,
):
    """
    Examples:
      /api/v1/web/search?engine=exa&q=llm+observability
      /api/v1/web/search?engine=exa|serper&q=ray+serve&data=true&top_n=2&user_id=demo
      /api/v1/web/search?engine=serper,exa&query=python%20asyncio&data=true
    """
    import time as _time
    t0 = _time.perf_counter()
    uid = (user_id or "anonymous").strip()
    ensure_user(uid, None)

    qtxt = _pick_query(q, query)
    engines = _parse_engines(engine)

    attempt_errors: list[dict] = []
    results: list[dict] = []
    scrape_logs: list[dict] = []
    scraped = 0
    engine_used: str | None = None

    for eng in engines:
        try:
            if eng == "exa":
                pack = await _exa_search(qtxt, top_n, include_text=data)
                results = pack["results"]
                engine_used = "exa"
                scraped = int(bool(data))  # Exa inlines text when data=true
                scrape_logs = []
            elif eng == "serper":
                pack = await _serper_search(qtxt, top_n)
                results = pack["results"]
                engine_used = "serper"
                if data:
                    results, scrape_logs = await _maybe_scrape(results, top_n=top_n)
                    scraped = min(top_n, len(scrape_logs))
                else:
                    scraped = 0
                    scrape_logs = []
            break  # success → stop trying others
        except Exception as e:
            attempt_errors.append({"engine": eng, "error": str(e)})

    latency_ms = int((_time.perf_counter() - t0) * 1000)

    if engine_used is None:
        event_id = log_api_event(
            user_id=uid, api="/api/v1/web/search",
            request_obj={"engines": engines, "q": qtxt, "data": data, "top_n": top_n, "user_id": uid},
            response_obj={"errors": attempt_errors},
            status="error", latency_ms=latency_ms, notes="all engines failed"
        )
        raise HTTPException(
            status_code=502,
            detail={"message": "All engines failed", "attempts": attempt_errors, "event_id": event_id},
        )

    response_summary = {
        "engine_used": engine_used,
        "attempted_engines": engines,
        "results_count": len(results),
        "scraped": scraped,
        "first_error": attempt_errors[0] if attempt_errors else None,
    }
    event_id = log_api_event(
        user_id=uid, api="/api/v1/web/search",
        request_obj={"engines": engines, "q": qtxt, "data": data, "top_n": top_n, "user_id": uid},
        response_obj=response_summary, status="ok", latency_ms=latency_ms,
        notes="fallback_ok" if attempt_errors else None,
    )
    log_web_results(event_id, results)
    if data and scrape_logs:
        log_web_fetches(event_id, scrape_logs)

    return {
        "engine": engine_used,
        "attempted_engines": engines,
        "q": qtxt,
        "data": data,
        "top_n": top_n,
        "results": results,
        "scraped": scraped,
        "event_id": event_id,
        "attempt_errors": attempt_errors,
    }

# http://localhost:8000/api/v1/web/search?engine=exa|serper&data=true
