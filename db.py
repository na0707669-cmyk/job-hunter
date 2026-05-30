import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
import bcrypt

DATABASE_URL = os.environ.get("DATABASE_URL", "")


@contextmanager
def _conn():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    pw_hash TEXT NOT NULL,
                    is_admin BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS resumes (
                    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                    content TEXT DEFAULT '',
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS bookmarks (
                    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                    job_ids JSONB DEFAULT '[]',
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)
    seed = os.environ.get("INITIAL_ADMIN_USER", "")
    if seed and ":" in seed:
        username, password = seed.split(":", 1)
        if not get_user(username):
            create_user(username, password, is_admin=True)


def get_user(username):
    with _conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE username=%s", (username,))
            row = cur.fetchone()
            return dict(row) if row else None


def get_user_by_id(user_id):
    with _conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE id=%s", (user_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def create_user(username, password, is_admin=False):
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, pw_hash, is_admin) VALUES (%s,%s,%s) RETURNING id",
                (username, pw_hash, is_admin),
            )
            uid = cur.fetchone()[0]
            cur.execute("INSERT INTO resumes (user_id) VALUES (%s)", (uid,))
            cur.execute("INSERT INTO bookmarks (user_id) VALUES (%s)", (uid,))


def delete_user(user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE id=%s", (user_id,))


def check_password(username, password):
    user = get_user(username)
    if not user:
        return None
    if bcrypt.checkpw(password.encode(), user["pw_hash"].encode()):
        return user
    return None


def list_users():
    with _conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, username, is_admin, created_at FROM users ORDER BY id")
            return [dict(r) for r in cur.fetchall()]


def get_resume(user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT content FROM resumes WHERE user_id=%s", (user_id,))
            row = cur.fetchone()
            return row[0] if row else ""


def save_resume(user_id, content):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO resumes (user_id,content,updated_at) VALUES (%s,%s,NOW()) "
                "ON CONFLICT (user_id) DO UPDATE SET content=EXCLUDED.content, updated_at=NOW()",
                (user_id, content),
            )


def get_bookmarks(user_id):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT job_ids FROM bookmarks WHERE user_id=%s", (user_id,))
            row = cur.fetchone()
            return row[0] if row else []


def save_bookmarks(user_id, job_ids):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO bookmarks (user_id,job_ids,updated_at) VALUES (%s,%s::jsonb,NOW()) "
                "ON CONFLICT (user_id) DO UPDATE SET job_ids=EXCLUDED.job_ids, updated_at=NOW()",
                (user_id, json.dumps(job_ids)),
            )
