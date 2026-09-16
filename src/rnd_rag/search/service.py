"""하이브리드 검색. child 로 찾고 parent 섹션으로 돌려준다."""

from __future__ import annotations

from dataclasses import dataclass

from rnd_rag.search.fusion import KEYWORD_WEIGHT, reciprocal_rank_fusion
from rnd_rag.store import Chunk, Repository, Section
from rnd_rag.store.embedder import embed_query

CANDIDATE_POOL = 100  # 융합 전에 각 경로에서 가져오는 후보 수
DEFAULT_LIMIT = 5


@dataclass(frozen=True)
class SearchResult:
    section: Section
    chunks: tuple[Chunk, ...]
    score: float
    matched_chunk_id: str

    @property
    def citation(self) -> str:
        pages = self.section.page_printed_start, self.section.page_printed_end
        if pages[0] is None:
            return f"{self.section.doc_id} 머리말"
        span = f"p{pages[0]}" if pages[0] == pages[1] else f"p{pages[0]}~{pages[1]}"
        return f"{self.section.doc_id} {span}"

    @property
    def text(self) -> str:
        return "\n\n".join(c.text for c in self.chunks)


class SearchService:
    def __init__(self, repo: Repository):
        self.repo = repo

    def search(self, query: str, limit: int = DEFAULT_LIMIT,
               doc_id: str | None = None) -> list[SearchResult]:
        keyword = self.repo.search_keyword(query, CANDIDATE_POOL, doc_id=doc_id)
        vector = self.repo.search_vector(embed_query(query), CANDIDATE_POOL, doc_id=doc_id)
        fused = reciprocal_rank_fusion([
            ([h.chunk_id for h in keyword], KEYWORD_WEIGHT),
            ([h.chunk_id for h in vector], 1.0),
        ])
        return self._to_sections(fused, limit)

    def _to_sections(self, fused: list[tuple[str, float]], limit: int) -> list[SearchResult]:
        section_of = {c.chunk_id: c.section_id for c in self.repo.chunks([c for c, _ in fused])}
        best: dict[str, tuple[str, float]] = {}
        order: list[str] = []
        for chunk_id, score in fused:
            section_id = section_of.get(chunk_id)
            if section_id is None or section_id in best:
                continue
            best[section_id] = (chunk_id, score)
            order.append(section_id)
            if len(order) >= limit:
                break

        results = []
        for section_id in order:
            section = self.repo.section(section_id)
            if section is None:
                continue
            matched_id, score = best[section_id]
            results.append(
                SearchResult(
                    section=section,
                    chunks=tuple(self.repo.section_chunks(section_id)),
                    score=score,
                    matched_chunk_id=matched_id,
                )
            )
        return results
