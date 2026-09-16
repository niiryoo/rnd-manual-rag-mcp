"""프로젝트 경로. 데이터 폴더 위치를 한 곳에서만 정한다."""

from __future__ import annotations

import os
import pathlib

# 소스 위치로 루트를 찾으므로 editable 설치를 전제한다. 옮겨야 하면 환경변수로 덮어쓴다
ROOT = pathlib.Path(os.getenv("RND_RAG_ROOT") or pathlib.Path(__file__).resolve().parents[2])
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
DB_DIR = ROOT / "db"
