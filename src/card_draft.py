"""분석메모(화요일 텍스트)를 지식카드 초안으로 변환한다.

핵심 제약조건: "나의 판단", "판단이 틀릴 조건" 섹션은 AI가 절대 생성하지 않는다.
Gemini에게는 애초에 이 두 섹션에 대한 프롬프트를 주지 않고, 응답 스키마에도
해당 필드를 두지 않는다. 그리고 최종 마크다운 조립 시 이 두 섹션은 항상
코드가 직접 빈 헤더로 삽입한다 (AI 출력 경로와 완전히 분리) — 이것이
이중 방어선이다.
"""
from __future__ import annotations

import json
import os
import re
from datetime import date
from pathlib import Path
from typing import Any

import google.generativeai as genai
from slugify import slugify

REPO_ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_CARDS_DIR = REPO_ROOT / "vault" / "knowledge-cards"

MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# 이 프롬프트는 "핵심 사실 / 정책 방향 / 이해관계자 / 향후 변수" 네 항목만 요청한다.
# "나의 판단"이나 "판단이 틀릴 조건"에 해당하는 내용은 요청하지도, 응답 스키마에
# 포함하지도 않는다 — 사용자 판단 영역은 파이프라인에 존재하지 않는다.
SYSTEM_PROMPT = """당신은 에너지·전력시장 전문성 자산화를 돕는 리서치 보조원입니다.
사용자가 작성한 분석메모를 바탕으로 지식카드 초안의 사실관계 섹션만 작성하세요.

작성할 항목은 다음 네 가지뿐입니다:
1. facts: 핵심 사실 (객관적 사실관계 정리)
2. policy_direction: 정책 방향
3. stakeholders: 이해관계자 / 수혜자 / 피해자
4. future_variables: 향후 변수

중요: 이 카드에는 "나의 판단"이나 "판단이 틀릴 조건"에 해당하는 의견, 예측,
평가, 전망을 절대 포함하지 마세요. 그것은 항상 사용자 본인만 작성하는 영역이며
당신의 응답 대상이 아닙니다. 오직 객관적으로 확인 가능한 사실과 구조만 정리하세요.

반드시 다음 JSON 형식으로만 응답하세요. 다른 텍스트를 포함하지 마세요:
{"facts": "...", "policy_direction": "...", "stakeholders": "...", "future_variables": "..."}
"""

# 사용자 판단 섹션은 파이프라인 어디에서도 채워지지 않는다 — 항상 이 상수로 고정된다.
JUDGMENT_FOOTER = """
## 나의 판단
<!-- 항상 공란으로 생성. 사용자 전용 -->

## 판단이 틀릴 조건
<!-- 항상 공란으로 생성. 사용자 전용 -->
"""

CARD_TEMPLATE = """---
title: "{title}"
created: {created}
status: draft
evidence_type:
review_date:
source_news: "[[{source_news}]]"
---

## 핵심 사실
{facts}

## 정책 방향
{policy_direction}

## 이해관계자 / 수혜자 / 피해자
{stakeholders}

## 향후 변수
{future_variables}
""" + JUDGMENT_FOOTER


def _strip_judgment_leakage(text: str) -> str:
    """AI 출력에 '나의 판단' 계열 헤더가 실수로 섞여 들어온 경우를 대비한 방어 로직.

    해당 헤더 이후 내용은 모두 잘라낸다. 정상 상황에서는 아무 효과가 없어야 한다.
    """
    pattern = re.compile(r"#{1,6}\s*(나의\s*판단|판단이\s*틀릴\s*조건)")
    match = pattern.search(text)
    if match:
        return text[: match.start()].rstrip()
    return text


def _build_model() -> genai.GenerativeModel:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    return genai.GenerativeModel(MODEL, system_instruction=SYSTEM_PROMPT)


def generate_draft_sections(
    memo_text: str, model: genai.GenerativeModel | None = None
) -> dict[str, str]:
    model = model or _build_model()

    response = model.generate_content(
        memo_text,
        generation_config={"response_mime_type": "application/json"},
    )

    result = json.loads(response.text)

    # 스키마에 없는 판단 관련 키가 섞여 오더라도 아래 4개 필드만 사용한다.
    return {
        "facts": _strip_judgment_leakage(result.get("facts", "").strip()),
        "policy_direction": _strip_judgment_leakage(result.get("policy_direction", "").strip()),
        "stakeholders": _strip_judgment_leakage(result.get("stakeholders", "").strip()),
        "future_variables": _strip_judgment_leakage(result.get("future_variables", "").strip()),
    }


def write_knowledge_card(
    title: str,
    memo_text: str,
    source_news_stem: str,
    out_dir: Path = KNOWLEDGE_CARDS_DIR,
    model: genai.GenerativeModel | None = None,
) -> Path:
    """지식카드 초안을 생성해 vault/knowledge-cards에 저장하고 경로를 반환한다.

    title: 카드 제목
    memo_text: 화요일 분석메모 원문
    source_news_stem: 원본 뉴스 파일명(확장자 제외) — [[백링크]]로 연결됨
    """
    sections = generate_draft_sections(memo_text, model)

    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{slugify(title, allow_unicode=True, max_length=60)}.md"
    path = out_dir / filename
    counter = 2
    while path.exists():
        path = out_dir / filename.replace(".md", f"-{counter}.md")
        counter += 1

    content = CARD_TEMPLATE.format(
        title=title.replace('"', '\\"'),
        created=date.today().isoformat(),
        source_news=source_news_stem,
        **sections,
    )
    path.write_text(content, encoding="utf-8")
    return path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="분석메모를 지식카드 초안으로 변환")
    parser.add_argument("memo_path", help="분석메모 텍스트 파일 경로")
    parser.add_argument("--title", required=True, help="카드 제목")
    parser.add_argument("--source-news", required=True, help="원본 뉴스 파일명(확장자 제외)")
    args = parser.parse_args()

    memo = Path(args.memo_path).read_text(encoding="utf-8")
    result_path = write_knowledge_card(args.title, memo, args.source_news)
    print(f"카드 초안 생성: {result_path}")
