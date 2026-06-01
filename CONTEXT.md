# JOB HUNTER — LLM 인계 컨텍스트

> 이 문서는 다른 LLM 세션에서 본 프로젝트를 이어받아 작업할 때 사용하는 컨텍스트입니다.

---

## 프로젝트 한 줄 정의

한국 취업 공고(사람인·잡코리아·그룹바이·자소설닷컴·원티드) 자동 수집 + 필터링 + AI 매칭 웹앱.
Flask + Playwright + DeepSeek v4 Flash. Render(무료) 배포 완료.

---

## 현재 상태 (완료된 것)

### 크롤링
- [x] 사람인 크롤러 (requests + BeautifulSoup)
- [x] 잡코리아 크롤러 (requests + BeautifulSoup)
- [x] 그룹바이 크롤러 (api.groupby.kr/startup-positions/search REST API)
- [x] 자소설닷컴 크롤러 (Playwright 헤드리스 Chromium)
- [x] 원티드 크롤러 (wanted.co.kr/api/v4/jobs REST API) — `query` 파라미터 사용
- [x] 병렬 크롤링 (ThreadPoolExecutor)
- [x] 10분 서버 캐시 (키워드별 독립 캐시 — 유사어 추가 시 기존 결과 재사용)
- [x] 중복 제거 — 링크 기준 + 동일 사이트 내 회사+직책 기준
- [x] 경력 필터 전사이트 (신입/경력/무관 정규화, `_normalize_career()`)
- [x] **원티드 career 파싱** — years=0(신입) API 선수집 후 메인 결과와 비교해 신입/경력 레이블 부여
- [x] deadline 형식 통일 — "D-5"/"즉시" 파싱 포함 (`_parse_dday()`)

### UI / 필터
- [x] 기업 규모 필터 (전체/대기업/중견중소/스타트업) — 프론트엔드 표시 필터만
- [x] **사이트별 체크박스** — 검색 시 크롤링할 사이트 개별 선택. 자소설닷컴에 "느림" 뱃지
- [x] **유사어 병합 검색** — 검색 후 관련 직무 칩 표시. 클릭 시 병합. X로 제거. (~111개 클러스터)
- [x] D-day 배지 (마감일 파싱)
- [x] 지역 필터
- [x] 경력 필터
- [x] AI매칭만 필터 (매칭된 공고만 표시)
- [x] 마감 임박순 / NEW 우선 / 매칭순 정렬
- [x] 북마크 (서버 DB 저장)
- [x] 키워드 히스토리 (localStorage)
- [x] NEW 배지 (seen.json 기반)
- [x] **CSV 내보내기** — /export.csv, 검색 결과 메타 영역에 ⬇ CSV 버튼, Excel용 UTF-8 BOM

### 인증 / 유저
- [x] 로그인 / 로그아웃 (/login, /logout)
- [x] 공개 회원가입 (/register)
- [x] 관리자 유저 관리 페이지 (/admin) — 유저 추가/삭제
- [x] Flask session 기반 인증
- [x] bcrypt 비밀번호 해싱
- [x] INITIAL_ADMIN_USER 환경변수로 첫 관리자 자동 생성
- [x] CSRF 토큰 보호 (로그인/회원가입/어드민 폼 4개)

### AI 기능 (DeepSeek v4 Flash)
- [x] 이력서 저장 시 JSON 자동 구조화 (이름/희망직군/기술스택/자격증 등)
- [x] 이력서 분석 — 추천 키워드(클릭 시 검색), 적합 직군, 강점, 보완 포인트 (이력서 내용 인용)
- [x] 이력서 분석 결과 DB 저장 + 페이지 로드 시 자동 복원 (날짜 표시)
- [x] **AI 매칭 품질 개선** — 스택 없는 공고(사람인·잡코리아)는 공고 페이지 병렬 스크래핑 후 직무설명 200자를 프롬프트에 추가
- [x] AI 매칭 — 공고별 매칭율 0~100 + 한줄 이유 (수동 버튼)
- [x] **자소서 초안** — 📝 버튼 → 우측 패널 → 공고 페이지 실시간 스크래핑 + 문항 + DeepSeek 작성
- [x] **자소서 문항 자동 생성** — 🔍 버튼 → 공고 내용 스크래핑 → DeepSeek로 해당 공고 특화 문항 5개 생성

### 이력서 / 자소서 관리
- [x] **이력서 버전 관리** — 📌 버전 저장 버튼, 최대 10개 보관, 메모 입력, 복원 가능 (resumes.versions JSONB)
- [x] **북마크에 자소서 저장** — 💾 저장 버튼, 저장된 공고에 📝 배지 표시, 패널 재오픈 시 자동 복원 (bookmarks.drafts JSONB)

### DB (Supabase REST API)
- [x] users 테이블 (id, username, pw_hash, is_admin, created_at)
- [x] resumes 테이블 (user_id, content, structured, analysis, analyzed_at, updated_at, **versions JSONB**)
- [x] bookmarks 테이블 (user_id, job_ids JSONB, updated_at, **drafts JSONB**)
- [x] psycopg2 없음 — requests로 Supabase REST API 직접 호출 (IPv6 이슈 우회)

### 배포
- [x] Render 무료 배포
- [x] GitHub Actions keepalive (명시적 분 지정 스케줄: `2,16,30,44,58 * * * *`)

---

## ⚠️ Supabase 마이그레이션 (미실행 시 일부 기능 비작동)

Supabase Dashboard → SQL Editor에서 실행:

```sql
-- 지원 현황 트래커 (migrations/add_applications_table.sql)
CREATE TABLE IF NOT EXISTS applications (
  id SERIAL PRIMARY KEY, user_id INT REFERENCES users(id) ON DELETE CASCADE,
  job_key TEXT NOT NULL, company TEXT DEFAULT '', title TEXT DEFAULT '',
  link TEXT DEFAULT '', site TEXT DEFAULT '', status TEXT DEFAULT 'saved',
  notes TEXT DEFAULT '', created_at TIMESTAMPTZ DEFAULT now(), updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(user_id, job_key)
);
CREATE INDEX IF NOT EXISTS idx_applications_user_id ON applications(user_id);

-- 북마크에 자소서 저장 (migrations/add_drafts_column.sql)
ALTER TABLE bookmarks ADD COLUMN IF NOT EXISTS drafts JSONB NOT NULL DEFAULT '{}';

-- 이력서 버전 관리 (migrations/add_versions_column.sql)
ALTER TABLE resumes ADD COLUMN IF NOT EXISTS versions JSONB NOT NULL DEFAULT '[]';

-- 회원가입 승인제 (migrations/add_is_approved_column.sql)
-- 기존 유저는 모두 TRUE(승인됨)로 처리됨
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_approved BOOLEAN NOT NULL DEFAULT TRUE;
```

---

## 파일 구조

```
app.py             Flask 웹서버 — 라우팅/비즈니스 로직
job_hunt.py        크롤러 코어
db.py              Supabase REST API 클라이언트

templates/
  index.html       메인 검색 페이지 (Jinja2)
  login.html       로그인
  register.html    회원가입
  admin.html       유저 관리

static/
  css/style.css    메인 앱 스타일
  css/auth.css     로그인/회원가입 스타일
  css/admin.css    어드민 스타일
  js/app.js        메인 앱 JavaScript

migrations/
  add_drafts_column.sql    bookmarks.drafts 컬럼 추가
  add_versions_column.sql  resumes.versions 컬럼 추가

.claude/
  settings.json    Claude Code 권한 설정 (python/git/pip/curl 자동 허용)

Dockerfile         Render 배포용 (python:3.12-slim)
requirements.txt   flask, requests, beautifulsoup4, playwright, bcrypt
.github/workflows/keepalive.yml   명시적 분 스케줄로 Render 핑
seen.json          이전 검색 결과 ID 목록 (gitignore)
```

### app.py 주요 구성
```
SCRAPERS dict              사이트명 → 크롤러 함수
ALL_SITES                  사이트 목록
_SYNONYM_GROUPS            유사어 클러스터 (~111개)
SYNONYM_LOOKUP             양방향 유사어 룩업 dict
get_synonyms(keyword)      키워드 → 관련 직무 리스트
_cache_key/get/set         키워드+사이트 조합별 독립 캐시
_fetch_company_info(url)   공고 페이지 스크래핑 (자소서 초안·매칭용)
_run(q, sites)             단일 키워드 크롤링 실행
/export.csv                CSV 내보내기 (캐시 재활용)
/api/drafts                자소서 초안 저장/조회
/api/resume/versions       이력서 버전 저장/조회
/api/draft/questions       공고 분석 → AI 자소서 문항 생성
/api/match                 AI 매칭 (공고 본문 스크래핑 포함)
index()                    메인 뷰 — q, also, sites, size 파라미터
```

### job_hunt.py 주요 함수
```
search_saramin(keyword)     → list[job]
search_jobkorea(keyword)    → list[job]
search_groupby(keyword)     → list[job]   ← api.groupby.kr REST API
search_jasoseol(keyword)    → list[job]   ← Playwright
search_wanted(keyword)      → list[job]   ← years=0 신입 IDs 선수집 후 career 태깅
_normalize_career(txt)      → "신입"|"경력"|"무관"|""
_parse_dday(str)            → int|None
dedup(jobs) / mark_new(jobs) / save_seen(jobs) / load_seen()
```

---

## URL 파라미터 구조

```
/?q=백엔드&size=all&sites=사람인,원티드,그룹바이&also=서버개발자,백엔드개발자
```

| 파라미터 | 설명 |
|---|---|
| `q` | 주 검색 키워드 |
| `size` | 기업규모 (all/big/corp/startup) — 표시 필터만, 크롤링 제어 아님 |
| `sites` | 크롤링할 사이트 쉼표 구분 (없으면 전체) |
| `also` | 병합할 유사어 키워드 쉼표 구분 |

---

## job 객체 스키마

```python
{
    "site": "사람인" | "잡코리아" | "그룹바이" | "자소설닷컴" | "원티드",
    "size": "대기업·중소" | "중견·중소" | "스타트업" | "대기업",
    "company": str,
    "title": str,
    "link": str,
    "deadline": str,      # "2026.06.30" 형식 또는 ""
    "dday": int | None,
    "location": str,
    "career": str,        # "신입" | "경력" | "무관" | ""
    "is_new": bool,
    # 그룹바이·원티드 전용:
    "stacks": str,        # "Python, FastAPI, AWS"
    # 그룹바이 전용:
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
| Supabase REST API (requests) | psycopg2 direct/pooler 연결 불가 (Render IPv6 미지원) |
| deepseek-v4-flash | deepseek-chat 2026-07-24 은퇴 예정. V4 Flash가 현재 최신 |
| Playwright (자소설닷컴만) | 나머지는 requests/REST API로 충분. Render 무료 512MB 제약 |
| api.groupby.kr REST API | groupby.kr HTML __NEXT_DATA__는 고정 10건만 반환 |
| wanted.co.kr/api/v4/jobs?query= | `keywords` 파라미터는 API가 무시함. `query`가 실제 검색 파라미터 |
| 원티드 career 2-call 방식 | 리스트 API에 career 필드 없음. years=0 별도 호출로 신입 ID 수집 후 비교 |
| 사이트 체크박스 | 기업규모는 표시 필터만, 크롤링 제어는 체크박스 |
| 유사어 사전 테이블 (~111 클러스터) | DeepSeek 온디맨드 확장은 자동 오염 위험. 사전 테이블 + 사용자 선택 병합 |
| 키워드별 독립 캐시 | 유사어 추가 시 원본 키워드 캐시 재사용 |
| bookmarks.drafts JSONB | 자소서 초안 저장 — 새 테이블 없이 기존 bookmarks에 컬럼 추가 |
| resumes.versions JSONB 배열 | 이력서 버전 관리 — 최대 10개, Python 측에서 슬라이싱 |
| AI 매칭 공고 본문 스크래핑 | 스택 없는 사이트(사람인·잡코리아) 대상 병렬 스크래핑, 200자 스니펫 |
| 자소서 문항 AI 생성 | 사이트들이 공고 페이지에 자소서 문항 미노출 → 공고 내용 분석 후 DeepSeek 생성 |

---

## 미완성 / 다음 작업 후보

> 우선순위: ⭐⭐⭐ 핵심 · ⭐⭐ 고가치 · ⭐ 있으면 좋음

---

### 🔴 A. 지원 관리

| 항목 | 설명 | 우선순위 |
|---|---|---|
| ~~지원 현황 트래커~~ | ✅ 완료 | — |
| ~~지원 메모~~ | ✅ 완료 | — |
| **지원 달력/타임라인** | 마감일·면접일 기반 캘린더 뷰. FullCalendar.js 또는 직접 구현. | ⭐⭐ |

**DB 신규 테이블 (지원 트래커용)**
```sql
CREATE TABLE IF NOT EXISTS applications (
  id         SERIAL PRIMARY KEY,
  user_id    INT REFERENCES users(id) ON DELETE CASCADE,
  company    TEXT,
  title      TEXT,
  link       TEXT,
  site       TEXT,
  status     TEXT DEFAULT 'saved',  -- saved/applied/docs_pass/interview/offer/rejected
  applied_at DATE,
  interview_at TIMESTAMPTZ,
  notes      TEXT DEFAULT '',
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);
```

---

### 🟠 B. AI 기능 고도화

| 항목 | 설명 | 우선순위 |
|---|---|---|
| **자소서 첨삭** | 작성된 자소서를 AI가 문단별 피드백 (논리성·구체성·직무적합도). 드로어 내 "✏️ 첨삭" 버튼. | ⭐⭐⭐ |
| **면접 예상 질문 생성** | 공고·이력서 기반 예상 면접 질문 5~10개 + 답변 가이드. `/api/interview-questions` 엔드포인트. | ⭐⭐⭐ |
| **회사 리서치 요약** | 회사명으로 최근 뉴스·사업 방향·문화 AI 요약. DeepSeek web search 또는 _fetch_company_info 확장. | ⭐⭐ |
| **연봉 분석** | 직군·경력별 평균 연봉 DeepSeek 추론 (실시간 데이터 없으므로 LLM 추론 기반). | ⭐ |
| **키워드 트렌드** | 검색 결과 기반 자주 등장 스킬스택 집계 및 차트 표시. 순수 Python 집계. | ⭐⭐ |

---

### 🟡 C. 이력서·자소서 고도화

| 항목 | 설명 | 우선순위 |
|---|---|---|
| **이력서 PDF 출력** | 구조화된 이력서 데이터로 깔끔한 PDF 생성. `weasyprint` 또는 `reportlab` 사용. `/resume/export.pdf` 엔드포인트. | ⭐⭐⭐ |
| **자소서 문항 라이브러리** | 자주 쓰이는 자소서 문항 50~100개 내장 DB. 업종·직군별 필터. 원클릭으로 드로어에 추가. | ⭐⭐ |
| **자소서 히스토리** | 공고별 초안 버전 관리 (현재 1개만 저장). `bookmarks.drafts` 구조를 `{jobId: [{saved_at, text}]}` 로 변경. | ⭐⭐ |
| **맞춤법 검사 연동** | 부산대 맞춤법 검사기 API (`speller.cs.pusan.ac.kr`) 무료 사용. 자소서 드로어 내 "맞춤법 검사" 버튼. | ⭐⭐ |

---

### 🟢 D. UX / 접근성

| 항목 | 설명 | 우선순위 |
|---|---|---|
| **모바일 최적화** | 현재 데스크탑 위주. 반응형 CSS 추가. 테이블 → 카드 레이아웃 전환 (max-width: 768px). | ⭐⭐⭐ |
| **공고 상세 모달** | 공고 제목 클릭 시 페이지 이탈 없이 모달로 공고 내용 표시. `_fetch_company_info` 재활용. | ⭐⭐ |
| **고정 검색어 핀** | 자주 쓰는 키워드를 상단에 핀으로 고정. localStorage 저장. | ⭐ |
| **다중 탭 저장** | 여러 검색 결과를 탭으로 유지. 현재는 검색할 때마다 덮어씀. | ⭐ |

---

### 🔵 E. 크롤러 추가

| 항목 | 설명 | 우선순위 |
|---|---|---|
| **캐치(catch.co.kr)** | `/api/v1.0/recruit/` 경로 확인됨. requests 403 → Playwright 또는 인증 헤더 필요. 추가 조사 필요. | ⭐⭐ |
| **잡플래닛(jobplanet.co.kr)** | 구직자 리뷰 사이트이나 채용공고도 있음. API 미확인. | ⭐ |
| **회사 정보 (DART API)** | `opendart.fss.or.kr` 무료 API. DART_API_KEY 환경변수 필요. 상장사 재무·직원 수 표시. | ⭐⭐ |

---

### ⚪ F. 인프라 / 운영

| 항목 | 설명 | 우선순위 |
|---|---|---|
| **마감 임박 이메일 알림** | 북마크 공고 D-3 이내 이메일 발송. SendGrid 또는 Gmail SMTP. `EMAIL_*` 환경변수 필요. | ⭐⭐ |
| **캐시 공유** | 현재 인메모리 캐시는 서버 재시작 시 초기화. Redis 또는 파일 캐시로 영속화. | ⭐ |
| **검색 로그** | 어떤 키워드가 자주 검색되는지 어드민에서 확인. `search_logs` 테이블. | ⭐ |

---

### 크롤러 상태 요약 (조사 완료)
- [x] 사람인, 잡코리아, 그룹바이, 자소설닷컴, 원티드 — 구현 완료
- [ ] **캐치** — robots.txt에 `/api/v1.0/recruit/` 경로 존재. requests 403. Playwright 필요.
- [ ] **링커리어** — 대외활동 플랫폼. 구현 보류.

---

### 기능 완료 이력
- [x] **원티드 stacks 필드** — 병렬 fetch, 상위 20개 (job_hunt.py)
- [x] **CSV 북마크 내보내기** — `/export.csv?bm=1` (app.py)
- [x] **이력서 버전 diff** — LCS 기반 라인 diff (app.js)
- [x] **회원가입 승인제** — is_approved, 어드민 승인/거절 (db.py, app.py, admin.html)
- [x] **다크모드** — CSS 변수 + prefers-color-scheme (style.css, auth.css, admin.css)
- [x] **지원 현황 트래커** — 공고별 상태 추적(관심/지원예정/지원완료/서류통과/면접/합격/불합격), applications 테이블, 대시보드 탭 (app.py, db.py, app.js, style.css)
- [x] **지원 메모** — 앱 패널 각 공고에 메모 textarea, 800ms debounce 자동저장 (db.py, app.py, app.js, style.css)
- [x] **자소서 문항 라이브러리** — 65개 내장 문항 JS 임베드, 드로어 내 📚 버튼, LLM 호출 없이 사용 가능 (app.js, style.css, index.html)
- [x] **키워드 트렌드** — 검색 결과 stacks 집계 → 상위 12개 칩 표시 (app.js, style.css, index.html)
- [x] **모바일 최적화** — 640px 이하 반응형 CSS (style.css, index.html hide-mob)

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
