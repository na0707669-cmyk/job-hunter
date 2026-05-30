# 공고 사냥 (Job Hunter)

취업 공고 자동 수집 + 필터링 웹앱.

---

## 라이브 URL

**https://job-hunter-v28m.onrender.com**

---

## 구조 요약

```
사용자 브라우저
    │
    ▼
Render (Flask 서버) ──── GitHub Actions (14분마다 핑)
    │
    ├── requests (사람인, 잡코리아, 그룹바이)
    └── Playwright Chromium (자소설닷컴)
```

---

## 파일 구조

```
job_hunt.py       크롤러 코어 (4개 사이트 스크래퍼)
app.py            Flask 웹서버 + HTML UI
Dockerfile        Render 배포용 (Python + Playwright Chromium)
requirements.txt  pip 의존성
seen.json         이전 검색 결과 저장 (NEW 배지용, gitignore)
.github/
  workflows/
    keepalive.yml  GitHub Actions — 14분마다 Render 핑
```

---

## 크롤링 방식

| 사이트 | 방식 | 이유 |
|---|---|---|
| 사람인 | requests + BeautifulSoup | HTML 서버사이드 렌더링 |
| 잡코리아 | requests + BeautifulSoup | HTML 서버사이드 렌더링 |
| 그룹바이 | requests + `__NEXT_DATA__` JSON 파싱 | Next.js 정적 props 활용 |
| 자소설닷컴 | Playwright (헤드리스 Chromium) | React SPA, JS 렌더링 필요 |

---

## 기능

- 키워드 검색
- 기업 규모 필터: 전체 / 대기업(자소설닷컴) / 중견·중소(사람인+잡코리아) / 스타트업(그룹바이)
- 중복 제거 (회사명+공고명 기준)
- D-day 배지 (D-3 이내 빨강 / D-7 이내 주황 / 이후 초록)
- 지역 필터
- 마감 임박순 / NEW 우선 정렬
- 북마크 (브라우저 localStorage)
- 키워드 히스토리 (브라우저 localStorage)
- NEW 배지 (이전 검색 대비 신규 공고)
- 10분 서버 캐시 (같은 키워드 재검색 즉시 반환)
- 이력서 텍스트 저장 패널 (DeepSeek API 연동 준비 중)

---

## 배포 구조

### Render (웹서버)
- 플랜: **Free** ($0/월)
- 런타임: **Docker**
- GitHub repo `main` 브랜치에 push하면 **자동 재배포**
- 무료 플랜 제약: 15분 비활성 시 슬립 → GitHub Actions keepalive로 해결

### GitHub Actions (keepalive)
- 파일: `.github/workflows/keepalive.yml`
- 동작: **14분마다** Render URL에 GET 요청 1회
- 목적: Render 무료 플랜 슬립 방지 → 콜드스타트 제거
- 비용: 무료 (GitHub Actions 월 2000분 무료)

---

## 끄는 법

### 서비스 전체 중단
1. Render 대시보드 → `job-hunter` → Settings → **Suspend Service**

### keepalive만 중단 (서버는 유지, 슬립 허용)
1. GitHub → Actions → `Keep Render Alive` → 우상단 `...` → **Disable workflow**

### keepalive 재개
1. GitHub → Actions → `Keep Render Alive` → **Enable workflow**

### 완전 삭제
1. Render → Settings → Delete Service
2. GitHub → Settings → Delete Repository

---

## 로컬 실행

```bash
# 의존성 설치
pip install -r requirements.txt
playwright install chromium

# 서버 실행
python app.py
# → http://localhost:5000
```

---

## 환경변수

| 변수 | 설명 | 기본값 |
|---|---|---|
| `PORT` | 서버 포트 | 5000 |
| `DEEPSEEK_API_KEY` | DeepSeek 매칭 기능용 (미구현) | 없음 |

Render 환경변수 설정: Render 대시보드 → `job-hunter` → Environment

---

## 향후 계획

- [ ] DeepSeek API 이력서 매칭율 계산
- [ ] 방문자 카운터
- [ ] GitHub Actions 사전 크롤링으로 구조 전환 (속도 개선)
- [ ] 우대사항/스펙 크롤링 (개별 공고 페이지 진입)
