"""정답셋이 실제 말뭉치와 맞는지 검증한다.

정답 섹션이 존재하는지, must_contain 문자열이 그 섹션 안에 실제로 있는지 확인한다.
정답이 틀리면 이후 모든 측정이 무의미하므로 측정 전에 반드시 통과해야 한다.

사용:
    python eval/check_ground_truth.py
"""

from __future__ import annotations

import collections
import json
import pathlib

from rnd_rag.paths import PROCESSED_DIR

GT_PATH = pathlib.Path(__file__).resolve().parent / "ground_truth.jsonl"


def load_jsonl(path: pathlib.Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def main() -> int:
    cases = load_jsonl(GT_PATH)
    chunks = load_jsonl(PROCESSED_DIR / "chunks.jsonl")
    sections = load_jsonl(PROCESSED_DIR / "sections.jsonl")

    known = {s["section_id"]: s for s in sections}
    text_of: dict[str, list[str]] = collections.defaultdict(list)
    for c in chunks:
        text_of[c["section_id"]].append(c["text"])
    joined = {sid: "\n".join(parts) for sid, parts in text_of.items()}

    problems = 0
    by_type = collections.Counter(c["type"] for c in cases)

    for case in cases:
        issues = []
        for sid in case["answer_sections"]:
            if sid not in known:
                issues.append(f"섹션 없음: {sid}")
                continue
            if sid not in joined:
                issues.append(f"섹션에 청크 없음: {sid}")
        body = "\n".join(joined.get(sid, "") for sid in case["answer_sections"])
        for needle in case["must_contain"]:
            if needle not in body:
                issues.append(f"정답 섹션에 {needle!r} 없음")

        mark = "OK  " if not issues else "FAIL"
        titles = " / ".join(
            " > ".join(known[sid]["level_path"][-2:]) if sid in known else "?"
            for sid in case["answer_sections"]
        )
        print(f"{mark} {case['id']}  [{case['type']:<11}] {case['query']}")
        print(f"       → {titles[:86]}")
        for i in issues:
            print(f"       !! {i}")
            problems += 1

    print(f"\n유형 분포: {dict(by_type)}")
    print(f"질의 {len(cases)}개, 문제 {problems}건")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
