# -*- coding: utf-8 -*-
"""구별 평당가(전용 기준, 만원/평) 월별 중앙값 + 3개월 이동중앙값, 양끝 6개월 평균 변화율.
   원칙(realprice-flow gotchas): 해제거래 제외, 상하위 1% 컷, 단일월 비교 금지."""
import csv, glob, json, os, statistics
WORKDIR = os.path.dirname(os.path.abspath(__file__))
PYEONG = 3.3058
import sys; sys.path.insert(0, WORKDIR)
from windows import MONTHS

result = {}
for f in sorted(glob.glob(os.path.join(WORKDIR, 'sale_*.csv'))):
    gu = os.path.basename(f)[5:-4]
    prices = []  # (ym, 평당가)
    for r in csv.DictReader(open(f, encoding='utf-8-sig')):
        if r['cdealType'] == 'O': continue
        try:
            amt = float(r['dealAmount'].replace(',', ''))
            ar = float(r['excluUseAr'])
            if ar <= 0: continue
        except ValueError:
            continue
        prices.append((r['ym'], amt / (ar / PYEONG)))
    if not prices: continue
    # 상하위 1% 컷 (구 단위)
    vals = sorted(p for _, p in prices)
    lo, hi = vals[int(len(vals)*0.01)], vals[int(len(vals)*0.99)-1]
    prices = [(ym, p) for ym, p in prices if lo <= p <= hi]
    monthly = {}
    for ym, p in prices:
        monthly.setdefault(ym, []).append(p)
    med = {ym: statistics.median(v) for ym, v in monthly.items()}
    cnt = {ym: len(v) for ym, v in monthly.items()}
    # 3개월 이동중앙값 (있는 달만)
    series, smooth = [], []
    for i, ym in enumerate(MONTHS):
        series.append(med.get(ym))
        window = [med[m] for m in MONTHS[max(0,i-2):i+1] if m in med]
        smooth.append(statistics.median(window) if window else None)
    first6 = [med[m] for m in MONTHS[:6] if m in med]
    last6 = [med[m] for m in MONTHS[-6:] if m in med]
    chg = None
    if first6 and last6:
        a, b = statistics.mean(first6), statistics.mean(last6)
        chg = (b / a - 1) * 100
    result[gu] = {
        'months': MONTHS,
        'median': [round(x) if x else None for x in series],
        'smooth': [round(x) if x else None for x in smooth],
        'count': [cnt.get(m, 0) for m in MONTHS],
        'first6_avg': round(statistics.mean(first6)) if first6 else None,
        'last6_avg': round(statistics.mean(last6)) if last6 else None,
        'chg_pct': round(chg, 1) if chg is not None else None,
        'total_trades': sum(cnt.values()),
    }

json.dump(result, open(os.path.join(WORKDIR, 'seoul_gu_insights.json'), 'w', encoding='utf-8'),
          ensure_ascii=False)
rank = sorted(result.items(), key=lambda kv: -(kv[1]['chg_pct'] or -99))
print(f"{'구':6s} {'첫6M평당':>9s} {'끝6M평당':>9s} {'변화':>7s} {'거래':>7s}")
for gu, d in rank:
    print(f"{gu:6s} {d['first6_avg'] or 0:9,} {d['last6_avg'] or 0:9,} {d['chg_pct'] or 0:6.1f}% {d['total_trades']:7,}")
