from __future__ import annotations
import os, json
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _parse_paths(val: str | None) -> list[str]:
    if not val:
        return []
    v = val.strip()
    if v.startswith("["):
        try:
            return [str(p) for p in json.loads(v)]
        except Exception:
            pass
    return [p.strip() for p in v.split(",") if p.strip()]


@dataclass(frozen=True)
class Settings:
    data_dir: str = os.getenv("DATA_DIR", "./data")
    chroma_dir: str = os.getenv("CHROMA_DIR", "./data/chroma")
    checkpoint_dir: str = os.getenv("CHECKPOINT_DIR", "./data/checkpoints")
    sqlite_path: str = os.path.join(os.getenv("DATA_DIR", "./data"), "app.sqlite")
    openai_api_key: str | None = os.getenv("AI_API_KEY")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    default_roots: tuple[str, ...] = tuple(_parse_paths(os.getenv("INDEX_ROOTS")))


SETTINGS = Settings()
