import os
import json
import sqlite3
from utils import log, now_ms

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "data",
    "nexa.db"
)

_conn = None


def get_conn():
    global _conn
    if _conn is None:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA foreign_keys = ON")
    return _conn


def init():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT,
            avatar TEXT,
            bio TEXT DEFAULT '',
            created_at INTEGER
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at INTEGER,
            expires_at INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS follows (
            follower_id INTEGER NOT NULL,
            following_id INTEGER NOT NULL,
            created_at INTEGER,
            PRIMARY KEY (follower_id, following_id),
            FOREIGN KEY (follower_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (following_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            image TEXT,
            created_at INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS post_likes (
            post_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            created_at INTEGER,
            PRIMARY KEY (post_id, user_id),
            FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS post_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at INTEGER,
            FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS groups_table (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            owner_id INTEGER NOT NULL,
            is_private INTEGER DEFAULT 0,
            avatar TEXT,
            created_at INTEGER,
            FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS group_members (
            group_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT DEFAULT 'member',
            joined_at INTEGER,
            PRIMARY KEY (group_id, user_id),
            FOREIGN KEY (group_id) REFERENCES groups_table(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS group_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at INTEGER,
            FOREIGN KEY (group_id) REFERENCES groups_table(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS private_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user INTEGER NOT NULL,
            to_user INTEGER NOT NULL,
            content TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at INTEGER,
            FOREIGN KEY (from_user) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (to_user) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            ref_id INTEGER,
            text TEXT,
            is_read INTEGER DEFAULT 0,
            created_at INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_posts_user ON posts(user_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(created_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_pm_from ON private_messages(from_user)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_pm_to ON private_messages(to_user)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_gm_group ON group_messages(group_id)")

    conn.commit()
    log("Database initialized at " + DB_PATH)


def row_to_dict(row):
    if row is None:
        return None
    return dict(row)


def execute(query, params=(), commit=True):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(query, params)
    if commit:
        conn.commit()
    return cur


def fetch_one(query, params=()):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(query, params)
    return row_to_dict(cur.fetchone())


def fetch_all(query, params=()):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(query, params)
    return [row_to_dict(r) for r in cur.fetchall()]


def get_user_by_id(uid):
    return fetch_one("SELECT * FROM users WHERE id = ?", (uid,))


def get_user_by_username(username):
    return fetch_one("SELECT * FROM users WHERE username = ?", (username,))


def get_user_by_email(email):
    return fetch_one("SELECT * FROM users WHERE email = ?", (email,))


def create_user(username, email, password_hash, display_name):
    cur = execute(
        "INSERT INTO users (username, email, password_hash, display_name, created_at) VALUES (?, ?, ?, ?, ?)",
        (username, email, password_hash, display_name, now_ms())
    )
    return cur.lastrowid


def update_user(uid, fields):
    allowed = ["display_name", "avatar", "bio", "password_hash"]
    sets = []
    values = []
    for k, v in fields.items():
        if k in allowed:
            sets.append(k + " = ?")
            values.append(v)
    if not sets:
        return False
    values.append(uid)
    execute("UPDATE users SET " + ", ".join(sets) + " WHERE id = ?", tuple(values))
    return True


def create_session(token, user_id, expires_at):
    execute(
        "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (token, user_id, now_ms(), expires_at)
    )


def get_session(token):
    return fetch_one("SELECT * FROM sessions WHERE token = ?", (token,))


def delete_session(token):
    execute("DELETE FROM sessions WHERE token = ?", (token,))


def delete_expired_sessions():
    execute("DELETE FROM sessions WHERE expires_at < ?", (now_ms(),))
