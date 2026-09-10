"""문서별 파싱 프로파일. 문서 간 차이를 전부 여기로 모은다."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# 목차 들여쓰기는 문서마다 제각각이라 번호 패턴으로 레벨을 판정한다.
CHAPTER_KO = re.compile(r"^제\s*(\d+)\s*장(?:\s|$)")
SECTION_KO = re.compile(r"^제\s*(\d+)\s*절(?:\s|$)")
ROMAN = re.compile(r"^([ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+)\s*[.．]?(?:\s|$)")
ARABIC = re.compile(r"^(\d+)\s*[.．](?:\s|$)")
PAREN = re.compile(r"^\((\d+)\)(?:\s|$)")
# 참고·부칙·붙임은 괄호를 쓰기도 하고 안 쓰기도 한다.
NOTE = re.compile(r"^[<\[]?\s*(?:참고|붙임|부칙)\s*\d*\s*[>\]]?\s*[.:：]?")
APPENDIX = re.compile(r"^[<\[]?\s*부록\s*\d*\s*[>\]]")
# 본권 목차 뒤에는 표·그림 목차가 따로 붙는다. 섹션이 아니라 캡션 목록이다.
FIGURE = re.compile(r"^[<\[]\s*(?:표|그림)\s*[\d\-–~]+\s*[>\]]")


@dataclass(frozen=True)
class DocProfile:
    doc_id: str
    filename: str
    short_title: str
    page_offset: int  # 인쇄 쪽번호 = PDF 페이지 - page_offset
    toc_pdf_pages: tuple[int, ...]
    body_size: float
    level_patterns: tuple[tuple[re.Pattern, int], ...]
    alias_map: dict[str, str] = field(default_factory=dict)
    # 서식 본문은 저해상도 이미지라 색인하지 않고 카탈로그만 쓴다.
    form_appendix_printed: tuple[tuple[int, int], ...] = ()

    def printed_page(self, page_pdf: int) -> int:
        return page_pdf - self.page_offset

    def level_of(self, text: str) -> int | None:
        for pat, lvl in self.level_patterns:
            if pat.match(text.strip()):
                return lvl
        return None

    def in_form_appendix(self, printed: int) -> bool:
        return any(lo <= printed <= hi for lo, hi in self.form_appendix_printed)


_CHAPTER_SECTION_ITEM = (
    (CHAPTER_KO, 1),
    (APPENDIX, 1),
    (SECTION_KO, 2),
    (ARABIC, 3),
    (PAREN, 4),
    (NOTE, 5),
)

_CHAPTER_ITEM = (
    (CHAPTER_KO, 1),
    (APPENDIX, 1),
    (ARABIC, 2),
    (PAREN, 3),
    (NOTE, 4),
)

_ROMAN_ITEM = (
    (ROMAN, 1),
    (APPENDIX, 1),
    (ARABIC, 2),
    (PAREN, 3),
    (NOTE, 4),
)

INNOVATION_LAW_ALIASES = {
    "법": "국가연구개발혁신법",
    "혁신법": "국가연구개발혁신법",
    "시행령": "국가연구개발혁신법 시행령",
    "시행규칙": "국가연구개발혁신법 시행규칙",
}

# 별권1 2p 약어표에서 '고시'의 지시 대상을 명시하고 있다.
FUNDING_STANDARD = "국가연구개발사업 연구개발비 사용 기준"

PROFILES: dict[str, DocProfile] = {
    "main": DocProfile(
        doc_id="main",
        filename="[본권]_26년도_국가연구개발혁신법_매뉴얼.pdf",
        short_title="본권 국가연구개발혁신법 매뉴얼",
        page_offset=10,
        toc_pdf_pages=tuple(range(3, 11)),
        body_size=10.4,
        level_patterns=_CHAPTER_SECTION_ITEM,
        alias_map=dict(INNOVATION_LAW_ALIASES),
        # 부록5의 서식 활용 매트릭스가 마지막 쪽까지 이어진다
        form_appendix_printed=((327, 517),),
    ),
    "v1": DocProfile(
        doc_id="v1",
        filename="[별권1]_26년도_학생인건비통합관리_제도_매뉴얼.pdf",
        short_title="별권1 학생인건비통합관리",
        page_offset=4,
        toc_pdf_pages=(3, 4),
        body_size=9.9,
        level_patterns=_CHAPTER_ITEM,
        alias_map={**INNOVATION_LAW_ALIASES, "고시": FUNDING_STANDARD},
    ),
    "v2": DocProfile(
        doc_id="v2",
        filename="[별권2]_26년도_국가연구개발사업_기술료제도_매뉴얼.pdf",
        short_title="별권2 기술료제도",
        page_offset=4,
        toc_pdf_pages=(3,),
        body_size=11.0,
        level_patterns=_CHAPTER_ITEM,
        alias_map=dict(INNOVATION_LAW_ALIASES),
    ),
    "v3": DocProfile(
        doc_id="v3",
        filename="[별권3]_26년도_국가연구개발사업_제재처분_가이드라인.pdf",
        short_title="별권3 제재처분 가이드라인",
        page_offset=10,
        toc_pdf_pages=(7, 8, 9, 10),
        body_size=11.0,
        level_patterns=_CHAPTER_ITEM,
        alias_map=dict(INNOVATION_LAW_ALIASES),
    ),
    "v4": DocProfile(
        doc_id="v4",
        filename="[별권4]_26년도_연구시설·장비비_통합관리제_운영·관리_매뉴얼.pdf",
        short_title="별권4 연구시설·장비비 통합관리제",
        page_offset=4,
        toc_pdf_pages=(3,),
        body_size=12.0,
        level_patterns=_ROMAN_ITEM,
        alias_map={**INNOVATION_LAW_ALIASES, "고시": FUNDING_STANDARD},
    ),
}
