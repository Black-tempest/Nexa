from flask import Blueprint, request, jsonify
from database import execute, fetch_one, fetch_all, get_user_by_id, get_user_by_username
from utils import clean_text, now_ms, log
from auth import get_current_user

profile = Blueprint("profile", __name__)


def public_user(u):
    if not u:
        return None
    return {
        "id": u["id"],
        "username": u["username"],
        "display_name": u.get("display_name"),
        "avatar": u.get("avatar"),
        "bio": u.get("bio", ""),
        "created_at": u.get("created_at")
    }


def enrich_profile(u, current_uid=None):
    if not u:
        return None
    p = public_user(u)

    posts = fetch_one("SELECT COUNT(*) AS c FROM posts WHERE user_id = ?", (u["id"],))
    p["posts_count"] = posts["c"] if posts else 0

    followers = fetch_one("SELECT COUNT(*) AS c FROM follows WHERE following_id = ?", (u["id"],))
    p["followers_count"] = followers["c"] if followers else 0

    following = fetch_one("SELECT COUNT(*) AS c FROM follows WHERE follower_id = ?", (u["id"],))
    p["following_count"] = following["c"] if following else 0

    if current_uid:
        is_following = fetch_one(
            "SELECT 1 FROM follows WHERE follower_id = ? AND following_id = ?",
            (current_uid, u["id"])
        )
        p["is_following"] = bool(is_following)
        p["is_me"] = (current_uid == u["id"])
    else:
        p["is_following"] = False
        p["is_me"] = False

    return p


@profile.route("/api/profile/me", methods=["GET"])
def route_my_profile():
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "Not authenticated"}), 401

    full = get_user_by_id(user["id"])
    full.pop("password_hash", None)
    return jsonify({"ok": True, "profile": enrich_profile(full, user["id"])})


@profile.route("/api/profile/<username>", methods=["GET"])
def route_get_profile(username):
    user = get_current_user()
    current_uid = user["id"] if user else None

    target = get_user_by_username(username)
    if not target:
        return jsonify({"ok": False, "error": "User not found"}), 404

    return jsonify({"ok": True, "profile": enrich_profile(target, current_uid)})


@profile.route("/api/profile/<int:user_id>", methods=["GET"])
def route_get_profile_by_id(user_id):
    user = get_current_user()
    current_uid = user["id"] if user else None

    target = get_user_by_id(user_id)
    if not target:
        return jsonify({"ok": False, "error": "User not found"}), 404

    return jsonify({"ok": True, "profile": enrich_profile(target, current_uid)})


@profile.route("/api/profile/<int:user_id>/follow", methods=["POST"])
def route_follow(user_id):
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "Not authenticated"}), 401

    if user_id == user["id"]:
        return jsonify({"ok": False, "error": "Cannot follow yourself"}), 400

    target = get_user_by_id(user_id)
    if not target:
        return jsonify({"ok": False, "error": "User not found"}), 404

    existing = fetch_one(
        "SELECT 1 FROM follows WHERE follower_id = ? AND following_id = ?",
        (user["id"], user_id)
    )

    if existing:
        execute(
            "DELETE FROM follows WHERE follower_id = ? AND following_id = ?",
            (user["id"], user_id)
        )
        following = False
    else:
        execute(
            "INSERT INTO follows (follower_id, following_id, created_at) VALUES (?, ?, ?)",
            (user["id"], user_id, now_ms())
        )
        following = True

        execute("""
            INSERT INTO notifications (user_id, type, ref_id, text, is_read, created_at)
            VALUES (?, 'follow', ?, ?, 0, ?)
        """, (user_id, user["id"], user["username"] + " started following you", now_ms()))

    count = fetch_one("SELECT COUNT(*) AS c FROM follows WHERE following_id = ?", (user_id,))

    return jsonify({
        "ok": True,
        "following": following,
        "followers_count": count["c"] if count else 0
    })


@profile.route("/api/profile/<int:user_id>/followers", methods=["GET"])
def route_followers(user_id):
    target = get_user_by_id(user_id)
    if not target:
        return jsonify({"ok": False, "error": "User not found"}), 404

    rows = fetch_all("""
        SELECT u.* FROM follows f
        INNER JOIN users u ON u.id = f.follower_id
        WHERE f.following_id = ?
        ORDER BY f.created_at DESC
        LIMIT 100
    """, (user_id,))

    return jsonify({"ok": True, "users": [public_user(u) for u in rows]})


@profile.route("/api/profile/<int:user_id>/following", methods=["GET"])
def route_following(user_id):
    target = get_user_by_id(user_id)
    if not target:
        return jsonify({"ok": False, "error": "User not found"}), 404

    rows = fetch_all("""
        SELECT u.* FROM follows f
        INNER JOIN users u ON u.id = f.following_id
        WHERE f.follower_id = ?
        ORDER BY f.created_at DESC
        LIMIT 100
    """, (user_id,))

    return jsonify({"ok": True, "users": [public_user(u) for u in rows]})


@profile.route("/api/search/users", methods=["GET"])
def route_search_users():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"ok": True, "users": []})

    rows = fetch_all("""
        SELECT * FROM users
        WHERE username LIKE ? OR display_name LIKE ?
        ORDER BY username ASC
        LIMIT 30
    """, ("%" + q + "%", "%" + q + "%"))

    return jsonify({"ok": True, "users": [public_user(u) for u in rows]})


@profile.route("/api/notifications", methods=["GET"])
def route_notifications():
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "Not authenticated"}), 401

    rows = fetch_all("""
        SELECT * FROM notifications
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 50
    """, (user["id"],))

    return jsonify({"ok": True, "notifications": rows})


@profile.route("/api/notifications/read", methods=["POST"])
def route_read_notifications():
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "Not authenticated"}), 401

    execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (user["id"],))
    return jsonify({"ok": True})


@profile.route("/api/notifications/unread", methods=["GET"])
def route_unread_notifications():
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "Not authenticated"}), 401

    row = fetch_one("""
        SELECT COUNT(*) AS c FROM notifications
        WHERE user_id = ? AND is_read = 0
    """, (user["id"],))

    return jsonify({"ok": True, "count": row["c"] if row else 0})
