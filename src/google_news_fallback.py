"""
google_news_fallback.py
------------------------
Reuters와 Bloomberg는 공식 공개 RSS를 제공하지 않는다(Reuters는 2020년경 서비스
종료, Bloomberg는 애초에 일반 공개 RSS 없음). 대안으로 Google News의 검색 결과
RSS(news.google.com/rss/search)를 site: 연산자와 함께 사용해 특정 매체의 기사를
간접적으로 수집한다.

이 방식의 한계와 리스크 (반드시 인지할 것):
1. 비공식 우회이며 Google이 언제든 URL 패턴/정책을 바꾸면 깨질 수 있다.
   프로덕션 파이프라인에 넣기 전 로컬에서 curl로 반드시 재확인할 것:
     curl -sI "https://news.google.com/rss/search?q=site:reuters.com+energy&hl=en-US&gl=US&ceid=US:en"
2. Google News RSS의 <link>는 대부분 Google 리다이렉트 URL이다
   (news.google.com/rss/articles/... 형태). 실제 매체 원문 URL을 얻으려면
   redirect를 따라가거나 <source url="..."> 속성을 파싱해야 하는데, 완전한
   원문 URL이 항상 나오는 것은 아니다. 아래 resolve_original_url()은 리다이렉트를
   따라가는 best-effort 구현이며, 실패 시 Google News 링크 그대로 저장한다.
3. 저작권: Reuters/Bloomberg 기사 본문을 스크래핑해서 재게시하는 것은 저작권
   위반이다. 이 스크립트는 제목·요약·링크만 수집하는 용도로 제한할 것. 본문은
   절대 긁지 말고, 카드/콘텐츠 작성 시에도 반드시 자기 언어로 paraphrase할 것.
4. 이 우회가 불안정하다고 느껴지면 Reuters Connect, Bloomberg API 같은
   공식 유료 구독으로 전환을 검토할 것 (설계 검토 시 이미 안내한 내용).

설치: pip install feedparser requests
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import feedparser
import requests
import yaml

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("google_news_fallback")

REPO_ROOT = Path(__file__).resolve().parent.parent
GOOGLE_NEWS_SOURCES_PATH = REPO_ROOT / "config" / "google_news_sources.yaml"

REQUEST_DELAY_SECONDS = 3


def load_source_queries(path: Path = GOOGLE_NEWS_SOURCES_PATH) -> dict[str, str]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return {item["name"]: item["query"] for item in data.get("sources", [])}


def build_google_news_rss_url(query: str, when: str = "1d") -> str:
    """
    when 파라미터(when:1d, when:7d 등)는 Google News 검색 문법으로,
    최근 N일 이내 기사로 제한한다. 매일 실행하는 파이프라인이면 when:1d 권장.
    """
    full_query = f"{query} when:{when}"
    encoded = quote_plus(full_query)
    return f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"


def resolve_original_url(google_news_url: str, timeout: int = 8) -> str:
    """
    Google News 리다이렉트 URL을 따라가 실제 매체 원문 URL을 얻어본다.
    실패하면 원래 URL을 그대로 반환한다 (파이프라인이 죽지 않도록).
    """
    try:
        resp = requests.get(
            google_news_url,
            timeout=timeout,
            allow_redirects=True,
            headers={"User-Agent": "energy-asset-agent/0.1 (personal research bot)"},
        )
        return resp.url
    except requests.RequestException as e:
        logger.warning("리다이렉트 해석 실패, 원본 링크 유지: %s (%s)", google_news_url, e)
        return google_news_url


def fetch_source_via_google_news(
    source_name: str, query: str, when: str = "1d"
) -> list[dict[str, Any]]:
    rss_url = build_google_news_rss_url(query, when=when)
    logger.info("[%s] Google News RSS 조회: %s", source_name, rss_url)

    feed = feedparser.parse(rss_url)
    if feed.bozo:
        logger.error("[%s] 피드 파싱 오류: %s", source_name, feed.bozo_exception)
        return []

    items = []
    for entry in feed.entries:
        google_link = entry.get("link", "")
        resolved_url = resolve_original_url(google_link) if google_link else ""
        time.sleep(0.5)  # 리다이렉트 해석 요청 간 짧은 대기

        items.append(
            {
                "source": source_name,
                "title": entry.get("title", "").strip(),
                "google_news_url": google_link,
                "resolved_url": resolved_url,
                "published": entry.get("published", ""),
                # summary는 Google이 재구성한 스니펫. 원문 그대로 저장하지 말고
                # 카드/콘텐츠 작성 단계에서 반드시 paraphrase 해서 사용할 것.
                "summary_snippet": entry.get("summary", "")[:300],
            }
        )

    logger.info("[%s] %d건 수집", source_name, len(items))
    return items


def fetch_all_sources(
    when: str = "1d", path: Path = GOOGLE_NEWS_SOURCES_PATH
) -> dict[str, list[dict[str, Any]]]:
    results = {}
    for source_name, query in load_source_queries(path).items():
        results[source_name] = fetch_source_via_google_news(source_name, query, when=when)
        time.sleep(REQUEST_DELAY_SECONDS)
    return results


def fetch_all(when: str = "1d", path: Path = GOOGLE_NEWS_SOURCES_PATH) -> list[dict[str, Any]]:
    """news_fetch.fetch_all()과 동일한 스키마(title/link/summary/published/source)로
    평탄화해 반환한다 — news_filter.py/gemini_summarize.py에 그대로 흘려보내기 위함."""
    flattened = []
    for items in fetch_all_sources(when=when, path=path).values():
        for item in items:
            flattened.append(
                {
                    "title": item["title"],
                    "link": item["resolved_url"] or item["google_news_url"],
                    "summary": item["summary_snippet"],
                    "published": item["published"],
                    "source": item["source"],
                }
            )
    return flattened


if __name__ == "__main__":
    all_results = fetch_all_sources(when="1d")
    for source_name, items in all_results.items():
        print(f"\n=== {source_name} ({len(items)}건) ===")
        for item in items[:5]:
            print("-", item["title"])
            print("  ", item["resolved_url"])
