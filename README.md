# Slack Jargon Explainer

A Slack app that explains technical jargon, acronyms, and complex terms in simple language using Claude AI.

## Features

- **Message Shortcut**: Right-click any message to get an explanation of technical terms
- **Private Responses**: Explanations are sent as ephemeral messages (only you can see them)
- **Context-Aware**: Understands technical concepts across various domains
- **Slack-Formatted**: Responses are formatted nicely for Slack

## How It Works

1. You see a message with confusing technical jargon
2. Click the three dots menu (⋮) on the message
3. Select "Explain Jargon"
4. The app sends you a private explanation breaking down the technical terms

## Setup

### Prerequisites

- Node.js 18 or higher
- A Slack workspace where you can install apps
- An Anthropic API key

### 1. Create a Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Click "Create New App" → "From scratch"
3. Name it "Jargon Explainer" and select your workspace

### 2. Configure the Slack App

#### Enable Socket Mode
1. Go to "Socket Mode" in the sidebar
2. Toggle "Enable Socket Mode" ON
3. Create an app-level token with `connections:write` scope
4. Save the token (starts with `xapp-`)

#### Add Bot Scopes
1. Go to "OAuth & Permissions"
2. Under "Bot Token Scopes", add:
   - `chat:write` - Send messages
   - `commands` - Use shortcuts

#### Create the Message Shortcut
1. Go to "Interactivity & Shortcuts"
2. Toggle "Interactivity" ON
3. Click "Create New Shortcut" → "On messages"
4. Configure:
   - Name: `Explain Jargon`
   - Short Description: `Explain technical terms in this message`
   - Callback ID: `explain_jargon`
5. Save

#### Enable App Home (Optional)
1. Go to "App Home"
2. Toggle "Home Tab" ON

#### Install to Workspace
1. Go to "Install App"
2. Click "Install to Workspace"
3. Authorize the app
4. Copy the "Bot User OAuth Token" (starts with `xoxb-`)

### 3. Configure Environment

```bash
# Clone the repository
git clone <your-repo-url>
cd slack-jargon-explainer

# Install dependencies
npm install

# Create environment file
cp .env.example .env
```

Edit `.env` with your credentials:
```
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_SIGNING_SECRET=your-signing-secret
SLACK_APP_TOKEN=xapp-your-app-token
ANTHROPIC_API_KEY=sk-ant-your-api-key
```

### 4. Run the App

```bash
# Development mode
npm run dev

# Or build and run production
npm run build
npm start
```

You should see: `⚡️ Jargon Explainer is running on port 3000!`

## Usage

1. Go to any channel in your Slack workspace
2. Find a message with technical jargon
3. Click the ⋮ menu on the message
4. Select "Explain Jargon" from the shortcuts
5. You'll receive a private explanation!

## Project Structure

```
├── src/
│   ├── app.ts              # Main application entry point
│   ├── handlers/
│   │   └── explainJargon.ts # Message shortcut handler
│   └── services/
│       └── claude.ts       # Claude API integration
├── package.json
├── tsconfig.json
├── .env.example
└── README.md
```

## Deployment

For production deployment, consider:

- **Heroku**: Easy deployment with `Procfile`
- **Railway**: Simple Node.js deployment
- **AWS Lambda**: Serverless option (requires code changes)
- **Docker**: Containerized deployment

Make sure to set environment variables in your hosting platform.

## Troubleshooting

**"Shortcut not appearing"**
- Make sure the app is installed to your workspace
- Check that the callback ID matches exactly: `explain_jargon`
- Try refreshing Slack

**"Connection errors"**
- Verify Socket Mode is enabled
- Check that SLACK_APP_TOKEN is correct
- Ensure the app-level token has `connections:write` scope

**"AI errors"**
- Verify your ANTHROPIC_API_KEY is valid
- Check API usage limits

## License

MIT
