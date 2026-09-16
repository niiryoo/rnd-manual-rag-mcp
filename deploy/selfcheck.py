"""설치 상태 점검. 임베딩이 막힌 것은 고장이 아니므로 구분해서 알린다."""

from __future__ import annotations

import sys


def line(label: str, ok: bool, detail: str = "") -> bool:
    mark = "OK  " if ok else "실패"
    print(f"  {label:<22} {mark}  {detail}")
    return ok


def main() -> int:
    print()
    problems = 0

    try:
        from rnd_rag.store import DB_PATH
    except Exception as e:
        line("패키지 불러오기", False, f"{type(e).__name__}: {e}")
        return 1
    line("패키지 불러오기", True, sys.version.split()[0])

    if not DB_PATH.exists():
        line("검색 데이터", False, f"{DB_PATH} 없음")
        print("\n  db 폴더의 manual.db 가 빠졌습니다. 압축을 다시 풀어주세요.")
        return 1
    size = DB_PATH.stat().st_size / 1024 / 1024
    line("검색 데이터", True, f"{size:.1f}MB")

    from rnd_rag.search import SearchService
    from rnd_rag.store import Repository, open_db

    con = open_db(readonly=True)
    service = SearchService(Repository(con))
    counts = Repository(con).counts()
    line("색인", True, f"섹션 {counts['sections']} · 청크 {counts['chunks']}")

    response = service.search("중소기업 기술료율", limit=1)
    if not response.results:
        problems += 1
        line("검색 동작", False, "결과 없음")
    else:
        top = response.results[0]
        line("검색 동작", True, f"'기술료율' → {top.section.doc_id} {top.citation}")

    if response.keyword_only:
        line("의미 검색", True, "사용 불가 — 키워드 검색으로 동작합니다")
        print("      (회사망 차단이거나 키가 없는 경우입니다. 검색은 계속 됩니다)")
    else:
        line("의미 검색", True, "정상")

    con.close()

    print()
    if problems:
        print(f"  문제 {problems}건. 위 '실패' 항목을 확인해주세요.")
        return 1
    print("  이상 없습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
