# -*- coding: utf-8 -*-
"""아파트 검색·분석기 데이터 빌더 → app_data.json
   실거래(24M)·전세(6M)·K-apt 프로파일을 단지 단위로 결합"""
import json, os, re, statistics
W = os.path.dirname(os.path.abspath(__file__))
import sys; sys.path.insert(0, W)
from windows import MONTHS, B
from sales_io import load_sales, load_rent, list_gus
PYEONG = 3.3058
MIN_TRADES = 6

def norm(s):
    s = re.sub(r'[\s,()\-·.]+', '', s or '')
    return s.replace('이편한세상', 'e편한세상').lower()

def fnum(x):
    try: return float(str(x).replace(',', ''))
    except (TypeError, ValueError): return None

complexes = []
for gu in list_gus(W):
    # K-apt 프로파일 인덱스 (동 우선 → 전체)
    kapt = []
    kf = os.path.join(W, f'kapt_{gu}.json')
    if os.path.exists(kf):
        kapt = json.load(open(kf, encoding='utf-8'))
    # (법정동, 이름) 우선 → 이름+준공연도(±1) → 이름 단독 순으로 매칭 (동명 단지: 삼성·신동아·현대… 오매칭 방지)
    kidx_dong, kidx_name = {}, {}
    for k in kapt:
        kidx_dong.setdefault((k.get('dong_nm') or '', norm(k['name'])), k)
        kidx_name.setdefault(norm(k['name']), []).append(k)
    def match_kapt(dong, nk, build_year):
        k = kidx_dong.get((dong, nk))
        if k: return k
        cands = kidx_name.get(nk) or []
        if build_year:
            for c in cands:
                by = (c.get('built') or '')[:4]
                if by.isdigit() and abs(int(by) - build_year) <= 1:
                    return c
        if len(cands) == 1:
            return cands[0]
        # 부분 일치는 같은 법정동 안에서만
        for (d, kn), c in kidx_dong.items():
            if d == dong and (nk in kn or kn in nk):
                return c
        return None
    # 전세: (단지norm, 면적int) → 보증금 리스트
    je = {}   # (법정동, 단지norm) → {면적int: [보증금]}
    for r in load_rent(gu, W):
        if (r.get('contractType') or '').strip() == '갱신': continue
        dep, mr, ar = fnum(r['deposit']), fnum(r['monthlyRent'] or 0), fnum(r['excluUseAr'])
        if not dep or (mr and mr > 0) or not ar: continue
        je.setdefault((r.get('umdNm', ''), norm(r['aptNm'])), {}).setdefault(int(ar), []).append(dep)
    # 매매 그룹핑
    groups = {}
    for r in load_sales(gu, W):
        amt, ar = fnum(r['dealAmount']), fnum(r['excluUseAr'])
        if not amt or not ar: continue
        key = (r['umdNm'], norm(r['aptNm']))
        g = groups.setdefault(key, {'nm': r['aptNm'], 'rows': [], 'by': []})
        if (r.get('buildYear') or '').isdigit(): g['by'].append(int(r['buildYear']))
        try: fl = int(float(r['floor']))
        except (TypeError, ValueError): fl = None
        g['rows'].append((r['ym'], amt, ar, fl, amt / (ar / PYEONG)))
    for (dong, nk), g in groups.items():
        rows = g['rows']
        if len(rows) < MIN_TRADES: continue
        monthly = {}
        for ym, amt, ar, fl, pp in rows:
            monthly.setdefault(ym, []).append(pp)
        series = [round(statistics.median(monthly[m])) if m in monthly else None for m in MONTHS]
        cnt = [len(monthly.get(m, [])) for m in MONTHS]
        vals = [v for v in series if v]
        first = [series[i] for i in range(8) if series[i]]
        last = [series[i] for i in range(len(series)-8, len(series)) if series[i]]
        chg = round((statistics.mean(last) / statistics.mean(first) - 1) * 100, 1) if len(first) >= 2 and len(last) >= 2 else None
        # 층 밴드 (전체 24M)
        fb = {'저(1~5)': [], '중(6~15)': [], '고(16+)': []}
        for ym, amt, ar, fl, pp in rows:
            if fl is None: continue
            fb['저(1~5)' if fl <= 5 else '중(6~15)' if fl <= 15 else '고(16+)'].append(pp)
        floors = {k: round(statistics.median(v)) for k, v in fb.items() if len(v) >= 3}
        # 평형 구간 (전용)
        sz = {}
        for ym, amt, ar, fl, pp in rows:
            b = '~40' if ar < 40 else '40~62' if ar < 62 else '62~85' if ar < 85 else '85~110' if ar < 110 else '110+'
            s = sz.setdefault(b, {'n': 0, 'recent': []})
            s['n'] += 1
            if ym in B: s['recent'].append(amt)
        sizes = {b: {'n': s['n'], 'p': round(statistics.median(s['recent'])) if s['recent'] else None}
                 for b, s in sz.items()}
        # 전세가율 (단지)
        jr_pairs = []
        sale_by_ar = {}
        for ym, amt, ar, fl, pp in rows:
            if ym in B: sale_by_ar.setdefault(int(ar), []).append(amt)
        for jar, deps in (je.get((dong, nk)) or {}).items():
            if jar in sale_by_ar and len(deps) >= 2:
                jr_pairs.append(statistics.median(deps) / statistics.median(sale_by_ar[jar]))
        jr = round(statistics.median(jr_pairs) * 100, 1) if jr_pairs else None
        k = match_kapt(dong, nk, statistics.mode(g['by']) if g['by'] else None)
        rec = {'n': g['nm'], 'g': gu, 'd': dong, 't': len(rows), 'chg': chg,
               'last': round(statistics.mean(last)) if last else None,
               's': series, 'c': cnt, 'fl': floors, 'sz': sizes, 'jr': jr}
        if k:
            rec.update({'hh': k['hh'] or None, 'bd': k.get('dongs'), 'bt': k.get('built'),
                        'tf': k.get('top_floor'), 'ht': k.get('heat'),
                        'sw': [k.get('subway_line'), k.get('subway_st'), k.get('subway_time')],
                        'edu': k.get('edu'), 'pk': k.get('park'), 'pku': k.get('park_u')})
        complexes.append(rec)

complexes.sort(key=lambda r: (r['g'], r['d'], r['n']))
out = {'months': MONTHS, 'complexes': complexes}
json.dump(out, open(os.path.join(W, 'app_data.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
size = os.path.getsize(os.path.join(W, 'app_data.json'))
matched = sum(1 for c in complexes if c.get('hh'))
print(f'단지 {len(complexes)}개 (K-apt 매칭 {matched}) → app_data.json {size/1e6:.1f}MB')
