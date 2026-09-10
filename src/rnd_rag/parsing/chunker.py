"""섹션(parent)을 조립하고 그 안을 검색 단위(child)로 나눈다."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from rnd_rag.parsing import tables
from rnd_rag.parsing.forms import FormEntry, to_text as form_to_text
from rnd_rag.parsing.headings import Heading
from rnd_rag.parsing.pdf_doc import Line, PdfDoc
from rnd_rag.parsing.profiles import DocProfile
from rnd_rag.parsing.tables import Table

CHILD_MAX_CHARS = 700
TABLE_MAX_CHARS = 1800
MIN_STANDALONE_CHARS = 60
PAGE_TOP = 0.0
PAGE_BOTTOM = 10_000.0


@dataclass(frozen=True)
class Section:
    section_id: str
    doc_id: str
    title: str
    level_path: tuple[str, ...]
    page_pdf_start: int
    page_pdf_end: int
    # 앞머리는 쪽번호가 매겨지기 전 구간이라 인쇄 쪽을 비워 둔다
    page_printed_start: int | None
    page_printed_end: int | None


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    section_id: str
    doc_id: str
    content_type: str
    text: str
    text_for_embedding: str
    page_pdf_start: int
    page_pdf_end: int
    page_printed_start: int | None
    page_printed_end: int | None
    char_count: int
    caption: str = ""


@dataclass
class _TableCache:
    doc: PdfDoc
    _cache: dict[int, list[Table]] = field(default_factory=dict)

    def get(self, page_pdf: int) -> list[Table]:
        if page_pdf not in self._cache:
            self._cache[page_pdf] = tables.extract(self.doc, page_pdf)
        return self._cache[page_pdf]


def _level_paths(headings: list[Heading]) -> list[tuple[str, ...]]:
    paths: list[tuple[str, ...]] = []
    stack: list[tuple[int, str]] = []
    for h in headings:
        while stack and stack[-1][0] >= h.level:
            stack.pop()
        stack.append((h.level, h.title))
        paths.append(tuple(t for _, t in stack))
    return paths


def _in_table(line: Line, tbls: list[Table]) -> bool:
    return any(t.bbox[1] - 2 <= line.y0 <= t.bbox[3] + 2 for t in tbls)


def _page_blocks(cache: _TableCache, page_pdf: int, y_min: float, y_max: float):
    """(y좌표, 종류, 내용) 목록을 조판 순서대로 돌려준다."""
    page = cache.doc.page(page_pdf)
    tbls = [
        t
        for t in cache.get(page_pdf)
        if y_min <= (t.bbox[1] + t.bbox[3]) / 2 <= y_max
    ]
    items: list[tuple[float, str, object]] = [(t.bbox[1], "table", t) for t in tbls]
    # 캡션은 표 바깥에 있어 텍스트로 남지만 이미 표 청크가 들고 있다
    claimed = {re.sub(r"\s", "", t.caption) for t in tbls if t.caption}
    for line in page.lines:
        if not (y_min <= line.y0 <= y_max):
            continue
        if _in_table(line, tbls):
            continue
        if re.sub(r"\s", "", line.stripped) in claimed:
            continue
        items.append((line.y0, "line", line))
    items.sort(key=lambda x: x[0])
    return items


def _split_text(lines: list[Line]) -> list[list[Line]]:
    runs: list[list[Line]] = []
    current: list[Line] = []
    size = 0
    for line in lines:
        n = len(line.stripped)
        if current and size + n > CHILD_MAX_CHARS:
            runs.append(current)
            current, size = [], 0
        current.append(line)
        size += n
    if current:
        runs.append(current)
    return runs


def _split_table(table: Table) -> list[str]:
    md = tables.to_markdown(table)
    if len(md) <= TABLE_MAX_CHARS or table.kind == "formula":
        return [md]
    rows = table.rows
    width = max(len(r) for r in rows)
    head = rows[0] + [""] * (width - len(rows[0]))
    head_md = ["| " + " | ".join(head) + " |", "|" + "---|" * width]
    parts, buf, size = [], [], 0
    for row in rows[1:]:
        padded = row + [""] * (width - len(row))
        line = "| " + " | ".join(padded) + " |"
        if buf and size + len(line) > TABLE_MAX_CHARS:
            parts.append("\n".join(head_md + buf))
            buf, size = [], 0
        buf.append(line)
        size += len(line)
    if buf:
        parts.append("\n".join(head_md + buf))
    return parts


def _embedding_text(profile: DocProfile, path: tuple[str, ...], body: str) -> str:
    return f"[{profile.short_title}] " + " > ".join(path) + f"\n{body}"


def _printed(profile: DocProfile, page_pdf: int) -> int | None:
    n = profile.printed_page(page_pdf)
    return n if n >= 1 else None


def _emit(
    cache: _TableCache,
    profile: DocProfile,
    section_id: str,
    path: tuple[str, ...],
    ranges: list[tuple[int, float, float]],
) -> list[Chunk]:
    chunks: list[Chunk] = []
    pending: list[Line] = []

    def make(content_type: str, text: str, pages: list[int], caption: str = "") -> None:
        chunks.append(
            Chunk(
                chunk_id=f"{section_id}-c{len(chunks):02d}",
                section_id=section_id,
                doc_id=profile.doc_id,
                content_type=content_type,
                text=text,
                text_for_embedding=_embedding_text(profile, path, text),
                page_pdf_start=min(pages),
                page_pdf_end=max(pages),
                page_printed_start=_printed(profile, min(pages)),
                page_printed_end=_printed(profile, max(pages)),
                char_count=len(text),
                caption=caption,
            )
        )

    def flush() -> None:
        nonlocal pending
        for run in _split_text(pending):
            body = "\n".join(l.stripped for l in run)
            if body.strip():
                make("text", body, [l.page_pdf for l in run])
        pending = []

    for page_pdf, y_min, y_max in ranges:
        for _, kind, payload in _page_blocks(cache, page_pdf, y_min, y_max):
            if kind == "line":
                pending.append(payload)
                continue
            # 표 바로 앞 도입줄은 혼자 두면 검색에 쓸모가 없어 표에 붙인다
            lead = f"{payload.caption}\n" if payload.caption else ""
            if pending and sum(len(l.stripped) for l in pending) < MIN_STANDALONE_CHARS:
                lead += "\n".join(l.stripped for l in pending) + "\n"
                pending = []
            flush()
            for part in _split_table(payload):
                make(payload.kind, lead + part, [page_pdf], payload.caption)
                lead = ""
    flush()
    return chunks


def _front_ranges(doc: PdfDoc, profile: DocProfile, first: Heading) -> list[tuple[int, float, float]]:
    out = []
    for page_pdf in range(1, first.page_pdf + 1):
        if page_pdf in profile.toc_pdf_pages:
            continue
        y_max = first.y0 - 1 if page_pdf == first.page_pdf else PAGE_BOTTOM
        if y_max > PAGE_TOP:
            out.append((page_pdf, PAGE_TOP, y_max))
    return out


def build(
    doc: PdfDoc,
    profile: DocProfile,
    headings: list[Heading],
    catalog: list[FormEntry] | None = None,
) -> tuple[list[Section], list[Chunk]]:
    ordered = sorted(headings, key=lambda h: (h.page_pdf, h.y0))
    paths = _level_paths(ordered)
    cache = _TableCache(doc)
    sections: list[Section] = []
    chunks: list[Chunk] = []

    if ordered:
        front = _emit(cache, profile, f"{profile.doc_id}-front", ("머리말",),
                      _front_ranges(doc, profile, ordered[0]))
        if front:
            chunks += front
            sections.append(
                Section(
                    section_id=f"{profile.doc_id}-front",
                    doc_id=profile.doc_id,
                    title="머리말",
                    level_path=("머리말",),
                    page_pdf_start=1,
                    page_pdf_end=ordered[0].page_pdf,
                    page_printed_start=_printed(profile, 1),
                    page_printed_end=_printed(profile, ordered[0].page_pdf),
                )
            )

    for i, h in enumerate(ordered):
        nxt = ordered[i + 1] if i + 1 < len(ordered) else None
        end_page = nxt.page_pdf if nxt else doc.page_count
        if profile.in_form_appendix(profile.printed_page(h.page_pdf)):
            continue

        section_id = f"{profile.doc_id}-s{len(sections):03d}"
        ranges = []
        for page_pdf in range(h.page_pdf, min(end_page, doc.page_count) + 1):
            y_min = h.y0 + 1 if page_pdf == h.page_pdf else PAGE_TOP
            y_max = nxt.y0 - 1 if (nxt and page_pdf == end_page) else PAGE_BOTTOM
            if y_max > y_min:
                ranges.append((page_pdf, y_min, y_max))
        chunks += _emit(cache, profile, section_id, paths[i], ranges)
        sections.append(
            Section(
                section_id=section_id,
                doc_id=profile.doc_id,
                title=h.title,
                level_path=paths[i],
                page_pdf_start=h.page_pdf,
                page_pdf_end=end_page,
                page_printed_start=_printed(profile, h.page_pdf),
                page_printed_end=_printed(profile, end_page),
            )
        )

    for j, entry in enumerate(catalog or []):
        body = form_to_text(entry)
        section_id = f"{profile.doc_id}-forms"
        chunks.append(
            Chunk(
                chunk_id=f"{section_id}-c{j:03d}",
                section_id=section_id,
                doc_id=profile.doc_id,
                content_type="form_index",
                text=body,
                text_for_embedding=f"[{profile.short_title}] 서식 목록\n{body}",
                page_pdf_start=entry.page_start + profile.page_offset,
                page_pdf_end=entry.page_end + profile.page_offset,
                page_printed_start=entry.page_start,
                page_printed_end=entry.page_end,
                char_count=len(body),
                caption=entry.name,
            )
        )
    if catalog:
        sections.append(
            Section(
                section_id=f"{profile.doc_id}-forms",
                doc_id=profile.doc_id,
                title="서식 목록",
                level_path=("서식 목록",),
                page_pdf_start=min(e.page_start for e in catalog) + profile.page_offset,
                page_pdf_end=max(e.page_end for e in catalog) + profile.page_offset,
                page_printed_start=min(e.page_start for e in catalog),
                page_printed_end=max(e.page_end for e in catalog),
            )
        )
    return sections, chunks
