"""rotation.pick_today_exercise() 테스트."""
from datetime import date, timedelta

from app.rotation import WEEKDAY_POOL, pick_today_exercise


# 2026-04~05
#   2026-04-27 월 / 2026-04-28 화 / 2026-04-29 수
#   2026-04-30 목 / 2026-05-01 금
#   2026-05-02 토 / 2026-05-03 일


class TestWeekendSkipped:
    def test_saturday_returns_none(self):
        assert pick_today_exercise(date(2026, 5, 2), -1) == (None, None)

    def test_sunday_returns_none(self):
        assert pick_today_exercise(date(2026, 5, 3), 2) == (None, None)


class TestWeekdayRotation:
    def test_first_run_starts_at_index_0(self):
        result, new_idx = pick_today_exercise(date(2026, 4, 27), -1)
        assert result == WEEKDAY_POOL[0]
        assert new_idx == 0

    def test_advances_to_next_index(self):
        result, new_idx = pick_today_exercise(date(2026, 4, 28), 0)
        assert result == WEEKDAY_POOL[1]
        assert new_idx == 1

    def test_friday_uses_pool(self):
        result, new_idx = pick_today_exercise(date(2026, 5, 1), 3)
        assert result == WEEKDAY_POOL[4]
        assert new_idx == 4

    def test_wraps_around_at_end(self):
        result, new_idx = pick_today_exercise(date(2026, 4, 27), 5)
        assert result == WEEKDAY_POOL[0]
        assert new_idx == 0


class TestThreeWeekCycle:
    """평일 5일×3주 = 15일이 6개 풀을 어떻게 순환하는지."""

    def test_full_three_week_cycle(self):
        plan: list[tuple[int, str]] = []
        last_idx = -1
        d = date(2026, 4, 27)

        for _ in range(21):
            result, new_idx = pick_today_exercise(d, last_idx)
            if result is not None:
                plan.append((d.weekday(), result))
            if new_idx is not None:
                last_idx = new_idx
            d += timedelta(days=1)

        # Week 1 (월~금)
        assert plan[0] == (0, "mental_math")
        assert plan[1] == (1, "logic_deduction")
        assert plan[2] == (2, "memory")
        assert plan[3] == (3, "pattern_visual")
        assert plan[4] == (4, "verbal_fluency")

        # Week 2
        assert plan[5] == (0, "free_writing")
        assert plan[6] == (1, "mental_math")
        assert plan[7] == (2, "logic_deduction")
        assert plan[8] == (3, "memory")
        assert plan[9] == (4, "pattern_visual")

        # Week 3
        assert plan[10] == (0, "verbal_fluency")
        assert plan[11] == (1, "free_writing")
        assert plan[12] == (2, "mental_math")
        assert plan[13] == (3, "logic_deduction")
        assert plan[14] == (4, "memory")
