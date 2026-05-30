# JOB HUNTER — LLM 인계 컨텍스트

> 이 문서는 다른 LLM 세션에서 본 프로젝트를 이어받아 작업할 때 사용하는 컨텍스트입니다.
> 아래 내용을 프롬프트 앞에 붙여서 사용하세요.

---

## 프로젝트 한 줄 정의

한국 취업 공고(사람인·잡코리아·그룹바이·자소설닷컴) 자동 수집 + 필터링 웹앱.
개인 + 소수 지인 사용 목적. Flask + Playwright. Render(무료) 배포 완료.

---

## 현재 상태 (완료된 것)

- [x] 사람인 크롤러 (requests + BeautifulSoup)
- [x] 잡코리아 크롤러 (requests + BeautifulSoup)
- [x] 그룹바이 크롤러 (requests + __NEXT_DATA__ JSON)
- [x] 자소설닷컴 크롤러 (Playwright 헤드리스 Chromium)
- [x] 병렬 크롤링 (ThreadPoolExecutor)
- [x] 10분 서버 캐시
- [x] 중복 제거
- [x] 기업 규모 필터 (전체/대기업/중견중소/스타트업)
- [x] D-day 배지 (마감일 파싱)
- [x] 지역 필터
- [x] 마감 임박순 / NEW 우선 정렬
- [x] 북마크 (localStorage)
- [x] 키워드 히스토리 (localStorage)
- [x] NEW 배지 (seen.json 기반)
- [x] 이력서 저장 패널 UI (localStorage, 백엔드 미연결)
- [x] Render 무료 배포
- [x] GitHub Actions keepalive (14분마다 핑, 콜드스타트 방지)

---

## 파일 구조

```
job_hunt.py        크롤러 코어
  - search_saramin(keyword)     → list[job]
  - search_jobkorea(keyword)    → list[job]
  - search_groupby(keyword)     → list[job]
  - search_jasoseol(keyword)    → list[job] (Playwright)
  - dedup(jobs)                 → 중복 제거
  - mark_new(jobs)              → is_new 필드 추가
  - save_seen(jobs) / load_seen()

app.py             Flask 웹서버 + Jinja2 HTML
  - CACHE dict (10분 TTL)
  - _run(q, size)               → 병렬 크롤링
  - GET /                       → 검색 결과 페이지

Dockerfile         Render 배포용
requirements.txt   flask, requests, beautifulsoup4, playwright

.github/workflows/keepalive.yml   14분마다 Render 핑

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
    "dday": int | None,   # 오늘 기준 남은 일수
    "location": str,      # "서울 강남구" 등
    "is_new": bool,       # seen.json 기준 신규 여부
    # 그룹바이 전용 추가 필드:
    "stacks": str,        # "Python, FastAPI, AWS"
    "career": str,        # "경력" | "신입" | "무관"
    "funding": str,       # "Pre-A" | "A" | "B" 등
    "members": int,       # 인원수
}
```

---

## 배포 정보

| 항목 | 값 |
|---|---|
| 라이브 URL | https://job-hunter-v28m.onrender.com |
| GitHub repo | https://github.com/na0707669-cmyk/job-hunter |
| 플랫폼 | Render (무료, Docker) |
| keepalive | GitHub Actions, 14분 주기 |
| 자동배포 | main 브랜치 push 시 Render 자동 재배포 |

---

## 미완성 / 다음 작업 목록

### 우선순위 높음
- [ ] **DeepSeek API 이력서 매칭**
  - 환경변수: `DEEPSEEK_API_KEY` (Render Environment에 추가 필요)
  - 구현 위치: `app.py`에 `POST /match` 엔드포인트 추가
  - 입력: 이력서 텍스트(localStorage `jh_r`) + 공고 목록
  - 출력: 각 공고별 매칭율 0~100 + 한줄 이유
  - 모델: `deepseek-chat` (OpenAI 호환 API, base_url=`https://api.deepseek.com`)
  - UI: 이미 이력서 저장 패널 있음 (`#rv` textarea), 매칭율 컬럼만 추가하면 됨

- [ ] **방문자 카운터**
  - 간단하게: 서버 메모리에 카운터 + `/stats` 엔드포인트
  - 또는: Render 로그에서 IP 확인 (현재도 가능)

### 우선순위 중간
- [ ] **사전 크롤링 구조 전환** (속도 근본 해결)
  - GitHub Actions로 4시간마다 크롤링 → JSON 저장
  - Flask는 저장된 JSON 서빙만 → 검색 즉시
  - Vercel로 이전하면 더 빠름

- [ ] **우대사항/스펙 크롤링**
  - 공고 개별 페이지 진입 필요 (느림 주의)
  - 그룹바이는 이미 `techStacks` 있음
  - 사람인/잡코리아는 개별 URL 진입 후 파싱

### 우선순위 낮음
- [ ] 지역 필터 고도화 (시/구 단위)
- [ ] 경력 필터 (신입/경력 구분)
- [ ] 검색 결과 CSV 내보내기

---

## 기술 결정 기록

| 결정 | 이유 |
|---|---|
| Playwright (자소설닷컴만) | 나머지 3개는 requests로 충분, Playwright는 느려서 최소화 |
| requests 우선 | 빠르고 서버 부하 낮음 |
| ThreadPoolExecutor | 4개 사이트 병렬 크롤링, 전체 시간 = 가장 느린 사이트 기준 |
| 인메모리 캐시 | DB 없이 간단하게, 10분 TTL |
| localStorage | 북마크/키워드/이력서 — 서버 DB 불필요, 개인 도구라 적합 |
| Render 무료 | $0, Docker 지원, GitHub 자동배포 |
| keepalive via GitHub Actions | 무료, 외부 서비스 의존 없음, 끄기 쉬움 |
| DeepSeek (미구현) | GPT보다 저렴, OpenAI 호환 API |

---

## 로컬 실행

```bash
cd C:\Users\ZOB\Documents\JOB_HUNTER
pip install -r requirements.txt
playwright install chromium
python app.py
# → http://localhost:5000
```

---

## 작업 인계 프롬프트 예시

```
위 CONTEXT.md를 참조해서 작업을 이어받는다.
현재 작업 디렉토리: C:\Users\ZOB\Documents\JOB_HUNTER
GitHub: https://github.com/na0707669-cmyk/job-hunter
라이브: https://job-hunter-v28m.onrender.com

[여기에 요청사항 입력]
```
