"""목차 파싱. 헤딩 검출의 앵커이자 검증 정답셋으로 쓴다."""

from __future__ import annotations

import re
from dataclasses import dataclass

from pdf_doc import PdfDoc
from profiles import FIGURE, DocProfile

# 제목이 길면 리더가 점 두 개까지 줄어드는 줄이 있다.
LEADER = re.compile(r"[·․‥…．.∙•]{2,}")
# 한 줄에 항목이 둘씩 들어가는 줄이 있어 리더+쪽번호마다 끊는다.
TERMINATOR = re.compile(r"[·․‥…．.∙•]{2,}\s*(?P<page>\d{1,3})(?:\s|$)")
SKIP = ("CONTENTS", "목 차", "목  차", "목차")
# 목차 페이지에 섞인 안내 문구는 글머리 기호로 시작한다.
DECOR = re.compile(r"^[◆◇■□▶●○※]")


@dataclass(frozen=True)
class TocEntry:
    title: str
    level: int
    page_printed: int
    order: int
    numbered: bool = True
    kind: str = "section"  # section | caption

    @property
    def key(self) -> str:
        return normalize(self.title)


def normalize(text: str) -> str:
    text = re.sub(r"\s+", "", text)
    return re.sub(r"[·․‥…．.∙•]+$", "", text)


def parse_toc(doc: PdfDoc, profile: DocProfile) -> list[TocEntry]:
    entries: list[TocEntry] = []
    buffer: list[str] = []
    for page_pdf in profile.toc_pdf_pages:
        for line in doc.page(page_pdf).lines:
            raw = line.stripped
            if not raw or any(s in raw for s in SKIP):
                continue
            hits = list(TERMINATOR.finditer(raw))
            if not hits:
                # 제목이 다음 줄로 이어지는 항목이 있어 리더가 나올 때까지 모은다.
                if not LEADER.search(raw):
                    buffer.append(raw)
                continue
            cursor = 0
            for i, m in enumerate(hits):
                title = raw[cursor : m.start()].strip()
                cursor = m.end()
                if i == 0:
                    title = " ".join(buffer + [title]).strip()
                    buffer.clear()
                entry = _make_entry(title, int(m.group("page")), len(entries), profile)
                if entry:
                    entries.append(entry)
            tail = raw[cursor:].strip()
            if tail:
                buffer.append(tail)
    return entries


def _make_entry(title: str, page: int, order: int, profile: DocProfile) -> TocEntry | None:
    if not title or DECOR.match(title):
        return None
    if FIGURE.match(title):
        return TocEntry(title=title, level=0, page_printed=page, order=order, kind="caption")
    level = profile.level_of(title)
    return TocEntry(
        title=title,
        level=level if level is not None else 1,
        page_printed=page,
        order=order,
        numbered=level is not None,
    )


def sections(entries: list[TocEntry]) -> list[TocEntry]:
    return [e for e in entries if e.kind == "section"]


def captions(entries: list[TocEntry]) -> list[TocEntry]:
    return [e for e in entries if e.kind == "caption"]
