import time
from flask import Blueprint, request, jsonify, session
from database import (
    create_user, get_user_by_username, get_user_by_email,
    get_user_by_id, create_session, get_session, delete_session,
    delete_expired_sessions, update_user
)
from utils import (
    hash_password, verify_password, generate_token,
    is_valid_username, is_valid_email, is_valid_password,
    safe_username, log
)

auth = Blueprint("auth", __name__)

SESSION_DURATION_MS = 30 * 24 * 60 * 60 * 1000


def get_token_from_request():
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    return request.cookies.get("nexa_token")


def get_current_user():
    token = get_token_from_request()
    if not token:
        return None
    s = get_session(token)
    if not s:
        return None
    if s["expires_at"] < int(time.time() * 1000):
        delete_session(token)
        return None
    user = get_user_by_id(s["user_id"])
    if not user:
        delete_session(token)
        return None
    user.pop("password_hash", None)
    return user


def public_user(user):
    if not user:
        return None
    u = dict(user)
    u.pop("password_hash", None)
    u.pop("email", None)
    return u


@auth.route("/api/auth/register", methods=["POST"])
def route_register():
    try:
        data = request.get_json(force=True) or {}
        username = safe_username(data.get("username"))
        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", ""))
        display_name = str(data.get("display_name", "")).strip() or username

        if not is_valid_username(username):
            return jsonify({"ok": False, "error": "Invalid username (3-30 chars, letters/numbers/._-)"}), 400

        if not is_valid_email(email):
            return jsonify({"ok": False, "error": "Invalid email"}), 400

        if not is_valid_password(password):
            return jsonify({"ok": False, "error": "Password must be at least 6 characters"}), 400

        if get_user_by_username(username):
            return jsonify({"ok": False, "error": "Username already taken"}), 409

        if get_user_by_email(email):
            return jsonify({"ok": False, "error": "Email already registered"}), 409

        pwd_hash = hash_password(password)
        user_id = create_user(username, email, pwd_hash, display_name)

        token = generate_token()
        expires_at = int(time.time() * 1000) + SESSION_DURATION_MS
        create_session(token, user_id, expires_at)
        delete_expired_sessions()

        user = get_user_by_id(user_id)
        user.pop("password_hash", None)

        log("New user registered: " + username)
        return jsonify({"ok": True, "token": token, "user": user})
    except Exception as e:
        log("Register error: " + str(e))
        return jsonify({"ok": False, "error": str(e)}), 500


@auth.route("/api/auth/login", methods=["POST"])
def route_login():
    try:
        data = request.get_json(force=True) or {}
        login_id = str(data.get("username", "")).strip().lower()
        password = str(data.get("password", ""))

        if not login_id or not password:
            return jsonify({"ok": False, "error": "Missing credentials"}), 400

        user = get_user_by_username(login_id)
        if not user:
            user = get_user_by_email(login_id)

        if not user or not verify_password(password, user["password_hash"]):
            return jsonify({"ok": False, "error": "Invalid credentials"}), 401

        token = generate_token()
        expires_at = int(time.time() * 1000) + SESSION_DURATION_MS
        create_session(token, user["id"], expires_at)
        delete_expired_sessions()

        user.pop("password_hash", None)
        log("User logged in: " + user["username"])
        return jsonify({"ok": True, "token": token, "user": user})
    except Exception as e:
        log("Login error: " + str(e))
        return jsonify({"ok": False, "error": str(e)}), 500


@auth.route("/api/auth/logout", methods=["POST"])
def route_logout():
    token = get_token_from_request()
    if token:
        delete_session(token)
    return jsonify({"ok": True})


@auth.route("/api/auth/me", methods=["GET"])
def route_me():
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "Not authenticated"}), 401
    return jsonify({"ok": True, "user": user})


@auth.route("/api/auth/update", methods=["POST"])
def route_update():
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "Not authenticated"}), 401

    try:
        data = request.get_json(force=True) or {}
        fields = {}

        if "display_name" in data:
            dn = str(data["display_name"]).strip()
            if dn:
                fields["display_name"] = dn[:50]

        if "bio" in data:
            fields["bio"] = str(data["bio"]).strip()[:300]

        if "avatar" in data:
            fields["avatar"] = str(data["avatar"]).strip()[:500]

        if "password" in data and data["password"]:
            if not is_valid_password(data["password"]):
                return jsonify({"ok": False, "error": "Password too short"}), 400
            fields["password_hash"] = hash_password(data["password"])

        if fields:
            update_user(user["id"], fields)

        updated = get_user_by_id(user["id"])
        updated.pop("password_hash", None)
        return jsonify({"ok": True, "user": updated})
    except Exception as e:
        log("Update error: " + str(e))
        return jsonify({"ok": False, "error": str(e)}), 500
