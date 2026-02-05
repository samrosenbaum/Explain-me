# Slack Jargon Explainer

A Slack app that explains technical jargon in simple language using AI. Deploys to Vercel.

## Features

- **Message shortcut** - Right-click any message to get an explanation
- **Private or public** - Get explanations just for you, or share with the channel
- **Chat mode** - React with 💬 to start a DM conversation about any message
- **Vercel AI Gateway** - Uses your existing AI Gateway setup

## How It Works

1. See a message with confusing technical jargon
2. Click the three dots menu on the message
3. Select "Explain Jargon" (private) or "Explain Jargon (Public)"
4. Get an explanation in simple terms

## Deploy to Vercel

### 1. Create a Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Click **Create New App** > **From scratch**
3. Name it "Jargon Explainer" and select your workspace

### 2. Configure the Slack App

**Add Bot Scopes:**
1. Go to **OAuth & Permissions**
2. Under **Bot Token Scopes**, add:
   - `chat:write`
   - `channels:history`
   - `groups:history`
   - `im:history`
   - `mpim:history`
   - `reactions:read`

**Create Message Shortcuts:**
1. Go to **Interactivity & Shortcuts**
2. Toggle **Interactivity** ON
3. Create two shortcuts (both **On messages**):

   | Name | Callback ID |
   |------|-------------|
   | Explain Jargon | `explain_jargon` |
   | Explain Jargon (Public) | `explain_jargon_public` |

**Subscribe to Events:**
1. Go to **Event Subscriptions**
2. Toggle **Enable Events** ON
3. Under **Subscribe to bot events**, add:
   - `message.im`
   - `reaction_added`
   - `app_home_opened`

**Get your credentials:**
- **Bot Token**: OAuth & Permissions → Bot User OAuth Token (`xoxb-...`)
- **Signing Secret**: Basic Information → App Credentials → Signing Secret

### 3. Deploy to Vercel

```bash
git clone <repo-url>
cd Explain-me
vercel
```

Add these environment variables in your Vercel project settings:

| Variable | Value |
|----------|-------|
| `SLACK_BOT_TOKEN` | `xoxb-...` from OAuth & Permissions |
| `SLACK_SIGNING_SECRET` | From Basic Information → App Credentials |
| `AI_GATEWAY_API_KEY` | Your Vercel AI Gateway key |

### 4. Connect Slack to Vercel

After deploying, copy your Vercel URL and update these in your Slack app:

1. **Interactivity & Shortcuts** → Request URL:
   ```
   https://your-app.vercel.app/api/slack/events
   ```

2. **Event Subscriptions** → Request URL:
   ```
   https://your-app.vercel.app/api/slack/events
   ```

3. **Reinstall the app** to your workspace (Install App → Reinstall)

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SLACK_BOT_TOKEN` | Yes | Bot token from OAuth & Permissions |
| `SLACK_SIGNING_SECRET` | Yes | From Basic Information → App Credentials |
| `AI_GATEWAY_API_KEY` | Yes | Vercel AI Gateway API key |
| `AI_GATEWAY_MODEL` | No | Model to use (default: `anthropic/claude-sonnet-4-20250514`) |

### Available Models

- `anthropic/claude-sonnet-4-20250514`
- `openai/gpt-4o`
- `openai/gpt-4o-mini`
- `google/gemini-2.0-flash`

## Local Development

For local testing with Socket Mode:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

export SLACK_BOT_TOKEN=xoxb-...
export SLACK_SIGNING_SECRET=...
export SLACK_APP_TOKEN=xapp-...  # Socket Mode only
export AI_GATEWAY_API_KEY=...

python app.py
```

## Project Structure

```
.
├── api/
│   └── index.py        # Vercel serverless function
├── slack_app.py        # Core app logic (shared)
├── app.py              # Socket Mode runner (local dev)
├── vercel.json         # Vercel configuration
├── requirements.txt    # Python dependencies
└── .env.example        # Environment template
```

## License

MIT
