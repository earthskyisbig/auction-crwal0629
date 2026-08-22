# -*- coding: utf-8 -*-
"""입체 분석 차트 3종: 코로플레스 지도 · 구×월 매트릭스 히트맵 · 가격×상승률 버블 사분면"""
import json, math, os
W = os.path.dirname(os.path.abspath(__file__))

def _hex(c): return tuple(int(c[i:i+2], 16) for i in (1, 3, 5))
def _mix(c1, c2, t):
    a, b = _hex(c1), _hex(c2)
    return '#%02x%02x%02x' % tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))

def seq_color(t):
    """순차 램프(단일 오렌지 계열, 밝음→어두움)"""
    t = max(0.0, min(1.0, t))
    if t < 0.5: return _mix('#f6e3da', '#d97757', t * 2)
    return _mix('#d97757', '#7f3416', (t - 0.5) * 2)

def div_color(t):
    """발산 램프: -1(블루) ~ 0(중립) ~ +1(오렌지)"""
    t = max(-1.0, min(1.0, t))
    if t >= 0: return _mix('#f0ede4', '#c05a35', t)
    return _mix('#f0ede4', '#3f7fb8', -t)

# ── 1. 코로플레스 지도 ──────────────────────────────
def choropleth(mat):
    geo = json.load(open(os.path.join(W, 'seoul_geo.json')))
    pts = [(x, y) for f in geo['features'] for ring in (
        f['geometry']['coordinates'] if f['geometry']['type'] == 'Polygon'
        else [r for p in f['geometry']['coordinates'] for r in p]) for x, y in ring]
    lons = [p[0] for p in pts]; lats = [p[1] for p in pts]
    lo_x, hi_x, lo_y, hi_y = min(lons), max(lons), min(lats), max(lats)
    Wpx = 940
    kx = Wpx / (hi_x - lo_x)
    ky = kx * 1.262  # 위도 1도가 경도 1도보다 길다 (cos 37.5° 보정)
    Hpx = (hi_y - lo_y) * ky
    def P(lon, lat): return ((lon - lo_x) * kx, (hi_y - lat) * ky)
    vals = {g: d['matched_chg_pct'] for g, d in mat.items()}
    vmin, vmax = min(vals.values()), max(vals.values())
    s = [f'<svg viewBox="0 0 {Wpx} {Hpx + 54:.0f}" role="img" aria-label="구별 상승률 지도" style="width:100%;height:auto;">']
    for f in geo['features']:
        name = f['properties']['name']
        v = vals.get(name)
        t = (v - vmin) / (vmax - vmin)
        rings = (f['geometry']['coordinates'] if f['geometry']['type'] == 'Polygon'
                 else [r for p in f['geometry']['coordinates'] for r in p])
        d = []
        for ring in rings:
            seg = [f"{'M' if i == 0 else 'L'}{P(x, y)[0]:.1f},{P(x, y)[1]:.1f}" for i, (x, y) in enumerate(ring)]
            d.append(' '.join(seg) + ' Z')
        s.append(f'<path class="bar" data-tip="{name} +{v}% (매칭 지수)" d="{" ".join(d)}" '
                 f'fill="{seq_color(t)}" stroke="#faf9f5" stroke-width="1.5"/>')
        cx = sum(x for x, y in rings[0]) / len(rings[0]); cy = sum(y for x, y in rings[0]) / len(rings[0])
        px, py = P(cx, cy)
        ink = '#faf9f5' if t > 0.62 else '#141413'
        s.append(f'<text x="{px:.0f}" y="{py - 2:.0f}" font-size="11" font-weight="600" fill="{ink}" '
                 f'text-anchor="middle" font-family="Poppins,Arial" pointer-events="none">{name[:-1]}</text>')
        s.append(f'<text x="{px:.0f}" y="{py + 11:.0f}" font-size="10" fill="{ink}" '
                 f'text-anchor="middle" pointer-events="none">+{v:.0f}%</text>')
    # 범례 (그라디언트 바)
    s.append(f'<defs><linearGradient id="ramp">' + ''.join(
        f'<stop offset="{p}%" stop-color="{seq_color(p / 100)}"/>' for p in range(0, 101, 20)) + '</linearGradient></defs>')
    ly = Hpx + 22
    s.append(f'<rect x="330" y="{ly:.0f}" width="280" height="10" rx="4" fill="url(#ramp)"/>')
    s.append(f'<text x="322" y="{ly + 9:.0f}" font-size="11" fill="rgba(20,20,19,0.6)" text-anchor="end">+{vmin}%</text>')
    s.append(f'<text x="618" y="{ly + 9:.0f}" font-size="11" fill="rgba(20,20,19,0.6)">+{vmax}%</text>')
    s.append('</svg>')
    return ''.join(s)

# ── 2. 구×월 매트릭스 히트맵 ────────────────────────
def heatmap(ins, mat, rank, months):
    lab_w, cell_w, cell_h, gap = 84, 33, 21, 2
    Wpx = lab_w + 24 * (cell_w + gap) + 60
    Hpx = len(rank) * (cell_h + gap) + 58
    s = [f'<svg viewBox="0 0 {Wpx} {Hpx}" role="img" aria-label="구별 월별 평당가 지수 히트맵" style="width:100%;height:auto;">']
    for j, ym in enumerate(months):
        if ym[4:] in ('09', '01', '05'):
            s.append(f'<text x="{lab_w + j * (cell_w + gap) + cell_w / 2:.0f}" y="12" font-size="10" '
                     f'fill="rgba(20,20,19,0.5)" text-anchor="middle">{ym[2:4]}.{ym[4:]}</text>')
    for i, g in enumerate(rank):
        d = ins[g]
        base = d['first6_avg']
        y = 20 + i * (cell_h + gap)
        s.append(f'<text x="{lab_w - 8}" y="{y + 15}" font-size="11.5" fill="#141413" text-anchor="end">{g}</text>')
        for j, v in enumerate(d['smooth']):
            x = lab_w + j * (cell_w + gap)
            if v is None or not base:
                s.append(f'<rect x="{x}" y="{y}" width="{cell_w}" height="{cell_h}" rx="3" fill="#f0ede4"/>')
                continue
            idx = v / base * 100
            col = div_color((idx - 100) / 38)
            s.append(f'<rect class="bar" data-tip="{g} {months[j][:4]}.{months[j][4:]} — 지수 {idx:.0f} (평당 {v:,}만원)" '
                     f'x="{x}" y="{y}" width="{cell_w}" height="{cell_h}" rx="3" fill="{col}"/>')
    # 범례
    ly = Hpx - 20
    s.append('<defs><linearGradient id="dramp">' + ''.join(
        f'<stop offset="{p}%" stop-color="{div_color(p / 50 - 1)}"/>' for p in range(0, 101, 10)) + '</linearGradient></defs>')
    s.append(f'<rect x="{lab_w}" y="{ly}" width="240" height="10" rx="4" fill="url(#dramp)"/>')
    s.append(f'<text x="{lab_w - 6}" y="{ly + 9}" font-size="10.5" fill="rgba(20,20,19,0.6)" text-anchor="end">62</text>')
    s.append(f'<text x="{lab_w + 246}" y="{ly + 9}" font-size="10.5" fill="rgba(20,20,19,0.6)">138</text>')
    s.append(f'<text x="{lab_w + 290}" y="{ly + 9}" font-size="10.5" fill="rgba(20,20,19,0.6)">지수 100(중립색) = 그 구의 첫 6개월 평균 평당가</text>')
    s.append('</svg>')
    return ''.join(s)

# ── 3. 가격 × 상승률 버블 사분면 ────────────────────
def scatter(ins, mat, apthh, rank):
    Wpx, Hpx, pl, pr, pt, pb = 940, 480, 64, 30, 20, 44
    xmin, xmax, ymin, ymax = 2000, 12500, 0, 40
    pw, ph = Wpx - pl - pr, Hpx - pt - pb
    def X(v): return pl + pw * (v - xmin) / (xmax - xmin)
    def Y(v): return pt + ph * (1 - (v - ymin) / (ymax - ymin))
    med_x = 5000; med_y = 21.4  # 중위 기준선(최근 평당 5천만·상승률 중앙값)
    s = [f'<svg viewBox="0 0 {Wpx} {Hpx}" role="img" aria-label="평당가 대비 상승률 버블" style="width:100%;height:auto;">']
    for gx in range(2000, 12501, 2000):
        s.append(f'<line x1="{X(gx):.0f}" y1="{pt}" x2="{X(gx):.0f}" y2="{Hpx - pb}" stroke="rgba(20,20,19,0.07)"/>')
        s.append(f'<text x="{X(gx):.0f}" y="{Hpx - 24}" font-size="11" fill="rgba(20,20,19,0.5)" text-anchor="middle">{gx / 10000:.1f}억</text>')
    for gy in range(0, 41, 10):
        s.append(f'<line x1="{pl}" y1="{Y(gy):.0f}" x2="{Wpx - pr}" y2="{Y(gy):.0f}" stroke="rgba(20,20,19,0.07)"/>')
        s.append(f'<text x="{pl - 8}" y="{Y(gy) + 4:.0f}" font-size="11" fill="rgba(20,20,19,0.5)" text-anchor="end">+{gy}%</text>')
    s.append(f'<line x1="{X(med_x):.0f}" y1="{pt}" x2="{X(med_x):.0f}" y2="{Hpx - pb}" stroke="rgba(20,20,19,0.25)" stroke-dasharray="4 4"/>')
    s.append(f'<line x1="{pl}" y1="{Y(med_y):.0f}" x2="{Wpx - pr}" y2="{Y(med_y):.0f}" stroke="rgba(20,20,19,0.25)" stroke-dasharray="4 4"/>')
    s.append(f'<text x="{Wpx - pr - 4}" y="{Y(med_y) - 6:.0f}" font-size="10.5" fill="rgba(20,20,19,0.45)" text-anchor="end">상승률 중앙값 +{med_y}%</text>')
    s.append(f'<text x="{X(med_x) + 6:.0f}" y="{pt + 12}" font-size="10.5" fill="rgba(20,20,19,0.45)">평당 5천만원</text>')
    s.append(f'<text x="{Wpx - pr - 4}" y="{Hpx - 6}" font-size="10.5" fill="rgba(20,20,19,0.45)" text-anchor="end">→ 최근 6개월 평당가</text>')
    LABEL = {'강남구', '서초구', '송파구', '성동구', '용산구', '마포구', '동작구', '노원구', '도봉구', '금천구', '강동구', '양천구', '광진구'}
    labels = []
    for g in sorted(rank, key=lambda g: -apthh[g]):
        d, v = ins[g], mat[g]['matched_chg_pct']
        x, y = X(d['last6_avg']), Y(v)
        r = max(5, math.sqrt(apthh[g] / 1000) * 2.4)
        s.append(f'<circle class="bar" data-tip="{g} — 평당 {d["last6_avg"]:,}만원 · +{v}% · 아파트 {apthh[g]:,}세대" '
                 f'cx="{x:.0f}" cy="{y:.0f}" r="{r:.0f}" fill="#cf6a48" fill-opacity="0.45" stroke="#faf9f5" stroke-width="2"/>')
        if g in LABEL:
            ly_ = y + r + 13 if g == '강남구' else y - r - 4
            labels.append(f'<text x="{x:.0f}" y="{ly_:.0f}" font-size="11" font-weight="600" fill="#141413" '
                          f'text-anchor="middle" font-family="Poppins,Arial" pointer-events="none">{g[:-1]}</text>')
    s += labels  # 라벨은 항상 원 위 레이어
    s.append('</svg>')
    return ''.join(s)

# ── 4. 한강벨트 법정동 드릴다운 막대 ─────────────────
GU_COLORS = {'성동구': '#4f7d3a', '광진구': '#8a6bb8', '동작구': '#cf6a48', '송파구': '#3f7fb8', '강동구': '#b0893a'}
def belt_dongs():
    data = json.load(open(os.path.join(W, 'belt_dong.json')))
    rows = [(gu, r) for gu, rs in data.items() for r in rs]
    rows.sort(key=lambda x: -x[1]['chg'])
    w, rh, lab_w, val_w = 940, 24, 130, 62
    plot_w = w - lab_w - val_w
    vmax = max(r['chg'] for _, r in rows)
    h = len(rows) * rh + 34
    s = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="한강벨트 법정동별 상승률" style="width:100%;height:auto;">']
    for gx in range(0, 61, 10):
        x = lab_w + plot_w * gx / max(60, vmax)
        s.append(f'<line x1="{x:.0f}" y1="4" x2="{x:.0f}" y2="{h-28}" stroke="rgba(20,20,19,0.08)"/>')
        s.append(f'<text x="{x:.0f}" y="{h-12}" font-size="11" fill="rgba(20,20,19,0.5)" text-anchor="middle">{gx}%</text>')
    for i, (gu, r) in enumerate(rows):
        y = i * rh + 6
        bw = plot_w * r['chg'] / max(60, vmax)
        s.append(f'<text x="{lab_w-8}" y="{y+12}" font-size="11.5" fill="#141413" text-anchor="end">{gu[:2]} {r["dong"]}</text>')
        s.append(f'<rect class="bar" data-tip="{gu} {r["dong"]} +{r["chg"]}% · {r["pairs"]}개 단지·평형 쌍 · 최근 평당 {r["last_pp"]:,}만원 · 24개월 거래 {r["trades"]:,}건" '
                 f'x="{lab_w}" y="{y}" width="{bw:.0f}" height="{rh-8}" rx="4" fill="{GU_COLORS[gu]}" fill-opacity="0.85"/>')
        s.append(f'<text x="{lab_w+bw+6:.0f}" y="{y+12}" font-size="11" fill="rgba(20,20,19,0.75)" font-family="Poppins,Arial">+{r["chg"]}%</text>')
    s.append('</svg>')
    return ''.join(s)

# ── 5. 전세가율 코로플레스 (블루 순차 램프) ─────────────
def seq_blue(t):
    t = max(0.0, min(1.0, t))
    if t < 0.5: return _mix('#e2ebf4', '#5b90c2', t * 2)
    return _mix('#5b90c2', '#1d4771', (t - 0.5) * 2)

def jeonse_map(jr):
    geo = json.load(open(os.path.join(W, 'seoul_geo.json')))
    pts = [(x, y) for f in geo['features'] for ring in (
        f['geometry']['coordinates'] if f['geometry']['type'] == 'Polygon'
        else [r for p in f['geometry']['coordinates'] for r in p]) for x, y in ring]
    lons = [p[0] for p in pts]; lats = [p[1] for p in pts]
    lo_x, hi_x, lo_y, hi_y = min(lons), max(lons), min(lats), max(lats)
    Wpx = 940
    kx = Wpx / (hi_x - lo_x); ky = kx * 1.262
    Hpx = (hi_y - lo_y) * ky
    def P(lon, lat): return ((lon - lo_x) * kx, (hi_y - lat) * ky)
    vals = {g: d['jeonse_ratio'] for g, d in jr.items() if d['jeonse_ratio'] is not None}
    vmin, vmax = min(vals.values()), max(vals.values())
    s = [f'<svg viewBox="0 0 {Wpx} {Hpx + 54:.0f}" role="img" aria-label="구별 전세가율 지도" style="width:100%;height:auto;">']
    for f in geo['features']:
        name = f['properties']['name']
        v = vals.get(name)
        t = (v - vmin) / (vmax - vmin)
        rings = (f['geometry']['coordinates'] if f['geometry']['type'] == 'Polygon'
                 else [r for p in f['geometry']['coordinates'] for r in p])
        d = []
        for ring in rings:
            seg = [f"{'M' if i == 0 else 'L'}{P(x, y)[0]:.1f},{P(x, y)[1]:.1f}" for i, (x, y) in enumerate(ring)]
            d.append(' '.join(seg) + ' Z')
        s.append(f'<path class="bar" data-tip="{name} 전세가율 {v}% ({jr[name]["pairs"]}개 단지·평형 쌍)" d="{" ".join(d)}" '
                 f'fill="{seq_blue(t)}" stroke="#faf9f5" stroke-width="1.5"/>')
        cx = sum(x for x, y in rings[0]) / len(rings[0]); cy = sum(y for x, y in rings[0]) / len(rings[0])
        px, py = P(cx, cy)
        ink = '#faf9f5' if t > 0.6 else '#141413'
        s.append(f'<text x="{px:.0f}" y="{py - 2:.0f}" font-size="11" font-weight="600" fill="{ink}" '
                 f'text-anchor="middle" font-family="Poppins,Arial" pointer-events="none">{name[:-1]}</text>')
        s.append(f'<text x="{px:.0f}" y="{py + 11:.0f}" font-size="10" fill="{ink}" '
                 f'text-anchor="middle" pointer-events="none">{v:.0f}%</text>')
    s.append('<defs><linearGradient id="bramp">' + ''.join(
        f'<stop offset="{p}%" stop-color="{seq_blue(p / 100)}"/>' for p in range(0, 101, 20)) + '</linearGradient></defs>')
    ly = Hpx + 22
    s.append(f'<rect x="330" y="{ly:.0f}" width="280" height="10" rx="4" fill="url(#bramp)"/>')
    s.append(f'<text x="322" y="{ly + 9:.0f}" font-size="11" fill="rgba(20,20,19,0.6)" text-anchor="end">{vmin}%</text>')
    s.append(f'<text x="618" y="{ly + 9:.0f}" font-size="11" fill="rgba(20,20,19,0.6)">{vmax}%</text>')
    s.append('</svg>')
    return ''.join(s)
