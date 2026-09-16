"""청킹 산출물을 DB로 적재한다."""

from __future__ import annotations

import sys

from rnd_rag.store import DB_PATH, Repository, connect
from rnd_rag.store import indexer
from rnd_rag.store.embedder import model_name


def run() -> None:
    print(f"모델 {model_name()}  →  {DB_PATH}")
    with connect() as con:
        stats = indexer.build(con, progress=True)
        counts = Repository(con).counts()
    print(f"\n적재 완료  섹션 {stats['sections']}  청크 {stats['chunks']}  "
          f"참조 {stats['refs']}  차원 {stats['dim']}")
    print("  " + "  ".join(f"{k} {v}" for k, v in counts.items()))
    print(f"  파일 {DB_PATH.stat().st_size / 1024 / 1024:.1f}MB")


def main() -> None:
    try:
        run()
    except Exception as e:
        print(f"실패: {type(e).__name__}: {e}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
