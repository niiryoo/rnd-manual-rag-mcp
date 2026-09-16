"""2-gram 전처리. 색인과 질의가 같은 변환을 거쳐야 검색이 어긋나지 않는다."""

from __future__ import annotations

import re

WORD = re.compile(r"[0-9A-Za-z가-힣]+")
# 말뭉치에 거의 없어 AND 질의를 0건으로 만드는 의문사·조사
STOPWORDS = re.compile(
    r"^(얼마|얼마야|얼마인가|어떻게|어떡해|누가|언제|어디|어디야|왜|몇|몇년|뭐|무엇|"
    r"인가|인가요|일까|할까|되나|되나요|해줘|알려줘|있어|있나|야|요|좀|최대|경우|하는|"
    r"이|가|은|는|을|를|의|에|로|과|와|도|만|퍼센트)$"
)


def bigrams(word: str) -> list[str]:
    if len(word) < 2:
        return [word]
    return [word[i : i + 2] for i in range(len(word) - 1)]


def to_index_text(text: str) -> str:
    return " ".join(gram for word in WORD.findall(text) for gram in bigrams(word))


def content_words(query: str) -> list[str]:
    words = [w for w in WORD.findall(query) if not STOPWORDS.match(w)]
    return words or WORD.findall(query)


def to_match_expr(query: str) -> str:
    """어절 안은 구절로 묶고 어절끼리는 OR 로 잇는다."""
    return " OR ".join('"' + " ".join(bigrams(w)) + '"' for w in content_words(query))
