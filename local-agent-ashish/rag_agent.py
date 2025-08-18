import os
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import chromadb
from chromadb.config import Settings
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_community.vectorstores import Chroma
from langchain.schema import Document
from langchain.chains import RetrievalQA
from langgraph.graph import StateGraph, END
from typing_extensions import TypedDict
from document_parser import DocumentParser
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RAGState(TypedDict):
    query: str
    documents: List[Document]
    results: List[Dict[str, Any]]
    answer: Optional[str]


class RAGAgent:
    def __init__(self):
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.index_directory = os.getenv("INDEX_DIRECTORY", "./documents")
        self.persist_directory = os.getenv("CHROMA_PERSIST_DIRECTORY", "./chroma_db")
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "models/embedding-001")
        self.llm_model = os.getenv("LLM_MODEL", "gemini-1.5-flash")
        
        # Initialize embeddings with timeout
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model=self.embedding_model,
            google_api_key=self.google_api_key,
            request_timeout=30
        )
        
        # Initialize LLM with timeout
        self.llm = ChatGoogleGenerativeAI(
            model=self.llm_model,
            google_api_key=self.google_api_key,
            temperature=0.3,
            request_timeout=30
        )
        
        # Initialize document parser
        self.parser = DocumentParser(chunk_size=1000, chunk_overlap=200)
        
        # Initialize or load vector store
        self.vector_store = self._initialize_vector_store()
        
        # Build the RAG graph
        self.graph = self._build_graph()
    
    def _initialize_vector_store(self) -> Chroma:
        """Initialize or load existing vector store"""
        try:
            # Create persist directory if it doesn't exist
            os.makedirs(self.persist_directory, exist_ok=True)
            
            # Initialize Chroma with persistence
            vector_store = Chroma(
                embedding_function=self.embeddings,
                persist_directory=self.persist_directory,
                collection_name="rag_documents"
            )
            
            logger.info(f"Vector store initialized at {self.persist_directory}")
            return vector_store
            
        except Exception as e:
            logger.error(f"Error initializing vector store: {str(e)}")
            raise
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow for RAG"""
        workflow = StateGraph(RAGState)
        
        # Define nodes
        workflow.add_node("retrieve", self._retrieve_documents)
        workflow.add_node("generate", self._generate_answer)
        
        # Define edges
        workflow.set_entry_point("retrieve")
        workflow.add_edge("retrieve", "generate")
        workflow.add_edge("generate", END)
        
        return workflow.compile()
    
    def _retrieve_documents(self, state: RAGState) -> RAGState:
        """Retrieve relevant documents from vector store"""
        query = state["query"]
        limit = state.get("limit", 10)
        
        try:
            # Perform similarity search
            docs = self.vector_store.similarity_search_with_score(
                query=query,
                k=limit
            )
            
            # Format results
            results = []
            for doc, score in docs:
                results.append({
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "similarity_score": float(1 - score)  # Convert distance to similarity
                })
            
            state["documents"] = [doc for doc, _ in docs]
            state["results"] = results
            
            logger.info(f"Retrieved {len(results)} documents for query: {query}")
            
        except Exception as e:
            logger.error(f"Error retrieving documents: {str(e)}")
            state["documents"] = []
            state["results"] = []
        
        return state
    
    def _generate_answer(self, state: RAGState) -> RAGState:
        """Generate answer using retrieved documents"""
        if not state["documents"]:
            state["answer"] = "No relevant documents found for your query."
            return state
        
        try:
            # Create context from documents
            context = "\n\n".join([doc.page_content for doc in state["documents"][:5]])
            
            # Generate answer
            prompt = f"""Based on the following context, answer the question. If the answer cannot be found in the context, say so.

Context:
{context}

Question: {state["query"]}

Answer:"""
            
            response = self.llm.invoke(prompt)
            state["answer"] = response.content
            
        except Exception as e:
            logger.error(f"Error generating answer: {str(e)}")
            state["answer"] = f"Error generating answer: {str(e)}"
        
        return state
    
    def index_documents(self, directory_path: Optional[str] = None) -> Dict[str, Any]:
        """Index all documents in the specified directory"""
        if directory_path is None:
            directory_path = self.index_directory
        
        try:
            # Create directory if it doesn't exist
            os.makedirs(directory_path, exist_ok=True)
            
            # Parse all documents
            logger.info(f"Starting document indexing from {directory_path}")
            documents = self.parser.parse_directory(directory_path)
            
            if not documents:
                return {
                    "status": "warning",
                    "message": "No documents found to index",
                    "documents_indexed": 0
                }
            
            # Clear existing vector store
            self.vector_store.delete_collection()
            self.vector_store = self._initialize_vector_store()
            
            # Add documents to vector store
            self.vector_store.add_documents(documents)
            
            # Persist the vector store
            self.vector_store.persist()
            
            logger.info(f"Successfully indexed {len(documents)} document chunks")
            
            return {
                "status": "success",
                "message": f"Successfully indexed {len(documents)} document chunks",
                "documents_indexed": len(documents),
                "directory": directory_path
            }
            
        except Exception as e:
            logger.error(f"Error indexing documents: {str(e)}")
            return {
                "status": "error",
                "message": f"Error indexing documents: {str(e)}",
                "documents_indexed": 0
            }
    
    def query(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Query the RAG system"""
        try:
            # Initialize state
            initial_state = RAGState(
                query=query,
                documents=[],
                results=[],
                answer=None,
                limit=limit
            )
            
            # Run the graph
            final_state = self.graph.invoke(initial_state)
            
            return {
                "status": "success",
                "query": query,
                "results": final_state["results"],
                "answer": final_state["answer"],
                "total_results": len(final_state["results"])
            }
            
        except Exception as e:
            logger.error(f"Error processing query: {str(e)}")
            return {
                "status": "error",
                "query": query,
                "message": f"Error processing query: {str(e)}",
                "results": [],
                "answer": None
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector store"""
        try:
            collection = self.vector_store._collection
            count = collection.count()
            
            return {
                "total_documents": count,
                "persist_directory": self.persist_directory,
                "embedding_model": self.embedding_model,
                "llm_model": self.llm_model
            }
        except Exception as e:
            logger.error(f"Error getting stats: {str(e)}")
            return {
                "error": str(e)
            }