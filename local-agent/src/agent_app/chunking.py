from __future__ import annotations
import tiktoken

def _enc():
    try:
        return tiktoken.get_encoding("cl100k_base")
    except Exception:
        return tiktoken.get_encoding("cl100k_base")

def chunk_text(text: str, target_tokens: int = 800, overlap: int = 200) -> list[tuple[int,int,str]]:
    enc = _enc()
    toks = enc.encode(text)
    chunks = []
    i = 0
    while i < len(toks):
        j = min(i + target_tokens, len(toks))
        sub = toks[i:j]
        chunk_text = enc.decode(sub)
        start_char = len(enc.decode(toks[:i]))
        end_char = start_char + len(chunk_text)
        chunks.append((start_char, end_char, chunk_text))
        i = j - overlap if j - overlap > i else j
    return chunks
