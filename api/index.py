from flask import Flask, request, jsonify, make_response

app = Flask(__name__)

_handler = None


def get_handler():
    global _handler
    if _handler is None:
        from slack_bolt.adapter.flask import SlackRequestHandler
        from slack_app import app as slack_app
        _handler = SlackRequestHandler(slack_app)
    return _handler


@app.route("/api/health", methods=["GET"])
def health_check():
    return {"ok": True}


@app.route("/api/slack/events", methods=["POST"])
@app.route("/api", methods=["POST"])
def slack_events():
    body = request.get_json(silent=True) or {}

    # Handle Slack URL verification challenge directly
    if body.get("type") == "url_verification":
        return jsonify({"challenge": body.get("challenge")})

    return get_handler().handle(request)
