"""검색 결과를 Claude 가 읽을 텍스트로 만든다."""

from __future__ import annotations

from rnd_rag.search import SearchResult
from rnd_rag.store import Chunk

SNIPPET_CHARS = 1200  # 섹션 하나가 3만 자를 넘기도 해 그대로 주면 토큰이 샌다
SECTION_CHARS = 6000  # get_section 한 번에 돌려줄 상한. 넘으면 이어보기로 나눈다
DEGRADED_NOTE = (
    "[주의] 의미 검색을 쓸 수 없어 키워드 검색 결과만이다. "
    "질문의 표현이 매뉴얼 용어와 다르면 관련 내용이 빠졌을 수 있으니, "
    "답이 불충분하면 매뉴얼에 쓰일 법한 용어로 다시 검색할 것."
)

DOC_TITLES = {
    "main": "본권 국가연구개발혁신법 매뉴얼",
    "v1": "별권1 학생인건비통합관리",
    "v2": "별권2 기술료제도",
    "v3": "별권3 제재처분 가이드라인",
    "v4": "별권4 연구시설·장비비 통합관리제",
}


def doc_title(doc_id: str) -> str:
    return DOC_TITLES.get(doc_id, doc_id)


def _truncate(text: str, limit: int) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return text[:limit].rstrip(), True


def format_result(result: SearchResult, index: int, limit: int = SNIPPET_CHARS) -> str:
    body, cut = _truncate(result.text, limit)
    lines = [
        f"## {index}. {' > '.join(result.section.level_path)}",
        f"출처: {doc_title(result.section.doc_id)} {result.citation}",
        f"section_id: {result.section.section_id}",
        "",
        body,
    ]
    if cut:
        lines.append(f"\n(본문 일부만 표시. 전문은 get_section(\"{result.section.section_id}\"))")
    return "\n".join(lines)


def format_results(results: list[SearchResult], limit: int = SNIPPET_CHARS,
                   keyword_only: bool = False) -> str:
    if not results:
        return "검색 결과가 없다. 다른 표현으로 다시 검색할 것."
    body = "\n\n---\n\n".join(format_result(r, i, limit) for i, r in enumerate(results, 1))
    return f"{DEGRADED_NOTE}\n\n{body}" if keyword_only else body


def format_section(level_path: tuple[str, ...], doc_id: str, citation: str,
                   chunks: list[Chunk], offset: int = 0,
                   limit: int = SECTION_CHARS) -> str:
    taken: list[str] = []
    used = 0
    index = 0
    for chunk in chunks:
        if index < offset:
            index += 1
            continue
        # 첫 청크는 한도를 넘어도 담는다. 안 그러면 큰 청크를 영영 못 돌려준다
        if taken and used + len(chunk.text) > limit:
            break
        taken.append(chunk.text)
        used += len(chunk.text)
        index += 1

    head = [f"## {' > '.join(level_path)}", f"출처: {doc_title(doc_id)} {citation}"]
    if offset or index < len(chunks):
        head.append(f"청크 {offset + 1}~{index} / 전체 {len(chunks)}")
    body = "\n".join(head + [""] + taken)
    if index < len(chunks):
        body += f"\n\n(이어서 보려면 offset={index})"
    return body
