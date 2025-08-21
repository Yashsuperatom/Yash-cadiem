from __future__ import annotations
from typing import List
import hashlib
from openai import AsyncOpenAI
from openai import AuthenticationError
from .config import SETTINGS
import os

class Embedder:
    def __init__(self, model: str | None = None, api_key: str | None = None):
        from agent_app.config import SETTINGS
        self.model = model or SETTINGS.embedding_model
        api_key = os.getenv("AI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set; put it in .env or export it.")
        self.client = AsyncOpenAI(api_key=api_key)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        try:
            resp = await self.client.embeddings.create(model=self.model, input=texts)
            return [d.embedding for d in resp.data]
        except AuthenticationError as e:
            # Raise something your FastAPI handler will show as a 401
            raise RuntimeError("OPENAI_API_KEY is missing or invalid") from e

class LocalDebugEmbedder:
    def __init__(self, dim: int = 256):
        self.dim = dim
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        out = []
        for t in texts:
            h = hashlib.sha256(t.encode("utf-8")).digest()
            rep = (self.dim // len(h)) + 1
            vec = (list(h) * rep)[:self.dim]
            out.append([v/255.0 for v in vec])
        return out
