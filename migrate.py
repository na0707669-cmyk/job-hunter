"""
Supabase 마이그레이션 헬퍼
환경변수 SUPABASE_URL, SUPABASE_KEY를 설정한 뒤 실행:

  set SUPABASE_URL=https://shsijosqjnfhmuooiyfv.supabase.co
  set SUPABASE_KEY=<service_role JWT>
  python migrate.py
"""
import os, requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

SQL_MIGRATIONS = [
    ("add_drafts_column",
     "ALTER TABLE bookmarks ADD COLUMN IF NOT EXISTS drafts JSONB NOT NULL DEFAULT '{}';"),
    ("add_versions_column",
     "ALTER TABLE resumes ADD COLUMN IF NOT EXISTS versions JSONB NOT NULL DEFAULT '[]';"),
    ("add_is_approved_column",
     "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_approved BOOLEAN NOT NULL DEFAULT TRUE;"),
    ("add_applications_table", """
CREATE TABLE IF NOT EXISTS applications (
  id         SERIAL PRIMARY KEY,
  user_id    INT REFERENCES users(id) ON DELETE CASCADE,
  job_key    TEXT NOT NULL,
  company    TEXT DEFAULT '',
  title      TEXT DEFAULT '',
  link       TEXT DEFAULT '',
  site       TEXT DEFAULT '',
  status     TEXT DEFAULT 'saved',
  notes      TEXT DEFAULT '',
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(user_id, job_key)
);
CREATE INDEX IF NOT EXISTS idx_applications_user_id ON applications(user_id);
"""),
]


def run_sql(name, sql):
    """Supabase Management API로 SQL 실행"""
    project_ref = SUPABASE_URL.replace("https://", "").split(".")[0]
    url = f"https://api.supabase.com/v1/projects/{project_ref}/database/query"
    headers = {
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    resp = requests.post(url, json={"query": sql.strip()}, headers=headers, timeout=30)
    if resp.status_code in (200, 201):
        print(f"  ✅ {name}")
    else:
        print(f"  ⚠️  {name} → HTTP {resp.status_code}: {resp.text[:200]}")
        print("     (Management API 토큰이 필요할 수 있습니다. Supabase Dashboard > SQL Editor에서 직접 실행하세요.)")


if __name__ == "__main__":
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ 환경변수 SUPABASE_URL, SUPABASE_KEY를 설정하세요.")
    else:
        print(f"Supabase 프로젝트: {SUPABASE_URL}")
        for name, sql in SQL_MIGRATIONS:
            run_sql(name, sql)
        print("\n대안: Supabase Dashboard → SQL Editor → migrations/ 폴더의 .sql 파일 직접 실행")
