"""Socket Mode runner for local development."""

from slack_bolt.adapter.socket_mode import SocketModeHandler

from slack_app import SLACK_APP_TOKEN, app

if __name__ == "__main__":
    if not SLACK_APP_TOKEN:
        raise RuntimeError("Missing Slack app token. Set SLACK_APP_TOKEN for Socket Mode.")
    print("Starting Jargon Explainer (Socket Mode)...")
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()
