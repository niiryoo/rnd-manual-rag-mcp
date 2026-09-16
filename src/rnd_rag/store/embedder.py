"""임베딩 생성. 입력이 그대로면 캐시를 쓰고 바뀌면 다시 부른다."""

from __future__ import annotations

import hashlib
import os
import time

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

from rnd_rag.paths import DB_DIR, ROOT

CACHE_DIR = DB_DIR / "emb_cache"
DEFAULT_MODEL = "text-embedding-3-large"
BATCH = 128
RETRIES = 3

load_dotenv(ROOT / ".env")


def model_name() -> str:
    return os.getenv("EMBEDDING_MODEL") or DEFAULT_MODEL


def _digest(texts: list[str], model: str) -> str:
    h = hashlib.sha256(model.encode())
    for t in texts:
        h.update(t.encode())
    return h.hexdigest()[:16]


def _call(client: OpenAI, batch: list[str], model: str):
    for attempt in range(RETRIES):
        try:
            return client.embeddings.create(model=model, input=batch)
        except Exception:
            if attempt == RETRIES - 1:
                raise
            time.sleep(2 * (attempt + 1))


def embed(texts: list[str], model: str | None = None, progress: bool = False) -> np.ndarray:
    model = model or model_name()
    client = OpenAI()
    vectors = []
    for i in range(0, len(texts), BATCH):
        response = _call(client, texts[i : i + BATCH], model)
        vectors += [d.embedding for d in response.data]
        if progress:
            print(f"    임베딩 {min(i + BATCH, len(texts))}/{len(texts)}", end="\r")
    return normalize(np.array(vectors, dtype=np.float32))


def embed_cached(name: str, texts: list[str], model: str | None = None,
                 progress: bool = False) -> np.ndarray:
    """색인용. 같은 입력이면 API 를 다시 부르지 않는다."""
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
