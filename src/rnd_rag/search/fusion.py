"""순위 융합. 점수 체계가 달라 직접 더할 수 없으므로 순위만 쓴다."""

from __future__ import annotations

from collections import defaultdict

RRF_K = 60  # 원 논문(Cormack 2009) 값. 크면 상위권 우위가 완만해진다
KEYWORD_WEIGHT = 2.0  # 정답셋에서 1·2·3 중 2가 최적


def reciprocal_rank_fusion(
    ranked_lists: list[tuple[list[str], float]], k: int = RRF_K
) -> list[tuple[str, float]]:
    scores: dict[str, float] = defaultdict(float)
    for ids, weight in ranked_lists:
        for position, item_id in enumerate(ids):
            scores[item_id] += weight / (k + position + 1)
    return sorted(scores.items(), key=lambda pair: -pair[1])
