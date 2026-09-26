"""생성된 vault 파일을 git에 커밋/푸시한다.

GitHub Actions 워크플로에서 사용하며, 로컬에서도 동일하게 동작한다.
커밋할 변경사항이 없으면 조용히 종료한다 (에러 아님).
"""
from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

MAX_PUSH_RETRIES = 3


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=REPO_ROOT, check=True, capture_output=True, text=True)


def _push_with_retry() -> None:
    """다른 워크플로/사람이 같은 브랜치에 먼저 push해서 non-fast-forward로 실패하면
    rebase 후 재시도한다 (daily_news/weekly_digest가 비슷한 시각에 겹치는 경우 대비)."""
    for attempt in range(1, MAX_PUSH_RETRIES + 1):
        try:
            _run(["git", "push"])
            return
        except subprocess.CalledProcessError as exc:
            if attempt == MAX_PUSH_RETRIES:
                raise
            print(
                f"[git_commit] push 실패 — 원격에 새 커밋이 있을 수 있어 rebase 후 재시도 "
                f"({attempt}/{MAX_PUSH_RETRIES})"
            )
            print(exc.stderr)
            _run(["git", "pull", "--rebase", "--autostash"])


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
    _push_with_retry()
    print(f"[git_commit] 커밋/푸시 완료: {commit_message}")
    return True


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="지정된 경로를 git에 add/commit/push")
    parser.add_argument("paths", nargs="*", help="커밋할 경로 (기본: vault/ 전체)")
    parser.add_argument("--message", help="커밋 메시지 (기본: '뉴스 자동 수집: 오늘 날짜')")
    args = parser.parse_args()

    target_paths = [Path(p) for p in args.paths] or [REPO_ROOT / "vault"]
    commit_and_push(target_paths, args.message)
