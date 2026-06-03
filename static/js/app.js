// ── History ──────────────────────────────────────────────────────
const HK = 'jh_h';
const PK = 'jh_pins';
const gh = () => { try { return JSON.parse(localStorage.getItem(HK)) || []; } catch { return []; } };
const sh = v => localStorage.setItem(HK, JSON.stringify(v));
const gp = () => { try { return JSON.parse(localStorage.getItem(PK)) || []; } catch { return []; } };
const sp = v => localStorage.setItem(PK, JSON.stringify(v));

function addH(q) {
  if (!q) return;
  let h = gh().filter(x => x !== q);
  h.unshift(q);
  sh(h.slice(0, 8));
}
function renderH() {
  const box = document.getElementById('hist'), h = gh();
  if (!h.length) { box.style.display = 'none'; return; }
  box.innerHTML = h.map(q =>
    `<div class="hi" onclick="pickH('${q}')"><span>${q}</span><span class="hx" onclick="delH(event,'${q}')">✕</span></div>`
  ).join('');
  box.style.display = 'block';
}
function pickH(q) { document.getElementById('qi').value = q; document.getElementById('hist').style.display = 'none'; go(); }
function delH(e, q) { e.stopPropagation(); sh(gh().filter(x => x !== q)); renderH(); }

function renderPins() {
  const box = document.getElementById('pin-row');
  if (!box) return;
  const pins = gp();
  if (!pins.length) { box.style.display = 'none'; return; }
  box.innerHTML = '<span class="pin-label">고정 검색어</span>' + pins.map(q =>
    `<button class="pin-chip" onclick="pickPin('${q}')"><span>${q}</span><b onclick="unpin(event,'${q}')">✕</b></button>`
  ).join('');
  box.style.display = 'flex';
}
function pinCurrent() {
  const q = document.getElementById('qi').value.trim();
  if (!q) return;
  const pins = gp().filter(x => x !== q);
  pins.unshift(q);
  sp(pins.slice(0, 10));
  renderPins();
}
function pickPin(q) {
  document.getElementById('qi').value = q;
  go();
}
function unpin(e, q) {
  e.stopPropagation();
  sp(gp().filter(x => x !== q));
  renderPins();
}

document.getElementById('qi').addEventListener('focus', renderH);
document.addEventListener('click', e => {
  if (!e.target.closest('.search-row')) document.getElementById('hist').style.display = 'none';
});

// ── Navigation ───────────────────────────────────────────────────
function showLoading() {
  const el = document.getElementById('loading-overlay');
  if (el) el.classList.add('on');
}
// 뒤로가기로 복귀 시 오버레이가 남아있지 않도록
window.addEventListener('pageshow', () => {
  const el = document.getElementById('loading-overlay');
  if (el) el.classList.remove('on');
});

function go() {
  const q = document.getElementById('qi').value.trim();
  if (!q) return;
  addH(q);
  const sites = [...document.querySelectorAll('.site-cb:checked')].map(c => c.value).join(',');
  showLoading();
  window.location.href = `/?q=${encodeURIComponent(q)}&size=${document.getElementById('sz').value}&sites=${encodeURIComponent(sites)}`;
}
document.getElementById('qi').addEventListener('keydown', e => { if (e.key === 'Enter') go(); });

function addAlso(term) {
  const u = new URL(window.location.href);
  const a = (u.searchParams.get('also') || '').split(',').filter(t => t);
  if (!a.includes(term)) a.push(term);
  u.searchParams.set('also', a.join(','));
  showLoading();
  window.location.href = u.toString();
}
function removeAlso(term) {
  const u = new URL(window.location.href);
  const a = (u.searchParams.get('also') || '').split(',').filter(t => t && t !== term);
  if (a.length > 0) u.searchParams.set('also', a.join(','));
  else u.searchParams.delete('also');
  showLoading();
  window.location.href = u.toString();
}

function escHtml(s) {
  return String(s || '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}

// ── Bookmarks ────────────────────────────────────────────────────
let _bm = [];
const gb = () => _bm;

// ── Saved drafts ─────────────────────────────────────────────────
let _drafts = {};   // { "company|title": "draft text" }
async function loadDrafts() {
  try { const r = await fetch('/api/drafts'); const d = await r.json(); _drafts = d.drafts || {}; } catch { _drafts = {}; }
  markDraftRows();
}
async function saveDraftToServer(jobId, text) {
  try {
    await fetch('/api/drafts', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ job_id: jobId, draft: text }) });
    _drafts[jobId] = text;
    markDraftRows();
  } catch { alert('저장 실패'); }
}
function markDraftRows() {
  document.querySelectorAll('.jr').forEach(r => {
    const hasDraft = !!_drafts[r.dataset.id];
    let badge = r.querySelector('.draft-badge');
    if (hasDraft && !badge) {
      badge = document.createElement('span');
      badge.className = 'draft-badge';
      badge.title = '저장된 자소서 초안 있음';
      badge.textContent = '📝';
      badge.style.cssText = 'margin-left:4px;font-size:11px;cursor:default';
      r.querySelector('.bm')?.after(badge);
    } else if (!hasDraft && badge) {
      badge.remove();
    }
  });
}
const sb = async v => {
  _bm = v;
  try { await fetch('/api/bookmarks', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ job_ids: v }) }); } catch {}
};

async function bm(btn, id) {
  let b = gb().slice();
  if (b.includes(id)) { b = b.filter(x => x !== id); btn.textContent = '☆'; }
  else { b.push(id); btn.textContent = '⭐'; }
  await sb(b); updBC();
  if (document.getElementById('fb')?.checked) filt();
}
function initBM() {
  const b = gb();
  document.querySelectorAll('.jr').forEach(r => {
    if (b.includes(r.dataset.id)) r.querySelector('.bm').textContent = '⭐';
  });
}
function updBC() { const el = document.getElementById('bc'); if (el) el.textContent = gb().length; }

// ── Application Tracker ──────────────────────────────────────────
const APP_LABELS = { saved:'관심', applying:'지원예정', applied:'지원완료', docs_pass:'서류통과', interview:'면접', offer:'합격', rejected:'불합격' };
const APP_COLORS = { saved:'#8888aa', applying:'#1a73e8', applied:'#34a853', docs_pass:'#0097a7', interview:'#f57c00', offer:'#4caf50', rejected:'#e94560' };
const APP_BGS    = { saved:'#f0f0f8', applying:'#e8f0fe', applied:'#e6f4ea', docs_pass:'#e0f7fa', interview:'#fff3e0', offer:'#e8f5e9', rejected:'#fce8e6' };
const APP_ORDER  = ['interview','docs_pass','applied','applying','saved','offer','rejected'];

let _apps = {};
let _appFilter = '';

async function loadApplications() {
  if (!window.DB_ENABLED) return;
  try {
    const r = await fetch('/api/applications');
    const d = await r.json();
    _apps = {};
    (d.applications || []).forEach(a => { _apps[a.job_key] = a; });
  } catch { _apps = {}; }
  markAppRows();
  updAC();
}

function updAC() {
  const el = document.getElementById('ac');
  if (el) el.textContent = Object.keys(_apps).length;
}

function colorAppSelect(sel, status) {
  sel.style.color      = status ? APP_COLORS[status] : '';
  sel.style.background = status ? APP_BGS[status]    : '';
  sel.style.borderColor= status ? APP_COLORS[status] : '';
  sel.style.fontWeight = status ? '600' : '';
}

function markAppRows() {
  document.querySelectorAll('.jr').forEach(r => {
    const a = _apps[r.dataset.id];
    const sel = r.querySelector('.app-sel');
    if (!sel) return;
    sel.value = a ? a.status : '';
    colorAppSelect(sel, a ? a.status : '');
  });
}

async function setAppStatus(sel) {
  const row = sel.closest('.jr');
  if (!row) return;
  const jobKey = row.dataset.id;
  const status = sel.value;
  const job = (window.JOBS || []).find(j => (j.company + '|' + j.title) === jobKey);
  colorAppSelect(sel, status);
  try {
    await fetch('/api/applications', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ job_key: jobKey, status,
        company: job ? job.company : '', title: job ? job.title : '',
        link: job ? job.link : '', site: job ? job.site : '' }),
    });
    if (status) _apps[jobKey] = { job_key: jobKey, status, company: job?.company||'', title: job?.title||'', link: job?.link||'', site: job?.site||'' };
    else delete _apps[jobKey];
    updAC();
  } catch { alert('저장 실패'); }
}

function renderAppPanel() {
  const sumEl  = document.getElementById('app-summary');
  const listEl = document.getElementById('app-list');
  if (!sumEl || !listEl) return;

  const apps   = Object.values(_apps);
  const counts = {};
  apps.forEach(a => { counts[a.status] = (counts[a.status] || 0) + 1; });

  // 요약 카드
  sumEl.innerHTML =
    `<div class="app-sum-card ${_appFilter==='' ? 'active' : ''}" onclick="filterApp('')" style="--acolor:#1a1a2e">
       <b>${apps.length}</b><span>전체</span>
     </div>` +
    APP_ORDER.map(s =>
      `<div class="app-sum-card ${_appFilter===s ? 'active' : ''}" onclick="filterApp('${s}')" style="--acolor:${APP_COLORS[s]}">
         <b>${counts[s]||0}</b><span>${APP_LABELS[s]}</span>
       </div>`
    ).join('');

  // 목록
  let filtered = apps;
  if (_appFilter) filtered = apps.filter(a => a.status === _appFilter);
  filtered.sort((a,b) => APP_ORDER.indexOf(a.status) - APP_ORDER.indexOf(b.status));

  if (!filtered.length) {
    listEl.innerHTML = '<div class="empty">추적 중인 공고가 없습니다</div>';
    return;
  }

  const groups = {};
  filtered.forEach(a => { (groups[a.status] = groups[a.status] || []).push(a); });

  listEl.innerHTML = APP_ORDER.filter(s => groups[s]).map(s => {
    const c = APP_COLORS[s];
    const rows = groups[s].map(a => {
      const titleEsc = (a.title||a.job_key).replace(/</g,'&lt;').replace(/"/g,'&quot;');
      const coEsc    = (a.company||'').replace(/</g,'&lt;');
      const keyEsc   = a.job_key.replace(/\\/g,'\\\\').replace(/'/g,"\\'");
      const noteId   = 'anotes-' + btoa(unescape(encodeURIComponent(a.job_key))).replace(/[^a-zA-Z0-9]/g,'').slice(0,20);
      const notesEsc = (a.notes||'').replace(/</g,'&lt;').replace(/"/g,'&quot;');
      const optHtml  = Object.entries(APP_LABELS).map(([v,l]) =>
        `<option value="${v}" ${v===a.status?'selected':''}>${l}</option>`).join('');
      return `<div class="app-row">
        <div class="app-row-info">
          <a href="${a.link||'#'}" target="_blank" class="app-row-title">${titleEsc}</a>
          <span class="app-row-co">${coEsc}${a.site ? ' · '+a.site : ''}</span>
        </div>
        <select class="app-inline-sel" onchange="changeApp(this,'${keyEsc}')"
                style="border:1px solid ${c};color:${c};background:${APP_BGS[s]}">${optHtml}</select>
        <button class="app-note-btn ${a.notes ? 'has-note' : ''}" onclick="toggleAppNotes('${keyEsc}')" title="메모">📝</button>
        <button class="app-del" onclick="delApp('${keyEsc}')" title="삭제">✕</button>
      </div>
      <div class="app-notes-wrap" id="${noteId}" style="display:none">
        <textarea class="app-notes-ta" placeholder="면접 후기, 담당자 연락처, 연봉 협상 메모 등..."
                  oninput="scheduleNotesSave('${keyEsc}',this)">${notesEsc}</textarea>
      </div>`;
    }).join('');
    return `<div class="app-group">
      <div class="app-group-hd" style="color:${c}">● ${APP_LABELS[s]} <span style="font-size:11px;color:var(--text-dim)">${groups[s].length}건</span></div>
      ${rows}
    </div>`;
  }).join('');
}

function filterApp(status) {
  _appFilter = status;
  renderAppPanel();
}

async function changeApp(sel, jobKey) {
  const status = sel.value;
  try {
    await fetch('/api/applications', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ job_key: jobKey, status }),
    });
    if (_apps[jobKey]) _apps[jobKey].status = status;
    markAppRows(); updAC(); renderAppPanel();
  } catch { alert('저장 실패'); }
}

let _noteTimers = {};
function toggleAppNotes(jobKey) {
  const el = document.getElementById('anotes-' + btoa(unescape(encodeURIComponent(jobKey))).replace(/[^a-zA-Z0-9]/g,'').slice(0,20));
  if (!el) return;
  el.style.display = el.style.display === 'none' ? 'block' : 'none';
  if (el.style.display === 'block') el.querySelector('textarea')?.focus();
}

function scheduleNotesSave(jobKey, ta) {
  clearTimeout(_noteTimers[jobKey]);
  _noteTimers[jobKey] = setTimeout(async () => {
    try {
      await fetch('/api/applications', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ job_key: jobKey, notes: ta.value }),
      });
      if (_apps[jobKey]) _apps[jobKey].notes = ta.value;
    } catch {}
  }, 800);
}

async function delApp(jobKey) {
  try {
    await fetch('/api/applications', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ job_key: jobKey, status: '' }),
    });
    delete _apps[jobKey];
    markAppRows(); updAC(); renderAppPanel();
  } catch { alert('삭제 실패'); }
}

// ── Job detail modal ─────────────────────────────────────────────
async function openJobDetail(idx) {
  const job = window.JOBS?.[idx];
  if (!job) return;
  let modal = document.getElementById('jd-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'jd-modal';
    modal.className = 'jd-overlay';
    modal.innerHTML = `
      <div class="jd-box">
        <div class="jd-head">
          <div>
            <strong id="jd-title"></strong>
            <span id="jd-sub"></span>
          </div>
          <button onclick="closeJobDetail()">✕</button>
        </div>
        <div id="jd-body" class="jd-body"></div>
        <div class="jd-actions">
          <a id="jd-link" href="#" target="_blank">원문 보기</a>
          <button onclick="closeJobDetail()">닫기</button>
        </div>
      </div>`;
    document.body.appendChild(modal);
    modal.addEventListener('click', e => { if (e.target === modal) closeJobDetail(); });
  }
  document.getElementById('jd-title').textContent = job.title || '공고 상세';
  document.getElementById('jd-sub').textContent = `${job.company || ''}${job.site ? ' · ' + job.site : ''}`;
  document.getElementById('jd-link').href = job.link || '#';
  const body = document.getElementById('jd-body');
  body.innerHTML = '<div class="jd-loading">공고 내용을 불러오는 중입니다...</div>';
  modal.style.display = 'flex';
  try {
    const resp = await fetch('/api/job-detail', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job }),
    });
    const d = await resp.json();
    if (d.error) {
      body.innerHTML = `<span style="color:#e94560">${escHtml(d.error)}</span>`;
      return;
    }
    body.innerHTML = `<p>${escHtml(d.text).replace(/\n/g, '<br>')}</p>`;
  } catch {
    body.innerHTML = '<span style="color:#e94560">네트워크 오류</span>';
  }
}

function closeJobDetail() {
  const modal = document.getElementById('jd-modal');
  if (modal) modal.style.display = 'none';
}

// ── Keyword Trend ─────────────────────────────────────────────────
function renderTrend() {
  if (!window.JOBS || !window.JOBS.length) return;
  const counts = {};
  window.JOBS.forEach(j => {
    if (!j.stacks) return;
    j.stacks.split(/[,、·]/).map(s => s.trim()).filter(s => s.length >= 2 && s.length <= 30).forEach(s => {
      counts[s] = (counts[s]||0) + 1;
    });
  });
  const top = Object.entries(counts).sort((a,b) => b[1]-a[1]).slice(0, 12);
  if (top.length < 3) return;
  const el = document.getElementById('trend-bar');
  if (!el) return;
  const max = top[0][1];
  el.innerHTML = '<span class="trend-lbl">📈 자주 보이는 스택</span>' +
    top.map(([skill, cnt]) =>
      `<span class="trend-chip" title="${cnt}건" style="opacity:${(0.5 + 0.5*cnt/max).toFixed(2)}"
             onclick="document.getElementById('qi').value='${skill.replace(/'/g,'').replace(/"/g,'')}'">` +
      `${skill}<b>${cnt}</b></span>`
    ).join('');
  el.style.display = 'flex';
}

// ── Tabs ─────────────────────────────────────────────────────────
function switchTab(t) {
  const isApp = t === 'app';
  document.getElementById('ta').classList.toggle('on', t === 'all');
  document.getElementById('tb').classList.toggle('on', t === 'bm');
  const tc = document.getElementById('tc');
  if (tc) tc.classList.toggle('on', isApp);

  const tw = document.querySelector('.tw');
  const ap = document.getElementById('app-panel');
  if (tw) tw.style.display = isApp ? 'none' : '';
  if (ap) { ap.style.display = isApp ? 'block' : 'none'; if (isApp) { _appFilter=''; renderAppPanel(); } }

  if (!isApp) {
    document.getElementById('fb').checked = t === 'bm';
    filt();
  }
}

// ── Filters ──────────────────────────────────────────────────────
function filt() {
  const dd    = parseInt(document.getElementById('fd')?.value) || 0;
  const locs  = [...document.querySelectorAll('.fl-cb:checked')].map(c => c.value);
  const cars  = [...document.querySelectorAll('.fc-cb:checked')].map(c => c.value);
  const yEl   = document.getElementById('fy');
  const yMax  = yEl ? parseInt(yEl.value) : 11;
  const yLimit = (yEl && yMax <= 10) ? yMax : null;  // 11 = 제한 없음
  const yLabel = document.getElementById('fy-val');
  if (yLabel) yLabel.textContent = (yLimit === null) ? '제한 없음' : (yLimit + '년 이내');
  const sort  = document.getElementById('fs')?.value || '';
  const aiOnly = document.getElementById('fai')?.checked;
  const bmOnly = document.getElementById('fb')?.checked;
  const hideExpired = document.getElementById('fx')?.checked;
  const b = gb();
  const rows = Array.from(document.querySelectorAll('.jr'));

  rows.forEach(r => {
    const rd = parseInt(r.dataset.dday), rg = r.dataset.region || '', rc = r.dataset.career || '', rs = r.dataset.score;
    let show = true;
    if (dd && (isNaN(rd) || rd > dd || rd < 0)) show = false;
    if (hideExpired && !isNaN(rd) && rd < 0) show = false;  // 마감(dday<0)만 숨김, 상시(9999) 유지
    if (locs.length && !locs.includes(rg)) show = false;
    if (cars.length && !cars.includes(rc)) show = false;
    if (yLimit !== null) {
      const ryRaw = r.dataset.years;
      // 연차 미표기 공고는 항상 표시(판단 불가). 표기된 경우만 상한 적용.
      if (ryRaw !== '' && ryRaw != null) {
        const ry = parseInt(ryRaw);
        if (!isNaN(ry) && ry > yLimit) show = false;
      }
    }
    if (aiOnly && !rs) show = false;
    if (bmOnly && !b.includes(r.dataset.id)) show = false;
    r.style.display = show ? '' : 'none';
  });

  if (sort) {
    const tbody = document.getElementById('tb-body');
    const vis = rows.filter(r => r.style.display !== 'none');
    vis.sort((a, z) =>
      sort === 'dday'  ? parseInt(a.dataset.dday) - parseInt(z.dataset.dday) :
      sort === 'score' ? parseInt(z.dataset.score || 0) - parseInt(a.dataset.score || 0) :
      (z.dataset.isnew === 'y') - (a.dataset.isnew === 'y')
    );
    vis.forEach(r => tbody.appendChild(r));
  }
  let n = 1; rows.forEach(r => { if (r.style.display !== 'none') r.cells[0].textContent = n++; });
}
function clrF() {
  ['fd', 'fs'].forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
  document.querySelectorAll('.fl-cb, .fc-cb').forEach(c => { c.checked = false; });
  const fy = document.getElementById('fy'); if (fy) fy.value = fy.max;
  document.getElementById('fb').checked = false;
  const fai = document.getElementById('fai'); if (fai) fai.checked = false;
  const fx = document.getElementById('fx'); if (fx) fx.checked = false;
  filt();
}

// ── Draft drawer ─────────────────────────────────────────────────
const DEFAULT_QS = [
  '1분 자기소개를 해주세요.',
  '지원동기를 말씀해주세요.',
  '본인의 강점과 약점을 설명해주세요.',
  '입사 후 포부를 말씀해주세요.',
  '직무 관련 경험이나 역량을 설명해주세요.',
];
const STYLE_KEY = 'jh_style_sample';
let _dpJob = null;

function openDraft(idx) {
  _dpJob = window.JOBS[idx];
  if (!_dpJob) return;
  document.getElementById('dp-title').textContent = _dpJob.company + ' 자소서 초안';
  document.getElementById('dp-job-info').innerHTML =
    `<strong>${_dpJob.title}</strong><span>${_dpJob.company}${_dpJob.stacks ? ' · ' + _dpJob.stacks : ''}</span>`;
  const ql = document.getElementById('dp-qlist');
  ql.innerHTML = '';
  DEFAULT_QS.forEach(q => addQ(q));
  // 저장된 초안 복원
  const jobId = _dpJob.company + '|' + _dpJob.title;
  const saved = _drafts[jobId];
  const out = document.getElementById('dp-out');
  const savebtn = document.getElementById('dp-save');
  const ivOut = document.getElementById('iv-out');
  const crOut = document.getElementById('cr-out');
  if (saved) {
    out.textContent = saved;
    out.style.display = 'block';
    document.getElementById('dp-copy').style.display = 'inline-block';
    if (savebtn) { savebtn.style.display = 'inline-block'; savebtn.textContent = '💾 저장됨'; }
  } else {
    out.style.display = 'none';
    out.textContent = '';
    document.getElementById('dp-copy').style.display = 'none';
    if (savebtn) savebtn.style.display = 'none';
  }
  if (ivOut) {
    ivOut.style.display = 'none';
    ivOut.innerHTML = '';
  }
  if (crOut) {
    crOut.style.display = 'none';
    crOut.innerHTML = '';
  }
  const styleTa = document.getElementById('dp-style-sample');
  if (styleTa) styleTa.value = localStorage.getItem(STYLE_KEY) || '';
  document.getElementById('dp').classList.add('open');
}
function closeDraft() { document.getElementById('dp').classList.remove('open'); }
function addQ(txt = '') {
  const ql = document.getElementById('dp-qlist');
  const d = document.createElement('div'); d.className = 'dp-q';
  d.innerHTML = `<textarea rows="2">${txt}</textarea><button onclick="this.parentElement.remove()">✕</button>`;
  ql.appendChild(d);
}
async function autoQuestions() {
  if (!_dpJob) return;
  const btn = document.getElementById('dp-autoq');
  btn.disabled = true; btn.textContent = '분석 중...';
  try {
    const resp = await fetch('/api/draft/questions', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job: _dpJob }),
    });
    const d = await resp.json();
    if (d.error) { alert('오류: ' + d.error); return; }
    const ql = document.getElementById('dp-qlist');
    ql.innerHTML = '';
    (d.questions || []).forEach(q => addQ(q));
  } catch { alert('네트워크 오류'); }
  finally { btn.disabled = false; btn.textContent = '🔍 문항 자동 생성'; }
}

async function genDraft() {
  const resume = document.getElementById('rv')?.value.trim();
  if (!resume) { alert('이력서를 먼저 입력하세요.'); return; }
  const qs = [...document.querySelectorAll('#dp-qlist textarea')].map(t => t.value.trim()).filter(Boolean);
  if (!qs.length) { alert('문항을 입력하세요.'); return; }
  const styleSample = document.getElementById('dp-style-sample')?.value.trim() || '';
  if (styleSample) localStorage.setItem(STYLE_KEY, styleSample);
  const btn = document.getElementById('dp-gen');
  btn.disabled = true; btn.textContent = '생성 중...';
  try {
    const resp = await fetch('/api/draft', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ resume, job: _dpJob, questions: qs, style_sample: styleSample }),
    });
    const d = await resp.json();
    if (d.error) { alert('오류: ' + d.error); return; }
    const out = document.getElementById('dp-out');
    out.textContent = d.draft; out.style.display = 'block';
    document.getElementById('dp-copy').style.display = 'inline-block';
    const savebtn = document.getElementById('dp-save');
    if (savebtn) { savebtn.style.display = 'inline-block'; savebtn.textContent = '💾 저장'; }
  } catch { alert('네트워크 오류'); }
  finally { btn.disabled = false; btn.textContent = '✨ 초안 생성'; }
}
function copyDraft() {
  navigator.clipboard.writeText(document.getElementById('dp-out').textContent);
  const b = document.getElementById('dp-copy'); b.textContent = '✓ 복사됨';
  setTimeout(() => b.textContent = '📋 복사', 1500);
}
async function saveDraft() {
  if (!_dpJob) return;
  const text = document.getElementById('dp-out').textContent.trim();
  if (!text) return;
  const jobId = _dpJob.company + '|' + _dpJob.title;
  const btn = document.getElementById('dp-save');
  btn.disabled = true; btn.textContent = '저장 중...';
  await saveDraftToServer(jobId, text);
  btn.disabled = false; btn.textContent = '✓ 저장됨';
  setTimeout(() => { btn.textContent = '💾 저장'; }, 2000);
}

async function critiqueDraft() {
  if (!_dpJob) return;
  const resume = document.getElementById('rv')?.value.trim();
  if (!resume) { alert('이력서를 먼저 입력하세요.'); return; }
  const draft = document.getElementById('dp-out')?.textContent.trim();
  if (!draft) { alert('먼저 자소서 초안을 생성하거나 저장된 초안을 열어주세요.'); return; }
  const btn = document.getElementById('cr-gen');
  const out = document.getElementById('cr-out');
  btn.disabled = true; btn.textContent = '첨삭 중...';
  if (out) {
    out.style.display = 'block';
    out.innerHTML = '<div class="iv-loading">초안을 읽고 첨삭하는 중입니다...</div>';
  }
  try {
    const resp = await fetch('/api/draft/critique', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ resume, job: _dpJob, draft }),
    });
    const d = await resp.json();
    if (d.error) {
      if (out) out.innerHTML = `<span style="color:#e94560">${d.error}</span>`;
      return;
    }
    if (out) out.innerHTML = d.html || '';
  } catch {
    if (out) out.innerHTML = '<span style="color:#e94560">네트워크 오류</span>';
  } finally {
    btn.disabled = false; btn.textContent = '✏️ 첨삭';
  }
}

async function genInterviewQuestions() {
  if (!_dpJob) return;
  const resume = document.getElementById('rv')?.value.trim();
  if (!resume) { alert('이력서를 먼저 입력하세요.'); return; }
  const btn = document.getElementById('iv-gen');
  const out = document.getElementById('iv-out');
  btn.disabled = true; btn.textContent = '생성 중...';
  if (out) {
    out.style.display = 'block';
    out.innerHTML = '<div class="iv-loading">면접 질문을 준비하는 중입니다...</div>';
  }
  try {
    const resp = await fetch('/api/interview-questions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ resume, job: _dpJob }),
    });
    const d = await resp.json();
    if (d.error) {
      if (out) out.innerHTML = `<span style="color:#e94560">${d.error}</span>`;
      return;
    }
    if (out) out.innerHTML = d.html || '';
  } catch {
    if (out) out.innerHTML = '<span style="color:#e94560">네트워크 오류</span>';
  } finally {
    btn.disabled = false; btn.textContent = '🎤 면접 질문';
  }
}

// ── Question Library ─────────────────────────────────────────────
const Q_LIBRARY = [
  // 자기소개 · 지원동기
  { c:'자기소개·지원동기', q:'1분 자기소개를 해주세요.' },
  { c:'자기소개·지원동기', q:'이 회사에 지원하게 된 동기를 구체적으로 설명해주세요.' },
  { c:'자기소개·지원동기', q:'이 직무를 선택하게 된 이유가 무엇인가요?' },
  { c:'자기소개·지원동기', q:'10년 후 본인의 모습을 설명해주세요.' },
  { c:'자기소개·지원동기', q:'타사도 지원했나요? 왜 우리 회사를 선택했나요?' },
  { c:'자기소개·지원동기', q:'본인을 한 단어로 표현한다면 무엇인가요? 그 이유는?' },
  // 역량 · 경험
  { c:'역량·경험', q:'가장 도전적이었던 프로젝트 경험을 말씀해주세요.' },
  { c:'역량·경험', q:'성과를 위해 초과 노력을 기울인 경험이 있나요?' },
  { c:'역량·경험', q:'실패 경험과 그로부터 배운 점을 말씀해주세요.' },
  { c:'역량·경험', q:'짧은 기간에 새로운 기술을 습득했던 경험이 있나요?' },
  { c:'역량·경험', q:'본인이 주도적으로 문제를 발견하고 해결한 경험을 말씀해주세요.' },
  { c:'역량·경험', q:'데이터나 근거를 바탕으로 의사결정을 내린 경험을 설명해주세요.' },
  { c:'역량·경험', q:'동시에 여러 업무를 처리해야 했던 경험과 대처법을 설명해주세요.' },
  { c:'역량·경험', q:'고객 또는 사용자 피드백을 반영해 개선한 사례가 있나요?' },
  // 팀워크 · 협업
  { c:'팀워크·협업', q:'팀 내 갈등을 해결했던 경험을 구체적으로 설명하세요.' },
  { c:'팀워크·협업', q:'리더십을 발휘했던 경험을 설명해주세요.' },
  { c:'팀워크·협업', q:'다양한 배경의 팀원과 협업한 경험이 있나요?' },
  { c:'팀워크·협업', q:'팀의 성과를 위해 개인 이익을 양보한 경험이 있나요?' },
  { c:'팀워크·협업', q:'원격/비대면 환경에서 협업한 경험을 말씀해주세요.' },
  { c:'팀워크·협업', q:'비전공 부서(기획, 디자인, 영업 등)와 협업한 경험이 있나요?' },
  // 직무 적합성
  { c:'직무 적합성', q:'본인의 전공/경험이 이 직무에 어떻게 도움이 되나요?' },
  { c:'직무 적합성', q:'보유한 기술 스택과 실무 경험을 구체적으로 설명해주세요.' },
  { c:'직무 적합성', q:'이 직무에서 가장 중요한 역량은 무엇이라고 생각하나요?' },
  { c:'직무 적합성', q:'이 업계의 최신 트렌드에 대해 어떻게 생각하시나요?' },
  { c:'직무 적합성', q:'포트폴리오/작업물 중 가장 자신 있는 것을 설명해주세요.' },
  { c:'직무 적합성', q:'이 직무에서 첫 3개월 안에 어떤 성과를 낼 수 있나요?' },
  // 강점 · 약점
  { c:'강점·약점', q:'본인의 가장 큰 강점 3가지를 말씀해주세요.' },
  { c:'강점·약점', q:'본인의 단점과 이를 극복하려는 노력을 설명해주세요.' },
  { c:'강점·약점', q:'동료들이 당신을 어떻게 평가하나요?' },
  { c:'강점·약점', q:'상사/교수에게 들은 긍정적인 피드백과 부정적인 피드백은?' },
  { c:'강점·약점', q:'스트레스 상황에서 어떻게 대처하나요?' },
  // 입사 후 포부
  { c:'입사 후 포부', q:'입사 후 3~6개월 내 이루고 싶은 목표가 있나요?' },
  { c:'입사 후 포부', q:'이 회사에서 장기적으로 어떤 가치를 만들고 싶으신가요?' },
  { c:'입사 후 포부', q:'5년 뒤 이 회사에서 어떤 역할을 맡고 싶으신가요?' },
  { c:'입사 후 포부', q:'이 회사/서비스를 더 발전시키기 위한 아이디어가 있나요?' },
  // 상황 판단
  { c:'상황판단', q:'상사의 지시가 비효율적이라고 판단될 때 어떻게 하시겠습니까?' },
  { c:'상황판단', q:'마감 기한이 촉박한 상황에서 어떻게 우선순위를 정하나요?' },
  { c:'상황판단', q:'불확실한 상황에서 결정을 내려야 할 때 어떻게 접근하나요?' },
  { c:'상황판단', q:'본인이 옳다고 생각하는 방향과 팀의 방향이 다를 때 어떻게 하나요?' },
  { c:'상황판단', q:'급격한 방향 전환이 필요할 때 어떻게 대응하나요?' },
  // 기타
  { c:'기타', q:'지원 전 우리 회사/서비스를 얼마나 사용해봤나요? 개선점은?' },
  { c:'기타', q:'최근 읽은 책/아티클 중 인상 깊었던 것을 소개해주세요.' },
  { c:'기타', q:'개인 프로젝트나 사이드 프로젝트를 진행한 경험이 있나요?' },
  { c:'기타', q:'연봉 외에 직장을 선택할 때 중요시하는 요소는 무엇인가요?' },
];

function openQLibrary() {
  let modal = document.getElementById('qlib-modal');
  if (!modal) {
    const cats = [...new Set(Q_LIBRARY.map(q => q.c))];
    const catHtml = cats.map(cat => {
      const qs = Q_LIBRARY.filter(q => q.c === cat);
      return `<div class="qlib-cat">
        <div class="qlib-cat-hd">${cat}</div>
        ${qs.map(({q}) => `<div class="qlib-item" onclick="addQFromLib(this)">${q}</div>`).join('')}
      </div>`;
    }).join('');
    modal = document.createElement('div');
    modal.id = 'qlib-modal';
    modal.className = 'qlib-overlay';
    modal.innerHTML = `
      <div class="qlib-box">
        <div class="qlib-head">
          <span>📚 자소서 문항 라이브러리 <small style="color:#aaa;font-weight:400">(클릭하면 추가)</small></span>
          <button onclick="document.getElementById('qlib-modal').remove()" style="background:none;border:none;color:#aaa;font-size:20px;cursor:pointer;line-height:1">✕</button>
        </div>
        <div class="qlib-body">${catHtml}</div>
      </div>`;
    document.body.appendChild(modal);
    modal.addEventListener('click', e => { if (e.target === modal) modal.remove(); });
  } else {
    modal.style.display = 'flex';
  }
}

function addQFromLib(el) {
  addQ(el.textContent);
  el.style.background = '#e6f4ea';
  el.style.color = '#34a853';
  setTimeout(() => { el.style.background = ''; el.style.color = ''; }, 1200);
}

// ── Resume / Analysis / Matching ─────────────────────────────────
function renderStructured(s) {
  if (!s || !Object.keys(s).length) return;
  const el = document.getElementById('rv-structured');
  if (!el) return;
  const rows = [];
  if (s['이름'])        rows.push(`<b>이름</b> ${s['이름']}`);
  if (s['희망직군'])    rows.push(`<b>희망직군</b> ${s['희망직군']}`);
  if (s['경력'])        rows.push(`<b>경력</b> ${s['경력']}`);
  if (s['학력'])        rows.push(`<b>학력</b> ${s['학력']}`);
  if (s['기술스택']?.length) rows.push(`<b>기술스택</b> ${s['기술스택'].join(', ')}`);
  if (s['자격증']?.length)   rows.push(`<b>자격증</b> ${s['자격증'].join(', ')}`);
  if (s['언어']?.length)     rows.push(`<b>언어</b> ${s['언어'].join(', ')}`);
  if (s['기타'])        rows.push(`<b>기타</b> ${s['기타']}`);
  if (!rows.length) return;
  el.innerHTML = '<div style="color:#888;font-size:11px;margin-bottom:6px">📋 구조화된 이력서</div>' + rows.map(r => `<div style="margin-bottom:3px">${r}</div>`).join('');
  el.style.display = 'block';
}

function bindKwChips(container) {
  container.querySelectorAll('.kw-chip').forEach(el => {
    el.style.cssText = 'display:inline-block;padding:3px 10px;background:#e8f0fe;color:#1a73e8;border-radius:12px;margin:2px;cursor:pointer;font-size:12px;font-weight:600';
    el.onclick = () => { document.getElementById('qi').value = el.textContent; go(); };
  });
}

async function analyzeR() {
  const resume = document.getElementById('rv')?.value.trim();
  if (!resume) { alert('이력서를 먼저 입력하세요.'); return; }
  const btn = document.getElementById('analyze-btn');
  btn.disabled = true; btn.textContent = '분석 중...';
  const out = document.getElementById('analyze-out');
  out.style.display = 'none';
  try {
    const resp = await fetch('/api/analyze', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ resume }) });
    const d = await resp.json();
    if (d.error) { out.innerHTML = `<span style="color:#e94560">${d.error}</span>`; out.style.display = 'block'; return; }
    out.innerHTML = d.html || ''; out.style.display = 'block';
    bindKwChips(out);
  } catch { out.innerHTML = '<span style="color:#e94560">네트워크 오류</span>'; out.style.display = 'block'; }
  finally { btn.disabled = false; btn.textContent = '이력서 분석'; }
}

async function matchJobs() {
  const resume = document.getElementById('rv')?.value.trim();
  if (!resume) { alert('이력서를 먼저 입력/저장하세요.'); return; }
  if (!window.JOBS || !window.JOBS.length) { alert('먼저 공고를 검색하세요.'); return; }
  const btn = document.getElementById('match-btn');
  btn.disabled = true; btn.textContent = '분석 중...';
  try {
    const resp = await fetch('/api/match', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ resume, jobs: window.JOBS }) });
    const data = await resp.json();
    if (data.error) { alert('오류: ' + data.error); return; }
    data.scores.forEach(({ idx, score, reason }) => {
      const rows = document.querySelectorAll('.jr');
      if (!rows[idx]) return;
      rows[idx].dataset.score = score;
      const jt = rows[idx].querySelector('.jt');
      if (jt) {
        jt.querySelectorAll('.sc-badge').forEach(e => e.remove());
        const b = document.createElement('span');
        b.className = 'sc-badge'; b.title = reason; b.textContent = score + '%';
        const c  = score >= 70 ? '#34a853' : score >= 50 ? '#f57c00' : '#e94560';
        const bg = score >= 70 ? '#e6f4ea' : score >= 50 ? '#fff3e0' : '#fce8e6';
        b.style.cssText = `display:inline-block;font-size:10px;padding:1px 7px;border-radius:10px;margin-left:6px;font-weight:700;background:${bg};color:${c};cursor:default`;
        jt.querySelector('a').insertAdjacentElement('afterend', b);
      }
    });
    const fs = document.getElementById('fs');
    if (fs && ![...fs.options].find(o => o.value === 'score')) {
      const o = document.createElement('option'); o.value = 'score'; o.textContent = '매칭순'; fs.appendChild(o);
    }
  } catch { alert('네트워크 오류'); }
  finally { btn.disabled = false; btn.textContent = 'AI 매칭'; }
}

async function saveR() {
  const v = document.getElementById('rv')?.value.trim();
  if (!v) return;
  try {
    const resp = await fetch('/api/resume', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content: v }) });
    const d = await resp.json();
    if (d.structured) renderStructured(d.structured);
    alert('이력서 저장 완료');
  } catch { alert('저장 실패'); }
}

// ── Resume version management ─────────────────────────────────────
async function saveVersion() {
  const content = document.getElementById('rv')?.value.trim();
  if (!content) { alert('이력서를 먼저 입력하세요.'); return; }
  const label = prompt('버전 메모 (선택, 예: "네이버 지원용")') ?? null;
  if (label === null) return;  // 취소
  const btn = document.getElementById('ver-save-btn');
  if (btn) { btn.disabled = true; btn.textContent = '저장 중...'; }
  try {
    await fetch('/api/resume/versions', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content, label }),
    });
    await loadVersions();
    if (btn) btn.textContent = '✓ 저장됨';
    setTimeout(() => { if (btn) { btn.disabled = false; btn.textContent = '📌 버전 저장'; } }, 1500);
  } catch { alert('저장 실패'); if (btn) { btn.disabled = false; btn.textContent = '📌 버전 저장'; } }
}

async function loadVersions() {
  try {
    const r = await fetch('/api/resume/versions');
    const d = await r.json();
    renderVersions(d.versions || []);
  } catch {}
}

function renderVersions(versions) {
  const el = document.getElementById('ver-list');
  if (!el) return;
  if (!versions.length) { el.style.display = 'none'; return; }
  el.style.display = 'block';
  el.innerHTML = '<div style="font-size:11px;color:#888;margin-bottom:6px">📂 저장된 버전 (최신 10개)</div>' +
    versions.map((v, i) => {
      const dt = v.saved_at ? v.saved_at.replace('T', ' ').slice(0, 16) : '';
      const lbl = v.label ? ` · ${v.label}` : '';
      return `<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">
        <span style="font-size:12px;color:#555;flex:1">${dt}${lbl}</span>
        <button onclick="showDiff(${i})"
          style="font-size:11px;padding:2px 8px;background:#e8f0fe;color:#1a73e8;border:1px solid #c5d8f8;border-radius:4px;cursor:pointer">
          비교
        </button>
        <button onclick="restoreVersion(${i})"
          style="font-size:11px;padding:2px 8px;background:#f0f0f0;border:1px solid #ccc;border-radius:4px;cursor:pointer">
          복원
        </button>
      </div>`;
    }).join('');
  el._versions = versions;
}

function restoreVersion(idx) {
  const el = document.getElementById('ver-list');
  const versions = el?._versions;
  if (!versions || !versions[idx]) return;
  const v = versions[idx];
  if (!confirm(`"${v.saved_at?.slice(0,10) || '?'} ${v.label || ''}" 버전으로 복원하시겠습니까?\n현재 내용은 덮어씁니다.`)) return;
  const rv = document.getElementById('rv');
  if (rv) rv.value = v.content;
}

// ── 버전 diff ────────────────────────────────────────────────────
function _computeLineDiff(oldText, newText) {
  const A = oldText.split('\n'), B = newText.split('\n');
  const m = A.length, n = B.length;
  // LCS 테이블
  const dp = Array.from({length: m + 1}, () => new Int32Array(n + 1));
  for (let i = 1; i <= m; i++)
    for (let j = 1; j <= n; j++)
      dp[i][j] = A[i-1] === B[j-1] ? dp[i-1][j-1] + 1 : Math.max(dp[i-1][j], dp[i][j-1]);
  // 역추적
  const ops = [];
  let i = m, j = n;
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && A[i-1] === B[j-1]) { ops.unshift({t:'=', s:A[i-1]}); i--; j--; }
    else if (j > 0 && (i === 0 || dp[i][j-1] >= dp[i-1][j])) { ops.unshift({t:'+', s:B[j-1]}); j--; }
    else { ops.unshift({t:'-', s:A[i-1]}); i--; }
  }
  return ops;
}

function showDiff(idx) {
  const el = document.getElementById('ver-list');
  const versions = el?._versions;
  if (!versions || !versions[idx]) return;
  const oldContent = versions[idx].content;
  const newContent = document.getElementById('rv')?.value || '';
  const ops = _computeLineDiff(oldContent, newContent);
  const label = versions[idx].label ? ` (${versions[idx].label})` : '';
  const dt = (versions[idx].saved_at || '').slice(0, 10);

  const lines = ops.map(op => {
    const esc = op.s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    if (op.t === '+') return `<div class="diff-add">+ ${esc}</div>`;
    if (op.t === '-') return `<div class="diff-del">- ${esc}</div>`;
    return `<div class="diff-ctx">  ${esc}</div>`;
  }).join('');

  let modal = document.getElementById('diff-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'diff-modal';
    modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:500;display:flex;align-items:center;justify-content:center';
    modal.innerHTML = `<div style="background:var(--surface);border-radius:10px;width:700px;max-width:95vw;max-height:80vh;display:flex;flex-direction:column;overflow:hidden;box-shadow:0 8px 32px rgba(0,0,0,.4)">
      <div id="diff-head" style="background:#1a1a2e;color:#fff;padding:12px 16px;display:flex;justify-content:space-between;align-items:center;flex-shrink:0">
        <span id="diff-title" style="font-size:13px;font-weight:700"></span>
        <button onclick="document.getElementById('diff-modal').remove()" style="background:none;border:none;color:#aaa;font-size:20px;cursor:pointer;line-height:1">✕</button>
      </div>
      <div id="diff-legend" style="padding:8px 16px;font-size:11px;display:flex;gap:16px;background:var(--surface-2);border-bottom:1px solid var(--border);flex-shrink:0">
        <span style="color:#6fcf97">+ 현재 (추가)</span>
        <span style="color:#eb5757">- 저장 버전 (삭제)</span>
      </div>
      <div id="diff-body" style="flex:1;overflow-y:auto;font-family:monospace;font-size:12px;line-height:1.6;padding:8px 0;background:var(--surface)"></div>
    </div>`;
    document.body.appendChild(modal);
    modal.addEventListener('click', e => { if (e.target === modal) modal.remove(); });
  }
  document.getElementById('diff-title').textContent = `${dt}${label} ↔ 현재 편집 중`;
  document.getElementById('diff-body').innerHTML = lines || '<div style="padding:16px;color:#bbb;text-align:center">변경사항 없음</div>';
}

// ── Init ─────────────────────────────────────────────────────────
window.addEventListener('load', async () => {
  renderPins();
  try { const r = await fetch('/api/bookmarks'); const d = await r.json(); _bm = d.job_ids || []; } catch { _bm = []; }
  initBM(); updBC();
  await loadDrafts();
  await loadVersions();
  await loadApplications();
  renderTrend();

  try {
    const r = await fetch('/api/resume'); const d = await r.json();
    if (d.content && document.getElementById('rv')) document.getElementById('rv').value = d.content;
    if (d.structured) renderStructured(d.structured);
    if (d.analysis) {
      const out = document.getElementById('analyze-out');
      if (out) {
        const ts = d.analyzed_at ? `<div style="color:#bbb;font-size:11px;margin-bottom:8px">마지막 분석: ${d.analyzed_at.slice(0, 10)}</div>` : '';
        out.innerHTML = ts + d.analysis;
        out.style.display = 'block';
        bindKwChips(out);
      }
    }
  } catch {}

  const mp = document.getElementById('mp');
  if (mp) mp.style.display = '';
  const matchBtn = document.getElementById('match-btn');
  if (window.JOBS && window.JOBS.length > 0 && matchBtn) matchBtn.style.display = '';
});
