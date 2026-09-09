"""목차 항목을 본문의 실제 시작 위치에 고정한다."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

from pdf_doc import Line, Page, PdfDoc
from profiles import DocProfile
from toc import TocEntry

# 장 표지는 번호 없이 제목만 큰 글씨로 앉히고, 본문 첫 장은 번호만 따로 조판한다.
LEADING_NUMBER = re.compile(
    r"^(?:제\s*\d+\s*[장절]|[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+\s*[.．]?|\d+\s*[.．]|\(\d+\)"
    r"|[<\[]\s*(?:참고|부록|붙임|부칙)\s*\d*\s*[>\]]?)\s*"
)

MAX_JOIN = 4  # 제목이 쪼개지는 최대 줄 수
SEARCH_BACK = 1
SEARCH_FORWARD = 3
FUZZY_MIN = 0.72  # 목차와 본문 제목이 다른 문서용 최소 유사도


@dataclass(frozen=True)
class Heading:
    entry: TocEntry
    page_pdf: int
    y0: float
    method: str

    @property
    def title(self) -> str:
        return self.entry.title

    @property
    def level(self) -> int:
        return self.entry.level


def match_key(text: str) -> str:
    return "".join(c for c in text if c.isalnum())


def strip_number(title: str) -> str:
    return LEADING_NUMBER.sub("", title.strip(), count=1)


def _is_heading_typeset(line: Line, profile: DocProfile) -> bool:
    return line.size > profile.body_size + 0.4 or line.bold


def _find_on_page(page: Page, targets: set[str], profile: DocProfile):
    # 상위 절 제목이 같은 페이지 위쪽에 있는 경우가 있어 첫 매치가 아니라 최고 점수를 쓴다.
    best = (0.0, None, "")
    lines = page.lines
    for i, line in enumerate(lines):
        if not _is_heading_typeset(line, profile):
            continue
        joined = ""
        for j in range(i, min(i + MAX_JOIN, len(lines))):
            joined += match_key(lines[j].text)
            if not joined:
                continue
            for t in targets:
                if joined == t:
                    return line.y0, "exact"
                # 본문 제목에는 근거 조항이나 상호참조가 덧붙는 경우가 많다.
                if joined.startswith(t):
                    score = difflib.SequenceMatcher(None, joined, t).ratio()
                    if score > best[0]:
                        best = (score, line.y0, "prefix")
            if not any(t.startswith(joined) for t in targets):
                break
    if best[1] is not None:
        return best[1], best[2]
    return None


def _find_fuzzy(page: Page, targets: set[str], profile: DocProfile):
    best = (0.0, None)
    lines = page.lines
    for i, line in enumerate(lines):
        if not _is_heading_typeset(line, profile):
            continue
        joined = ""
        for j in range(i, min(i + MAX_JOIN, len(lines))):
            joined += match_key(lines[j].text)
            for t in targets:
                r = difflib.SequenceMatcher(None, joined, t).ratio()
                if r > best[0]:
                    best = (r, line.y0)
    if best[0] >= FUZZY_MIN:
        return best[1], "fuzzy"
    return None


def locate(doc: PdfDoc, profile: DocProfile, entries: list[TocEntry]) -> list[Heading]:
    found: list[Heading] = []
    for e in entries:
        full = match_key(e.title)
        stripped = match_key(strip_number(e.title))
        targets = {t for t in (full, stripped) if len(t) >= 4}
        if not targets:
            targets = {t for t in (full, stripped) if t}
        base = e.page_printed + profile.page_offset
        window = [
            p for p in range(base - SEARCH_BACK, base + SEARCH_FORWARD + 1)
            if 1 <= p <= doc.page_count
        ]
        hit = None
        for finder in (_find_on_page, _find_fuzzy):
            for page_pdf in window:
                res = finder(doc.page(page_pdf), targets, profile)
                if res:
                    hit = Heading(entry=e, page_pdf=page_pdf, y0=res[0], method=res[1])
                    break
            if hit:
                break
        if hit:
            found.append(hit)
        else:
            found.append(Heading(entry=e, page_pdf=base, y0=0.0, method="none"))
    return found
