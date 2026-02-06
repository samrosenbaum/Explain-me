"""
ELI5 - Explains technical terms in simple language for Vercel employees.

Supports Vercel AI Gateway, direct Anthropic, or any OpenAI-compatible API.
"""

import os
import re
import base64
import urllib.request
from slack_bolt import App

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# AI Provider config
# Option 1: Vercel AI Gateway (recommended) - set AI_GATEWAY_API_KEY
# Option 2: Direct Anthropic - set ANTHROPIC_API_KEY
# Option 3: Any OpenAI-compatible API - set AI_GATEWAY_API_KEY + AI_GATEWAY_BASE_URL
AI_GATEWAY_API_KEY = os.environ.get("AI_GATEWAY_API_KEY")
AI_GATEWAY_BASE_URL = os.environ.get(
    "AI_GATEWAY_BASE_URL", "https://ai-gateway.vercel.sh/v1"
)
AI_GATEWAY_MODEL = os.environ.get(
    "AI_GATEWAY_MODEL", "anthropic/claude-sonnet-4-20250514"
)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# Slack config
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")

if not SLACK_BOT_TOKEN or not SLACK_SIGNING_SECRET:
    raise RuntimeError(
        "Missing Slack credentials. Set SLACK_BOT_TOKEN and SLACK_SIGNING_SECRET."
    )

app = App(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)

# Emojis that trigger DM chat (user reacts with any of these to start a conversation)
CHAT_TRIGGER_EMOJIS = {"speech_balloon", "eli5"}  # 💬 or custom :eli5: emoji

SYSTEM_PROMPT = """You are ELI5, a friendly explainer bot for employees at Vercel.

Vercel is a cloud platform for frontend developers. Key products and terms employees discuss:
- Vercel Platform: Deploys frontend apps with serverless functions, edge network, automatic HTTPS
- Next.js: React framework (created by Vercel) for SSR, SSG, ISR, App Router, Server Components
- v0: AI-powered UI generation tool that creates React components from prompts
- Turbopack: Rust-based bundler (successor to Webpack), used in Next.js dev server
- Turborepo: Monorepo build tool with remote caching
- Edge Functions / Edge Middleware: Code that runs at the CDN edge (not origin)
- Serverless Functions: Backend code that scales to zero, runs on-demand
- ISR (Incremental Static Regeneration): Revalidates static pages without full rebuild
- AI SDK: Vercel's TypeScript toolkit for building AI-powered applications
- AI Gateway: Unified API endpoint routing to 100+ models across providers. Provides automatic provider fallback when primary fails, request/response passthrough with no markup on BYOK pricing, and a dashboard showing Requests by Model, TTFT, Token Counts, and Spend
- DPS (Data Processing Service), KV, Postgres, Blob: Vercel storage products
- Conformance: Enterprise code quality/governance tool
- Vercel Firewall / WAF: Web application firewall and DDoS protection

You explain technical concepts in simple, friendly terms. Be concise. You understand Vercel's products deeply and can relate jargon to how Vercel uses it internally."""

CHAT_SYSTEM_PROMPT = """You are ELI5, a friendly technical explainer for Vercel employees helping them understand jargon and technical concepts.

You know Vercel's products well: Next.js, v0, Turbopack, Turborepo, Edge Functions, Serverless Functions, ISR, AI SDK, KV, Postgres, Blob, Conformance, Firewall/WAF, and more.

- Explain things in simple, plain English
- Be conversational and helpful
- If they ask follow-up questions, build on what you've already explained
- Keep responses concise but thorough
- If you're not sure what they're asking about, ask for clarification"""

USER_PROMPT = """Explain the following message for someone who isn't familiar with the technical terms.

Structure your response with these sections (use the exact headers with bold markdown):

*TLDR*
A one or two sentence version that a 5-year-old could understand.

*Here's What It Means*
Rewrite the message in plain English so anyone can understand it.

*Technical Terms*
List the technical terms used and briefly define each one.

*Abbreviations*
List any abbreviations or acronyms and what they stand for. If there are none, skip this section entirely.

Message:
{text}"""


IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}


def fetch_url_content(url: str) -> str:
    """Fetch a URL and return plain text content (HTML tags stripped)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ELI5-SlackBot/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        # Strip HTML tags
        text = re.sub(r"<[^>]+>", " ", raw)
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text[:2000]
    except Exception:
        return ""


def download_slack_image(file_info, client):
    """Download an image file from Slack and return base64 data + mime type."""
    mime = file_info.get("mimetype", "")
    if mime not in IMAGE_MIME_TYPES:
        return None
    url = file_info.get("url_private_download") or file_info.get("url_private")
    if not url:
        return None
    try:
        req = urllib.request.Request(
            url, headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
        return {"base64": base64.b64encode(data).decode(), "mime_type": mime}
    except Exception:
        return None


def extract_message_text(message: dict, client=None):
    """Extract text and images from a message.

    Returns (text, images) where images is a list of {"base64": ..., "mime_type": ...}.
    """
    text = message.get("text", "").strip()

    # Pull text from Slack link unfurls and attachments
    attachment_parts = []
    for att in message.get("attachments", []):
        for field in ("text", "pretext", "title"):
            val = att.get(field, "")
            if val and val not in text:
                attachment_parts.append(val)

    if attachment_parts:
        text = text + "\n\n" + "\n\n".join(attachment_parts)

    # Fetch content from URLs in the message
    urls = re.findall(r"https?://\S+", text)
    for url in urls[:3]:  # Limit to 3 URLs
        url = url.rstrip(">|)")  # Clean Slack formatting artifacts
        if "slack.com" in url:
            continue
        content = fetch_url_content(url)
        if content:
            text += f"\n\n[Content from {url}]:\n{content}"

    # Download images from file attachments
    images = []
    if client:
        for f in message.get("files", []):
            img = download_slack_image(f, client)
            if img:
                images.append(img)

    return text, images


def get_explanation(text, images=None):
    """Get an explanation using available AI provider (Vercel AI Gateway preferred)."""

    if not AI_GATEWAY_API_KEY and not ANTHROPIC_API_KEY:
        return (
            "No AI provider configured. "
            "Set `AI_GATEWAY_API_KEY` (for Vercel AI Gateway) or `ANTHROPIC_API_KEY`."
        )

    # Try with images first, fall back to text-only if image processing fails
    if images:
        try:
            if AI_GATEWAY_API_KEY:
                return _explain_with_gateway(text, images)
            return _explain_with_anthropic(text, images)
        except Exception:
            pass  # Retry without images below

    if AI_GATEWAY_API_KEY:
        return _explain_with_gateway(text)
    return _explain_with_anthropic(text)


def _build_user_content(text, images=None, provider="openai"):
    """Build the user message content array with text and optional images."""
    prompt_text = USER_PROMPT.format(text=text)

    if not images:
        return prompt_text

    # Multimodal: include images before the text prompt
    content = []
    for img in images:
        if provider == "anthropic":
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": img["mime_type"],
                    "data": img["base64"],
                },
            })
        else:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{img['mime_type']};base64,{img['base64']}",
                },
            })
    content.append({"type": "text", "text": prompt_text})
    return content


def _explain_with_anthropic(text, images=None):
    """Use Anthropic's Claude API."""
    import anthropic

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    user_content = _build_user_content(text, images, provider="anthropic")

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    return message.content[0].text


def _explain_with_gateway(text, images=None):
    """Use Vercel AI Gateway or any OpenAI-compatible API."""
    import openai

    client = openai.OpenAI(api_key=AI_GATEWAY_API_KEY, base_url=AI_GATEWAY_BASE_URL)
    user_content = _build_user_content(text, images, provider="openai")

    response = client.chat.completions.create(
        model=AI_GATEWAY_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
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
    if ANTHROPIC_API_KEY:
        import anthropic

        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=CHAT_SYSTEM_PROMPT,
            messages=messages,
        )
        return message.content[0].text
    return "No AI provider configured."


def split_explanation_blocks(explanation: str) -> list:
    """Split explanation into Slack blocks, respecting the 3000-char limit per block."""
    blocks = []
    # Split on section headers like *TLDR*, *Technical Terms*, *Abbreviations*, etc.
    sections = re.split(r"(?=\*(?:TLDR|Technical Terms|Abbreviations|Here's What It Means)\*)", explanation)
    for section in sections:
        section = section.strip()
        if not section:
            continue
        # If a section is still too long, chunk it
        while len(section) > 2900:
            # Find a good break point
            cut = section.rfind("\n", 0, 2900)
            if cut < 100:
                cut = 2900
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": section[:cut]},
            })
            section = section[cut:].strip()
        if section:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": section},
            })
    return blocks


def format_explanation_blocks(original_text: str, explanation: str) -> list:
    """Format the explanation nicely using Slack Block Kit."""
    preview = f"{original_text[:500]}{'...' if len(original_text) > 500 else ''}"
    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Original message:*\n>{preview}"},
        },
        {"type": "divider"},
    ]
    blocks.extend(split_explanation_blocks(explanation))
    return blocks


LOADING_MESSAGES = [
    ":robot_face: Beep boop bop... translating the tech speak...",
    ":robot_face: Beep boop... consulting my jargon-to-English dictionary...",
    ":robot_face: Boop beep bop... decoding the tech speak...",
    ":robot_face: Beep boop... did you know the first computer bug was an actual moth? Anyway, thinking...",
    ":robot_face: Boop boop beep... fun fact: 'HTTP' stands for HyperText Transfer Protocol. Now let me explain the rest...",
    ":robot_face: Beep bop... fun fact: the first 1GB hard drive weighed 550 pounds. Translating your message...",
    ":robot_face: Beep boop bop... crunching the jargon into bite-sized pieces...",
    ":robot_face: Boop beep... warming up my explain-o-tron 3000...",
]


def open_loading_modal(client, trigger_id):
    """Open a modal with a loading state. Returns the view ID for updating later."""
    import random
    loading_msg = random.choice(LOADING_MESSAGES)
    result = client.views_open(
        trigger_id=trigger_id,
        view={
            "type": "modal",
            "title": {"type": "plain_text", "text": "ELI5 at your service"},
            "close": {"type": "plain_text", "text": "Close"},
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": loading_msg},
                },
            ],
        },
    )
    return result["view"]["id"]


def build_modal_metadata(original_text, conversation=None):
    """Build private_metadata JSON for the modal. Stays under 3000 char limit."""
    import json as _json
    data = {
        "original_text": original_text[:800],
        "conversation": conversation or [],
    }
    result = _json.dumps(data)
    # Truncate conversation if metadata is too long
    while len(result) > 2900 and data["conversation"]:
        data["conversation"].pop(0)
        result = _json.dumps(data)
    return result


def build_explanation_modal_view(original_text, explanation, conversation=None):
    """Build the modal view dict with explanation, follow-up Q&A, and input field."""
    preview = f"{original_text[:500]}{'...' if len(original_text) > 500 else ''}"
    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Original message:*\n>{preview}"},
        },
        {"type": "divider"},
    ]
    blocks.extend(split_explanation_blocks(explanation))

    # Show previous follow-up Q&A
    if conversation:
        for entry in conversation:
            if entry.get("role") == "user":
                blocks.append({"type": "divider"})
                blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*You asked:* {entry['content']}"},
                })
            elif entry.get("role") == "assistant":
                blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": entry["content"]},
                })

    blocks.append({"type": "divider"})
    blocks.append({
        "type": "input",
        "block_id": "followup_block",
        "optional": True,
        "element": {
            "type": "plain_text_input",
            "action_id": "followup_input",
            "placeholder": {"type": "plain_text", "text": "Ask a follow-up question..."},
        },
        "label": {"type": "plain_text", "text": "Want to dig deeper?"},
    })

    metadata = build_modal_metadata(original_text, conversation)

    return {
        "type": "modal",
        "callback_id": "eli5_followup",
        "notify_on_close": True,
        "title": {"type": "plain_text", "text": "ELI5 at your service"},
        "submit": {"type": "plain_text", "text": "Ask"},
        "close": {"type": "plain_text", "text": "Done"},
        "private_metadata": metadata,
        "blocks": blocks,
    }


def update_modal_with_explanation(client, view_id, original_text: str, explanation: str):
    """Update an existing modal with the explanation."""
    view = build_explanation_modal_view(original_text, explanation)
    client.views_update(view_id=view_id, view=view)


def handle_explain_jargon_ack(ack):
    ack()


def handle_explain_jargon_lazy(shortcut, client, logger):
    """Handle the 'Explain Jargon' message shortcut (private - opens a modal)."""
    message = shortcut.get("message", {})
    text, images = extract_message_text(message, client=client)
    trigger_id = shortcut.get("trigger_id")

    # Open modal immediately (trigger_id expires in 3s)
    view_id = open_loading_modal(client, trigger_id)

    if not text and not images:
        client.views_update(
            view_id=view_id,
            view={
                "type": "modal",
                "title": {"type": "plain_text", "text": "ELI5 at your service"},
                "close": {"type": "plain_text", "text": "Close"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": "I couldn't find any text to explain in that message."},
                    }
                ],
            },
        )
        return

    try:
        explanation = get_explanation(text, images)
        update_modal_with_explanation(client, view_id, text, explanation)
    except Exception as exc:
        logger.exception(f"Failed to generate explanation: {exc}")
        client.views_update(
            view_id=view_id,
            view={
                "type": "modal",
                "title": {"type": "plain_text", "text": "ELI5 at your service"},
                "close": {"type": "plain_text", "text": "Close"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": "Sorry, I had trouble generating an explanation. Please try again."},
                    }
                ],
            },
        )


app.shortcut("explain_jargon")(
    ack=handle_explain_jargon_ack,
    lazy=[handle_explain_jargon_lazy],
)


def handle_explain_jargon_public_ack(ack):
    ack()


def handle_explain_jargon_public_lazy(shortcut, client, logger):
    """Handle the 'Explain Jargon (Public)' message shortcut - posts to channel."""
    message = shortcut.get("message", {})
    text, images = extract_message_text(message, client=client)
    channel_id = shortcut.get("channel", {}).get("id")
    message_ts = message.get("ts")
    trigger_id = shortcut.get("trigger_id")

    # Open modal immediately as loading indicator
    view_id = open_loading_modal(client, trigger_id)

    if not text and not images:
        client.views_update(
            view_id=view_id,
            view={
                "type": "modal",
                "title": {"type": "plain_text", "text": "ELI5 at your service"},
                "close": {"type": "plain_text", "text": "Close"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": "I couldn't find any text to explain in that message."},
                    }
                ],
            },
        )
        return

    try:
        explanation = get_explanation(text, images)
        blocks = format_explanation_blocks(text, explanation)

        # Try to post publicly to the channel
        client.chat_postMessage(
            channel=channel_id,
            thread_ts=message_ts,
            text=explanation,
            blocks=blocks,
        )
        # Close the loading modal on success
        client.views_update(
            view_id=view_id,
            view={
                "type": "modal",
                "title": {"type": "plain_text", "text": "ELI5 at your service"},
                "close": {"type": "plain_text", "text": "Close"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": ":white_check_mark: Explanation posted to the channel!"},
                    }
                ],
            },
        )
    except Exception as exc:
        if "not_in_channel" in str(exc):
            # Bot isn't in the channel — show explanation in the modal instead
            logger.info("Bot not in channel, falling back to modal")
            update_modal_with_explanation(client, view_id, text, explanation)
        else:
            logger.exception(f"Failed to generate explanation: {exc}")
            client.views_update(
                view_id=view_id,
                view={
                    "type": "modal",
                    "title": {"type": "plain_text", "text": "ELI5 at your service"},
                    "close": {"type": "plain_text", "text": "Close"},
                    "blocks": [
                        {
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": "Sorry, I had trouble generating an explanation. Please try again."},
                        }
                    ],
                },
            )


app.shortcut("explain_jargon_public")(
    ack=handle_explain_jargon_public_ack,
    lazy=[handle_explain_jargon_public_lazy],
)


@app.action("chat_about_this")
def handle_chat_button(ack, body, client, logger):
    """Handle the 'Chat about this' button click in the modal."""
    import json as _json

    ack()
    user_id = body.get("user", {}).get("id")
    view = body.get("view", {})
    metadata = view.get("private_metadata", "{}")

    try:
        data = _json.loads(metadata)
        original_text = data.get("original_text", "")
    except Exception:
        original_text = ""

    if not user_id:
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
    except Exception as exc:
        logger.exception(f"Failed to open DM from modal button: {exc}")


@app.event("reaction_added")
def handle_reaction(event, client, logger):
    """When user reacts with 💬 or :eli5:, start a DM conversation about that message."""
    if event.get("reaction") not in CHAT_TRIGGER_EMOJIS:
        return

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

        client.chat_postMessage(
            channel=dm_channel,
            text=(
                "Hey! I saw you wanted to chat about this message:\n\n"
                f">{original_text[:500]}{'...' if len(original_text) > 500 else ''}\n\n"
                "What would you like me to explain? Ask me anything!"
            ),
        )
    except Exception as exc:
        logger.exception(f"Failed to start DM conversation: {exc}")


SLACK_MESSAGE_LINK_RE = re.compile(
    r"https?://[a-zA-Z0-9\-]+\.slack\.com/archives/([A-Z0-9]+)/p(\d+)"
)


def fetch_slack_message(client, link_match):
    """Fetch the text of a Slack message from a message link."""
    channel_id = link_match.group(1)
    # Slack encodes ts as digits without dot; e.g. p1234567890123456 -> 1234567890.123456
    raw_ts = link_match.group(2)
    message_ts = raw_ts[:10] + "." + raw_ts[10:]
    try:
        result = client.conversations_history(
            channel=channel_id, latest=message_ts, limit=1, inclusive=True
        )
        msgs = result.get("messages", [])
        if msgs:
            return msgs[0].get("text", "")
    except Exception:
        pass
    return None


@app.event("message")
def handle_dm_message(event, client, logger):
    """Handle direct messages - have a conversation with the user."""
    if event.get("channel_type") != "im":
        return

    if event.get("bot_id") or event.get("subtype"):
        return

    channel_id = event.get("channel")
    user_message = event.get("text", "").strip()

    if not user_message:
        return

    try:
        # Check if the user pasted a Slack message link
        link_match = SLACK_MESSAGE_LINK_RE.search(user_message)
        if link_match:
            linked_text = fetch_slack_message(client, link_match)
            if linked_text:
                # Give them an explanation of the linked message
                explanation = get_explanation(linked_text)
                client.chat_postMessage(
                    channel=channel_id,
                    text=(
                        f"Here's that message:\n>{linked_text[:500]}{'...' if len(linked_text) > 500 else ''}\n\n"
                        f"{explanation}\n\n"
                        "Feel free to ask me follow-up questions!"
                    ),
                )
                return
            else:
                client.chat_postMessage(
                    channel=channel_id,
                    text="I couldn't fetch that message. I might not have access to that channel. Try copying the message text and sending it to me directly!",
                )
                return

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
        logger.exception(f"Failed to respond to DM: {exc}")
        client.chat_postMessage(
            channel=channel_id,
            text="Sorry, I had trouble processing that. Could you try again?",
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
                        "text": {"type": "plain_text", "text": "ELI5 at your service"},
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                "I help you understand technical terms, acronyms, "
                                "and complex concepts in simple language."
                            ),
                        },
                    },
                    {"type": "divider"},
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                "*How to use:*\n"
                                "1. Find a message with confusing technical terms\n"
                                "2. Click the *three dots menu* (more actions) "
                                "on the message\n"
                                "3. Choose *ELI5* to get an explanation\n"
                                "I can also read images and links in messages!"
                            ),
                        },
                    },
                    {"type": "divider"},
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                "*Want to chat about it?*\n"
                                "• Click the *Chat about this* button in the explanation\n"
                                "• React to any message with :eli5: or :speech_balloon:\n"
                                "• Or just DM me directly! Paste a Slack message link and I'll explain it"
                            ),
                        },
                    },
                ],
            },
        )
    except Exception as exc:
        logger.error(f"Error publishing home view: {exc}")
