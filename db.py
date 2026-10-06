"""
db.py - طبقة قاعدة البيانات
يستخدم PostgreSQL لما يلاقي DATABASE_URL (Railway/Cloud) وإلا SQLite للتطوير المحلي.
"""
import os
import secrets
import time
import json
import threading

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# ─── اختيار نوع قاعدة البيانات ─────────────────────────────────────────────
USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras
    _pg_lock = threading.Lock()
else:
    import sqlite3
    from contextlib import contextmanager
    DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "remote_admin.db"))
    _lock = threading.Lock()


# ─── PostgreSQL helpers ──────────────────────────────────────────────────────

def _pg_conn():
    url = DATABASE_URL
    # Railway بيبعت postgres:// لكن psycopg2 بيحتاج postgresql://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    conn = psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = False
    return conn


def _pg_exec(sql, params=(), fetchone=False, fetchall=False, lastrowid=False):
    with _pg_lock:
        conn = _pg_conn()
        try:
            cur = conn.cursor()
            cur.execute(sql, params)
            conn.commit()
            if fetchone:
                return cur.fetchone()
            if fetchall:
                return cur.fetchall()
            if lastrowid:
                return cur.fetchone()[0] if cur.rowcount else None
            return None
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


# ─── SQLite helpers ──────────────────────────────────────────────────────────

if not USE_POSTGRES:
    from contextlib import contextmanager

    @contextmanager
    def get_conn():
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


# ─── init_db ─────────────────────────────────────────────────────────────────

def init_db():
    if USE_POSTGRES:
        sql = """
        CREATE TABLE IF NOT EXISTS users (
            chat_id BIGINT PRIMARY KEY,
            device_id TEXT UNIQUE,
            device_name TEXT,
            token TEXT UNIQUE,
            paired_at DOUBLE PRECISION
        );
        CREATE TABLE IF NOT EXISTS pairing_codes (
            code TEXT PRIMARY KEY,
            chat_id BIGINT NOT NULL,
            expires_at DOUBLE PRECISION NOT NULL
        );
        CREATE TABLE IF NOT EXISTS commands (
            id SERIAL PRIMARY KEY,
            device_id TEXT NOT NULL,
            command TEXT NOT NULL,
            args TEXT,
            status TEXT DEFAULT 'pending',
            result TEXT,
            created_at DOUBLE PRECISION,
            updated_at DOUBLE PRECISION
        );
        """
        with _pg_lock:
            conn = _pg_conn()
            try:
                cur = conn.cursor()
                cur.execute(sql)
                conn.commit()
            finally:
                conn.close()
    else:
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
                status TEXT DEFAULT 'pending',
                result TEXT,
                created_at REAL,
                updated_at REAL
            );
            """)


# ─── Pairing ──────────────────────────────────────────────────────────────────

def create_pairing_code(chat_id: int, ttl_seconds: int = 300) -> str:
    code = f"{secrets.randbelow(900000) + 100000}"
    expires_at = time.time() + ttl_seconds

    if USE_POSTGRES:
        _pg_exec("DELETE FROM pairing_codes WHERE chat_id = %s", (chat_id,))
        _pg_exec(
            "INSERT INTO pairing_codes (code, chat_id, expires_at) VALUES (%s, %s, %s)",
            (code, chat_id, expires_at),
        )
    else:
        with get_conn() as conn:
            conn.execute("DELETE FROM pairing_codes WHERE chat_id = ?", (chat_id,))
            conn.execute(
                "INSERT INTO pairing_codes (code, chat_id, expires_at) VALUES (?, ?, ?)",
                (code, chat_id, expires_at),
            )
    return code


def consume_pairing_code(code: str, device_id: str, device_name: str):
    """يتحقق من الكود، ولو صح يربط الجهاز بالمستخدم ويرجع توكن جديد."""
    if USE_POSTGRES:
        with _pg_lock:
            conn = _pg_conn()
            try:
                cur = conn.cursor()
                cur.execute("SELECT * FROM pairing_codes WHERE code = %s", (code,))
                row = cur.fetchone()
                if not row:
                    return None, "كود غير صحيح"
                if row["expires_at"] < time.time():
                    cur.execute("DELETE FROM pairing_codes WHERE code = %s", (code,))
                    conn.commit()
                    return None, "الكود منتهي الصلاحية"

                token = secrets.token_hex(32)
                cur.execute(
                    """INSERT INTO users (chat_id, device_id, device_name, token, paired_at)
                       VALUES (%s, %s, %s, %s, %s)
                       ON CONFLICT(chat_id) DO UPDATE SET
                         device_id=EXCLUDED.device_id,
                         device_name=EXCLUDED.device_name,
                         token=EXCLUDED.token,
                         paired_at=EXCLUDED.paired_at""",
                    (row["chat_id"], device_id, device_name, token, time.time()),
                )
                cur.execute("DELETE FROM pairing_codes WHERE code = %s", (code,))
                conn.commit()
                return {"token": token, "chat_id": row["chat_id"]}, None
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
    else:
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
    if USE_POSTGRES:
        return _pg_exec("SELECT * FROM users WHERE chat_id = %s", (chat_id,), fetchone=True)
    else:
        with get_conn() as conn:
            return conn.execute("SELECT * FROM users WHERE chat_id = ?", (chat_id,)).fetchone()


def get_user_by_token(token: str):
    if USE_POSTGRES:
        return _pg_exec("SELECT * FROM users WHERE token = %s", (token,), fetchone=True)
    else:
        with get_conn() as conn:
            return conn.execute("SELECT * FROM users WHERE token = ?", (token,)).fetchone()


def unpair(chat_id: int):
    if USE_POSTGRES:
        _pg_exec("DELETE FROM users WHERE chat_id = %s", (chat_id,))
    else:
        with get_conn() as conn:
            conn.execute("DELETE FROM users WHERE chat_id = ?", (chat_id,))


# ─── Commands ────────────────────────────────────────────────────────────────

def push_command(device_id: str, command: str, args: dict = None) -> int:
    now = time.time()
    if USE_POSTGRES:
        with _pg_lock:
            conn = _pg_conn()
            try:
                cur = conn.cursor()
                cur.execute(
                    """INSERT INTO commands (device_id, command, args, status, created_at, updated_at)
                       VALUES (%s, %s, %s, 'pending', %s, %s) RETURNING id""",
                    (device_id, command, json.dumps(args or {}), now, now),
                )
                row = cur.fetchone()
                conn.commit()
                return row["id"]
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
    else:
        with get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO commands (device_id, command, args, status, created_at, updated_at)
                   VALUES (?, ?, ?, 'pending', ?, ?)""",
                (device_id, command, json.dumps(args or {}), now, now),
            )
            return cur.lastrowid


def pop_pending_commands(device_id: str, limit: int = 5):
    if USE_POSTGRES:
        return _pg_exec(
            "SELECT * FROM commands WHERE device_id = %s AND status = 'pending' ORDER BY id ASC LIMIT %s",
            (device_id, limit),
            fetchall=True,
        ) or []
    else:
        with get_conn() as conn:
            return conn.execute(
                """SELECT * FROM commands WHERE device_id = ? AND status = 'pending'
                   ORDER BY id ASC LIMIT ?""",
                (device_id, limit),
            ).fetchall()


def set_command_result(cmd_id: int, status: str, result: str):
    if USE_POSTGRES:
        _pg_exec(
            "UPDATE commands SET status = %s, result = %s, updated_at = %s WHERE id = %s",
            (status, result, time.time(), cmd_id),
        )
    else:
        with get_conn() as conn:
            conn.execute(
                "UPDATE commands SET status = ?, result = ?, updated_at = ? WHERE id = ?",
                (status, result, time.time(), cmd_id),
            )


def get_command(cmd_id: int):
    if USE_POSTGRES:
        return _pg_exec("SELECT * FROM commands WHERE id = %s", (cmd_id,), fetchone=True)
    else:
        with get_conn() as conn:
            return conn.execute("SELECT * FROM commands WHERE id = ?", (cmd_id,)).fetchone()
