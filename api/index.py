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
    text, images = extract_message_text(message, client=client)
    trigger_id = payload.get("trigger_id")
    channel_id = payload.get("channel", {}).get("id")
    message_ts = message.get("ts")

    try:
        view_id = open_loading_modal(client, trigger_id)
    except Exception:
        return

    if not text and not images:
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
        explanation = get_explanation(text, images)

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

    except Exception as exc:
        import traceback
        print(f"[shortcut] Error: {exc}", flush=True)
        traceback.print_exc()
        client.views_update(
            view_id=view_id,
            view={
                "type": "modal",
                "title": {"type": "plain_text", "text": "ELI5 at your service"},
                "close": {"type": "plain_text", "text": "Close"},
                "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": f"Sorry, I had trouble generating an explanation.\n\n`{str(exc)[:200]}`"}}],
            },
        )


def handle_block_action(payload):
    """Handle block_actions like button clicks in modals."""
    import traceback
    from slack_sdk import WebClient
    from slack_app import SLACK_BOT_TOKEN

    client = WebClient(token=SLACK_BOT_TOKEN)

    actions = payload.get("actions", [])
    if not actions:
        print("[block_action] No actions in payload")
        return

    action_id = actions[0].get("action_id")
    print(f"[block_action] action_id={action_id}")

    if action_id == "chat_about_this":
        user_id = payload.get("user", {}).get("id")
        view = payload.get("view", {})
        view_id = view.get("id")
        metadata = view.get("private_metadata", "{}")

        try:
            data = json.loads(metadata)
            original_text = data.get("original_text", "")
        except Exception:
            original_text = ""

        if not user_id:
            print("[block_action] No user_id")
            return

        try:
            dm = client.conversations_open(users=[user_id])
            dm_channel = dm["channel"]["id"]
            preview = f"{original_text[:500]}{'...' if len(original_text) > 500 else ''}"
            client.chat_postMessage(
                channel=dm_channel,
                text=(
                    "Hey! You wanted to chat about this message:\n\n"
                    f">{preview}\n\n"
                    "What would you like me to explain? Ask me anything!"
                ),
            )
            # Update modal to confirm DM was sent
            if view_id:
                client.views_update(
                    view_id=view_id,
                    view={
                        "type": "modal",
                        "title": {"type": "plain_text", "text": "ELI5 at your service"},
                        "close": {"type": "plain_text", "text": "Close"},
                        "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": ":white_check_mark: Check your DMs! I sent you a message so we can chat."}}],
                    },
                )
        except Exception as exc:
            print(f"[block_action] Error: {exc}")
            traceback.print_exc()


def parse_view_submission(payload):
    """Parse the view_submission and return (view_id, question, original_text, conversation, initial_explanation) or None."""
    view = payload.get("view", {})
    callback_id = view.get("callback_id")

    if callback_id != "eli5_followup":
        return None

    view_id = view.get("id")
    metadata = view.get("private_metadata", "{}")
    try:
        data = json.loads(metadata)
    except Exception:
        data = {}

    original_text = data.get("original_text", "")
    conversation = data.get("conversation", [])

    # Get the follow-up question from the input
    values = view.get("state", {}).get("values", {})
    followup_block = values.get("followup_block", {})
    followup_input = followup_block.get("followup_input", {})
    question = (followup_input.get("value") or "").strip()

    if not question:
        return None

    # Extract the initial explanation from the current blocks
    blocks = view.get("blocks", [])
    explanation_parts = []
    in_explanation = False
    for block in blocks:
        if block.get("type") == "divider" and not in_explanation:
            in_explanation = True
            continue
        if in_explanation:
            if block.get("type") == "divider":
                break
            text = block.get("text", {}).get("text", "")
            if text:
                explanation_parts.append(text)
    initial_explanation = "\n\n".join(explanation_parts)

    return view_id, question, original_text, conversation, initial_explanation


def handle_view_closed(payload):
    """When modal closes, send conversation recap to user's DM."""
    from slack_sdk import WebClient
    from slack_app import SLACK_BOT_TOKEN

    view = payload.get("view", {})
    callback_id = view.get("callback_id")
    user_id = payload.get("user", {}).get("id")

    if callback_id != "eli5_followup" or not user_id:
        return

    metadata = view.get("private_metadata", "{}")
    try:
        data = json.loads(metadata)
    except Exception:
        return

    conversation = data.get("conversation", [])
    if not conversation:
        return  # No follow-up questions were asked, skip DM

    original_text = data.get("original_text", "")
    client = WebClient(token=SLACK_BOT_TOKEN)

    try:
        # Build recap message
        recap = ":robot_face: *Here's your ELI5 conversation for reference:*\n\n"
        if original_text:
            preview = f"{original_text[:300]}{'...' if len(original_text) > 300 else ''}"
            recap += f"*Original message:*\n>{preview}\n\n"

        for entry in conversation:
            if entry["role"] == "user":
                recap += f"*You asked:* {entry['content']}\n\n"
            else:
                recap += f"{entry['content']}\n\n"

        dm = client.conversations_open(users=[user_id])
        dm_channel = dm["channel"]["id"]
        client.chat_postMessage(channel=dm_channel, text=recap)
    except Exception as exc:
        print(f"[view_closed] Error: {exc}", flush=True)


def handle_dm_event(event):
    """Handle a DM message event directly."""
    import re
    from slack_sdk import WebClient
    from slack_app import (
        SLACK_BOT_TOKEN, chat_response, get_explanation,
        SLACK_MESSAGE_LINK_RE, fetch_slack_message,
    )

    client = WebClient(token=SLACK_BOT_TOKEN)
    channel_id = event.get("channel")
    user_message = event.get("text", "").strip()

    if not user_message or not channel_id:
        return

    try:
        # Check if the user pasted a Slack message link
        link_match = SLACK_MESSAGE_LINK_RE.search(user_message)
        if link_match:
            linked_text = fetch_slack_message(client, link_match)
            if linked_text:
                explanation = get_explanation(linked_text)
                preview = f"{linked_text[:500]}{'...' if len(linked_text) > 500 else ''}"
                client.chat_postMessage(
                    channel=channel_id,
                    text=(
                        f"Here's that message:\n>{preview}\n\n"
                        f"{explanation}\n\n"
                        "Feel free to ask me follow-up questions!"
                    ),
                )
            else:
                client.chat_postMessage(
                    channel=channel_id,
                    text="I couldn't fetch that message. I might not have access to that channel. Try copying the message text and sending it to me directly!",
                )
            return

        # Regular conversation — build history and respond
        result = client.conversations_history(channel=channel_id, limit=10)
        history = result.get("messages", [])

        messages = []
        for msg in reversed(history[1:]):
            if msg.get("bot_id"):
                messages.append({"role": "assistant", "content": msg.get("text", "")})
            elif not msg.get("subtype"):
                messages.append({"role": "user", "content": msg.get("text", "")})
        messages.append({"role": "user", "content": user_message})

        response = chat_response(messages)
        client.chat_postMessage(channel=channel_id, text=response)

    except Exception as exc:
        print(f"[dm_event] Error: {exc}", flush=True)
        try:
            client.chat_postMessage(
                channel=channel_id,
                text="Sorry, I had trouble processing that. Could you try again?",
            )
        except Exception:
            pass


def handle_reaction_event(event):
    """Handle a reaction_added event directly."""
    from slack_sdk import WebClient
    from slack_app import SLACK_BOT_TOKEN, CHAT_TRIGGER_EMOJIS

    reaction = event.get("reaction")
    print(f"[reaction_event] Reaction: {reaction}, triggers: {CHAT_TRIGGER_EMOJIS}", flush=True)

    if reaction not in CHAT_TRIGGER_EMOJIS:
        return

    client = WebClient(token=SLACK_BOT_TOKEN)
    user_id = event.get("user")
    item = event.get("item", {})
    channel_id = item.get("channel")
    message_ts = item.get("ts")

    if not all([user_id, channel_id, message_ts]):
        return

    try:
        result = client.conversations_history(
            channel=channel_id, latest=message_ts, limit=1, inclusive=True
        )
        messages = result.get("messages", [])
        if not messages:
            return

        original_text = messages[0].get("text", "")
        if not original_text:
            return

        dm = client.conversations_open(users=[user_id])
        dm_channel = dm["channel"]["id"]
        preview = f"{original_text[:500]}{'...' if len(original_text) > 500 else ''}"
        client.chat_postMessage(
            channel=dm_channel,
            text=(
                "Hey! I saw you wanted to chat about this message:\n\n"
                f">{preview}\n\n"
                "What would you like me to explain? Ask me anything!"
            ),
        )
    except Exception as exc:
        print(f"[reaction_event] Error: {exc}", flush=True)


@app.route("/api/followup", methods=["POST"])
def handle_followup_request():
    """Process a follow-up question asynchronously (called by view_submission handler)."""
    print(f"[followup] Received request", flush=True)
    data = request.get_json()

    # Simple auth — verify caller knows our signing secret
    if data.get("secret") != os.environ.get("SLACK_SIGNING_SECRET"):
        print(f"[followup] Auth failed", flush=True)
        return "", 403

    view_id = data["view_id"]
    question = data["question"]
    original_text = data["original_text"]
    conversation = data["conversation"]
    initial_explanation = data["initial_explanation"]
    print(f"[followup] question={question[:50]}, view_id={view_id}", flush=True)

    from slack_sdk import WebClient
    from slack_app import (
        chat_response, build_explanation_modal_view, SLACK_BOT_TOKEN,
        AI_GATEWAY_CHAT_MODEL,
    )
    client = WebClient(token=SLACK_BOT_TOKEN)
    print(f"[followup] Using chat model: {AI_GATEWAY_CHAT_MODEL}", flush=True)

    messages = [
        {"role": "user", "content": f"Original message to explain:\n{original_text}"},
    ]
    for entry in conversation:
        messages.append(entry)
    messages.append({"role": "user", "content": question})

    try:
        answer = chat_response(messages)
        print(f"[followup] Got AI answer ({len(answer)} chars)", flush=True)
    except Exception as exc:
        import traceback
        print(f"[followup] AI error: {exc}", flush=True)
        traceback.print_exc()
        answer = "Sorry, I had trouble with that question. Try asking differently!"

    updated_conv = list(conversation) + [
        {"role": "user", "content": question},
        {"role": "assistant", "content": answer},
    ]
    final_view = build_explanation_modal_view(
        original_text, initial_explanation, updated_conv
    )

    try:
        client.views_update(view_id=view_id, view=final_view)
        print(f"[followup] Modal updated successfully", flush=True)
    except Exception as exc:
        import traceback
        print(f"[followup] views.update error: {exc}", flush=True)
        traceback.print_exc()

    return {"ok": True}


@app.route("/api/health", methods=["GET"])
def health_check():
    return {"ok": True}


@app.route("/api/slack/events", methods=["POST"])
@app.route("/api", methods=["POST"])
def slack_events():
    body_bytes = request.get_data()
    body = request.get_json(silent=True) or {}

    print(f"[slack_events] content_type={request.content_type}, body_type={body.get('type')}", flush=True)

    # Skip Slack retries — we already handled the first attempt
    if request.headers.get("X-Slack-Retry-Num"):
        print(f"[slack_events] Skipping retry #{request.headers.get('X-Slack-Retry-Num')}", flush=True)
        return jsonify({"ok": True})

    # Handle Slack URL verification challenge
    if body.get("type") == "url_verification":
        return jsonify({"challenge": body.get("challenge")})

    # Handle interactive payloads (shortcuts, button clicks)
    if request.content_type and "x-www-form-urlencoded" in request.content_type:
        payload_str = request.form.get("payload", "{}")
        payload = json.loads(payload_str)
        payload_type = payload.get("type")
        print(f"[slack_events] payload_type={payload_type}", flush=True)

        if payload_type in ("shortcut", "message_action"):
            # Start processing in a thread, respond to Slack immediately
            t = threading.Thread(target=handle_shortcut_async, args=(payload,))
            t.start()
            # Wait for it to complete (Vercel keeps function alive until response)
            t.join(timeout=25)
            return "", 200

        if payload_type == "block_actions":
            print(f"[slack_events] handling block_actions", flush=True)
            t = threading.Thread(target=handle_block_action, args=(payload,))
            t.start()
            t.join(timeout=10)
            return "", 200

        if payload_type == "view_submission":
            print(f"[slack_events] handling view_submission", flush=True)
            parsed = parse_view_submission(payload)
            if parsed:
                view_id, question, original_text, conversation, initial_explanation = parsed
                print(f"[view_submission] q={question[:50]}, vid={view_id}", flush=True)

                import random
                from slack_app import build_explanation_modal_view, THINKING_MESSAGES

                # Build "Thinking..." view to return immediately (within 3s)
                thinking_conv = list(conversation) + [
                    {"role": "user", "content": question},
                    {"role": "assistant", "content": random.choice(THINKING_MESSAGES)},
                ]
                thinking_view = build_explanation_modal_view(
                    original_text, initial_explanation, thinking_conv
                )

                # Send request to /api/followup synchronously — this ensures
                # the data reaches Vercel before we return the response.
                # We use http.client so we can send without waiting for the
                # response (the /api/followup function runs independently).
                import http.client as _http
                host = request.host
                followup_body = json.dumps({
                    "secret": os.environ.get("SLACK_SIGNING_SECRET"),
                    "view_id": view_id,
                    "question": question,
                    "original_text": original_text,
                    "conversation": conversation,
                    "initial_explanation": initial_explanation,
                })

                try:
                    conn = _http.HTTPSConnection(host, timeout=3)
                    conn.request(
                        "POST", "/api/followup",
                        body=followup_body,
                        headers={"Content-Type": "application/json"},
                    )
                    print(f"[view_submission] Sent followup request to {host}", flush=True)
                except Exception as exc:
                    print(f"[view_submission] Failed to send followup: {exc}", flush=True)

                # Return thinking view immediately — /api/followup will update with answer
                return jsonify({"response_action": "update", "view": thinking_view})

            # No question entered — show validation error
            return jsonify({
                "response_action": "errors",
                "errors": {"followup_block": "Please type a question first!"}
            })

        if payload_type == "view_closed":
            # Send conversation recap to DM when modal closes
            print(f"[slack_events] handling view_closed", flush=True)
            handle_view_closed(payload)
            return "", 200

    # Handle event callbacks directly (slack-bolt handlers don't complete on Vercel)
    if body.get("type") == "event_callback":
        event = body.get("event", {})
        event_type = event.get("type")
        print(f"[slack_events] event_type={event_type}", flush=True)

        if event_type == "message" and event.get("channel_type") == "im":
            # DM message — handle in thread
            if not event.get("bot_id") and not event.get("subtype"):
                t = threading.Thread(target=handle_dm_event, args=(event,))
                t.start()
                t.join(timeout=25)
            return jsonify({"ok": True})

        if event_type == "reaction_added":
            t = threading.Thread(target=handle_reaction_event, args=(event,))
            t.start()
            t.join(timeout=2)  # Fast — only Slack API calls, no AI
            return jsonify({"ok": True})

        # Ack other events we don't handle directly
        return jsonify({"ok": True})

    # Fallback to slack-bolt for anything else
    from slack_bolt.adapter.flask import SlackRequestHandler
    handler = SlackRequestHandler(get_slack_app())
    return handler.handle(request)
