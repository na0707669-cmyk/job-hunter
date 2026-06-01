-- 지원 현황 트래커 테이블
-- Supabase Dashboard → SQL Editor에서 실행

CREATE TABLE IF NOT EXISTS applications (
  id         SERIAL PRIMARY KEY,
  user_id    INT REFERENCES users(id) ON DELETE CASCADE,
  job_key    TEXT NOT NULL,          -- "company|title" 형식
  company    TEXT DEFAULT '',
  title      TEXT DEFAULT '',
  link       TEXT DEFAULT '',
  site       TEXT DEFAULT '',
  status     TEXT DEFAULT 'saved',   -- saved/applying/applied/docs_pass/interview/offer/rejected
  notes      TEXT DEFAULT '',
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(user_id, job_key)
);

CREATE INDEX IF NOT EXISTS idx_applications_user_id ON applications(user_id);
