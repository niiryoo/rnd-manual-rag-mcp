"""읽기 접근. 검색 계층이 SQL 을 직접 쓰지 않도록 여기서만 질의한다."""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass

import numpy as np

from rnd_rag.store.tokenizer import to_match_expr

# 테이블명을 문자열로 조립하지 않도록 질의를 통째로 상수로 둔다
COUNT_SQL = {
    "sections": "SELECT count(*) FROM sections",
    "chunks": "SELECT count(*) FROM chunks",
    "refs": "SELECT count(*) FROM refs",
    "chunks_fts": "SELECT count(*) FROM chunks_fts",
    "chunk_vec": "SELECT count(*) FROM chunk_vec",
}


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    section_id: str
    doc_id: str
    content_type: str
    text: str
    page_printed_start: int | None
    page_printed_end: int | None
    caption: str


@dataclass(frozen=True)
class Section:
    section_id: str
    doc_id: str
    title: str
    level_path: tuple[str, ...]
    page_printed_start: int | None
    page_printed_end: int | None

    @property
    def citation(self) -> str:
        start, end = self.page_printed_start, self.page_printed_end
        if start is None:
            return "머리말"
        return f"p{start}" if start == end else f"p{start}~{end}"


@dataclass(frozen=True)
class Hit:
    chunk_id: str
    score: float


def _chunk(row: sqlite3.Row) -> Chunk:
    return Chunk(
        chunk_id=row["chunk_id"],
        section_id=row["section_id"],
        doc_id=row["doc_id"],
        content_type=row["content_type"],
        text=row["text"],
        page_printed_start=row["page_printed_start"],
        page_printed_end=row["page_printed_end"],
        caption=row["caption"],
    )


def _section(row: sqlite3.Row) -> Section:
    return Section(
        section_id=row["section_id"],
        doc_id=row["doc_id"],
        title=row["title"],
        level_path=tuple(json.loads(row["level_path"])),
        page_printed_start=row["page_printed_start"],
        page_printed_end=row["page_printed_end"],
    )


class Repository:
    """커넥션 하나를 여러 스레드가 동시에 쓰면 커서 상태가 엉킨다."""

    def __init__(self, con: sqlite3.Connection):
        self.con = con
        self._lock = threading.Lock()

    def _query(self, sql: str, params=()) -> list[sqlite3.Row]:
        with self._lock:
            return self.con.execute(sql, params).fetchall()

    def search_keyword(self, query: str, limit: int, doc_id: str | None = None,
                       content_type: str | None = None) -> list[Hit]:
        expr = to_match_expr(query)
        if not expr:
            return []
        # 필터를 limit 뒤에 걸면 대상이 소수일 때 결과가 빈다
        where = ["chunks_fts MATCH ?"]
        params: list = [expr]
        if doc_id:
            where.append("c.doc_id = ?")
            params.append(doc_id)
        if content_type:
            where.append("c.content_type = ?")
            params.append(content_type)
        params.append(limit)
        rows = self._query(
            "SELECT f.chunk_id, bm25(chunks_fts) AS score "
            "FROM chunks_fts f JOIN chunks c ON c.chunk_id = f.chunk_id "
            f"WHERE {' AND '.join(where)} ORDER BY score LIMIT ?",
            params,
        )
        return [Hit(r["chunk_id"], r["score"]) for r in rows]

    def search_vector(self, vector: np.ndarray, limit: int, doc_id: str | None = None,
                      content_type: str | None = None) -> list[Hit]:
        where = ["embedding MATCH ?", "k = ?"]
        params: list = [vector.astype(np.float32).tobytes(), limit]
        if doc_id:
            where.append("doc_id = ?")
            params.append(doc_id)
        if content_type:
            where.append("content_type = ?")
            params.append(content_type)
        rows = self._query(
            f"SELECT chunk_id, distance FROM chunk_vec WHERE {' AND '.join(where)} "
            "ORDER BY distance",
            params,
        )
        return [Hit(r["chunk_id"], r["distance"]) for r in rows]

    def chunks(self, chunk_ids: list[str]) -> list[Chunk]:
        if not chunk_ids:
            return []
        marks = ",".join("?" * len(chunk_ids))
        rows = self._query(f"SELECT * FROM chunks WHERE chunk_id IN ({marks})", chunk_ids)
        found = {r["chunk_id"]: _chunk(r) for r in rows}
        return [found[cid] for cid in chunk_ids if cid in found]

    def section(self, section_id: str) -> Section | None:
        rows = self._query("SELECT * FROM sections WHERE section_id = ?", (section_id,))
        return _section(rows[0]) if rows else None

    def section_chunks(self, section_id: str) -> list[Chunk]:
        rows = self._query(
            "SELECT * FROM chunks WHERE section_id = ? ORDER BY chunk_id", (section_id,)
        )
        return [_chunk(r) for r in rows]

    def chunks_citing(self, target: str, law: str | None = None) -> list[str]:
        if law:
            sql = "SELECT DISTINCT chunk_id FROM refs WHERE target = ? AND law = ?"
            params = (target, law)
        else:
            sql = "SELECT DISTINCT chunk_id FROM refs WHERE target = ?"
            params = (target,)
        return [r["chunk_id"] for r in self._query(sql, params)]

    def counts(self) -> dict[str, int]:
        return {name: self._query(sql)[0][0] for name, sql in COUNT_SQL.items()}
