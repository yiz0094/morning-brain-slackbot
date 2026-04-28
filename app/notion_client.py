"""
Notion API 래퍼.

Tasks 데이터소스: NOTION_TASKS_DATA_SOURCE_ID

기록할 속성:
  - Task (title): "🧠 [요일] [운동타입 한글] - YYYY-MM-DD"
  - 완료 (checkbox): 처음 False, 답변 후 True
  - 구분 (select): "저널"
  - 중요/긴급 (select): "5. 습관 / 루틴"
  - 날짜 (date)
  - 소요시간(분) (number): 10
  - 프로젝트 (relation): NOTION_PROJECT_PAGE_ID
  - 박스 (relation): NOTION_BOX_PAGE_ID

페이지 본문:
  ## 🧠 오늘의 운동
  [운동 콘텐츠]

  답변/피드백 헤더는 답변이 들어왔을 때 append.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional

from notion_client import APIResponseError, Client

from . import config


class NotionAPIError(Exception):
    """노션 API 호출 실패. 호출자가 SQLite fallback 트리거."""


_client: Optional[Client] = None


def _notion() -> Client:
    global _client
    if _client is None:
        if not config.NOTION_TOKEN:
            raise NotionAPIError("NOTION_TOKEN 미설정")
        _client = Client(auth=config.NOTION_TOKEN)
    return _client


_WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]


def _markdown_to_blocks(md: str) -> list[dict[str, Any]]:
    """간이 변환: ## → heading_2, ### → heading_3, 그 외 줄 → paragraph."""
    blocks: list[dict[str, Any]] = []
    for raw in md.split("\n"):
        line = raw.rstrip()
        if not line:
            continue
        if line.startswith("## "):
            content, btype, key = line[3:], "heading_2", "heading_2"
        elif line.startswith("### "):
            content, btype, key = line[4:], "heading_3", "heading_3"
        else:
            content, btype, key = line, "paragraph", "paragraph"
        # Notion rich_text는 단일 청크 2000자 제한
        chunks = [content[i:i + 1900] for i in range(0, len(content), 1900)] or [""]
        rich_text = [
            {"type": "text", "text": {"content": ch}} for ch in chunks
        ]
        blocks.append({"object": "block", "type": btype, key: {"rich_text": rich_text}})
    return blocks


def create_task(
    *,
    exercise_type: str,
    display_name: str,
    emoji: str,
    today: date,
    exercise_content: str,
) -> tuple[str, str]:
    """Tasks DB에 새 운동 레코드를 만든다."""
    weekday_kr = _WEEKDAY_KR[today.weekday()]
    title = f"{emoji} [{weekday_kr}] {display_name} - {today.isoformat()}"

    properties: dict[str, Any] = {
        "Task": {"title": [{"text": {"content": title}}]},
        "완료": {"checkbox": False},
        "구분": {"select": {"name": "저널"}},
        "중요/긴급": {"select": {"name": "5. 습관 / 루틴"}},
        "날짜": {"date": {"start": today.isoformat()}},
        "소요시간(분)": {"number": 10},
        "프로젝트": {"relation": [{"id": config.NOTION_PROJECT_PAGE_ID}]},
        "박스": {"relation": [{"id": config.NOTION_BOX_PAGE_ID}]},
    }

    children: list[dict[str, Any]] = [
        {
            "object": "block", "type": "heading_2",
            "heading_2": {"rich_text": [
                {"type": "text", "text": {"content": "🧠 오늘의 운동"}}
            ]},
        }
    ] + _markdown_to_blocks(exercise_content)

    # 신규 API: data_source_id, 안 되면 구버전 database_id
    last_err: Optional[Exception] = None
    for parent_kind in ("data_source_id", "database_id"):
        try:
            page = _notion().pages.create(
                parent={parent_kind: config.NOTION_TASKS_DATA_SOURCE_ID},
                properties=properties,
                children=children,
            )
            return page["id"], page["url"]
        except APIResponseError as e:
            last_err = e
            continue
    raise NotionAPIError(f"Notion create_task 실패: {last_err}")


def append_answer_and_feedback(
    *, page_id: str, answer: str, feedback: str
) -> None:
    """답변/피드백 헤더와 본문을 페이지 끝에 append."""
    blocks = (
        [{
            "object": "block", "type": "heading_2",
            "heading_2": {"rich_text": [
                {"type": "text", "text": {"content": "✏️ 내 답변"}}
            ]},
        }]
        + _markdown_to_blocks(answer)
        + [{
            "object": "block", "type": "heading_2",
            "heading_2": {"rich_text": [
                {"type": "text", "text": {"content": "💬 피드백"}}
            ]},
        }]
        + _markdown_to_blocks(feedback)
    )
    try:
        _notion().blocks.children.append(block_id=page_id, children=blocks)
    except APIResponseError as e:
        raise NotionAPIError(f"Notion append 실패: {e}") from e


def mark_completed(*, page_id: str) -> None:
    """'완료' 체크박스 True."""
    try:
        _notion().pages.update(
            page_id=page_id,
            properties={"완료": {"checkbox": True}},
        )
    except APIResponseError as e:
        raise NotionAPIError(f"Notion mark_completed 실패: {e}") from e


def fetch_weekly_context(*, week_start: date) -> str:
    """그 주 월~목 Task 페이지 본문을 합친 컨텍스트 문자열."""
    end = week_start + timedelta(days=4)  # 목까지 (금 제외)
    filter_body = {
        "and": [
            {"property": "날짜", "date": {
                "on_or_after": week_start.isoformat()
            }},
            {"property": "날짜", "date": {
                "before": end.isoformat()
            }},
        ]
    }

    try:
        res = _notion().databases.query(
            database_id=config.NOTION_TASKS_DATA_SOURCE_ID,
            filter=filter_body,
            sorts=[{"property": "날짜", "direction": "ascending"}],
        )
    except APIResponseError as e:
        raise NotionAPIError(f"Notion 주간 조회 실패: {e}") from e

    pages = res.get("results", [])
    parts: list[str] = []
    for p in pages:
        title_rich = p["properties"].get("Task", {}).get("title", [])
        title = title_rich[0]["plain_text"] if title_rich else "(제목 없음)"
        body = _read_page_text(p["id"])
        parts.append(f"--- {title} ---\n{body}\n")
    return "\n".join(parts) if parts else "(이번 주 기록 없음)"


def _read_page_text(page_id: str) -> str:
    """페이지 children 블록의 plain text를 한 덩어리로 추출."""
    try:
        res = _notion().blocks.children.list(block_id=page_id)
    except APIResponseError as e:
        raise NotionAPIError(f"Notion 페이지 본문 조회 실패: {e}") from e

    lines: list[str] = []
    for block in res.get("results", []):
        btype = block.get("type")
        rich = block.get(btype, {}).get("rich_text", []) if btype else []
        text = "".join(rt.get("plain_text", "") for rt in rich)
        if not text:
            continue
        if btype == "heading_2":
            lines.append(f"## {text}")
        elif btype == "heading_3":
            lines.append(f"### {text}")
        else:
            lines.append(text)
    return "\n".join(lines)
