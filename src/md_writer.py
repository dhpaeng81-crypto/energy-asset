"""news-inbox에 frontmatter가 포함된 markdown 파일을 생성한다."""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

from slugify import slugify

REPO_ROOT = Path(__file__).resolve().parent.parent
NEWS_INBOX_DIR = REPO_ROOT / "vault" / "news-inbox"

FRONTMATTER_TEMPLATE = """---
date: {date}
title: "{title}"
source_url: {source_url}
category: {category}
relevance: {relevance}
status: unread
---

{summary}
"""


def _escape_title(title: str) -> str:
    return title.replace('"', '\\"')


def build_filename(entry_date: str, title: str) -> str:
    slug = slugify(title, allow_unicode=True, max_length=60)
    return f"{entry_date}-{slug}.md"


def write_news_item(entry: dict[str, Any], out_dir: Path = NEWS_INBOX_DIR) -> Path:
    """뉴스 항목 하나를 news-inbox에 markdown 파일로 저장하고 경로를 반환한다.

    동일 파일명이 이미 존재하면 -2, -3 ... 접미사를 붙여 덮어쓰지 않는다.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    entry_date = entry.get("published_date") or date.today().isoformat()
    entry_date = entry_date[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", entry_date) else date.today().isoformat()

    filename = build_filename(entry_date, entry["title"])
    path = out_dir / filename
    counter = 2
    while path.exists():
        path = out_dir / filename.replace(".md", f"-{counter}.md")
        counter += 1

    content = FRONTMATTER_TEMPLATE.format(
        date=entry_date,
        title=_escape_title(entry["title"]),
        source_url=entry.get("link", ""),
        category=entry["category"],
        relevance=entry["relevance"],
        summary=entry["summary"],
    )
    path.write_text(content, encoding="utf-8")
    return path


def write_all(entries: list[dict[str, Any]], out_dir: Path = NEWS_INBOX_DIR) -> list[Path]:
    return [write_news_item(entry, out_dir) for entry in entries]
