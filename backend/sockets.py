from flask_socketio import SocketIO, emit, join_room, leave_room, rooms
from flask import request
from database import execute, fetch_one, fetch_all, get_user_by_id, get_session
from utils import clean_text, now_ms, log

socketio = SocketIO(cors_allowed_origins="*", async_mode="eventlet")

_connected = {}


def get_user_from_token(token):
    if not token:
        return None
    s = get_session(token)
    if not s:
        return None
    import time
    if s["expires_at"] < int(time.time() * 1000):
        return None
    return get_user_by_id(s["user_id"])


def public_user(u):
    if not u:
        return None
    return {
        "id": u["id"],
        "username": u["username"],
        "display_name": u.get("display_name"),
        "avatar": u.get("avatar")
    }


@socketio.on("connect")
def on_connect(auth=None):
    try:
        token = None
        if auth and isinstance(auth, dict):
            token = auth.get("token")

        if not token:
            token = request.args.get("token")

        user = get_user_from_token(token)
        if not user:
            log("Socket connect refused: invalid token")
            return False

        sid = request.sid
        _connected[sid] = user["id"]

        join_room("user_" + str(user["id"]))

        emit("connected", {"ok": True, "user": public_user(user)})
        log("Socket connected: " + user["username"])
        return True
    except Exception as e:
        log("Socket connect error: " + str(e))
        return False


@socketio.on("disconnect")
def on_disconnect():
    sid = request.sid
    uid = _connected.pop(sid, None)
    if uid:
        log("Socket disconnected: user " + str(uid))


@socketio.on("join_group")
def on_join_group(data):
    sid = request.sid
    uid = _connected.get(sid)
    if not uid:
        return

    try:
        group_id = int(data.get("group_id", 0))
        if not group_id:
            return

        member = fetch_one(
            "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?",
            (group_id, uid)
        )
        if not member:
            emit("error", {"error": "Not a member of this group"})
            return

        join_room("group_" + str(group_id))
        emit("joined_group", {"group_id": group_id})
    except Exception as e:
        log("join_group error: " + str(e))


@socketio.on("leave_group")
def on_leave_group(data):
    try:
        group_id = int(data.get("group_id", 0))
        if group_id:
            leave_room("group_" + str(group_id))
            emit("left_group", {"group_id": group_id})
    except Exception as e:
        log("leave_group error: " + str(e))


@socketio.on("private_message")
def on_private_message(data):
    sid = request.sid
    uid = _connected.get(sid)
    if not uid:
        return

    try:
        to_user = int(data.get("to_user", 0))
        content = clean_text(data.get("content"), 5000)

        if not to_user or not content:
            emit("error", {"error": "Missing fields"})
            return

        target = get_user_by_id(to_user)
        if not target:
            emit("error", {"error": "User not found"})
            return

        cur = execute("""
            INSERT INTO private_messages (from_user, to_user, content, is_read, created_at)
            VALUES (?, ?, ?, 0, ?)
        """, (uid, to_user, content, now_ms()))

        msg_id = cur.lastrowid
        msg = fetch_one("SELECT * FROM private_messages WHERE id = ?", (msg_id,))
        msg["sender"] = public_user(get_user_by_id(uid))

        emit("private_message", {"message": msg}, room="user_" + str(to_user))
        emit("private_message_sent", {"message": msg})

        log("PM " + str(uid) + " -> " + str(to_user))
    except Exception as e:
        log("private_message error: " + str(e))
        emit("error", {"error": str(e)})


@socketio.on("group_message")
def on_group_message(data):
    sid = request.sid
    uid = _connected.get(sid)
    if not uid:
        return

    try:
        group_id = int(data.get("group_id", 0))
        content = clean_text(data.get("content"), 5000)

        if not group_id or not content:
            emit("error", {"error": "Missing fields"})
            return

        member = fetch_one(
            "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?",
            (group_id, uid)
        )
        if not member:
            emit("error", {"error": "Not a member"})
            return

        cur = execute("""
            INSERT INTO group_messages (group_id, user_id, content, created_at)
            VALUES (?, ?, ?, ?)
        """, (group_id, uid, content, now_ms()))

        msg_id = cur.lastrowid
        msg = fetch_one("SELECT * FROM group_messages WHERE id = ?", (msg_id,))
        msg["sender"] = public_user(get_user_by_id(uid))

        emit("group_message", {"message": msg, "group_id": group_id},
             room="group_" + str(group_id))

        log("Group msg " + str(group_id) + " from " + str(uid))
    except Exception as e:
        log("group_message error: " + str(e))
        emit("error", {"error": str(e)})


@socketio.on("typing")
def on_typing(data):
    sid = request.sid
    uid = _connected.get(sid)
    if not uid:
        return

    try:
        target_type = data.get("type")

        if target_type == "private":
            to_user = int(data.get("to_user", 0))
            if to_user:
                emit("typing", {"from_user": uid, "type": "private"},
                     room="user_" + str(to_user), include_self=False)

        elif target_type == "group":
            group_id = int(data.get("group_id", 0))
            if group_id:
                emit("typing", {"from_user": uid, "type": "group", "group_id": group_id},
                     room="group_" + str(group_id), include_self=False)
    except Exception as e:
        log("typing error: " + str(e))


@socketio.on("mark_read")
def on_mark_read(data):
    sid = request.sid
    uid = _connected.get(sid)
    if not uid:
        return

    try:
        from_user = int(data.get("from_user", 0))
        if not from_user:
            return

        execute("""
            UPDATE private_messages SET is_read = 1
            WHERE from_user = ? AND to_user = ?
        """, (from_user, uid))

        emit("messages_read", {"reader_id": uid}, room="user_" + str(from_user))
    except Exception as e:
        log("mark_read error: " + str(e))
