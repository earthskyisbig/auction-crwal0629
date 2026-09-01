# -*- coding: utf-8 -*-
"""서울 단지별 평당가 2년 변화 리포트 HTML 생성 (구별 리포트의 단지 단위 버전, algo-design 톤)
   입력: complex_index.json (compute_complex.py), seoul_gu_matched.json  → seoul_complex_report.html
   서술·축·순위는 전부 데이터에서 만든다."""
import json, os, html, statistics, math
from datetime import date
W = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(W, 'complex_index.json'), encoding='utf-8'))
MONTHS, C = D['months'], D['complexes']
GU_MAT = json.load(open(os.path.join(W, 'seoul_gu_matched.json'), encoding='utf-8'))
ORANGE, BLUE, GREEN, INK, MUTE = '#cf6a48', '#3f7fb8', '#4f7d3a', '#141413', 'rgba(20,20,19,0.55)'

def ym_str(ym): return f"{ym[:4]}.{ym[4:]}"
A_STR = f"{ym_str(MONTHS[0])}~{ym_str(MONTHS[5])}"
B_STR = f"{ym_str(MONTHS[-6])}~{ym_str(MONTHS[-1])}"
def esc(s): return html.escape(str(s or ''))
def eok(man): return '—' if man is None else f"{man/10000:.1f}억"
def pct(v, d=1): return '—' if v is None else f"{v:+.{d}f}%"
def label(r): return f"{r['g'][:-1]} {r['d']} · {r['n']}"

# 신뢰 등급: 매칭 쌍 2개 이상 + 24개월 거래 12건 이상 → 순위·산점도에 사용
REL = [r for r in C if r['chg'] is not None and r['pairs'] >= 2 and r['t'] >= 12]
WITH_CHG = [r for r in C if r['chg'] is not None]
rel_sorted = sorted(REL, key=lambda r: -r['chg'])
top30, bot15 = rel_sorted[:30], rel_sorted[-15:][::-1]
big = sorted([r for r in REL if (r.get('hh') or 0) >= 1000], key=lambda r: -r['chg'])[:20]
gapl = sorted([r for r in REL if r['jr'] and r.get('n_ar', 0) >= 3], key=lambda r: -r['jr'])[:25]
med_chg = statistics.median(r['chg'] for r in REL)
top1 = rel_sorted[0]

# ── 구별 대장·상승 1위 ─────────────────────────────────
def gu_table():
    rows = []
    gus = sorted(GU_MAT, key=lambda g: -(GU_MAT[g]['matched_chg_pct'] or -99))
    for g in gus:
        cs = [r for r in C if r['g'] == g]
        pricey = max((r for r in cs if r['pp'] and r['tb'] >= 6), key=lambda r: r['pp'], default=None)
        riser = max((r for r in REL if r['g'] == g), key=lambda r: r['chg'], default=None)
        rows.append('<tr>'
            f'<td class="name">{g}</td><td>{pct(GU_MAT[g]["matched_chg_pct"])}</td>'
            + (f'<td class="l">{esc(pricey["d"])} {esc(pricey["n"])}</td><td>{pricey["pp"]:,}</td>' if pricey else '<td class="l">—</td><td>—</td>')
            + (f'<td class="l">{esc(riser["d"])} {esc(riser["n"])}</td><td><strong>{pct(riser["chg"])}</strong> <span class="mute">({riser["pairs"]}쌍·{riser["t"]}건)</span></td>' if riser else '<td class="l">—</td><td>—</td>')
            + '</tr>')
    return ''.join(rows)

# ── 가로 막대 (순위) ───────────────────────────────────
def bars(rows, color=ORANGE, span_min=40):
    w, rh, lab_w, val_w = 940, 24, 330, 64
    plot_w = w - lab_w - val_w
    vmax = max((abs(r['chg']) for r in rows), default=1)
    span = max(span_min, vmax)
    h = len(rows) * rh + 30
    s = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="단지별 매칭 상승률" style="width:100%;height:auto;">']
    for gx in range(0, int(span) + 1, 10):
        x = lab_w + plot_w * gx / span
        s.append(f'<line x1="{x:.0f}" y1="4" x2="{x:.0f}" y2="{h-26}" stroke="rgba(20,20,19,0.08)"/>'
                 f'<text x="{x:.0f}" y="{h-10}" font-size="11" fill="{MUTE}" text-anchor="middle">{gx}%</text>')
    for i, r in enumerate(rows):
        y = i * rh + 6
        bw = plot_w * abs(r['chg']) / span
        fill = color if r['chg'] >= 0 else BLUE
        tip = (f"{label(r)} · {pct(r['chg'])} · 매칭 {r['pairs']}쌍 · 24개월 {r['t']}건 · 최근 평당 {r['pp']:,}만원"
               + (f" · 전용 {r['ar']}㎡ {eok(r['price'])}" if r['ar'] else '')
               + (f" · {r['hh']:,}세대" if r.get('hh') else ''))
        s.append(f'<text x="{lab_w-8}" y="{y+12}" font-size="11.5" fill="{INK}" text-anchor="end">{esc(label(r))[:34]}</text>'
                 f'<rect class="bar" data-tip="{esc(tip)}" x="{lab_w}" y="{y}" width="{bw:.0f}" height="{rh-7}" rx="4" fill="{fill}" fill-opacity="{0.5 + 0.5*abs(r["chg"])/span:.2f}"/>'
                 f'<text x="{lab_w+bw+6:.0f}" y="{y+12}" font-size="11" fill="rgba(20,20,19,0.75)" font-family="Poppins,Arial">{pct(r["chg"])}</text>')
    s.append('</svg>')
    return ''.join(s)

# ── 산점도: 최근 평당가 × 상승률, 원 = 세대수 ─────────────
def scatter():
    pts = [r for r in REL if r.get('hh') and r['pp']]
    Wpx, Hpx, pl, pr, pt, pb = 940, 520, 64, 30, 20, 44
    xs, ys = [r['pp'] for r in pts], [r['chg'] for r in pts]
    xmin, xmax = 0, ((max(xs) // 2000) + 1) * 2000
    ymin, ymax = min(-10, (min(ys) // 10) * 10), ((max(ys) // 10) + 1) * 10
    pw, ph = Wpx - pl - pr, Hpx - pt - pb
    X = lambda v: pl + pw * (v - xmin) / (xmax - xmin)
    Y = lambda v: pt + ph * (1 - (v - ymin) / (ymax - ymin))
    mx, my = statistics.median(xs), statistics.median(ys)
    s = [f'<svg viewBox="0 0 {Wpx} {Hpx}" role="img" aria-label="단지별 평당가 대비 상승률" style="width:100%;height:auto;">']
    for gx in range(int(xmin), int(xmax) + 1, 2000):
        s.append(f'<line x1="{X(gx):.0f}" y1="{pt}" x2="{X(gx):.0f}" y2="{Hpx-pb}" stroke="rgba(20,20,19,0.07)"/>'
                 f'<text x="{X(gx):.0f}" y="{Hpx-24}" font-size="11" fill="{MUTE}" text-anchor="middle">{gx/10000:.1f}억</text>')
    for gy in range(int(ymin), int(ymax) + 1, 10):
        s.append(f'<line x1="{pl}" y1="{Y(gy):.0f}" x2="{Wpx-pr}" y2="{Y(gy):.0f}" stroke="rgba(20,20,19,0.07)"/>'
                 f'<text x="{pl-8}" y="{Y(gy)+4:.0f}" font-size="11" fill="{MUTE}" text-anchor="end">{gy:+d}%</text>')
    s.append(f'<line x1="{X(mx):.0f}" y1="{pt}" x2="{X(mx):.0f}" y2="{Hpx-pb}" stroke="rgba(20,20,19,0.25)" stroke-dasharray="4 4"/>'
             f'<line x1="{pl}" y1="{Y(my):.0f}" x2="{Wpx-pr}" y2="{Y(my):.0f}" stroke="rgba(20,20,19,0.25)" stroke-dasharray="4 4"/>'
             f'<text x="{Wpx-pr-4}" y="{Y(my)-6:.0f}" font-size="10.5" fill="rgba(20,20,19,0.45)" text-anchor="end">상승률 중앙값 {pct(my)}</text>'
             f'<text x="{X(mx)+6:.0f}" y="{pt+12}" font-size="10.5" fill="rgba(20,20,19,0.45)">평당가 중앙값 {mx/10000:.2f}억</text>'
             f'<text x="{Wpx-pr-4}" y="{Hpx-6}" font-size="10.5" fill="rgba(20,20,19,0.45)" text-anchor="end">→ 최근 6개월 평당가(전용)</text>')
    for r in sorted(pts, key=lambda r: -r['hh']):
        rad = max(3.5, math.sqrt(r['hh'] / 1000) * 3.2)
        tip = f"{label(r)} · {pct(r['chg'])} · 평당 {r['pp']:,}만원 · {r['hh']:,}세대 · 매칭 {r['pairs']}쌍"
        s.append(f'<circle class="bar" data-tip="{esc(tip)}" cx="{X(r["pp"]):.0f}" cy="{Y(r["chg"]):.0f}" r="{rad:.1f}" fill="{ORANGE}" fill-opacity="0.38" stroke="#faf9f5" stroke-width="1.2"/>')
    # 라벨: 상승률 상위 4 + 평당가 상위 3 + 세대수 상위 3, 겹치면 위로 밀어 올린다
    lab = {id(r): r for r in sorted(pts, key=lambda r: -r['chg'])[:4]}
    lab.update({id(r): r for r in sorted(pts, key=lambda r: -r['pp'])[:3]})
    lab.update({id(r): r for r in sorted(pts, key=lambda r: -r['hh'])[:3]})
    placed = []
    for r in sorted(lab.values(), key=lambda r: (X(r['pp']), -r['chg'])):
        x, y = X(r['pp']), Y(r['chg']) - 8
        for _ in range(6):
            if all(abs(x - px) > 78 or abs(y - py) > 13 for px, py in placed): break
            y -= 13
        placed.append((x, y))
        s.append(f'<text x="{x:.0f}" y="{y:.0f}" font-size="10.5" font-weight="600" fill="{INK}" text-anchor="middle" font-family="Poppins,Arial" pointer-events="none">{esc(r["n"])[:12]}</text>')
    s.append('</svg>')
    return ''.join(s), len(pts)

# ── 갭 작은 단지 표 ────────────────────────────────────
def gap_table():
    rows = []
    for r in gapl:
        rows.append(f'<tr><td class="name">{esc(r["n"])}</td><td class="l">{r["g"]} {esc(r["d"])}</td>'
                    f'<td>{r["ar"]}㎡</td><td>{eok(r["price"])}</td><td>{eok(r["jeonse"])}</td>'
                    f'<td><strong>{eok(r["gap"])}</strong></td><td>{r["jr"]}%</td><td>{pct(r["chg"])}</td>'
                    f'<td>{r["hh"]:,}</td></tr>' if r.get('hh') else
                    f'<tr><td class="name">{esc(r["n"])}</td><td class="l">{r["g"]} {esc(r["d"])}</td>'
                    f'<td>{r["ar"]}㎡</td><td>{eok(r["price"])}</td><td>{eok(r["jeonse"])}</td>'
                    f'<td><strong>{eok(r["gap"])}</strong></td><td>{r["jr"]}%</td><td>{pct(r["chg"])}</td><td>—</td></tr>')
    return ''.join(rows)

scatter_svg, n_scatter = scatter()
today = date.today().strftime('%Y.%m.%d')
gus_all = sorted({r['g'] for r in C})
# 전체 표용 데이터 (매칭 지수 있는 단지)
table_rows = [{'g': r['g'], 'd': r['d'], 'n': r['n'], 'hh': r.get('hh'), 'bt': (r.get('bt') or '')[:4] or None,
               't': r['t'], 'p': r['pairs'], 'chg': r['chg'], 'pp': r['pp'], 'ar': r['ar'], 'pr': r['price'],
               'jr': r['jr'], 'gap': r['gap'], 'rel': (r['pairs'] >= 2 and r['t'] >= 12), 's': r['s']}
              for r in WITH_CHG]
DATA_JSON = json.dumps(table_rows, ensure_ascii=False, separators=(',', ':'))
gap_ex = gapl[0] if gapl else None

page = '''<title>서울 단지별 평당가 2년</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Poppins:wght@500;600&family=Lora:ital,wght@0,400;0,600;1,400&display=swap">
<style>
:root{ --dark:#141413; --light:#faf9f5; --light-gray:#e8e6dc; --orange:#d97757; --blue:#6a9bcc;
  --mute:rgba(20,20,19,0.62); --line:rgba(20,20,19,0.1);
  --heading:'Poppins','Apple SD Gothic Neo','Malgun Gothic',Arial,sans-serif;
  --body:'Lora','Apple SD Gothic Neo','Malgun Gothic',Georgia,serif;
  --maxw:1050px; }
body{ margin:0; background:var(--light); color:var(--dark); font-family:var(--body); line-height:1.65; -webkit-font-smoothing:antialiased; }
h1,h2,h3{ margin:0; font-family:var(--heading); font-weight:600; letter-spacing:-0.01em; text-wrap:balance; }
.wrap{ max-width:var(--maxw); margin:0 auto; padding:0 28px; }
section{ padding:52px 0; }
section.bg-soft{ background:var(--light-gray); }
section.on-dark{ background:var(--dark); color:var(--light); }
.on-dark h2{ color:var(--light); }
.eyebrow{ font-family:var(--heading); font-size:0.72rem; font-weight:600; letter-spacing:0.1em; text-transform:uppercase; color:var(--mute);
  display:inline-flex; align-items:center; gap:0.5em; background:var(--light-gray); padding:6px 14px; border-radius:999px; }
.eyebrow::before{ content:''; width:6px; height:6px; background:var(--orange); border-radius:50%; }
.eyebrow.inv{ background:rgba(250,249,245,0.08); color:rgba(250,249,245,0.6); }
.hero{ padding:84px 0 52px; }
.hero h1{ font-size:clamp(1.8rem,4vw,2.7rem); margin:18px 0 12px; }
.hero .lead{ font-style:italic; color:var(--mute); max-width:38em; }
.stats{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:14px; margin-top:34px; }
.stat{ background:var(--light); border:1px solid var(--line); border-radius:16px; padding:16px 18px; }
.stat .v{ font-family:var(--heading); font-weight:600; font-size:1.35rem; font-variant-numeric:tabular-nums; }
.stat .k{ font-family:var(--heading); font-size:0.68rem; text-transform:uppercase; letter-spacing:0.08em; color:var(--mute); margin-top:2px; }
h2{ font-size:1.5rem; margin-top:12px; }
.sec-head p{ color:var(--mute); max-width:46em; margin:10px 0 0; }
.chartbox{ background:var(--light); border:1px solid var(--line); border-radius:16px; padding:22px; margin-top:24px; }
.tablebox{ overflow-x:auto; margin-top:24px; border:1px solid var(--line); border-radius:16px; background:var(--light); }
table{ border-collapse:collapse; width:100%; font-size:0.86rem; }
th{ font-family:var(--heading); font-size:0.64rem; text-transform:uppercase; letter-spacing:0.06em; color:var(--mute); text-align:right; padding:11px 12px; border-bottom:1px solid var(--line); white-space:nowrap; }
th:first-child, th.l{ text-align:left; }
td{ padding:8px 12px; border-bottom:1px solid var(--line); text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }
td.name{ font-family:var(--heading); font-weight:600; text-align:left; }
td.l{ text-align:left; color:var(--mute); }
tr:last-child td{ border-bottom:none; }
.mute{ color:var(--mute); font-size:0.82em; }
.bar:hover{ stroke:#141413; stroke-width:1; }
#tip{ position:fixed; pointer-events:none; background:var(--dark); color:var(--light); font-family:var(--heading);
  font-size:0.76rem; padding:7px 11px; border-radius:8px; opacity:0; transition:opacity 0.12s; z-index:50; max-width:320px; }
.warn-list{ display:grid; gap:12px; margin-top:24px; }
.warn{ display:flex; gap:14px; background:rgba(250,249,245,0.05); border:1px solid rgba(250,249,245,0.12); border-radius:14px; padding:14px 18px; }
.warn .n{ font-family:var(--heading); font-weight:600; color:var(--orange); flex:none; }
.warn p{ margin:0; color:rgba(250,249,245,0.65); font-size:0.93rem; }
.warn p strong{ color:var(--light); }
/* 전체 표 컨트롤 */
.ctl{ display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin-top:20px; }
.ctl input{ font-family:var(--heading); font-size:0.85rem; padding:8px 12px; border:1px solid var(--line); border-radius:999px; background:var(--light); color:var(--dark); min-width:220px; }
.ctl input:focus{ outline:2px solid var(--orange); outline-offset:1px; }
.chip{ font-family:var(--heading); font-size:0.74rem; padding:5px 11px; border-radius:999px; border:1px solid var(--line); background:var(--light); color:var(--mute); cursor:pointer; }
.chip[aria-pressed="true"]{ background:var(--dark); color:var(--light); border-color:var(--dark); }
.chip:focus-visible{ outline:2px solid var(--orange); outline-offset:1px; }
th.sortable{ cursor:pointer; }
th.sortable[data-dir="desc"]::after{ content:' ↓'; } th.sortable[data-dir="asc"]::after{ content:' ↑'; }
td svg{ vertical-align:middle; }
.tag{ display:inline-block; font-family:var(--heading); font-size:0.62rem; padding:1px 6px; border-radius:999px; background:var(--light-gray); color:var(--mute); margin-left:4px; }
footer{ padding:36px 0 52px; color:var(--mute); font-size:0.84rem; }
@media (prefers-reduced-motion: reduce){ *{ transition:none !important; } }
</style>
<div id="tip"></div>

<section class="hero"><div class="wrap">
  <span class="eyebrow">국토부 실거래가 · %%PERIOD%% (24개월, %%TODAY%% 생성)</span>
  <h1>서울 단지별 평당가, 2년간 어느 단지가 얼마나 올랐나</h1>
  <p class="lead">구별 리포트의 매칭 지수를 단지 하나하나에 적용했습니다. <strong>같은 단지·같은 평형끼리 %%A%% 와 %%B%% 의 중앙값을 비교</strong>한 값이라 대형 평형이 많이 팔린 달의 착시가 없습니다. 24개월 거래 6건 이상인 %%N_ALL%%개 단지 중 매칭 쌍이 있는 %%N_CHG%%개를 실었고, 순위는 쌍 2개·거래 12건 이상인 %%N_REL%%개로 매겼습니다.</p>
  <div class="stats">
    <div class="stat"><div class="v">%%TOP1_CHG%%</div><div class="k">상승 1위 · %%TOP1%%</div></div>
    <div class="stat"><div class="v">%%MED%%</div><div class="k">단지 상승률 중앙값 (%%N_REL%%개)</div></div>
    <div class="stat"><div class="v">%%N_BIG%%개</div><div class="k">1,000세대 이상 순위 단지</div></div>
    <div class="stat"><div class="v">%%GAP_MIN%%</div><div class="k">가장 작은 갭 · %%GAP_N%%</div></div>
  </div>
</div></section>

<section class="bg-soft"><div class="wrap sec-head">
  <span class="eyebrow">랭킹</span>
  <h2>상승 상위 30 단지 — 매칭 지수</h2>
  <p>막대 위에 올리면 매칭 쌍·거래량·대표 평형 가격이 보입니다. 쌍이 2~3개인 단지는 한두 평형의 움직임이라 변동이 크니 거래량을 같이 보세요.</p>
  <div class="chartbox">%%TOP30%%</div>
</div></section>

<section><div class="wrap sec-head">
  <span class="eyebrow">구 → 단지</span>
  <h2>구마다 누가 대장이고 누가 끌었나</h2>
  <p>구별 매칭 지수 순서입니다. '최고 평당가'는 최근 6개월 거래 6건 이상인 단지 중 평당가 1위, '상승 1위'는 그 구에서 매칭 지수가 가장 높은 순위 단지입니다. 두 칸이 다른 구가 대부분 — 대장이 끈 곳과 뒤따라 오른 곳이 다르다는 뜻입니다.</p>
  <div class="tablebox"><table>
    <thead><tr><th>구</th><th>구 매칭</th><th class="l">최고 평당가 단지</th><th>평당(만원)</th><th class="l">상승 1위 단지</th><th>매칭 변화</th></tr></thead>
    <tbody>%%GU_TABLE%%</tbody></table></div>
</div></section>

<section class="bg-soft"><div class="wrap sec-head">
  <span class="eyebrow">사분면</span>
  <h2>비싼 단지가 더 올랐나 — 평당가 × 상승률 × 세대수</h2>
  <p>K-apt 세대수가 있는 순위 단지 %%N_SCATTER%%개. 가로축은 최근 6개월 평당가, 세로축은 매칭 상승률, 원 크기는 세대수입니다. 점선은 각각의 중앙값 — 좌상단이 '싸면서 많이 오른' 단지, 우하단이 '비싼데 덜 오른' 단지입니다.</p>
  <div class="chartbox">%%SCATTER%%</div>
</div></section>

<section><div class="wrap sec-head">
  <span class="eyebrow">대단지</span>
  <h2>1,000세대 이상 — 상승 상위 20</h2>
  <p>거래가 두터워 지수가 안정적인 단지들입니다. 재건축·리모델링 기대가 실린 구축 대단지가 얼마나 섞여 있는지 준공연도(표 아래)와 함께 보세요.</p>
  <div class="chartbox">%%BIG20%%</div>
</div></section>

<section class="bg-soft"><div class="wrap sec-head">
  <span class="eyebrow">갭</span>
  <h2>전세가 매매를 바짝 따라온 단지 — 갭이 작은 25곳</h2>
  <p>대표 평형(최근 6개월 최다 거래 평형)의 매매 중앙가와 신규 전세 중앙가 차이입니다. 갭이 작다는 것은 실수요 가격이 매매가를 받치고 있다는 뜻이자, 적은 자기자본으로 접근 가능한 곳이라는 뜻입니다. 순위 단지 중 대표 평형 거래 3건 이상만.</p>
  <div class="tablebox"><table>
    <thead><tr><th>단지</th><th class="l">위치</th><th>대표 전용</th><th>매매 중앙</th><th>전세 중앙</th><th>갭</th><th>전세가율</th><th>2년 매칭</th><th>세대수</th></tr></thead>
    <tbody>%%GAP_TABLE%%</tbody></table></div>
</div></section>

<section><div class="wrap sec-head">
  <span class="eyebrow">반대편</span>
  <h2>덜 오르거나 내린 단지 15</h2>
  <p>순위 단지 중 매칭 지수 하위 15곳. 파란 막대가 하락입니다. 특정 평형의 급매 한두 건이 만든 값일 수 있으니 쌍 수와 거래량을 확인하세요.</p>
  <div class="chartbox">%%BOT15%%</div>
</div></section>

<section class="bg-soft"><div class="wrap sec-head">
  <span class="eyebrow">전체 데이터</span>
  <h2>%%N_CHG%%개 단지 전체 — 구 선택 · 검색 · 정렬</h2>
  <p>열 제목을 누르면 정렬됩니다. 순위 기준(쌍 2·거래 12) 미달 단지는 회색 '참고' 표시가 붙고 뒤에 정렬됩니다. 추이 칸은 24개월 월별 평당가 중앙값입니다.</p>
  <div class="ctl" id="ctl"><input id="q" type="search" placeholder="단지명·동 검색" aria-label="단지명 검색"><button class="chip" data-gu="" aria-pressed="true">전체</button>%%CHIPS%%</div>
  <div class="tablebox"><table id="all">
    <thead><tr><th class="l">단지</th><th class="l">위치</th><th class="sortable" data-k="hh">세대</th><th class="sortable" data-k="bt">준공</th><th class="sortable" data-k="t">거래 24M</th><th class="sortable" data-k="p">쌍</th><th class="sortable" data-k="chg" data-dir="desc">매칭 변화</th><th class="sortable" data-k="pp">최근 평당</th><th>대표 평형 · 가격</th><th class="sortable" data-k="jr">전세가율</th><th class="sortable" data-k="gap">갭</th><th>추이</th></tr></thead>
    <tbody id="tb"></tbody></table></div>
  <p class="mute" id="cnt"></p>
</div></section>

<section class="on-dark"><div class="wrap sec-head">
  <span class="eyebrow inv">해석 시 주의</span>
  <h2>숫자를 읽기 전에</h2>
  <div class="warn-list">
    <div class="warn"><span class="n">쌍</span><p><strong>매칭 쌍이 적을수록 값이 거칩니다.</strong> 구 단위는 쌍이 100개를 넘지만 단지 단위는 2~5개가 보통입니다. 한 평형의 급매·신고가 한 건이 지수를 10%p 움직일 수 있습니다.</p></div>
    <div class="warn"><span class="n">동명</span><p><strong>단지는 (구, 법정동, 이름)으로 묶었습니다.</strong> 같은 이름의 단지가 다른 동에 있으면 따로 셉니다. 국토부 표기와 K-apt 표기가 달라 세대수·준공이 비는 단지가 있습니다.</p></div>
    <div class="warn"><span class="n">최근</span><p><strong>%%LAST2%% 거래는 아직 덜 신고된 상태입니다.</strong> 실거래 신고는 계약 후 30일 이내라 최근 두 달의 표본이 작고, 이후 갱신됩니다. 해제거래는 원본행까지 제외했습니다.</p></div>
  </div>
</div></section>

<footer><div class="wrap">국토교통부 아파트 매매·전월세 실거래가(RTMS) · 해제거래 제외 · 전세는 신규 계약만 · 평당가는 전용면적 기준 · %%TODAY%% 생성 · 단지 검색·층별·평형별은 <em>서울 아파트 파인더</em>에서</div></footer>

<script>
var tip = document.getElementById('tip');
function bindTips(root){
  (root||document).querySelectorAll('[data-tip]').forEach(function(el){
    el.addEventListener('mousemove', function(e){
      tip.textContent = el.getAttribute('data-tip');
      tip.style.left = Math.min(e.clientX + 14, window.innerWidth - 330) + 'px';
      tip.style.top = (e.clientY - 36) + 'px'; tip.style.opacity = 1; });
    el.addEventListener('mouseleave', function(){ tip.style.opacity = 0; });
  });
}
bindTips();
var ROWS = %%DATA%%;
var gu = '', q = '', sortK = 'chg', sortDir = -1;
function eok(m){ return m == null ? '—' : (m/10000).toFixed(1) + '억'; }
function pct(v){ return v == null ? '—' : (v > 0 ? '+' : '') + v.toFixed(1) + '%'; }
function spark(s){
  var v = s.filter(function(x){ return x != null; }); if (v.length < 2) return '';
  var mn = Math.min.apply(null, v), mx = Math.max.apply(null, v), w = 84, h = 22, n = s.length, d = '', started = false;
  for (var i = 0; i < n; i++){ if (s[i] == null) continue; var x = (i/(n-1))*w, y = mx === mn ? h/2 : h - 2 - (s[i]-mn)/(mx-mn)*(h-4);
    d += (started ? 'L' : 'M') + x.toFixed(1) + ',' + y.toFixed(1); started = true; }
  return '<svg width="84" height="22" viewBox="0 0 84 22" aria-hidden="true"><path d="' + d + '" fill="none" stroke="#cf6a48" stroke-width="1.5"/></svg>';
}
function render(){
  var rows = ROWS.filter(function(r){ return (!gu || r.g === gu) && (!q || (r.n + r.d).toLowerCase().indexOf(q) >= 0); });
  rows.sort(function(a, b){ if (a.rel !== b.rel) return a.rel ? -1 : 1;   // 순위 기준 충족 단지 먼저
    var x = a[sortK], y = b[sortK]; if (x == null) return 1; if (y == null) return -1; return (x - y) * sortDir; });
  var out = [];
  for (var i = 0; i < rows.length; i++){ var r = rows[i];
    out.push('<tr' + (r.rel ? '' : ' style="color:rgba(20,20,19,0.5)"') + '><td class="name">' + r.n + (r.rel ? '' : '<span class="tag">참고</span>') + '</td><td class="l">' + r.g + ' ' + r.d + '</td>'
      + '<td>' + (r.hh ? r.hh.toLocaleString() : '—') + '</td><td>' + (r.bt || '—') + '</td><td>' + r.t + '</td><td>' + r.p + '</td>'
      + '<td><strong>' + pct(r.chg) + '</strong></td><td>' + (r.pp ? r.pp.toLocaleString() : '—') + '</td>'
      + '<td>' + (r.ar ? r.ar + '㎡ · ' + eok(r.pr) : '—') + '</td><td>' + (r.jr != null ? r.jr + '%' : '—') + '</td><td>' + eok(r.gap) + '</td><td>' + spark(r.s) + '</td></tr>');
  }
  document.getElementById('tb').innerHTML = out.join('');
  document.getElementById('cnt').textContent = rows.length.toLocaleString() + '개 단지 표시' + (gu ? ' · ' + gu : '') + (q ? ' · "' + q + '"' : '');
}
document.querySelectorAll('.chip').forEach(function(b){ b.addEventListener('click', function(){
  document.querySelectorAll('.chip').forEach(function(x){ x.setAttribute('aria-pressed', 'false'); });
  b.setAttribute('aria-pressed', 'true'); gu = b.getAttribute('data-gu'); render(); }); });
document.getElementById('q').addEventListener('input', function(e){ q = e.target.value.trim().toLowerCase(); render(); });
document.querySelectorAll('th.sortable').forEach(function(th){ th.addEventListener('click', function(){
  var k = th.getAttribute('data-k'); if (sortK === k) sortDir = -sortDir; else { sortK = k; sortDir = -1; }
  document.querySelectorAll('th.sortable').forEach(function(x){ x.removeAttribute('data-dir'); });
  th.setAttribute('data-dir', sortDir < 0 ? 'desc' : 'asc'); render(); }); });
render();
</script>
'''
chips = ''.join(f'<button class="chip" data-gu="{g}" aria-pressed="false">{g}</button>' for g in gus_all)
reps = {
 '%%PERIOD%%': f"{ym_str(MONTHS[0])} ~ {ym_str(MONTHS[-1])}", '%%TODAY%%': today, '%%A%%': A_STR, '%%B%%': B_STR,
 '%%N_ALL%%': f"{len(C):,}", '%%N_CHG%%': f"{len(WITH_CHG):,}", '%%N_REL%%': f"{len(REL):,}",
 '%%TOP1_CHG%%': pct(top1['chg']), '%%TOP1%%': esc(f"{top1['g'][:-1]} {top1['n']}"), '%%MED%%': pct(med_chg),
 '%%N_BIG%%': str(len([r for r in REL if (r.get('hh') or 0) >= 1000])),
 '%%GAP_MIN%%': eok(gap_ex['gap']) if gap_ex else '—', '%%GAP_N%%': esc(f"{gap_ex['n']} {gap_ex['ar']}㎡") if gap_ex else '—',
 '%%TOP30%%': bars(top30), '%%GU_TABLE%%': gu_table(), '%%SCATTER%%': scatter_svg, '%%N_SCATTER%%': f"{n_scatter:,}",
 '%%BIG20%%': bars(big), '%%GAP_TABLE%%': gap_table(), '%%BOT15%%': bars(bot15, span_min=20),
 '%%CHIPS%%': chips, '%%DATA%%': DATA_JSON, '%%LAST2%%': f"{ym_str(MONTHS[-2])}·{MONTHS[-1][4:]}",
}
for k, v in reps.items():
    page = page.replace(k, v)
assert '%%' not in page
out = os.path.join(W, 'seoul_complex_report.html')
open(out, 'w', encoding='utf-8').write(page)
print(f'seoul_complex_report.html 생성 ({len(page)/1e6:.2f}MB) · 단지 {len(C)} / 매칭 {len(WITH_CHG)} / 순위 {len(REL)}')
