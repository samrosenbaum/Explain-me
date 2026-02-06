import json
import hashlib
import hmac
import time
import os
import threading

from flask import Flask, request, jsonify

app = Flask(__name__)

_slack_app = None


def get_slack_app():
    global _slack_app
    if _slack_app is None:
        from slack_app import app as sa
        _slack_app = sa
    return _slack_app


def verify_slack_signature(body_bytes):
    """Verify the request is from Slack."""
    signing_secret = os.environ.get("SLACK_SIGNING_SECRET", "")
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    if abs(time.time() - int(timestamp or 0)) > 60 * 5:
        return False

    sig_basestring = f"v0:{timestamp}:{body_bytes.decode()}"
    my_signature = "v0=" + hmac.new(
        signing_secret.encode(), sig_basestring.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(my_signature, signature)


def handle_shortcut_async(payload):
    """Handle shortcut in a way that completes before the function dies."""
    from slack_sdk import WebClient
    from slack_app import (
        extract_message_text, get_explanation, open_loading_modal,
        update_modal_with_explanation, format_explanation_blocks,
        SLACK_BOT_TOKEN,
    )

    client = WebClient(token=SLACK_BOT_TOKEN)
    callback_id = payload.get("callback_id")
    message = payload.get("message", {})
    text = extract_message_text(message)
    trigger_id = payload.get("trigger_id")
    channel_id = payload.get("channel", {}).get("id")
    message_ts = message.get("ts")

    try:
        view_id = open_loading_modal(client, trigger_id)
    except Exception:
        return

    if not text:
        client.views_update(
            view_id=view_id,
            view={
                "type": "modal",
                "title": {"type": "plain_text", "text": "ELI5 at your service"},
                "close": {"type": "plain_text", "text": "Close"},
                "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": "I couldn't find any text to explain in that message."}}],
            },
        )
        return

    try:
        explanation = get_explanation(text)

        if callback_id == "explain_jargon_public" and channel_id:
            try:
                blocks = format_explanation_blocks(text, explanation)
                client.chat_postMessage(
                    channel=channel_id, thread_ts=message_ts,
                    text=explanation, blocks=blocks,
                )
                client.views_update(
                    view_id=view_id,
                    view={
                        "type": "modal",
                        "title": {"type": "plain_text", "text": "ELI5 at your service"},
                        "close": {"type": "plain_text", "text": "Close"},
                        "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": ":white_check_mark: Explanation posted to the channel!"}}],
                    },
                )
                return
            except Exception as exc:
                if "not_in_channel" in str(exc):
                    pass  # Fall through to modal
                else:
                    raise

        update_modal_with_explanation(client, view_id, text, explanation)

    except Exception:
        client.views_update(
            view_id=view_id,
            view={
                "type": "modal",
                "title": {"type": "plain_text", "text": "ELI5 at your service"},
                "close": {"type": "plain_text", "text": "Close"},
                "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": "Sorry, I had trouble generating an explanation. Please try again."}}],
            },
        )


@app.route("/api/health", methods=["GET"])
def health_check():
    return {"ok": True}


@app.route("/api/slack/events", methods=["POST"])
@app.route("/api", methods=["POST"])
def slack_events():
    body_bytes = request.get_data()
    body = request.get_json(silent=True) or {}

    # Handle Slack URL verification challenge
    if body.get("type") == "url_verification":
        return jsonify({"challenge": body.get("challenge")})

    # Handle interactive payloads (shortcuts)
    if request.content_type and "x-www-form-urlencoded" in request.content_type:
        payload_str = request.form.get("payload", "{}")
        payload = json.loads(payload_str)

        if payload.get("type") == "shortcut" or payload.get("type") == "message_action":
            # Start processing in a thread, respond to Slack immediately
            t = threading.Thread(target=handle_shortcut_async, args=(payload,))
            t.start()
            # Wait for it to complete (Vercel keeps function alive until response)
            t.join(timeout=25)
            return "", 200

    # All other events go through slack-bolt
    from slack_bolt.adapter.flask import SlackRequestHandler
    handler = SlackRequestHandler(get_slack_app())
    return handler.handle(request)
