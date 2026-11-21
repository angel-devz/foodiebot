"""FoodieBot web service.

Routes
  GET  /                 FoodieBot website with the chat widget embedded
  GET  /dashboard        analytics dashboard
  POST /api/chat         {"message": "...", "session_id": "..."} -> bot reply
  POST /api/feedback     {"message_id": 1, "helpful": true}
  GET  /api/stats        analytics JSON
  GET  /health           health check for the cloud load balancer
"""
import os
import time
import uuid
from collections import defaultdict, deque

from flask import Flask, jsonify, render_template, request

from chatbot import ChatBot, ChatStore

MAX_MESSAGE_LEN = 500
RATE_LIMIT = int(os.environ.get("RATE_LIMIT_PER_MIN", "30"))


def create_app(db_path: str | None = None) -> Flask:
    app = Flask(__name__)
    app.json.ensure_ascii = False
    bot = ChatBot(threshold=float(os.environ.get("CONFIDENCE_THRESHOLD", "0.30")))
    default_db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "chat_logs.db")
    store = ChatStore(db_path or os.environ.get("DB_PATH", default_db))
    hits: dict[str, deque] = defaultdict(deque)
    app.config.update(BOT=bot, STORE=store, PROFILE=bot.data["profile"])

    def rate_limited(key: str) -> bool:
        now = time.time()
        q = hits[key]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= RATE_LIMIT:
            return True
        q.append(now)
        return False

    @app.after_request
    def cors(resp):
        # Allows the widget to be embedded on any website.
        if request.path.startswith("/api/"):
            resp.headers["Access-Control-Allow-Origin"] = os.environ.get("ALLOWED_ORIGIN", "*")
            resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return resp

    @app.get("/")
    def index():
        return render_template("index.html", profile=app.config["PROFILE"], recipes=bot.kitchen.recipes)

    @app.get("/dashboard")
    def dashboard():
        return render_template("dashboard.html", profile=app.config["PROFILE"])

    @app.get("/health")
    def health():
        return jsonify(status="ok", intents=len(bot.intents), recipes=len(bot.kitchen.recipes))

    @app.route("/api/chat", methods=["POST", "OPTIONS"])
    def chat():
        if request.method == "OPTIONS":
            return "", 204
        payload = request.get_json(silent=True) or {}
        message = payload.get("message")
        if not isinstance(message, str) or not message.strip():
            return jsonify(error="'message' must be a non-empty string"), 400
        if len(message) > MAX_MESSAGE_LEN:
            return jsonify(error=f"message too long (max {MAX_MESSAGE_LEN} characters)"), 400
        session_id = str(payload.get("session_id") or uuid.uuid4())[:64]
        if rate_limited(request.headers.get("X-Forwarded-For", request.remote_addr or "?")):
            return jsonify(error="Too many messages, please wait a moment."), 429

        reply = bot.respond(message, session_id).to_dict()
        reply["message_id"] = store.log(session_id, message.strip(), reply)
        reply["session_id"] = session_id
        return jsonify(reply)

    @app.route("/api/feedback", methods=["POST", "OPTIONS"])
    def feedback():
        if request.method == "OPTIONS":
            return "", 204
        payload = request.get_json(silent=True) or {}
        message_id, helpful = payload.get("message_id"), payload.get("helpful")
        if not isinstance(message_id, int) or not isinstance(helpful, bool):
            return jsonify(error="'message_id' (int) and 'helpful' (bool) are required"), 400
        if not store.set_feedback(message_id, helpful):
            return jsonify(error="message not found"), 404
        return jsonify(ok=True)

    @app.get("/api/stats")
    def stats():
        return jsonify(store.stats())

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
