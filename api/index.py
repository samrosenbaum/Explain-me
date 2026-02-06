from fastapi import FastAPI, Request
from slack_bolt.adapter.fastapi import SlackRequestHandler

from slack_app import app as slack_app

app = FastAPI()
handler = SlackRequestHandler(slack_app)


@app.get("/health")
async def health_check():
    return {"ok": True}


@app.post("/slack/events")
async def slack_events(request: Request):
    return await handler.handle(request)
