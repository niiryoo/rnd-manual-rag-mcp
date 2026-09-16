"""스키마 정의. 벡터 차원은 임베딩 모델이 정하므로 여기서 받아 쓴다."""

from __future__ import annotations

import sqlite3

TABLES = """
CREATE TABLE IF NOT EXISTS sections (
    section_id          TEXT PRIMARY KEY,
    doc_id              TEXT NOT NULL,
    title               TEXT NOT NULL,
    level_path          TEXT NOT NULL,
    page_pdf_start      INTEGER,
    page_pdf_end        INTEGER,
    page_printed_start  INTEGER,
    page_printed_end    INTEGER
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id            TEXT PRIMARY KEY,
    section_id          TEXT NOT NULL REFERENCES sections(section_id),
    doc_id              TEXT NOT NULL,
    content_type        TEXT NOT NULL,
    text                TEXT NOT NULL,
    text_for_embedding  TEXT NOT NULL,
    page_pdf_start      INTEGER,
    page_pdf_end        INTEGER,
    page_printed_start  INTEGER,
    page_printed_end    INTEGER,
    char_count          INTEGER NOT NULL,
    caption             TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS refs (
    chunk_id  TEXT NOT NULL REFERENCES chunks(chunk_id),
    doc_id    TEXT NOT NULL,
    law       TEXT NOT NULL,
    target    TEXT NOT NULL,
    raw       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chunks_section ON chunks(section_id);
CREATE INDEX IF NOT EXISTS idx_chunks_doc     ON chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_refs_target    ON refs(law, target);
CREATE INDEX IF NOT EXISTS idx_refs_chunk     ON refs(chunk_id);
"""

# body 는 2-gram 전처리를 거친 텍스트. 원문은 chunks 에 있다
FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    chunk_id UNINDEXED,
    body,
    tokenize='unicode61'
);
"""

# 메타데이터 컬럼이 없으면 k 가 필터보다 먼저 적용돼 결과가 비어버린다
VEC = """
CREATE VIRTUAL TABLE IF NOT EXISTS chunk_vec USING vec0(
    chunk_id     TEXT PRIMARY KEY,
    embedding    FLOAT[{dim}],
    doc_id       TEXT,
    content_type TEXT
);
"""

DROP = [
    "DROP TABLE IF EXISTS chunk_vec",
    "DROP TABLE IF EXISTS chunks_fts",
    "DROP TABLE IF EXISTS refs",
    "DROP TABLE IF EXISTS chunks",
    "DROP TABLE IF EXISTS sections",
]


def create(con: sqlite3.Connection, dim: int) -> None:
    con.executescript(TABLES)
    con.executescript(FTS)
    con.executescript(VEC.format(dim=dim))
    con.commit()


def drop(con: sqlite3.Connection) -> None:
    con.execute("PRAGMA foreign_keys = OFF")
    for stmt in DROP:
        con.execute(stmt)
    con.commit()
    con.execute("PRAGMA foreign_keys = ON")
