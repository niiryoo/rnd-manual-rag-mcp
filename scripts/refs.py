"""청크 본문에서 법령 조항 참조를 뽑아낸다."""

from __future__ import annotations

import re
from dataclasses import dataclass

# 긴 이름을 먼저 두어야 '국가연구개발혁신법 시행령'이 '국가연구개발혁신법'으로 잘리지 않는다
FULL_NAMES = (
    "국가연구개발혁신법 시행규칙",
    "국가연구개발혁신법 시행령",
    "국가연구개발혁신법",
    "국가연구개발사업 연구개발비 사용 기준",
    "과학기술기본법",
)
ALIASES = ("혁신법", "시행규칙", "시행령", "고시", "법")

_NAME_GROUP = "|".join(re.escape(n) for n in FULL_NAMES + ALIASES)
_ARTICLE = r"제\s*\d+\s*조(?:\s*의\s*\d+)?(?:\s*제?\s*\d+\s*항)?(?:\s*제?\s*\d+\s*호)?"

ARTICLE_REF = re.compile(rf"(?:(?P<law>{_NAME_GROUP})\s*)?(?P<article>{_ARTICLE})")
ATTACHMENT_REF = re.compile(
    r"(?:(?P<law>" + _NAME_GROUP + r")\s*)?"
    r"[\[［]?\s*(?P<kind>별표|별지)\s*(?:제\s*)?(?P<no>\d+)\s*(?:호)?\s*(?:서식)?\s*[\]］]?"
)


@dataclass(frozen=True)
class Ref:
    law: str
    target: str
    raw: str


def _squash(text: str) -> str:
    return re.sub(r"\s+", "", text)


def extract(text: str, alias_map: dict[str, str]) -> list[Ref]:
    seen: set[tuple[str, str]] = set()
    out: list[Ref] = []
    for m in ARTICLE_REF.finditer(text):
        law_raw = m.group("law")
        # 법령명이 없는 참조는 앞 문장에 딸린 것이라 문서 기본값으로 해석하지 않는다
        if not law_raw:
            continue
        law = alias_map.get(law_raw, law_raw)
        target = _squash(m.group("article"))
        key = (law, target)
        if key in seen:
            continue
        seen.add(key)
        out.append(Ref(law=law, target=target, raw=m.group(0).strip()))
    for m in ATTACHMENT_REF.finditer(text):
        law_raw = m.group("law")
        law = alias_map.get(law_raw, law_raw) if law_raw else ""
        target = f"{m.group('kind')}{m.group('no')}"
        key = (law, target)
        if key in seen:
            continue
        seen.add(key)
        out.append(Ref(law=law, target=target, raw=m.group(0).strip()))
    return out
