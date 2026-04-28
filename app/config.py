"""환경변수 로딩과 검증."""
from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


# 필수
ANTHROPIC_API_KEY: Optional[str] = os.environ.get("ANTHROPIC_API_KEY")
SLACK_BOT_TOKEN: Optional[str] = os.environ.get("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET: Optional[str] = os.environ.get("SLACK_SIGNING_SECRET")
BRAIN_CHANNEL_ID: Optional[str] = os.environ.get("BRAIN_CHANNEL_ID")
OWNER_USER_ID: Optional[str] = os.environ.get("OWNER_USER_ID")
NOTION_TOKEN: Optional[str] = os.environ.get("NOTION_TOKEN")
NOTION_PROJECT_PAGE_ID: Optional[str] = os.environ.get("NOTION_PROJECT_PAGE_ID")
NOTION_BOX_PAGE_ID: Optional[str] = os.environ.get("NOTION_BOX_PAGE_ID")
NOTION_TASKS_DATA_SOURCE_ID: Optional[str] = os.environ.get(
    "NOTION_TASKS_DATA_SOURCE_ID"
)

# 선택 (기본값 있음)
DAILY_TIME_KST: str = os.environ.get("DAILY_TIME_KST", "09:00")
DAILY_API_CAP: int = int(os.environ.get("DAILY_API_CAP", "10"))
TIMEZONE: str = os.environ.get("TIMEZONE", "Asia/Seoul")
SQLITE_PATH: str = os.environ.get("SQLITE_PATH", "data.db")
CLAUDE_MODEL: str = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")


def validate() -> None:
    """필수 환경변수 누락 시 즉시 실패."""
    required = {
        "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
        "SLACK_BOT_TOKEN": SLACK_BOT_TOKEN,
        "SLACK_SIGNING_SECRET": SLACK_SIGNING_SECRET,
        "BRAIN_CHANNEL_ID": BRAIN_CHANNEL_ID,
        "OWNER_USER_ID": OWNER_USER_ID,
        "NOTION_TOKEN": NOTION_TOKEN,
        "NOTION_TASKS_DATA_SOURCE_ID": NOTION_TASKS_DATA_SOURCE_ID,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise RuntimeError(f"필수 환경변수 누락: {', '.join(missing)}")
