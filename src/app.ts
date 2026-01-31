import "dotenv/config";
import { App, LogLevel } from "@slack/bolt";
import { handleExplainJargon } from "./handlers/explainJargon";

// Initialize the Slack app
const app = new App({
  token: process.env.SLACK_BOT_TOKEN,
  signingSecret: process.env.SLACK_SIGNING_SECRET,
  socketMode: true,
  appToken: process.env.SLACK_APP_TOKEN,
  logLevel:
    process.env.NODE_ENV === "production" ? LogLevel.INFO : LogLevel.DEBUG,
});

// Register the message shortcut for explaining jargon
// This creates a right-click menu option on messages
app.shortcut("explain_jargon", handleExplainJargon);

// Health check endpoint (useful for monitoring)
app.event("app_home_opened", async ({ event, client }) => {
  try {
    await client.views.publish({
      user_id: event.user,
      view: {
        type: "home",
        blocks: [
          {
            type: "section",
            text: {
              type: "mrkdwn",
              text: "*Welcome to Jargon Explainer! 📚*",
            },
          },
          {
            type: "section",
            text: {
              type: "mrkdwn",
              text: "I help you understand technical jargon and acronyms in simple terms.",
            },
          },
          {
            type: "divider",
          },
          {
            type: "section",
            text: {
              type: "mrkdwn",
              text: "*How to use:*\n1. Find a message with confusing technical terms\n2. Click the three dots menu (⋮) on the message\n3. Select *Explain Jargon*\n4. I'll send you a private explanation!",
            },
          },
          {
            type: "section",
            text: {
              type: "mrkdwn",
              text: "_The explanation is only visible to you, so don't worry about asking!_",
            },
          },
        ],
      },
    });
  } catch (error) {
    console.error("Error publishing home view:", error);
  }
});

// Start the app
(async () => {
  const port = process.env.PORT || 3000;
  await app.start(port);
  console.log(`⚡️ Jargon Explainer is running on port ${port}!`);
})();
