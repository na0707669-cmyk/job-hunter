import sys
import json
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")

_pw_browser = None

def _get_browser():
    global _pw_browser
    if _pw_browser is None:
        _pw = sync_playwright().start()
        _pw_browser = _pw.chromium.launch(headless=True)
    return _pw_browser


def _pw_page(url, wait="networkidle", timeout=20000):
    page = _get_browser().new_page()
    page.goto(url, wait_until=wait, timeout=timeout)
    return page

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

SIZE_SITES = {
    "1": ["자소설닷컴", "사람인", "잡코리아", "그룹바이"],  # 전체
    "2": ["자소설닷컴"],                                    # 대기업
    "3": ["사람인", "잡코리아"],                            # 중견·중소
    "4": ["그룹바이"],                                      # 스타트업
}


def get(url):
    return requests.get(url, headers=HEADERS, timeout=10)


def search_saramin(keyword):
    soup = BeautifulSoup(
        get(f"https://www.saramin.co.kr/zf_user/search?searchType=search&searchword={quote(keyword)}").text,
        "html.parser",
    )
    jobs = []
    for item in soup.select(".item_recruit"):
        title_el = item.select_one(".job_tit a")
        company_el = item.select_one(".corp_name a")
        if title_el and company_el:
            jobs.append({
                "site": "사람인",
                "size": "대기업·중소",
                "company": company_el.get_text(strip=True),
                "title": title_el.get_text(strip=True),
                "link": "https://www.saramin.co.kr" + title_el.get("href", ""),
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
        if len(a_tags) >= 2:
            jobs.append({
                "site": "잡코리아",
                "size": "중견·중소",
                "company": a_tags[1].get_text(strip=True),
                "title": a_tags[0].get_text(strip=True),
                "link": a_tags[0].get("href", ""),
            })
    return jobs


def search_jasoseol(keyword):
    page = _pw_page(f"https://jasoseol.com/recruit?searchQuery={quote(keyword)}")
    groups = page.query_selector_all('[class*="employment-group-title"]')
    jobs = []
    for group in groups:
        company_el = group.query_selector("span.company-name")
        company = company_el.inner_text().strip() if company_el else ""
        parent = group.query_selector("xpath=..")
        if not parent:
            continue
        for a in parent.query_selector_all('a[href*="/recruit/"]'):
            title_el = a.query_selector('[class*="employment-title"]')
            if not title_el:
                continue
            href = a.get_attribute("href") or ""
            jobs.append({
                "site": "자소설닷컴",
                "size": "대기업",
                "company": company,
                "title": title_el.inner_text().strip(),
                "link": "https://jasoseol.com" + href,
            })
    page.close()
    return jobs


def search_groupby(keyword):
    keyword_map = {
        "백엔드": "engineering", "프론트": "engineering",
        "풀스택": "engineering", "개발": "engineering",
        "AI": "ai", "인공지능": "ai",
        "마케팅": "marketing", "디자인": "design",
        "iOS": "ios", "안드로이드": "android",
    }
    path = "engineering"
    for k, v in keyword_map.items():
        if k in keyword:
            path = v
            break

    soup = BeautifulSoup(get(f"https://groupby.kr/jobs/{path}").text, "html.parser")
    nd = soup.find("script", id="__NEXT_DATA__")
    if not nd:
        return []

    positions = json.loads(nd.string).get("props", {}).get("pageProps", {}).get("positions", [])
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
            "career": p.get("careerType", ""),
            "location": startup.get("location", ""),
        })
    return jobs


def dedup(jobs):
    seen = set()
    result = []
    for j in jobs:
        key = (j["company"].strip().lower(), j["title"].strip().lower())
        if key not in seen:
            seen.add(key)
            result.append(j)
    return result


def print_jobs(jobs):
    for i, j in enumerate(jobs, 1):
        career = f" [{j.get('career')}]" if j.get("career") else ""
        location = f" {j.get('location')}" if j.get("location") else ""
        stacks = f"\n     스택: {j['stacks']}" if j.get("stacks") else ""
        print(f"{i:>3}. [{j['site']}·{j['size']}] {j['company']}{career}{location}")
        print(f"     {j['title']}{stacks}")
        print(f"     {j['link']}")


if __name__ == "__main__":
    keyword = input("검색 키워드: ").strip()
    print("기업 규모 선택:")
    print("  1. 전체")
    print("  2. 대기업 (자소설닷컴)")
    print("  3. 중견·중소 (사람인 + 잡코리아)")
    print("  4. 스타트업 (그룹바이)")
    size_choice = input("선택 (기본 1): ").strip() or "1"
    target_sites = SIZE_SITES.get(size_choice, SIZE_SITES["1"])

    scrapers = {
        "자소설닷컴": search_jasoseol,
        "사람인": search_saramin,
        "잡코리아": search_jobkorea,
        "그룹바이": search_groupby,
    }

    raw = []
    for name, fn in scrapers.items():
        if name not in target_sites:
            continue
        try:
            jobs = fn(keyword)
            raw += jobs
            print(f"  [{name}] {len(jobs)}개 수집")
        except Exception as e:
            print(f"  [{name}] 실패: {e}")

    results = dedup(raw)
    removed = len(raw) - len(results)

    print(f"\n중복 제거: {removed}개 제거 → 최종 {len(results)}개\n")
    print_jobs(results)

    with open("results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n→ results.json 저장 완료")
