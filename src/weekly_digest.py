"""주간 다이제스트 생성: news-inbox의 미검토(unread) 뉴스를 관련도순으로 정리해
월요일 검토를 돕는다.

핵심 제약: 이번 주에 무엇을 파고들지 "고르는 것"은 항상 사용자 몫이다. 이 스크립트는
정렬/집계만 하고 선택은 하지 않는다 — 다이제스트에는 순위와 링크만 있을 뿐,
어떤 이슈를 골라야 한다는 판단이나 추천 문구는 넣지 않는다.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
NEWS_INBOX_DIR = REPO_ROOT / "vault" / "news-inbox"
WEEKLY_DIGESTS_DIR = REPO_ROOT / "vault" / "weekly-digests"

STARS = {1: "★", 2: "★★", 3: "★★★", 4: "★★★★", 5: "★★★★★"}


def _parse_frontmatter(path: Path) -> dict[str, Any] | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    frontmatter = yaml.safe_load(parts[1]) or {}
    frontmatter["_stem"] = path.stem
    return frontmatter


def _as_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def collect_unread(since: date, inbox_dir: Path = NEWS_INBOX_DIR) -> list[dict[str, Any]]:
    items = []
    for path in inbox_dir.glob("*.md"):
        frontmatter = _parse_frontmatter(path)
        if not frontmatter or frontmatter.get("status") != "unread":
            continue
        item_date = _as_date(frontmatter.get("date"))
        if item_date is None or item_date < since:
            continue
        items.append(frontmatter)
    return items


def build_digest(items: list[dict[str, Any]], today: date) -> str:
    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        by_category[item.get("category", "미분류")].append(item)

    lines = [
        "---",
        f"date: {today.isoformat()}",
        "type: weekly-digest",
        "---",
        "",
        f"# 주간 다이제스트 ({today.isoformat()})",
        "",
        f"미검토 뉴스 {len(items)}건 — 관련도순으로 정리했습니다. "
        "이번 주 파고들 이슈는 직접 골라주세요.",
        "",
    ]

    for category in sorted(
        by_category, key=lambda c: -max(i.get("relevance", 0) for i in by_category[c])
    ):
        lines.append(f"## {category}")
        lines.append("")
        for item in sorted(by_category[category], key=lambda i: -i.get("relevance", 0)):
            stars = STARS.get(item.get("relevance", 0), "")
            title = item.get("title", item["_stem"])
            lines.append(f"- {stars} [[{item['_stem']}|{title}]]")
        lines.append("")

    return "\n".join(lines)


def generate_weekly_digest(
    today: date | None = None,
    inbox_dir: Path = NEWS_INBOX_DIR,
    out_dir: Path = WEEKLY_DIGESTS_DIR,
) -> Path | None:
    today = today or date.today()
    since = today - timedelta(days=6)
    items = collect_unread(since, inbox_dir)

    if not items:
        print("[weekly_digest] 지난 7일간 미검토 뉴스가 없어 다이제스트를 생성하지 않습니다.")
        return None

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{today.isoformat()}-주간다이제스트.md"
    path.write_text(build_digest(items, today), encoding="utf-8")
    print(f"[weekly_digest] 생성: {path} ({len(items)}건)")
    return path


if __name__ == "__main__":
    generate_weekly_digest()
