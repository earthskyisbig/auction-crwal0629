# -*- coding: utf-8 -*-
"""서울 84㎡ 가격 지도 — 화면 단계: p84_data.json + p84_template.html → seoul84_report.html

문장(헤드라인·지도 설명·σ 해설·재건축/신축 해설·순위 이동)은 전부 p84_data.json 에서 만든다.
분기마다 숫자와 구 이름이 바뀌어도 고칠 필요가 없게 하는 것이 목적이다.
아티팩트: https://claude.ai/artifact/3srFbVLVrNQ5cqRGRN41W6 (재발행은 url 파라미터 필수)
"""
import html, json, os, random
from datetime import date

W = os.path.dirname(os.path.abspath(__file__))
esc = html.escape


def eok(v): return f'{v / 1e4:.1f}'


def josa(word, pair='은는'):
    """마지막 한글 글자의 받침으로 조사 선택. josa('양천') → '양천은', josa('도봉') → '도봉은', josa('강서') → '강서는'."""
    import re as _re
    core = _re.sub(r'<[^>]+>', '', word)
    if core.endswith('%'):
        core = core + '트'   # '퍼센트'로 읽는다
    for ch in reversed(core):
        if '가' <= ch <= '힣':
            jong = (ord(ch) - 0xAC00) % 28
            if pair == '으로로':
                return word + ('로' if jong in (0, 8) else '으로')
            return word + (pair[0] if jong else pair[1])
        if ch.isdigit():   # 숫자 읽기: 0·1·3·6·7·8 은 받침 있음(1·7·8 은 ㄹ 받침)
            if pair == '으로로':
                return word + ('으로' if ch in '036' else '로')
            return word + (pair[0] if ch in '013678' else pair[1])
    return word + pair[1]
def short(g): return g[:-1] if g.endswith('구') and len(g) > 2 else g
def pct(v, sign=True): return (f'{v * 100:+.0f}%' if sign else f'{v * 100:.0f}%').replace('-', '−')
def ym_dot(ym): return f'{ym[:4]}.{ym[4:]}'
def names(gs): return '·'.join(short(g) for g in gs)


# ---------------- 서술 (순수 함수) ----------------
def narrative(D):
    G = D['gu']; GUS = list(G)
    T = {g: G[g]['t'] for g in GUS}
    by_med = sorted(GUS, key=lambda g: -G[g]['med6'])
    hi, lo = by_med[0], by_med[-1]
    ratio = G[hi]['med6'] / G[lo]['med6']
    dev = D['dev']; vd = D['vardec']
    n = {}
    n['PERIOD'] = f"{ym_dot(D['m6'][0])}–{D['m6'][1][4:]}"
    n['H1'] = f'같은 84㎡, 서울에서는 {ratio:.0f}배가 벌어진다'
    n['KPI1'] = f"{eok(G[hi]['med6'])}억 ↔ {eok(G[lo]['med6'])}억"
    n['KPI1S'] = f'84㎡ 중앙값 최고 {short(hi)} · 최저 {short(lo)}'
    n['KPI3'] = pct(dev['재건축 본격']); n['KPI4'] = pct(dev['일반 구축'])
    old_cheap = dev['일반 구축'] < 0 < dev['재건축 본격']
    n['LEDE'] = (f"값의 {pct(vd['gu'], False)}는 <b>어느 구인가</b>가, {pct(vd['cx'], False)}는 <b>어느 단지인가</b>가 정합니다."
                 + (' 오래됐는지는 재건축 계획이 있을 때만 값을 올립니다.' if old_cheap else ''))
    n['VARH2'] = f"값의 {pct(vd['gu'], False)}는 구가, {pct(vd['cx'], False)}는 단지가 정한다"
    # σ
    cv = sorted(GUS, key=lambda g: -G[g]['cv'])
    wide, narrow = cv[:4], cv[-5:][::-1]
    n['SIGH2'] = f'비싼 구일수록 폭도 넓다. {josa(names(wide[:3]))} 그보다 더 넓다'
    n['SIGWIDE'] = ('<b>' + ' · '.join(f"{short(g)} {G[g]['cv']:.2f}" for g in wide) + '.</b> '
                    + '최고 거래가 ' + '·'.join(esc(G[g]['mx']['n']) for g in wide[:3])
                    + '처럼 구 평균과 동떨어진 단지에서 나오는 곳입니다.')
    n['SIGNARROW'] = ('<b>' + ' · '.join(f"{short(g)} {G[g]['cv']:.2f}" for g in narrow) + '.</b> '
                      '비슷한 단지끼리 거래돼 시세가 촘촘합니다.')
    zmx = sum(G[g]['zmx'] for g in GUS) / len(GUS); zmn = sum(G[g]['zmn'] for g in GUS) / len(GUS)
    out2 = sorted(GUS, key=lambda g: -G[g]['zmx'])[:2]
    tail = (f'최고 거래는 평균에서 평균 <b>{zmx:+.1f}σ</b>, 최저 거래는 <b>{zmn:+.1f}σ</b>입니다. ').replace('-', '−')
    if zmx > -zmn + 0.5:
        tail += ('싼 쪽에는 바닥이 있고, 비싼 쪽은 단지 하나가 위로 끌고 갑니다('
                 + ', '.join(f"{short(g)} {esc(G[g]['mx']['n'])} {G[g]['zmx']:+.1f}σ" for g in out2) + ').')
    n['TAIL'] = tail
    n['DEVH2'] = ('오래돼서 싼 게 아니다. 재건축 계획이 없으면 쌀 뿐이다' if old_cheap
                  else '유형별로 같은 구 평균과 비교하면')
    n['DEVTXT'] = (f"같은 구 평균과 비교했습니다. 재건축 계획이 없는 일반 구축은 {pct(dev['일반 구축'])}, "
                   f"{D['old_y'] + 1}~{D['new_y'] - 1}년 준공 단지는 {pct(dev['중간'])}입니다. "
                   f"재건축 단지는 초기 {pct(dev['재건축 초기'])}, 조합설립 이후 {pct(dev['재건축 본격'])}이고 "
                   f"신축은 {pct(dev['신축'])}입니다.")
    # 유형별 최고가
    rb_top, new_top, rb_neg = [], [], []
    for g in GUS:
        t = T[g]
        vals = {'new': t['new'], 'mid': t['mid'], 'ob': t['ob'], 'rb': t['rb'] if t['nrb'] >= 20 else None}
        vals = {k: v for k, v in vals.items() if v}
        top = max(vals, key=vals.get)
        rest = sorted([v for k, v in vals.items() if k != top], reverse=True)
        if top == 'rb':
            rb_top.append(g)
        elif top == 'new' and rest and vals['new'] / rest[0] >= 1.3:
            new_top.append(g)
        if t['prem'] is not None and t['nrb'] >= 20 and t['prem'] < -0.05:
            rb_neg.append(g)
    rb_top.sort(key=lambda g: -T[g]['prem']); new_top.sort(key=lambda g: -T[g]['new'] / max(T[g]['mid'] or 1, T[g]['ob'] or 1))
    n['COMBOH2'] = ((f'{josa(names(rb_top[:4]))} 재건축이' if rb_top else '')
                    + (', ' if rb_top and new_top else '')
                    + (f'{josa(names(new_top[:4]))} 신축이' if new_top else '')
                    + ' 구의 최고가를 만든다') if (rb_top or new_top) else '구마다 최고가를 만드는 유형이 다르다'
    txt = []
    if rb_top:
        g = rb_top[0]; t = T[g]
        if t['new']:
            txt.append(f"{josa('<b>' + short(g) + '</b>')} 재건축({eok(t['rb'])}억)이 신축({eok(t['new'])}억)보다 {eok(t['rb'] - t['new'])}억 비쌉니다.")
    if rb_neg:
        txt.append(f"반대로 {josa('<b>' + names(sorted(rb_neg, key=lambda g: T[g]['prem'])) + '</b>')} 재건축 단지가 일반 구축보다도 쌉니다.")
    if new_top:
        txt.append(f"{josa('<b>' + names(new_top[:4]) + '</b>')} 파란 점(신축)이 홀로 멀리 떨어져 있습니다.")
    n['COMBOTXT'] = ' '.join(txt)
    mix = D['mix']
    n['MIXTXT'] = (f"신축 {pct(mix.get('신축', 0), False)}·중간 {pct(mix.get('중간', 0), False)}·"
                   f"일반 구축 {pct(mix.get('일반 구축', 0), False)}·재건축 {pct(mix.get('재건축 초기', 0) + mix.get('재건축 본격', 0), False)}")
    movers = sorted([g for g in GUS if abs(T[g]['rank_std'] - T[g]['rank_raw']) >= 2],
                    key=lambda g: -abs(T[g]['rank_std'] - T[g]['rank_raw']))
    n['SLOPEH2'] = ('신축·재건축 비중을 맞춰도 순위는 거의 그대로다' if len(movers) <= 5
                    else f'신축·재건축 비중을 맞추면 {len(movers)}개 구의 순위가 2계단 넘게 바뀐다')

    def why(g):
        t = T[g]
        if t['rank_std'] > t['rank_raw']:
            if t['sh_rb'] >= 0.08: return f"재건축 거래 비중이 {pct(t['sh_rb'], False)}라 실제보다 높아 보였습니다"
            return f"신축 거래 비중이 {josa(pct(t['share']['신축'], False), '으로로')} 높았습니다(전 평형 기준)"
        return '오래된 단지 거래가 많아 실제보다 낮아 보였습니다'
    if movers:
        n['SLOPETXT'] = (f"<b>2계단 이상 움직인 곳은 {len(movers)}개 구입니다.</b> "
                         + ' '.join(f"{josa(short(g))}({T[g]['rank_raw']}→{T[g]['rank_std']}위) {why(g)}." for g in movers[:4])
                         + ' 그 밖의 구는 구별 순위표를 그대로 믿어도 됩니다.')
    else:
        n['SLOPETXT'] = '<b>2계단 이상 움직인 구가 없습니다.</b> 구별 순위표는 거래 구성의 영향을 거의 받지 않았습니다.'
    n['P12'] = f"{ym_dot(D['m12'][0])}–{ym_dot(D['m12'][1])}"
    n['ENDYM'] = f"{D['m6'][1][:4]}-{D['m6'][1][4:]}"
    n['GEN'] = date.today().isoformat()
    n['RB84'] = f"{D['rb_trades84']:,}"; n['RBN'] = f"{D['rb_complexes']:,}"; n['RBTN'] = f"{D['rb_trades']:,}"
    n['ZEXP'] = D.get('zones_exported') or '-'
    n['N'] = f"{sum(G[g]['n6'] for g in GUS):,}"; n['NALL'] = f"{D['n_all']:,}"
    for k in ('gu', 'age', 'cx', 'rest'):
        n['V' + {'gu': 'GU', 'age': 'AGE', 'cx': 'CX', 'rest': 'REST'}[k]] = pct(vd[k], False)
    # 지도 설명
    over20 = [g for g in by_med if G[g]['med6'] >= 200000]
    sd = sorted(GUS, key=lambda g: -G[g]['sd'])
    shn = sorted(GUS, key=lambda g: -G[g]['sh_new'])
    zero_new = [g for g in GUS if G[g]['sh_new'] < 0.01]
    prem = sorted([g for g in GUS if T[g]['prem'] is not None and T[g]['nrb'] >= 20], key=lambda g: -T[g]['prem'])
    n['_notes'] = {
        'price': (f"{names(over20)} {len(over20)}개 구가 20억을 넘습니다. " if over20 else '')
                 + f"가장 낮은 {josa(names(by_med[-3:]))} {eok(G[by_med[-1]]['med6'])}~{eok(G[by_med[-3]]['med6'])}억입니다.",
        'sd': (f"{short(sd[0])}의 σ는 {eok(G[sd[0]]['sd'])}억으로 {short(sd[-1])}({eok(G[sd[-1]]['sd'])}억)의 "
               f"{G[sd[0]]['sd'] / G[sd[-1]]['sd']:.0f}배입니다. {short(sd[0])} 안에서도 {eok(G[sd[0]]['mn']['p'])}억~"
               f"{eok(G[sd[0]]['mx']['p'])}억까지 벌어집니다."),
        'new': (f"{D['new_y']}년 이후 준공 단지 거래 비중입니다. " + ', '.join(f"{short(g)} {pct(G[g]['sh_new'], False)}" for g in shn[:4])
                + ('는' if True else '') + ' 신축 거래가 많아 구 평균이 실제보다 높게 나옵니다.'
                + (f" {josa(names(zero_new))} 0%입니다." if zero_new else '')),
        'prem': ('같은 구 일반 구축보다 재건축 추진 단지가 얼마나 비싼지입니다. '
                 + (f"{josa(short(prem[0]))} {pct(T[prem[0]]['prem'])}" if prem else '')
                 + (f", {josa(names([g for g in prem if T[g]['prem'] < 0][::-1][:3]))} 오히려 쌉니다." if any(T[g]['prem'] < 0 for g in prem) else '.')
                 + ' 재건축 거래 20건 미만인 구는 회색입니다.'),
    }
    return n


# ---------------- 차트 ----------------
def charts(D, geo, n):
    G = D['gu']; GUS = list(G); T = {g: G[g]['t'] for g in GUS}
    NY, OY = D['new_y'], D['old_y']
    out = {}
    # 지도
    pts = [(x, y) for f in geo['features'] for poly in ([f['geometry']['coordinates']] if f['geometry']['type'] == 'Polygon' else f['geometry']['coordinates']) for ring in poly for x, y in ring]
    lx = min(p[0] for p in pts); hx = max(p[0] for p in pts); hy = max(p[1] for p in pts); ly = min(p[1] for p in pts)
    Wm = 900; kx = Wm / (hx - lx); ky = kx * 1.262; Hm = (hy - ly) * ky
    Pj = lambda x, y: ((x - lx) * kx, (hy - y) * ky)
    paths, labels = [], []
    for f in geo['features']:
        g = f['properties']['name']
        polys = [f['geometry']['coordinates']] if f['geometry']['type'] == 'Polygon' else f['geometry']['coordinates']
        d = ' '.join(' '.join(('M' if i == 0 else 'L') + '%.1f,%.1f' % Pj(x, y) for i, (x, y) in enumerate(ring)) + 'Z' for poly in polys for ring in poly)
        paths.append(f'<path class="gu" data-gu="{g}" d="{d}"/>')
        ring = max((p[0] for p in polys), key=len); cx = sum(x for x, y in ring) / len(ring); cy = sum(y for x, y in ring) / len(ring)
        px, py = Pj(cx, cy)
        labels.append(f'<g class="lb" data-gu="{g}" transform="translate({px:.0f},{py:.0f})"><text y="-4">{g}</text><text y="13" class="v"></text></g>')
    out['MAP'] = f'<svg viewBox="0 0 {Wm} {Hm:.0f}" id="map" role="img" aria-label="서울 구별 지도">{"".join(paths)}{"".join(labels)}</svg>'
    M = {
        'price': dict(label='84㎡ 중앙값', unit='억', kind='seq', bins=[8, 10, 13, 16, 20], vals={g: G[g]['med6'] / 1e4 for g in GUS}, fmt=1),
        'sd': dict(label='가격 폭 σ', unit='억', kind='seq', bins=[2, 3, 4, 5.5, 8], vals={g: G[g]['sd'] / 1e4 for g in GUS}, fmt=1),
        'new': dict(label='신축 거래 비중', unit='%', kind='seq', bins=[8, 13, 18, 23, 28], vals={g: G[g]['sh_new'] * 100 for g in GUS}, fmt=0),
        'prem': dict(label='재건축 프리미엄', unit='%', kind='div', bins=[-15, -5, 5, 25, 45],
                     vals={g: T[g]['prem'] * 100 for g in GUS if T[g]['prem'] is not None and T[g]['nrb'] >= 20}, fmt=0),
    }
    for k, m in M.items():
        m['note'] = n['_notes'][k]
        m['tip'] = {g: (f"{v:.1f}억" if m['unit'] == '억' else f"{v:+.0f}%" if m['kind'] == 'div' else f"{v:.0f}%") for g, v in m['vals'].items()}
    out['MJS'] = json.dumps(M, ensure_ascii=False)
    # 분산 분해
    vd = D['vardec']
    VDP = [('gu', '어느 구인가', vd['gu']), ('age', '신축·재건축 여부', vd['age']), ('cx', '같은 구·같은 유형 안의 단지', vd['cx']), ('rest', '층·평형·거래 시점 등', vd['rest'])]
    out['VDBAR'] = ''.join(f'<div class="vseg v-{k}" style="flex:{v:.4f}" data-tip="{lab} — 가격 차이의 {v:.0%}"><b>{v:.0%}</b></div>' for k, lab, v in VDP)
    out['VDLEG'] = ''.join(f'<li><i class="sw v-{k}"></i><span>{lab}</span><b>{v:.0%}</b></li>' for k, lab, v in VDP)
    # 산점도
    SW, SH = 640, 400; ml, mr, mt, mb = 52, 20, 16, 40
    xm = max(5, (max(G[g]['mu'] for g in GUS) / 1e4 // 5 + 1) * 5); ym = max(6, (max(G[g]['sd'] for g in GUS) / 1e4 // 2 + 1) * 2)
    X = lambda v: ml + v / xm * (SW - ml - mr); Y = lambda v: SH - mb - v / ym * (SH - mt - mb)
    sc = [f'<svg viewBox="0 0 {SW} {SH}" class="chart" role="img" aria-label="구별 평균 가격과 가격 폭 산점도">']
    for t in range(0, int(xm) + 1, 5):
        sc.append(f'<line x1="{X(t):.1f}" x2="{X(t):.1f}" y1="{mt}" y2="{SH - mb}" class="gl"/><text x="{X(t):.1f}" y="{SH - mb + 16}" class="ax" text-anchor="middle">{t}억</text>')
    step = 3 if ym > 9 else 2
    for t in range(0, int(ym) + 1, step):
        sc.append(f'<line x1="{ml}" x2="{SW - mr}" y1="{Y(t):.1f}" y2="{Y(t):.1f}" class="gl"/><text x="{ml - 8}" y="{Y(t) + 4:.1f}" class="ax" text-anchor="end">{t}억</text>')
    for cv, lab in [(0.25, 'σ=평균의 25%'), (0.40, 'σ=평균의 40%')]:
        x2 = min(xm, ym / cv); lx_ = xm * (0.56 if cv > 0.3 else 0.8)
        sc.append(f'<line x1="{X(0):.1f}" y1="{Y(0):.1f}" x2="{X(x2):.1f}" y2="{Y(cv * x2):.1f}" class="ref"/>'
                  f'<text x="{X(lx_) + (-6 if cv > 0.3 else 8):.1f}" y="{Y(cv * lx_) + (-6 if cv > 0.3 else 16):.1f}" class="ax" text-anchor="{"end" if cv > 0.3 else "start"}">{lab}</text>')
    sc.append(f'<text x="{SW - mr}" y="{SH - 6}" class="axt" text-anchor="end">평균 가격 →</text><text x="{ml}" y="{mt - 4}" class="axt">↑ 가격 폭 σ</text>')
    cvs = sorted(GUS, key=lambda g: -G[g]['cv']); mus = sorted(GUS, key=lambda g: -G[g]['mu'])
    show = list(dict.fromkeys(mus[:3] + cvs[:4] + cvs[-3:] + mus[-1:]))
    for g in sorted(GUS, key=lambda g: -G[g]['n6']):
        v = G[g]; r = 4 + v['n6'] ** 0.5 / 3.2
        cls = 'hi' if g in cvs[:4] else ('lo' if g in cvs[-5:] else '')
        sc.append(f'<circle cx="{X(v["mu"] / 1e4):.1f}" cy="{Y(v["sd"] / 1e4):.1f}" r="{r:.1f}" class="sdot {cls}" data-gu="{g}" '
                  f'data-tip="{g} · 평균 {eok(v["mu"])}억 · σ {eok(v["sd"])}억 · 변동계수 {v["cv"]:.2f} · {v["n6"]}건"/>')
    placed = []
    for g in show:
        v = G[g]; r = 4 + v['n6'] ** 0.5 / 3.2; x, y = X(v['mu'] / 1e4), Y(v['sd'] / 1e4)
        for tx, ty, an in [(x + r + 3, y + 4, 'start'), (x - r - 3, y + 4, 'end'), (x, y - r - 4, 'middle'), (x, y + r + 13, 'middle')]:
            if all(abs(tx - px) > 40 or abs(ty - py) > 13 for px, py in placed):
                break
        placed.append((tx, ty))
        sc.append(f'<text x="{tx:.1f}" y="{ty:.1f}" class="dl" text-anchor="{an}">{g}</text>')
    sc.append('</svg>'); out['SCATTER'] = ''.join(sc)
    # 분포 스트립
    order = sorted(GUS, key=lambda g: -G[g]['mu'])
    L, RW, RH, TOP = 74, 880, 26, 30
    XMAX = (max(G[g]['mx']['p'] for g in GUS) // 100000 + 1) * 100000
    Xs = lambda p: L + p / XMAX * RW
    Wd = L + RW + 56; Hd = TOP + RH * len(order) + 6
    s = [f'<svg viewBox="0 0 {Wd} {Hd}" class="chart sg" role="img" aria-label="구별 84㎡ 거래가 분포">']
    for t in range(0, int(XMAX / 1e4) + 1, 10):
        x = Xs(t * 1e4); s.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{TOP - 6}" y2="{Hd - 4}" class="gl"/><text x="{x:.1f}" y="{TOP - 12}" class="ax" text-anchor="middle">{t}억</text>')
    random.seed(7)
    for i, g in enumerate(order):
        v = G[g]; y = TOP + i * RH + RH / 2; mu, sd = v['mu'], v['sd']
        s.append(f'<g data-gu="{g}"><text x="{L - 10}" y="{y + 4:.1f}" class="gn">{g}</text>')
        s.append(f'<rect x="{Xs(max(0, mu - 2 * sd)):.1f}" y="{y - 8:.1f}" width="{Xs(mu + 2 * sd) - Xs(max(0, mu - 2 * sd)):.1f}" height="16" class="s2"/>')
        s.append(f'<rect x="{Xs(mu - sd):.1f}" y="{y - 8:.1f}" width="{Xs(mu + sd) - Xs(mu - sd):.1f}" height="16" class="s1"/>')
        for p in v['prices']:
            s.append(f'<circle cx="{Xs(p):.1f}" cy="{y + random.uniform(-5.5, 5.5):.1f}" r="1.5" class="dot"/>')
        s.append(f'<line x1="{Xs(mu):.1f}" x2="{Xs(mu):.1f}" y1="{y - 10:.1f}" y2="{y + 10:.1f}" class="mu"/>')
        mx, mn = v['mx'], v['mn']
        s.append(f'<circle cx="{Xs(mx["p"]):.1f}" cy="{y:.1f}" r="4.5" class="mx" data-tip="{g} 최고 · {esc(mx["n"])} {eok(mx["p"])}억 · {mx["by"]}년 준공 {mx["f"]}층 · 평균 {v["zmx"]:+.1f}σ"/>')
        s.append(f'<circle cx="{Xs(mn["p"]):.1f}" cy="{y:.1f}" r="4.5" class="mn" data-tip="{g} 최저 · {esc(mn["n"])} {eok(mn["p"])}억 · {mn["by"]}년 준공 {mn["f"]}층 · 평균 {v["zmn"]:+.1f}σ"/>')
        s.append(f'<text x="{Xs(mx["p"]) + 8:.1f}" y="{y + 4:.1f}" class="zl">{v["zmx"]:+.1f}σ</text></g>')
    s.append('</svg>'); out['STRIP'] = ''.join(s)
    # 구성 + 유형별 가격
    GR = [('신축', 'new', f'신축 {NY}~'), ('재건축', 'rb', '재건축 추진'), ('일반 구축', 'ob', f'일반 구축 ~{OY}'), ('중간', 'mid', f'중간 {OY + 1}~{str(NY - 1)[2:]}')]
    ordr = sorted(GUS, key=lambda g: -T[g]['raw'])
    CW, DW, RHh, TP, GAP = 230, 560, 24, 44, 34
    DX0 = CW + GAP + 70
    DXM = (max(max(v for v in (T[g]['new'], T[g]['mid'], T[g]['ob'], T[g]['rb']) if v) for g in GUS) / 1e4 // 5 + 1) * 5
    Xd = lambda v: DX0 + v / DXM * DW
    Wc = DX0 + DW + 16; Hc = TP + RHh * len(ordr) + 8
    c = [f'<svg viewBox="0 0 {Wc} {Hc}" class="chart" role="img" aria-label="구별 거래 구성과 유형별 84㎡ 환산가">',
         f'<text x="0" y="14" class="axt">거래 구성 (100%)</text><text x="{DX0}" y="14" class="axt">유형별 84㎡ 환산 평균가</text>']
    for t in range(0, int(DXM) + 1, 5):
        c.append(f'<line x1="{Xd(t):.1f}" x2="{Xd(t):.1f}" y1="{TP - 4}" y2="{Hc - 4}" class="gl"/>'
                 + (f'<text x="{Xd(t):.1f}" y="{TP - 8}" class="ax" text-anchor="middle">{t}억</text>' if t % 10 == 0 else ''))
    for i, g in enumerate(ordr):
        y = TP + i * RHh + RHh / 2; t = T[g]; x = 0
        c.append(f'<g data-gu="{g}">')
        for k, key, lab in GR:
            w = t['share'][k] * CW
            if w > 0:
                c.append(f'<rect x="{x + 1:.1f}" y="{y - 7:.1f}" width="{max(0, w - 2):.1f}" height="14" class="f-{key}" data-tip="{g} · {lab} {t["share"][k]:.0%}"/>')
            x += w
        c.append(f'<text x="{CW + GAP + 62}" y="{y + 4:.1f}" class="gn">{g}</text>')
        vals = [(key, t[key] if key != 'rb' else (t['rb'] if t['nrb'] >= 5 else None)) for k, key, lab in GR]
        vv = [v for _, v in vals if v]
        c.append(f'<line x1="{Xd(min(vv) / 1e4):.1f}" x2="{Xd(max(vv) / 1e4):.1f}" y1="{y:.1f}" y2="{y:.1f}" class="rng"/>')
        for (k, key, lab), (_, v) in zip(GR, vals):
            if v is None:
                continue
            hol = ' hol' if key == 'rb' and t['nrb'] < 20 else ''
            cnt = f" · {t['nrb']}건" if key == 'rb' else ''
            c.append(f'<circle cx="{Xd(v / 1e4):.1f}" cy="{y:.1f}" r="5.5" class="d-{key}{hol}" data-tip="{g} · {lab} {eok(v)}억{cnt}"/>')
        c.append('</g>')
    c.append('</svg>'); out['COMBO'] = ''.join(c)
    out['GRLEG'] = ''.join(f'<span><i class="sw f-{key}"></i>{lab}</span>' for k, key, lab in GR) + '<span><i class="sw hol-k"></i>재건축 거래 20건 미만</span>'
    # 유형별 구 평균 대비
    G5 = [('신축', 'new', f'신축 {NY}~'), ('중간', 'mid', f'중간 {OY + 1}~{NY - 1}'), ('일반 구축', 'ob', f'일반 구축 ~{OY}'),
          ('재건축 초기', 'rb', '재건축 초기 · 안전진단~구역지정'), ('재건축 본격', 'rb', '재건축 본격 · 조합설립~관리처분')]
    dev, cnt = D['dev'], D['cnt']
    BW, BX, BH = 460, 250, 34
    mxd = max(0.4, max(abs(v) for v in dev.values()) * 1.15)
    B = [f'<svg viewBox="0 0 {BX + BW + 70} {len(G5) * BH + 30}" class="chart" role="img" aria-label="유형별 같은 구 평균 대비 가격">']
    z = BX + BW / 2
    for t in (-mxd, -mxd / 2, 0, mxd / 2, mxd):
        x = z + t / mxd * BW / 2
        B.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="6" y2="{len(G5) * BH + 8}" class="{"zero" if t == 0 else "gl"}"/><text x="{x:.1f}" y="{len(G5) * BH + 24}" class="ax" text-anchor="middle">{t * 100:+.0f}%</text>')
    for i, (k, key, lab) in enumerate(G5):
        y = 10 + i * BH; v = dev[k]; w = abs(v) / mxd * BW / 2; x = z if v >= 0 else z - w
        hat = ' hatch' if k == '재건축 초기' else ''
        B.append(f'<text x="{BX - 12}" y="{y + 16}" class="gn">{lab}</text><text x="{BX - 12}" y="{y + 29}" class="ax" text-anchor="end">{cnt[k]:,}건</text>')
        B.append(f'<rect x="{x:.1f}" y="{y + 4}" width="{w:.1f}" height="18" rx="3" class="f-{key}{hat}" data-tip="{lab} · 같은 구 평균보다 {v * 100:+.0f}% · {cnt[k]:,}건"/>')
        B.append(f'<text x="{(x + w + 6) if v >= 0 else (x - 6):.1f}" y="{y + 18}" class="vl" text-anchor="{"start" if v >= 0 else "end"}">{v * 100:+.0f}%</text>')
    B.append('</svg>'); out['DEVBAR'] = ''.join(B)
    # 순위 슬로프
    SWd, SHd = 520, len(GUS) * 22 + 40; xl, xr = 150, 370
    Ys = lambda r: 28 + (r - 1) * 22
    sl = [f'<svg viewBox="0 0 {SWd} {SHd}" class="chart" role="img" aria-label="구성 보정 전후 순위">',
          f'<text x="{xl}" y="14" class="axt" text-anchor="end">실제 거래 그대로</text><text x="{xr}" y="14" class="axt">서울 평균 구성으로 맞춘 뒤</text>']
    for g in GUS:
        a, b = T[g]['rank_raw'], T[g]['rank_std']
        cls = 'up' if b - a <= -2 else ('dn' if b - a >= 2 else '')
        sl.append(f'<g class="sl {cls}" data-gu="{g}" data-tip="{g} · {eok(T[g]["raw"])}억 → {eok(T[g]["std"])}억 · {a}위 → {b}위">'
                  f'<line x1="{xl + 6}" y1="{Ys(a) - 4}" x2="{xr - 6}" y2="{Ys(b) - 4}"/>'
                  f'<text x="{xl}" y="{Ys(a)}" text-anchor="end">{a}. {g} {eok(T[g]["raw"])}</text><text x="{xr}" y="{Ys(b)}">{b}. {g} {eok(T[g]["std"])}</text></g>')
    sl.append('</svg>'); out['SLOPE'] = ''.join(sl)
    # 대표 단지 카드
    cards = []
    for r, g in enumerate(sorted(GUS, key=lambda g: -G[g]['med6']), 1):
        v = G[g]; top5 = v['top5']
        if not top5:
            continue
        hi = max(x['hi'] for x in top5); lo = min(x['lo'] for x in top5); span = hi - lo + 1
        rows = ''.join(
            f'<tr><td class="nm">{esc(x["n"])}<small>{x["d"]} · {(str(format(x["hh"], ",")) + "세대") if x["hh"] else "세대수 미상"} · {x["by"]}년</small></td>'
            f'<td class="num strong">{eok(x["med"])}억</td>'
            f'<td class="rbar"><span class="rtrack"><i style="left:{(x["lo"] - lo) / span * 100:.0f}%;width:{max(2, (x["hi"] - x["lo"]) / span * 100):.0f}%"></i>'
            f'<b style="left:{(x["med"] - lo) / span * 100:.0f}%"></b></span><small>{eok(x["lo"])}–{eok(x["hi"])} · {x["cnt"]}건</small></td></tr>'
            for x in top5)
        cards.append(f'<article class="card" id="g-{g}" data-gu="{g}"><header><span class="rk">{r}</span><h3>{g}</h3>'
                     f'<div class="gm"><b>{eok(v["med6"])}억</b><small>84㎡ 중앙값 · {v["n6"]}건</small></div></header>'
                     f'<table><tbody>{rows}</tbody></table></article>')
    out['CARDS'] = '\n'.join(cards)
    # 상세 표
    out['STAT'] = ('<div class="tw"><table class="st"><thead><tr><th>구</th><th>건수</th><th>평균</th><th>σ</th><th>변동계수</th><th>왜도</th><th>최저 거래</th><th>최고 거래</th><th>최고÷최저</th></tr></thead><tbody>'
                   + ''.join(f'<tr><td>{g}</td><td class="num">{G[g]["n6"]}</td><td class="num">{eok(G[g]["mu"])}</td><td class="num">{eok(G[g]["sd"])}</td>'
                             f'<td class="num">{G[g]["cv"]:.2f}</td><td class="num">{G[g]["sk"]:+.2f}</td>'
                             f'<td class="nm">{esc(G[g]["mn"]["n"])} <small>{eok(G[g]["mn"]["p"])}억 · {G[g]["mn"]["by"]}년 · {G[g]["mn"]["f"]}층</small></td>'
                             f'<td class="nm">{esc(G[g]["mx"]["n"])} <small>{eok(G[g]["mx"]["p"])}억 · {G[g]["mx"]["by"]}년 · {G[g]["mx"]["f"]}층</small></td>'
                             f'<td class="num">{G[g]["ratio"]:.1f}배</td></tr>' for g in order) + '</tbody></table></div>')
    e2 = lambda v: eok(v) if v else '–'
    out['RBT'] = ('<div class="tw"><table class="st"><thead><tr><th>구</th><th>재건축 거래</th><th>신축</th><th>중간</th><th>일반 구축</th><th>재건축</th><th>재건축÷일반 구축</th><th>구 안 설명력 (재건축 분리 전→후)</th></tr></thead><tbody>'
                  + ''.join(f'<tr><td>{g}</td><td class="num">{T[g]["nrb"]:,} <small>{T[g]["sh_rb"]:.0%}</small></td><td class="num">{e2(T[g]["new"])}</td><td class="num">{e2(T[g]["mid"])}</td>'
                            f'<td class="num">{e2(T[g]["ob"])}</td><td class="num">{e2(T[g]["rb"])}</td><td class="num">{pct(T[g]["prem"]) if T[g]["prem"] is not None else "–"}</td>'
                            f'<td class="num">{T[g]["e3"]:.0%} → {T[g]["e4"]:.0%}</td></tr>'
                            for g in sorted(GUS, key=lambda g: -(T[g]['prem'] if T[g]['prem'] is not None else -9))) + '</tbody></table></div>')
    return out


def main():
    D = json.load(open(os.path.join(W, 'p84_data.json'), encoding='utf-8'))
    geo = json.load(open(os.path.join(W, 'seoul_geo.json'), encoding='utf-8'))
    n = narrative(D)
    rep = {**{k: v for k, v in n.items() if not k.startswith('_')}, **charts(D, geo, n)}
    tpl = open(os.path.join(W, 'p84_template.html'), encoding='utf-8').read()
    for k, v in rep.items():
        tpl = tpl.replace(f'%{k}%', v)
    left = sorted(set(__import__('re').findall(r'%[A-Z0-9]+%', tpl)))
    if left:
        raise SystemExit(f'채워지지 않은 자리표시자: {left}')
    open(os.path.join(W, 'seoul84_report.html'), 'w', encoding='utf-8').write(tpl)
    print(f'seoul84_report.html: {len(tpl):,} bytes')


if __name__ == '__main__':
    main()
