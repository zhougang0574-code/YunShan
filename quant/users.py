"""用户与收藏（轻量本地存储，供个人/小范围使用）。

存到本地 SQLite（``data/users.db``）。密码用标准库 ``hashlib.pbkdf2_hmac`` 加盐
哈希，不引入第三方依赖；登录后发一个随机 token（``secrets``）做会话凭证。
收藏按用户隔离：每个用户只看到自己收藏的股票。

设计刻意从简（项目只供几人使用）：连接每次开关、无连接池、token 不过期（登出即删）。
"""

import datetime
import hashlib
import hmac
import secrets
import sqlite3

from . import config

_DB_PATH = config.DATA_DIR / "users.db"

_PBKDF2_ITERATIONS = 200_000


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    config.DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            pwd_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tokens (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            name TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(user_id, symbol)
        )
        """
    )
    return conn


# ---- 密码哈希 ----


def _hash_password(password: str, salt: str) -> str:
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), _PBKDF2_ITERATIONS
    )
    return dk.hex()


# ---- 用户 ----


class UserExistsError(Exception):
    """用户名已被占用。"""


def create_user(username: str, password: str) -> dict:
    """新建用户，返回 {id, username}。用户名已存在则抛 UserExistsError。"""
    username = username.strip()
    salt = secrets.token_bytes(16).hex()
    pwd_hash = _hash_password(password, salt)
    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO users (username, pwd_hash, salt, created_at)"
                " VALUES (?, ?, ?, ?)",
                (username, pwd_hash, salt, _now()),
            )
        return {"id": cur.lastrowid, "username": username}
    except sqlite3.IntegrityError as err:
        raise UserExistsError(username) from err
    finally:
        conn.close()


def verify_user(username: str, password: str) -> dict | None:
    """校验用户名+密码，成功返回 {id, username}，否则 None。"""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT id, username, pwd_hash, salt FROM users WHERE username = ?",
            (username.strip(),),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    expected = row[2]
    actual = _hash_password(password, row[3])
    if not hmac.compare_digest(expected, actual):
        return None
    return {"id": row[0], "username": row[1]}


# ---- 会话 token ----


def create_token(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    conn = _connect()
    with conn:
        conn.execute(
            "INSERT INTO tokens (token, user_id, created_at) VALUES (?, ?, ?)",
            (token, user_id, _now()),
        )
    conn.close()
    return token


def user_for_token(token: str) -> dict | None:
    """凭 token 取当前用户 {id, username}；无效返回 None。"""
    if not token:
        return None
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT u.id, u.username FROM tokens t"
            " JOIN users u ON u.id = t.user_id WHERE t.token = ?",
            (token,),
        ).fetchone()
    finally:
        conn.close()
    return {"id": row[0], "username": row[1]} if row else None


def delete_token(token: str) -> None:
    conn = _connect()
    with conn:
        conn.execute("DELETE FROM tokens WHERE token = ?", (token,))
    conn.close()


# ---- 收藏 ----


def add_favorite(user_id: int, symbol: str, name: str | None = None) -> None:
    """加收藏；已收藏则幂等更新名称。"""
    conn = _connect()
    with conn:
        conn.execute(
            "INSERT INTO favorites (user_id, symbol, name, created_at)"
            " VALUES (?, ?, ?, ?)"
            " ON CONFLICT(user_id, symbol) DO UPDATE SET name = excluded.name",
            (user_id, symbol.strip(), name, _now()),
        )
    conn.close()


def remove_favorite(user_id: int, symbol: str) -> None:
    conn = _connect()
    with conn:
        conn.execute(
            "DELETE FROM favorites WHERE user_id = ? AND symbol = ?",
            (user_id, symbol.strip()),
        )
    conn.close()


def list_favorites(user_id: int) -> list[dict]:
    """返回该用户的收藏，最近收藏在前。"""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT symbol, name, created_at FROM favorites"
            " WHERE user_id = ? ORDER BY id DESC",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()
    return [{"symbol": r[0], "name": r[1] or "", "created_at": r[2]} for r in rows]
