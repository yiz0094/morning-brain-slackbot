"""
요일별 운동 선택 로직.

규칙:
- 월~목: WEEKDAY_POOL에서 순환 (4일 단위로 다음 인덱스)
- 금: 항상 WEEKLY_REVIEW 고정 (풀 인덱스 갱신 안 함)
- 토/일: None 반환 (스케줄러 트리거 자체 안 함)
"""
from __future__ import annotations

from datetime import date

WEEKDAY_POOL = [
    "mental_math",
    "logic_deduction",
    "memory",
    "pattern_visual",
    "verbal_fluency",
    "free_writing",
]

WEEKLY_REVIEW = "weekly_review"


def pick_today_exercise(
    today: date, last_pool_index: int
) -> tuple[str | None, int | None]:
    """
    오늘의 운동 타입을 결정한다.

    Args:
        today: 오늘 날짜
        last_pool_index: SQLite에 저장된 마지막 풀 인덱스 (없으면 -1)

    Returns:
        (exercise_type, new_pool_index)
        - 토/일: (None, None) — 트리거 X
        - 금:   (WEEKLY_REVIEW, None) — 인덱스 갱신 X
        - 월~목: (WEEKDAY_POOL[next_idx], next_idx) — 호출자가 인덱스 저장
    """
    weekday = today.weekday()  # 0=월 ... 4=금, 5=토, 6=일

    if weekday >= 5:
        return None, None

    if weekday == 4:
        return WEEKLY_REVIEW, None

    next_idx = (last_pool_index + 1) % len(WEEKDAY_POOL)
    return WEEKDAY_POOL[next_idx], next_idx
