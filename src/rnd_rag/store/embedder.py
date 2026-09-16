"""임베딩 생성. 입력이 그대로면 캐시를 쓰고 바뀌면 다시 부른다."""

from __future__ import annotations

import hashlib
import os
import time
from functools import lru_cache

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

from rnd_rag.paths import DB_DIR, ROOT

CACHE_DIR = DB_DIR / "emb_cache"
DEFAULT_MODEL = "text-embedding-3-large"
BATCH = 128
RETRIES = 3

load_dotenv(ROOT / ".env")


_client: OpenAI | None = None


def client() -> OpenAI:
    """커넥션 풀을 유지해야 왕복이 2초에서 300ms대로 떨어진다."""
    global _client
    if _client is None:
        _client = OpenAI()
    return _client


def model_name() -> str:
    return os.getenv("EMBEDDING_MODEL") or DEFAULT_MODEL


def _digest(texts: list[str], model: str) -> str:
    h = hashlib.sha256(model.encode())
    for t in texts:
        h.update(t.encode())
    return h.hexdigest()[:16]


def _call(batch: list[str], model: str):
    for attempt in range(RETRIES):
        try:
            return client().embeddings.create(model=model, input=batch)
        except Exception:
            if attempt == RETRIES - 1:
                raise
            time.sleep(2 * (attempt + 1))


def embed(texts: list[str], model: str | None = None, progress: bool = False) -> np.ndarray:
    model = model or model_name()
    vectors = []
    for i in range(0, len(texts), BATCH):
        response = _call(texts[i : i + BATCH], model)
        vectors += [d.embedding for d in response.data]
        if progress:
            print(f"    임베딩 {min(i + BATCH, len(texts))}/{len(texts)}", end="\r")
    return normalize(np.array(vectors, dtype=np.float32))


@lru_cache(maxsize=512)
def embed_query(query: str, model: str | None = None) -> np.ndarray:
    """같은 질의가 반복되는 벤치마크에서 API 호출을 줄인다."""
    return embed([query], model)[0]


def embed_cached(name: str, texts: list[str], model: str | None = None,
                 progress: bool = False) -> np.ndarray:
    model = model or model_name()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{name}.npz"
    digest = _digest(texts, model)
    if path.exists():
        cached = np.load(path)
        if str(cached["digest"]) == digest:
            return cached["vectors"]
    vectors = embed(texts, model, progress)
    np.savez(path, vectors=vectors, digest=digest)
    return vectors


def normalize(matrix: np.ndarray) -> np.ndarray:
    """L2 정규화하면 코사인 유사도가 내적과 같아진다."""
    return matrix / np.linalg.norm(matrix, axis=-1, keepdims=True)
