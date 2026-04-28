"""FastAPI + Slack Bolt + APScheduler 통합."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, Request, Response
from slack_bolt import App
from slack_bolt.adapter.fastapi import SlackRequestHandler

from . import config, scheduler, slack_handlers, storage

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


config.validate()
storage.init_db()

bolt_app = App(
    token=config.SLACK_BOT_TOKEN,
    signing_secret=config.SLACK_SIGNING_SECRET,
)
slack_handlers.register(bolt_app)
bolt_handler = SlackRequestHandler(bolt_app)


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.setup(bolt_app.client)
    log.info("Service started.")
    try:
        yield
    finally:
        scheduler.shutdown()
        log.info("Service stopped.")


app =FastAPI(lifespan=lifespan)


@app.post("/slack/events")
async def slack_events(req: Request):
    return await bolt_handler.handle(req)


@app.post("/slack/commands")
async def slack_commands(req: Request):
    return await bolt_handler.handle(req)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "pool_index": storage.get_last_pool_index(),
        "today_pending": len(storage.get_today_pending_sessions()),
    }


@app.post("/trigger")
async def trigger_endpoint(x_trigger_key: str = Header(default="")):
    """수동 운동 트리거. SLACK_SIGNING_SECRET을 키로 재사용."""
    if x_trigger_key != config.SLACK_SIGNING_SECRET:
        return Response(status_code=401)
    posted = scheduler.trigger_morning_exercise(force=True)
    return {"posted": posted}
