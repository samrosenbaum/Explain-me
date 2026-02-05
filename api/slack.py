"""
Slack Jargon Explainer - Vercel Serverless Function

Handles Slack events via HTTP (no Socket Mode needed).
Deploy to Vercel and set your Request URL to: https://your-app.vercel.app/api/slack
"""

import os
from slack_bolt import App
from slack_bolt.adapter.starlette import SlackRequestHandler
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Route

# AI Provider config
AI_GATEWAY_API_KEY = os.environ.get("AI_GATEWAY_API_KEY")
AI_GATEWAY_BASE_URL = os.environ.get("AI_GATEWAY_BASE_URL", "https://ai-gateway.vercel.sh/v1")
AI_GATEWAY_MODEL = os.environ.get("AI_GATEWAY_MODEL", "anthropic/claude-sonnet-4-20250514")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# Slack config
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")

app = App(
    token=SLACK_BOT_TOKEN,
    signing_secret=SLACK_SIGNING_SECRET,
)

# Emoji that triggers DM chat
CHAT_TRIGGER_EMOJI = "speech_balloon"

SYSTEM_PROMPT = "You explain technical jargon in simple, friendly terms. Be concise."

CHAT_SYSTEM_PROMPT = """You are a friendly technical explainer helping someone understand jargon and technical concepts.

- Explain things in simple, plain English
- Be conversational and helpful
- If they ask follow-up questions, build on what you've already explained
- Keep responses concise but thorough
- If you're not sure what they're asking about, ask for clarification"""

USER_PROMPT = """Explain the following message for someone who isn't familiar with the technical terms.

- Break down any jargon, acronyms, or technical concepts
- Use simple, plain English
- Keep it brief (2-3 short paragraphs max)
- If there's no jargon, just say so briefly

Message:
{text}"""


def get_explanation(text: str) -> str:
    """Get an explanation using available AI provider."""
    if AI_GATEWAY_API_KEY:
        return _explain_with_gateway(text)
    elif ANTHROPIC_API_KEY:
        return _explain_with_anthropic(text)
    else:
        return "No AI provider configured. Set `AI_GATEWAY_API_KEY` or `ANTHROPIC_API_KEY`."


def _explain_with_anthropic(text: str) -> str:
    """Use Anthropic's Claude API."""
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": USER_PROMPT.format(text=text)}]
    )
    return message.content[0].text


def _explain_with_gateway(text: str) -> str:
    """Use Vercel AI Gateway or any OpenAI-compatible API."""
    import openai
    client = openai.OpenAI(api_key=AI_GATEWAY_API_KEY, base_url=AI_GATEWAY_BASE_URL)
    response = client.chat.completions.create(
        model=AI_GATEWAY_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT.format(text=text)},
        ],
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()


def chat_response(messages: list) -> str:
    """Generate a conversational response given message history."""
    if AI_GATEWAY_API_KEY:
        import openai
        client = openai.OpenAI(api_key=AI_GATEWAY_API_KEY, base_url=AI_GATEWAY_BASE_URL)
        response = client.chat.completions.create(
            model=AI_GATEWAY_MODEL,
            messages=[{"role": "system", "content": CHAT_SYSTEM_PROMPT}] + messages,
            temperature=0.4,
        )
        return response.choices[0].message.content.strip()
    elif ANTHROPIC_API_KEY:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=CHAT_SYSTEM_PROMPT,
            messages=messages
        )
        return message.content[0].text
    else:
        return "No AI provider configured."


def format_explanation_blocks(original_text: str, explanation: str) -> list:
    """Format the explanation using Slack Block Kit."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Original message:*\n>{original_text[:500]}{'...' if len(original_text) > 500 else ''}"
            }
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Explanation:*\n{explanation}"
            }
        }
    ]


@app.shortcut("explain_jargon")
def handle_explain_jargon(ack, shortcut, client, logger):
    """Handle the 'Explain Jargon' message shortcut (private/ephemeral)."""
    ack()

    message = shortcut.get("message", {})
    text = message.get("text", "").strip()
    channel_id = shortcut.get("channel", {}).get("id")
    user_id = shortcut.get("user", {}).get("id")

    if not channel_id or not user_id:
        logger.error("Missing channel_id or user_id in shortcut payload")
        return

    if not text:
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text="I couldn't find any text to explain in that message."
        )
        return

    client.chat_postEphemeral(
        channel=channel_id,
        user=user_id,
        text=":hourglass_flowing_sand: Thinking..."
    )

    try:
        explanation = get_explanation(text)
        blocks = format_explanation_blocks(text, explanation)
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text=explanation,
            blocks=blocks
        )
    except Exception as e:
        logger.exception(f"Failed to generate explanation: {e}")
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text="Sorry, I had trouble generating an explanation. Please try again."
        )


@app.shortcut("explain_jargon_public")
def handle_explain_jargon_public(ack, shortcut, client, logger):
    """Handle the 'Explain Jargon (Public)' message shortcut - posts to channel."""
    ack()

    message = shortcut.get("message", {})
    text = message.get("text", "").strip()
    channel_id = shortcut.get("channel", {}).get("id")
    user_id = shortcut.get("user", {}).get("id")
    message_ts = message.get("ts")

    if not channel_id or not user_id:
        logger.error("Missing channel_id or user_id in shortcut payload")
        return

    if not text:
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text="I couldn't find any text to explain in that message."
        )
        return

    client.chat_postEphemeral(
        channel=channel_id,
        user=user_id,
        text=":hourglass_flowing_sand: Generating explanation for everyone..."
    )

    try:
        explanation = get_explanation(text)
        blocks = format_explanation_blocks(text, explanation)
        client.chat_postMessage(
            channel=channel_id,
            thread_ts=message_ts,
            text=explanation,
            blocks=blocks
        )
    except Exception as e:
        logger.exception(f"Failed to generate explanation: {e}")
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text="Sorry, I had trouble generating an explanation. Please try again."
        )


@app.event("reaction_added")
def handle_reaction(event, client, logger):
    """When user reacts with 💬, start a DM conversation about that message."""
    if event.get("reaction") != CHAT_TRIGGER_EMOJI:
        return

    user_id = event.get("user")
    item = event.get("item", {})
    channel_id = item.get("channel")
    message_ts = item.get("ts")

    if not all([user_id, channel_id, message_ts]):
        return

    try:
        result = client.conversations_history(
            channel=channel_id,
            latest=message_ts,
            limit=1,
            inclusive=True
        )
        messages = result.get("messages", [])
        if not messages:
            return

        original_text = messages[0].get("text", "")
        if not original_text:
            return

        dm = client.conversations_open(users=[user_id])
        dm_channel = dm["channel"]["id"]

        client.chat_postMessage(
            channel=dm_channel,
            text=(
                f"Hey! I saw you wanted to chat about this message:\n\n"
                f">{original_text[:500]}{'...' if len(original_text) > 500 else ''}\n\n"
                f"What would you like me to explain? Ask me anything!"
            )
        )
    except Exception as e:
        logger.exception(f"Failed to start DM conversation: {e}")


@app.event("message")
def handle_dm_message(event, client, logger):
    """Handle direct messages - have a conversation with the user."""
    if event.get("channel_type") != "im":
        return

    if event.get("bot_id") or event.get("subtype"):
        return

    user_id = event.get("user")
    channel_id = event.get("channel")
    user_message = event.get("text", "").strip()

    if not user_message:
        return

    try:
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
    except Exception as e:
        logger.exception(f"Failed to respond to DM: {e}")
        client.chat_postMessage(
            channel=channel_id,
            text="Sorry, I had trouble processing that. Could you try again?"
        )


@app.event("app_home_opened")
def handle_app_home(client, event, logger):
    """Show helpful info when user opens the App Home tab."""
    try:
        client.views_publish(
            user_id=event["user"],
            view={
                "type": "home",
                "blocks": [
                    {
                        "type": "header",
                        "text": {"type": "plain_text", "text": "Jargon Explainer"}
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "I help you understand technical jargon and acronyms in simple terms."
                        }
                    },
                    {"type": "divider"},
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                "*How to use:*\n"
                                "1. Find a message with confusing technical terms\n"
                                "2. Click the *three dots menu* (more actions) on the message\n"
                                "3. Choose an option:\n"
                                "   • *Explain Jargon* → private (only you see it)\n"
                                "   • *Explain Jargon (Public)* → posts to the channel"
                            )
                        }
                    },
                    {"type": "divider"},
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                "*Want to chat about it?*\n"
                                "React to any message with 💬 and I'll DM you so we can discuss it!"
                            )
                        }
                    }
                ]
            }
        )
    except Exception as e:
        logger.error(f"Error publishing home view: {e}")


# Starlette app for Vercel
handler = SlackRequestHandler(app)


async def slack_events(request: Request):
    return await handler.handle(request)


starlette_app = Starlette(
    routes=[Route("/api/slack", endpoint=slack_events, methods=["POST"])]
)

# Vercel entry point
app = starlette_app
