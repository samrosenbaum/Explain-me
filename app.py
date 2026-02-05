import os

import requests
from flask import Flask, Response, request
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")

if not SLACK_BOT_TOKEN or not SLACK_SIGNING_SECRET:
    raise RuntimeError(
        "Missing Slack credentials. Set SLACK_BOT_TOKEN and SLACK_SIGNING_SECRET."
    )

bolt_app = App(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)
flask_app = Flask(__name__)
handler = SlackRequestHandler(bolt_app)


@bolt_app.shortcut("explain_jargon")
def explain_jargon_shortcut(ack, payload, client, logger):
    ack()
    message = payload.get("message", {})
    text = message.get("text", "").strip()
    channel_id = payload.get("channel", {}).get("id")
    user_id = payload.get("user", {}).get("id")

    if not text:
        if channel_id and user_id:
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text="I couldn't find any text to explain in that message.",
            )
        return

    explanation = explain_text(text, logger)

    if channel_id and user_id:
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text=explanation,
        )


@flask_app.route("/slack/events", methods=["POST"])
def slack_events() -> Response:
    return handler.handle(request)


@flask_app.route("/health", methods=["GET"])
def health() -> Response:
    return Response("ok", status=200)


def explain_text(text: str, logger) -> str:
    if not OPENAI_API_KEY:
        return (
            "I can explain this once the OpenAI API key is configured. "
            "Set OPENAI_API_KEY to enable explanations."
        )

    prompt = (
        "Explain the following technical text in simple, plain English for a "
        "non-expert colleague. Keep it short and avoid jargon. Text:\n\n"
        f"{text}"
    )

    try:
        response = requests.post(
            f"{OPENAI_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": OPENAI_MODEL,
                "messages": [
                    {"role": "system", "content": "You simplify technical jargon."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
            },
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as exc:  # noqa: BLE001 - surface errors to the user
        logger.exception("Failed to generate explanation: %s", exc)
        return "Sorry, I had trouble generating an explanation right now."


if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "3000")))
