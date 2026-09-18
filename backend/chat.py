from flask import Blueprint, request, jsonify
from database import execute, fetch_one, fetch_all, get_user_by_id
from utils import clean_text, now_ms, log
from auth import get_current_user

chat = Blueprint("chat", __name__)


def public_user(u):
    if not u:
        return None
    return {
        "id": u["id"],
        "username": u["username"],
        "display_name": u.get("display_name"),
        "avatar": u.get("avatar")
    }


def enrich_message(msg):
    if not msg:
        return None
    m = dict(msg)
    sender = get_user_by_id(m["user_id"]) if "user_id" in m else get_user_by_id(m["from_user"])
    if "from_user" in m:
        sender = get_user_by_id(m["from_user"])
    m["sender"] = public_user(sender)
    return m


def are_friends_or_self(uid1, uid2):
    return uid1 == uid2


@chat.route("/api/chat/conversations", methods=["GET"])
def route_conversations():
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "Not authenticated"}), 401

    uid = user["id"]

    rows = fetch_all("""
        SELECT
            CASE
                WHEN from_user = ? THEN to_user
                ELSE from_user
            END AS other_id,
            MAX(created_at) AS last_at
        FROM private_messages
        WHERE from_user = ? OR to_user = ?
        GROUP BY other_id
        ORDER BY last_at DESC
    """, (uid, uid, uid))

    conversations = []
    for row in rows:
        other = get_user_by_id(row["other_id"])
        if not other:
            continue
        last = fetch_one("""
            SELECT * FROM private_messages
            WHERE (from_user = ? AND to_user = ?)
               OR (from_user = ? AND to_user = ?)
            ORDER BY created_at DESC
            LIMIT 1
        """, (uid, row["other_id"], row["other_id"], uid))

        unread = fetch_one("""
            SELECT COUNT(*) AS c FROM private_messages
            WHERE from_user = ? AND to_user = ? AND is_read = 0
        """, (row["other_id"], uid))

        conversations.append({
            "user": public_user(other),
            "last_message": last,
            "unread": unread["c"] if unread else 0
        })

    return jsonify({"ok": True, "conversations": conversations})


@chat.route("/api/chat/with/<int:other_id>", methods=["GET"])
def route_chat_with(other_id):
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "Not authenticated"}), 401

    uid = user["id"]
    other = get_user_by_id(other_id)
    if not other:
        return jsonify({"ok": False, "error": "User not found"}), 404

    limit = min(int(request.args.get("limit", 100)), 500)
    before = request.args.get("before")

    if before:
        rows = fetch_all("""
            SELECT * FROM private_messages
            WHERE ((from_user = ? AND to_user = ?) OR (from_user = ? AND to_user = ?))
              AND created_at < ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (uid, other_id, other_id, uid, int(before), limit))
    else:
        rows = fetch_all("""
            SELECT * FROM private_messages
            WHERE (from_user = ? AND to_user = ?) OR (from_user = ? AND to_user = ?)
            ORDER BY created_at DESC
            LIMIT ?
        """, (uid, other_id, other_id, uid, limit))

    rows.reverse()

    for m in rows:
        m["sender"] = public_user(get_user_by_id(m["from_user"]))

    execute("""
        UPDATE private_messages SET is_read = 1
        WHERE from_user = ? AND to_user = ?
    """, (other_id, uid))

    return jsonify({"ok": True, "messages": rows, "user": public_user(other)})


@chat.route("/api/chat/send", methods=["POST"])
def route_send():
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "Not authenticated"}), 401

    try:
        data = request.get_json(force=True) or {}
        to_user = int(data.get("to_user", 0))
        content = clean_text(data.get("content"), 5000)

        if not to_user or not content:
            return jsonify({"ok": False, "error": "Missing fields"}), 400

        target = get_user_by_id(to_user)
        if not target:
            return jsonify({"ok": False, "error": "User not found"}), 404

        if to_user == user["id"]:
            return jsonify({"ok": False, "error": "Cannot message yourself"}), 400

        cur = execute("""
            INSERT INTO private_messages (from_user, to_user, content, is_read, created_at)
            VALUES (?, ?, ?, 0, ?)
        """, (user["id"], to_user, content, now_ms()))

        msg_id = cur.lastrowid
        msg = fetch_one("SELECT * FROM private_messages WHERE id = ?", (msg_id,))
        msg["sender"] = public_user(user)

        return jsonify({"ok": True, "message": msg})
    except Exception as e:
        log("Send message error: " + str(e))
        return jsonify({"ok": False, "error": str(e)}), 500


@chat.route("/api/chat/unread", methods=["GET"])
def route_unread_count():
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "Not authenticated"}), 401

    row = fetch_one("""
        SELECT COUNT(*) AS c FROM private_messages
        WHERE to_user = ? AND is_read = 0
    """, (user["id"],))

    return jsonify({"ok": True, "count": row["c"] if row else 0})


@chat.route("/api/chat/delete/<int:msg_id>", methods=["DELETE"])
def route_delete_message(msg_id):
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "Not authenticated"}), 401

    msg = fetch_one("SELECT * FROM private_messages WHERE id = ?", (msg_id,))
    if not msg:
        return jsonify({"ok": False, "error": "Message not found"}), 404

    if msg["from_user"] != user["id"]:
        return jsonify({"ok": False, "error": "Not allowed"}), 403

    execute("DELETE FROM private_messages WHERE id = ?", (msg_id,))
    return jsonify({"ok": True})
