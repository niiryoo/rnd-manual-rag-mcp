# rnd-manual-rag-mcp

정부과제 매뉴얼(국가연구개발혁신법 관련 5개 문서) 기반 RAG 검색 도구를 만들어, Claude가 조항을 정확히 인용하며 답하도록 grounding 지원. MCP 서버로 노출.

## 폴더 구조

```
rnd-manual-rag-mcp/
├── pyproject.toml        # 프로젝트 정의 · 의존성 · 실행 진입점
├── src/
│   └── rnd_rag/          # 라이브러리 (import되는 쪽)
│       ├── paths.py      #   데이터 폴더 위치
│       ├── parsing/      #   PDF → 조항 단위 청크
│       ├── store/        #   SQLite · 벡터/FTS 인덱스
│       ├── search/       #   하이브리드 검색
│       ├── agents/       #   LangGraph 오케스트레이션
│       ├── mcp/          #   MCP 서버 (검색 도구를 Claude에 노출)
│       └── cli/          #   실행 진입점
├── eval/                 # 검증 스크립트, 벤치마크 질문/정답, 평가 결과
├── data/
│   ├── raw/              # 원본 PDF 5개 (git 추적 제외 — 용량)
│   └── processed/        # 청킹 산출물 JSONL (git 추적 제외 — 재생성 가능)
├── db/                   # SQLite DB, 인덱스 (git 추적 제외)
├── demo/                 # 데모 스크린샷 · GIF
└── docs/                 # README, 아키텍처 노트
```

`src/rnd_rag/`는 import되는 라이브러리, `eval/`은 그것을 실행하는 소비자다.
`src` 레이아웃이라 `pip install -e .` 없이는 import되지 않으므로, 설치된 패키지와
작업 디렉터리가 섞이는 혼동이 생기지 않는다.

## 파이프라인 개요

```
data/raw (PDF)
   └─ parsing/   파싱 → 조항 단위 청킹 → data/processed
        └─ store/    색인 → db/ (SQLite + 인덱스)
             └─ search/   하이브리드 검색
                  └─ agents/  복잡도 분기 · 검증 루프
                       └─ mcp/   검색 도구 제공 → Claude가 조항 인용하며 응답
                            └─ eval/  정확도 · 토큰 정량 비교
```

## 시작하기

```powershell
# 1) 가상환경 활성화
.\.venv\Scripts\Activate.ps1

# 2) 프로젝트 설치 (editable — 코드 수정이 바로 반영됨)
pip install -e .

# 3) 원본 PDF 5개를 data/raw/ 에 넣기 (git에는 커밋되지 않음)

# 4) .env 만들고 OPENAI_API_KEY 채우기
copy .env.example .env
```

## 사용

```powershell
rag-build                      # 5개 문서 청킹 → data/processed/*.jsonl
rag-index                      # 청킹 산출물 → db/manual.db (임베딩 포함)

python eval\validate.py        # 파싱 검증
python eval\check_ground_truth.py   # 정답셋이 말뭉치와 맞는지
python eval\check_mcp.py       # MCP 서버를 띄워 도구 응답 확인
```

검증 스크립트는 기준을 충족하지 못하면 종료 코드 1을 반환한다.

## Claude Desktop 연결

`claude_desktop_config.json` 에 아래를 추가하고 Claude Desktop 을 재시작한다.

```json
{
  "mcpServers": {
    "rnd-manual": {
      "command": "C:\\경로\\rnd-manual-rag-mcp\\.venv\\Scripts\\python.exe",
      "args": ["-m", "rnd_rag.mcp.server"]
    }
  }
}
```

노출되는 도구는 넷이다. 사용자가 도구 이름을 부를 필요는 없고 Claude 가 질문을
보고 스스로 호출한다.

| 도구 | 용도 |
|---|---|
| `search_manual` | 규정 검색. 출처 쪽번호와 함께 섹션을 돌려준다 |
| `get_section` | 섹션 전문. 긴 섹션은 `offset` 으로 이어서 본다 |
| `find_form` | 서식 수록 위치 |
| `find_citation` | 조항 번호를 인용한 대목 |

## 향후 개선

- 배포 시 의존성 버전 고정(lock) 추가 — 다른 컴퓨터에서 동일 환경 재현
