"""파싱 파이프라인 검증. 기준을 명시하고 충족 여부를 판정한다.

사용:
    python eval/validate.py            5개 문서 전부
    python eval/validate.py v2 v4      일부만
"""

from __future__ import annotations

import collections
import json
import re
import statistics
import sys
from dataclasses import dataclass

from rnd_rag.parsing.forms import declared_count, parse_catalog
from rnd_rag.parsing.headings import locate
from rnd_rag.parsing.pdf_doc import PdfDoc
from rnd_rag.parsing.profiles import PROFILES
from rnd_rag.parsing.toc import parse_toc, sections as toc_sections
from rnd_rag.paths import PROCESSED_DIR

MIN_COVERAGE = 0.99
FOOTER_NUM = re.compile(r"^[/\\]?\s*(\d{1,3})\s*[/\\]?$")


@dataclass
class Result:
    name: str
    passed: bool
    summary: str


def _squash(text: str) -> str:
    return re.sub(r"[\s|\-]", "", text)


def check_page_offset(docs: dict[str, PdfDoc]) -> Result:
    print("■ 쪽번호 오프셋")
    mismatched = 0
    for doc_id, doc in docs.items():
        profile = doc.profile
        hit = miss = 0
        for page_pdf in range(1, doc.page_count + 1):
            for text in doc.footer_lines(page_pdf):
                m = FOOTER_NUM.match(text)
                if not m:
                    continue
                if int(m.group(1)) == profile.printed_page(page_pdf):
                    hit += 1
                else:
                    miss += 1
        mismatched += miss
        print(f"  {doc_id:<5} PDF-{profile.page_offset:<3} {hit:>4}/{hit + miss:<4} 일치"
              + (f"   불일치 {miss}" if miss else ""))
    passed = mismatched == 0
    return Result("쪽번호 오프셋", passed, f"불일치 {mismatched}건")


def check_headings(docs: dict[str, PdfDoc]) -> Result:
    print("\n■ 헤딩 매칭")
    failed = 0
    inexact: list[tuple[str, object]] = []
    for doc_id, doc in docs.items():
        entries = toc_sections(parse_toc(doc, doc.profile))
        found = locate(doc, doc.profile, entries)
        methods = collections.Counter(h.method for h in found)
        failed += methods["none"]
        inexact += [(doc_id, h) for h in found if h.method not in ("exact", "none")]
        ok = len(found) - methods["none"]
        detail = "  ".join(f"{k} {v}" for k, v in sorted(methods.items()))
        print(f"  {doc_id:<5} {ok:>3}/{len(found):<3} {detail}")

    if inexact:
        print(f"\n  비-exact {len(inexact)}건 (목차와 본문 제목이 다른 경우):")
        for doc_id, h in inexact:
            print(f"    [{doc_id:<4}] p{h.entry.page_printed:>3}  {h.method:<6} 목차 {h.title[:52]!r}")
    return Result("헤딩 매칭", failed == 0, f"실패 {failed}건")


def check_coverage(docs: dict[str, PdfDoc], chunks: list[dict], sections: list[dict]) -> Result:
    print("\n■ 본문 커버리지 (줄 단위)")
    blobs: dict[str, str] = {}
    for doc_id in docs:
        parts = [c["text"] for c in chunks if c["doc_id"] == doc_id]
        parts += [s["title"] for s in sections if s["doc_id"] == doc_id]
        blobs[doc_id] = _squash("".join(parts))

    worst = 1.0
    for doc_id, doc in docs.items():
        profile = doc.profile
        blob = blobs[doc_id]
        hit = total = 0
        for page_pdf in range(1, doc.page_count + 1):
            printed = profile.printed_page(page_pdf)
            if printed < 1 or profile.in_form_appendix(printed):
                continue
            if page_pdf in profile.toc_pdf_pages:
                continue
            for line in doc.page(page_pdf).lines:
                key = _squash(line.stripped)
                if len(key) < 6:
                    continue
                total += 1
                hit += key in blob
        ratio = hit / total if total else 1.0
        worst = min(worst, ratio)
        flag = "" if ratio >= MIN_COVERAGE else "   기준 미달"
        print(f"  {doc_id:<5} {hit:>6}/{total:<6} {ratio:>6.1%}{flag}")
    return Result("본문 커버리지", worst >= MIN_COVERAGE,
                  f"최저 {worst:.1%} (기준 {MIN_COVERAGE:.0%})")


def check_form_catalog(docs: dict[str, PdfDoc]) -> Result | None:
    targets = {d: doc for d, doc in docs.items() if doc.profile.form_appendix_printed}
    if not targets:
        return None
    print("\n■ 서식 카탈로그 (표지가 선언한 종수와 대조)")
    wrong = unchecked = 0
    for doc_id, doc in targets.items():
        catalog = parse_catalog(doc, doc.profile)
        counted = collections.Counter(e.appendix_no for e in catalog)
        titles = {e.appendix_no: e.appendix_title for e in catalog}
        for appendix_no in sorted(counted):
            got = counted[appendix_no]
            want = declared_count(titles[appendix_no])
            if want is None:
                unchecked += 1
                print(f"  부록{appendix_no}  {got:>2}종  표지에 종수 선언 없음 — 대조 불가")
                continue
            wrong += got != want
            mark = "일치" if got == want else "불일치"
            print(f"  부록{appendix_no}  {got:>2}종  표지 선언 {want}종  {mark}")
        print(f"  {doc_id} 합계 {len(catalog)}종")
    summary = f"불일치 {wrong}건"
    if unchecked:
        summary += f" (대조 불가 {unchecked}건)"
    return Result("서식 카탈로그", wrong == 0, summary)


def report_chunk_sizes(chunks: list[dict]) -> None:
    print("\n■ 청크 크기 분포 (판정 없음 — 임계값 근거가 아직 경험적)")
    child = sorted(c["char_count"] for c in chunks)
    parent: dict[str, int] = collections.defaultdict(int)
    for c in chunks:
        parent[c["section_id"]] += c["char_count"]
    sizes = sorted(parent.values())

    def q(values, p):
        return values[min(int(len(values) * p), len(values) - 1)]

    print(f"  child   최소 {child[0]}  중앙 {statistics.median(child):.0f}"
          f"  90% {q(child, 0.9)}  최대 {child[-1]}")
    print(f"  parent  중앙 {statistics.median(sizes):.0f}"
          f"  90% {q(sizes, 0.9)}  최대 {sizes[-1]}")
    kinds = collections.Counter(c["content_type"] for c in chunks)
    print(f"  종류별 {dict(kinds)}")
    print(f"  50자 미만 {sum(1 for s in child if s < 50)}개")


def _load(name: str) -> list[dict] | None:
    path = PROCESSED_DIR / name
    if not path.exists():
        return None
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]


def main() -> int:
    doc_ids = sys.argv[1:] or list(PROFILES)
    unknown = [d for d in doc_ids if d not in PROFILES]
    if unknown:
        print(f"알 수 없는 문서: {unknown}. 가능한 값: {list(PROFILES)}")
        return 2

    docs = {d: PdfDoc(PROFILES[d]) for d in doc_ids}
    try:
        results = [check_page_offset(docs), check_headings(docs)]

        chunks = _load("chunks.jsonl")
        sections = _load("sections.jsonl")
        if chunks is None or sections is None:
            print("\n■ 본문 커버리지 / 청크 크기 — 건너뜀")
            print("  data/processed 산출물이 없다. 먼저 `rag-build`를 실행할 것.")
        else:
            chunks = [c for c in chunks if c["doc_id"] in docs]
            sections = [s for s in sections if s["doc_id"] in docs]
            results.append(check_coverage(docs, chunks, sections))

        catalog_result = check_form_catalog(docs)
        if catalog_result:
            results.append(catalog_result)
        if chunks:
            report_chunk_sizes(chunks)
    finally:
        for doc in docs.values():
            doc.close()

    print("\n" + "─" * 56)
    for r in results:
        print(f"  {'PASS' if r.passed else 'FAIL'}  {r.name:<14} {r.summary}")
    failed = [r for r in results if not r.passed]
    print(f"\n{len(results)}개 검사 중 {len(results) - len(failed)}개 PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
