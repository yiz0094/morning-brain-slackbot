"""도메인 모델."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

# 세션 상태
STATUS_PENDING = "pending"
STATUS_COMPLETED = "completed"
STATUS_SKIPPED = "skipped"
STATUS_MISSED = "missed"


@dataclass
class ExerciseType:
    """prompts/*.yaml 한 개의 메모리 표현."""
    type: str
    display_name: str
    emoji: str
    system_prompt: str
    generation_prompt: str
    feedback_prompt: str


@dataclass
class Session:
    """오늘의 운동 한 회차. SQLite sessions 테이블 한 row."""
    id: int
    date: date
    exercise_type: str
    slack_channel: Optional[str]
    slack_ts: Optional[str]
    notion_page_id: Optional[str]
    notion_url: Optional[str]
    status: str
    exercise_content: Optional[str]
    answer: Optional[str]
    feedback: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]
    reminded_at: Optional[datetime]
