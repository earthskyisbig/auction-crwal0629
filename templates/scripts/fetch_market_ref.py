# -*- coding: utf-8 -*-
"""템플릿 실거래 참조 카드용: 단지별 월별 집계 + 최근거래 + 통계"""
import os, re, json, statistics, warnings
warnings.filterwarnings('ignore')
import PublicDataReader as pdr
from dotenv import load_dotenv, find_dotenv
from datetime import datetime

load_dotenv(find_dotenv(usecwd=True))
key = os.getenv('PUBLIC_DATA_SERVICE_KEY')
api = pdr.TransactionPrice(key)

now = datetime.now()
ey, em = (now.year, now.month - 1) if now.month > 1 else (now.year - 1, 12)
yms = []
y, m = ey, em
for _ in range(12):
    yms.append(f'{y}{m:02d}')
    m -= 1
    if m < 1: y, m = y - 1, 12
yms = yms[::-1]  # 과거→최근

TARGETS = [
    ('lotte', '안성롯데캐슬', '41550', 75.7, 4.0),      # 74.44~77.03 계열 통합
    ('elcru', '평택뉴비전엘크루', '41220', 74.834, 3.0),
    ('hille', '힐스테이트평택2차', '41220', 101.41, 3.0),
]

out = {}
for tid, name, sgg, area_c, tol in TARGETS:
    core = re.sub(r'\s+', '', name)
    trades = []
    for ym in yms:
        try:
            df = api.get_data(property_type='아파트', trade_type='매매',
                              sigungu_code=sgg, year_month=ym, verbose=False)
        except Exception:
            continue
        if df is None or len(df) == 0: continue
        namecol = '단지명' if '단지명' in df.columns else ('아파트' if '아파트' in df.columns else None)
        if not namecol: continue
        for _, r in df.iterrows():
            nm = re.sub(r'\s+', '', str(r.get(namecol, '')))
            if not (core in nm or nm in core): continue
            try: area = float(r.get('전용면적'))
            except (TypeError, ValueError): continue
            if abs(area - area_c) > tol: continue
            if str(r.get('해제여부', '')).strip() == 'O': continue
            try: amt = int(str(r.get('거래금액')).replace(',', ''))  # 만원
            except (TypeError, ValueError): continue
            day = str(r.get('일', '') or '')
            trades.append({'ym': ym, 'day': day, 'area': area,
                           'floor': r.get('층', ''), 'amt': amt})
    prices = [t['amt'] for t in trades]
    monthly = []
    for ym in yms:
        sub = [t['amt'] for t in trades if t['ym'] == ym]
        monthly.append([f"{ym[2:4]}.{ym[4:]}", len(sub), round(sum(sub)/len(sub)) if sub else 0])
    recent = sorted(trades, key=lambda t: (t['ym'], t['day']), reverse=True)[:5]
    out[tid] = {
        'name': name, 'cnt': len(trades),
        'med': round(statistics.median(prices)) if prices else 0,
        'min': min(prices) if prices else 0, 'max': max(prices) if prices else 0,
        'months': monthly,
        'recent': [[f"20{t['ym'][2:4]}.{t['ym'][4:]}.{str(t['day']).zfill(2)}",
                    f"{t['area']:g}㎡", f"{t['floor']}층", t['amt']] for t in recent],
    }
    print(tid, name, 'cnt=', out[tid]['cnt'], 'med=', out[tid]['med'])

with open('_workspace/top10_0819/market_ref.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print('saved market_ref.json')
