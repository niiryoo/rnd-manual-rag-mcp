# rnd-manual-rag-mcp

정부과제 매뉴얼(국가연구개발혁신법 관련 5개 문서) 기반 RAG 검색 도구를 만들어, Claude가 조항을 정확히 인용하며 답하도록 grounding 지원. MCP 서버로 노출.

## 폴더 구조

```
rnd-manual-rag-mcp/
├── data/
│   ├── raw/          # 원본 PDF 5개 (git 추적 제외 — 용량 문제)
│   └── processed/    # 파싱 중간 산출물 (조항 단위 청크, JSONL 등)
├── db/               # SQLite DB, 벡터/FTS 인덱스 (git 추적 제외)
├── scripts/          # 파싱 · 조항 추출 · 색인 배치 스크립트
├── mcp_server/       # MCP 서버 코드 (검색 도구를 Claude에 노출)
├── eval/             # 벤치마크 질문/정답, Before-After 평가 결과
├── demo/             # 데모 스크린샷 · GIF
└── docs/             # README, 아키텍처 노트, 의사결정 기록
```

## 파이프라인 개요

```
data/raw (PDF)
   └─ scripts/  파싱 → 조항 단위 청킹 → data/processed
        └─ scripts/  색인 → db/ (SQLite + 인덱스)
             └─ mcp_server/  검색 도구 제공 → Claude가 조항 인용하며 응답
                  └─ eval/  Before-After 정량 비교
```

## 시작하기

```powershell
# 1) 가상환경 활성화
.\.venv\Scripts\Activate.ps1

# 2) 의존성 설치
pip install -r requirements.txt

# 3) 원본 PDF 5개를 data/raw/ 에 넣기 (git에는 커밋되지 않음)
```

## 관련 문서

- [decisions.md](decisions.md) — 설계 의사결정 기록
