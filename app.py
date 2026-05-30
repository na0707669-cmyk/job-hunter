import os
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, request, render_template_string
from job_hunt import (
    search_saramin, search_jobkorea, search_groupby, search_jasoseol,
    dedup, mark_new, save_seen
)

app = Flask(__name__)

SIZE_SITES = {
    "all":     ["자소설닷컴", "사람인", "잡코리아", "그룹바이"],
    "big":     ["자소설닷컴"],
    "corp":    ["사람인", "잡코리아"],
    "startup": ["그룹바이"],
}

SCRAPERS = {
    "자소설닷컴": search_jasoseol,
    "사람인": search_saramin,
    "잡코리아": search_jobkorea,
    "그룹바이": search_groupby,
}

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
</div>

<div class="mp" id="mp" style="display:none">
  <h3>📄 이력서 매칭</h3>
  <div class="mr">
    <textarea id="rv" placeholder="이력서 내용을 붙여넣으세요..."></textarea>
    <button onclick="saveR()">저장</button>
  </div>
  <div class="mn">저장된 이력서는 로컬에 보관됩니다. DeepSeek API 키 설정 시 각 공고 매칭율이 표시됩니다.</div>
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
  <label style="margin-left:8px">정렬</label>
  <select id="fs" onchange="filt()">
    <option value="">기본순</option>
    <option value="dday">마감 임박순</option>
    <option value="new">NEW 우선</option>
  </select>
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
  </tr></thead>
  <tbody id="tb-body">
  {% for j in results %}
  <tr class="jr"
      data-dday="{{ j.dday if j.dday is not none else 9999 }}"
      data-loc="{{ j.location }}"
      data-id="{{ j.company }}|{{ j.title }}"
      data-isnew="{{ 'y' if j.is_new else 'n' }}">
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

<script>
const HK='jh_h', BK='jh_b', RK='jh_r';
const gh=()=>{try{return JSON.parse(localStorage.getItem(HK))||[]}catch{return[]}};
const gb=()=>{try{return JSON.parse(localStorage.getItem(BK))||[]}catch{return[]}};
const sh=v=>localStorage.setItem(HK,JSON.stringify(v));
const sb=v=>localStorage.setItem(BK,JSON.stringify(v));

function addH(q){if(!q)return;let h=gh().filter(x=>x!==q);h.unshift(q);sh(h.slice(0,8))}
function renderH(){
  const box=document.getElementById('hist'), h=gh();
  if(!h.length){box.style.display='none';return}
  box.innerHTML=h.map(q=>`<div class="hi" onclick="pickH('${q}')"><span>${q}</span><span class="hx" onclick="delH(event,'${q}')">✕</span></div>`).join('');
  box.style.display='block';
}
function pickH(q){document.getElementById('qi').value=q;document.getElementById('hist').style.display='none';go()}
function delH(e,q){e.stopPropagation();sh(gh().filter(x=>x!==q));renderH()}
document.getElementById('qi').addEventListener('focus',renderH);
document.addEventListener('click',e=>{if(!e.target.closest('.search-row'))document.getElementById('hist').style.display='none'});

function go(){
  const q=document.getElementById('qi').value.trim();
  if(!q)return;
  addH(q);
  window.location.href=`/?q=${encodeURIComponent(q)}&size=${document.getElementById('sz').value}`;
}
document.getElementById('qi').addEventListener('keydown',e=>{if(e.key==='Enter')go()});

function bm(btn,id){
  let b=gb();
  if(b.includes(id)){b=b.filter(x=>x!==id);btn.textContent='☆'}
  else{b.push(id);btn.textContent='⭐'}
  sb(b);updBC();
  if(document.getElementById('fb')&&document.getElementById('fb').checked)filt();
}
function initBM(){
  const b=gb();
  document.querySelectorAll('.jr').forEach(r=>{
    if(b.includes(r.dataset.id))r.querySelector('.bm').textContent='⭐';
  });
  updBC();
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
  const sort=document.getElementById('fs')?.value||'';
  const bmOnly=document.getElementById('fb')?.checked;
  const b=gb();
  const rows=Array.from(document.querySelectorAll('.jr'));
  rows.forEach(r=>{
    const rd=parseInt(r.dataset.dday),rl=r.dataset.loc||'',ri=r.dataset.id;
    let show=true;
    if(dd&&(isNaN(rd)||rd>dd||rd<0))show=false;
    if(loc&&!rl.includes(loc))show=false;
    if(bmOnly&&!b.includes(ri))show=false;
    r.style.display=show?'':'none';
  });
  if(sort){
    const tbody=document.getElementById('tb-body');
    const vis=rows.filter(r=>r.style.display!=='none');
    vis.sort((a,z)=>sort==='dday'?parseInt(a.dataset.dday)-parseInt(z.dataset.dday):(z.dataset.isnew==='y')-(a.dataset.isnew==='y'));
    vis.forEach(r=>tbody.appendChild(r));
  }
  let n=1;rows.forEach(r=>{if(r.style.display!=='none')r.cells[0].textContent=n++});
}
function clrF(){
  ['fd','fl','fs'].forEach(id=>{const el=document.getElementById(id);if(el)el.value=''});
  document.getElementById('fb').checked=false;
  filt();
}

function saveR(){
  const v=document.getElementById('rv')?.value.trim();
  if(!v)return;
  localStorage.setItem(RK,v);
  alert('이력서 저장 완료');
}

window.addEventListener('load',()=>{
  initBM();
  const rv=localStorage.getItem(RK);
  if(rv&&document.getElementById('rv'))document.getElementById('rv').value=rv;
  const mp=document.getElementById('mp');
  if(mp)mp.style.display='';
});
</script>
</body>
</html>"""


def _run(q, size):
    target = SIZE_SITES.get(size, SIZE_SITES["all"])
    tasks = {name: fn for name, fn in SCRAPERS.items() if name in target}
    raw, counts = [], {}

    def fetch(name, fn):
        try:
            jobs = fn(q)
            return name, jobs
        except Exception:
            return name, []

    with ThreadPoolExecutor(max_workers=len(tasks)) as ex:
        futures = {ex.submit(fetch, name, fn): name for name, fn in tasks.items()}
        for future in as_completed(futures):
            name, jobs = future.result()
            raw += jobs
            counts[name] = len(jobs)

    return raw, counts


@app.route("/")
def index():
    q    = request.args.get("q", "").strip()
    size = request.args.get("size", "all")
    label = {"all":"전체","big":"대기업","corp":"중견·중소","startup":"스타트업"}.get(size,"전체")
    results, duped, counts, locs = [], 0, {}, []

    if q:
        raw, counts = _run(q, size)
        deduped  = dedup(raw)
        results  = mark_new(deduped)
        duped    = len(raw) - len(deduped)
        save_seen(results)
        locs = sorted({(j.get("location") or "").strip().split()[0]
                       for j in results if j.get("location")} - {""})

    return render_template_string(
        HTML, q=q, size=size, size_label=label,
        results=results, duped=duped, site_counts=counts, locations=locs,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"http://localhost:{port}")
    app.run(debug=False, host="0.0.0.0", port=port)
