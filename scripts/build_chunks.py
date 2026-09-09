"""매뉴얼 5종을 청크로 만들어 data/processed에 JSONL로 떨군다."""

from __future__ import annotations

import dataclasses
import json
import pathlib
import sys

import refs
from chunker import build
from forms import parse_catalog
from headings import locate
from pdf_doc import PdfDoc
from profiles import PROFILES
from toc import parse_toc, sections as toc_sections

OUT_DIR = pathlib.Path(__file__).resolve().parent.parent / "data" / "processed"


def _write(path: pathlib.Path, rows) -> int:
    with path.open("w", encoding="utf-8") as f:
        n = 0
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
    return n


def run(doc_ids: list[str] | None = None) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    targets = doc_ids or list(PROFILES)
    all_sections, all_chunks, all_refs = [], [], []

    for doc_id in targets:
        profile = PROFILES[doc_id]
        with PdfDoc(profile) as doc:
            entries = toc_sections(parse_toc(doc, profile))
            headings = locate(doc, profile, entries)
            catalog = parse_catalog(doc, profile) if profile.form_appendix_printed else []
            sections, chunks = build(doc, profile, headings, catalog)

        for c in chunks:
            for r in refs.extract(c.text, profile.alias_map):
                all_refs.append(
                    {"chunk_id": c.chunk_id, "doc_id": doc_id, **dataclasses.asdict(r)}
                )
        all_sections += [dataclasses.asdict(s) for s in sections]
        all_chunks += [dataclasses.asdict(c) for c in chunks]

        kinds: dict[str, int] = {}
        for c in chunks:
            kinds[c.content_type] = kinds.get(c.content_type, 0) + 1
        print(f"{doc_id:>5}: 섹션 {len(sections):>3}  청크 {len(chunks):>4}  {kinds}")

    n_sec = _write(OUT_DIR / "sections.jsonl", all_sections)
    n_chunk = _write(OUT_DIR / "chunks.jsonl", all_chunks)
    n_ref = _write(OUT_DIR / "refs.jsonl", all_refs)
    print(f"\n합계  섹션 {n_sec}  청크 {n_chunk}  참조 {n_ref}  →  {OUT_DIR}")


if __name__ == "__main__":
    run(sys.argv[1:] or None)
