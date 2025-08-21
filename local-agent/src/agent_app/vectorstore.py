from __future__ import annotations
import chromadb
from chromadb.config import Settings as ChromaSettings
from .config import SETTINGS

_COLLECTION = "docs_v1"

def get_client():
    return chromadb.Client(ChromaSettings(is_persistent=True, persist_directory=SETTINGS.chroma_dir))

def get_collection():
    client = get_client()
    try:
        return client.get_collection(_COLLECTION)
    except Exception:
        return client.create_collection(_COLLECTION, metadata={"embedding_model": SETTINGS.embedding_model})
