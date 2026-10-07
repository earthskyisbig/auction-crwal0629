# -*- coding: utf-8 -*-
"""서울 84㎡ 가격 지도 — 계산 단계 → p84_data.json

입력: sale_<구>.csv (collect_seoul.py), complex_index.json (세대수), rebuild_zones.json (재건축 구역 스냅샷),
      seoul_geo.json 의 구 목록.
기간: windows.py 의 롤링 24개월 중 최근 6개월(구별 분포·유형 분석), 최근 12개월(대표 단지).

계산 항목
  1) 구별 84㎡(전용 83~86㎡) 중앙값·사분위, 대표 단지 5곳(12개월 84㎡ 거래 3건↑, 세대수 순)
  2) 구별 σ 분포: 평균·σ·변동계수·왜도·최고/최저 거래와 z
  3) 연식 3군(신축 = 준공 10년 이내, 중간, 구축 = 26년 이상) 비중
  4) 재건축 분류: 정비구역 대표지번(동·본번·부번) 또는 같은 동·같은 단지명(숫자까지 일치), 2003년 이전 준공만
     → 전 평형(40~135㎡) ㎡당×84 환산가로 유형별 가격·프리미엄·구 안 설명력·구성 보정 순위
  5) 가격 차이 분해: 구 → 구×유형 → 단지 순 설명 분산
"""
import collections, json, os, re, statistics as st, sys

W = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, W)
from sales_io import load_sales
from windows import MONTHS

M6, M12 = MONTHS[-6:], MONTHS[-12:]
END_Y = int(MONTHS[-1][:4])
NEW_Y = END_Y - 10          # 이 해 이후 준공 = 신축
OLD_Y = END_Y - 26          # 이 해 이전 준공 = 구축 (그 사이 = 중간)
RB_MAX_Y = 2003             # 재건축 판정은 이 해 이전 준공만 (같은 지번의 재건축 후 신축 오매칭 방지)
EARLY = ('구역지정전', '추진위', '구역지정')
# 지번·이름 대조로 잡히지만 실제로는 다른 단지인 쌍 (2026-10 수동 확인)
BAD = {('명진에버그린', '경남1차'), ('현대3차', '양평현대2차아파트')}



def amt(r): return int(r['dealAmount'].replace(',', '').strip())


def is84(a): return 83 <= a < 86


# ---------- 지번: CSV 에 없으면(구버전 CSV) 최근 6개월만 RTMS 로 보충 ----------
def jibun_lookup(GUS):
    sample = load_sales(GUS[0])
    if sample and 'bonbun' in sample[0]:
        return None   # CSV 행에서 직접 읽는다
    cache = os.path.join(W, 'p84_jibun_cache.json')
    if os.path.exists(cache):
        c = json.load(open(cache, encoding='utf-8'))
        if c.get('months') == M6:
            return c['map']
    from collect_seoul import fetch_month, GUS as CODES
    mp = {}
    for gu in GUS:
        for ym in M6:
            for d in fetch_month(CODES[gu], ym):
                k = f"{gu}|{d.get('umdNm')}|{d.get('aptNm')}|{d.get('buildYear')}"
                mp.setdefault(k, {'bonbun': d.get('bonbun'), 'bubun': d.get('bubun')})
        print(f'  지번 보충 {gu}', flush=True)
    json.dump({'months': M6, 'map': mp}, open(cache, 'w', encoding='utf-8'), ensure_ascii=False)
    return mp


def jib(r, JMAP):
    """행 → (본번, 부번). JMAP 이 None 이면 CSV 행의 bonbun/bubun 을 쓴다."""
    src = r if JMAP is None else JMAP.get(f"{r['gu']}|{r['umdNm']}|{r['aptNm']}|{r['buildYear']}", {})
    b = (src.get('bonbun') or '').strip()
    if not b.strip('0'):
        return None, 0
    return int(b), int((src.get('bubun') or '0').strip() or 0)


# ---------- 재건축 분류 ----------
def norm(s):
    s = re.sub(r'\(.*?\)', '', s)
    for w in ['주택재건축정비사업', '주택재건축', '재건축', '정비구역', '정비사업', '조합', '아파트', '소규모', '위원회', '추진',
              ' ', '·', '-', '제', '단지']:
        s = s.replace(w, '')
    return re.sub(r'목동신시가지(\d+)', r'목동\1', s).lower()


def base(d): return re.sub(r'\d+가$', '', d or '')


def build_index(zones):
    byjib = collections.defaultdict(list)
    for z in zones:
        if z['bonbun']:
            byjib[(z['gu'], z['jb_dong'], z['bonbun'])].append(z)
    return dict(byjib=byjib, zn=[(z, norm(z['name'])) for z in zones],
                apgu=next((z for z in zones if '압구정아파트지구' in z['name']), None), cache={})


def name_match(a, kz):
    """정규화된 실거래 단지명 a 와 구역명 kz 가 같은 단지인가 — 포함 관계는 숫자까지 같아야 한다(창동주공1 ≠ 18)."""
    if not kz or len(a) < 2:
        return False
    if kz == a:
        return True
    return (len(a) >= 3 and len(kz) >= 3 and (a in kz or kz in a)
            and re.findall(r'\d+', a) == re.findall(r'\d+', kz))


def classify(r, by, idx, bon_bub):
    """실거래 행 → 재건축 구역 dict 또는 None. bon_bub = (본번, 부번) 또는 (None, 0)."""
    k = (r['gu'], r['umdNm'], r['aptNm'], by)
    if k in idx['cache']:
        return idx['cache'][k]
    res = None
    if by <= RB_MAX_Y:
        bon, bub = bon_bub
        if bon:
            L = idx['byjib'].get((r['gu'], r['umdNm'], bon), [])
            ex = [z for z in L if z['bubun'] is not None and z['bubun'] == bub]
            loose = [z for z in L if z['bubun'] is None or bub == 0]
            res = (ex or loose or [None])[0]
        if not res:
            a = norm(r['aptNm'])
            for z, kz in idx['zn']:
                if z['gu'] == r['gu'] and base(z['dong']) == base(r['umdNm']) and name_match(a, kz):
                    res = z; break
        if not res and idx['apgu'] and r['umdNm'] == '압구정동' and by <= 1990:
            res = idx['apgu']
    if res and (r['aptNm'], res['name']) in BAD:
        res = None
    idx['cache'][k] = res
    return res


def age3(by): return '신축' if by >= NEW_Y else ('중간' if by > OLD_Y else '구축')


def main():
    geo = json.load(open(os.path.join(W, 'seoul_geo.json'), encoding='utf-8'))
    GUS = [f['properties']['name'] for f in geo['features']]
    CI = json.load(open(os.path.join(W, 'complex_index.json'), encoding='utf-8'))['complexes']
    HH = {(c['g'], c['d'], c['n']): c.get('hh') for c in CI}
    ZJ = json.load(open(os.path.join(W, 'rebuild_zones.json'), encoding='utf-8'))
    IDX = build_index(ZJ['zones'])
    JMAP = jibun_lookup(GUS)
    S84_6, S84_12, ALL6 = {}, {}, []
    for g in GUS:
        rows = load_sales(g)
        S84_6[g], S84_12[g] = [], []
        for r in rows:
            try:
                a = float(r['excluUseAr']); by = int(r['buildYear'] or 0); p = amt(r)
            except ValueError:
                continue
            if r['ym'] in M12 and is84(a):
                S84_12[g].append(dict(d=r['umdNm'], n=r['aptNm'], by=by, p=p, f=int(r['floor'] or 0),
                                      dt=r['ym'] + r['dealDay'].zfill(2)))
            if r['ym'] in M6:
                if is84(a):
                    S84_6[g].append(dict(d=r['umdNm'], n=r['aptNm'], by=by, p=p, f=int(r['floor'] or 0),
                                         hh=HH.get((g, r['umdNm'], r['aptNm']))))
                if 40 <= a < 135:
                    z = classify(r, by, IDX, jib(r, JMAP) if by <= RB_MAX_Y else (None, 0))
                    t = dict(g=g, d=r['umdNm'], n=r['aptNm'], by=by, p84=p / a * 84, is84=is84(a))
                    if z:
                        t['grp'] = '재건축 초기' if z['stage'] in EARLY else '재건축 본격'
                        t['zone'], t['stage'] = z['name'], z['stage']
                    else:
                        t['grp'] = {'신축': '신축', '중간': '중간', '구축': '일반 구축'}[age3(by)]
                    ALL6.append(t)

    out = {'months': MONTHS, 'm6': [M6[0], M6[-1]], 'm12': [M12[0], M12[-1]], 'new_y': NEW_Y, 'old_y': OLD_Y,
           'zones_exported': ZJ.get('exported'), 'gu': {}}

    # ---------- 1·2·3) 84㎡ ----------
    for g in GUS:
        t6 = S84_6[g]; ps = [x['p'] for x in t6]
        q = st.quantiles(ps, n=4) if len(ps) > 3 else [None, None, None]
        agg = collections.defaultdict(list)
        for x in S84_12[g]:
            agg[(x['d'], x['n'])].append(x)
        cands = []
        for (d, n), v in agg.items():
            if len(v) < 3:
                continue
            v.sort(key=lambda x: x['dt'])
            cands.append(dict(d=d, n=n, cnt=len(v), med=st.median(x['p'] for x in v), lo=min(x['p'] for x in v),
                              hi=max(x['p'] for x in v), last=v[-1]['p'], lastd=v[-1]['dt'], by=v[-1]['by'],
                              hh=HH.get((g, d, n))))
        cands.sort(key=lambda c: (-(c['hh'] or 0), -c['cnt']))
        best = {}
        for c in cands:   # K-apt 세대수가 단지군 합으로 붙은 경우(같은 동·같은 세대수) 거래 많은 하나만
            k = (c['d'], c['hh']) if c['hh'] else (c['d'], c['n'])
            if k not in best or c['cnt'] > best[k]['cnt']:
                best[k] = c
        top5 = sorted(best.values(), key=lambda c: (-(c['hh'] or 0), -c['cnt']))[:5]
        mu = st.mean(ps); sd = st.pstdev(ps); n = len(ps)
        mx = max(t6, key=lambda x: x['p']); mn = min(t6, key=lambda x: x['p'])
        sh = collections.Counter(age3(x['by']) for x in t6)
        out['gu'][g] = dict(
            n6=n, med6=st.median(ps), q1=q[0], q3=q[2], top5=top5,
            mu=mu, sd=sd, cv=sd / mu, sk=sum(((p - mu) / sd) ** 3 for p in ps) / n,
            w1=sum(1 for p in ps if abs(p - mu) <= sd) / n, prices=sorted(ps),
            mx=mx, mn=mn, zmx=(mx['p'] - mu) / sd, zmn=(mn['p'] - mu) / sd, ratio=mx['p'] / mn['p'],
            sh_new=sh['신축'] / n, sh_mid=sh['중간'] / n, sh_old=sh['구축'] / n)

    # ---------- 4) 유형 분석 (전 평형 환산가) ----------
    G5 = ['신축', '중간', '일반 구축', '재건축 초기', '재건축 본격']
    g4 = lambda t: '재건축' if t['grp'].startswith('재건축') else t['grp']
    g3 = lambda t: '구축' if t['grp'] in ('일반 구축', '재건축 초기', '재건축 본격') else t['grp']
    N = len(ALL6)
    WS = {k: v / N for k, v in collections.Counter(t['grp'] for t in ALL6).items()}


    def eta(ts, f):
        ps = [t['p84'] for t in ts]; m = st.mean(ps); tot = st.pvariance(ps)
        gr = collections.defaultdict(list)
        for t in ts: gr[f(t)].append(t['p84'])
        return sum(len(L) * (st.mean(L) - m) ** 2 for L in gr.values()) / len(ps) / tot


    for g in GUS:
        ts = [t for t in ALL6 if t['g'] == g]
        m = {k: [t['p84'] for t in ts if t['grp'] == k] for k in G5}
        mean = {k: st.mean(v) for k, v in m.items() if len(v) >= 5}
        rb = [t['p84'] for t in ts if t['grp'].startswith('재건축')]
        ob = m['일반 구축']
        raw = st.mean(t['p84'] for t in ts)
        std = sum(WS.get(k, 0) * mean[k] for k in mean) / sum(WS.get(k, 0) for k in mean)
        c4 = collections.Counter(g4(t) for t in ts)
        r = dict(n=len(ts), nrb=len(rb), sh_rb=len(rb) / len(ts),
                 rb=st.mean(rb) if len(rb) >= 5 else None, ob=st.mean(ob) if len(ob) >= 5 else None,
                 new=mean.get('신축'), mid=mean.get('중간'), e3=eta(ts, g3), e4=eta(ts, g4), raw=raw, std=std,
                 share={k: c4[k] / len(ts) for k in ['신축', '재건축', '일반 구축', '중간']})
        r['prem'] = (r['rb'] / r['ob'] - 1) if r['rb'] and r['ob'] else None
        out['gu'][g]['t'] = r

    ro = sorted(GUS, key=lambda g: -out['gu'][g]['t']['raw'])
    so = sorted(GUS, key=lambda g: -out['gu'][g]['t']['std'])
    for g in GUS:
        out['gu'][g]['t']['rank_raw'] = ro.index(g) + 1
        out['gu'][g]['t']['rank_std'] = so.index(g) + 1
    out['dev'] = {k: st.mean(t['p84'] / out['gu'][t['g']]['t']['raw'] - 1 for t in ALL6 if t['grp'] == k) for k in G5}
    out['cnt'] = {k: sum(1 for t in ALL6 if t['grp'] == k) for k in G5}
    out['mix'] = WS
    out['n_all'] = N
    out['rb_complexes'] = len({(t['g'], t['n'], t['by']) for t in ALL6 if t['grp'].startswith('재건축')})
    out['rb_trades'] = sum(1 for t in ALL6 if t['grp'].startswith('재건축'))
    out['rb_trades84'] = sum(1 for t in ALL6 if t['grp'].startswith('재건축') and t['is84'])

    # ---------- 5) 가격 차이 분해 ----------
    ps = [t['p84'] for t in ALL6]; mu = st.mean(ps); tot = sum((p - mu) ** 2 for p in ps)


    def r2(key):
        c = collections.defaultdict(list)
        for t in ALL6: c[key(t)].append(t['p84'])
        m = {k: st.mean(v) for k, v in c.items()}
        return 1 - sum((t['p84'] - m[key(t)]) ** 2 for t in ALL6) / tot


    a = r2(lambda t: t['g']); b = r2(lambda t: (t['g'], g4(t))); c = r2(lambda t: (t['g'], t['d'], t['n'], t['by']))
    out['vardec'] = dict(gu=a, age=b - a, cx=c - b, rest=1 - c)

    json.dump(out, open(os.path.join(W, 'p84_data.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    print(f"p84_data.json: 기간 {M6[0]}~{M6[-1]}, 84㎡ {sum(v['n6'] for v in out['gu'].values()):,}건, "
          f"전 평형 {N:,}건, 재건축 {out['rb_complexes']}단지 {out['rb_trades']:,}건, "
          f"분해 구 {a:.0%}·유형 {b - a:.0%}·단지 {c - b:.0%}")


if __name__ == '__main__':
    main()
