"""키워드 기반 1차 필터링.

config/keywords.yaml 의 카테고리별 키워드 중 하나라도 제목 또는 요약에
포함된 뉴스만 통과시키고, 매칭된 카테고리를 부여한다.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
KEYWORDS_PATH = REPO_ROOT / "config" / "keywords.yaml"


def load_categories(path: Path = KEYWORDS_PATH) -> dict[str, list[str]]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("categories", {})


def match_category(text: str, categories: dict[str, list[str]]) -> str | None:
    for category, keywords in categories.items():
        if any(keyword in text for keyword in keywords):
            return category
    return None


def filter_entries(
    entries: list[dict[str, Any]], path: Path = KEYWORDS_PATH
) -> list[dict[str, Any]]:
    categories = load_categories(path)
    filtered = []
    for entry in entries:
        haystack = f"{entry.get('title', '')} {entry.get('summary', '')}"
        category = match_category(haystack, categories)
        if category is None:
            continue
        filtered.append({**entry, "category": category})
    return filtered


if __name__ == "__main__":
    from news_fetch import fetch_all

    for item in filter_entries(fetch_all()):
        print(f"[{item['category']}] {item['title']}")
