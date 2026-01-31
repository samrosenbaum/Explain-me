import {
  AllMiddlewareArgs,
  SlackShortcutMiddlewareArgs,
  MessageShortcut,
} from "@slack/bolt";
import { explainJargon } from "../services/claude";

type MessageShortcutArgs = SlackShortcutMiddlewareArgs<MessageShortcut> &
  AllMiddlewareArgs;

export async function handleExplainJargon({
  shortcut,
  ack,
  client,
  logger,
}: MessageShortcutArgs): Promise<void> {
  await ack();

  const messageText = shortcut.message.text;

  if (!messageText) {
    await client.chat.postEphemeral({
      channel: shortcut.channel.id,
      user: shortcut.user.id,
      text: "⚠️ This message doesn't contain any text to explain.",
    });
    return;
  }

  try {
    // Send a loading message
    await client.chat.postEphemeral({
      channel: shortcut.channel.id,
      user: shortcut.user.id,
      text: "🔍 Analyzing the text for technical jargon...",
    });

    // Get explanation from Claude
    const explanation = await explainJargon(messageText);

    // Send the explanation as an ephemeral message (only visible to the user)
    await client.chat.postEphemeral({
      channel: shortcut.channel.id,
      user: shortcut.user.id,
      blocks: [
        {
          type: "section",
          text: {
            type: "mrkdwn",
            text: "*📚 Jargon Explanation*",
          },
        },
        {
          type: "divider",
        },
        {
          type: "section",
          text: {
            type: "mrkdwn",
            text: `*Original text:*\n>${messageText.split("\n").join("\n>")}`,
          },
        },
        {
          type: "divider",
        },
        {
          type: "section",
          text: {
            type: "mrkdwn",
            text: `*Explanation:*\n${explanation}`,
          },
        },
      ],
      text: `Explanation: ${explanation}`, // Fallback for notifications
    });
  } catch (error) {
    logger.error("Error explaining jargon:", error);

    await client.chat.postEphemeral({
      channel: shortcut.channel.id,
      user: shortcut.user.id,
      text: "❌ Sorry, I encountered an error while trying to explain this text. Please try again later.",
    });
  }
}
