"""Anthropic SDK 래퍼 — 운동 생성과 피드백."""
from __future__ import annotations

from typing import Optional

from anthropic import Anthropic

from . import config, storage
from .models import ExerciseType


class ClaudeClient:
    def __init__(self) -> None:
        self._client: Optional[Anthropic] = None

    def _api(self) -> Anthropic:
        if self._client is None:
            self._client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
        return self._client

    def _call(self, system: str, user: str, max_tokens: int = 1024) -> str:
        if not storage.can_call_api():
            raise RuntimeError(
                f"오늘 Claude API 호출 한도({config.DAILY_API_CAP}) 초과"
            )
        msg = self._api().messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        storage.record_api_call()
        return "".join(
            getattr(block, "text", "") for block in msg.content
        ).strip()

    def generate_exercise(
        self, ex: ExerciseType, recent_summaries: list[str]
    ) -> str:
        recent_str = (
            "\n".join(f"- {s[:120]}" for s in recent_summaries)
            if recent_summaries else "(없음)"
        )
        user = ex.generation_prompt.replace("{recent_summaries}", recent_str)
        return self._call(ex.system_prompt, user, max_tokens=1024)

    def generate_weekly_review(
        self, ex: ExerciseType, weekly_context: str
    ) -> str:
        user = ex.generation_prompt.replace("{weekly_context}", weekly_context)
        return self._call(ex.system_prompt, user, max_tokens=1024)

    def generate_feedback(
        self, ex: ExerciseType, exercise_content: str, answer: str
    ) -> str:
        user = (
            f"{ex.feedback_prompt}\n\n"
            f"=== 운동 내용 ===\n{exercise_content}\n\n"
            f"=== Yiz의 답변 ===\n{answer}"
        )
        return self._call(ex.system_prompt, user, max_tokens=512)


claude = ClaudeClient()
