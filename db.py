import os
import json
from datetime import datetime
import bcrypt
import requests as _req

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")


def _h(prefer=None):
    h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
    if prefer:
        h["Prefer"] = prefer
    return h


def _url(table):
    return f"{SUPABASE_URL}/rest/v1/{table}"


def init_db():
    seed = os.environ.get("INITIAL_ADMIN_USER", "")
    if seed and ":" in seed:
        username, password = seed.split(":", 1)
        if not get_user(username):
            create_user(username, password, is_admin=True)


def get_user(username):
    r = _req.get(_url("users"), headers=_h(), params={"username": f"eq.{username}", "select": "*"}, timeout=10)
    data = r.json()
    return data[0] if isinstance(data, list) and data else None


def get_user_by_id(user_id):
    r = _req.get(_url("users"), headers=_h(), params={"id": f"eq.{user_id}", "select": "*"}, timeout=10)
    data = r.json()
    return data[0] if isinstance(data, list) and data else None


def create_user(username, password, is_admin=False):
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    r = _req.post(_url("users"), headers=_h("return=representation"),
                  json={"username": username, "pw_hash": pw_hash, "is_admin": is_admin}, timeout=10)
    r.raise_for_status()
    uid = r.json()[0]["id"]
    _req.post(_url("resumes"), headers=_h(), json={"user_id": uid, "content": ""}, timeout=10)
    _req.post(_url("bookmarks"), headers=_h(), json={"user_id": uid, "job_ids": []}, timeout=10)


def delete_user(user_id):
    _req.delete(_url("users"), headers=_h(), params={"id": f"eq.{user_id}"}, timeout=10)


def check_password(username, password):
    user = get_user(username)
    if not user:
        return None
    if bcrypt.checkpw(password.encode(), user["pw_hash"].encode()):
        return user
    return None


def list_users():
    r = _req.get(_url("users"), headers=_h(),
                 params={"select": "id,username,is_admin,created_at", "order": "id"}, timeout=10)
    return r.json() if isinstance(r.json(), list) else []


def get_resume(user_id):
    r = _req.get(_url("resumes"), headers=_h(),
                 params={"user_id": f"eq.{user_id}", "select": "content,structured,analysis,analyzed_at"}, timeout=10)
    data = r.json()
    if isinstance(data, list) and data:
        row = data[0]
        return row.get("content", ""), row.get("structured", {}), row.get("analysis", ""), row.get("analyzed_at", "")
    return "", {}, "", ""


def save_resume(user_id, content, structured=None):
    payload = {"content": content, "updated_at": datetime.utcnow().isoformat()}
    if structured is not None:
        payload["structured"] = structured
    _req.patch(_url("resumes"), headers=_h(), params={"user_id": f"eq.{user_id}"},
               json=payload, timeout=10)


def save_analysis(user_id, analysis):
    _req.patch(_url("resumes"), headers=_h(), params={"user_id": f"eq.{user_id}"},
               json={"analysis": analysis, "analyzed_at": datetime.utcnow().isoformat()}, timeout=10)


def get_bookmarks(user_id):
    r = _req.get(_url("bookmarks"), headers=_h(), params={"user_id": f"eq.{user_id}", "select": "job_ids"}, timeout=10)
    data = r.json()
    return data[0]["job_ids"] if isinstance(data, list) and data else []


def save_bookmarks(user_id, job_ids):
    _req.patch(_url("bookmarks"), headers=_h(), params={"user_id": f"eq.{user_id}"},
               json={"job_ids": job_ids, "updated_at": datetime.utcnow().isoformat()}, timeout=10)
