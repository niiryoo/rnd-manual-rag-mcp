"""국가연구개발혁신법 매뉴얼 검색을 MCP 도구로 노출한다."""

from __future__ import annotations

import logging
import sys

from mcp.server.mcpserver import MCPServer

from rnd_rag.mcp.formatting import doc_title, format_results, format_section
from rnd_rag.search import SearchService
from rnd_rag.store import Repository, open_db

DOC_IDS = "main(본권) · v1(학생인건비) · v2(기술료) · v3(제재처분) · v4(연구시설·장비비)"

# stdout 은 JSON-RPC 전용이다. 로그가 한 줄만 섞여도 연결이 끊긴다
logging.basicConfig(stream=sys.stderr, level=logging.WARNING, force=True)

mcp = MCPServer(
    name="rnd-manual",
    instructions=(
        "국가연구개발혁신법 매뉴얼 5종(2026년, 과학기술정보통신부·KISTEP)을 검색한다. "
        "정부과제 규정을 묻는 질문에는 추측하지 말고 이 도구로 원문을 확인한 뒤 "
        "출처 쪽번호와 함께 답한다. 개인 포트폴리오 프로젝트이며 공식 정부 서비스가 아니다."
    ),
)

_con = open_db(readonly=True, shared_threads=True)
_repo = Repository(_con)
_service = SearchService(_repo)


@mcp.tool(
    description=(
        "국가연구개발사업 규정을 매뉴얼에서 검색한다. 기술료율, 인건비 계상기준, "
        "학생인건비 이관·잔액 처리, 연구시설·장비비 적립, 제재처분과 참여제한 기간, "
        "간접비, 정산 같은 질문에 쓴다. 관련 조문과 표를 출처 쪽번호와 함께 돌려준다. "
        f"doc_id 로 특정 매뉴얼만 좁힐 수 있다: {DOC_IDS}"
    )
)
def search_manual(query: str, limit: int = 3, doc_id: str | None = None) -> str:
    return format_results(_service.search(query, limit=limit, doc_id=doc_id))


@mcp.tool(
    description=(
        "섹션 전문을 가져온다. search_manual 결과가 잘려 있고 더 읽어야 할 때 "
        "그 결과에 표시된 section_id 를 넣어 호출한다. 긴 섹션은 나뉘어 오며 "
        "끝에 표시된 offset 으로 이어서 볼 수 있다."
    )
)
def get_section(section_id: str, offset: int = 0) -> str:
    section = _repo.section(section_id)
    if section is None:
        return f"'{section_id}' 섹션이 없다. search_manual 결과의 section_id 를 쓸 것."
    chunks = _repo.section_chunks(section_id)
    return format_section(section.level_path, section.doc_id, section.citation, chunks, offset)


@mcp.tool(
    description=(
        "서식(양식)이 매뉴얼 어느 쪽에 있는지 찾는다. 연구개발계획서, 협약서, "
        "연차·단계·최종보고서, 정산 이의신청서 같은 서식명으로 검색한다. "
        "서식 본문은 스캔 이미지라 색인하지 않았고 수록 위치만 돌려준다."
    )
)
def find_form(name: str) -> str:
    hits = _repo.search_keyword(name, limit=5, content_type="form_index")
    chunks = _repo.chunks([h.chunk_id for h in hits])
    if not chunks:
        return f"'{name}' 서식을 찾지 못했다."
    return "\n\n".join(f"{c.text}\n(출처: {doc_title(c.doc_id)})" for c in chunks)


@mcp.tool(
    description=(
        "조항 번호로 그 조항을 인용한 대목을 찾는다. target 은 '제32조제1항', "
        "'별표6', '별지10' 형태로 공백 없이 넣는다. law 를 주면 좁혀진다 "
        "(예: 국가연구개발혁신법, 국가연구개발혁신법 시행령)."
    )
)
def find_citation(target: str, law: str | None = None, limit: int = 5) -> str:
    chunk_ids = _repo.chunks_citing(target.replace(" ", ""), law)
    chunks = _repo.chunks(chunk_ids[:limit])
    if not chunks:
        return f"'{target}' 을 인용한 대목을 찾지 못했다."
    parts = []
    for c in chunks:
        section = _repo.section(c.section_id)
        where = f"{doc_title(c.doc_id)} {section.citation}" if section else doc_title(c.doc_id)
        parts.append(f"출처: {where}\nsection_id: {c.section_id}\n\n{c.text}")
    return f"{target} 인용 {len(chunk_ids)}건 중 {len(chunks)}건\n\n" + "\n\n---\n\n".join(parts)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
