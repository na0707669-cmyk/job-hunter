-- users 테이블에 is_approved 컬럼 추가 (회원가입 승인제)
-- Supabase Dashboard > SQL Editor 에서 실행하세요.
-- 기존 유저는 모두 자동 승인 상태(TRUE)로 처리됩니다.

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS is_approved BOOLEAN NOT NULL DEFAULT TRUE;
