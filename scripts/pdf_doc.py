"""PDF 접근 계층. 페이지에서 줄 단위 텍스트와 조판 정보를 꺼낸다."""

from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass

import pymupdf

from profiles import DocProfile

RAW_DIR = pathlib.Path(__file__).resolve().parent.parent / "data" / "raw"

MARGIN = 60.0  # 러닝 헤더·푸터가 놓이는 상하단 여백
BOLD_FLAG = 1 << 4

_FOOTER_NUM = re.compile(r"^[/\\]?\s*\d{1,3}\s*[/\\]?$")


@dataclass(frozen=True)
class Line:
    text: str
    size: float
    bold: bool
    x0: float
    y0: float
    page_pdf: int

    @property
    def stripped(self) -> str:
        return self.text.strip()


@dataclass(frozen=True)
class Page:
    page_pdf: int
    page_printed: int
    lines: tuple[Line, ...]
    width: float
    height: float

    @property
    def text(self) -> str:
        return "\n".join(l.text for l in self.lines)

    @property
    def char_count(self) -> int:
        return len(re.sub(r"\s", "", self.text))


class PdfDoc:
    def __init__(self, profile: DocProfile):
        self.profile = profile
        self.path = RAW_DIR / profile.filename
        self._doc = pymupdf.open(self.path)

    def __enter__(self) -> "PdfDoc":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        self._doc.close()

    @property
    def page_count(self) -> int:
        return self._doc.page_count

    def raw_page(self, page_pdf: int):
        return self._doc[page_pdf - 1]

    def page(self, page_pdf: int) -> Page:
        p = self.raw_page(page_pdf)
        h, w = p.rect.height, p.rect.width
        lines: list[Line] = []
        for block in p.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                spans = [s for s in line["spans"] if s["text"].strip()]
                if not spans:
                    continue
                y0 = line["bbox"][1]
                if y0 < MARGIN or y0 > h - MARGIN:
                    continue
                text = "".join(s["text"] for s in line["spans"])
                lead = spans[0]
                lines.append(
                    Line(
                        text=text,
                        size=round(lead["size"], 1),
                        bold=bool(lead["flags"] & BOLD_FLAG),
                        x0=line["bbox"][0],
                        y0=y0,
                        page_pdf=page_pdf,
                    )
                )
        lines.sort(key=lambda l: (round(l.y0, 1), l.x0))
        return Page(
            page_pdf=page_pdf,
            page_printed=self.profile.printed_page(page_pdf),
            lines=tuple(lines),
            width=w,
            height=h,
        )

    def pages(self, start: int = 1, end: int | None = None):
        end = end or self.page_count
        for pno in range(start, end + 1):
            yield self.page(pno)

    def image_coverage(self, page_pdf: int) -> float:
        p = self.raw_page(page_pdf)
        area = 0.0
        for im in p.get_images(full=True):
            for r in p.get_image_rects(im[0]):
                area += r.width * r.height
        return area / (p.rect.width * p.rect.height)


def is_footer_number(text: str) -> bool:
    return bool(_FOOTER_NUM.match(text.strip()))
