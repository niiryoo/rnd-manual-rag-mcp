"""하이브리드 검색. child 로 찾고 parent 섹션으로 돌려준다."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from rnd_rag.search.fusion import KEYWORD_WEIGHT, reciprocal_rank_fusion
from rnd_rag.store import Chunk, Repository, Section
from rnd_rag.store.embedder import embed_query

CANDIDATE_POOL = 100  # 융합 전에 각 경로에서 가져오는 후보 수
DEFAULT_LIMIT = 5

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchResult:
    section: Section
    chunks: tuple[Chunk, ...]
    score: float
    matched_chunk_id: str

    @property
    def citation(self) -> str:
        return self.section.citation

    @property
    def text(self) -> str:
        return "\n\n".join(c.text for c in self.chunks)


@dataclass(frozen=True)
class SearchResponse:
    results: list[SearchResult]
    keyword_only: bool = False  # 임베딩 호출이 실패해 키워드로만 찾은 경우


class SearchService:
    def __init__(self, repo: Repository):
        self.repo = repo

    def search(self, query: str, limit: int = DEFAULT_LIMIT,
               doc_id: str | None = None) -> SearchResponse:
        keyword = self.repo.search_keyword(query, CANDIDATE_POOL, doc_id=doc_id)
        ranked = [([h.chunk_id for h in keyword], KEYWORD_WEIGHT)]

        # 회사망에서 API 가 막혀 있어도 도구는 동작해야 한다
        keyword_only = False
        try:
            vector = self.repo.search_vector(embed_query(query), CANDIDATE_POOL, doc_id=doc_id)
            ranked.append(([h.chunk_id for h in vector], 1.0))
        except Exception as e:
            log.warning("질의 임베딩 실패, 키워드만 사용: %s: %s", type(e).__name__, e)
            keyword_only = True

        fused = reciprocal_rank_fusion(ranked)
        return SearchResponse(self._to_sections(fused, limit), keyword_only)

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
