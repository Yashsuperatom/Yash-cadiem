from __future__ import annotations
import hashlib, mimetypes, pathlib

TEXT_EXTS = {'.txt', '.md', '.py', '.json', '.yaml', '.yml', '.csv', '.toml', '.ini', '.log'}
ALWAYS_INCLUDE = {'.pdf'}

def is_text_like(path: str) -> bool:
    ext = pathlib.Path(path).suffix.lower()
    if ext in TEXT_EXTS or ext in ALWAYS_INCLUDE:
        return True
    mime, _ = mimetypes.guess_type(path)
    return (mime or '').startswith('text/')

def sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256(); h.update(data); return h.hexdigest()
