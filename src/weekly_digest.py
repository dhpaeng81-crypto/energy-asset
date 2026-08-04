"""주간 다이제스트 생성: news-inbox의 미검토(unread) 뉴스를 관련도순으로 정리해
월요일 검토를 돕는다.

핵심 제약: 이번 주에 무엇을 파고들지 "고르는 것"은 항상 사용자 몫이다. 이 스크립트는
정렬/집계/중복제거/관련도 컷오프만 하고 "이걸 읽으세요" 식의 선택은 하지 않는다 —
다이제스트에는 순위와 링크만 있을 뿐, 개별 이슈를 추천하는 문구는 넣지 않는다.
"""
from __future__ import annotations

import html
import os
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
NEWS_INBOX_DIR = REPO_ROOT / "vault" / "news-inbox"
WEEKLY_DIGESTS_DIR = REPO_ROOT / "vault" / "weekly-digests"

STARS = {1: "★", 2: "★★", 3: "★★★", 4: "★★★★", 5: "★★★★★"}

# 관련도 낮은 기사와 (같은 기사가 RSS+Google News 등 여러 경로로 중복 수집된) 반복 항목이
# 다이제스트를 읽기 힘들 만큼 늘려서, 컷오프와 중복 제거를 기본으로 적용한다.
MIN_RELEVANCE = int(os.environ.get("DIGEST_MIN_RELEVANCE", "4"))
MAX_PER_CATEGORY = int(os.environ.get("DIGEST_MAX_PER_CATEGORY", "15"))


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


def _dedupe_by_title(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """제목이 같은 기사(RSS+Google News 중복 수집 등)는 먼저 나온 것만 남긴다."""
    seen: set[str] = set()
    unique = []
    for item in items:
        key = str(item.get("title", "")).strip().lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def collect_unread(
    since: date,
    inbox_dir: Path = NEWS_INBOX_DIR,
    min_relevance: int = MIN_RELEVANCE,
) -> list[dict[str, Any]]:
    candidates = []
    for path in inbox_dir.glob("*.md"):
        frontmatter = _parse_frontmatter(path)
        if not frontmatter or frontmatter.get("status") != "unread":
            continue
        item_date = _as_date(frontmatter.get("date"))
        if item_date is None or item_date < since:
            continue
        candidates.append(frontmatter)

    unique = _dedupe_by_title(candidates)
    return [item for item in unique if item.get("relevance", 0) >= min_relevance]


def _render_item(item: dict[str, Any]) -> str:
    title = html.escape(str(item.get("title", item["_stem"])))
    url = html.escape(str(item.get("source_url", "")))
    stars = STARS.get(item.get("relevance", 0), "")
    category = html.escape(str(item.get("category", "미분류")))
    link = f'<a href="{url}">{title}</a>' if url else title
    return f'<li><span class="stars">{stars}</span> {link} <span class="category">{category}</span></li>'


def build_digest_html(items: list[dict[str, Any]], today: date) -> str:
    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        by_category[item.get("category", "미분류")].append(item)

    sections = []
    for category in sorted(
        by_category, key=lambda c: -max(i.get("relevance", 0) for i in by_category[c])
    ):
        sorted_items = sorted(by_category[category], key=lambda i: -i.get("relevance", 0))
        shown = sorted_items[:MAX_PER_CATEGORY]
        omitted = len(sorted_items) - len(shown)

        items_html = "\n".join(_render_item(item) for item in shown)
        note = (
            f'<p class="omitted">관련도 상위 {MAX_PER_CATEGORY}건만 표시 — {omitted}건 생략</p>'
            if omitted > 0
            else ""
        )
        sections.append(
            f"<section><h2>{html.escape(category)} "
            f'<span class="count">({len(shown)}/{len(sorted_items)})</span></h2>'
            f"<ul>{items_html}</ul>{note}</section>"
        )

    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>주간 다이제스트 ({today.isoformat()})</title>
<style>
  body {{ font-family: -apple-system, "Noto Sans KR", sans-serif; max-width: 720px;
          margin: 40px auto; padding: 0 16px; line-height: 1.6; color: #222; }}
  h1 {{ font-size: 1.4rem; }}
  h2 {{ font-size: 1.1rem; border-bottom: 1px solid #ddd; padding-bottom: 4px; margin-top: 32px; }}
  .count {{ color: #999; font-weight: normal; font-size: 0.85rem; }}
  ul {{ list-style: none; padding-left: 0; }}
  li {{ margin: 10px 0; }}
  .stars {{ color: #d9a441; margin-right: 8px; }}
  .category {{ color: #888; font-size: 0.85rem; margin-left: 8px; }}
  a {{ color: #1a5fb4; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .meta {{ color: #666; font-size: 0.9rem; }}
  .omitted {{ color: #999; font-size: 0.85rem; font-style: italic; }}
</style>
</head>
<body>
<h1>주간 다이제스트 ({today.isoformat()})</h1>
<p class="meta">관련도 {MIN_RELEVANCE}점 이상(중복 제거 완료) {len(items)}건 — 카테고리별 관련도순으로
정리했습니다. 이번 주 파고들 이슈는 직접 골라주세요.</p>
{"".join(sections)}
</body>
</html>
"""


def generate_weekly_digest(
    today: date | None = None,
    inbox_dir: Path = NEWS_INBOX_DIR,
    out_dir: Path = WEEKLY_DIGESTS_DIR,
) -> Path | None:
    today = today or date.today()
    since = today - timedelta(days=6)
    items = collect_unread(since, inbox_dir)

    if not items:
        print("[weekly_digest] 지난 7일간 조건(관련도/중복 제거)을 만족하는 뉴스가 없어 다이제스트를 생성하지 않습니다.")
        return None

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{today.isoformat()}-주간다이제스트.html"
    path.write_text(build_digest_html(items, today), encoding="utf-8")
    print(f"[weekly_digest] 생성: {path} ({len(items)}건)")
    return path


if __name__ == "__main__":
    generate_weekly_digest()
