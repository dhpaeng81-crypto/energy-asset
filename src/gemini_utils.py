"""Gemini API 공통 유틸: 무료 티어 rate limit(429 RESOURCE_EXHAUSTED) 대응.

무료 티어는 모델당 분당 요청 수(RPM)가 낮아(예: gemini-2.5-flash 5RPM), 여러 건을
연속 호출하면 곧바로 쿼터를 초과한다. 호출 간 최소 간격을 두고, 쿼터 초과 시
서버가 알려주는 대기시간만큼 기다렸다가 재시도한다.
"""
from __future__ import annotations

import os
import re
import time
from typing import Any, Callable, TypeVar

from google.api_core.exceptions import ResourceExhausted

T = TypeVar("T")

MAX_RETRIES = 5
DEFAULT_RETRY_DELAY_SECONDS = 30.0

REQUESTS_PER_MINUTE = float(os.environ.get("GEMINI_REQUESTS_PER_MINUTE", "4"))
MIN_CALL_INTERVAL_SECONDS = 60.0 / REQUESTS_PER_MINUTE

_last_call_at: float | None = None


def _extract_retry_delay(exc: Exception) -> float | None:
    match = re.search(r"retry_delay\s*\{\s*seconds:\s*(\d+)", str(exc))
    if match:
        return float(match.group(1))
    match = re.search(r"[Rr]etry in ([\d.]+)s", str(exc))
    if match:
        return float(match.group(1))
    return None


def throttle() -> None:
    """직전 호출로부터 최소 간격이 지나지 않았으면 대기한다."""
    global _last_call_at
    if _last_call_at is not None:
        elapsed = time.monotonic() - _last_call_at
        wait = MIN_CALL_INTERVAL_SECONDS - elapsed
        if wait > 0:
            time.sleep(wait)
    _last_call_at = time.monotonic()


def call_with_retry(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """호출 간 간격을 두고, 429 발생 시 서버가 안내한 대기시간만큼 기다렸다가 재시도한다."""
    attempt = 0
    while True:
        throttle()
        try:
            return fn(*args, **kwargs)
        except ResourceExhausted as exc:
            attempt += 1
            if attempt >= MAX_RETRIES:
                raise
            delay = _extract_retry_delay(exc) or DEFAULT_RETRY_DELAY_SECONDS
            print(f"[gemini] 쿼터 초과 — {delay:.0f}초 대기 후 재시도 ({attempt}/{MAX_RETRIES})")
            time.sleep(delay)
