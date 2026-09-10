"""프로젝트 경로. 데이터 폴더 위치를 한 곳에서만 정한다."""

from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
DB_DIR = ROOT / "db"
