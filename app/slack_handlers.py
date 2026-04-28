"""슬랙 메시지/슬래시 커맨드 핸들러 등록."""
from __future__ import annotations

from datetime import datetime

from slack_bolt import App

from . import config, exercises, notion_client, storage
from .models import STATUS_PENDING


def register(app: App) -> None:
    """Bolt App에 모든 핸들러를 등록."""

    # ---- 메시지 이벤트: 스레드 답글 → 피드백 + 메트릭 ----
    @app.event("message")
    def handle_message(event, client, logger):
        if event.get("subtype") == "bot_message":
            return
        if event.get("bot_id"):
            return
        thread_ts = event.get("thread_ts")
        if not thread_ts:
            return
        if event.get("user") != config.OWNER_USER_ID:
            return

        session = storage.get_session_by_slack_ts(thread_ts)
        if not session or session.status != STATUS_PENDING:
            return

        answer = (event.get("text") or "").strip()
        if not answer:
            return

        response_minutes = max(
            1, int((datetime.utcnow() - session.created_at).total_seconds() / 60)
        )

        try:
            feedback, metric = exercises.generate_feedback_and_metric(
                session, answer, response_minutes
            )
        except Exception as e:
            logger.exception("피드백/메트릭 생성 실패")
            client.chat_postMessage(
                channel=event["channel"],
                thread_ts=thread_ts,
                text=f"⚠️ 피드백 생성 실패: {e}",
            )
            return

        if session.notion_page_id:
            try:
                notion_client.append_answer_and_feedback(
                    page_id=session.notion_page_id,
                    answer=answer,
                    feedback=feedback,
                    metric=metric,
                )
                notion_client.mark_completed(page_id=session.notion_page_id)
            except notion_client.NotionAPIError as e:
                logger.warning(f"Notion 동기화 실패, 큐 적재: {e}")
                storage.queue_notion_sync(
                    session.id,
                    "append_and_complete",
                    {"answer": answer, "feedback": feedback, "metric": metric},
                )
        else:
            storage.queue_notion_sync(
                session.id,
                "append_and_complete",
                {"answer": answer, "feedback": feedback, "metric": metric},
            )

        storage.save_answer_and_feedback(
            slack_ts=thread_ts, answer=answer, feedback=feedback
        )

        client.chat_postMessage(
            channel=event["channel"],
            thread_ts=thread_ts,
            text=f"💬 {feedback}\n\n📊 {metric}\n\n✅ 노션에 저장됨",
        )

    # ---- 슬래시 커맨드 ----

    def _is_owner(body) -> bool:
        return body.get("user_id") == config.OWNER_USER_ID

    @app.command("/brain-skip")
    def cmd_skip(ack, body, respond, client):
        ack()
        if not _is_owner(body):
            respond("권한 없음")
            return
        pending = storage.get_today_pending_sessions()
        if not pending:
            respond("오늘 진행 중인 운동이 없어요 🌱")
            return
        for s in pending:
            if s.slack_ts:
                storage.mark_skipped(s.slack_ts)
                if s.slack_channel:
                    client.chat_postMessage(
                        channel=s.slack_channel,
                        thread_ts=s.slack_ts,
                        text="오늘은 쉬어요. 내일 다시 봬요 🌿",
                    )
        respond(f"오늘 {len(pending)}개 세션 skip 처리.")

    @app.command("/brain-streak")
    def cmd_streak(ack, body, respond):
        ack()
        if not _is_owner(body):
            respond("권한 없음")
            return
        streak = storage.get_streak()
        history = storage.get_recent_weekday_history(weekdays=14)
        respond(f"🔥 연속 *{streak}* 평일\n최근 14평일: {history}")

    @app.command("/brain-history")
    def cmd_history(ack, body, respond):
        ack()
        if not _is_owner(body):
            respond("권한 없음")
            return
        type_key = (body.get("text") or "").strip()
        sessions = (
            storage.get_history_for_type(type_key, limit=5)
            if type_key
            else storage.get_recent_history(limit=5)
        )
        if not sessions:
            respond("기록 없음.")
            return
        lines = []
        for s in sessions:
            link = (
                f"<{s.notion_url}|노션 페이지>"
                if s.notion_url else "(노션 링크 없음)"
            )
            lines.append(f"• {s.date} `{s.exercise_type}` — {link}")
        respond("\n".join(lines))

    @app.command("/brain-now")
    def cmd_now(ack, body, respond):
        ack()
        if not _is_owner(body):
            respond("권한 없음")
            return
        from .scheduler import trigger_morning_exercise
        try:
            posted = trigger_morning_exercise(force=True)
        except Exception as e:
            respond(f"트리거 실패: {e}")
            return
        respond(
            "✅ 새 운동 포스트 완료." if posted
            else "오늘은 운동 X (주말 또는 cap 초과)."
        )
