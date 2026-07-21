"""일일 뉴스 파이프라인 진입점: 수집 → 필터 → 요약/분류 → 저장 → 커밋.

GitHub Actions daily_news.yml 워크플로에서 호출된다.
"""
from __future__ import annotations

from gemini_summarize import summarize_all
from git_commit import commit_and_push
from md_writer import write_all
from news_fetch import fetch_all
from news_filter import filter_entries


def main() -> None:
    raw_entries = fetch_all()
    print(f"[run_daily_news] 수집: {len(raw_entries)}건")

    filtered_entries = filter_entries(raw_entries)
    print(f"[run_daily_news] 키워드 필터 통과: {len(filtered_entries)}건")

    if not filtered_entries:
        print("[run_daily_news] 필터를 통과한 항목이 없어 종료합니다.")
        return

    summarized_entries = summarize_all(filtered_entries)
    written_paths = write_all(summarized_entries)
    print(f"[run_daily_news] 저장: {len(written_paths)}건")

    commit_and_push(written_paths)


if __name__ == "__main__":
    main()
