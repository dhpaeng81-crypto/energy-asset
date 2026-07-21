"""Gemini API로 뉴스 항목을 요약/분류하고 관련도 점수를 매긴다.

news_filter.py가 키워드로 1차 분류한 카테고리를 Gemini가 재검토/확정하고,
2줄 요약과 1~5점의 관련도 점수를 생성한다.
"""
from __future__ import annotations

import json
import os
from typing import Any

import google.generativeai as genai

from gemini_utils import call_with_retry

MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

CATEGORIES = ["전력시장", "LNG·가스", "에너지전환정책"]

SYSTEM_PROMPT = """당신은 에너지·전력시장 전문 애널리스트의 리서치 보조원입니다.
주어진 뉴스 항목에 대해 다음을 생성하세요:
1. summary: 핵심 내용을 담은 정확히 2줄 요약 (한국어, 평서체)
2. category: 다음 중 하나 — 전력시장 / LNG·가스 / 에너지전환정책
3. relevance: 에너지·전력시장 전문성 자산화 관점에서의 관련도, 1(낮음)~5(높음) 정수

반드시 다음 JSON 형식으로만 응답하세요. 다른 텍스트를 포함하지 마세요:
{"summary": "...", "category": "...", "relevance": 3}
"""


def _build_model() -> genai.GenerativeModel:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    return genai.GenerativeModel(MODEL, system_instruction=SYSTEM_PROMPT)


def summarize(entry: dict[str, Any], model: genai.GenerativeModel | None = None) -> dict[str, Any]:
    model = model or _build_model()

    user_content = (
        f"제목: {entry.get('title', '')}\n"
        f"출처: {entry.get('source', '')}\n"
        f"1차 분류(키워드 기반): {entry.get('category', '미분류')}\n"
        f"본문/요약: {entry.get('summary', '')}"
    )

    response = call_with_retry(
        model.generate_content,
        user_content,
        generation_config={"response_mime_type": "application/json"},
    )

    result = json.loads(response.text)

    category = result.get("category")
    if category not in CATEGORIES:
        category = entry.get("category", CATEGORIES[0])

    relevance = int(result.get("relevance", 3))
    relevance = max(1, min(5, relevance))

    return {
        **entry,
        "summary": result.get("summary", "").strip(),
        "category": category,
        "relevance": relevance,
    }


def summarize_all(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    model = _build_model()
    return [summarize(entry, model) for entry in entries]
