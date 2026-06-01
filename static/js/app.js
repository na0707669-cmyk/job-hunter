// ── History ──────────────────────────────────────────────────────
const HK = 'jh_h';
const gh = () => { try { return JSON.parse(localStorage.getItem(HK)) || []; } catch { return []; } };
const sh = v => localStorage.setItem(HK, JSON.stringify(v));

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

document.getElementById('qi').addEventListener('focus', renderH);
document.addEventListener('click', e => {
  if (!e.target.closest('.search-row')) document.getElementById('hist').style.display = 'none';
});

// ── Navigation ───────────────────────────────────────────────────
function go() {
  const q = document.getElementById('qi').value.trim();
  if (!q) return;
  addH(q);
  const sites = [...document.querySelectorAll('.site-cb:checked')].map(c => c.value).join(',');
  window.location.href = `/?q=${encodeURIComponent(q)}&size=${document.getElementById('sz').value}&sites=${encodeURIComponent(sites)}`;
}
document.getElementById('qi').addEventListener('keydown', e => { if (e.key === 'Enter') go(); });

function addAlso(term) {
  const u = new URL(window.location.href);
  const a = (u.searchParams.get('also') || '').split(',').filter(t => t);
  if (!a.includes(term)) a.push(term);
  u.searchParams.set('also', a.join(','));
  window.location.href = u.toString();
}
function removeAlso(term) {
  const u = new URL(window.location.href);
  const a = (u.searchParams.get('also') || '').split(',').filter(t => t && t !== term);
  if (a.length > 0) u.searchParams.set('also', a.join(','));
  else u.searchParams.delete('also');
  window.location.href = u.toString();
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

// ── Tabs ─────────────────────────────────────────────────────────
function switchTab(t) {
  document.getElementById('ta').classList.toggle('on', t === 'all');
  document.getElementById('tb').classList.toggle('on', t === 'bm');
  document.getElementById('fb').checked = t === 'bm';
  filt();
}

// ── Filters ──────────────────────────────────────────────────────
function filt() {
  const dd    = parseInt(document.getElementById('fd')?.value) || 0;
  const loc   = document.getElementById('fl')?.value || '';
  const car   = document.getElementById('fc')?.value || '';
  const sort  = document.getElementById('fs')?.value || '';
  const aiOnly = document.getElementById('fai')?.checked;
  const bmOnly = document.getElementById('fb')?.checked;
  const b = gb();
  const rows = Array.from(document.querySelectorAll('.jr'));

  rows.forEach(r => {
    const rd = parseInt(r.dataset.dday), rl = r.dataset.loc || '', rc = r.dataset.career || '', rs = r.dataset.score;
    let show = true;
    if (dd && (isNaN(rd) || rd > dd || rd < 0)) show = false;
    if (loc && !rl.includes(loc)) show = false;
    if (car && rc !== car) show = false;
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
  ['fd', 'fl', 'fc', 'fs'].forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
  document.getElementById('fb').checked = false;
  const fai = document.getElementById('fai'); if (fai) fai.checked = false;
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
  const btn = document.getElementById('dp-gen');
  btn.disabled = true; btn.textContent = '생성 중...';
  try {
    const resp = await fetch('/api/draft', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ resume, job: _dpJob, questions: qs }) });
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
    if (op.t === '+') return `<div style="background:#e6f4ea;color:#137333;padding:1px 8px">+ ${esc}</div>`;
    if (op.t === '-') return `<div style="background:#fce8e6;color:#c62828;padding:1px 8px">- ${esc}</div>`;
    return `<div style="color:#666;padding:1px 8px;opacity:.7">  ${esc}</div>`;
  }).join('');

  let modal = document.getElementById('diff-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'diff-modal';
    modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:500;display:flex;align-items:center;justify-content:center';
    modal.innerHTML = `<div style="background:#fff;border-radius:10px;width:700px;max-width:95vw;max-height:80vh;display:flex;flex-direction:column;overflow:hidden;box-shadow:0 8px 32px rgba(0,0,0,.2)">
      <div id="diff-head" style="background:#1a1a2e;color:#fff;padding:12px 16px;display:flex;justify-content:space-between;align-items:center;flex-shrink:0">
        <span id="diff-title" style="font-size:13px;font-weight:700"></span>
        <button onclick="document.getElementById('diff-modal').remove()" style="background:none;border:none;color:#aaa;font-size:20px;cursor:pointer;line-height:1">✕</button>
      </div>
      <div id="diff-legend" style="padding:8px 16px;font-size:11px;display:flex;gap:16px;background:#fafafa;border-bottom:1px solid #eee;flex-shrink:0">
        <span style="color:#137333">+ 현재 (추가)</span>
        <span style="color:#c62828">- 저장 버전 (삭제)</span>
      </div>
      <div id="diff-body" style="flex:1;overflow-y:auto;font-family:monospace;font-size:12px;line-height:1.6;padding:8px 0"></div>
    </div>`;
    document.body.appendChild(modal);
    modal.addEventListener('click', e => { if (e.target === modal) modal.remove(); });
  }
  document.getElementById('diff-title').textContent = `${dt}${label} ↔ 현재 편집 중`;
  document.getElementById('diff-body').innerHTML = lines || '<div style="padding:16px;color:#bbb;text-align:center">변경사항 없음</div>';
}

// ── Init ─────────────────────────────────────────────────────────
window.addEventListener('load', async () => {
  try { const r = await fetch('/api/bookmarks'); const d = await r.json(); _bm = d.job_ids || []; } catch { _bm = []; }
  initBM(); updBC();
  await loadDrafts();
  await loadVersions();

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
