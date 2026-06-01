-- resumes 테이블에 versions 컬럼 추가
-- Supabase Dashboard > SQL Editor 에서 실행하세요.

ALTER TABLE resumes
  ADD COLUMN IF NOT EXISTS versions JSONB NOT NULL DEFAULT '[]';
