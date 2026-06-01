import os
import re
import time
import json
import secrets
import functools
import requests as _req
from bs4 import BeautifulSoup as _BS
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import io
from flask import Flask, request, render_template, redirect, url_for, session, jsonify, Response
from job_hunt import (
    search_saramin, search_jobkorea, search_groupby, search_jasoseol,
    search_wanted,
    dedup, mark_new, save_seen,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")


def _csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return session["csrf_token"]


def _csrf_validate():
    token = request.form.get("csrf_token", "")
    return secrets.compare_digest(token, session.get("csrf_token", ""))


app.jinja_env.globals["csrf_token"] = _csrf_token

_db_enabled = bool(os.environ.get("SUPABASE_URL"))
if _db_enabled:
    import db
    try:
        db.init_db()
    except Exception as e:
        print(f"[WARN] DB init failed: {e} — running without DB")

CACHE = {}
CACHE_TTL = 600

SCRAPERS = {
    "사람인":     search_saramin,
    "잡코리아":   search_jobkorea,
    "그룹바이":   search_groupby,
    "원티드":     search_wanted,
    "자소설닷컴": search_jasoseol,
}
ALL_SITES = list(SCRAPERS.keys())

# ── 유사어 클러스터 ──────────────────────────────────────────────
_SYNONYM_GROUPS = [
    # ── 기획/PM ──────────────────────────────────────────────────────
    {"MD", "머천다이저", "상품기획자", "상품기획", "바이어"},
    {"PM", "PO", "프로덕트매니저", "프로덕트오너", "서비스기획자"},
    {"사업기획", "전략기획", "경영기획", "비즈니스기획"},
    {"IT기획", "시스템기획", "디지털기획"},
    {"스타트업기획", "신사업기획", "사업개발"},

    # ── 개발 — 백엔드 ────────────────────────────────────────────────
    {"백엔드", "백엔드개발자", "서버개발자", "서버"},
    {"Java개발자", "스프링개발자", "Spring개발자"},
    {"Python개발자", "파이썬개발자", "Django개발자", "FastAPI개발자"},
    {"Node.js개발자", "NodeJS개발자", "Express개발자"},
    {"Go개발자", "Golang개발자"},
    {"Kotlin개발자", "코틀린개발자"},
    {"PHP개발자", "Laravel개발자"},

    # ── 개발 — 프론트엔드 ────────────────────────────────────────────
    {"프론트엔드", "프론트엔드개발자", "프론트", "웹프론트엔드"},
    {"React개발자", "리액트개발자"},
    {"Vue개발자", "뷰개발자", "Vue.js개발자"},
    {"TypeScript개발자", "타입스크립트개발자"},

    # ── 개발 — 풀스택 ────────────────────────────────────────────────
    {"풀스택", "풀스택개발자", "웹개발자"},

    # ── 개발 — 모바일 ────────────────────────────────────────────────
    {"iOS", "iOS개발자", "아이폰개발자", "Swift"},
    {"안드로이드", "안드로이드개발자", "Android"},
    {"모바일개발자", "앱개발자", "크로스플랫폼개발자"},
    {"Flutter개발자", "플러터개발자", "ReactNative개발자"},

    # ── 개발 — 인프라/클라우드 ──────────────────────────────────────
    {"DevOps", "데브옵스", "SRE", "인프라엔지니어", "클라우드엔지니어"},
    {"AWS엔지니어", "클라우드아키텍트", "솔루션아키텍트"},
    {"플랫폼엔지니어", "Platform엔지니어", "쿠버네티스엔지니어"},
    {"네트워크엔지니어", "네트워크관리자", "시스템엔지니어"},
    {"임베디드개발자", "펌웨어개발자", "임베디드SW"},

    # ── 개발 — 보안 ──────────────────────────────────────────────────
    {"정보보안", "보안엔지니어", "보안담당자", "사이버보안"},
    {"모의해킹", "침투테스트", "레드팀"},
    {"보안관제", "SOC", "CERT"},

    # ── 개발 — QA/테스트 ─────────────────────────────────────────────
    {"QA", "QA엔지니어", "품질보증", "테스터", "QE"},
    {"자동화테스트", "테스트자동화", "SDET"},

    # ── 개발 — 퍼블리셔 ──────────────────────────────────────────────
    {"퍼블리셔", "웹퍼블리셔", "마크업개발자", "UI개발자"},

    # ── 개발 — 블록체인/Web3 ─────────────────────────────────────────
    {"블록체인개발자", "Web3개발자", "Solidity개발자", "스마트컨트랙트"},

    # ── 개발 — ERP/SI ────────────────────────────────────────────────
    {"ERP개발자", "SAP개발자", "SI개발자"},

    # ── 개발 — 게임 ──────────────────────────────────────────────────
    {"게임개발자", "게임클라이언트", "게임서버개발자"},
    {"유니티개발자", "언리얼개발자", "게임엔진개발자"},
    {"게임기획자", "게임디자이너", "레벨디자이너"},

    # ── 데이터/AI ────────────────────────────────────────────────────
    {"데이터분석가", "DA", "데이터애널리스트", "분석가"},
    {"데이터엔지니어", "DE", "데이터파이프라인"},
    {"데이터사이언티스트", "DS", "머신러닝엔지니어", "ML엔지니어"},
    {"AI엔지니어", "AI개발자", "딥러닝엔지니어", "LLM엔지니어"},
    {"MLOps엔지니어", "MLOps", "AI인프라"},
    {"컴퓨터비전엔지니어", "CV엔지니어", "영상인식"},
    {"NLP엔지니어", "자연어처리", "언어모델"},
    {"BI엔지니어", "비즈니스인텔리전스", "데이터시각화"},
    {"리서처", "AI리서처", "연구원"},

    # ── 디자인 ───────────────────────────────────────────────────────
    {"UX디자이너", "UI디자이너", "UXUI디자이너", "프로덕트디자이너"},
    {"브랜드디자이너", "BX디자이너", "브랜딩디자이너"},
    {"그래픽디자이너", "그래픽디자인"},
    {"영상편집자", "영상편집", "영상디자이너"},
    {"모션그래픽", "모션디자이너"},
    {"3D디자이너", "3D모델러", "3D아티스트"},
    {"일러스트레이터", "일러스트작가"},
    {"포토그래퍼", "사진작가"},
    {"패션디자이너", "의류디자이너"},
    {"인테리어디자이너", "공간디자이너"},

    # ── 마케팅 ───────────────────────────────────────────────────────
    {"퍼포먼스마케터", "퍼포먼스마케팅", "그로스마케터", "디지털마케터"},
    {"콘텐츠마케터", "콘텐츠마케팅", "SNS마케터"},
    {"브랜드마케터", "브랜드마케팅"},
    {"CRM마케터", "CRM마케팅", "이메일마케팅"},
    {"마케터", "마케팅담당자"},
    {"SEO담당자", "SEO마케터", "검색엔진최적화"},
    {"그로스해킹", "그로스", "Growth"},
    {"오프라인마케터", "ATL마케터", "BTL마케터"},
    {"커머스마케터", "이커머스마케터"},

    # ── HR ───────────────────────────────────────────────────────────
    {"HR", "인사담당자", "HRM", "HRD", "인사관리"},
    {"채용담당자", "채용", "리크루터", "Recruiter"},
    {"HRBP", "HR비즈니스파트너"},
    {"조직문화", "피플팀", "사내문화"},
    {"교육담당자", "HRD담당자", "러닝앤디벨롭먼트"},

    # ── 영업 ─────────────────────────────────────────────────────────
    {"영업", "세일즈", "영업담당자"},
    {"B2B영업", "기업영업", "법인영업"},
    {"기술영업", "솔루션영업", "세일즈엔지니어"},
    {"해외영업", "글로벌영업", "수출입영업"},
    {"영업관리", "영업지원", "세일즈옵스"},
    {"대리점관리", "채널영업", "파트너영업"},

    # ── CS/고객 ──────────────────────────────────────────────────────
    {"CS", "고객서비스", "고객지원", "CX", "고객경험"},
    {"어카운트매니저", "AM", "고객성공", "CSM"},

    # ── 재무/회계/IR ─────────────────────────────────────────────────
    {"재무", "재무관리", "재무담당자", "재무기획"},
    {"회계", "회계담당자", "경리", "세무"},
    {"IR", "투자유치", "투자관계"},
    {"FP&A", "재무계획", "경영분석"},
    {"세무사", "세금신고", "세무담당"},
    {"회계사", "공인회계사", "CPA"},

    # ── 법무/컴플라이언스 ────────────────────────────────────────────
    {"법무", "법무담당자", "계약관리", "컴플라이언스"},
    {"변호사", "기업법무", "사내변호사"},

    # ── 물류/SCM/구매 ────────────────────────────────────────────────
    {"물류", "SCM", "공급망관리", "물류기획"},
    {"구매", "구매담당자", "소싱"},
    {"무역", "무역담당자", "수출입"},
    {"생산관리", "생산기획", "공정관리"},
    {"품질관리", "QC", "품질검사"},

    # ── 총무/경영지원 ────────────────────────────────────────────────
    {"총무", "경영지원", "어드민"},
    {"시설관리", "자산관리", "건물관리"},

    # ── 콘텐츠/미디어 ────────────────────────────────────────────────
    {"작가", "콘텐츠작가", "카피라이터", "에디터"},
    {"PD", "영상PD", "콘텐츠PD"},
    {"기자", "뉴스에디터", "저널리스트"},
    {"번역가", "통역사", "로컬라이제이션"},

    # ── 교육/강사 ────────────────────────────────────────────────────
    {"강사", "교육담당", "트레이너"},
    {"에듀테크", "교육콘텐츠", "교육기획"},

    # ── 컨설팅/연구 ──────────────────────────────────────────────────
    {"컨설턴트", "경영컨설턴트", "전략컨설턴트"},
    {"연구개발", "R&D", "연구원"},

    # ── 의료/헬스케어 ────────────────────────────────────────────────
    {"의료기기", "헬스케어IT", "디지털헬스"},
    {"임상연구", "CRA", "임상시험"},

    # ── 금융/핀테크 ──────────────────────────────────────────────────
    {"애널리스트", "투자분석가", "리서치애널리스트"},
    {"핀테크", "금융IT", "금융개발자"},
    {"리스크관리", "리스크", "위험관리"},

    # ── 임원 ─────────────────────────────────────────────────────────
    {"CTO", "기술이사"}, {"CFO", "재무이사"}, {"CMO", "마케팅이사"},
    {"COO", "운영이사"}, {"CPO", "프로덕트이사"},
]

def _build_synonym_lookup(groups):
    lookup = {}
    for group in groups:
        lst = sorted(group)
        for term in group:
            others = [t for t in lst if t != term]
            if others:
                lookup[term.lower()] = others
    return lookup

SYNONYM_LOOKUP = _build_synonym_lookup(_SYNONYM_GROUPS)

def get_synonyms(keyword):
    return SYNONYM_LOOKUP.get(keyword.strip().lower(), [])

# ── 캐시 ────────────────────────────────────────────────────────
def _cache_key(q, sites): return f"{q}|{','.join(sorted(sites))}"

def _get_cache(q, sites):
    key = _cache_key(q, sites)
    if key in CACHE:
        data, ts = CACHE[key]
        if time.time() - ts < CACHE_TTL:
            return data
    return None

def _set_cache(q, sites, data):
    CACHE[_cache_key(q, sites)] = (data, time.time())


_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def _fetch_company_info(url, site):
    if not url or site == "자소설닷컴":
        return ""
    try:
        r = _req.get(url, headers=_HEADERS, timeout=8)
        soup = _BS(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer"]):
            tag.decompose()
        text = re.sub(r"\s+", " ", soup.get_text()).strip()
        return text[300:2500]
    except Exception:
        return ""


def login_required(f):
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        if _db_enabled and not session.get("user_id"):
            return redirect(url_for("login_page", next=request.path))
        return f(*args, **kwargs)
    return wrapped


def admin_required(f):
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return wrapped


def _run(q, sites):
    tasks = {name: fn for name, fn in SCRAPERS.items() if name in sites}
    raw, counts = [], {}

    def fetch(name, fn):
        try:
            return name, fn(q)
        except Exception:
            return name, []

    with ThreadPoolExecutor(max_workers=len(tasks)) as ex:
        futures = {ex.submit(fetch, name, fn): name for name, fn in tasks.items()}
        for future in as_completed(futures):
            name, jobs = future.result()
            raw += jobs
            counts[name] = len(jobs)

    return raw, counts


@app.route("/login", methods=["GET", "POST"])
def login_page():
    if not _db_enabled:
        return redirect(url_for("index"))
    if session.get("user_id"):
        return redirect(url_for("index"))
    error = None
    if request.method == "POST":
        if not _csrf_validate():
            return "잘못된 요청입니다.", 403
        try:
            user = db.check_password(request.form["username"], request.form["password"])
            if user:
                session["user_id"]  = user["id"]
                session["username"] = user["username"]
                session["is_admin"] = user["is_admin"]
                return redirect(request.args.get("next") or url_for("index"))
            error = "아이디 또는 비밀번호가 올바르지 않습니다."
        except Exception as e:
            print(f"[LOGIN ERROR] {e}")
            error = f"DB 오류: {e}"
    return render_template("login.html", error=error)


@app.route("/health")
def health():
    status = {"db_enabled": _db_enabled}
    if _db_enabled:
        try:
            db.init_db()
            status["db"] = "ok"
        except Exception as e:
            status["db"] = f"error: {e}"
    return jsonify(status)


@app.route("/register", methods=["GET", "POST"])
def register():
    if not _db_enabled:
        return redirect(url_for("index"))
    if session.get("user_id"):
        return redirect(url_for("index"))
    error = ok = None
    if request.method == "POST":
        if not _csrf_validate():
            return "잘못된 요청입니다.", 403
        username  = request.form.get("username","").strip()
        password  = request.form.get("password","")
        password2 = request.form.get("password2","")
        if not username or not password:
            error = "아이디와 비밀번호를 입력하세요."
        elif password != password2:
            error = "비밀번호가 일치하지 않습니다."
        elif len(password) < 6:
            error = "비밀번호는 6자 이상이어야 합니다."
        else:
            try:
                db.create_user(username, password, is_admin=False)
                ok = "가입 완료! 로그인해주세요."
            except Exception as e:
                error = "이미 사용 중인 아이디이거나 오류가 발생했습니다."
    return render_template("register.html", error=error, ok=ok)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page") if _db_enabled else url_for("index"))


@app.route("/admin")
@login_required
@admin_required
def admin_page():
    users   = db.list_users()
    msg     = request.args.get("msg")
    msg_err = request.args.get("err")
    return render_template("admin.html", users=users, msg=msg, msg_err=msg_err)


@app.route("/admin/users", methods=["POST"])
@login_required
@admin_required
def admin_add_user():
    if not _csrf_validate():
        return "잘못된 요청입니다.", 403
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    is_admin = bool(request.form.get("is_admin"))
    if not username or not password:
        return redirect(url_for("admin_page", msg="아이디와 비밀번호를 입력하세요.", err=1))
    try:
        db.create_user(username, password, is_admin)
        return redirect(url_for("admin_page", msg=f"{username} 추가 완료"))
    except Exception as e:
        return redirect(url_for("admin_page", msg=f"오류: {e}", err=1))


@app.route("/admin/users/<int:uid>/delete", methods=["POST"])
@login_required
@admin_required
def admin_delete_user(uid):
    if not _csrf_validate():
        return "잘못된 요청입니다.", 403
    if uid == session.get("user_id"):
        return redirect(url_for("admin_page", msg="자신은 삭제할 수 없습니다.", err=1))
    db.delete_user(uid)
    return redirect(url_for("admin_page", msg="삭제 완료"))


@app.route("/api/analyze", methods=["POST"])
@login_required
def api_analyze():
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        return jsonify({"error": "API key not configured"}), 503
    resume = (request.get_json(force=True) or {}).get("resume", "").strip()[:2000]
    if not resume:
        return jsonify({"error": "이력서를 입력하세요"}), 400
    prompt = (
        f"다음 이력서를 분석해주세요.\n\n이력서:\n{resume}\n\n"
        "각 항목마다 이력서의 구체적인 내용을 근거로 인용하세요. 일반적인 조언 금지.\n"
        "아래 형식의 HTML로만 응답하세요. 다른 텍스트 없이.\n\n"
        "<b>추천 검색 키워드</b><br>"
        "<span class='kw-chip'>키워드1</span> ...(5~8개)<br><br>"
        "<b>적합한 직군</b><br>이력서 내용 인용하며 이유 설명<br><br>"
        "<b>강점</b><br>이력서에서 확인된 강점 2~3가지 (인용 포함)<br><br>"
        "<b>보완 포인트</b><br>직군 대비 이력서에서 빠진 항목 1~2가지"
    )
    try:
        resp = _req.post(
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": "deepseek-v4-flash", "messages": [{"role": "user", "content": prompt}], "temperature": 0.5},
            timeout=30,
        )
        resp.raise_for_status()
        html = resp.json()["choices"][0]["message"]["content"].strip()
        html = re.sub(r"^```html\s*|```$", "", html, flags=re.MULTILINE).strip()
    except Exception as e:
        return jsonify({"error": f"DeepSeek 호출 실패: {e}"}), 500
    db.save_analysis(session["user_id"], html)
    return jsonify({"html": html})


@app.route("/api/draft", methods=["POST"])
@login_required
def api_draft():
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        return jsonify({"error": "API key not configured"}), 503
    data      = request.get_json(force=True) or {}
    resume    = data.get("resume", "").strip()[:1500]
    job       = data.get("job", {})
    questions = data.get("questions", [])
    if not resume or not questions:
        return jsonify({"error": "resume and questions required"}), 400

    qs_text = "\n".join(f"문항 {i+1}: {q}" for i, q in enumerate(questions))
    company_info = f"지원 공고: {job.get('company','')} — {job.get('title','')}\n"
    if job.get("stacks"):   company_info += f"기술 스택: {job['stacks']}\n"
    if job.get("career"):   company_info += f"경력 요건: {job['career']}\n"
    if job.get("funding"):  company_info += f"투자 단계: {job['funding']}\n"
    if job.get("members"):  company_info += f"직원 수: {job['members']}명\n"
    if job.get("location"): company_info += f"위치: {job['location']}\n"
    scraped = _fetch_company_info(job.get("link",""), job.get("site",""))
    if scraped:
        company_info += f"\n[공고 페이지에서 수집한 회사/직무 정보]\n{scraped}\n"
    prompt = (
        f"지원자 이력서:\n{resume}\n\n"
        f"{company_info}\n"
        f"아래 자소서 문항에 대해 이력서와 회사 정보를 최대한 활용해 구체적으로 답변을 작성해주세요.\n\n"
        f"{qs_text}\n\n"
        "각 문항을 '【문항 1】', '【문항 2】' 형식으로 구분해서 작성해주세요."
    )
    try:
        resp = _req.post(
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": "deepseek-v4-flash", "messages": [{"role": "user", "content": prompt}], "temperature": 0.7},
            timeout=90,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return jsonify({"error": f"DeepSeek 호출 실패: {e}"}), 500
    return jsonify({"draft": content})


@app.route("/api/match", methods=["POST"])
@login_required
def api_match():
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        return jsonify({"error": "API key not configured"}), 503
    data    = request.get_json(force=True) or {}
    resume  = data.get("resume", "").strip()[:1500]
    jobs    = data.get("jobs", [])
    if not resume or not jobs:
        return jsonify({"error": "resume and jobs required"}), 400

    # 스택 정보 없는 공고만 병렬 스크래핑해서 직무 설명 보완
    def _scrape(item):
        idx, j = item
        if j.get("stacks") or j.get("site") == "자소설닷컴":
            return idx, ""
        return idx, _fetch_company_info(j.get("link", ""), j.get("site", ""))

    snippets = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        for idx, text in ex.map(_scrape, enumerate(jobs)):
            snippets[idx] = text[:200] if text else ""

    compressed = [
        {
            "idx": i,
            "title": j.get("title", ""),
            "company": j.get("company", ""),
            "stacks": j.get("stacks", ""),
            "career": j.get("career", ""),
            **({"desc": snippets[i]} if snippets.get(i) else {}),
        }
        for i, j in enumerate(jobs)
    ]
    prompt = (
        "다음 이력서를 기반으로 각 공고 매칭율을 분석해주세요.\n\n"
        f"이력서:\n{resume}\n\n"
        f"공고 목록 (desc는 공고 페이지에서 수집한 직무 설명 일부):\n"
        f"{json.dumps(compressed, ensure_ascii=False)}\n\n"
        "JSON 배열만 반환하세요. 다른 텍스트 없이.\n"
        '형식: [{"idx":0,"score":85,"reason":"한줄이유"}, ...]'
    )
    try:
        resp = _req.post(
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": "deepseek-v4-flash", "messages": [{"role": "user", "content": prompt}], "temperature": 0.3},
            timeout=60,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return jsonify({"error": f"DeepSeek 호출 실패: {e}"}), 500
    m = re.search(r"\[.*\]", content, re.DOTALL)
    if m:
        return jsonify({"scores": json.loads(m.group())})
    return jsonify({"error": "응답 파싱 실패", "raw": content[:200]}), 500


@app.route("/api/resume/versions", methods=["GET", "POST"])
@login_required
def api_resume_versions():
    uid = session["user_id"]
    if request.method == "POST":
        data  = request.get_json(force=True) or {}
        content = data.get("content", "").strip()
        label   = data.get("label", "").strip()
        if not content:
            return jsonify({"error": "content required"}), 400
        db.save_resume_version(uid, content, label)
        return jsonify({"ok": True})
    versions = db.get_resume_versions(uid)
    return jsonify({"versions": versions})


@app.route("/api/resume", methods=["GET", "POST"])
@login_required
def api_resume():
    uid = session["user_id"]
    if request.method == "POST":
        content = (request.get_json(force=True) or {}).get("content", "").strip()
        structured = {}
        key = os.environ.get("DEEPSEEK_API_KEY")
        if key and content:
            try:
                prompt = (
                    f"다음 이력서를 JSON으로 구조화하세요.\n\n이력서:\n{content[:2000]}\n\n"
                    '아래 JSON 형식으로만 응답하세요. 없는 항목은 빈 값으로:\n'
                    '{"이름":"","희망직군":"","경력":"","기술스택":[],"자격증":[],"학력":"","언어":[],"기타":""}'
                )
                r = _req.post(
                    "https://api.deepseek.com/chat/completions",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json={"model": "deepseek-v4-flash", "messages": [{"role": "user", "content": prompt}], "temperature": 0.1},
                    timeout=20,
                )
                raw = r.json()["choices"][0]["message"]["content"].strip()
                raw = re.sub(r"^```json\s*|```$", "", raw, flags=re.MULTILINE).strip()
                structured = json.loads(raw)
            except Exception:
                pass
        db.save_resume(uid, content, structured if structured else None)
        return jsonify({"ok": True, "structured": structured})
    content, structured, analysis, analyzed_at = db.get_resume(uid)
    return jsonify({"content": content, "structured": structured, "analysis": analysis, "analyzed_at": analyzed_at})


@app.route("/api/bookmarks", methods=["GET", "POST"])
@login_required
def api_bookmarks():
    uid = session["user_id"]
    if request.method == "POST":
        job_ids = (request.get_json(force=True) or {}).get("job_ids", [])
        db.save_bookmarks(uid, job_ids)
        return jsonify({"ok": True})
    return jsonify({"job_ids": db.get_bookmarks(uid)})


@app.route("/api/drafts", methods=["GET", "POST"])
@login_required
def api_drafts():
    uid = session["user_id"]
    if request.method == "POST":
        data = request.get_json(force=True) or {}
        job_id     = data.get("job_id", "").strip()
        draft_text = data.get("draft", "").strip()
        if not job_id:
            return jsonify({"error": "job_id required"}), 400
        db.save_draft(uid, job_id, draft_text)
        return jsonify({"ok": True})
    return jsonify({"drafts": db.get_drafts(uid)})


@app.route("/export.csv")
@login_required
def export_csv():
    q           = request.args.get("q", "").strip()
    sites_param = request.args.get("sites", "")
    also_param  = request.args.get("also", "")
    active_sites = [s for s in sites_param.split(",") if s in SCRAPERS] if sites_param else ALL_SITES
    also_terms   = [t.strip() for t in also_param.split(",") if t.strip()] if also_param else []

    all_raw = []
    for kw in ([q] + also_terms if q else []):
        cached = _get_cache(kw, active_sites)
        raw, _ = cached if cached else _run(kw, active_sites)
        all_raw.extend(raw)

    results = mark_new(dedup(all_raw))

    fields = ["site", "company", "title", "career", "location", "deadline", "dday", "stacks", "link"]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    w.writerows(results)

    filename = f"jobs_{q or 'all'}.csv"
    return Response(
        "﻿" + buf.getvalue(),  # BOM for Excel UTF-8
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.route("/")
@login_required
def index():
    q     = request.args.get("q", "").strip()
    size  = request.args.get("size", "all")
    label = {"all": "전체", "big": "대기업", "corp": "중견·중소", "startup": "스타트업"}.get(size, "전체")
    sites_param   = request.args.get("sites", "")
    active_sites  = [s for s in sites_param.split(",") if s in SCRAPERS] if sites_param else ALL_SITES
    results, duped, counts, locs = [], 0, {}, []
    current_user = (
        {"username": session.get("username"), "is_admin": session.get("is_admin")}
        if _db_enabled else None
    )

    also_param = request.args.get("also", "")
    also_terms = [t.strip() for t in also_param.split(",") if t.strip()] if also_param else []
    suggestions = [s for s in get_synonyms(q) if s.lower() not in {a.lower() for a in also_terms}] if q else []

    if q:
        keywords = [q] + also_terms

        def fetch_kw(kw):
            cached = _get_cache(kw, active_sites)
            if cached:
                return cached  # (raw, counts)
            raw, cnts = _run(kw, active_sites)
            _set_cache(kw, active_sites, (raw, cnts))
            return raw, cnts

        all_raw, counts = [], {}
        with ThreadPoolExecutor(max_workers=len(keywords)) as ex:
            for raw, cnts in ex.map(fetch_kw, keywords):
                all_raw.extend(raw)
                for site, cnt in cnts.items():
                    counts[site] = counts.get(site, 0) + cnt

        deduped = dedup(all_raw)
        results = mark_new(deduped)
        duped   = len(all_raw) - len(deduped)
        locs = sorted({(j.get("location") or "").strip().split()[0]
                       for j in results if j.get("location")} - {""})

    return render_template(
        "index.html", q=q, size=size, size_label=label,
        results=results, duped=duped, site_counts=counts, locations=locs,
        current_user=current_user,
        all_sites=ALL_SITES, active_sites=active_sites,
        also_terms=also_terms, suggestions=suggestions,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"http://localhost:{port}")
    app.run(debug=False, host="0.0.0.0", port=port)
