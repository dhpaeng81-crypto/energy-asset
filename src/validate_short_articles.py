"""short-articles 발행 게이트 검증.

status가 published인데 opinion_ratio_check가 true가 아닌 글이 있으면 실패 처리한다.
발행 전 게이트 체크리스트(README 참고)를 통과하지 않은 글이 실수로 발행 상태로
남는 것을 막기 위한 검증이다. GitHub Actions에서 vault/short-articles 변경 시
자동 실행된다.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SHORT_ARTICLES_DIR = REPO_ROOT / "vault" / "short-articles"


def _parse_frontmatter(path: Path) -> dict[str, Any] | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    return yaml.safe_load(parts[1]) or {}


def find_violations(articles_dir: Path = SHORT_ARTICLES_DIR) -> list[Path]:
    violations = []
    for path in sorted(articles_dir.glob("*.md")):
        frontmatter = _parse_frontmatter(path)
        if not frontmatter:
            continue
        if frontmatter.get("status") == "published" and not frontmatter.get(
            "opinion_ratio_check"
        ):
            violations.append(path)
    return violations


def main() -> int:
    violations = find_violations()
    if violations:
        print("[validate_short_articles] 발행 게이트 미통과 상태로 published된 글이 있습니다:")
        for path in violations:
            print(f"  - {path.relative_to(REPO_ROOT)}")
        print(
            "opinion_ratio_check를 true로 바꾸기 전에는 status를 published로 둘 수 없습니다."
        )
        return 1

    print("[validate_short_articles] 발행 게이트 검증 통과.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
