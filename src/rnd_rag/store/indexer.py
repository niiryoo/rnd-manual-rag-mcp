"""JSONL 산출물을 DB에 적재한다. 빌드 타임에만 쓴다."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import numpy as np

from rnd_rag.paths import PROCESSED_DIR
from rnd_rag.store import embedder, schema
from rnd_rag.store.tokenizer import to_index_text

INSERT_CHUNK_SIZE = 500


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _load_sections(con: sqlite3.Connection, sections: list[dict]) -> None:
    con.executemany(
        "INSERT INTO sections VALUES (:section_id, :doc_id, :title, :level_path, "
        ":page_pdf_start, :page_pdf_end, :page_printed_start, :page_printed_end)",
        [{**s, "level_path": json.dumps(s["level_path"], ensure_ascii=False)} for s in sections],
    )


def _load_chunks(con: sqlite3.Connection, chunks: list[dict]) -> None:
    con.executemany(
        "INSERT INTO chunks VALUES (:chunk_id, :section_id, :doc_id, :content_type, "
        ":text, :text_for_embedding, :page_pdf_start, :page_pdf_end, "
        ":page_printed_start, :page_printed_end, :char_count, :caption)",
        chunks,
    )


def _load_refs(con: sqlite3.Connection, refs: list[dict]) -> None:
    con.executemany(
        "INSERT INTO refs VALUES (:chunk_id, :doc_id, :law, :target, :raw)", refs
    )


def _load_fts(con: sqlite3.Connection, chunks: list[dict]) -> None:
    con.executemany(
        "INSERT INTO chunks_fts(chunk_id, body) VALUES (?, ?)",
        [(c["chunk_id"], to_index_text(c["text"])) for c in chunks],
    )


def _load_vectors(con: sqlite3.Connection, chunks: list[dict], vectors: np.ndarray) -> None:
    rows = [
        (c["chunk_id"], v.astype(np.float32).tobytes(), c["doc_id"], c["content_type"])
        for c, v in zip(chunks, vectors)
    ]
    for i in range(0, len(rows), INSERT_CHUNK_SIZE):
        con.executemany(
            "INSERT INTO chunk_vec(chunk_id, embedding, doc_id, content_type) VALUES (?, ?, ?, ?)",
            rows[i : i + INSERT_CHUNK_SIZE],
        )


def build(con: sqlite3.Connection, source: Path | None = None, progress: bool = True) -> dict[str, int]:
    source = source or PROCESSED_DIR
    sections = read_jsonl(source / "sections.jsonl")
    chunks = read_jsonl(source / "chunks.jsonl")
    refs = read_jsonl(source / "refs.jsonl")

    vectors = embedder.embed_cached(
        "chunks", [c["text_for_embedding"] for c in chunks], progress=progress
    )
    if len(vectors) != len(chunks):
        raise ValueError(f"임베딩 {len(vectors)}개와 청크 {len(chunks)}개가 어긋난다")

    schema.drop(con)
    schema.create(con, dim=vectors.shape[1])
    _load_sections(con, sections)
    _load_chunks(con, chunks)
    _load_refs(con, refs)
    _load_fts(con, chunks)
    _load_vectors(con, chunks, vectors)
    con.commit()

    return {
        "sections": len(sections),
        "chunks": len(chunks),
        "refs": len(refs),
        "dim": vectors.shape[1],
    }
