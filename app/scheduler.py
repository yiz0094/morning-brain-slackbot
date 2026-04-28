"""APScheduler 셋업과 트리거 함수들."""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone

from . import config, exercises, notion_client, storage

log = logging.getLogger(__name__)

_KST = timezone(config.TIMEZONE)
_scheduler: Optional[BackgroundScheduler] = None
_slack_client: Any = None  # WebClient (런타임 주입)

_WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]


def setup(slack_client: Any) -> None:
    """main.py가 호출. WebClient를 받아 cron 잡 등록."""
    global _scheduler, _slack_client
    _slack_client = slack_client
    storage.init_db()

    _scheduler = BackgroundScheduler(timezone=_KST)

    hour, minute = map(int, config.DAILY_TIME_KST.split(":"))
    _scheduler.add_job(
        trigger_morning_exercise,
        CronTrigger(
            day_of_week="mon-fri", hour=hour, minute=minute, timezone=_KST
        ),
        id="morning_exercise",
    )
    _scheduler.add_job(
        trigger_reminder,
        CronTrigger(day_of_week="mon-fri", hour=12, minute=0, timezone=_KST),
        id="reminder",
    )
    _scheduler.start()
    log.info(
        "Scheduler started, jobs: %s",
        [j.id for j in _scheduler.get_jobs()],
    )


def shutdown() -> None:
    if _scheduler:
        _scheduler.shutdown(wait=False)


def trigger_morning_exercise(force: bool = False) -> bool:
    """오늘 운동 생성 → 노션 + 슬랙 포스트.

    토/일이거나 cap 초과면 False. force=True면 cap 우회.
    """
    today = date.today()

    if today.weekday() >= 5:
        log.info("주말이라 트리거 X (today=%s)", today)
        return False
    if not force and not storage.can_call_api():
        log.warning("Daily API cap 초과, skip")
        return False

    result = exercises.generate_today_exercise(today)
    if result is None:
        return False
    ex, content = result

    session_id = storage.create_session(
        today=today, exercise_type=ex.type, exercise_content=content,
    )

    notion_url: Optional[str] = None
    try:
        page_id, notion_url = notion_client.create_task(
            exercise_type=ex.type,
            display_name=ex.display_name,
            emoji=ex.emoji,
            today=today,
            exercise_content=content,
        )
        storage.attach_notion(session_id, page_id, notion_url)
    except notion_client.NotionAPIError as e:
        log.warning(f"Notion create 실패, 큐 적재: {e}")
        storage.queue_notion_sync(
            session_id, "create",
            {
                "display_name": ex.display_name,
                "emoji": ex.emoji,
                "today": today.isoformat(),
                "exercise_content": content,
            },
        )

    weekday_kr = _WEEKDAY_KR[today.weekday()]
    notion_line = (
        f"📝 노션: <{notion_url}|Task 페이지>"
        if notion_url else "📝 노션: (동기화 대기)"
    )
    text = (
        f"*{ex.emoji} [{weekday_kr}] {ex.display_name}*\n\n"
        f"{content}\n\n"
        f"⏱ 10분 안에 답해주세요\n"
        f"{notion_line}\n\n"
        f"👇 이 메시지 *스레드*에 답글로 적어 주세요"
    )

    posted = _slack_client.chat_postMessage(
        channel=config.BRAIN_CHANNEL_ID, text=text,
    )
    storage.attach_slack(
        session_id, channel=posted["channel"], ts=posted["ts"]
    )
    return True


def trigger_reminder() -> None:
    """오늘 pending 세션에 한 번만 부드러운 리마인드."""
    if date.today().weekday() >= 5:
        return
    for s in storage.get_today_pending_sessions():
        if s.reminded_at is not None:
            continue
        if not s.slack_ts or not s.slack_channel:
            continue
        _slack_client.chat_postMessage(
            channel=s.slack_channel,
            thread_ts=s.slack_ts,
            text="여유 될 때 답해주세요 🌱",
        )
        storage.mark_reminded(s.id)
