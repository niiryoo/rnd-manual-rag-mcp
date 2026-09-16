"""Claude Desktop 설정에 이 서버를 등록한다. 기존 설정은 백업하고 병합한다."""

from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

SERVER_NAME = "rnd-manual"


def config_path() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("APPDATA 환경변수를 찾을 수 없습니다.")
    return Path(appdata) / "Claude" / "claude_desktop_config.json"


def load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # 손상된 설정을 덮어쓰면 다른 서버 설정까지 잃는다
        raise RuntimeError(
            f"기존 설정 파일이 손상되어 있습니다: {path}\n"
            "    파일을 직접 확인하거나 이름을 바꿔 치운 뒤 다시 실행하세요."
        )


def backup(path: Path) -> Path | None:
    if not path.exists():
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = path.with_name(f"{path.stem}.backup-{stamp}.json")
    shutil.copy2(path, target)
    return target


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    python = root / ".venv" / "Scripts" / "python.exe"
    if not python.exists():
        print(f"  가상환경을 찾을 수 없습니다: {python}")
        return 1

    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    config = load(path)
    saved = backup(path)

    servers = config.setdefault("mcpServers", {})
    servers[SERVER_NAME] = {"command": str(python), "args": ["-m", "rnd_rag.mcp.server"]}
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    others = [n for n in servers if n != SERVER_NAME]
    print(f"  등록 완료: {path}")
    if saved:
        print(f"  기존 설정 백업: {saved.name}")
    if others:
        print(f"  함께 등록된 다른 서버: {', '.join(others)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as e:
        print(f"  {e}")
        raise SystemExit(1)
