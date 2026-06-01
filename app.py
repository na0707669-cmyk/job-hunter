import os
import re
import time
import json
import secrets
import functools
import requests as _req
from bs4 import BeautifulSoup as _BS
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, request, render_template_string, redirect, url_for, session, jsonify
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


_AUTH_STYLE = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,'Noto Sans KR',sans-serif;background:#f0f2f5;display:flex;justify-content:center;align-items:center;min-height:100vh}
.box{background:#fff;padding:40px;border-radius:12px;box-shadow:0 2px 16px rgba(0,0,0,.1);width:340px}
h1{font-size:20px;font-weight:800;color:#1a1a2e;margin-bottom:24px;text-align:center}
input{display:block;width:100%;padding:10px 12px;border:1px solid #ddd;border-radius:6px;font-size:14px;margin-bottom:12px;outline:none}
input:focus{border-color:#1a1a2e}
button{width:100%;padding:11px;background:#1a1a2e;color:#fff;border:none;border-radius:6px;font-size:14px;cursor:pointer;font-weight:700}
button:hover{background:#2d2d4e}
.err{color:#e94560;font-size:13px;margin-bottom:12px;text-align:center}
.ok{color:#34a853;font-size:13px;margin-bottom:12px;text-align:center}
.sub{text-align:center;margin-top:14px;font-size:13px;color:#888}
.sub a{color:#1a1a2e;text-decoration:underline}
"""

LOGIN_HTML = """<!doctype html>
<html lang="ko">
<head><meta charset="utf-8"><title>공고 사냥 - 로그인</title>
<style>""" + _AUTH_STYLE + """</style></head>
<body>
<div class="box">
  <h1>🎯 공고 사냥</h1>
  {% if error %}<div class="err">{{ error }}</div>{% endif %}
  <form method="post">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <input type="text" name="username" placeholder="아이디" required autofocus>
    <input type="password" name="password" placeholder="비밀번호" required>
    <button type="submit">로그인</button>
  </form>
  <div class="sub">계정이 없으신가요? <a href="/register">회원가입</a></div>
</div>
</body>
</html>"""

REGISTER_HTML = """<!doctype html>
<html lang="ko">
<head><meta charset="utf-8"><title>공고 사냥 - 회원가입</title>
<style>""" + _AUTH_STYLE + """</style></head>
<body>
<div class="box">
  <h1>🎯 회원가입</h1>
  {% if error %}<div class="err">{{ error }}</div>{% endif %}
  {% if ok %}<div class="ok">{{ ok }}</div>{% endif %}
  <form method="post">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <input type="text" name="username" placeholder="아이디 (영문/숫자)" required autofocus>
    <input type="password" name="password" placeholder="비밀번호" required>
    <input type="password" name="password2" placeholder="비밀번호 확인" required>
    <button type="submit">가입하기</button>
  </form>
  <div class="sub">이미 계정이 있으신가요? <a href="/login">로그인</a></div>
</div>
</body>
</html>"""


ADMIN_HTML = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>유저 관리</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,'Noto Sans KR',sans-serif;background:#f0f2f5;padding:32px}
.wrap{max-width:680px;margin:0 auto}
h1{font-size:18px;font-weight:800;color:#1a1a2e;margin-bottom:4px}
.back{font-size:13px;color:#888;text-decoration:none;display:inline-block;margin-bottom:20px}
.back:hover{color:#1a1a2e}
h2{font-size:14px;font-weight:700;margin:20px 0 10px;color:#1a1a2e}
table{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.07)}
th{background:#1a1a2e;color:#8888aa;font-size:11px;text-align:left;padding:9px 12px;font-weight:500}
td{padding:10px 12px;border-bottom:1px solid #f2f2f2;font-size:13px}
tr:last-child td{border-bottom:none}
.del{background:#fce8e6;color:#e94560;border:none;border-radius:4px;padding:3px 9px;cursor:pointer;font-size:12px}
.add-form{background:#fff;border-radius:8px;padding:16px;box-shadow:0 1px 4px rgba(0,0,0,.07);display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.add-form input[type=text],.add-form input[type=password]{padding:8px 10px;border:1px solid #ddd;border-radius:6px;font-size:13px;flex:1;min-width:100px}
.add-form label{font-size:13px;display:flex;align-items:center;gap:4px;white-space:nowrap}
.add-form button{padding:8px 18px;background:#1a1a2e;color:#fff;border:none;border-radius:6px;font-size:13px;cursor:pointer;font-weight:600}
.msg{font-size:13px;color:#34a853;margin:8px 0}
.merr{font-size:13px;color:#e94560;margin:8px 0}
</style>
</head>
<body>
<div class="wrap">
  <h1>👥 유저 관리</h1>
  <a class="back" href="/">← 메인으로</a>
  <h2>유저 목록 ({{ users|length }}명)</h2>
  <table>
    <tr><th>아이디</th><th>권한</th><th>가입일</th><th></th></tr>
    {% for u in users %}
    <tr>
      <td>{{ u.username }}</td>
      <td>{{ '관리자' if u.is_admin else '일반' }}</td>
      <td style="color:#999">{{ u.created_at[:10] if u.created_at else '-' }}</td>
      <td>
        {% if not u.is_admin %}
        <form method="post" action="/admin/users/{{ u.id }}/delete" style="display:inline" onsubmit="return confirm('{{ u.username }} 삭제?')">
          <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
          <button class="del">삭제</button>
        </form>
        {% endif %}
      </td>
    </tr>
    {% endfor %}
  </table>
  <h2>유저 추가</h2>
  {% if msg %}<div class="{{ 'merr' if msg_err else 'msg' }}">{{ msg }}</div>{% endif %}
  <form method="post" action="/admin/users" class="add-form">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <input type="text" name="username" placeholder="아이디" required>
    <input type="password" name="password" placeholder="비밀번호" required>
    <label><input type="checkbox" name="is_admin"> 관리자</label>
    <button type="submit">추가</button>
  </form>
</div>
</body>
</html>"""


HTML = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>공고 사냥</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,'Noto Sans KR',sans-serif;background:#f0f2f5;color:#222}

.top{background:#1a1a2e;color:#fff;padding:14px 24px;display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.top h1{font-size:16px;font-weight:800;white-space:nowrap}
.search-row{display:flex;gap:7px;flex:1;min-width:280px;position:relative}
.search-row input[type=text]{flex:1;padding:8px 11px;border:none;border-radius:6px;font-size:14px;outline:none}
.search-row select{padding:8px 9px;border:none;border-radius:6px;font-size:13px;background:#fff;cursor:pointer}
.search-row button{padding:8px 16px;background:#e94560;color:#fff;border:none;border-radius:6px;font-size:13px;cursor:pointer;font-weight:700}
.search-row button:hover{background:#c73652}
.uinfo{display:flex;align-items:center;gap:10px;margin-left:auto;font-size:12px;white-space:nowrap}
.uinfo a{color:#8888aa;text-decoration:none}
.site-row{flex-basis:100%;display:flex;gap:14px;flex-wrap:wrap;padding-top:8px;border-top:1px solid rgba(255,255,255,.12);margin-top:2px}
.site-lbl{display:flex;align-items:center;gap:4px;font-size:12px;cursor:pointer;color:#bbb;white-space:nowrap;user-select:none}
.site-lbl input{cursor:pointer;accent-color:#e94560}
.site-lbl:hover{color:#fff}
.slow-badge{font-size:10px;padding:1px 6px;background:#7c3aed;color:#fff;border-radius:8px;margin-left:2px}
.uinfo a:hover{color:#fff}

#hist{position:absolute;top:38px;left:0;width:260px;background:#fff;border-radius:8px;box-shadow:0 4px 16px rgba(0,0,0,.15);z-index:100;display:none;overflow:hidden}
#hist .hi{padding:9px 13px;font-size:13px;cursor:pointer;color:#333;display:flex;justify-content:space-between;align-items:center}
#hist .hi:hover{background:#f5f5f5}
#hist .hx{color:#bbb;font-size:11px;padding:2px 4px}
#hist .hx:hover{color:#e94560}

.filter-bar{background:#fff;padding:9px 24px;display:flex;gap:10px;align-items:center;flex-wrap:wrap;border-bottom:1px solid #eee}
.filter-bar label{font-size:12px;color:#888}
.filter-bar select{padding:5px 8px;border:1px solid #ddd;border-radius:5px;font-size:13px}
.filter-bar input[type=checkbox]{cursor:pointer}
.clr{margin-left:auto;font-size:12px;color:#e94560;cursor:pointer;text-decoration:underline}

.meta{padding:10px 24px 4px;font-size:13px;color:#666;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.meta b{color:#1a1a2e}
.stag{font-size:11px;padding:3px 9px;border-radius:20px;border:1px solid}
.stag-자소설닷컴{border-color:#7c3aed;color:#7c3aed;background:#ede9fe}
.stag-사람인{border-color:#1a73e8;color:#1a73e8;background:#e8f0fe}
.stag-잡코리아{border-color:#ea4335;color:#ea4335;background:#fce8e6}
.stag-그룹바이{border-color:#34a853;color:#34a853;background:#e6f4ea}
.stag-원티드{border-color:#36f;color:#36f;background:#eef}

.tabs{display:flex;padding:8px 24px 0}
.tab{padding:8px 16px;font-size:13px;cursor:pointer;border-bottom:2px solid transparent;color:#888}
.tab.on{color:#1a1a2e;border-bottom-color:#1a1a2e;font-weight:700}

.tw{padding:10px 24px 40px}
table{width:100%;border-collapse:collapse;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.07)}
th{background:#1a1a2e;color:#8888aa;font-size:11px;text-align:left;padding:10px 13px;font-weight:500;letter-spacing:.5px;text-transform:uppercase}
td{padding:11px 13px;border-bottom:1px solid #f2f2f2;font-size:13px;vertical-align:middle}
tr:last-child td{border-bottom:none}
tr:hover td{background:#fafbff}

.sb{display:inline-block;font-size:11px;padding:2px 6px;border-radius:4px;font-weight:700;white-space:nowrap}
.sb-자소설닷컴{background:#ede9fe;color:#7c3aed}
.sb-사람인{background:#e8f0fe;color:#1a73e8}
.sb-잡코리아{background:#fce8e6;color:#ea4335}
.sb-그룹바이{background:#e6f4ea;color:#34a853}

.jt a{color:#1a1a2e;text-decoration:none;font-weight:600;font-size:14px}
.jt a:hover{color:#e94560}
.js{font-size:12px;color:#777;margin-top:3px}
.stk{font-size:11px;color:#aaa;margin-top:3px}
.nb{display:inline-block;font-size:10px;padding:1px 5px;background:#e94560;color:#fff;border-radius:3px;margin-left:5px;font-weight:700}

.dd{display:inline-block;font-size:11px;padding:2px 6px;border-radius:4px;font-weight:600;white-space:nowrap}
.dd-u{background:#fce8e6;color:#e94560}
.dd-s{background:#fff3e0;color:#f57c00}
.dd-o{background:#e6f4ea;color:#34a853}
.dd-e{background:#f5f5f5;color:#aaa}

.cb{font-size:11px;padding:2px 6px;background:#f5f5f5;border-radius:4px;color:#666}
.fb{font-size:10px;padding:1px 5px;background:#e8f4fd;color:#0277bd;border-radius:3px;margin-left:4px}
.bm{background:none;border:none;cursor:pointer;font-size:16px;padding:2px;line-height:1}
.bm:hover{transform:scale(1.2)}

.mp{background:#fff;margin:8px 24px 12px;border-radius:10px;padding:18px;box-shadow:0 1px 4px rgba(0,0,0,.07)}
.mp h3{font-size:14px;margin-bottom:10px;color:#1a1a2e}
.mr{display:flex;gap:9px;align-items:flex-start;flex-wrap:wrap}
.mr textarea{flex:1;min-width:180px;height:80px;padding:8px;border:1px solid #ddd;border-radius:6px;font-size:13px;resize:vertical}
.mr button{padding:8px 14px;background:#1a1a2e;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:13px}
.mn{font-size:11px;color:#bbb;margin-top:5px}

.empty{text-align:center;padding:60px;color:#bbb;font-size:14px}

#dp{position:fixed;right:-520px;top:0;width:500px;height:100vh;background:#fff;box-shadow:-4px 0 24px rgba(0,0,0,.13);transition:right .28s ease;z-index:200;display:flex;flex-direction:column}
#dp.open{right:0}
#dp-head{background:#1a1a2e;color:#fff;padding:14px 18px;display:flex;justify-content:space-between;align-items:center;flex-shrink:0}
#dp-head h2{font-size:14px;font-weight:700}
#dp-close{background:none;border:none;color:#aaa;font-size:20px;cursor:pointer;line-height:1}
#dp-close:hover{color:#fff}
#dp-body{flex:1;overflow-y:auto;padding:16px 18px;display:flex;flex-direction:column;gap:12px}
.dp-job{background:#f8f8ff;border-radius:8px;padding:10px 12px;font-size:13px}
.dp-job strong{display:block;font-size:14px;margin-bottom:3px}
.dp-job span{color:#888}
.dp-qs label{font-size:12px;font-weight:700;color:#1a1a2e;margin-bottom:6px;display:block}
.dp-q{display:flex;gap:6px;margin-bottom:6px;align-items:flex-start}
.dp-q textarea{flex:1;padding:7px 9px;border:1px solid #ddd;border-radius:6px;font-size:12px;resize:vertical;min-height:38px;font-family:inherit}
.dp-q button{padding:4px 8px;border:none;border-radius:4px;cursor:pointer;font-size:14px;background:#f5f5f5;color:#999}
.dp-q button:hover{background:#fce8e6;color:#e94560}
#dp-add{font-size:12px;color:#7c3aed;cursor:pointer;text-decoration:underline;background:none;border:none;padding:0}
#dp-gen{padding:10px;background:#7c3aed;color:#fff;border:none;border-radius:8px;font-size:14px;cursor:pointer;font-weight:700;width:100%}
#dp-gen:hover{background:#6d28d9}
#dp-gen:disabled{background:#bbb;cursor:not-allowed}
#dp-out{background:#f8f8ff;border-radius:8px;padding:12px;font-size:13px;line-height:1.7;white-space:pre-wrap;border:1px solid #e8e8f0;display:none}
#dp-copy{padding:7px 14px;background:#1a1a2e;color:#fff;border:none;border-radius:6px;font-size:12px;cursor:pointer;display:none}
</style>
</head>
<body>

<div class="top">
  <h1>🎯 공고 사냥</h1>
  <div class="search-row">
    <input type="text" id="qi" placeholder="직무 키워드 (예: 백엔드 개발자)" value="{{ q }}" autocomplete="off" autofocus>
    <div id="hist"></div>
    <select id="sz">
      <option value="all"    {% if size=='all'    %}selected{% endif %}>전체</option>
      <option value="big"    {% if size=='big'    %}selected{% endif %}>대기업</option>
      <option value="corp"   {% if size=='corp'   %}selected{% endif %}>중견·중소</option>
      <option value="startup"{% if size=='startup'%}selected{% endif %}>스타트업</option>
    </select>
    <button onclick="go()">검색</button>
  </div>
  {% if current_user %}
  <div class="uinfo">
    <span style="color:#aaa">{{ current_user.username }}</span>
    {% if current_user.is_admin %}<a href="/admin">관리</a>{% endif %}
    <a href="/logout">로그아웃</a>
  </div>
  {% endif %}
  <div class="site-row">
    {% for site in all_sites %}
    <label class="site-lbl">
      <input type="checkbox" class="site-cb" value="{{ site }}"{% if site in active_sites %} checked{% endif %}>
      {{ site }}{% if site == '자소설닷컴' %}<span class="slow-badge">느림</span>{% endif %}
    </label>
    {% endfor %}
  </div>
</div>

<div class="mp" id="mp" style="display:none">
  <h3>📄 이력서</h3>
  <div class="mr">
    <textarea id="rv" placeholder="이력서 내용을 붙여넣으세요 (자격증, 스킬, 경력 등)..."></textarea>
    <div style="display:flex;flex-direction:column;gap:6px">
      <button onclick="saveR()">저장</button>
      <button id="analyze-btn" onclick="analyzeR()" style="background:#0277bd">이력서 분석</button>
      <button id="match-btn" onclick="matchJobs()" style="background:#7c3aed;display:none">AI 매칭</button>
    </div>
  </div>
  <div id="rv-structured" style="display:none;margin-top:10px;background:#f8f8ff;border-radius:8px;padding:12px;font-size:13px;border:1px solid #e0e0f0"></div>
  <div id="analyze-out" style="display:none;margin-top:10px;background:#f8f8ff;border-radius:8px;padding:12px;font-size:13px;line-height:1.7;border:1px solid #e0e0f0"></div>
  <div class="mn">이력서는 서버에 저장되며 자동으로 구조화됩니다.</div>
</div>

{% if q %}
<div class="meta">
  <b>{{ q }}</b> · {{ size_label }} · 총 <b>{{ results|length }}개</b>
  {% if duped %}<span style="color:#bbb">(중복 {{ duped }}개 제거)</span>{% endif %}
  <span style="display:flex;gap:6px;flex-wrap:wrap">
    {% for site,cnt in site_counts.items() %}
    <span class="stag stag-{{ site }}">{{ site }} {{ cnt }}</span>
    {% endfor %}
  </span>
</div>

<div class="filter-bar">
  <label>마감</label>
  <select id="fd" onchange="filt()">
    <option value="">전체</option>
    <option value="7">D-7 이내</option>
    <option value="14">D-14 이내</option>
    <option value="30">D-30 이내</option>
  </select>
  <label style="margin-left:8px">지역</label>
  <select id="fl" onchange="filt()">
    <option value="">전체</option>
    {% for loc in locations %}<option value="{{ loc }}">{{ loc }}</option>{% endfor %}
  </select>
  <label style="margin-left:8px">경력</label>
  <select id="fc" onchange="filt()">
    <option value="">전체</option>
    <option value="신입">신입</option>
    <option value="경력">경력</option>
    <option value="무관">무관</option>
  </select>
  <label style="margin-left:8px">정렬</label>
  <select id="fs" onchange="filt()">
    <option value="">기본순</option>
    <option value="dday">마감 임박순</option>
    <option value="new">NEW 우선</option>
  </select>
  <label style="margin-left:8px">AI매칭만</label>
  <input type="checkbox" id="fai" onchange="filt()">
  <label style="margin-left:8px">북마크만</label>
  <input type="checkbox" id="fb" onchange="filt()">
  <span class="clr" onclick="clrF()">초기화</span>
</div>

<div class="tabs">
  <div class="tab on" id="ta" onclick="switchTab('all')">전체</div>
  <div class="tab" id="tb" onclick="switchTab('bm')">⭐ 북마크 <span id="bc">0</span></div>
</div>
{% endif %}

<div class="tw">
{% if q and results %}
<table>
  <thead><tr>
    <th style="width:30px">#</th>
    <th style="width:98px">출처</th>
    <th>공고</th>
    <th style="width:76px">지역</th>
    <th style="width:76px">마감</th>
    <th style="width:58px">경력</th>
    <th style="width:34px">⭐</th>
    <th style="width:34px">📝</th>
  </tr></thead>
  <tbody id="tb-body">
  {% for j in results %}
  <tr class="jr"
      data-dday="{{ j.dday if j.dday is not none else 9999 }}"
      data-loc="{{ j.location }}"
      data-id="{{ j.company }}|{{ j.title }}"
      data-isnew="{{ 'y' if j.is_new else 'n' }}"
      data-career="{{ j.get('career','') }}">
    <td style="color:#ccc">{{ loop.index }}</td>
    <td>
      <span class="sb sb-{{ j.site }}">{{ j.site }}</span><br>
      <span style="font-size:10px;color:#ccc">{{ j.size }}</span>
      {% if j.get('funding') %}<span class="fb">{{ j.funding }}</span>{% endif %}
    </td>
    <td>
      <div class="jt">
        <a href="{{ j.link }}" target="_blank">{{ j.title }}</a>
        {% if j.is_new %}<span class="nb">NEW</span>{% endif %}
      </div>
      <div class="js">{{ j.company }}{% if j.get('location') %} · {{ j.location }}{% endif %}{% if j.get('members') %} · {{ j.members }}인{% endif %}</div>
      {% if j.get('stacks') %}<div class="stk">{{ j.stacks }}</div>{% endif %}
    </td>
    <td style="font-size:12px;color:#999">{{ j.location }}</td>
    <td>
      {% if j.dday is not none %}
        {% if j.dday < 0 %}<span class="dd dd-e">마감</span>
        {% elif j.dday <= 3 %}<span class="dd dd-u">D-{{ j.dday }}</span>
        {% elif j.dday <= 7 %}<span class="dd dd-s">D-{{ j.dday }}</span>
        {% else %}<span class="dd dd-o">D-{{ j.dday }}</span>{% endif %}
      {% elif j.deadline %}<span style="font-size:11px;color:#bbb">{{ j.deadline }}</span>
      {% else %}<span style="color:#ddd;font-size:11px">-</span>{% endif %}
    </td>
    <td>{% if j.get('career') %}<span class="cb">{{ j.career }}</span>{% endif %}</td>
    <td><button class="bm" onclick="bm(this,'{{ j.company }}|{{ j.title }}')">☆</button></td>
    <td><button class="bm" onclick='openDraft({{ loop.index0 }})'>📝</button></td>
  </tr>
  {% endfor %}
  </tbody>
</table>
{% elif q %}
<div class="empty">결과 없음 — 다른 키워드를 입력해보세요</div>
{% else %}
<div class="empty" style="margin-top:60px">키워드를 입력하고 검색하세요<br><span style="font-size:12px;color:#ddd;margin-top:8px;display:block">예: 백엔드 개발자 · PM · 마케터</span></div>
{% endif %}
</div>

<div id="dp">
  <div id="dp-head">
    <h2 id="dp-title">자소서 초안</h2>
    <button id="dp-close" onclick="closeDraft()">✕</button>
  </div>
  <div id="dp-body">
    <div class="dp-job" id="dp-job-info"></div>
    <div class="dp-qs">
      <label>자소서 문항 (수정·추가 가능)</label>
      <div id="dp-qlist"></div>
      <button id="dp-add" onclick="addQ()">+ 문항 추가</button>
    </div>
    <button id="dp-gen" onclick="genDraft()">✨ 초안 생성</button>
    <pre id="dp-out"></pre>
    <button id="dp-copy" onclick="copyDraft()">📋 복사</button>
  </div>
</div>

<script>
const JOBS={{ results|tojson }};
const HK='jh_h';
const gh=()=>{try{return JSON.parse(localStorage.getItem(HK))||[]}catch{return[]}};
const sh=v=>localStorage.setItem(HK,JSON.stringify(v));
let _bm=[];
const gb=()=>_bm;
const sb=async v=>{
  _bm=v;
  try{await fetch('/api/bookmarks',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_ids:v})})}catch{}
};

function addH(q){if(!q)return;let h=gh().filter(x=>x!==q);h.unshift(q);sh(h.slice(0,8))}
function renderH(){
  const box=document.getElementById('hist'),h=gh();
  if(!h.length){box.style.display='none';return}
  box.innerHTML=h.map(q=>`<div class="hi" onclick="pickH('${q}')"><span>${q}</span><span class="hx" onclick="delH(event,'${q}')">✕</span></div>`).join('');
  box.style.display='block';
}
function pickH(q){document.getElementById('qi').value=q;document.getElementById('hist').style.display='none';go();}
function delH(e,q){e.stopPropagation();sh(gh().filter(x=>x!==q));renderH()}
document.getElementById('qi').addEventListener('focus',renderH);
document.addEventListener('click',e=>{if(!e.target.closest('.search-row'))document.getElementById('hist').style.display='none'});

function go(){
  const q=document.getElementById('qi').value.trim();
  if(!q)return;
  addH(q);
  const sites=[...document.querySelectorAll('.site-cb:checked')].map(c=>c.value).join(',');
  window.location.href=`/?q=${encodeURIComponent(q)}&size=${document.getElementById('sz').value}&sites=${encodeURIComponent(sites)}`;
}
document.getElementById('qi').addEventListener('keydown',e=>{if(e.key==='Enter')go()});

async function bm(btn,id){
  let b=gb().slice();
  if(b.includes(id)){b=b.filter(x=>x!==id);btn.textContent='☆'}
  else{b.push(id);btn.textContent='⭐'}
  await sb(b);updBC();
  if(document.getElementById('fb')?.checked)filt();
}
function initBM(){
  const b=gb();
  document.querySelectorAll('.jr').forEach(r=>{
    if(b.includes(r.dataset.id))r.querySelector('.bm').textContent='⭐';
  });
}
function updBC(){const el=document.getElementById('bc');if(el)el.textContent=gb().length}

function switchTab(t){
  document.getElementById('ta').classList.toggle('on',t==='all');
  document.getElementById('tb').classList.toggle('on',t==='bm');
  document.getElementById('fb').checked=t==='bm';
  filt();
}

function filt(){
  const dd=parseInt(document.getElementById('fd')?.value)||0;
  const loc=document.getElementById('fl')?.value||'';
  const car=document.getElementById('fc')?.value||'';
  const sort=document.getElementById('fs')?.value||'';
  const aiOnly=document.getElementById('fai')?.checked;
  const bmOnly=document.getElementById('fb')?.checked;
  const b=gb();
  const rows=Array.from(document.querySelectorAll('.jr'));
  rows.forEach(r=>{
    const rd=parseInt(r.dataset.dday),rl=r.dataset.loc||'',ri=r.dataset.id,rc=r.dataset.career||'',rs=r.dataset.score;
    let show=true;
    if(dd&&(isNaN(rd)||rd>dd||rd<0))show=false;
    if(loc&&!rl.includes(loc))show=false;
    if(car&&rc!==car)show=false;
    if(aiOnly&&!rs)show=false;
    if(bmOnly&&!b.includes(ri))show=false;
    r.style.display=show?'':'none';
  });
  if(sort){
    const tbody=document.getElementById('tb-body');
    const vis=rows.filter(r=>r.style.display!=='none');
    vis.sort((a,z)=>sort==='dday'?parseInt(a.dataset.dday)-parseInt(z.dataset.dday):sort==='score'?parseInt(z.dataset.score||0)-parseInt(a.dataset.score||0):(z.dataset.isnew==='y')-(a.dataset.isnew==='y'));
    vis.forEach(r=>tbody.appendChild(r));
  }
  let n=1;rows.forEach(r=>{if(r.style.display!=='none')r.cells[0].textContent=n++});
}
function clrF(){
  ['fd','fl','fc','fs'].forEach(id=>{const el=document.getElementById(id);if(el)el.value=''});
  document.getElementById('fb').checked=false;
  const fai=document.getElementById('fai');if(fai)fai.checked=false;
  filt();
}

const DEFAULT_QS=[
  '1분 자기소개를 해주세요.',
  '지원동기를 말씀해주세요.',
  '본인의 강점과 약점을 설명해주세요.',
  '입사 후 포부를 말씀해주세요.',
  '직무 관련 경험이나 역량을 설명해주세요.',
];
let _dpJob=null;

function openDraft(idx){
  _dpJob=JOBS[idx];
  if(!_dpJob)return;
  document.getElementById('dp-title').textContent=_dpJob.company+' 자소서 초안';
  document.getElementById('dp-job-info').innerHTML=`<strong>${_dpJob.title}</strong><span>${_dpJob.company}${_dpJob.stacks?' · '+_dpJob.stacks:''}</span>`;
  const ql=document.getElementById('dp-qlist');
  ql.innerHTML='';
  DEFAULT_QS.forEach(q=>addQ(q));
  document.getElementById('dp-out').style.display='none';
  document.getElementById('dp-copy').style.display='none';
  document.getElementById('dp-out').textContent='';
  document.getElementById('dp').classList.add('open');
}
function closeDraft(){document.getElementById('dp').classList.remove('open');}
function addQ(txt=''){
  const ql=document.getElementById('dp-qlist');
  const d=document.createElement('div');d.className='dp-q';
  d.innerHTML=`<textarea rows="2">${txt}</textarea><button onclick="this.parentElement.remove()">✕</button>`;
  ql.appendChild(d);
}
async function genDraft(){
  const resume=document.getElementById('rv')?.value.trim();
  if(!resume){alert('이력서를 먼저 입력하세요.');return;}
  const qs=[...document.querySelectorAll('#dp-qlist textarea')].map(t=>t.value.trim()).filter(Boolean);
  if(!qs.length){alert('문항을 입력하세요.');return;}
  const btn=document.getElementById('dp-gen');
  btn.disabled=true;btn.textContent='생성 중...';
  try{
    const resp=await fetch('/api/draft',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({resume,job:_dpJob,questions:qs})});
    const d=await resp.json();
    if(d.error){alert('오류: '+d.error);return;}
    const out=document.getElementById('dp-out');
    out.textContent=d.draft;out.style.display='block';
    document.getElementById('dp-copy').style.display='inline-block';
  }catch{alert('네트워크 오류');}
  finally{btn.disabled=false;btn.textContent='✨ 초안 생성';}
}
function copyDraft(){
  navigator.clipboard.writeText(document.getElementById('dp-out').textContent);
  const b=document.getElementById('dp-copy');b.textContent='✓ 복사됨';
  setTimeout(()=>b.textContent='📋 복사',1500);
}

async function analyzeR(){
  const resume=document.getElementById('rv')?.value.trim();
  if(!resume){alert('이력서를 먼저 입력하세요.');return;}
  const btn=document.getElementById('analyze-btn');
  btn.disabled=true;btn.textContent='분석 중...';
  const out=document.getElementById('analyze-out');
  out.style.display='none';
  try{
    const resp=await fetch('/api/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({resume})});
    const d=await resp.json();
    if(d.error){out.innerHTML='<span style="color:#e94560">'+d.error+'</span>';out.style.display='block';return;}
    // Render keywords as clickable chips
    let html=d.html||'';
    out.innerHTML=html;
    out.style.display='block';
    // Bind keyword chips to search
    out.querySelectorAll('.kw-chip').forEach(el=>{
      el.style.cssText='display:inline-block;padding:3px 10px;background:#e8f0fe;color:#1a73e8;border-radius:12px;margin:2px;cursor:pointer;font-size:12px;font-weight:600';
      el.onclick=()=>{document.getElementById('qi').value=el.textContent;go();};
    });
  }catch{out.innerHTML='<span style="color:#e94560">네트워크 오류</span>';out.style.display='block';}
  finally{btn.disabled=false;btn.textContent='이력서 분석';}
}

async function matchJobs(){
  const resume=document.getElementById('rv')?.value.trim();
  if(!resume){alert('이력서를 먼저 입력/저장하세요.');return;}
  if(!JOBS||!JOBS.length){alert('먼저 공고를 검색하세요.');return;}
  const btn=document.getElementById('match-btn');
  btn.disabled=true;btn.textContent='분석 중...';
  try{
    const resp=await fetch('/api/match',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({resume,jobs:JOBS})});
    const data=await resp.json();
    if(data.error){alert('오류: '+data.error);return;}
    data.scores.forEach(({idx,score,reason})=>{
      const rows=document.querySelectorAll('.jr');
      if(!rows[idx])return;
      rows[idx].dataset.score=score;
      const jt=rows[idx].querySelector('.jt');
      if(jt){
        jt.querySelectorAll('.sc-badge').forEach(e=>e.remove());
        const b=document.createElement('span');
        b.className='sc-badge';
        b.title=reason;
        b.textContent=score+'%';
        const c=score>=70?'#34a853':score>=50?'#f57c00':'#e94560';
        const bg=score>=70?'#e6f4ea':score>=50?'#fff3e0':'#fce8e6';
        b.style.cssText=`display:inline-block;font-size:10px;padding:1px 7px;border-radius:10px;margin-left:6px;font-weight:700;background:${bg};color:${c};cursor:default`;
        jt.querySelector('a').insertAdjacentElement('afterend',b);
      }
    });
    const fs=document.getElementById('fs');
    if(fs&&![...fs.options].find(o=>o.value==='score')){
      const o=document.createElement('option');o.value='score';o.textContent='매칭순';fs.appendChild(o);
    }
  }catch(e){alert('네트워크 오류');}
  finally{btn.disabled=false;btn.textContent='AI 매칭';}
}

function renderStructured(s){
  if(!s||!Object.keys(s).length)return;
  const el=document.getElementById('rv-structured');
  if(!el)return;
  const rows=[];
  if(s['이름'])rows.push(`<b>이름</b> ${s['이름']}`);
  if(s['희망직군'])rows.push(`<b>희망직군</b> ${s['희망직군']}`);
  if(s['경력'])rows.push(`<b>경력</b> ${s['경력']}`);
  if(s['학력'])rows.push(`<b>학력</b> ${s['학력']}`);
  if(s['기술스택']?.length)rows.push(`<b>기술스택</b> ${s['기술스택'].join(', ')}`);
  if(s['자격증']?.length)rows.push(`<b>자격증</b> ${s['자격증'].join(', ')}`);
  if(s['언어']?.length)rows.push(`<b>언어</b> ${s['언어'].join(', ')}`);
  if(s['기타'])rows.push(`<b>기타</b> ${s['기타']}`);
  if(!rows.length)return;
  el.innerHTML='<div style="color:#888;font-size:11px;margin-bottom:6px">📋 구조화된 이력서</div>'+rows.map(r=>`<div style="margin-bottom:3px">${r}</div>`).join('');
  el.style.display='block';
}

async function saveR(){
  const v=document.getElementById('rv')?.value.trim();
  if(!v)return;
  try{
    const resp=await fetch('/api/resume',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({content:v})});
    const d=await resp.json();
    if(d.structured)renderStructured(d.structured);
    alert('이력서 저장 완료');
  }catch{alert('저장 실패');}
}

window.addEventListener('load',async()=>{
  try{const r=await fetch('/api/bookmarks');const d=await r.json();_bm=d.job_ids||[];}catch{_bm=[];}
  initBM();updBC();
  try{
    const r=await fetch('/api/resume');const d=await r.json();
    if(d.content&&document.getElementById('rv'))document.getElementById('rv').value=d.content;
    if(d.structured)renderStructured(d.structured);
    if(d.analysis){
      const out=document.getElementById('analyze-out');
      if(out){
        const ts=d.analyzed_at?`<div style="color:#bbb;font-size:11px;margin-bottom:8px">마지막 분석: ${d.analyzed_at.slice(0,10)}</div>`:'';
        out.innerHTML=ts+d.analysis;
        out.style.display='block';
        out.querySelectorAll('.kw-chip').forEach(el=>{
          el.style.cssText='display:inline-block;padding:3px 10px;background:#e8f0fe;color:#1a73e8;border-radius:12px;margin:2px;cursor:pointer;font-size:12px;font-weight:600';
          el.onclick=()=>{document.getElementById('qi').value=el.textContent;go();};
        });
      }
    }
  }catch{}
  const mp=document.getElementById('mp');
  if(mp)mp.style.display='';
  const matchBtn=document.getElementById('match-btn');
  if(JOBS&&JOBS.length>0&&matchBtn)matchBtn.style.display='';
});
</script>
</body>
</html>"""


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
    return render_template_string(LOGIN_HTML, error=error)


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
    return render_template_string(REGISTER_HTML, error=error, ok=ok)


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
    return render_template_string(ADMIN_HTML, users=users, msg=msg, msg_err=msg_err)


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

    compressed = [
        {"idx": i, "title": j.get("title",""), "company": j.get("company",""),
         "stacks": j.get("stacks",""), "career": j.get("career","")}
        for i, j in enumerate(jobs)
    ]
    prompt = (
        "다음 이력서를 기반으로 각 공고 매칭율을 분석해주세요.\n\n"
        f"이력서:\n{resume}\n\n"
        f"공고 목록:\n{json.dumps(compressed, ensure_ascii=False)}\n\n"
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

    if q:
        cached = _get_cache(q, active_sites)
        if cached:
            results, duped, counts = cached
        else:
            raw, counts = _run(q, active_sites)
            deduped = dedup(raw)
            results = mark_new(deduped)
            duped   = len(raw) - len(deduped)
            _set_cache(q, active_sites, (results, duped, counts))
        locs = sorted({(j.get("location") or "").strip().split()[0]
                       for j in results if j.get("location")} - {""})

    return render_template_string(
        HTML, q=q, size=size, size_label=label,
        results=results, duped=duped, site_counts=counts, locations=locs,
        current_user=current_user,
        all_sites=ALL_SITES, active_sites=active_sites,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"http://localhost:{port}")
    app.run(debug=False, host="0.0.0.0", port=port)
