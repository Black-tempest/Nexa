from flask import Blueprint, request, jsonify
from database import execute, fetch_one, fetch_all, get_user_by_id
from utils import clean_text, now_ms, log
from auth import get_current_user

groups_bp = Blueprint("groups", __name__)


def public_user(u):
    if not u:
        return None
    return {
        "id": u["id"],
        "username": u["username"],
        "display_name": u.get("display_name"),
        "avatar": u.get("avatar")
    }


def enrich_group(group, current_uid=None):
    if not group:
        return None
    g = dict(group)
    owner = get_user_by_id(g["owner_id"])
    g["owner"] = public_user(owner)

    count = fetch_one(
        "SELECT COUNT(*) AS c FROM group_members WHERE group_id = ?",
        (g["id"],)
    )
    g["members_count"] = count["c"] if count else 0

    if current_uid:
        member = fetch_one(
            "SELECT role FROM group_members WHERE group_id = ? AND user_id = ?",
            (g["id"], current_uid)
        )
        g["is_member"] = bool(member)
        g["my_role"] = member["role"] if member else None
    else:
        g["is_member"] = False
        g["my_role"] = None

    return g


@groups_bp.route("/api/groups", methods=["GET"])
def route_list_groups():
    user = get_current_user()
    current_uid = user["id"] if user else None

    search = request.args.get("search", "").strip()
    mine = request.args.get("mine") == "1"

    if mine and current_uid:
        rows = fetch_all("""
            SELECT g.* FROM groups_table g
            INNER JOIN group_members m ON m.group_id = g.id
            WHERE m.user_id = ?
            ORDER BY g.created_at DESC
        """, (current_uid,))
    elif search:
        rows = fetch_all("""
            SELECT * FROM groups_table
            WHERE name LIKE ?
            ORDER BY created_at DESC
            LIMIT 50
        """, ("%" + search + "%",))
    else:
        rows = fetch_all("""
            SELECT * FROM groups_table
            WHERE is_private = 0
            ORDER BY created_at DESC
            LIMIT 50
        """)

    result = [enrich_group(g, current_uid) for g in rows]
    return jsonify({"ok": True, "groups": result})


@groups_bp.route("/api/groups/<int:group_id>", methods=["GET"])
def route_get_group(group_id):
    user = get_current_user()
    current_uid = user["id"] if user else None

    group = fetch_one("SELECT * FROM groups_table WHERE id = ?", (group_id,))
    if not group:
        return jsonify({"ok": False, "error": "Group not found"}), 404

    if group["is_private"] and not current_uid:
        return jsonify({"ok": False, "error": "Private group"}), 403

    if group["is_private"] and current_uid:
        member = fetch_one(
            "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?",
            (group_id, current_uid)
        )
        if not member:
            return jsonify({"ok": False, "error": "Private group"}), 403

    return jsonify({"ok": True, "group": enrich_group(group, current_uid)})


@groups_bp.route("/api/groups", methods=["POST"])
def route_create_group():
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "Not authenticated"}), 401

    try:
        data = request.get_json(force=True) or {}
        name = clean_text(data.get("name"), 60)
        description = clean_text(data.get("description"), 500)
        is_private = 1 if data.get("is_private") else 0

        if not name or len(name) < 2:
            return jsonify({"ok": False, "error": "Group name too short"}), 400

        cur = execute("""
            INSERT INTO groups_table (name, description, owner_id, is_private, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (name, description, user["id"], is_private, now_ms()))

        group_id = cur.lastrowid

        execute("""
            INSERT INTO group_members (group_id, user_id, role, joined_at)
            VALUES (?, ?, 'owner', ?)
        """, (group_id, user["id"], now_ms()))

        group = fetch_one("SELECT * FROM groups_table WHERE id = ?", (group_id,))

        return jsonify({"ok": True, "group": enrich_group(group, user["id"])})
    except Exception as e:
        log("Create group error: " + str(e))
        return jsonify({"ok": False, "error": str(e)}), 500


@groups_bp.route("/api/groups/<int:group_id>/join", methods=["POST"])
def route_join_group(group_id):
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "Not authenticated"}), 401

    group = fetch_one("SELECT * FROM groups_table WHERE id = ?", (group_id,))
    if not group:
        return jsonify({"ok": False, "error": "Group not found"}), 404

    existing = fetch_one(
        "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?",
        (group_id, user["id"])
    )
    if existing:
        return jsonify({"ok": False, "error": "Already a member"}), 409

    execute("""
        INSERT INTO group_members (group_id, user_id, role, joined_at)
        VALUES (?, ?, 'member', ?)
    """, (group_id, user["id"], now_ms()))

    return jsonify({"ok": True})


@groups_bp.route("/api/groups/<int:group_id>/leave", methods=["POST"])
def route_leave_group(group_id):
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "Not authenticated"}), 401

    group = fetch_one("SELECT * FROM groups_table WHERE id = ?", (group_id,))
    if not group:
        return jsonify({"ok": False, "error": "Group not found"}), 404

    if group["owner_id"] == user["id"]:
        return jsonify({"ok": False, "error": "Owner cannot leave. Delete the group instead."}), 400

    execute(
        "DELETE FROM group_members WHERE group_id = ? AND user_id = ?",
        (group_id, user["id"])
    )
    return jsonify({"ok": True})


@groups_bp.route("/api/groups/<int:group_id>", methods=["DELETE"])
def route_delete_group(group_id):
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "Not authenticated"}), 401

    group = fetch_one("SELECT * FROM groups_table WHERE id = ?", (group_id,))
    if not group:
        return jsonify({"ok": False, "error": "Group not found"}), 404

    if group["owner_id"] != user["id"]:
        return jsonify({"ok": False, "error": "Not allowed"}), 403

    execute("DELETE FROM groups_table WHERE id = ?", (group_id,))
    return jsonify({"ok": True})


@groups_bp.route("/api/groups/<int:group_id>/members", methods=["GET"])
def route_group_members(group_id):
    user = get_current_user()
    current_uid = user["id"] if user else None

    group = fetch_one("SELECT * FROM groups_table WHERE id = ?", (group_id,))
    if not group:
        return jsonify({"ok": False, "error": "Group not found"}), 404

    if group["is_private"] and current_uid:
        member = fetch_one(
            "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?",
            (group_id, current_uid)
        )
        if not member:
            return jsonify({"ok": False, "error": "Private group"}), 403
    elif group["is_private"] and not current_uid:
        return jsonify({"ok": False, "error": "Private group"}), 403

    rows = fetch_all("""
        SELECT u.*, m.role, m.joined_at FROM group_members m
        INNER JOIN users u ON u.id = m.user_id
        WHERE m.group_id = ?
        ORDER BY m.role DESC, m.joined_at ASC
    """, (group_id,))

    members = []
    for r in rows:
        members.append({
            "user": public_user(r),
            "role": r["role"],
            "joined_at": r["joined_at"]
        })

    return jsonify({"ok": True, "members": members})


@groups_bp.route("/api/groups/<int:group_id>/messages", methods=["GET"])
def route_group_messages(group_id):
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "Not authenticated"}), 401

    member = fetch_one(
        "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?",
        (group_id, user["id"])
    )
    if not member:
        return jsonify({"ok": False, "error": "Not a member"}), 403

    limit = min(int(request.args.get("limit", 100)), 500)
    before = request.args.get("before")

    if before:
        rows = fetch_all("""
            SELECT * FROM group_messages
            WHERE group_id = ? AND created_at < ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (group_id, int(before), limit))
    else:
        rows = fetch_all("""
            SELECT * FROM group_messages
            WHERE group_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (group_id, limit))

    rows.reverse()

    for m in rows:
        m["sender"] = public_user(get_user_by_id(m["user_id"]))

    return jsonify({"ok": True, "messages": rows})


@groups_bp.route("/api/groups/<int:group_id>/messages", methods=["POST"])
def route_send_group_message(group_id):
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "Not authenticated"}), 401

    member = fetch_one(
        "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?",
        (group_id, user["id"])
    )
    if not member:
        return jsonify({"ok": False, "error": "Not a member"}), 403

    try:
        data = request.get_json(force=True) or {}
        content = clean_text(data.get("content"), 5000)

        if not content:
            return jsonify({"ok": False, "error": "Content required"}), 400

        cur = execute("""
            INSERT INTO group_messages (group_id, user_id, content, created_at)
            VALUES (?, ?, ?, ?)
        """, (group_id, user["id"], content, now_ms()))

        msg_id = cur.lastrowid
        msg = fetch_one("SELECT * FROM group_messages WHERE id = ?", (msg_id,))
        msg["sender"] = public_user(user)

        return jsonify({"ok": True, "message": msg})
    except Exception as e:
        log("Group message error: " + str(e))
        return jsonify({"ok": False, "error": str(e)}), 500
