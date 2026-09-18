from flask import Blueprint, request, jsonify
from database import execute, fetch_one, fetch_all, get_user_by_id
from utils import clean_text, now_ms, log
from auth import get_current_user

posts = Blueprint("posts", __name__)


def public_user(u):
    if not u:
        return None
    return {
        "id": u["id"],
        "username": u["username"],
        "display_name": u.get("display_name"),
        "avatar": u.get("avatar")
    }


def enrich_post(post, current_uid=None):
    if not post:
        return None
    p = dict(post)
    author = get_user_by_id(p["user_id"])
    p["author"] = public_user(author)

    likes = fetch_one("SELECT COUNT(*) AS c FROM post_likes WHERE post_id = ?", (p["id"],))
    p["likes_count"] = likes["c"] if likes else 0

    comments = fetch_one("SELECT COUNT(*) AS c FROM post_comments WHERE post_id = ?", (p["id"],))
    p["comments_count"] = comments["c"] if comments else 0

    if current_uid:
        liked = fetch_one(
            "SELECT 1 FROM post_likes WHERE post_id = ? AND user_id = ?",
            (p["id"], current_uid)
        )
        p["liked"] = bool(liked)
    else:
        p["liked"] = False

    return p


@posts.route("/api/posts", methods=["GET"])
def route_feed():
    user = get_current_user()
    current_uid = user["id"] if user else None

    limit = min(int(request.args.get("limit", 20)), 100)
    before = request.args.get("before")
    author_id = request.args.get("author")

    if author_id:
        if before:
            rows = fetch_all("""
                SELECT * FROM posts
                WHERE user_id = ? AND created_at < ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (int(author_id), int(before), limit))
        else:
            rows = fetch_all("""
                SELECT * FROM posts
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (int(author_id), limit))
    else:
        if before:
            rows = fetch_all("""
                SELECT * FROM posts
                WHERE created_at < ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (int(before), limit))
        else:
            rows = fetch_all("""
                SELECT * FROM posts
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))

    result = [enrich_post(p, current_uid) for p in rows]
    return jsonify({"ok": True, "posts": result})


@posts.route("/api/posts/<int:post_id>", methods=["GET"])
def route_get_post(post_id):
    user = get_current_user()
    current_uid = user["id"] if user else None

    post = fetch_one("SELECT * FROM posts WHERE id = ?", (post_id,))
    if not post:
        return jsonify({"ok": False, "error": "Post not found"}), 404

    return jsonify({"ok": True, "post": enrich_post(post, current_uid)})


@posts.route("/api/posts", methods=["POST"])
def route_create_post():
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "Not authenticated"}), 401

    try:
        data = request.get_json(force=True) or {}
        content = clean_text(data.get("content"), 5000)
        image = data.get("image")

        if not content:
            return jsonify({"ok": False, "error": "Content is required"}), 400

        cur = execute("""
            INSERT INTO posts (user_id, content, image, created_at)
            VALUES (?, ?, ?, ?)
        """, (user["id"], content, image, now_ms()))

        post_id = cur.lastrowid
        post = fetch_one("SELECT * FROM posts WHERE id = ?", (post_id,))

        return jsonify({"ok": True, "post": enrich_post(post, user["id"])})
    except Exception as e:
        log("Create post error: " + str(e))
        return jsonify({"ok": False, "error": str(e)}), 500


@posts.route("/api/posts/<int:post_id>", methods=["DELETE"])
def route_delete_post(post_id):
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "Not authenticated"}), 401

    post = fetch_one("SELECT * FROM posts WHERE id = ?", (post_id,))
    if not post:
        return jsonify({"ok": False, "error": "Post not found"}), 404

    if post["user_id"] != user["id"]:
        return jsonify({"ok": False, "error": "Not allowed"}), 403

    execute("DELETE FROM posts WHERE id = ?", (post_id,))
    return jsonify({"ok": True})


@posts.route("/api/posts/<int:post_id>/like", methods=["POST"])
def route_like_post(post_id):
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "Not authenticated"}), 401

    post = fetch_one("SELECT * FROM posts WHERE id = ?", (post_id,))
    if not post:
        return jsonify({"ok": False, "error": "Post not found"}), 404

    existing = fetch_one(
        "SELECT 1 FROM post_likes WHERE post_id = ? AND user_id = ?",
        (post_id, user["id"])
    )

    if existing:
        execute(
            "DELETE FROM post_likes WHERE post_id = ? AND user_id = ?",
            (post_id, user["id"])
        )
        liked = False
    else:
        execute(
            "INSERT INTO post_likes (post_id, user_id, created_at) VALUES (?, ?, ?)",
            (post_id, user["id"], now_ms())
        )
        liked = True

        if post["user_id"] != user["id"]:
            execute("""
                INSERT INTO notifications (user_id, type, ref_id, text, is_read, created_at)
                VALUES (?, 'like', ?, ?, 0, ?)
            """, (post["user_id"], post_id, user["username"] + " liked your post", now_ms()))

    likes = fetch_one("SELECT COUNT(*) AS c FROM post_likes WHERE post_id = ?", (post_id,))

    return jsonify({
        "ok": True,
        "liked": liked,
        "count": likes["c"] if likes else 0
    })


@posts.route("/api/posts/<int:post_id>/comments", methods=["GET"])
def route_get_comments(post_id):
    user = get_current_user()
    current_uid = user["id"] if user else None

    post = fetch_one("SELECT * FROM posts WHERE id = ?", (post_id,))
    if not post:
        return jsonify({"ok": False, "error": "Post not found"}), 404

    rows = fetch_all("""
        SELECT * FROM post_comments
        WHERE post_id = ?
        ORDER BY created_at ASC
    """, (post_id,))

    for c in rows:
        c["author"] = public_user(get_user_by_id(c["user_id"]))

    return jsonify({"ok": True, "comments": rows})


@posts.route("/api/posts/<int:post_id>/comments", methods=["POST"])
def route_add_comment(post_id):
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "Not authenticated"}), 401

    post = fetch_one("SELECT * FROM posts WHERE id = ?", (post_id,))
    if not post:
        return jsonify({"ok": False, "error": "Post not found"}), 404

    try:
        data = request.get_json(force=True) or {}
        content = clean_text(data.get("content"), 1000)

        if not content:
            return jsonify({"ok": False, "error": "Content required"}), 400

        cur = execute("""
            INSERT INTO post_comments (post_id, user_id, content, created_at)
            VALUES (?, ?, ?, ?)
        """, (post_id, user["id"], content, now_ms()))

        comment_id = cur.lastrowid
        comment = fetch_one("SELECT * FROM post_comments WHERE id = ?", (comment_id,))
        comment["author"] = public_user(user)

        if post["user_id"] != user["id"]:
            execute("""
                INSERT INTO notifications (user_id, type, ref_id, text, is_read, created_at)
                VALUES (?, 'comment', ?, ?, 0, ?)
            """, (post["user_id"], post_id, user["username"] + " commented on your post", now_ms()))

        return jsonify({"ok": True, "comment": comment})
    except Exception as e:
        log("Add comment error: " + str(e))
        return jsonify({"ok": False, "error": str(e)}), 500


@posts.route("/api/posts/comments/<int:comment_id>", methods=["DELETE"])
def route_delete_comment(comment_id):
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "Not authenticated"}), 401

    comment = fetch_one("SELECT * FROM post_comments WHERE id = ?", (comment_id,))
    if not comment:
        return jsonify({"ok": False, "error": "Comment not found"}), 404

    if comment["user_id"] != user["id"]:
        return jsonify({"ok": False, "error": "Not allowed"}), 403

    execute("DELETE FROM post_comments WHERE id = ?", (comment_id,))
    return jsonify({"ok": True})
