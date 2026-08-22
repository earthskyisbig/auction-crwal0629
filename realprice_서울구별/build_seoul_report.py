# -*- coding: utf-8 -*-
"""서울 구별 평당가 2년 변화 검토보고 HTML 생성 (algo-design 톤, 인라인 SVG 차트)"""
import json, os, html
W = os.path.dirname(os.path.abspath(__file__))
ins = json.load(open(os.path.join(W, 'seoul_gu_insights.json')))
mat = json.load(open(os.path.join(W, 'seoul_gu_matched.json')))
pop = json.load(open(os.path.join(W, 'population_202607.json')))
apthh = json.load(open(os.path.join(W, 'apt_households.json')))
# 2023 전국사업체조사 종사자수 — 공표 확인된 상위 5개 구만 (나머지는 KOSIS 확인 필요)
jobs = {'강남구': 772567, '서초구': 495335, '영등포구': 435180, '중구': 419211, '송파구': 412433}

ORANGE, BLUE, GREEN, PURPLE, GOLD = '#cf6a48', '#3f7fb8', '#4f7d3a', '#8a6bb8', '#b0893a'
MONTHS = ins['강남구']['months']

rank = sorted(ins.keys(), key=lambda g: -(mat[g]['matched_chg_pct'] or -99))

# ── 1. 매칭 변화율 가로 막대 ──────────────────────────────
def bar_chart():
    rows = [(g, mat[g]['matched_chg_pct']) for g in rank]
    w, rh, lab_w, val_w = 940, 26, 90, 60
    max_v = max(v for _, v in rows)
    plot_w = w - lab_w - val_w
    h = len(rows) * rh + 30
    s = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="구별 매칭 변화율" style="width:100%;height:auto;">']
    for gx in range(0, 41, 10):
        x = lab_w + plot_w * gx / max(40, max_v)
        s.append(f'<line x1="{x:.0f}" y1="4" x2="{x:.0f}" y2="{h-26}" stroke="rgba(20,20,19,0.08)"/>')
        s.append(f'<text x="{x:.0f}" y="{h-10}" font-size="11" fill="rgba(20,20,19,0.5)" text-anchor="middle">{gx}%</text>')
    for i, (g, v) in enumerate(rows):
        y = i * rh + 6
        bw = plot_w * v / max(40, max_v)
        s.append(f'<text x="{lab_w-8}" y="{y+13}" font-size="12.5" fill="#141413" text-anchor="end">{g}</text>')
        s.append(f'<rect class="bar" data-tip="{g} +{v}% ({mat[g]["pairs"]}개 단지·평형 쌍)" x="{lab_w}" y="{y}" width="{bw:.0f}" height="{rh-8}" rx="4" fill="{ORANGE}" fill-opacity="{0.55 + 0.45*v/max_v:.2f}"/>')
        s.append(f'<text x="{lab_w+bw+6:.0f}" y="{y+13}" font-size="12" fill="rgba(20,20,19,0.75)" font-family="Poppins,Arial">+{v}%</text>')
    s.append('</svg>')
    return ''.join(s)

# ── 2. 평당가 추이 라인 (5개 구, smooth) ──────────────────
LINE_GUS = [('강남구', ORANGE), ('송파구', BLUE), ('성동구', GREEN), ('마포구', PURPLE), ('노원구', GOLD)]
def line_chart():
    w, h, pl, pr, pt, pb = 940, 430, 64, 96, 16, 40
    ymin, ymax = 2000, 13000
    pw, ph = w - pl - pr, h - pt - pb
    def X(i): return pl + pw * i / (len(MONTHS) - 1)
    def Y(v): return pt + ph * (1 - (v - ymin) / (ymax - ymin))
    s = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="구별 평당가 추이" style="width:100%;height:auto;">']
    for gy in range(2000, 13001, 2000):
        s.append(f'<line x1="{pl}" y1="{Y(gy):.0f}" x2="{w-pr}" y2="{Y(gy):.0f}" stroke="rgba(20,20,19,0.08)"/>')
        s.append(f'<text x="{pl-8}" y="{Y(gy)+4:.0f}" font-size="11" fill="rgba(20,20,19,0.5)" text-anchor="end">{gy/10000:.1f}억</text>')
    for i, ym in enumerate(MONTHS):
        if ym[4:] in ('09','01','05'):
            s.append(f'<text x="{X(i):.0f}" y="{h-14}" font-size="11" fill="rgba(20,20,19,0.5)" text-anchor="middle">{ym[2:4]}.{ym[4:]}</text>')
    labels = []
    for g, color in LINE_GUS:
        pts = ins[g]['smooth']
        path = []
        for i, v in enumerate(pts):
            if v is None: continue
            path.append(f"{'M' if not path else 'L'}{X(i):.1f},{Y(v):.1f}")
        s.append(f'<path d="{" ".join(path)}" fill="none" stroke="{color}" stroke-width="2.5" stroke-linejoin="round"/>')
        last = next(v for v in reversed(pts) if v is not None)
        labels.append([Y(last), g[:2], color])
        for i, v in enumerate(pts):
            if v is None: continue
            s.append(f'<circle class="pt" data-tip="{g} {MONTHS[i][:4]}.{MONTHS[i][4:]} — 평당 {v:,}만원 ({ins[g]["count"][i]}건)" cx="{X(i):.1f}" cy="{Y(v):.1f}" r="8" fill="transparent"/>')
    # 끝 라벨 충돌 방지: 위→아래 정렬 후 최소 16px 간격 강제
    labels.sort()
    for j in range(1, len(labels)):
        if labels[j][0] - labels[j-1][0] < 16:
            labels[j][0] = labels[j-1][0] + 16
    for ly, name, color in labels:
        s.append(f'<text x="{w-pr+8}" y="{ly+4:.0f}" font-size="12" font-weight="600" fill="{color}" font-family="Poppins,Arial">{name}</text>')
    s.append('</svg>')
    return ''.join(s)

# ── 3. 표 ──────────────────────────────────────────────
def table():
    rows = []
    for g in rank:
        d, m = ins[g], mat[g]
        job = f'{jobs[g]:,}' if g in jobs else '<span style="color:var(--mute);">—</span>'
        jrv = jr[g]['jeonse_ratio']
        rows.append(f'<tr><td class="name">{g}</td>'
                    f'<td>{d["first6_avg"]:,}</td><td>{d["last6_avg"]:,}</td>'
                    f'<td>{"+" if d["chg_pct"]>=0 else ""}{d["chg_pct"]}%</td>'
                    f'<td><strong>+{m["matched_chg_pct"]}%</strong> <span style="color:var(--mute);font-size:0.8em;">({m["pairs"]}쌍)</span></td>'
                    f'<td>{jrv}%</td>'
                    f'<td>{d["total_trades"]:,}</td>'
                    f'<td>{pop[g]:,}</td>'
                    f'<td>{apthh[g]:,}</td>'
                    f'<td>{job}</td></tr>')
    return ''.join(rows)

top5 = [(g, mat[g]['matched_chg_pct']) for g in rank[:5]]
bot5 = [(g, mat[g]['matched_chg_pct']) for g in rank[-5:]]

from datetime import date
import sys; sys.path.insert(0, W)
from windows import MONTHS as WMONTHS
top_gu, bot_gu = rank[0], rank[-1]
total_trades = sum(d['total_trades'] for d in ins.values())
gangnam_pp = ins['강남구']['last6_avg']
period_str = f"{WMONTHS[0][:4]}.{WMONTHS[0][4:]} ~ {WMONTHS[-1][:4]}.{WMONTHS[-1][4:]}"
today_str = date.today().strftime('%Y.%m.%d')

import charts_extra
map_svg = charts_extra.choropleth(mat)
heat_svg = charts_extra.heatmap(ins, mat, rank, MONTHS)
scatter_svg = charts_extra.scatter(ins, mat, {g: int(v) for g, v in apthh.items()}, rank)
belt_svg = charts_extra.belt_dongs()
jr = json.load(open(os.path.join(W, 'jeonse_ratio.json')))
jeonse_svg = charts_extra.jeonse_map(jr)

html_doc = f'''<title>서울 구별 평당가 2년</title>
<style>
:root{{ --dark:#141413; --light:#faf9f5; --light-gray:#e8e6dc; --mid-gray:#b0aea5;
  --orange:#d97757; --blue:#6a9bcc; --mute:rgba(20,20,19,0.62); --line:rgba(20,20,19,0.1);
  --heading:'Poppins','Apple SD Gothic Neo','Malgun Gothic',Arial,sans-serif;
  --body:'Lora','Apple SD Gothic Neo','Malgun Gothic',Georgia,serif;
  --label:'Poppins','Apple SD Gothic Neo','Malgun Gothic',Arial,sans-serif;
  --maxw:1050px; --ease:cubic-bezier(.16,1,.3,1); }}
body{{ margin:0; background:var(--light); color:var(--dark); font-family:var(--body); line-height:1.65; -webkit-font-smoothing:antialiased; }}
h1,h2{{ margin:0; font-family:var(--heading); font-weight:600; letter-spacing:-0.01em; text-wrap:balance; }}
.wrap{{ max-width:var(--maxw); margin:0 auto; padding:0 28px; }}
section{{ padding:56px 0; }}
section.bg-soft{{ background:var(--light-gray); }}
section.on-dark{{ background:var(--dark); color:var(--light); }}
.on-dark h2{{ color:var(--light); }}
.eyebrow{{ font-family:var(--label); font-size:0.72rem; font-weight:600; letter-spacing:0.1em; text-transform:uppercase; color:var(--mute);
  display:inline-flex; align-items:center; gap:0.5em; background:var(--light-gray); padding:6px 14px; border-radius:999px; }}
.eyebrow::before{{ content:''; width:6px; height:6px; background:var(--orange); border-radius:50%; }}
.eyebrow.inv{{ background:rgba(250,249,245,0.08); color:rgba(250,249,245,0.6); }}
.hero{{ padding:88px 0 56px; position:relative; overflow:hidden; }}
.hero h1{{ font-size:clamp(1.8rem,4vw,2.7rem); margin:18px 0 12px; }}
.hero .lead{{ font-style:italic; color:var(--mute); max-width:36em; }}
.stats{{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:14px; margin-top:34px; }}
.stat{{ background:var(--light); border:1px solid var(--line); border-radius:16px; padding:16px 18px; }}
.stat .v{{ font-family:var(--heading); font-weight:600; font-size:1.4rem; font-variant-numeric:tabular-nums; }}
.stat .k{{ font-family:var(--label); font-size:0.68rem; text-transform:uppercase; letter-spacing:0.08em; color:var(--mute); margin-top:2px; }}
h2{{ font-size:1.5rem; margin-top:12px; }}
.sec-head p{{ color:var(--mute); max-width:44em; margin:10px 0 0; }}
.chartbox{{ background:var(--light); border:1px solid var(--line); border-radius:16px; padding:22px; margin-top:24px; }}
.legend{{ display:flex; flex-wrap:wrap; gap:16px; margin:6px 0 14px; font-family:var(--label); font-size:0.8rem; }}
.legend span{{ display:inline-flex; align-items:center; gap:6px; color:var(--mute); }}
.legend i{{ width:14px; height:3px; border-radius:2px; display:inline-block; }}
.tablebox{{ overflow-x:auto; margin-top:24px; border:1px solid var(--line); border-radius:16px; background:var(--light); }}
table{{ border-collapse:collapse; width:100%; min-width:1000px; font-size:0.88rem; }}
th{{ font-family:var(--label); font-size:0.66rem; text-transform:uppercase; letter-spacing:0.06em; color:var(--mute); text-align:right; padding:12px 14px; border-bottom:1px solid var(--line); white-space:nowrap; }}
th:first-child{{ text-align:left; }}
td{{ padding:9px 14px; border-bottom:1px solid var(--line); text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }}
td.name{{ font-family:var(--heading); font-weight:600; text-align:left; }}
tr:last-child td{{ border-bottom:none; }}
.warn-list{{ display:grid; gap:12px; margin-top:24px; }}
.warn{{ display:flex; gap:14px; background:rgba(250,249,245,0.05); border:1px solid rgba(250,249,245,0.12); border-radius:14px; padding:14px 18px; }}
.warn .n{{ font-family:var(--heading); font-weight:600; color:var(--orange); flex:none; }}
.warn p{{ margin:0; color:rgba(250,249,245,0.65); font-size:0.93rem; }}
.warn p strong{{ color:var(--light); }}
#tip{{ position:fixed; pointer-events:none; background:var(--dark); color:var(--light); font-family:var(--label);
  font-size:0.78rem; padding:7px 11px; border-radius:8px; opacity:0; transition:opacity 0.12s; z-index:50; max-width:280px; }}
.bar:hover{{ stroke:#141413; stroke-width:1; }}
footer{{ padding:36px 0 52px; color:var(--mute); font-size:0.84rem; }}
</style>

<div id="tip"></div>

<section class="hero">
  <div class="wrap">
    <span class="eyebrow">국토부 실거래가 · {period_str} (24개월, {today_str} 수집)</span>
    <h1>서울 구별 평당가, 2년간 어디가 얼마나 올랐나</h1>
    <p class="lead">서울 25개 구 아파트 매매 {total_trades:,}건(해제 제외)의 전용면적 평당가를 집계했습니다. 헤드라인 변화율은 <strong>동일 단지·동일 평형끼리 두 기간을 직접 비교한 매칭 지수</strong> — 거래 구성이 바뀌어 생기는 착시를 걷어낸 수치입니다.</p>
    <div class="stats">
      <div class="stat"><div class="v">+{mat[top_gu]["matched_chg_pct"]}%</div><div class="k">상승 1위 {top_gu}</div></div>
      <div class="stat"><div class="v">+{mat[bot_gu]["matched_chg_pct"]}%</div><div class="k">최하위 {bot_gu}</div></div>
      <div class="stat"><div class="v">{gangnam_pp/10000:.2f}억</div><div class="k">강남구 평당 (최근 6개월)</div></div>
      <div class="stat"><div class="v">{total_trades:,}건</div><div class="k">분석 거래</div></div>
    </div>
  </div>
</section>

<section class="bg-soft">
  <div class="wrap sec-head">
    <span class="eyebrow">랭킹</span>
    <h2>구별 2년 상승률 — 매칭 지수 기준</h2>
    <p>2024.09~2025.02 대비 2026.03~2026.08. 같은 단지·같은 평형에서 양쪽 기간 각 2건 이상 거래된 쌍의 가격 비율 중앙값입니다.</p>
    <div class="chartbox">{bar_chart()}</div>
  </div>
</section>

<section>
  <div class="wrap sec-head">
    <span class="eyebrow">지도</span>
    <h2>서울 지도에서 본 상승률 — 한강벨트의 온도</h2>
    <p>색이 짙을수록 2년 상승률(매칭 지수)이 높습니다. 성동·광진·동작·송파·강동으로 이어지는 한강 동남 벨트가 짙고, 외곽(노도강·금천·중랑·은평)이 옅습니다. 구를 클릭하지 않아도 올리면 수치가 보입니다.</p>
    <div class="chartbox">{map_svg}</div>
  </div>
</section>

<section>
  <div class="wrap sec-head">
    <span class="eyebrow">지도 · 전세가율</span>
    <h2>전세가율 지도 — 상승률의 거울상</h2>
    <p>같은 기간(2026.03~08) 동일 단지·평형의 전세 보증금 ÷ 매매가입니다. 위의 상승률 지도와 정확히 반대로 칠해집니다: <strong>많이 오른 성동·송파·강남은 전세가율 39~40%</strong>(전세가 못 따라와 갭이 큼), <strong>덜 오른 금천·도봉·강북은 62~64%</strong>(갭이 작아 갭투자 접근이 쉬운 곳). 매매가 급등이 실수요 가격(전세)보다 앞서 나갔다는 뜻이기도 합니다.</p>
    <div class="chartbox">{jeonse_svg}</div>
  </div>
</section>

<section class="bg-soft">
  <div class="wrap sec-head">
    <span class="eyebrow">매트릭스</span>
    <h2>25개 구 × 24개월 — 언제, 어디가 움직였나</h2>
    <p>각 칸은 그 달의 평당가 지수(첫 6개월 평균 = 100)입니다. 주황이 짙을수록 출발점 대비 상승, 파랑은 하락. 위쪽(상승 상위 구)이 2026년 봄부터 일제히 짙어지는 것과, 2025년 6·27 대출규제 직후 몇 달간 색이 옅어지는 것이 보입니다.</p>
    <div class="chartbox" style="overflow-x:auto;">{heat_svg}</div>
  </div>
</section>

<section>
  <div class="wrap sec-head">
    <span class="eyebrow">추이</span>
    <h2>월별 평당가 흐름 — 대표 5개 구</h2>
    <p>월별 중앙값에 3개월 이동중앙값을 적용한 값(전용면적 평당, 단위 억원). 점에 마우스를 올리면 값이 보입니다.</p>
    <div class="chartbox">
      <div class="legend">
        <span><i style="background:{ORANGE}"></i>강남구</span><span><i style="background:{BLUE}"></i>송파구</span>
        <span><i style="background:{GREEN}"></i>성동구</span><span><i style="background:{PURPLE}"></i>마포구</span>
        <span><i style="background:{GOLD}"></i>노원구</span>
      </div>
      {line_chart()}
    </div>
  </div>
</section>

<section class="bg-soft">
  <div class="wrap sec-head">
    <span class="eyebrow">사분면</span>
    <h2>비싼 곳이 더 올랐나 — 가격 × 상승률 × 규모</h2>
    <p>가로축은 최근 6개월 평당가, 세로축은 2년 상승률(매칭), 버블 크기는 그 구의 아파트 세대수입니다. 좌상단(싸면서 많이 오른 곳)에 동작·강동·동대문이, 우하단(비싼데 덜 오른 곳)에 서초·용산이 있습니다. 노원·도봉(큰 버블, 좌하단)은 규모는 크지만 흐름이 늦습니다.</p>
    <div class="chartbox">{scatter_svg}</div>
  </div>
</section>

<section>
  <div class="wrap sec-head">
    <span class="eyebrow">드릴다운 · 한강벨트</span>
    <h2>벨트 안에서는 어느 동이 끌었나 — 5개 구 법정동 분해</h2>
    <p>상승 상위 5개 구(성동·광진·동작·송파·강동)를 법정동 단위로 쪼갠 매칭 지수입니다(단지·평형 쌍 4개 이상인 동만). 두드러진 패턴: <strong>대장 동네가 아니라 그 옆 동네가 더 올랐습니다.</strong> 성동은 성수(+33%)보다 금호3가(+57%)·응봉(+48%)·마장(+44%)이, 송파는 잠실(+26%)보다 오금(+42%)·장지(+42%)·거여(+39%)가 높습니다 — 전형적인 갭 메우기 장세입니다.</p>
    <div class="chartbox">{belt_svg}</div>
  </div>
</section>

<section class="bg-soft">
  <div class="wrap sec-head">
    <span class="eyebrow">전체 데이터</span>
    <h2>25개 구 상세</h2>
    <p>평당가는 만원/평(전용면적 기준). '단순 변화'는 전체 거래 중앙값 기준이라 거래 구성이 바뀌면 왜곡됩니다 — 서초·양천의 마이너스가 그 예입니다. 매칭 지수를 기준으로 읽으세요. 인구는 주민등록인구(행안부, 2026.07), 아파트 세대수는 K-apt 등재 관리단지 합계(국토부 공동주택 기본정보 — 의무관리대상 위주라 실제 전체보다 작음), 종사자수는 2023 사업체조사 공표 확인분(상위 5개 구)만 표기했습니다.</p>
    <div class="tablebox">
      <table>
        <thead><tr><th>구</th><th>첫 6개월 평당</th><th>최근 6개월 평당</th><th>단순 변화</th><th>매칭 변화 ★</th><th>전세가율</th><th>거래량</th><th>인구</th><th>아파트 세대수</th><th>종사자수</th></tr></thead>
        <tbody>{table()}</tbody>
      </table>
    </div>
  </div>
</section>

<section class="on-dark">
  <div class="wrap sec-head">
    <span class="eyebrow inv">해석 시 주의</span>
    <h2>숫자를 읽기 전에</h2>
    <div class="warn-list">
      <div class="warn"><span class="n">01</span><p><strong>단순 중앙값의 서초 −5.4%, 양천 −10.7%는 하락이 아닙니다.</strong> 2025.6.27 대출규제 이후 초고가 거래가 급감하며 거래 '구성'이 중저가로 쏠린 착시입니다. 같은 단지끼리 비교한 매칭 지수로는 서초 +17.2%, 양천 +26.2%입니다.</p></div>
      <div class="warn"><span class="n">02</span><p><strong>2026년 7~8월 데이터는 아직 덜 신고된 상태입니다.</strong> 실거래 신고는 계약 후 30일 이내라 최근 2개월 수치는 표본이 작고, 이후 갱신될 수 있습니다.</p></div>
      <div class="warn"><span class="n">03</span><p><strong>중앙값 기반 참고용 통계입니다.</strong> 한국부동산원·KB 공식 지수와 다를 수 있으며, 개별 단지 판단은 단지별 실거래를 직접 확인해야 합니다.</p></div>
    </div>
  </div>
</section>

<footer>
  <div class="wrap">국토교통부 아파트 매매·전월세 실거래가(RTMS) · 해제거래 제외 · 평당가 상하위 1% 이상치 컷 · {today_str} 수집</div>
</footer>

<script>
var tip = document.getElementById('tip');
document.querySelectorAll('[data-tip]').forEach(function(el){{
  el.addEventListener('mousemove', function(e){{
    tip.textContent = el.getAttribute('data-tip');
    tip.style.left = Math.min(e.clientX + 14, window.innerWidth - 290) + 'px';
    tip.style.top = (e.clientY - 36) + 'px';
    tip.style.opacity = 1;
  }});
  el.addEventListener('mouseleave', function(){{ tip.style.opacity = 0; }});
}});
</script>
'''
open(os.path.join(W, 'seoul_report.html'), 'w', encoding='utf-8').write(html_doc)
print('seoul_report.html 생성 완료,', len(html_doc), 'bytes')
