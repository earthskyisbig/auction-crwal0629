# -*- coding: utf-8 -*-
"""행안부 주민등록인구(구별, 전월 기준) → population_202607.json 갱신"""
import json, os, re
from datetime import date
import requests, urllib3, warnings
warnings.filterwarnings('ignore'); urllib3.disable_warnings()
W = os.path.dirname(os.path.abspath(__file__))
t = date.today()
y, m = (t.year, t.month - 1) if t.month > 1 else (t.year - 1, 12)
r = requests.post('https://jumin.mois.go.kr/statMonth.do', headers={'User-Agent': 'Mozilla/5.0'},
                  data={'searchYearMonth': 'month', 'searchYearStart': y, 'searchMonthStart': f'{m:02d}',
                        'searchYearEnd': y, 'searchMonthEnd': f'{m:02d}', 'sltOrgLvl1': '1100000000',
                        'sltOrgLvl2': 'A', 'category': 'month', 'sltOrgType': '2'}, timeout=30, verify=False)
pop = {}
for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', r.text, re.S):
    c = re.findall(r'<t[dh][^>]*>\s*(?:<[^>]+>)*([^<]+)', tr)
    if len(c) >= 3 and c[1].strip().endswith('구'):
        try: pop[c[1].strip()] = int(c[2].replace(',', ''))
        except ValueError: pass
if len(pop) == 25:
    json.dump(pop, open(os.path.join(W, 'population_202607.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    print(f'인구 갱신 완료 ({y}.{m:02d} 기준, 25개 구)')
else:
    print(f'⚠️ 인구 {len(pop)}개 구만 수신 — 기존 파일 유지')
