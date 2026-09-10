"""표 추출. 조회형 질문의 답이 대부분 표 안에 있어 구조를 살려서 꺼낸다."""

from __future__ import annotations

import re
from dataclasses import dataclass

import pymupdf

from rnd_rag.parsing.pdf_doc import Page, PdfDoc

CAPTION = re.compile(r"^[<\[]\s*(?:표|그림)\s*[\d\-–~]+\s*[>\]]")
CAPTION_GAP = 45.0  # 표 위 캡션이 떨어져 있는 거리
MIN_ROWS = 2
MAX_EMPTY_RATIO = 0.6
MAX_DOMINANT_RATIO = 0.5


@dataclass(frozen=True)
class Table:
    page_pdf: int
    bbox: tuple[float, float, float, float]
    rows: list[list[str]]
    caption: str
    kind: str  # table | formula
    # 셀 추출이 놓친 표 안의 줄. 버리면 본문이 통째로 사라진다.
    residual: tuple[str, ...] = ()

    @property
    def header(self) -> list[str]:
        return self.rows[0] if self.rows else []


def _clean(cell) -> str:
    if not cell:
        return ""
    return re.sub(r"\s+", " ", cell).strip()


def _forward_fill(rows: list[list[str]]) -> list[list[str]]:
    """병합 셀은 빈 칸으로 나와서 각 행이 단독으로 해석되지 않는다."""
    filled: list[list[str]] = []
    for r, row in enumerate(rows):
        out = []
        for c, cell in enumerate(row):
            if cell:
                out.append(cell)
            elif r > 0 and c < len(filled[r - 1]):
                out.append(filled[r - 1][c])
            else:
                out.append("")
        filled.append(out)
    return filled


def _empty_ratio(rows: list[list[str]]) -> float:
    total = sum(len(r) for r in rows)
    if not total:
        return 1.0
    empty = sum(1 for r in rows for c in r if not c)
    return empty / total


def _dominant_cell_ratio(rows: list[list[str]]) -> float:
    """도표가 표로 잡히면 내용이 셀 하나에 통째로 들어간다."""
    lengths = [len(c) for r in rows for c in r]
    total = sum(lengths)
    if not total:
        return 1.0
    return max(lengths) / total


def _looks_like_formula(rows: list[list[str]]) -> bool:
    # 분수선이 벡터 선이라 계산식 블록이 표로 잡힌다. 표로 직렬화하면 나눗셈이 사라진다.
    if len(rows) > 5:
        return False
    joined = " ".join(c for r in rows for c in r)
    return "=" in joined and len(joined) < 400


def _residual_lines(page: Page, bbox, rows: list[list[str]]) -> tuple[str, ...]:
    captured = re.sub(r"\s", "", " ".join(c for r in rows for c in r))
    out = []
    for line in page.lines:
        if not (bbox[1] - 2 <= line.y0 <= bbox[3] + 2):
            continue
        text = line.stripped
        key = re.sub(r"\s", "", text)
        if len(key) < 2 or key in captured:
            continue
        out.append(text)
    return tuple(out)


def _caption_for(page: Page, bbox) -> str:
    top = bbox[1]
    best = ""
    best_gap = CAPTION_GAP
    for line in page.lines:
        gap = top - line.y0
        if 0 < gap <= best_gap:
            text = line.stripped
            if CAPTION.match(text) or (line.bold and len(text) <= 60):
                best, best_gap = text, gap
    return best


def extract(doc: PdfDoc, page_pdf: int) -> list[Table]:
    raw_page = doc.raw_page(page_pdf)
    page = doc.page(page_pdf)
    out: list[Table] = []
    for t in raw_page.find_tables().tables:
        rows = [[_clean(c) for c in row] for row in t.extract()]
        rows = [r for r in rows if any(r)]
        if len(rows) < MIN_ROWS:
            continue
        if _looks_like_formula(rows):
            text = raw_page.get_text("text", clip=pymupdf.Rect(t.bbox)).strip()
            out.append(
                Table(
                    page_pdf=page_pdf,
                    bbox=tuple(t.bbox),
                    rows=[[line] for line in text.splitlines() if line.strip()],
                    caption=_caption_for(page, t.bbox),
                    kind="formula",
                )
            )
            continue
        if _empty_ratio(rows) > MAX_EMPTY_RATIO:
            continue
        if _dominant_cell_ratio(rows) > MAX_DOMINANT_RATIO:
            continue
        out.append(
            Table(
                page_pdf=page_pdf,
                bbox=tuple(t.bbox),
                rows=_forward_fill(rows),
                caption=_caption_for(page, t.bbox),
                kind="table",
                residual=_residual_lines(page, t.bbox, rows),
            )
        )
    return out


def to_markdown(table: Table) -> str:
    if table.kind == "formula":
        return "\n".join(r[0] for r in table.rows)
    rows = table.rows
    width = max(len(r) for r in rows)
    padded = [r + [""] * (width - len(r)) for r in rows]
    head, body = padded[0], padded[1:]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * width]
    lines += ["| " + " | ".join(r) + " |" for r in body]
    if table.residual:
        lines += ["", *table.residual]
    return "\n".join(lines)
