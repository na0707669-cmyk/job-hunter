import sys
import json
import re
from datetime import datetime
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


def _parse_dday(deadline_str):
    if not deadline_str:
        return None
    for fmt in ("%Y.%m.%d", "%Y/%m/%d"):
        try:
            dt = datetime.strptime(deadline_str[:10], fmt)
            return (dt - datetime.now()).days
        except Exception:
            pass
    return None


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
        jobs.append({
            "site": "사람인",
            "size": "대기업·중소",
            "company": company_el.get_text(strip=True),
            "title": title_el.get_text(strip=True),
            "link": "https://www.saramin.co.kr" + title_el.get("href", ""),
            "deadline": deadline,
            "dday": _parse_dday(deadline),
            "location": location,
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
        jobs.append({
            "site": "잡코리아",
            "size": "중견·중소",
            "company": a_tags[1].get_text(strip=True),
            "title": a_tags[0].get_text(strip=True),
            "link": a_tags[0].get("href", ""),
            "deadline": deadline,
            "dday": None,
            "location": location,
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
            jobs.append({
                "site": "자소설닷컴",
                "size": "대기업",
                "company": company,
                "title": title_el.inner_text().strip(),
                "link": "https://jasoseol.com" + href,
                "deadline": deadline,
                "dday": dday,
                "location": "서울",
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
            "deadline": "",
            "dday": None,
            "funding": startup.get("fundingRound", ""),
            "members": startup.get("memberCount", ""),
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
