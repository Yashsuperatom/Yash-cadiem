from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import uvicorn
from rag_agent import RAGAgent
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize RAG Agent as global variable
rag_agent = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global rag_agent
    logger.info("Starting RAG AI Agent API...")
    
    try:
        # Create documents directory if it doesn't exist
        docs_dir = os.getenv("INDEX_DIRECTORY", "./documents")
        os.makedirs(docs_dir, exist_ok=True)
        logger.info(f"Documents directory: {docs_dir}")
        
        # Initialize RAG Agent
        logger.info("Initializing RAG Agent...")
        rag_agent = RAGAgent()
        logger.info("RAG Agent initialized successfully")
        
        # Get initial stats
        try:
            stats = rag_agent.get_stats()
            logger.info(f"Initial stats: {stats}")
        except Exception as e:
            logger.warning(f"Could not get initial stats: {e}")
        
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        # Set rag_agent to None so endpoints can handle the error
        rag_agent = None
    
    yield
    
    # Shutdown
    logger.info("Shutting down RAG AI Agent API...")

# Initialize FastAPI app with lifespan
app = FastAPI(
    title="RAG AI Agent API",
    description="API for indexing documents and performing RAG queries",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# Pydantic models
class IndexRequest(BaseModel):
    directory: Optional[str] = Field(None, description="Directory path to index")


class IndexResponse(BaseModel):
    status: str
    message: str
    documents_indexed: int
    directory: Optional[str] = None


class QueryResponse(BaseModel):
    status: str
    query: str
    results: List[Dict[str, Any]]
    answer: Optional[str]
    total_results: int


class HealthResponse(BaseModel):
    status: str
    message: str
    stats: Dict[str, Any]


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "RAG AI Agent API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "test": "/api/v1/rag/test",
            "index": "/api/v1/rag/index",
            "query": "/api/v1/rag/query",
            "health": "/api/v1/rag/health",
            "stats": "/api/v1/rag/stats"
        }
    }


@app.get("/api/v1/rag/test")
async def test_endpoint():
    """Simple test endpoint that doesn't require Google API"""
    return {
        "status": "success",
        "message": "API is working",
        "timestamp": "2025-08-15",
        "google_api_configured": bool(os.getenv("GOOGLE_API_KEY"))
    }


@app.post("/api/v1/rag/index", response_model=IndexResponse)
async def index_documents_post(
    request: Optional[IndexRequest] = None
):
    """
    Index all documents in the specified directory.
    If no directory is provided, uses the default directory from environment.
    """
    try:
        directory = request.directory if request and request.directory else None
        
        # Perform indexing
        result = rag_agent.index_documents(directory)
        
        return IndexResponse(
            status=result["status"],
            message=result["message"],
            documents_indexed=result["documents_indexed"],
            directory=result.get("directory")
        )
        
    except Exception as e:
        logger.error(f"Error in index endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/rag/index", response_model=IndexResponse)
async def index_documents_get(
    directory: Optional[str] = Query(None, description="Directory path to index")
):
    """
    Index all documents in the specified directory (GET version for browser testing).
    If no directory is provided, uses the default directory from environment.
    """
    try:
        if rag_agent is None:
            raise HTTPException(status_code=503, detail="RAG Agent not initialized. Check server logs for errors.")
        
        # Perform indexing
        result = rag_agent.index_documents(directory)
        
        return IndexResponse(
            status=result["status"],
            message=result["message"],
            documents_indexed=result["documents_indexed"],
            directory=result.get("directory")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in index endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/rag/query", response_model=QueryResponse)
async def query_documents(
    query: str = Query(..., description="Query string to search for"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of results to return")
):
    """
    Query the indexed documents and return relevant results with an AI-generated answer.
    """
    try:
        if not query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        # Perform query
        result = rag_agent.query(query, limit)
        
        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result.get("message", "Query failed"))
        
        return QueryResponse(
            status=result["status"],
            query=result["query"],
            results=result["results"],
            answer=result["answer"],
            total_results=result["total_results"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in query endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/rag/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint to verify the service is running and get stats.
    """
    try:
        stats = rag_agent.get_stats()
        
        return HealthResponse(
            status="healthy",
            message="RAG AI Agent is running",
            stats=stats
        )
        
    except Exception as e:
        logger.error(f"Error in health check: {str(e)}")
        return HealthResponse(
            status="unhealthy",
            message=f"Health check failed: {str(e)}",
            stats={}
        )


@app.get("/api/v1/rag/stats")
async def get_stats():
    """
    Get statistics about the vector store and indexed documents.
    """
    try:
        stats = rag_agent.get_stats()
        return {
            "status": "success",
            **stats
        }
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))




if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )