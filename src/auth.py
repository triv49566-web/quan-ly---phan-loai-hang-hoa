# -*- coding: utf-8 -*-
"""
Tài khoản đăng nhập: lưu trong bảng `users` của cùng file SQLite.

Mật khẩu KHÔNG bao giờ được lưu dạng chữ thường: mỗi tài khoản có một chuỗi
"muối" (salt) ngẫu nhiên, mật khẩu được băm bằng PBKDF2-HMAC-SHA256 nhiều vòng.
Chỉ dùng thư viện chuẩn của Python, không cần cài thêm gì.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import sqlite3

import pandas as pd

ITERATIONS = 240_000
MIN_PASSWORD = 8
USERNAME_RE = re.compile(r"^[a-z0-9_.-]{3,32}$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    full_name     TEXT DEFAULT '',
    password_hash TEXT NOT NULL,   -- dạng: pbkdf2_sha256$<vòng>$<salt hex>$<hash hex>
    is_admin      INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
"""


def init(conn: sqlite3.Connection) -> None:
    with conn:
        conn.executescript(SCHEMA)


# ---------------------------------------------------------------------------
# Băm & kiểm tra mật khẩu
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}"


def check_password(password: str, stored: str) -> bool:
    try:
        algo, rounds, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                     bytes.fromhex(salt_hex), int(rounds))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest.hex(), hash_hex)


# Băm sẵn một mật khẩu giả để tài khoản không tồn tại cũng tốn thời gian kiểm tra
# như tài khoản có thật (người ngoài không đoán được tên nào đang tồn tại).
_DUMMY_HASH = hash_password(secrets.token_hex(8))


# ---------------------------------------------------------------------------
# Kiểm tra dữ liệu nhập
# ---------------------------------------------------------------------------
def normalize_username(username: str) -> str:
    return (username or "").strip().lower()


def _check_username(username: str) -> str:
    u = normalize_username(username)
    if not USERNAME_RE.match(u):
        raise ValueError("Tên tài khoản dài 3–32 ký tự, chỉ gồm chữ không dấu, số, dấu . _ -")
    return u


def _check_new_password(password: str, confirm: str | None = None) -> None:
    if len(password or "") < MIN_PASSWORD:
        raise ValueError(f"Mật khẩu phải có ít nhất {MIN_PASSWORD} ký tự.")
    if confirm is not None and password != confirm:
        raise ValueError("Hai lần nhập mật khẩu không khớp.")


# ---------------------------------------------------------------------------
# Đọc / ghi tài khoản
# ---------------------------------------------------------------------------
def count_users(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def users_df(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT id, username, full_name, is_admin, created_at FROM users ORDER BY username", conn)


def create_user(conn: sqlite3.Connection, username: str, password: str, full_name: str = "",
                is_admin: bool = False, confirm: str | None = None) -> int:
    u = _check_username(username)
    _check_new_password(password, confirm)
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO users(username, full_name, password_hash, is_admin) VALUES (?, ?, ?, ?)",
                (u, (full_name or "").strip(), hash_password(password), int(bool(is_admin))))
    except sqlite3.IntegrityError:
        raise ValueError(f"Tài khoản “{u}” đã tồn tại.") from None
    return cur.lastrowid


def authenticate(conn: sqlite3.Connection, username: str, password: str) -> dict | None:
    """Trả về thông tin tài khoản nếu đúng tên & mật khẩu, ngược lại None."""
    row = conn.execute("SELECT id, username, full_name, password_hash, is_admin FROM users "
                       "WHERE username = ?", (normalize_username(username),)).fetchone()
    if row is None:
        check_password(password or "", _DUMMY_HASH)
        return None
    if not check_password(password or "", row["password_hash"]):
        return None
    return {"id": row["id"], "username": row["username"],
            "full_name": row["full_name"] or row["username"], "is_admin": bool(row["is_admin"])}


def get_user(conn: sqlite3.Connection, user_id: int) -> dict | None:
    row = conn.execute("SELECT id, username, full_name, is_admin FROM users WHERE id = ?",
                       (user_id,)).fetchone()
    if row is None:
        return None
    return {"id": row["id"], "username": row["username"],
            "full_name": row["full_name"] or row["username"], "is_admin": bool(row["is_admin"])}


def change_password(conn: sqlite3.Connection, user_id: int, old: str, new: str, confirm: str) -> None:
    row = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None or not check_password(old or "", row["password_hash"]):
        raise ValueError("Mật khẩu hiện tại không đúng.")
    _check_new_password(new, confirm)
    with conn:
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(new), user_id))


def reset_password(conn: sqlite3.Connection, user_id: int, new: str) -> None:
    """Quản trị viên đặt lại mật khẩu cho người khác."""
    _check_new_password(new)
    with conn:
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(new), user_id))


def delete_user(conn: sqlite3.Connection, user_id: int, acting_user_id: int) -> None:
    if user_id == acting_user_id:
        raise ValueError("Không thể tự xóa tài khoản đang đăng nhập.")
    row = conn.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        raise ValueError("Tài khoản không tồn tại.")
    if row["is_admin"]:
        admins = conn.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1").fetchone()[0]
        if admins <= 1:
            raise ValueError("Phải còn ít nhất một tài khoản quản trị.")
    with conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


def ensure_admin_from_secrets(conn: sqlite3.Connection, username: str | None,
                              password: str | None) -> bool:
    """Khi chưa có tài khoản nào: tạo quản trị viên từ cấu hình bí mật (nếu có)."""
    if count_users(conn) > 0 or not username or not password:
        return False
    create_user(conn, username, password, full_name="Quản trị viên", is_admin=True)
    return True
