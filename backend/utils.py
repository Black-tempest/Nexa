import os
import time
import hashlib
import secrets
from datetime import datetime


def log(message):
    now = datetime.now().strftime("%H:%M:%S")
    print("[" + now + "] [NEXA] " + str(message), flush=True)


def now_ms():
    return int(time.time() * 1000)


def now_iso():
    return datetime.now().isoformat()


def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100000
    )
    return salt + ":" + hashed.hex()


def verify_password(password, stored):
    try:
        salt, _ = stored.split(":", 1)
        return hash_password(password, salt) == stored
    except Exception:
        return False


def generate_token(length=32):
    return secrets.token_urlsafe(length)


def clean_text(text, max_length=5000):
    if not text:
        return ""
    text = str(text).strip()
    if len(text) > max_length:
        text = text[:max_length]
    return text


def safe_username(username):
    if not username:
        return ""
    u = str(username).strip().lower()
    u = "".join(c for c in u if c.isalnum() or c in "._-")
    return u[:30]


def is_valid_username(username):
    if not username:
        return False
    u = str(username).strip()
    if len(u) < 3 or len(u) > 30:
        return False
    return all(c.isalnum() or c in "._-" for c in u)


def is_valid_email(email):
    if not email:
        return False
    e = str(email).strip()
    if "@" not in e or "." not in e.split("@")[-1]:
        return False
    return len(e) <= 100


def is_valid_password(password):
    if not password:
        return False
    return len(str(password)) >= 6


def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
