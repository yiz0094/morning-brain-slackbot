"""
요일별 운동 선택 로직.

규칙:
- 월~금: WEEKDAY_POOL에서 순환
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


def pick_today_exercise(
    today: date, last_pool_index: int
) -> tuple[str | None, int | None]:
    """
    오늘의 운동 타입을 결정한다.

    Returns:
        (exercise_type, new_pool_index)
        - 토/일: (None, None)
        - 월~금: (WEEKDAY_POOL[next_idx], next_idx)
    """
    if today.weekday() >= 5:
        return None, None
    next_idx = (last_pool_index + 1) % len(WEEKDAY_POOL)
    return WEEKDAY_POOL[next_idx], next_idx
