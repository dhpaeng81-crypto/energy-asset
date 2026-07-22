"""생성된 vault 파일을 git에 커밋/푸시한다.

GitHub Actions 워크플로에서 사용하며, 로컬에서도 동일하게 동작한다.
커밋할 변경사항이 없으면 조용히 종료한다 (에러 아님).
"""
from __future__ import annotations

import subprocess
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=REPO_ROOT, check=True, capture_output=True, text=True)


def commit_and_push(paths: list[Path], message: str | None = None) -> bool:
    """지정된 경로들을 add/commit/push한다. 실제로 커밋이 생성되면 True를 반환한다."""
    if not paths:
        print("[git_commit] 커밋할 파일이 없습니다.")
        return False

    _run(["git", "add", *[str(p) for p in paths]])

    status = _run(["git", "status", "--porcelain"])
    if not status.stdout.strip():
        print("[git_commit] 변경사항 없음 — 커밋을 건너뜁니다.")
        return False

    commit_message = message or f"뉴스 자동 수집: {date.today().isoformat()}"
    _run(["git", "commit", "-m", commit_message])
    _run(["git", "push"])
    print(f"[git_commit] 커밋/푸시 완료: {commit_message}")
    return True


if __name__ == "__main__":
    target_paths = [Path(p) for p in sys.argv[1:]] or [REPO_ROOT / "vault"]
    commit_and_push(target_paths)
