"""텍스트 정리 공통 유틸.

일부 RSS 피드는 제목/요약에 HTML 태그(<span>, <br /> 등)를 그대로 흘려보낸다.
news_fetch.py, google_news_fallback.py에서 공통으로 사용한다.
"""
from __future__ import annotations

import html
import re

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def strip_html(text: str) -> str:
    """HTML 태그를 제거하고 엔티티(&amp; 등)를 원래 문자로 복원한다.

    태그를 빈 문자열이 아닌 공백으로 치환해 <br/>, </span> 등으로 붙어 있던
    단어들이 그대로 이어 붙지 않게 한다.
    """
    no_tags = _TAG_RE.sub(" ", text)
    return _WHITESPACE_RE.sub(" ", html.unescape(no_tags)).strip()
