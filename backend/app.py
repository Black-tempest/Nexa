import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_cors import CORS

from utils import log
import database

from auth import auth
from chat import chat
from posts import posts
from groups import groups_bp
from profile import profile
from sockets import socketio


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")


app = Flask(
    __name__,
    template_folder=TEMPLATES_DIR,
    static_folder=STATIC_DIR,
    static_url_path="/static"
)

app.config["SECRET_KEY"] = os.environ.get("NEXA_SECRET", "nexa-dev-secret-change-me")
app.config["JSON_SORT_KEYS"] = False

CORS(app, supports_credentials=True)


app.register_blueprint(auth)
app.register_blueprint(chat)
app.register_blueprint(posts)
app.register_blueprint(groups_bp)
app.register_blueprint(profile)


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/login", methods=["GET"])
def page_login():
    return render_template("login.html")


@app.route("/register", methods=["GET"])
def page_register():
    return render_template("register.html")


@app.route("/feed", methods=["GET"])
def page_feed():
    return render_template("feed.html")


@app.route("/chat", methods=["GET"])
def page_chat():
    return render_template("chat.html")


@app.route("/groups", methods=["GET"])
def page_groups():
    return render_template("groups.html")


@app.route("/profile", methods=["GET"])
def page_profile():
    return render_template("profile.html")


@app.route("/api/health", methods=["GET"])
def route_health():
    return jsonify({"ok": True, "status": "alive", "app": "Nexa"})


@app.errorhandler(404)
def not_found(e):
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "Not found"}), 404
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(e):
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "Server error"}), 500
    return jsonify({"ok": False, "error": "Server error"}), 500


def main():
    port = int(os.environ.get("PORT", 5000))
    host = "0.0.0.0"

    log("Starting Nexa on " + host + ":" + str(port))

    try:
        database.init()
        log("Database ready")
    except Exception as e:
        log("Database init failed: " + str(e))

    socketio.init_app(app)
    socketio.run(
        app,
        host=host,
        port=port,
        debug=False,
        use_reloader=False,
        allow_unsafe_werkzeug=True
    )


if __name__ == "__main__":
    main()
