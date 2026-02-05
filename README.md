# Slack Jargon Explainer

A Slack app that explains technical jargon in simple language using AI.

## Features

- **Message shortcut** - Right-click any message to get an explanation
- **Private responses** - Only you see the explanation (ephemeral messages)
- **Flexible AI** - Works with Vercel AI Gateway, Anthropic, or any OpenAI-compatible API
- **Socket Mode** - No public URL needed for local development
- **Nice formatting** - Uses Slack Block Kit for clean output

## How It Works

1. See a message with confusing technical jargon
2. Click the three dots menu on the message
3. Select "Explain Jargon"
4. Get a private explanation in simple terms

## Quick Start

### 1. Create a Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Click **Create New App** > **From scratch**
3. Name it "Jargon Explainer" and select your workspace

### 2. Configure the App

**Enable Socket Mode:**
1. Go to **Socket Mode** in sidebar
2. Toggle **Enable Socket Mode** ON
3. Create an app-level token with `connections:write` scope
4. Save the token (starts with `xapp-`)

**Add Bot Scopes:**
1. Go to **OAuth & Permissions**
2. Under **Bot Token Scopes**, add:
   - `chat:write`

**Create the Message Shortcut:**
1. Go to **Interactivity & Shortcuts**
2. Toggle **Interactivity** ON
3. Click **Create New Shortcut** > **On messages**
4. Set:
   - Name: `Explain Jargon`
   - Description: `Explain technical terms in this message`
   - Callback ID: `explain_jargon`

**Enable App Home (optional):**
1. Go to **App Home**
2. Toggle **Home Tab** ON

**Install to Workspace:**
1. Go to **Install App**
2. Click **Install to Workspace**
3. Copy the **Bot User OAuth Token** (starts with `xoxb-`)

### 3. Run the App

```bash
# Clone and enter directory
git clone <repo-url>
cd Explain-me

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your tokens

# Run
python app.py
```

You should see: `Starting Jargon Explainer...`

## Configuration

Set these in your `.env` file:

```bash
# Required - Slack credentials
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...

# AI Provider - choose one:

# Option 1: Vercel AI Gateway (recommended)
AI_GATEWAY_API_KEY=your-vercel-key
AI_GATEWAY_MODEL=anthropic/claude-sonnet-4-20250514  # or openai/gpt-4o, etc.

# Option 2: Direct Anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

### Vercel AI Gateway Models

Use the `provider/model` format:
- `anthropic/claude-sonnet-4-20250514`
- `openai/gpt-4o`
- `google/gemini-2.0-flash`
- `xai/grok-3`

Get your API key at [vercel.com/dashboard](https://vercel.com/dashboard) → AI → Gateway

## Project Structure

```
.
├── app.py              # Main application (single file)
├── requirements.txt    # Python dependencies
├── .env.example        # Environment template
└── README.md
```

## For Your Org

**Good news:** Once the app is running, **everyone in your Slack workspace can use it** - they don't need their own tokens or setup.

Here's how it works:
- **You (the admin)** set up and run the bot with the tokens in `.env`
- **Your teammates** just use the Slack shortcuts - no config needed on their end
- The Slack tokens authenticate the *bot*, not individual users

**For other developers** who want to run their own instance or contribute:
1. Clone the repo
2. Copy `.env.example` to `.env`
3. Get their own Slack app tokens (see setup above)
4. Fill in their `.env` file
5. Run `python app.py`

The `.env` file is gitignored, so tokens stay local and never get committed.

## Deployment

For production, you can deploy to any Python-friendly platform:

- **Railway** / **Render** - Easy Python deployment
- **Heroku** - Add a `Procfile`: `web: python app.py`
- **Docker** - Containerize with a simple Dockerfile
- **Any VPS** - Just run `python app.py` with a process manager

Remember to set environment variables in your hosting platform.

## License

MIT
