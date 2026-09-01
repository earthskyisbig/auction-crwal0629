# -*- coding: utf-8 -*-
"""한강벨트 5개 구 법정동별 매칭 지수 → belt_dong.json"""
import json, os, statistics
W = os.path.dirname(os.path.abspath(__file__))
import sys; sys.path.insert(0, W)
from windows import A, B
from sales_io import load_sales
PYEONG = 3.3058
BELT = ['성동구','광진구','동작구','송파구','강동구']
out = {}
for gu in BELT:
    dongs = {}
    for r in load_sales(gu, W):
        try:
            amt = float(r['dealAmount'].replace(',', '')); ar = float(r['excluUseAr'])
        except ValueError: continue
        if ar <= 0: continue
        key = (r['aptNm'].replace(' ',''), int(ar))
        px = amt / (ar / PYEONG)
        d = dongs.setdefault(r['umdNm'], {'a': {}, 'b': {}, 'cnt': 0, 'b_px': []})
        d['cnt'] += 1
        if r['ym'] in A: d['a'].setdefault(key, []).append(px)
        elif r['ym'] in B:
            d['b'].setdefault(key, []).append(px); d['b_px'].append(px)
    res = []
    for dong, d in dongs.items():
        ratios = [statistics.median(d['b'][k]) / statistics.median(d['a'][k])
                  for k in set(d['a']) & set(d['b'])
                  if len(d['a'][k]) >= 2 and len(d['b'][k]) >= 2]
        if len(ratios) < 4: continue
        res.append({'dong': dong, 'chg': round((statistics.median(ratios)-1)*100, 1),
                    'pairs': len(ratios), 'trades': d['cnt'],
                    'last_pp': round(statistics.median(d['b_px'])) if d['b_px'] else None})
    res.sort(key=lambda x: -x['chg'])
    out[gu] = res
json.dump(out, open(os.path.join(W, 'belt_dong.json'), 'w', encoding='utf-8'), ensure_ascii=False)
print('belt_dong.json 갱신:', {g: len(r) for g, r in out.items()})
