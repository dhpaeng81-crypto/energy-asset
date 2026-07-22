"""분석메모 스캐폴드 생성: 고른 뉴스 항목의 사실관계(제목·요약·백링크)를 미리 채워
화요일 메모 작성의 마찰을 줄인다.

핵심 제약: "나의 분석" 섹션은 항상 빈 채로 생성한다 — 어떤 뉴스를 고를지도,
그 뉴스에 대한 분석도 항상 사용자가 직접 채운다. 이 스크립트는 이미 news-inbox에
있는(이미 AI가 생성한) 요약을 그대로 옮겨 적을 뿐, 새로운 분석을 생성하지 않는다.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml
from slugify import slugify

REPO_ROOT = Path(__file__).resolve().parent.parent
NEWS_INBOX_DIR = REPO_ROOT / "vault" / "news-inbox"
ANALYSIS_MEMOS_DIR = REPO_ROOT / "vault" / "analysis-memos"

MEMO_TEMPLATE = """---
date: {date}
source_news: "[[{news_stem}]]"
status: draft
---

## 원문 요약
{summary}

## 나의 분석
<!-- 이 뉴스에 대한 본인 생각을 여기에 작성하세요 -->
"""


def _read_news_item(stem: str, inbox_dir: Path = NEWS_INBOX_DIR) -> tuple[dict, str]:
    path = inbox_dir / f"{stem}.md"
    if not path.exists():
        raise FileNotFoundError(f"뉴스 항목을 찾을 수 없습니다: {path}")

    text = path.read_text(encoding="utf-8")
    _, frontmatter_raw, body = text.split("---", 2)
    frontmatter = yaml.safe_load(frontmatter_raw) or {}
    return frontmatter, body.strip()


def create_memo_scaffold(
    news_stem: str,
    out_dir: Path = ANALYSIS_MEMOS_DIR,
    inbox_dir: Path = NEWS_INBOX_DIR,
) -> Path:
    frontmatter, summary = _read_news_item(news_stem, inbox_dir)
    title = frontmatter.get("title", news_stem)

    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{date.today().isoformat()}-{slugify(title, allow_unicode=True, max_length=60)}.md"
    path = out_dir / filename
    counter = 2
    while path.exists():
        path = out_dir / filename.replace(".md", f"-{counter}.md")
        counter += 1

    content = MEMO_TEMPLATE.format(
        date=date.today().isoformat(), news_stem=news_stem, summary=summary
    )
    path.write_text(content, encoding="utf-8")
    return path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="선택한 뉴스 항목으로 분석메모 스캐폴드 생성")
    parser.add_argument("news_stem", help="vault/news-inbox 안의 뉴스 파일명(확장자 제외)")
    args = parser.parse_args()

    result_path = create_memo_scaffold(args.news_stem)
    print(f"분석메모 스캐폴드 생성: {result_path}")
