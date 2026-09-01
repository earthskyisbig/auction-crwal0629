# -*- coding: utf-8 -*-
"""서울 평당가 지형 — 25개 구를 평당가 높이로 세운 3D 타임랩스 (three.js). → seoul_terrain.html
   데이터: seoul_geo.json(구 경계), seoul_gu_insights.json(월별 평당가·거래량), seoul_gu_matched.json"""
import json, os
from datetime import date
W = os.path.dirname(os.path.abspath(__file__))
geo = json.load(open(os.path.join(W, 'seoul_geo.json'), encoding='utf-8'))
ins = json.load(open(os.path.join(W, 'seoul_gu_insights.json'), encoding='utf-8'))
mat = json.load(open(os.path.join(W, 'seoul_gu_matched.json'), encoding='utf-8'))
MONTHS = ins['강남구']['months']

# 경계 좌표를 미리 평면 좌표(단위: 씬 유닛)로 변환해 페이지 JS 를 가볍게 한다
pts = [(x, y) for f in geo['features'] for x, y in f['geometry']['coordinates'][0]]
lo_x, hi_x = min(p[0] for p in pts), max(p[0] for p in pts)
lo_y, hi_y = min(p[1] for p in pts), max(p[1] for p in pts)
SCALE = 120.0 / (hi_x - lo_x)
KY = SCALE * 1.262
cx, cz = (hi_x - lo_x) * SCALE / 2, (hi_y - lo_y) * KY / 2
gus = []
for f in geo['features']:
    name = f['properties']['name']
    ring = [(round((x - lo_x) * SCALE - cx, 2), round((hi_y - y) * KY - cz, 2)) for x, y in f['geometry']['coordinates'][0]]
    d = ins[name]
    gus.append({'n': name, 'ring': ring, 's': d['smooth'], 'c': d['count'], 'base': d['first6_avg'],
                'last6': d['last6_avg'], 'm': mat[name]['matched_chg_pct'], 'pairs': mat[name]['pairs']})
DATA = json.dumps({'months': MONTHS, 'gus': gus}, ensure_ascii=False, separators=(',', ':'))
today = date.today().strftime('%Y.%m.%d')
period = f"{MONTHS[0][:4]}.{MONTHS[0][4:]} ~ {MONTHS[-1][:4]}.{MONTHS[-1][4:]}"

page = r'''<title>서울 평당가 지형</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Poppins:wght@500;600&family=Lora:ital@0;1&display=swap">
<style>
:root{ --bg:#0e1116; --bg2:#151a21; --ink:#f3efe6; --mute:rgba(243,239,230,0.62); --line:rgba(243,239,230,0.12);
  --orange:#e0784f; --blue:#5a93c9; --gold:#d9b25a;
  --head:'Poppins','Apple SD Gothic Neo','Malgun Gothic',Arial,sans-serif; --body:'Lora','Apple SD Gothic Neo','Malgun Gothic',Georgia,serif; }
html,body{ height:100%; }
body{ margin:0; background:var(--bg); color:var(--ink); font-family:var(--body); overflow:hidden; }
#c{ position:fixed; inset:0; display:block; }
.panel{ position:fixed; z-index:5; }
.head{ top:24px; left:24px; max-width:420px; pointer-events:none; }
.head h1{ font-family:var(--head); font-weight:600; font-size:clamp(1.4rem,2.6vw,2rem); margin:8px 0 6px; letter-spacing:-0.01em; text-wrap:balance; }
.head p{ margin:0; color:var(--mute); font-size:0.9rem; line-height:1.55; font-style:italic; }
.eyebrow{ font-family:var(--head); font-size:0.66rem; letter-spacing:0.12em; text-transform:uppercase; color:var(--mute); display:inline-flex; gap:0.5em; align-items:center; }
.eyebrow::before{ content:''; width:6px; height:6px; border-radius:50%; background:var(--orange); }
.month{ position:fixed; z-index:5; right:28px; top:22px; text-align:right; pointer-events:none; }
.month .big{ font-family:var(--head); font-weight:600; font-size:clamp(2rem,5vw,3.6rem); line-height:1; font-variant-numeric:tabular-nums; letter-spacing:-0.02em; }
.month .sub{ color:var(--mute); font-size:0.82rem; margin-top:6px; font-family:var(--head); }
.rank{ position:fixed; z-index:5; right:28px; top:118px; width:228px; font-family:var(--head); font-size:0.74rem; }
.rank .row{ display:grid; grid-template-columns:52px 1fr 54px; gap:8px; align-items:center; height:17px; color:var(--mute); }
.rank .row b{ color:var(--ink); font-weight:500; }
.rank .bar{ height:5px; border-radius:3px; background:var(--orange); transform-origin:left; transition:transform 0.35s ease, background 0.35s ease; }
.rank .v{ text-align:right; font-variant-numeric:tabular-nums; }
.ctl{ position:fixed; z-index:6; left:50%; bottom:22px; transform:translateX(-50%); width:min(760px,calc(100% - 40px));
  background:rgba(21,26,33,0.82); backdrop-filter:blur(8px); border:1px solid var(--line); border-radius:16px; padding:12px 16px;
  display:grid; grid-template-columns:auto 1fr auto; gap:14px; align-items:center; font-family:var(--head); }
.ctl button{ font-family:var(--head); font-size:0.8rem; background:var(--orange); color:#0e1116; border:0; border-radius:999px; padding:8px 16px; cursor:pointer; font-weight:600; min-width:74px; }
.ctl button:focus-visible, .ctl input:focus-visible, .ctl select:focus-visible{ outline:2px solid var(--gold); outline-offset:2px; }
.ctl input[type=range]{ width:100%; accent-color:var(--orange); }
.ticks{ display:flex; justify-content:space-between; font-size:0.64rem; color:var(--mute); margin-top:2px; }
.ctl select{ font-family:var(--head); font-size:0.76rem; background:var(--bg2); color:var(--ink); border:1px solid var(--line); border-radius:8px; padding:6px 8px; }
.legend{ position:fixed; z-index:5; left:24px; bottom:96px; font-family:var(--head); font-size:0.7rem; color:var(--mute); }
.legend .ramp{ width:180px; height:8px; border-radius:4px; background:linear-gradient(90deg,#5a93c9,#3a3f47 50%,#e0784f); margin:6px 0 4px; }
.legend .lr{ display:flex; justify-content:space-between; width:180px; }
#tip{ position:fixed; z-index:7; pointer-events:none; background:rgba(243,239,230,0.96); color:#0e1116; font-family:var(--head); font-size:0.76rem; line-height:1.45; padding:8px 11px; border-radius:8px; opacity:0; transition:opacity 0.12s; max-width:260px; }
#tip b{ font-weight:600; }
.hint{ position:fixed; z-index:5; left:24px; bottom:22px; font-family:var(--head); font-size:0.68rem; color:var(--mute); }
@media (max-width:760px){ .rank{ display:none; } .head{ max-width:70vw; } .legend{ bottom:110px; } }
@media (prefers-reduced-motion: reduce){ .rank .bar{ transition:none; } }
</style>
<canvas id="c"></canvas>
<div class="panel head">
  <span class="eyebrow">국토부 실거래 · %%PERIOD%%</span>
  <h1>서울 평당가 지형, 24개월을 한 번에</h1>
  <p>25개 구를 그 달 평당가(전용 기준, 3개월 이동중앙값) 높이로 세웠습니다. 색은 첫 6개월 평균 대비 지수 — 주황일수록 출발점보다 오른 달, 파랑은 내린 달. 튀는 불꽃은 그 달 실거래 건수입니다. 드래그로 돌리고 휠로 당겨 보세요.</p>
</div>
<div class="month"><div class="big" id="mo">—</div><div class="sub" id="mosub">평당가 지수 · 거래</div></div>
<div class="rank" id="rank" aria-live="off"></div>
<div class="legend"><div>첫 6개월 평균 = 100</div><div class="ramp"></div><div class="lr"><span id="lg0">70</span><span>100</span><span id="lg1">130</span></div></div>
<div class="hint" id="hint">높이 = 평당가 · 1억 = 20유닛</div>
<div class="ctl" role="group" aria-label="타임라인">
  <button id="play" aria-pressed="true">일시정지</button>
  <div><input id="t" type="range" min="0" max="23" step="0.01" value="0" aria-label="월 선택"><div class="ticks" id="ticks"></div></div>
  <select id="spd" aria-label="재생 속도"><option value="1.4">느리게</option><option value="0.9" selected>보통</option><option value="0.45">빠르게</option></select>
</div>
<div id="tip"></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
var D = %%DATA%%;
var MONTHS = D.months, GUS = D.gus, N = MONTHS.length;
var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
var H_PER_MAN = 20 / 10000;          // 평당 1억(=10000만원) → 20 유닛
var lerp = function(a, b, t){ return a + (b - a) * t; };
function hexMix(c1, c2, t){ var a = parseInt(c1.slice(1),16), b = parseInt(c2.slice(1),16);
  var r = Math.round(((a>>16)&255) + (((b>>16)&255) - ((a>>16)&255))*t), g = Math.round(((a>>8)&255) + (((b>>8)&255) - ((a>>8)&255))*t), bl = Math.round((a&255) + ((b&255) - (a&255))*t);
  return (r<<16)|(g<<8)|bl; }
// 지수 편차 스케일: 데이터의 최대 편차(최소 20)
var span = 20; GUS.forEach(function(g){ g.s.forEach(function(v){ if (v && g.base) span = Math.max(span, Math.abs(v/g.base*100-100)); }); });
document.getElementById('lg0').textContent = Math.round(100 - span); document.getElementById('lg1').textContent = Math.round(100 + span);
function idxColor(idx){ var t = Math.max(-1, Math.min(1, (idx - 100) / span)); return t >= 0 ? hexMix('#3a3f47', '#e0784f', t) : hexMix('#3a3f47', '#5a93c9', -t); }
// 월 사이 보간된 평당가 (빈 달은 이웃 값)
function valAt(g, m){
  var i = Math.floor(m), f = m - i, a = g.s[i], b = g.s[Math.min(N-1, i+1)];
  if (a == null) a = b; if (b == null) b = a; if (a == null) return 0; return lerp(a, b, f); }

// ── three.js 씬 ─────────────────────────────────────────
var canvas = document.getElementById('c');
var renderer = new THREE.WebGLRenderer({canvas: canvas, antialias: true});
renderer.setPixelRatio(Math.min(2, window.devicePixelRatio)); renderer.setSize(innerWidth, innerHeight);
renderer.outputEncoding = THREE.sRGBEncoding;
var scene = new THREE.Scene(); scene.background = new THREE.Color(0x0e1116); scene.fog = new THREE.Fog(0x0e1116, 220, 420);
var camera = new THREE.PerspectiveCamera(38, innerWidth/innerHeight, 1, 1000);
scene.add(new THREE.HemisphereLight(0xf3efe6, 0x1b2230, 0.85));
var sun = new THREE.DirectionalLight(0xffe8d0, 0.9); sun.position.set(-60, 120, 40); scene.add(sun);
var ground = new THREE.Mesh(new THREE.PlaneGeometry(600, 600), new THREE.MeshStandardMaterial({color: 0x12161c, roughness: 1}));
ground.rotation.x = -Math.PI/2; ground.position.y = -0.05; scene.add(ground);
var grid = new THREE.GridHelper(400, 40, 0x232a33, 0x1a2027); grid.position.y = 0; scene.add(grid);

var meshes = [], labels = [];
function makeLabel(text){ var cv = document.createElement('canvas'); cv.width = 256; cv.height = 96; var sp = new THREE.Sprite(new THREE.SpriteMaterial({map: new THREE.CanvasTexture(cv), transparent: true, depthTest: false}));
  sp.scale.set(16, 6, 1); sp.userData.cv = cv; setLabel(sp, text, ''); return sp; }
function setLabel(sp, line1, line2){ var cv = sp.userData.cv, ctx = cv.getContext('2d'); ctx.clearRect(0,0,256,96);
  ctx.font = '600 30px Poppins, "Apple SD Gothic Neo", Arial'; ctx.textAlign = 'center'; ctx.fillStyle = '#f3efe6'; ctx.shadowColor = 'rgba(0,0,0,0.8)'; ctx.shadowBlur = 8; ctx.fillText(line1, 128, 40);
  ctx.font = '500 24px Poppins, Arial'; ctx.fillStyle = 'rgba(243,239,230,0.75)'; ctx.fillText(line2, 128, 74); sp.material.map.needsUpdate = true; }
GUS.forEach(function(g){
  var shape = new THREE.Shape(); g.ring.forEach(function(p, i){ if (i === 0) shape.moveTo(p[0], -p[1]); else shape.lineTo(p[0], -p[1]); });
  var geom = new THREE.ExtrudeGeometry(shape, {depth: 1, bevelEnabled: false});
  var m = new THREE.Mesh(geom, new THREE.MeshStandardMaterial({color: 0x3a3f47, roughness: 0.75, metalness: 0.05, flatShading: true}));
  m.rotation.x = -Math.PI/2; m.scale.z = 0.01; m.userData = g; scene.add(m); meshes.push(m);
  var edge = new THREE.LineSegments(new THREE.EdgesGeometry(geom, 30), new THREE.LineBasicMaterial({color: 0x0e1116, transparent: true, opacity: 0.55}));
  m.add(edge);
  var cx = 0, cz = 0; g.ring.forEach(function(p){ cx += p[0]; cz += p[1]; }); cx /= g.ring.length; cz /= g.ring.length; g.cx = cx; g.cz = cz;
  var lb = makeLabel(g.n); scene.add(lb); labels.push(lb); g.label = lb;
});

// 불꽃 파티클: 그 달 거래 건수만큼 구 위에서 솟아 사라진다
var PMAX = 3000, pPos = new Float32Array(PMAX*3), pLife = new Float32Array(PMAX), pVel = new Float32Array(PMAX), pCount = 0, pHead = 0;
var pGeom = new THREE.BufferGeometry(); pGeom.setAttribute('position', new THREE.BufferAttribute(pPos, 3));
var pMat = new THREE.PointsMaterial({color: 0xf3d9a4, size: 1.1, transparent: true, opacity: 0.9, sizeAttenuation: true, depthWrite: false});
var points = new THREE.Points(pGeom, pMat); scene.add(points);
function spawn(g, n, h){ for (var k = 0; k < n; k++){ var i = pHead; pHead = (pHead + 1) % PMAX; pCount = Math.min(PMAX, pCount + 1);
  var p = g.ring[Math.floor(Math.random()*g.ring.length)];  // 경계와 중심 사이 임의 지점
  var t = 0.15 + Math.random()*0.8; pPos[i*3] = lerp(g.cx, p[0], t); pPos[i*3+1] = h + 0.3; pPos[i*3+2] = lerp(g.cz, p[1], t);
  pLife[i] = 1; pVel[i] = 6 + Math.random()*10; } }

// ── 카메라 (직접 구현한 궤도) ───────────────────────────
var cam = {th: -0.55, ph: 0.98, r: 210, tx: 0, ty: 12, tz: 0, auto: !reduced};
function applyCam(){ camera.position.set(cam.tx + cam.r*Math.sin(cam.ph)*Math.sin(cam.th), cam.ty + cam.r*Math.cos(cam.ph), cam.tz + cam.r*Math.sin(cam.ph)*Math.cos(cam.th)); camera.lookAt(cam.tx, cam.ty, cam.tz); }
var drag = null;
canvas.addEventListener('pointerdown', function(e){ drag = {x: e.clientX, y: e.clientY, th: cam.th, ph: cam.ph}; cam.auto = false; canvas.setPointerCapture(e.pointerId); });
canvas.addEventListener('pointermove', function(e){ mouse.x = (e.clientX/innerWidth)*2-1; mouse.y = -(e.clientY/innerHeight)*2+1; mouse.cx = e.clientX; mouse.cy = e.clientY;
  if (!drag) return; cam.th = drag.th - (e.clientX - drag.x)*0.006; cam.ph = Math.max(0.25, Math.min(1.45, drag.ph + (e.clientY - drag.y)*0.005)); });
canvas.addEventListener('pointerup', function(){ drag = null; }); canvas.addEventListener('pointercancel', function(){ drag = null; });
canvas.addEventListener('wheel', function(e){ e.preventDefault(); cam.r = Math.max(90, Math.min(420, cam.r * (1 + e.deltaY*0.001))); }, {passive: false});
addEventListener('resize', function(){ renderer.setSize(innerWidth, innerHeight); camera.aspect = innerWidth/innerHeight; camera.updateProjectionMatrix(); });

// ── 타임라인 ─────────────────────────────────────────────
var tEl = document.getElementById('t'), playBtn = document.getElementById('play'), spd = document.getElementById('spd');
var playing = !reduced, m = 0, lastInt = -1, intro = reduced ? 1 : 0, holdEnd = 0;
var ticks = document.getElementById('ticks'); MONTHS.forEach(function(ym, i){ if (ym.slice(4) === '01' || i === 0 || i === N-1){ var s = document.createElement('span'); s.textContent = ym.slice(2,4)+'.'+ym.slice(4); ticks.appendChild(s); } });
playBtn.addEventListener('click', function(){ playing = !playing; playBtn.textContent = playing ? '일시정지' : '재생'; playBtn.setAttribute('aria-pressed', String(playing)); if (playing && m >= N-1) m = 0; });
tEl.addEventListener('input', function(){ m = parseFloat(tEl.value); playing = false; playBtn.textContent = '재생'; playBtn.setAttribute('aria-pressed', 'false'); });
var moEl = document.getElementById('mo'), moSub = document.getElementById('mosub'), rankEl = document.getElementById('rank');
var rankRows = GUS.map(function(g){ var r = document.createElement('div'); r.className = 'row'; r.innerHTML = '<b></b><div class="bar"></div><span class="v"></span>'; rankEl.appendChild(r); return r; });
function updateMonthUI(i){
  var ym = MONTHS[i]; moEl.textContent = ym.slice(0,4) + '.' + ym.slice(4);
  var total = 0; GUS.forEach(function(g){ total += g.c[i] || 0; });
  moSub.textContent = '서울 거래 ' + total.toLocaleString() + '건 · 첫 6개월 대비 지수';
  var order = GUS.slice().sort(function(a, b){ return (b.s[i]||0) - (a.s[i]||0); });
  var top = order[0].s[i] || 1;
  order.forEach(function(g, k){ var r = rankRows[k], v = g.s[i]; r.children[0].textContent = g.n.slice(0,-1);
    r.children[1].style.transform = 'scaleX(' + ((v||0)/top).toFixed(3) + ')'; r.children[1].style.background = '#' + ('000000' + idxColor(g.base && v ? v/g.base*100 : 100).toString(16)).slice(-6);
    r.children[2].textContent = v ? (v/10000).toFixed(2) + '억' : '—'; });
  GUS.forEach(function(g){ var v = g.s[i]; setLabel(g.label, g.n, v ? (v/10000).toFixed(2) + '억 · ' + (g.c[i]||0) + '건' : '—'); });
}

// ── 호버 툴팁 ─────────────────────────────────────────────
var ray = new THREE.Raycaster(), mouse = {x: -2, y: -2, cx: 0, cy: 0}, tip = document.getElementById('tip'), hovered = null;
function pickTip(){
  ray.setFromCamera(mouse, camera); var hit = ray.intersectObjects(meshes, false)[0];
  var g = hit ? hit.object.userData : null;
  if (g !== hovered){ hovered = g; meshes.forEach(function(mm){ mm.material.emissive.setHex(mm.userData === g ? 0x3a2418 : 0x000000); }); }
  if (!g){ tip.style.opacity = 0; return; }
  var i = Math.round(m), v = g.s[i], idx = (v && g.base) ? Math.round(v/g.base*100) : null;
  tip.innerHTML = '<b>' + g.n + '</b> · ' + MONTHS[i].slice(0,4) + '.' + MONTHS[i].slice(4) + '<br>평당 ' + (v ? v.toLocaleString() + '만원' : '—') + (idx ? ' · 지수 ' + idx : '') + ' · 거래 ' + (g.c[i]||0) + '건<br>2년 매칭 지수 ' + (g.m == null ? '—' : (g.m > 0 ? '+' : '') + g.m + '%') + ' (' + g.pairs + '쌍)';
  tip.style.left = Math.min(mouse.cx + 14, innerWidth - 280) + 'px'; tip.style.top = (mouse.cy - 12) + 'px'; tip.style.opacity = 1;
}

// ── 루프 ─────────────────────────────────────────────────
var clock = new THREE.Clock();
function frame(){
  var dt = Math.min(0.05, clock.getDelta());
  if (intro < 1) intro = Math.min(1, intro + dt / 1.4);
  var ease = 1 - Math.pow(1 - intro, 3);
  if (playing && intro >= 1){
    if (m >= N - 1){ holdEnd += dt; if (holdEnd > 2.2){ m = 0; holdEnd = 0; } }
    else m = Math.min(N - 1, m + dt / parseFloat(spd.value));
    tEl.value = m.toFixed(2);
  }
  var mi = Math.round(m);
  if (mi !== lastInt){ lastInt = mi; updateMonthUI(mi); if (intro >= 1 && !reduced) GUS.forEach(function(g){ spawn(g, Math.round((g.c[mi]||0) / 8), valAt(g, m) * H_PER_MAN); }); }
  meshes.forEach(function(mm){ var g = mm.userData, v = valAt(g, m), h = Math.max(0.05, v * H_PER_MAN * ease);
    mm.scale.z = h; mm.material.color.setHex(idxColor(g.base && v ? v/g.base*100 : 100));
    g.label.position.set(g.cx, h + 3.8, g.cz); });
  // 파티클
  for (var i = 0; i < pCount; i++){ if (pLife[i] <= 0) continue; pLife[i] -= dt*0.6; pPos[i*3+1] += pVel[i]*dt; pVel[i] *= 0.97; if (pLife[i] <= 0) pPos[i*3+1] = -50; }
  pGeom.attributes.position.needsUpdate = true; pMat.opacity = 0.85;
  if (cam.auto) cam.th += dt * 0.06;
  applyCam(); pickTip(); renderer.render(scene, camera); requestAnimationFrame(frame);
}
updateMonthUI(0); applyCam(); frame();
</script>
'''
page = page.replace('%%DATA%%', DATA).replace('%%PERIOD%%', period)
open(os.path.join(W, 'seoul_terrain.html'), 'w', encoding='utf-8').write(page)
print(f'seoul_terrain.html 생성 ({len(page)/1e3:.0f}KB)')
