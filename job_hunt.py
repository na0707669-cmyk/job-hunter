import sys
import json
import re
from datetime import datetime
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")



HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def _normalize_career(txt):
    if not txt:
        return ""
    if "무관" in txt or "관계없음" in txt or ("신입" in txt and "경력" in txt):
        return "무관"
    if "신입" in txt:
        return "신입"
    if "경력" in txt:
        return "경력"
    return ""


# ── 지역 정규화 ──────────────────────────────────────────────────
# 표시·필터에서 시/도 단위로 묶기 위한 정규화. 알 수 없는 값(회사명·건물명 등)은 "" 반환.
REGION_ORDER = [
    "서울", "경기", "인천", "부산", "대구", "대전", "광주", "울산", "세종",
    "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주", "해외",
]

_REGION_LONG = {
    "서울특별시": "서울", "서울시": "서울",
    "경기도": "경기",
    "인천광역시": "인천",
    "부산광역시": "부산",
    "대구광역시": "대구",
    "대전광역시": "대전",
    "광주광역시": "광주",
    "울산광역시": "울산",
    "세종특별자치시": "세종", "세종시": "세종",
    "강원특별자치도": "강원", "강원도": "강원",
    "충청북도": "충북", "충청남도": "충남",
    "전라북도": "전북", "전북특별자치도": "전북",
    "전라남도": "전남",
    "경상북도": "경북", "경상남도": "경남",
    "제주특별자치도": "제주", "제주도": "제주",
}


def _normalize_region(loc):
    """위치 문자열을 시/도 단위로 정규화. 인식 불가 시 '' 반환."""
    if not loc:
        return ""
    s = str(loc).strip()
    # 긴 정식 명칭 먼저 (충청북도 → 충북)
    for k, v in _REGION_LONG.items():
        if s.startswith(k):
            return v
    # 짧은 접두어 (서울강남구, 경기 성남시 등)
    for v in REGION_ORDER:
        if s.startswith(v):
            return v
    if "해외" in s or "외국" in s or "글로벌" in s:
        return "해외"
    return ""


def _title_relevant(title, keyword):
    """검색어 토큰 중 하나라도 제목에 있으면 관련 공고로 간주.
    잡코리아가 검색 결과에 끼워넣는 무관한 광고 공고를 걸러낸다."""
    if not keyword:
        return True
    t = (title or "").replace(" ", "")
    tokens = [tok for tok in re.split(r"\s+", keyword.strip()) if len(tok) >= 2]
    if not tokens:
        return True
    return any(tok.replace(" ", "") in t for tok in tokens)


def parse_min_years(text):
    """제목 등에서 요구 경력 최소 연차를 추출. 없으면 None.
    예: '경력 1~5년'→1, '3년 이상'→3, '경력 2년'→2, '5년차'→5"""
    if not text:
        return None
    # 1~5년 / 1∼5년 / 1-5년 → 최소값
    m = re.search(r"(\d+)\s*[~∼\-]\s*\d+\s*년", text)
    if m:
        return int(m.group(1))
    # 3년 ~ 10년 / 3년~10년 → 최소값
    m = re.search(r"(\d+)\s*년\s*[~∼\-]\s*\d+", text)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*년\s*이상", text)
    if m:
        return int(m.group(1))
    m = re.search(r"경력\s*(\d+)\s*년", text)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*년\s*차", text)
    if m:
        return int(m.group(1))
    return None


def _parse_dday(deadline_str):
    if not deadline_str:
        return None
    # "D-5", "D-0" 형식 직접 파싱
    m = re.match(r"D-(\d+)$", deadline_str.strip())
    if m:
        return int(m.group(1))
    # "즉시" = 당일 마감으로 처리
    if "즉시" in deadline_str:
        return 0
    for fmt in ("%Y.%m.%d", "%Y/%m/%d"):
        try:
            dt = datetime.strptime(deadline_str[:10], fmt)
            return (dt - datetime.now()).days
        except Exception:
            pass
    return None


def get(url, headers=None):
    h = {**HEADERS, **(headers or {})}
    return requests.get(url, headers=h, timeout=10)


def search_saramin(keyword):
    soup = BeautifulSoup(
        get(f"https://www.saramin.co.kr/zf_user/search?searchType=search&searchword={quote(keyword)}").text,
        "html.parser",
    )
    jobs = []
    for item in soup.select(".item_recruit"):
        title_el = item.select_one(".job_tit a")
        company_el = item.select_one(".corp_name a")
        if not (title_el and company_el):
            continue
        deadline = ""
        date_el = item.select_one(".job_date .date")
        if date_el:
            deadline = date_el.get_text(strip=True).replace("~", "").strip()
        location = ""
        loc_el = item.select_one(".job_condition span")
        if loc_el:
            location = loc_el.get_text(strip=True)
        career = ""
        for span in item.select(".job_condition span"):
            txt = span.get_text(strip=True)
            if re.search(r"신입|경력|무관|관계없음", txt) and len(txt) < 25:
                career = _normalize_career(txt)
                break
        jobs.append({
            "site": "사람인",
            "size": "대기업·중소",
            "company": company_el.get_text(strip=True),
            "title": title_el.get_text(strip=True),
            "link": "https://www.saramin.co.kr" + title_el.get("href", ""),
            "deadline": deadline,
            "dday": _parse_dday(deadline),
            "location": location,
            "career": career,
        })
    return jobs


def search_jobkorea(keyword):
    soup = BeautifulSoup(
        get(f"https://www.jobkorea.co.kr/Search/?stext={quote(keyword)}").text,
        "html.parser",
    )
    jobs = []
    cards = [d for d in soup.find_all("div") if "hover:bg-blue54" in " ".join(d.get("class", []))]
    for card in cards:
        a_tags = [a for a in card.select('a[href*="/Recruit/GI_Read/"]') if a.get_text(strip=True)]
        if len(a_tags) < 2:
            continue
        title = a_tags[0].get_text(strip=True)
        # 잡코리아는 검색어와 무관한 광고 공고를 결과에 끼워넣음 → 제목 관련성으로 필터
        if not _title_relevant(title, keyword):
            continue
        parts = [t.strip() for t in card.get_text(separator="|").split("|") if t.strip()]
        deadline = ""
        for p in parts:
            if re.match(r"D-\d+|즉시", p):
                deadline = p
                break
        location = ""
        for p in parts:
            if any(c in p for c in ["서울", "경기", "부산", "인천", "대구", "대전", "광주", "울산"]):
                location = p.split()[0]
                break
        career = ""
        for p in parts:
            if re.search(r"신입|경력|무관|관계없음", p) and len(p) < 20:
                career = _normalize_career(p)
                break
        jobs.append({
            "site": "잡코리아",
            "size": "중견·중소",
            "company": a_tags[1].get_text(strip=True),
            "title": title,
            "link": a_tags[0].get("href", ""),
            "deadline": deadline,
            "dday": _parse_dday(deadline),
            "location": location,
            "career": career,
        })
    return jobs


def search_jasoseol(keyword):
    jobs = []
    with sync_playwright() as _pw:
        browser = _pw.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(
                f"https://jasoseol.com/recruit?searchQuery={quote(keyword)}",
                wait_until="networkidle",
                timeout=20000,
            )
            groups = page.query_selector_all('[class*="employment-group-title"]')
            for group in groups:
                company_el = group.query_selector("span.company-name")
                company = company_el.inner_text().strip() if company_el else ""
                parent = group.query_selector("xpath=..")
                if not parent:
                    continue
                for a in parent.query_selector_all('a[href*="/recruit/"]'):
                    title_el = a.query_selector('[class*="employment-title"]')
                    period_el = a.query_selector('[class*="employment-period"]')
                    if not title_el:
                        continue
                    deadline = ""
                    dday = None
                    if period_el:
                        m = re.search(r"(\d{4}\.\d{2}\.\d{2})", period_el.inner_text())
                        if m:
                            deadline = m.group(1)
                            dday = _parse_dday(deadline)
                    href = a.get_attribute("href") or ""
                    career = ""
                    try:
                        career_el = a.query_selector('[class*="career"]') or a.query_selector('[class*="type"]')
                        if career_el:
                            career = _normalize_career(career_el.inner_text().strip())
                    except Exception:
                        pass
                    jobs.append({
                        "site": "자소설닷컴",
                        "size": "대기업",
                        "company": company,
                        "title": title_el.inner_text().strip(),
                        "link": "https://jasoseol.com" + href,
                        "deadline": deadline,
                        "dday": dday,
                        "location": "서울",
                        "career": career,
                    })
        finally:
            browser.close()
    return jobs


def search_groupby(keyword):
    resp = get(
        f"https://api.groupby.kr/startup-positions/search"
        f"?searchQuery={quote(keyword)}&limit=30&offset=0",
        headers={"Accept": "application/json"},
    )
    data = resp.json().get("data", {})
    positions = data.get("items", []) if isinstance(data, dict) else []
    jobs = []
    for p in positions:
        startup = p.get("startup", {})
        jobs.append({
            "site": "그룹바이",
            "size": "스타트업",
            "company": startup.get("name", ""),
            "title": p.get("name", ""),
            "link": f"https://groupby.kr/positions/{p['id']}",
            "stacks": ", ".join(p.get("techStacks", [])[:5]),
            "career": _normalize_career(p.get("careerType", "")),
            "location": (startup.get("location") or "").split()[0] if startup.get("location") else "",
            "deadline": "",
            "dday": None,
            "funding": startup.get("fundingRound", ""),
            "members": startup.get("memberCount", ""),
        })
    return jobs


def dedup(jobs):
    seen_links = set()
    seen_cross_site = set()
    result = []
    for j in jobs:
        link = j.get("link", "").strip()
        cross_key = (j["company"].strip().lower(), j["title"].strip().lower(), j.get("site", ""))
        # 같은 링크 = 완전 중복
        if link and link in seen_links:
            continue
        # 같은 사이트에서 동일 회사+직책 = 중복 (다른 사이트는 허용)
        if cross_key in seen_cross_site:
            continue
        if link:
            seen_links.add(link)
        seen_cross_site.add(cross_key)
        result.append(j)
    return result


def _fetch_wanted_stacks(job_id, headers):
    try:
        r = requests.get(
            f"https://www.wanted.co.kr/api/v4/jobs/{job_id}",
            headers=headers, timeout=6,
        )
        tags = r.json().get("job", {}).get("skill_tags", [])
        return ", ".join(t.get("title", "") for t in tags if t.get("title"))
    except Exception:
        return ""


def search_wanted(keyword):
    _headers = {"Referer": "https://www.wanted.co.kr", "Accept": "application/json", "x-wanted-language": "ko"}
    _base = (
        f"https://www.wanted.co.kr/api/v4/jobs"
        f"?country=kr&job_sort=job.latest_order&locations=all&limit=30&query={quote(keyword)}"
    )
    # 신입 허용 공고 ID 수집 (years=0)
    try:
        newbie_ids = {
            item["id"]
            for item in get(_base + "&years=0", headers=_headers).json().get("data", [])
        }
    except Exception:
        newbie_ids = set()
    # 전체 공고 (years=-1 = 무관)
    items = get(_base + "&years=-1", headers=_headers).json().get("data", [])
    jobs = []
    job_ids = []
    for item in items:
        due = item.get("due_time")
        deadline = due[:10].replace("-", ".") if due else ""
        jid = item["id"]
        career = "신입" if jid in newbie_ids else "경력"
        job_ids.append(jid)
        jobs.append({
            "site": "원티드",
            "size": "스타트업",
            "company": item.get("company", {}).get("name", ""),
            "title": item.get("position", ""),
            "link": f"https://www.wanted.co.kr/wd/{jid}",
            "deadline": deadline,
            "dday": _parse_dday(deadline),
            "location": item.get("address", {}).get("location", ""),
            "career": career,
            "stacks": "",
        })
    # 상위 20개 공고 stacks 병렬 fetch
    MAX_STACKS = 20
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(_fetch_wanted_stacks, job_ids[i], _headers): i
                   for i in range(min(len(jobs), MAX_STACKS))}
        for fut, idx in futures.items():
            stacks = fut.result()
            if stacks:
                jobs[idx]["stacks"] = stacks
    return jobs


def load_seen():
    try:
        with open("seen.json", "r", encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()


def save_seen(jobs):
    ids = [f"{j['company']}|{j['title']}" for j in jobs]
    with open("seen.json", "w", encoding="utf-8") as f:
        json.dump(ids, f, ensure_ascii=False)


def mark_new(jobs):
    seen = load_seen()
    for j in jobs:
        j["is_new"] = f"{j['company']}|{j['title']}" not in seen
    return jobs
