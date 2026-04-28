"""오늘의 운동 콘텐츠 생성 + 피드백 생성."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import yaml

from . import claude_client, notion_client, storage
from .models import ExerciseType, Session
from .rotation import WEEKLY_REVIEW, pick_today_exercise

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def load_exercise_type(type_key: str) -> ExerciseType:
    path = PROMPTS_DIR / f"{type_key}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"운동 YAML 없음: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return ExerciseType(
        type=data["type"],
        display_name=data["display_name"],
        emoji=data["emoji"],
        system_prompt=data["system_prompt"],
        generation_prompt=data["generation_prompt"],
        feedback_prompt=data["feedback_prompt"],
    )


def generate_today_exercise(
    today: date,
) -> Optional[tuple[ExerciseType, str]]:
    """rotation으로 오늘 타입 결정 → 콘텐츠 생성. 토/일이면 None."""
    type_key, new_idx = pick_today_exercise(
        today, last_pool_index=storage.get_last_pool_index()
    )
    if type_key is None:
        return None

    ex = load_exercise_type(type_key)

    if type_key == WEEKLY_REVIEW:
        # 그 주 월요일 = 오늘(금) - 4
        week_start = today - timedelta(days=4)
        try:
            ctx = notion_client.fetch_weekly_context(week_start=week_start)
        except notion_client.NotionAPIError:
            ctx = "(노션 조회 실패 — 이번 주 기록 없이 회고)"
        content = claude_client.claude.generate_weekly_review(ex, ctx)
    else:
        recent = storage.recent_summaries_for_type(type_key, days=7)
        content = claude_client.claude.generate_exercise(ex, recent)

    if new_idx is not None:
        storage.save_last_pool_index(new_idx)

    return ex, content


def generate_feedback_for_session(session: Session, answer: str) -> str:
    ex = load_exercise_type(session.exercise_type)
    return claude_client.claude.generate_feedback(
        ex, session.exercise_content or "", answer
    )
