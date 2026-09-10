"""서식 부록 카탈로그. 서식 본문은 저해상도 이미지라 위치 정보만 색인한다."""

from __future__ import annotations

import re
from dataclasses import dataclass

from rnd_rag.parsing.pdf_doc import PdfDoc
from rnd_rag.parsing.profiles import DocProfile
from rnd_rag.parsing.toc import TERMINATOR

COVER = re.compile(r"^<\s*부록\s*(?P<no>\d+)\s*>")
FORM_NO = re.compile(r"^(?P<no>제\s*\d+\s*호|별표\s*\d+|\d+\s*[.．])\s*")
DELETED = re.compile(r"^삭제$")
# 표지 제목이 수록 종수를 밝히는 부록이 있다: "시행규칙 서식(10종)"
DECLARED = re.compile(r"\(\s*(\d+)\s*종\s*\)")


@dataclass(frozen=True)
class FormEntry:
    appendix_no: int
    appendix_title: str
    form_no: str
    name: str
    page_start: int
    page_end: int


COVER_SCAN = 3  # 표지 첫 줄에 쪽번호가 끼어드는 페이지가 있다


def _cover_pages(doc: PdfDoc, profile: DocProfile) -> list[tuple[int, int, str]]:
    """(부록번호, PDF페이지, 부록제목)"""
    out = []
    for lo, hi in profile.form_appendix_printed:
        for printed in range(lo, hi + 1):
            page = doc.page(printed + profile.page_offset)
            for i, line in enumerate(page.lines[:COVER_SCAN]):
                m = COVER.match(line.stripped)
                if not m:
                    continue
                rest = [
                    l.stripped
                    for l in page.lines[i + 1 :]
                    if abs(l.size - line.size) < 0.5
                ]
                title = COVER.sub("", line.stripped).strip()
                title = " ".join([title] + rest).strip()
                out.append((int(m.group("no")), page.page_pdf, title))
                break
    return out


def parse_catalog(doc: PdfDoc, profile: DocProfile) -> list[FormEntry]:
    entries: list[FormEntry] = []
    covers = _cover_pages(doc, profile)
    last_page = max(hi for _, hi in profile.form_appendix_printed)
    # 부록의 마지막 서식은 다음 부록 표지 직전에서 끝난다.
    bounds = [
        profile.printed_page(covers[i + 1][1]) - 1 if i + 1 < len(covers) else last_page
        for i in range(len(covers))
    ]
    for (appendix_no, page_pdf, appendix_title), appendix_end in zip(covers, bounds):
        rows: list[tuple[str, str, int]] = []
        for line in doc.page(page_pdf).lines:
            raw = line.stripped
            m = TERMINATOR.search(raw)
            if not m:
                continue
            head = raw[: m.start()].strip()
            fm = FORM_NO.match(head)
            if not fm:
                continue
            name = head[fm.end() :].strip()
            if not name or DELETED.match(name):
                continue
            rows.append((re.sub(r"\s+", "", fm.group("no")), name, int(m.group("page"))))
        for i, (form_no, name, start) in enumerate(rows):
            end = rows[i + 1][2] - 1 if i + 1 < len(rows) else appendix_end
            entries.append(
                FormEntry(
                    appendix_no=appendix_no,
                    appendix_title=appendix_title,
                    form_no=form_no,
                    name=name,
                    page_start=start,
                    page_end=max(start, end),
                )
            )
    return entries


def declared_count(appendix_title: str) -> int | None:
    """표지가 밝힌 수록 종수. 밝히지 않은 부록은 None."""
    m = DECLARED.search(appendix_title)
    return int(m.group(1)) if m else None


def to_text(e: FormEntry) -> str:
    return (
        f"서식명: {e.name}\n"
        f"근거: {e.appendix_title} {e.form_no}\n"
        f"수록 위치: 본권 인쇄 p{e.page_start}~{e.page_end}"
    )
