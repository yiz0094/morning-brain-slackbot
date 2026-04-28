"""rotation.pick_today_exercise() 테스트."""
from datetime import date, timedelta

from app.rotation import (
    WEEKDAY_POOL,
    WEEKLY_REVIEW,
    pick_today_exercise,
)


# 2026-04~05 달력 참조
#   2026-04-27 월
#   2026-04-28 화
#   2026-04-29 수
#   2026-04-30 목
#   2026-05-01 금
#   2026-05-02 토
#   2026-05-03 일


class TestWeekendSkipped:
    def test_saturday_returns_none(self):
        assert pick_today_exercise(date(2026, 5, 2), last_pool_index=-1) == (None, None)

    def test_sunday_returns_none(self):
        assert pick_today_exercise(date(2026, 5, 3), last_pool_index=2) == (None, None)


class TestFridayFixed:
    def test_friday_returns_weekly_review(self):
        result, new_idx = pick_today_exercise(date(2026, 5, 1), last_pool_index=2)
        assert result == WEEKLY_REVIEW
        assert new_idx is None

    def test_friday_does_not_advance_pool(self):
        _, new_idx = pick_today_exercise(date(2026, 5, 1), last_pool_index=0)
        assert new_idx is None


class TestWeekdayRotation:
    def test_first_run_starts_at_index_0(self):
        result, new_idx = pick_today_exercise(date(2026, 4, 27), last_pool_index=-1)
        assert result == WEEKDAY_POOL[0]
        assert new_idx == 0

    def test_advances_to_next_index(self):
        result, new_idx = pick_today_exercise(date(2026, 4, 28), last_pool_index=0)
        assert result == WEEKDAY_POOL[1]
        assert new_idx == 1

    def test_wraps_around_at_end(self):
        # last_idx=5는 vocabulary_en. 다음은 0=mental_math.
        result, new_idx = pick_today_exercise(date(2026, 4, 27), last_pool_index=5)
        assert result == WEEKDAY_POOL[0]
        assert new_idx == 0


class TestThreeWeekCycle:
    """원본 프롬프트의 3주 사이클 패턴 검증."""

    def test_full_three_week_cycle(self):
        # 시작: 2026-04-27(월), last_idx=-1 → 21일치 시뮬
        plan: list[tuple[int, str]] = []
        last_idx = -1
        d = date(2026, 4, 27)

        for _ in range(21):
            result, new_idx = pick_today_exercise(d, last_pool_index=last_idx)
            if result is not None:
                plan.append((d.weekday(), result))
            if new_idx is not None:
                last_idx = new_idx
            d += timedelta(days=1)

        # Week 1
        assert plan[0] == (0, "mental_math")
        assert plan[1] == (1, "logic_deduction")
        assert plan[2] == (2, "memory")
        assert plan[3] == (3, "pattern_visual")
        assert plan[4] == (4, "weekly_review")

        # Week 2
        assert plan[5] == (0, "verbal_fluency")
        assert plan[6] == (1, "free_writing")
        assert plan[7] == (2, "mental_math")
        assert plan[8] == (3, "logic_deduction")
        assert plan[9] == (4, "weekly_review")

        # Week 3
        assert plan[10] == (0, "memory")
        assert plan[11] == (1, "pattern_visual")
        assert plan[12] == (2, "verbal_fluency")
        assert plan[13] == (3, "free_writing")
        assert plan[14] == (4, "weekly_review")
