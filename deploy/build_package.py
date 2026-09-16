"""배포 꾸러미를 만든다. 원본 PDF 와 개발용 파일은 뺀다."""

from __future__ import annotations

import os
import shutil
import sys
import zipfile
from pathlib import Path

from dotenv import load_dotenv

from rnd_rag.paths import ROOT
from rnd_rag.store import DB_PATH

OUT_DIR = ROOT / "dist"
PACKAGE = "정부과제매뉴얼검색"

INCLUDE_DIRS = ["src", "deploy"]
INCLUDE_FILES = ["pyproject.toml"]
SKIP_NAMES = {"__pycache__", "build_package.py"}


def copy_tree(src: Path, dst: Path) -> None:
    for path in src.rglob("*"):
        if any(part in SKIP_NAMES for part in path.parts):
            continue
        if path.is_dir():
            continue
        target = dst / path.relative_to(src.parent)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def write_env(target: Path, key: str) -> None:
    target.write_text(
        "# 임베딩 전용 키. 비워두면 키워드 검색으로 동작한다\n"
        f"OPENAI_API_KEY={key}\n"
        "EMBEDDING_MODEL=text-embedding-3-large\n",
        encoding="utf-8",
    )


def main() -> int:
    if not DB_PATH.exists():
        print(f"db 파일이 없습니다: {DB_PATH}\n먼저 rag-index 를 실행하세요.")
        return 1

    key = ""
    if "--with-key" in sys.argv:
        load_dotenv(ROOT / ".env")
        key = os.getenv("OPENAI_API_KEY", "")
        if not key:
            print(".env 에 OPENAI_API_KEY 가 없습니다.")
            return 1

    staging = OUT_DIR / PACKAGE
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    for name in INCLUDE_DIRS:
        copy_tree(ROOT / name, staging)
    for name in INCLUDE_FILES:
        shutil.copy2(ROOT / name, staging / name)

    (staging / "db").mkdir()
    shutil.copy2(DB_PATH, staging / "db" / DB_PATH.name)
    write_env(staging / ".env", key)

    archive = OUT_DIR / f"{PACKAGE}.zip"
    if archive.exists():
        archive.unlink()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in staging.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(staging.parent))

    print(f"꾸러미 생성: {archive}")
    print(f"  크기 {archive.stat().st_size / 1024 / 1024:.1f}MB")
    print(f"  API 키 {'포함됨' if key else '비어 있음 (--with-key 로 포함)'}")
    print("\n포함된 파일")
    for path in sorted(staging.rglob("*")):
        if path.is_file():
            rel = path.relative_to(staging)
            print(f"  {str(rel):<46}{path.stat().st_size / 1024:>9,.0f}KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
