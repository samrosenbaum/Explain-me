# Explain-me Slack App

A Slack app that lets you highlight a message and get a plain-English explanation of technical jargon.

## How it works
- Adds a **message shortcut** called **Explain jargon**.
- When you invoke it on a message, the app sends the message text to the OpenAI API and responds with a short, simple explanation.
- The response is posted as an ephemeral message so only you can see it.

## Setup
1. **Create a Slack app** at https://api.slack.com/apps.
2. **Enable Interactivity** and set the Request URL to `https://<your-domain>/slack/events`.
3. **Create a message shortcut** named “Explain jargon” with callback ID `explain_jargon`.
4. **Add OAuth scopes**:
   - `commands`
   - `chat:write`
   - `chat:write.public` (optional)
   - `groups:read` (optional)
   - `channels:read` (optional)
5. **Install the app** to your workspace and copy the bot token.

## Local development
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Populate `.env` with your Slack and OpenAI credentials, then run:
```bash
export $(cat .env | xargs)
python app.py
```

## Deployment notes
- Run behind a public HTTPS URL (e.g., via ngrok, Cloud Run, or a load balancer).
- Set the Slack Request URL to `https://<host>/slack/events`.
- Optionally set `OPENAI_MODEL` to any model available to your API key.

## Security
- Keep `SLACK_SIGNING_SECRET` and API keys in secure storage.
- Limit the app to internal workspaces only.
