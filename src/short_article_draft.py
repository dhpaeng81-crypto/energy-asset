"""뉴스인박스 기사를 short article(기사요약+의견 종합) 초안으로 변환한다.

핵심 제약조건: "나의 의견", "이 판단이 틀릴 조건" 섹션은 AI가 절대 생성하지 않는다.
사용자가 참고용으로 남긴 의견 메모(opinion_context)는 Gemini에게 요약이 다룰 초점을
잡는 참고자료로만 제공될 뿐, 그 내용이 그대로든 재구성되든 결과물의 "나의 의견"
섹션에 들어가지 않는다 — 응답 스키마에 opinion 필드 자체가 없다. 최종 마크다운
조립 시 "나의 의견"/"이 판단이 틀릴 조건"은 항상 코드가 직접 빈 헤더로 삽입한다
(card_draft.py와 동일한 이중 방어).

원문 인용 금지: "요약"은 뉴스인박스에 이미 있는 2줄 요약을 자기 언어로 다시
재구성한 것이어야 하며, 그 문장을 그대로 베끼면 안 된다.
"""
from __future__ import annotations

import json
import os
import re
from datetime import date
from pathlib import Path
from typing import Any

import google.generativeai as genai
import yaml
from slugify import slugify

from gemini_utils import call_with_retry

REPO_ROOT = Path(__file__).resolve().parent.parent
NEWS_INBOX_DIR = REPO_ROOT / "vault" / "news-inbox"
SHORT_ARTICLES_DIR = REPO_ROOT / "vault" / "short-articles"

MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# 이 프롬프트는 "요약" 한 항목만 요청한다. "나의 의견"이나 "이 판단이 틀릴 조건"에
# 해당하는 내용은 요청하지도, 응답 스키마에 포함하지도 않는다.
SYSTEM_PROMPT = """당신은 에너지·전력시장 뉴스레터의 리서치 보조원입니다.
주어진 뉴스 기사에 대한 짧은 아티클의 "요약" 섹션만 작성하세요.

요구사항:
- 기사의 핵심 사실을 완전히 자기 언어로 재구성하세요. 주어진 원문 요약 문장을
  그대로 옮기거나 표현만 살짝 바꾸지 마세요.
- 참고로 사용자가 이 기사에 대해 쓰려는 의견의 방향이 함께 주어질 수 있습니다.
  이는 요약이 어떤 사실관계에 초점을 맞출지 참고하는 용도일 뿐입니다 — 그 의견
  자체를 서술하거나 요약, 평가, 전망하지 마세요.

중요: 이 아티클에는 "나의 의견"이나 "이 판단이 틀릴 조건"에 해당하는 의견, 예측,
평가, 전망을 절대 포함하지 마세요. 그것은 항상 사용자 본인만 작성하는 영역이며
당신의 응답 대상이 아닙니다.

반드시 다음 JSON 형식으로만 응답하세요. 다른 텍스트를 포함하지 마세요:
{"summary": "..."}
"""

# 사용자 의견/판단 섹션은 파이프라인 어디에서도 채워지지 않는다 — 항상 이 상수로 고정된다.
JUDGMENT_FOOTER = """
## 나의 의견
<!-- 항상 공란으로 생성. 사용자가 직접 작성 -->

## 이 판단이 틀릴 조건
<!-- 항상 공란으로 생성. 사용자가 직접 작성 -->
"""

ARTICLE_TEMPLATE = """---
title: "{title}"
created: {created}
status: draft
source_news: "[[{source_news}]]"
source_card: {source_card}
publish_channel:
publish_date:
opinion_ratio_check: false
---

## 요약 (AI 초안)
{summary}
""" + JUDGMENT_FOOTER


def _strip_judgment_leakage(text: str) -> str:
    """AI 출력에 '나의 의견' 계열 헤더가 실수로 섞여 들어온 경우를 대비한 방어 로직.

    해당 헤더 이후 내용은 모두 잘라낸다. 정상 상황에서는 아무 효과가 없어야 한다.
    """
    pattern = re.compile(r"#{1,6}\s*(나의\s*의견|판단이\s*틀릴\s*조건)")
    match = pattern.search(text)
    if match:
        return text[: match.start()].rstrip()
    return text


def _build_model() -> genai.GenerativeModel:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    return genai.GenerativeModel(MODEL, system_instruction=SYSTEM_PROMPT)


def _read_news_item(stem: str, inbox_dir: Path = NEWS_INBOX_DIR) -> tuple[dict[str, Any], str]:
    path = inbox_dir / f"{stem}.md"
    if not path.exists():
        raise FileNotFoundError(f"뉴스 항목을 찾을 수 없습니다: {path}")

    text = path.read_text(encoding="utf-8")
    _, frontmatter_raw, body = text.split("---", 2)
    frontmatter = yaml.safe_load(frontmatter_raw) or {}
    return frontmatter, body.strip()


def generate_summary(
    news_summary: str,
    opinion_context: str,
    model: genai.GenerativeModel | None = None,
) -> str:
    model = model or _build_model()

    user_content = f"뉴스 원문 요약:\n{news_summary}"
    if opinion_context:
        user_content += (
            "\n\n(참고용 — 요약에 그대로 포함하지 말 것) "
            f"사용자가 준비 중인 의견의 방향:\n{opinion_context}"
        )

    response = call_with_retry(
        model.generate_content,
        user_content,
        generation_config={"response_mime_type": "application/json"},
    )
    result = json.loads(response.text)
    return _strip_judgment_leakage(result.get("summary", "").strip())


def write_short_article(
    news_stem: str,
    title: str,
    opinion_context: str = "",
    source_card: str | None = None,
    out_dir: Path = SHORT_ARTICLES_DIR,
    inbox_dir: Path = NEWS_INBOX_DIR,
    model: genai.GenerativeModel | None = None,
) -> Path:
    """short article 초안을 생성해 vault/short-articles에 저장하고 경로를 반환한다.

    news_stem: 원본 뉴스 파일명(확장자 제외) — [[백링크]]로 연결됨
    title: 아티클 제목
    opinion_context: 사용자가 준비 중인 의견 메모(참고용, 결과물에는 들어가지 않음)
    source_card: 연관 지식카드 파일명(확장자 제외, 있으면 [[백링크]]로 연결)
    """
    frontmatter, news_body = _read_news_item(news_stem, inbox_dir)
    news_summary = news_body or str(frontmatter.get("title", ""))

    summary = generate_summary(news_summary, opinion_context, model)

    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{slugify(title, allow_unicode=True, max_length=60)}.md"
    path = out_dir / filename
    counter = 2
    while path.exists():
        path = out_dir / filename.replace(".md", f"-{counter}.md")
        counter += 1

    content = ARTICLE_TEMPLATE.format(
        title=title.replace('"', '\\"'),
        created=date.today().isoformat(),
        source_news=news_stem,
        source_card=f'"[[{source_card}]]"' if source_card else "",
        summary=summary,
    )
    path.write_text(content, encoding="utf-8")
    return path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="뉴스 항목을 short article 초안으로 변환")
    parser.add_argument("news_stem", help="vault/news-inbox 안의 뉴스 파일명(확장자 제외)")
    parser.add_argument("--title", required=True, help="아티클 제목")
    parser.add_argument(
        "--opinion-file",
        help="참고용 의견 메모 텍스트 파일 (요약 방향 참고용, 결과물에는 들어가지 않음)",
    )
    parser.add_argument("--source-card", help="연관 지식카드 파일명(확장자 제외, 있으면)")
    args = parser.parse_args()

    opinion_context = ""
    if args.opinion_file:
        opinion_context = Path(args.opinion_file).read_text(encoding="utf-8")

    result_path = write_short_article(
        args.news_stem, args.title, opinion_context, args.source_card
    )
    print(f"short article 초안 생성: {result_path}")
