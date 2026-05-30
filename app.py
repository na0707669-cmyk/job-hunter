from flask import Flask, request, render_template_string
from job_hunt import search_saramin, search_jobkorea, search_groupby, search_jasoseol, dedup

app = Flask(__name__)

SIZE_SITES = {
    "all":     ["자소설닷컴", "사람인", "잡코리아", "그룹바이"],
    "big":     ["자소설닷컴"],
    "corp":    ["사람인", "잡코리아"],
    "startup": ["그룹바이"],
}

HTML = """
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>공고 사냥</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, sans-serif; background: #f5f5f5; color: #222; }

  .top { background: #1a1a2e; color: #fff; padding: 20px 32px; display: flex; align-items: center; gap: 16px; }
  .top h1 { font-size: 18px; font-weight: 700; }

  form { display: flex; gap: 8px; flex: 1; max-width: 700px; margin-left: auto; }
  form input[type=text] {
    flex: 1; padding: 8px 12px; border: none; border-radius: 6px;
    font-size: 14px; outline: none;
  }
  form select {
    padding: 8px 10px; border: none; border-radius: 6px;
    font-size: 14px; background: #fff; cursor: pointer;
  }
  form button {
    padding: 8px 18px; background: #e94560; color: #fff;
    border: none; border-radius: 6px; font-size: 14px;
    cursor: pointer; font-weight: 600;
  }
  form button:hover { background: #c73652; }

  .meta { padding: 14px 32px; font-size: 13px; color: #666; }
  .meta b { color: #1a1a2e; }

  .tags { display: flex; gap: 8px; padding: 0 32px 12px; flex-wrap: wrap; }
  .tag {
    font-size: 12px; padding: 3px 10px; border-radius: 20px; border: 1px solid #ddd;
    background: #fff; cursor: pointer; color: #555;
  }
  .tag.자소설닷컴 { border-color: #7c3aed; color: #7c3aed; background: #ede9fe; }
  .tag.사람인   { border-color: #1a73e8; color: #1a73e8; background: #e8f0fe; }
  .tag.잡코리아 { border-color: #ea4335; color: #ea4335; background: #fce8e6; }
  .tag.그룹바이 { border-color: #34a853; color: #34a853; background: #e6f4ea; }

  table { width: calc(100% - 64px); margin: 0 32px 32px; border-collapse: collapse; background: #fff; border-radius: 10px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,.08); }
  th { background: #1a1a2e; color: #aaa; font-size: 11px; text-align: left; padding: 10px 14px; font-weight: 500; letter-spacing: .5px; text-transform: uppercase; }
  td { padding: 11px 14px; border-bottom: 1px solid #f0f0f0; font-size: 13px; vertical-align: middle; }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: #fafafa; }

  .site-badge {
    display: inline-block; font-size: 11px; padding: 2px 7px;
    border-radius: 4px; font-weight: 600; white-space: nowrap;
  }
  .badge-자소설닷컴 { background: #ede9fe; color: #7c3aed; }
  .badge-사람인   { background: #e8f0fe; color: #1a73e8; }
  .badge-잡코리아 { background: #fce8e6; color: #ea4335; }
  .badge-그룹바이 { background: #e6f4ea; color: #34a853; }

  .title a { color: #1a1a2e; text-decoration: none; font-weight: 500; }
  .title a:hover { color: #e94560; }
  .company { color: #555; font-size: 12px; margin-top: 2px; }
  .stacks { font-size: 11px; color: #888; margin-top: 3px; }

  .size-badge { font-size: 11px; color: #999; }
  .career-badge { font-size: 11px; padding: 1px 6px; background: #f0f0f0; border-radius: 3px; color: #555; }

  .empty { text-align: center; padding: 60px; color: #999; font-size: 14px; }
</style>
</head>
<body>

<div class="top">
  <h1>🎯 공고 사냥</h1>
  <form method="get" action="/">
    <input type="text" name="q" placeholder="직무 키워드 (예: 백엔드 개발자)" value="{{ q }}" autofocus>
    <select name="size">
      <option value="all"    {% if size=='all'    %}selected{% endif %}>전체</option>
      <option value="big"    {% if size=='big'    %}selected{% endif %}>대기업</option>
      <option value="corp"   {% if size=='corp'   %}selected{% endif %}>중견·중소</option>
      <option value="startup"{% if size=='startup'%}selected{% endif %}>스타트업</option>
    </select>
    <button type="submit">검색</button>
  </form>
</div>

{% if q %}
<div class="meta">
  <b>{{ q }}</b> · {{ size_label }} · 총 <b>{{ results|length }}개</b>
  {% if duped %} <span style="color:#999">(중복 {{ duped }}개 제거)</span>{% endif %}
</div>

<div class="tags">
  {% for site, cnt in site_counts.items() %}
  <span class="tag {{ site }}">{{ site }} {{ cnt }}</span>
  {% endfor %}
</div>

{% if results %}
<table>
  <thead>
    <tr>
      <th>#</th>
      <th>출처</th>
      <th>공고</th>
      <th>경력</th>
    </tr>
  </thead>
  <tbody>
  {% for j in results %}
  <tr>
    <td style="color:#bbb;width:36px">{{ loop.index }}</td>
    <td style="width:90px">
      <span class="site-badge badge-{{ j.site }}">{{ j.site }}</span><br>
      <span class="size-badge">{{ j.size }}</span>
    </td>
    <td>
      <div class="title"><a href="{{ j.link }}" target="_blank">{{ j.title }}</a></div>
      <div class="company">{{ j.company }}{% if j.get('location') %} · {{ j.location }}{% endif %}</div>
      {% if j.get('stacks') %}<div class="stacks">{{ j.stacks }}</div>{% endif %}
    </td>
    <td style="width:70px">
      {% if j.get('career') %}<span class="career-badge">{{ j.career }}</span>{% endif %}
    </td>
  </tr>
  {% endfor %}
  </tbody>
</table>
{% else %}
<div class="empty">결과 없음 — 다른 키워드를 입력해보세요</div>
{% endif %}

{% else %}
<div class="empty" style="margin-top:80px">키워드를 입력하고 검색하세요</div>
{% endif %}

</body>
</html>
"""

@app.route("/")
def index():
    q = request.args.get("q", "").strip()
    size = request.args.get("size", "all")
    target_sites = SIZE_SITES.get(size, SIZE_SITES["all"])
    size_label = {"all": "전체", "big": "대기업", "corp": "중견·중소", "startup": "스타트업"}.get(size, "전체")

    results, duped = [], 0
    site_counts = {}

    if q:
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
                jobs = fn(q)
                raw += jobs
                site_counts[name] = len(jobs)
            except Exception:
                site_counts[name] = 0
        results = dedup(raw)
        duped = len(raw) - len(results)

    return render_template_string(
        HTML, q=q, size=size, size_label=size_label,
        results=results, duped=duped, site_counts=site_counts
    )

if __name__ == "__main__":
    print("http://localhost:5000 에서 실행 중")
    app.run(debug=False, port=5000)
