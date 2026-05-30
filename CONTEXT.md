# JOB HUNTER — LLM 인계 컨텍스트

> 이 문서는 다른 LLM 세션에서 본 프로젝트를 이어받아 작업할 때 사용하는 컨텍스트입니다.

---

## 프로젝트 한 줄 정의

한국 취업 공고(사람인·잡코리아·그룹바이·자소설닷컴) 자동 수집 + 필터링 + AI 매칭 웹앱.
Flask + Playwright + DeepSeek v4 Flash. Render(무료) 배포 완료.

---

## 현재 상태 (완료된 것)

### 크롤링
- [x] 사람인 크롤러 (requests + BeautifulSoup)
- [x] 잡코리아 크롤러 (requests + BeautifulSoup)
- [x] 그룹바이 크롤러 (requests + __NEXT_DATA__ JSON)
- [x] 자소설닷컴 크롤러 (Playwright 헤드리스 Chromium)
- [x] 병렬 크롤링 (ThreadPoolExecutor)
- [x] 10분 서버 캐시
- [x] 중복 제거
- [x] 경력 필터 전사이트 (신입/경력/무관 정규화, `_normalize_career()`)

### UI / 필터
- [x] 기업 규모 필터 (전체/대기업/중견중소/스타트업)
- [x] D-day 배지 (마감일 파싱)
- [x] 지역 필터
- [x] 경력 필터
- [x] AI매칭만 필터 (매칭된 공고만 표시)
- [x] 마감 임박순 / NEW 우선 / 매칭순 정렬
- [x] 북마크 (서버 DB 저장)
- [x] 키워드 히스토리 (localStorage)
- [x] NEW 배지 (seen.json 기반)

### 인증 / 유저
- [x] 로그인 / 로그아웃 (/login, /logout)
- [x] 공개 회원가입 (/register)
- [x] 관리자 유저 관리 페이지 (/admin) — 유저 추가/삭제
- [x] Flask session 기반 인증
- [x] bcrypt 비밀번호 해싱
- [x] INITIAL_ADMIN_USER 환경변수로 첫 관리자 자동 생성

### AI 기능 (DeepSeek v4 Flash)
- [x] 이력서 저장 시 JSON 자동 구조화 (이름/희망직군/기술스택/자격증 등)
- [x] 이력서 분석 — 추천 키워드(클릭 시 검색), 적합 직군, 강점, 보완 포인트 (이력서 내용 인용)
- [x] 이력서 분석 결과 DB 저장 + 페이지 로드 시 자동 복원 (날짜 표시)
- [x] AI 매칭 — 공고별 매칭율 0~100 + 한줄 이유 (수동 버튼)
- [x] 자소서 초안 — 📝 버튼 → 우측 패널 → 공고 페이지 실시간 스크래핑 + 기본 문항 5개 + DeepSeek 작성

### DB (Supabase REST API)
- [x] users 테이블 (id, username, pw_hash, is_admin, created_at)
- [x] resumes 테이블 (user_id, content, structured, analysis, analyzed_at, updated_at)
- [x] bookmarks 테이블 (user_id, job_ids JSONB, updated_at)
- [x] psycopg2 없음 — requests로 Supabase REST API 직접 호출 (IPv6 이슈 우회)

### 배포
- [x] Render 무료 배포
- [x] GitHub Actions keepalive (명시적 분 지정 스케줄: `2,16,30,44,58 * * * *`)

---

## 파일 구조

```
job_hunt.py        크롤러 코어
  - search_saramin(keyword)     → list[job]
  - search_jobkorea(keyword)    → list[job]
  - search_groupby(keyword)     → list[job]
  - search_jasoseol(keyword)    → list[job] (Playwright)
  - _normalize_career(txt)      → "신입"|"경력"|"무관"|""
  - dedup(jobs) / mark_new(jobs) / save_seen(jobs) / load_seen()

db.py              Supabase REST API 클라이언트
  - init_db()                   → INITIAL_ADMIN_USER로 첫 관리자 생성
  - get/create/delete_user()
  - check_password()
  - list_users()
  - get/save_resume()           → (content, structured, analysis, analyzed_at)
  - save_analysis()
  - get/save_bookmarks()

app.py             Flask 웹서버 + Jinja2 HTML (전부 인라인)
  - CACHE dict (10분 TTL)
  - GET  /                      → 검색 결과 (login_required)
  - GET/POST /login, /logout, /register
  - GET  /admin                 → 유저 목록 (admin_required)
  - POST /admin/users           → 유저 추가
  - POST /admin/users/<id>/delete
  - GET/POST /api/resume        → 이력서 저장(구조화 포함)/조회
  - POST /api/analyze           → 이력서 분석 + DB 저장
  - POST /api/match             → AI 매칭 (공고 목록 기반)
  - POST /api/draft             → 자소서 초안 (공고 스크래핑 포함)
  - POST /api/bookmarks         → 북마크 저장/조회
  - GET  /health                → DB 상태 확인

Dockerfile         Render 배포용 (python:3.12-slim)
requirements.txt   flask, requests, beautifulsoup4, playwright, bcrypt

.github/workflows/keepalive.yml   명시적 분 스케줄로 Render 핑
seen.json          이전 검색 결과 ID 목록 (gitignore)
```

---

## job 객체 스키마

```python
{
    "site": "사람인" | "잡코리아" | "그룹바이" | "자소설닷컴",
    "size": "대기업·중소" | "중견·중소" | "스타트업" | "대기업",
    "company": str,
    "title": str,
    "link": str,
    "deadline": str,      # "2026.06.30" 형식 또는 ""
    "dday": int | None,
    "location": str,
    "career": str,        # "신입" | "경력" | "무관" | ""
    "is_new": bool,
    # 그룹바이 전용:
    "stacks": str,        # "Python, FastAPI, AWS"
    "funding": str,       # "Pre-A" | "A" | "B" 등
    "members": int,
}
```

---

## 환경변수 (Render)

| 변수 | 설명 |
|---|---|
| `SUPABASE_URL` | `https://shsijosqjnfhmuooiyfv.supabase.co` |
| `SUPABASE_KEY` | service_role JWT |
| `SECRET_KEY` | Flask session 서명키 |
| `INITIAL_ADMIN_USER` | `username:password` (최초 1회 관리자 생성) |
| `DEEPSEEK_API_KEY` | DeepSeek API 키 (sk-...) |

---

## 배포 정보

| 항목 | 값 |
|---|---|
| 라이브 URL | https://job-hunter-v28m.onrender.com |
| GitHub repo | https://github.com/na0707669-cmyk/job-hunter |
| 플랫폼 | Render (무료, Docker) |
| keepalive | GitHub Actions, `2,16,30,44,58 * * * *` |
| 자동배포 | main 브랜치 push 시 Render 자동 재배포 |
| DB | Supabase 무료 (ap-northeast-1, project: shsijosqjnfhmuooiyfv) |

---

## 기술 결정 기록

| 결정 | 이유 |
|---|---|
| Supabase REST API (requests) | psycopg2 direct/pooler 연결 불가 (Render IPv6 미지원, API 생성 프로젝트 pooler 미등록) |
| deepseek-v4-flash | deepseek-chat 2026-07-24 은퇴 예정. V4 Flash가 현재 최신 |
| Playwright (자소설닷컴만) | 나머지 3개는 requests로 충분 |
| 인메모리 캐시 | DB 없이 간단하게, 10분 TTL |
| 공개 회원가입 | 소수 지인 공유 목적, 관리자가 별도 추가 불필요 |

---

## 미완성 / 다음 작업 후보

- [ ] AI 매칭 결과 시각화 개선 (색상 구분 더 명확히)
- [ ] 자소서 문항 자동 크롤링 (현재 사용자가 직접 입력)
- [ ] 사전 크롤링 구조 전환 (속도 근본 해결)
- [ ] CSV 내보내기
- [ ] 회사 정보 자동 서치 (DART API 등)

---

## 로컬 실행

```bash
git clone https://github.com/na0707669-cmyk/job-hunter.git
cd job-hunter
pip install -r requirements.txt
playwright install chromium
python app.py
# → http://localhost:5000 (DB 없이 실행 시 로그인 없이 크롤링만 동작)
```

---

## 작업 인계 프롬프트

```
CONTEXT.md 읽고 현재 상태 파악해줘.
GitHub: https://github.com/na0707669-cmyk/job-hunter
라이브: https://job-hunter-v28m.onrender.com

[여기에 요청사항 입력]
```
