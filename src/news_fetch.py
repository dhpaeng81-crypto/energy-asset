"""RSS 피드에서 뉴스 항목을 수집한다.

config/rss_sources.yaml 에 정의된 각 피드를 읽어 표준화된 dict 목록으로 반환한다.
개별 피드가 실패해도 나머지 피드 수집은 계속 진행한다.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import feedparser
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
RSS_SOURCES_PATH = REPO_ROOT / "config" / "rss_sources.yaml"


def load_sources(path: Path = RSS_SOURCES_PATH) -> list[dict[str, str]]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("sources", [])


def fetch_source(source: dict[str, str]) -> list[dict[str, Any]]:
    """단일 RSS 소스에서 항목을 가져온다. 실패 시 빈 목록을 반환하고 stderr에 경고를 남긴다."""
    parsed = feedparser.parse(source["url"])
    if parsed.bozo and not parsed.entries:
        print(f"[news_fetch] 경고: '{source['name']}' 피드 파싱 실패: {parsed.bozo_exception}", file=sys.stderr)
        return []

    entries = []
    for entry in parsed.entries:
        entries.append(
            {
                "title": entry.get("title", "").strip(),
                "link": entry.get("link", "").strip(),
                "summary": entry.get("summary", entry.get("description", "")).strip(),
                "published": entry.get("published", entry.get("updated", "")),
                "source": source["name"],
            }
        )
    return entries


def fetch_all(path: Path = RSS_SOURCES_PATH) -> list[dict[str, Any]]:
    all_entries: list[dict[str, Any]] = []
    for source in load_sources(path):
        all_entries.extend(fetch_source(source))
    return all_entries


if __name__ == "__main__":
    for item in fetch_all():
        print(f"[{item['source']}] {item['title']} — {item['link']}")
