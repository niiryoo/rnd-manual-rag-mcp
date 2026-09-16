"""MCP 서버를 stdio 로 띄워 도구가 실제로 응답하는지 확인한다.

Claude Desktop 과 같은 경로로 별도 프로세스를 띄우고 프로토콜로 호출한다.

사용:
    python eval/check_mcp.py
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

EXPECTED_TOOLS = {"search_manual", "get_section", "find_form", "find_citation"}
# 응답이 커지면 토큰 예산이 조용히 무너진다
MAX_SEARCH_CHARS = 8000
MAX_SECTION_CHARS = 8000
CHARS_PER_TOKEN = 0.85


@dataclass
class Result:
    name: str
    passed: bool
    summary: str


def text_of(result) -> str:
    return "\n".join(c.text for c in result.content if hasattr(c, "text"))


def tokens(text: str) -> int:
    return round(len(text) / CHARS_PER_TOKEN)


async def run() -> list[Result]:
    params = StdioServerParameters(command=sys.executable, args=["-m", "rnd_rag.mcp.server"])
    results: list[Result] = []

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            info = await session.initialize()
            print(f"■ 서버 기동\n  {info.server_info.name} v{info.server_info.version or '0'}")
            results.append(Result("서버 기동", True, info.server_info.name))

            listed = await session.list_tools()
            names = {t.name for t in listed.tools}
            missing = EXPECTED_TOOLS - names
            print(f"\n■ 도구 등록\n  {sorted(names)}")
            results.append(
                Result("도구 등록", not missing,
                       "전부 등록" if not missing else f"누락 {sorted(missing)}")
            )

            print("\n■ 도구 호출")
            calls = [
                ("search_manual", {"query": "중소기업 기술료율 얼마야?", "limit": 3}),
                ("search_manual", {"query": "학생인건비 이관", "limit": 1, "doc_id": "v1"}),
                ("get_section", {"section_id": "v1-s030"}),
                ("find_form", {"name": "연차보고서"}),
                ("find_citation", {"target": "제32조제1항", "limit": 1}),
            ]
            failed = []
            sizes: dict[str, int] = {}
            for name, args in calls:
                try:
                    body = text_of(await session.call_tool(name, args))
                    label = f"{name}({', '.join(f'{k}={v!r}' for k, v in args.items())[:46]})"
                    print(f"  {label:<62} {len(body):>6,}자 ≈ {tokens(body):>6,}토큰")
                    sizes[name] = max(sizes.get(name, 0), len(body))
                    if not body.strip():
                        failed.append(f"{name} 빈 응답")
                except Exception as e:
                    print(f"  {name} 실패: {type(e).__name__}: {e}")
                    failed.append(name)
            results.append(
                Result("도구 호출", not failed,
                       f"{len(calls)}건 호출" if not failed else f"실패 {failed}")
            )

            over = []
            if sizes.get("search_manual", 0) > MAX_SEARCH_CHARS:
                over.append(f"search_manual {sizes['search_manual']}자")
            if sizes.get("get_section", 0) > MAX_SECTION_CHARS:
                over.append(f"get_section {sizes['get_section']}자")
            print(f"\n■ 응답 크기 상한 (search {MAX_SEARCH_CHARS:,}자 · section {MAX_SECTION_CHARS:,}자)")
            results.append(
                Result("응답 크기", not over, "상한 이내" if not over else f"초과 {over}")
            )

    return results


def main() -> int:
    results = asyncio.run(run())
    print("\n" + "─" * 56)
    for r in results:
        print(f"  {'PASS' if r.passed else 'FAIL'}  {r.name:<12} {r.summary}")
    failed = [r for r in results if not r.passed]
    print(f"\n{len(results)}개 검사 중 {len(results) - len(failed)}개 PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
