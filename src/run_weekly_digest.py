"""주간 다이제스트 생성 진입점: 생성 → 커밋.

GitHub Actions weekly_digest.yml 워크플로에서 호출된다.
"""
from __future__ import annotations

from git_commit import commit_and_push
from weekly_digest import generate_weekly_digest


def main() -> None:
    path = generate_weekly_digest()
    if path is not None:
        commit_and_push([path])


if __name__ == "__main__":
    main()
