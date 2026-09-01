# -*- coding: utf-8 -*-
"""구성편향 보정: 동일 (단지, 전용면적 정수) 쌍의 두 기간 중앙값 비율로 변화율 산출.
   A=롤링 24개월의 첫 6개월, B=최근 6개월 (windows.py). 양쪽 각 2건 이상인 쌍만 사용, 비율의 중앙값."""
import json, os, statistics
WORKDIR = os.path.dirname(os.path.abspath(__file__))
PYEONG = 3.3058
import sys; sys.path.insert(0, WORKDIR)
from windows import A, B
from sales_io import load_sales, list_gus

out = {}
for gu in list_gus(WORKDIR):
    a_px, b_px = {}, {}
    for r in load_sales(gu, WORKDIR):
        try:
            amt = float(r['dealAmount'].replace(',', ''))
            ar = float(r['excluUseAr'])
        except ValueError: continue
        if ar <= 0: continue
        key = (r['umdNm'], r['aptNm'].replace(' ', ''), int(ar))   # 법정동 포함 — 동명 단지 혼입 방지
        px = amt / (ar / PYEONG)
        if r['ym'] in A: a_px.setdefault(key, []).append(px)
        elif r['ym'] in B: b_px.setdefault(key, []).append(px)
    ratios = []
    for k in set(a_px) & set(b_px):
        if len(a_px[k]) >= 2 and len(b_px[k]) >= 2:
            ratios.append(statistics.median(b_px[k]) / statistics.median(a_px[k]))
    out[gu] = {'matched_chg_pct': round((statistics.median(ratios) - 1) * 100, 1) if len(ratios) >= 5 else None,
               'pairs': len(ratios)}

json.dump(out, open(os.path.join(WORKDIR, 'seoul_gu_matched.json'), 'w', encoding='utf-8'), ensure_ascii=False)
for gu, d in sorted(out.items(), key=lambda kv: -(kv[1]['matched_chg_pct'] if kv[1]['matched_chg_pct'] is not None else -99)):
    print(f"{gu:6s} 매칭 {d['matched_chg_pct'] if d['matched_chg_pct'] is not None else '  -  '}%  ({d['pairs']}쌍)")
