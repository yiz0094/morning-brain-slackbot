"""Anthropic SDK 래퍼 — 운동 생성 / 피드백 / 메트릭."""
from __future__ import annotations

from typing import Optional

from anthropic import Anthropic

from . import config, storage
from .models import ExerciseType


_METRIC_HINTS = {
    "mental_math": "5문제 중 정답 개수 (예: '정답 4/5')",
    "logic_deduction": "정답 여부 (예: '정답' 또는 '오답')",
    "memory": "회상 항목 정확도 (예: '회상 10/12')",
    "pattern_visual": "정답·규칙 맞춤 여부 (예: '정답·규칙 적중' 또는 '오답')",
    "verbal_fluency": "떠올린 단어 개수 (예: '단어 18개')",
    "free_writing": "답변 항목 개수 (예: '답 8개')",
}


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

    def generate_feedback(
        self, ex: ExerciseType, exercise_content: str, answer: str
    ) -> str:
        user = (
            f"{ex.feedback_prompt}\n\n"
            f"=== 운동 내용 ===\n{exercise_content}\n\n"
            f"=== Yiz의 답변 ===\n{answer}"
        )
        return self._call(ex.system_prompt, user, max_tokens=512)

    def generate_metric(
        self,
        ex: ExerciseType,
        exercise_content: str,
        answer: str,
        response_minutes: int,
    ) -> str:
        """운동별 정량 메트릭 한 줄 + 응답 시간."""
        hint = _METRIC_HINTS.get(ex.type, "주요 수치 한 가지")
        user = (
            f"운동 내용:\n{exercise_content}\n\n"
            f"답변:\n{answer}\n\n"
            f"이 답변에서 다음 메트릭을 한 줄로만 출력해라.\n"
            f"메트릭: {hint}\n"
            f"규칙: 다른 텍스트·설명·이모지 없이 한 줄. 예시 형식 그대로."
        )
        metric = self._call(ex.system_prompt, user, max_tokens=50)
        first_line = metric.strip().split("\n")[0].strip()
        return f"{first_line} · 응답 {response_minutes}분"


claude = ClaudeClient()
