from __future__ import annotations

from pathlib import Path
from typing import Optional, List, Dict, Any
import json

from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker

from agent_app.config import SETTINGS

# -------- Paths & engine --------
DATA_DIR = Path(getattr(SETTINGS, "data_dir", "./data")).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "agent.db"  # <<—— this is the only sqlite file the app uses

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
    future=True,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _):
    try:
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL;")
        cur.execute("PRAGMA synchronous=NORMAL;")
        cur.execute("PRAGMA foreign_keys=ON;")
        cur.close()
    except Exception:
        pass


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


# -------- Schema bootstrap --------
def init_db() -> None:
    """Create tables and indexes if they don't exist in data/agent.db."""
    with engine.begin() as conn:
        # users
        conn.execute(text("""
                          CREATE TABLE IF NOT EXISTS users
                          (
                              user_id   TEXT PRIMARY KEY,
                              info_json TEXT
                          );
                          """))

        # files
        conn.execute(text("""
                          CREATE TABLE IF NOT EXISTS files
                          (
                              id              INTEGER PRIMARY KEY AUTOINCREMENT,
                              path            TEXT UNIQUE,
                              bytes           INTEGER,
                              mtime_ns        INTEGER,
                              sha256          TEXT,
                              mime            TEXT,
                              last_indexed_at TEXT
                          );
                          """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_files_path ON files(path);"))

        # queries
        conn.execute(text("""
                          CREATE TABLE IF NOT EXISTS queries
                          (
                              id            INTEGER PRIMARY KEY AUTOINCREMENT,
                              user_id       TEXT,
                              qtext         TEXT,
                              top_k         INTEGER,
                              filters_json  TEXT,
                              model         TEXT,
                              latency_ms    INTEGER,
                              response_json TEXT,
                              created_at    TEXT DEFAULT (datetime('now'))
                          );
                          """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_queries_user_time ON queries(user_id, created_at);"))

        # query_hits
        conn.execute(text("""
                          CREATE TABLE IF NOT EXISTS query_hits
                          (
                              query_id  INTEGER,
                              rank      INTEGER,
                              score     REAL,
                              path      TEXT,
                              chunk_idx INTEGER,
                              sha256    TEXT,
                              snippet   TEXT
                          );
                          """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_query_hits_qid ON query_hits(query_id);"))

        # api_events (user-centric log of every endpoint)
        conn.execute(text("""
                          CREATE TABLE IF NOT EXISTS api_events
                          (
                              id            INTEGER PRIMARY KEY AUTOINCREMENT,
                              user_id       TEXT,
                              api           TEXT,
                              request_json  TEXT,
                              response_json TEXT,
                              status        TEXT,
                              latency_ms    INTEGER,
                              notes         TEXT,
                              created_at    TEXT DEFAULT (datetime('now'))
                          );
                          """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_api_events_user_time ON api_events(user_id, created_at);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_api_events_api_time ON api_events(api, created_at);"))

        # web_results (ranked items we returned)
        conn.execute(text("""
                          CREATE TABLE IF NOT EXISTS web_results
                          (
                              id           INTEGER PRIMARY KEY AUTOINCREMENT,
                              api_event_id INTEGER,
                              rank         INTEGER,
                              title        TEXT,
                              url          TEXT,
                              snippet      TEXT,
                              source       TEXT
                          );
                          """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_web_results_event ON web_results(api_event_id);"))

        # web_fetches (per-URL scrape outcomes)
        conn.execute(text("""
                          CREATE TABLE IF NOT EXISTS web_fetches
                          (
                              id           INTEGER PRIMARY KEY AUTOINCREMENT,
                              api_event_id INTEGER,
                              url          TEXT,
                              ok           INTEGER,
                              status_code  INTEGER,
                              text_length  INTEGER,
                              error        TEXT,
                              elapsed_ms   INTEGER
                          );
                          """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_web_fetches_event ON web_fetches(api_event_id);"))


# -------- helpers --------
def ensure_user(user_id: str, info_json: Optional[str]) -> None:
    if not user_id:
        return
    with engine.begin() as conn:
        conn.execute(text("""
                          INSERT INTO users(user_id, info_json)
                          VALUES (:u, :info)
                          ON CONFLICT(user_id) DO UPDATE SET info_json = COALESCE(:info, users.info_json)
                          """), {"u": user_id, "info": info_json})


def log_query_record(
        *, user_id: str, qtext: str, top_k: int,
        filters_json: Optional[str], model: Optional[str],
        latency_ms: int, response_json: str
) -> int:
    with engine.begin() as conn:
        res = conn.execute(text("""
                                INSERT INTO queries(user_id, qtext, top_k, filters_json, model, latency_ms, response_json)
                                VALUES (:user_id, :qtext, :top_k, :filters_json, :model, :latency_ms, :response_json)
                                """), {
                               "user_id": user_id,
                               "qtext": qtext,
                               "top_k": top_k,
                               "filters_json": filters_json,
                               "model": model,
                               "latency_ms": latency_ms,
                               "response_json": response_json,
                           })
        return int(res.lastrowid)


def log_query_hits_records(query_id: int, hits: List[Dict[str, Any]]) -> None:
    if not hits:
        return
    with engine.begin() as conn:
        for rank, h in enumerate(hits, start=1):
            conn.execute(text("""
                              INSERT INTO query_hits(query_id, rank, score, path, chunk_idx, sha256, snippet)
                              VALUES (:qid, :rank, :score, :path, :chunk_idx, :sha256, :snippet)
                              """), {
                             "qid": query_id,
                             "rank": rank,
                             "score": float(h.get("score", 0.0)),
                             "path": h.get("meta", {}).get("path"),
                             "chunk_idx": h.get("meta", {}).get("chunk_idx"),
                             "sha256": h.get("meta", {}).get("sha256"),
                             "snippet": (h.get("text") or "")[:2000],
                         })


def log_api_event(
        *, user_id: str, api: str,
        request_obj: Dict[str, Any] | None,
        response_obj: Dict[str, Any] | None,
        status: str, latency_ms: int,
        notes: str | None = None
) -> int:
    req_json = json.dumps(request_obj or {}, ensure_ascii=False)
    resp_json = json.dumps(response_obj or {}, ensure_ascii=False)
    with engine.begin() as conn:
        res = conn.execute(text("""
                                INSERT INTO api_events(user_id, api, request_json, response_json, status, latency_ms, notes)
                                VALUES (:user_id, :api, :request_json, :response_json, :status, :latency_ms, :notes)
                                """), {
                               "user_id": user_id or "anonymous",
                               "api": api,
                               "request_json": req_json,
                               "response_json": resp_json,
                               "status": status,
                               "latency_ms": latency_ms,
                               "notes": notes,
                           })
        return int(res.lastrowid)


def log_web_results(api_event_id: int, results: List[Dict[str, Any]]) -> None:
    if not results:
        return
    with engine.begin() as conn:
        for rank, r in enumerate(results, start=1):
            conn.execute(text("""
                              INSERT INTO web_results(api_event_id, rank, title, url, snippet, source)
                              VALUES (:api_event_id, :rank, :title, :url, :snippet, :source)
                              """), {
                             "api_event_id": api_event_id,
                             "rank": rank,
                             "title": r.get("title"),
                             "url": r.get("url"),
                             "snippet": r.get("snippet"),
                             "source": r.get("source"),
                         })


def log_web_fetches(api_event_id: int, fetches: List[Dict[str, Any]]) -> None:
    """Persist per-URL scrape outcomes (when data=true)."""
    if not fetches:
        return
    with engine.begin() as conn:
        for f in fetches:
            conn.execute(text("""
                              INSERT INTO web_fetches(api_event_id, url, ok, status_code, text_length, error, elapsed_ms)
                              VALUES (:api_event_id, :url, :ok, :status_code, :text_length, :error, :elapsed_ms)
                              """), {
                             "api_event_id": api_event_id,
                             "url": f.get("url"),
                             "ok": 1 if f.get("ok") else 0,
                             "status_code": f.get("status"),
                             "text_length": f.get("text_length"),
                             "error": f.get("error"),
                             "elapsed_ms": f.get("elapsed_ms"),
                         })
