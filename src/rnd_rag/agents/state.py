"""그래프가 노드 사이로 넘기는 상태."""

from __future__ import annotations

import operator
from dataclasses import dataclass
from typing import Annotated, Literal, TypedDict

from rnd_rag.search.service import SearchResult

Complexity = Literal["simple", "complex"]
Verdict = Literal["ok", "insufficient"]

MAX_ATTEMPTS = 2  # 재검색 상한. 없으면 검증-재검색이 순환한다
MAX_EVIDENCE = 6  # 발췌에 실을 섹션 수. 늘리면 하나당 예산이 줄어 표가 잘린다


@dataclass(frozen=True)
class Usage:
    """응답이 준 토큰 수. 추정값을 섞지 않는다."""

    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            self.input_tokens + other.input_tokens,
            self.output_tokens + other.output_tokens,
            self.calls + other.calls,
        )


def merge_evidence(old: tuple[SearchResult, ...],
                   new: tuple[SearchResult, ...]) -> tuple[SearchResult, ...]:
    """검증이 지적해 새로 찾아온 것을 앞에 둔다. 상한을 넘으면 오래된 것부터 밀려난다."""
    seen: set[str] = set()
    merged = []
    for result in (*new, *old):
        if result.section.section_id in seen:
            continue
        seen.add(result.section.section_id)
        merged.append(result)
    return tuple(merged[:MAX_EVIDENCE])


class AgentState(TypedDict, total=False):
    query: str
    complexity: Complexity
    subqueries: tuple[str, ...]
    retrieved: Annotated[tuple[SearchResult, ...], merge_evidence]
    answer: str
    citations: tuple[str, ...]
    verdict: Verdict
    gap: str  # 검증이 지적한 빠진 정보. 다음 재검색의 질의
    escalated: bool  # 단순 경로가 인용 검사에 걸려 복합 경로로 올라간 경우
    attempts: int
    usage: Annotated[Usage, operator.add]
    trace: Annotated[tuple[str, ...], operator.add]
