# -*- coding: utf-8 -*-
"""단지별 지수 → complex_index.json
   구별 리포트의 매칭 지수(같은 단지·평형의 A기간 대비 B기간 중앙값 비율)를 단지 하나하나에 적용한다.
   단지 키 = (구, 법정동, 정규화 단지명). 평형 = 전용면적 정수.
   각 단지: 24개월 거래수, 매칭 쌍 수·변화율, 최근 6개월 평당가 중앙값, 대표 평형(최근 6개월 최다 거래 평형)의
   매매 중앙가·전세 중앙가(신규)·전세가율·갭, K-apt 세대수·준공(app_data.json 에서 가져옴)."""
import json, os, re, statistics, sys
W = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, W)
from windows import MONTHS, A, B
from sales_io import load_sales, load_rent, list_gus
PYEONG = 3.3058
MIN_TRADES = 6          # 이보다 적으면 목록에서 제외 (파인더와 동일)


def norm(s):
    s = re.sub(r'[\s,()\-·.]+', '', s or '')
    return s.replace('이편한세상', 'e편한세상').lower()


def fnum(x):
    try: return float(str(x).replace(',', ''))
    except (TypeError, ValueError): return None


def matched_change(a_px, b_px, min_each=2):
    """{면적: [평당가]} A/B → (변화율 %, 쌍 수). 양쪽 각 min_each 건 이상인 평형만, 비율의 중앙값. 순수 함수."""
    ratios = []
    for k in set(a_px) & set(b_px):
        if len(a_px[k]) >= min_each and len(b_px[k]) >= min_each:
            ratios.append(statistics.median(b_px[k]) / statistics.median(a_px[k]))
    if not ratios:
        return None, 0
    return round((statistics.median(ratios) - 1) * 100, 1), len(ratios)


def summarize_complex(rows, rent_by_area=None):
    """한 단지의 매매 행(ym, amt[만원], ar, pp) → 지표 dict. 순수 함수.
    rent_by_area: {면적int: [전세보증금(만원)]} (최근 6개월 신규 계약)."""
    a_px, b_px, b_by_ar, pp_b = {}, {}, {}, []
    monthly = {}
    for ym, amt, ar, pp in rows:
        k = int(ar)
        monthly.setdefault(ym, []).append(pp)
        if ym in A: a_px.setdefault(k, []).append(pp)
        elif ym in B:
            b_px.setdefault(k, []).append(pp); b_by_ar.setdefault(k, []).append(amt); pp_b.append(pp)
    chg, pairs = matched_change(a_px, b_px)
    rec = {'t': len(rows), 'tb': len(pp_b), 'chg': chg, 'pairs': pairs,
           'pp': round(statistics.median(pp_b)) if pp_b else None,
           'ar': None, 'price': None, 'jeonse': None, 'jr': None, 'gap': None,
           's': [round(statistics.median(monthly[m])) if m in monthly else None for m in MONTHS]}
    if b_by_ar:
        ar = max(b_by_ar, key=lambda k: (len(b_by_ar[k]), k))     # 최근 6개월 최다 거래 평형
        price = statistics.median(b_by_ar[ar])
        rec.update({'ar': ar, 'price': round(price), 'n_ar': len(b_by_ar[ar])})
        deps = (rent_by_area or {}).get(ar) or []
        if len(deps) >= 2:
            je = statistics.median(deps)
            rec.update({'jeonse': round(je), 'jr': round(je / price * 100, 1), 'gap': round(price - je)})
    return rec


def main():
    app = {}
    ap = os.path.join(W, 'app_data.json')
    if os.path.exists(ap):
        for c in json.load(open(ap, encoding='utf-8'))['complexes']:
            app[(c['g'], c['d'], norm(c['n']))] = c
    out = []
    for gu in list_gus(W):
        rent = {}
        for r in load_rent(gu, W):
            if (r.get('contractType') or '').strip() == '갱신' or r.get('ym') not in B: continue
            dep, mr, ar = fnum(r['deposit']), fnum(r['monthlyRent'] or 0), fnum(r['excluUseAr'])
            if not dep or (mr and mr > 0) or not ar: continue
            rent.setdefault((r.get('umdNm', ''), norm(r['aptNm'])), {}).setdefault(int(ar), []).append(dep)
        groups = {}
        for r in load_sales(gu, W):
            amt, ar = fnum(r['dealAmount']), fnum(r['excluUseAr'])
            if not amt or not ar or ar <= 0: continue
            g = groups.setdefault((r['umdNm'], norm(r['aptNm'])), {'nm': r['aptNm'], 'rows': []})
            g['rows'].append((r['ym'], amt, ar, amt / (ar / PYEONG)))
        for (dong, nk), g in groups.items():
            if len(g['rows']) < MIN_TRADES: continue
            rec = summarize_complex(g['rows'], rent.get((dong, nk)))
            rec.update({'g': gu, 'd': dong, 'n': g['nm']})
            k = app.get((gu, dong, nk))
            if k:
                rec.update({'hh': k.get('hh'), 'bt': k.get('bt'), 'sw': k.get('sw')})
            out.append(rec)
    out.sort(key=lambda r: (r['g'], r['d'], r['n']))
    json.dump({'months': MONTHS, 'complexes': out},
              open(os.path.join(W, 'complex_index.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    n_m = sum(1 for r in out if r['chg'] is not None)
    print(f'단지 {len(out)}개 (매칭 지수 산출 {n_m}, 전세가율 {sum(1 for r in out if r["jr"])}) → complex_index.json')


if __name__ == '__main__':
    main()
