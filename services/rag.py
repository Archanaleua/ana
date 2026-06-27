"""Chunking + naive retrieval helpers."""
import re
from typing import Iterable


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 150) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    chunks: list[str] = []
    i = 0
    while i < len(text):
        chunks.append(text[i : i + chunk_size])
        i += chunk_size - overlap
    return chunks


def keyword_score(query: str, chunk: str) -> int:
    q = {w for w in re.findall(r"\w+", query.lower()) if len(w) > 2}
    c = re.findall(r"\w+", chunk.lower())
    return sum(1 for w in c if w in q)


def top_k(query: str, chunks: Iterable[str], k: int = 4) -> list[str]:
    scored = sorted(
        ((keyword_score(query, c), c) for c in chunks),
        key=lambda x: x[0],
        reverse=True,
    )
    return [c for s, c in scored[:k]]