from fastapi import FastAPI, Request

app = FastAPI()

_handler = None


def get_handler():
    global _handler
    if _handler is None:
        from slack_bolt.adapter.fastapi import SlackRequestHandler
        from slack_app import app as slack_app
        _handler = SlackRequestHandler(slack_app)
    return _handler


@app.get("/health")
async def health_check():
    return {"ok": True}


@app.post("/slack/events")
async def slack_events(request: Request):
    return await get_handler().handle(request)
