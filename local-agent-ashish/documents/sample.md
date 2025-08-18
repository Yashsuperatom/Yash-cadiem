# RAG System Documentation

## Overview
The RAG AI Agent is a powerful system for indexing and querying documents using advanced AI techniques.

## Architecture
- **Document Parser**: Handles multiple file formats
- **Vector Store**: ChromaDB for efficient similarity search
- **Embeddings**: Google Gemini embeddings for semantic understanding
- **LLM**: Gemini 1.5 Flash for answer generation
- **API**: FastAPI for RESTful endpoints

## Usage

### Indexing Documents
Send a POST request to `/api/v1/rag/index` to index all documents in the configured directory.

### Querying
Send a GET request to `/api/v1/rag/query?query=your+question` to search and get AI-generated answers.

## Benefits
1. Fast and accurate document retrieval
2. Context-aware answer generation
3. Support for multiple file formats
4. Scalable architecture
5. Easy API integration