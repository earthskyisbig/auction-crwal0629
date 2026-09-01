# -*- coding: utf-8 -*-
"""서울 아파트 은하 — 단지 하나가 별 하나. 가로=그 달 평당가(로그), 세로=첫 거래월 대비 상승률, 24개월 재생.
   데이터: app_data.json(단지별 월별 평당가 중앙값·거래수·세대수). → seoul_galaxy.html"""
import json, os
from datetime import date
W = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(W, 'app_data.json'), encoding='utf-8'))
MONTHS = D['months']
ZONE = {'동남권': ['강남구', '서초구', '송파구', '강동구'], '도심권': ['종로구', '중구', '용산구'],
        '서북권': ['은평구', '서대문구', '마포구'],
        '서남권': ['양천구', '강서구', '구로구', '금천구', '영등포구', '동작구', '관악구'],
        '동북권': ['성동구', '광진구', '동대문구', '중랑구', '성북구', '강북구', '도봉구', '노원구']}
Z_OF = {g: i for i, (z, gs) in enumerate(ZONE.items()) for g in gs}
stars = []
for c in D['complexes']:
    s = c['s']
    if sum(1 for v in s if v) < 8: continue
    # 빈 달은 이웃 값으로 선형 보간(애니메이션용), 원본 결측 여부는 비트로
    filled, miss = [], 0
    last_i = None
    for i, v in enumerate(s):
        if v: filled.append(v); last_i = i
        else: filled.append(None); miss |= (1 << i)
    # 앞뒤 보간
    idx = [i for i, v in enumerate(filled) if v is not None]
    for i in range(len(filled)):
        if filled[i] is None:
            prev = max([j for j in idx if j < i], default=None); nxt = min([j for j in idx if j > i], default=None)
            if prev is None: filled[i] = filled[nxt]
            elif nxt is None: filled[i] = filled[prev]
            else: filled[i] = round(filled[prev] + (filled[nxt] - filled[prev]) * (i - prev) / (nxt - prev))
    stars.append({'n': c['n'], 'g': c['g'], 'd': c['d'], 'z': Z_OF[c['g']], 'hh': c.get('hh') or 0, 'bt': (c.get('bt') or '')[:4],
                  's': filled, 'c': c['c'], 'm': miss, 'jr': c.get('jr')})
DATA = json.dumps({'months': MONTHS, 'zones': list(ZONE), 'stars': stars}, ensure_ascii=False, separators=(',', ':'))
period = f"{MONTHS[0][:4]}.{MONTHS[0][4:]} ~ {MONTHS[-1][:4]}.{MONTHS[-1][4:]}"

page = r'''<title>서울 아파트 은하</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Poppins:wght@500;600&family=Lora:ital@0;1&display=swap">
<style>
:root{ --bg:#07090d; --ink:#f3efe6; --mute:rgba(243,239,230,0.6); --line:rgba(243,239,230,0.12); --orange:#e0784f; --gold:#d9b25a;
  --head:'Poppins','Apple SD Gothic Neo','Malgun Gothic',Arial,sans-serif; --body:'Lora','Apple SD Gothic Neo','Malgun Gothic',Georgia,serif; }
html,body{ height:100%; } body{ margin:0; background:var(--bg); color:var(--ink); font-family:var(--body); overflow:hidden; }
canvas{ position:fixed; inset:0; display:block; }
#sky{ z-index:1; } #ui{ z-index:2; pointer-events:none; }
.head{ position:fixed; z-index:5; top:22px; left:24px; max-width:430px; pointer-events:none; }
.head h1{ font-family:var(--head); font-weight:600; font-size:clamp(1.4rem,2.6vw,2rem); margin:8px 0 6px; letter-spacing:-0.01em; text-wrap:balance; }
.head p{ margin:0; color:var(--mute); font-size:0.88rem; line-height:1.55; font-style:italic; }
.head p.small{ font-style:normal; font-family:var(--head); font-size:0.66rem; margin-top:10px; opacity:0.8; }
.eyebrow{ font-family:var(--head); font-size:0.66rem; letter-spacing:0.12em; text-transform:uppercase; color:var(--mute); display:inline-flex; gap:0.5em; align-items:center; }
.eyebrow::before{ content:''; width:6px; height:6px; border-radius:50%; background:var(--orange); }
.month{ position:fixed; z-index:5; right:28px; top:20px; text-align:right; pointer-events:none; }
.month .big{ font-family:var(--head); font-weight:600; font-size:clamp(2rem,5vw,3.6rem); line-height:1; font-variant-numeric:tabular-nums; letter-spacing:-0.02em; }
.month .sub{ color:var(--mute); font-size:0.8rem; margin-top:6px; font-family:var(--head); }
.side{ position:fixed; z-index:5; right:28px; top:112px; width:250px; font-family:var(--head); font-size:0.74rem; display:grid; gap:14px; }
.box{ background:rgba(12,15,21,0.78); backdrop-filter:blur(8px); border:1px solid var(--line); border-radius:14px; padding:12px 14px; }
.box h3{ margin:0 0 8px; font-size:0.66rem; letter-spacing:0.1em; text-transform:uppercase; color:var(--mute); font-weight:600; }
.zones{ display:grid; gap:6px; }
.zone{ display:flex; align-items:center; gap:8px; cursor:pointer; background:none; border:0; color:var(--ink); font-family:var(--head); font-size:0.76rem; padding:3px 0; text-align:left; }
.zone i{ width:10px; height:10px; border-radius:50%; flex:none; box-shadow:0 0 8px currentColor; }
.zone[aria-pressed="false"]{ color:var(--mute); } .zone[aria-pressed="false"] i{ opacity:0.25; box-shadow:none; }
.zone:focus-visible{ outline:2px solid var(--gold); outline-offset:2px; border-radius:4px; }
.movers .row{ display:grid; grid-template-columns:1fr 58px; gap:8px; color:var(--mute); line-height:1.5; }
.movers .row b{ color:var(--ink); font-weight:500; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.movers .row span{ text-align:right; font-variant-numeric:tabular-nums; }
.movers .row.up span{ color:#f0a07a; } .movers .row.dn span{ color:#8ab4e0; }
.ctl{ position:fixed; z-index:6; left:50%; bottom:22px; transform:translateX(-50%); width:min(820px,calc(100% - 40px));
  background:rgba(12,15,21,0.82); backdrop-filter:blur(8px); border:1px solid var(--line); border-radius:16px; padding:12px 16px;
  display:grid; grid-template-columns:auto 1fr auto auto; gap:14px; align-items:center; font-family:var(--head); }
.ctl button{ font-family:var(--head); font-size:0.8rem; background:var(--orange); color:#07090d; border:0; border-radius:999px; padding:8px 16px; cursor:pointer; font-weight:600; min-width:74px; }
.ctl input[type=range]{ width:100%; accent-color:var(--orange); }
.ctl input[type=search]{ font-family:var(--head); font-size:0.78rem; padding:7px 12px; border:1px solid var(--line); border-radius:999px; background:#0e1218; color:var(--ink); width:170px; }
.ctl select{ font-family:var(--head); font-size:0.76rem; background:#0e1218; color:var(--ink); border:1px solid var(--line); border-radius:8px; padding:6px 8px; }
.ctl :focus-visible{ outline:2px solid var(--gold); outline-offset:2px; }
.ticks{ display:flex; justify-content:space-between; font-size:0.64rem; color:var(--mute); margin-top:2px; }
#tip{ position:fixed; z-index:7; pointer-events:none; background:rgba(243,239,230,0.96); color:#07090d; font-family:var(--head); font-size:0.76rem; line-height:1.45; padding:8px 11px; border-radius:8px; opacity:0; transition:opacity 0.12s; max-width:280px; }
#tip b{ font-weight:600; }
.hint{ position:fixed; z-index:5; left:24px; bottom:22px; font-family:var(--head); font-size:0.68rem; color:var(--mute); max-width:300px; line-height:1.5; }
@media (max-width:820px){ .side{ display:none; } .ctl{ grid-template-columns:auto 1fr; } .ctl input[type=search], .ctl select{ display:none; } .head p.small{ display:none; } }
</style>
<canvas id="sky"></canvas><canvas id="ui"></canvas>
<div class="head">
  <span class="eyebrow">국토부 실거래 · %%PERIOD%%</span>
  <h1>서울 아파트 은하, 별 하나가 단지 하나</h1>
  <p>거래 8개월 이상인 %%N%%개 단지입니다. 가로는 그 달 평당가(로그), 세로는 첫 거래월 대비 상승률. 별의 크기는 세대수, 밝기는 그 달 거래 건수, 색은 생활권. 24개월을 재생하면 은하가 위로 흘러갑니다. 단지를 검색하면 그 별에 조명이 켜지고 24개월 궤적이 그려집니다.</p>
  <p class="small">세로축은 −40%~+120%만 표시하고 넘는 별은 가장자리에 둡니다 · 별 위에 올리면 이름 · 별을 누르면 고정, Esc 로 해제</p>
</div>
<div class="month"><div class="big" id="mo">—</div><div class="sub" id="mosub"></div></div>
<div class="side">
  <div class="box"><h3>생활권 · 눌러서 켜고 끄기</h3><div class="zones" id="zones"></div></div>
  <div class="box movers"><h3 id="mvh">이 달 크게 움직인 별</h3><div id="movers"></div></div>
</div>
<div class="ctl" role="group" aria-label="타임라인">
  <button id="play" aria-pressed="true">일시정지</button>
  <div><input id="t" type="range" min="0" max="23" step="0.01" value="0" aria-label="월 선택"><div class="ticks" id="ticks"></div></div>
  <input id="q" type="search" placeholder="단지 검색 (예: 헬리오)" aria-label="단지 검색">
  <select id="spd" aria-label="재생 속도"><option value="1.6">느리게</option><option value="1.0" selected>보통</option><option value="0.5">빠르게</option></select>
</div>
<div id="tip"></div>
<script>
var D = %%DATA%%, MONTHS = D.months, N = MONTHS.length, S = D.stars;
var ZCOL = ['#e0784f', '#e8d27a', '#c98fd6', '#5a93c9', '#6fbf8a'];   // 동남·도심·서북·서남·동북 (고정 순서)
var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
var sky = document.getElementById('sky'), ui = document.getElementById('ui'), ctx = sky.getContext('2d'), uctx = ui.getContext('2d');
var Wp, Hp, dpr = Math.min(2, devicePixelRatio || 1);
var PAD = {l: 70, r: 300, t: 250, b: 122};
var XMIN = Math.log(1000), XMAX = Math.log(32000), YMIN = -40, YMAX = 120;
function X(v){ return PAD.l + (Wp - PAD.l - PAD.r) * (Math.log(v) - XMIN) / (XMAX - XMIN); }
function Y(p){ return PAD.t + (Hp - PAD.t - PAD.b) * (1 - (Math.max(YMIN - 6, Math.min(YMAX + 6, p)) - YMIN) / (YMAX - YMIN)); }
function resize(){ Wp = innerWidth; Hp = innerHeight; PAD.r = Wp < 820 ? 24 : 300; PAD.t = Hp < 700 ? 150 : 250;
  [sky, ui].forEach(function(c){ c.width = Wp * dpr; c.height = Hp * dpr; c.style.width = Wp + 'px'; c.style.height = Hp + 'px'; });
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0); uctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.fillStyle = '#07090d'; ctx.fillRect(0, 0, Wp, Hp); drawAxes(); }
addEventListener('resize', resize);
// 별 스프라이트(방사형 글로우) 미리 렌더 — 권역별 색
var SPR = ZCOL.map(function(col){ var c = document.createElement('canvas'); c.width = c.height = 64; var g = c.getContext('2d');
  var r = g.createRadialGradient(32, 32, 0, 32, 32, 32); r.addColorStop(0, '#fff6ea'); r.addColorStop(0.22, col); r.addColorStop(0.45, col + '66'); r.addColorStop(1, col + '00');
  g.fillStyle = r; g.fillRect(0, 0, 64, 64); return c; });
S.forEach(function(s){ s.base = s.s.find(function(v){ return v; }) || s.s[0]; s.r = 1.5 + Math.sqrt(s.hh || 200) / 14; s.x = 0; s.y = 0; });
var zoneOn = [true, true, true, true, true], lit = null, m = 0, playing = !reduced, lastInt = -1, hold = 0;
function pos(s, mm){ var i = Math.floor(mm), f = mm - i, a = s.s[i], b = s.s[Math.min(N - 1, i + 1)]; var v = a + (b - a) * f; return [X(v), Y((v / s.base - 1) * 100), v]; }
function drawAxes(){
  uctx.clearRect(0, 0, Wp, Hp); uctx.font = '11px Poppins, Arial'; uctx.fillStyle = 'rgba(243,239,230,0.45)'; uctx.strokeStyle = 'rgba(243,239,230,0.07)'; uctx.lineWidth = 1;
  [1000, 2000, 4000, 8000, 16000, 32000].forEach(function(v){ var x = X(v); uctx.beginPath(); uctx.moveTo(x, PAD.t); uctx.lineTo(x, Hp - PAD.b); uctx.stroke(); uctx.textAlign = 'center'; uctx.fillText((v / 10000).toFixed(v < 10000 ? 1 : 1) + '억/평', x, Hp - PAD.b + 16); });
  for (var p = YMIN; p <= YMAX; p += 20){ var y = Y(p); uctx.beginPath(); uctx.moveTo(PAD.l, y); uctx.lineTo(Wp - PAD.r, y); uctx.strokeStyle = p === 0 ? 'rgba(243,239,230,0.22)' : 'rgba(243,239,230,0.07)'; uctx.stroke(); uctx.textAlign = 'right'; uctx.fillText((p > 0 ? '+' : '') + p + '%', PAD.l - 8, y + 4); }
  uctx.textAlign = 'left'; uctx.fillStyle = 'rgba(243,239,230,0.35)'; uctx.fillText('→ 그 달 평당가 (전용, 로그)', PAD.l, Hp - PAD.b + 34); uctx.fillText('↑ 첫 거래월 대비', PAD.l, PAD.t - 10);
}
var tip = document.getElementById('tip'), mouse = {x: -1, y: -1}, hoverS = null;
sky.addEventListener('mousemove', function(e){ mouse.x = e.clientX; mouse.y = e.clientY; });
sky.addEventListener('mouseleave', function(){ mouse.x = -1; });
sky.addEventListener('click', function(){ if (hoverS){ lit = hoverS; q.value = lit.n; } });
function nearest(){ if (mouse.x < 0) return null; var best = null, bd = 144; for (var i = 0; i < S.length; i++){ var s = S[i]; if (!zoneOn[s.z]) continue; var dx = s.x - mouse.x, dy = s.y - mouse.y, d = dx*dx + dy*dy; if (d < bd){ bd = d; best = s; } } return best; }
// UI
var zonesEl = document.getElementById('zones');
D.zones.forEach(function(z, i){ var b = document.createElement('button'); b.className = 'zone'; b.setAttribute('aria-pressed', 'true'); b.innerHTML = '<i style="background:' + ZCOL[i] + ';color:' + ZCOL[i] + '"></i>' + z + ' <span style="color:var(--mute)">' + S.filter(function(s){ return s.z === i; }).length + '</span>';
  b.addEventListener('click', function(){ zoneOn[i] = !zoneOn[i]; b.setAttribute('aria-pressed', String(zoneOn[i])); }); zonesEl.appendChild(b); });
var tEl = document.getElementById('t'), playBtn = document.getElementById('play'), spd = document.getElementById('spd'), q = document.getElementById('q');
var ticks = document.getElementById('ticks'); MONTHS.forEach(function(ym, i){ if (ym.slice(4) === '01' || i === 0 || i === N - 1){ var s = document.createElement('span'); s.textContent = ym.slice(2, 4) + '.' + ym.slice(4); ticks.appendChild(s); } });
playBtn.addEventListener('click', function(){ playing = !playing; playBtn.textContent = playing ? '일시정지' : '재생'; playBtn.setAttribute('aria-pressed', String(playing)); if (playing && m >= N - 1) m = 0; });
tEl.addEventListener('input', function(){ m = parseFloat(tEl.value); playing = false; playBtn.textContent = '재생'; playBtn.setAttribute('aria-pressed', 'false'); });
q.addEventListener('input', function(){ var v = q.value.trim().toLowerCase(); lit = v.length < 2 ? null : (S.find(function(s){ return s.n.toLowerCase().indexOf(v) >= 0 && zoneOn[s.z]; }) || null); });
addEventListener('keydown', function(e){ if (e.key === 'Escape'){ lit = null; q.value = ''; } });
var moEl = document.getElementById('mo'), moSub = document.getElementById('mosub'), mv = document.getElementById('movers'), mvh = document.getElementById('mvh');
function updateMonth(i){
  moEl.textContent = MONTHS[i].slice(0, 4) + '.' + MONTHS[i].slice(4);
  var tot = 0, up = 0; S.forEach(function(s){ tot += s.c[i] || 0; if (s.s[i] > s.base) up++; });
  moSub.textContent = '거래 ' + tot.toLocaleString() + '건 · 출발점보다 높은 별 ' + Math.round(up / S.length * 100) + '%';
  if (i === 0){ mvh.textContent = '이 달 크게 움직인 별'; mv.innerHTML = '<div class="row"><b>첫 달 — 출발선</b><span></span></div>'; return; }
  var rows = S.filter(function(s){ return !(s.m & (1 << i)) && !(s.m & (1 << (i - 1))) && (s.c[i] || 0) >= 2; })
    .map(function(s){ return [s, (s.s[i] / s.s[i - 1] - 1) * 100]; }).sort(function(a, b){ return b[1] - a[1]; });
  var top = rows.slice(0, 4), bot = rows.slice(-3).reverse();
  mvh.textContent = MONTHS[i].slice(0, 4) + '.' + MONTHS[i].slice(4) + ' 전월 대비 (거래 2건↑)';
  mv.innerHTML = top.map(function(r){ return '<div class="row up"><b>' + r[0].g.slice(0, -1) + ' ' + r[0].n + '</b><span>+' + r[1].toFixed(1) + '%</span></div>'; }).join('')
    + bot.map(function(r){ return '<div class="row dn"><b>' + r[0].g.slice(0, -1) + ' ' + r[0].n + '</b><span>' + r[1].toFixed(1) + '%</span></div>'; }).join('');
}
var last = performance.now();
function frame(now){
  var dt = Math.min(0.05, (now - last) / 1000); last = now;
  if (playing){ if (m >= N - 1){ hold += dt; if (hold > 2.5){ m = 0; hold = 0; ctx.fillStyle = '#07090d'; ctx.fillRect(0, 0, Wp, Hp); } } else m = Math.min(N - 1, m + dt / parseFloat(spd.value)); tEl.value = m.toFixed(2); }
  var mi = Math.round(m); if (mi !== lastInt){ lastInt = mi; updateMonth(mi); }
  // 잔상: 반투명으로 덮어 궤적이 서서히 사라진다
  ctx.globalCompositeOperation = 'source-over'; ctx.fillStyle = 'rgba(7,9,13,' + (playing ? 0.16 : 0.5) + ')'; ctx.fillRect(0, 0, Wp, Hp);
  ctx.globalCompositeOperation = 'source-over';   // 가산 합성은 밀집 구간이 하얗게 타서 쓰지 않는다
  for (var i = 0; i < S.length; i++){ var s = S[i]; var p = pos(s, m); s.x = p[0]; s.y = p[1]; if (!zoneOn[s.z]) continue;
    var cnt = s.c[mi] || 0, gap = (s.m & (1 << mi)) !== 0;
    var a = gap ? 0.2 : Math.min(0.95, 0.45 + cnt / 20), r = s.r * (lit === s ? 2.4 : 1) * (1 + Math.min(0.5, cnt / 30));
    ctx.globalAlpha = a; ctx.drawImage(SPR[s.z], s.x - r * 2, s.y - r * 2, r * 4, r * 4); }
  ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
  // 조명 받은 별: 궤적 + 라벨 (오버레이 캔버스)
  drawAxes();
  hoverS = nearest();
  var focus = lit || hoverS;
  if (focus){ uctx.strokeStyle = ZCOL[focus.z]; uctx.lineWidth = 1.5; uctx.globalAlpha = 0.9; uctx.beginPath();
    for (var k = 0; k <= Math.min(N - 1, Math.ceil(m)); k++){ var pp = pos(focus, Math.min(k, m)); if (k === 0) uctx.moveTo(pp[0], pp[1]); else uctx.lineTo(pp[0], pp[1]); }
    uctx.stroke(); uctx.beginPath(); uctx.arc(focus.x, focus.y, focus.r * 2 + 6, 0, Math.PI * 2); uctx.stroke(); uctx.globalAlpha = 1;
    var v = pos(focus, m)[2], ch = (v / focus.base - 1) * 100;
    tip.innerHTML = '<b>' + focus.n + '</b> · ' + focus.g + ' ' + focus.d + (focus.hh ? ' · ' + focus.hh.toLocaleString() + '세대' : '') + (focus.bt ? ' · ' + focus.bt + '년' : '') + '<br>평당 ' + Math.round(v).toLocaleString() + '만원 · 출발 대비 ' + (ch > 0 ? '+' : '') + ch.toFixed(1) + '% · 이달 거래 ' + (focus.c[mi] || 0) + '건' + (focus.jr ? ' · 전세가율 ' + focus.jr + '%' : '');
    tip.style.left = Math.min(focus.x + 16, Wp - 300) + 'px'; tip.style.top = Math.max(8, focus.y - 14) + 'px'; tip.style.opacity = 1;
  } else tip.style.opacity = 0;
  requestAnimationFrame(frame);
}
resize(); updateMonth(0); requestAnimationFrame(function(t){ last = t; frame(t); });
</script>
'''
page = page.replace('%%DATA%%', DATA).replace('%%PERIOD%%', period).replace('%%N%%', f"{len(stars):,}")
open(os.path.join(W, 'seoul_galaxy.html'), 'w', encoding='utf-8').write(page)
print(f'seoul_galaxy.html 생성 ({len(page)/1e6:.2f}MB) · 별 {len(stars)}')
