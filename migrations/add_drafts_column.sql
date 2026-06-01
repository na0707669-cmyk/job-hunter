-- bookmarks 테이블에 drafts 컬럼 추가
-- Supabase Dashboard > SQL Editor 에서 실행하세요.

ALTER TABLE bookmarks
  ADD COLUMN IF NOT EXISTS drafts JSONB NOT NULL DEFAULT '{}';
