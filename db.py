"""
db.py - طبقة قاعدة البيانات (SQLite)
تدير: المستخدمين المربوطين، أكواد الـ pairing المؤقتة، والأوامر المعلّقة/المنفذة.
"""
import sqlite3
import secrets
import time
import json
import threading
from contextlib import contextmanager

DB_PATH = "remote_admin.db"
_lock = threading.Lock()


def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER PRIMARY KEY,
            device_id TEXT UNIQUE,
            device_name TEXT,
            token TEXT UNIQUE,
            paired_at REAL
        );

        CREATE TABLE IF NOT EXISTS pairing_codes (
            code TEXT PRIMARY KEY,
            chat_id INTEGER NOT NULL,
            expires_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            command TEXT NOT NULL,
            args TEXT,
            status TEXT DEFAULT 'pending',  -- pending | done | error
            result TEXT,
            created_at REAL,
            updated_at REAL
        );
        """)


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ---------- Pairing ----------

def create_pairing_code(chat_id: int, ttl_seconds: int = 300) -> str:
    code = f"{secrets.randbelow(900000) + 100000}"  # 6 أرقام
    expires_at = time.time() + ttl_seconds
    with get_conn() as conn:
        conn.execute("DELETE FROM pairing_codes WHERE chat_id = ?", (chat_id,))
        conn.execute(
            "INSERT INTO pairing_codes (code, chat_id, expires_at) VALUES (?, ?, ?)",
            (code, chat_id, expires_at),
        )
    return code


def consume_pairing_code(code: str, device_id: str, device_name: str):
    """يتحقق من الكود، ولو صح يربط الجهاز بالمستخدم ويرجع توكن جديد."""
    with _lock, get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM pairing_codes WHERE code = ?", (code,)
        ).fetchone()
        if not row:
            return None, "كود غير صحيح"
        if row["expires_at"] < time.time():
            conn.execute("DELETE FROM pairing_codes WHERE code = ?", (code,))
            return None, "الكود منتهي الصلاحية"

        token = secrets.token_hex(32)
        conn.execute(
            """INSERT INTO users (chat_id, device_id, device_name, token, paired_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(chat_id) DO UPDATE SET
                 device_id=excluded.device_id,
                 device_name=excluded.device_name,
                 token=excluded.token,
                 paired_at=excluded.paired_at""",
            (row["chat_id"], device_id, device_name, token, time.time()),
        )
        conn.execute("DELETE FROM pairing_codes WHERE code = ?", (code,))
        return {"token": token, "chat_id": row["chat_id"]}, None


def get_user_by_chat(chat_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE chat_id = ?", (chat_id,)
        ).fetchone()


def get_user_by_token(token: str):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE token = ?", (token,)
        ).fetchone()


def unpair(chat_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM users WHERE chat_id = ?", (chat_id,))


# ---------- Commands ----------

def push_command(device_id: str, command: str, args: dict = None) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO commands (device_id, command, args, status, created_at, updated_at)
               VALUES (?, ?, ?, 'pending', ?, ?)""",
            (device_id, command, json.dumps(args or {}), time.time(), time.time()),
        )
        return cur.lastrowid


def pop_pending_commands(device_id: str, limit: int = 5):
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM commands WHERE device_id = ? AND status = 'pending'
               ORDER BY id ASC LIMIT ?""",
            (device_id, limit),
        ).fetchall()
        return rows


def set_command_result(cmd_id: int, status: str, result: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE commands SET status = ?, result = ?, updated_at = ? WHERE id = ?",
            (status, result, time.time(), cmd_id),
        )


def get_command(cmd_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM commands WHERE id = ?", (cmd_id,)
        ).fetchone()
