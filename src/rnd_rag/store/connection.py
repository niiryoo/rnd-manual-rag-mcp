"""DB 커넥션. sqlite-vec 확장 로딩을 이 한 곳에서만 한다."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

import sqlite_vec

from rnd_rag.paths import DB_DIR

DB_PATH = DB_DIR / "manual.db"


def open_db(path: Path | None = None, readonly: bool = False,
            shared_threads: bool = False) -> sqlite3.Connection:
    target = path or DB_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread: MCP 도구가 AnyIO 워커 스레드에서 실행된다
    if readonly:
        con = sqlite3.connect(f"file:{target}?mode=ro", uri=True, check_same_thread=not shared_threads)
    else:
        con = sqlite3.connect(target, check_same_thread=not shared_threads)
    con.row_factory = sqlite3.Row
    con.enable_load_extension(True)
    sqlite_vec.load(con)
    con.enable_load_extension(False)
    # SQLite 는 커넥션마다 꺼져 있어 명시적으로 켜야 한다
    con.execute("PRAGMA foreign_keys = ON")
    return con


@contextmanager
def connect(path: Path | None = None, readonly: bool = False):
    con = open_db(path, readonly)
    try:
        yield con
    finally:
        con.close()
