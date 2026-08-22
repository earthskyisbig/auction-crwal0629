# -*- coding: utf-8 -*-
"""구별 전세가율: 2026.03~08 동일 (단지, 전용면적 정수)에서
   전세 보증금 중앙값 ÷ 매매가 중앙값 비율의 중앙값 (쌍 10개 이상)"""
import csv, glob, json, os, statistics
W = os.path.dirname(os.path.abspath(__file__))
import sys; sys.path.insert(0, W)
from windows import B

out = {}
for f in sorted(glob.glob(os.path.join(W, 'rent_*.csv'))):
    gu = os.path.basename(f)[5:-4]
    je = {}
    for r in csv.DictReader(open(f, encoding='utf-8-sig')):
        try:
            dep = float(r['deposit'].replace(',', ''))
            mr = float((r['monthlyRent'] or '0').replace(',', ''))
            ar = float(r['excluUseAr'])
        except ValueError:
            continue
        if mr > 0 or ar <= 0 or dep <= 0: continue  # 순수 전세만
        je.setdefault((r['aptNm'].replace(' ', ''), int(ar)), []).append(dep)
    sale = {}
    for r in csv.DictReader(open(os.path.join(W, f'sale_{gu}.csv'), encoding='utf-8-sig')):
        if r['cdealType'] == 'O' or r['ym'] not in B: continue
        try:
            amt = float(r['dealAmount'].replace(',', '')); ar = float(r['excluUseAr'])
        except ValueError:
            continue
        if ar <= 0: continue
        sale.setdefault((r['aptNm'].replace(' ', ''), int(ar)), []).append(amt)
    ratios = []
    for k in set(je) & set(sale):
        if len(je[k]) >= 2 and len(sale[k]) >= 1:
            ratios.append(statistics.median(je[k]) / statistics.median(sale[k]))
    out[gu] = {'jeonse_ratio': round(statistics.median(ratios) * 100, 1) if len(ratios) >= 10 else None,
               'pairs': len(ratios)}
json.dump(out, open(os.path.join(W, 'jeonse_ratio.json'), 'w', encoding='utf-8'), ensure_ascii=False)
for gu, d in sorted(out.items(), key=lambda kv: -(kv[1]['jeonse_ratio'] or 0)):
    print(f"{gu:6s} 전세가율 {d['jeonse_ratio']}% ({d['pairs']}쌍)")
