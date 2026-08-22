# -*- coding: utf-8 -*-
"""서울 25개 구 아파트 전월세 실거래 최근 6개월(2026.03~08) 수집 — rent_<구>.csv 증분 저장"""
import csv, os, sys, time, warnings, xml.etree.ElementTree as ET
warnings.filterwarnings('ignore')
import requests, urllib3
urllib3.disable_warnings()
from dotenv import load_dotenv
load_dotenv('/Users/leomyung/auction-crwal0629/.env')
KEY = os.getenv('PUBLIC_DATA_SERVICE_KEY')
RTMS = 'https://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent'
W = os.path.dirname(os.path.abspath(__file__))

GUS = {
    '종로구':'11110','중구':'11140','용산구':'11170','성동구':'11200','광진구':'11215',
    '동대문구':'11230','중랑구':'11260','성북구':'11290','강북구':'11305','도봉구':'11320',
    '노원구':'11350','은평구':'11380','서대문구':'11410','마포구':'11440','양천구':'11470',
    '강서구':'11500','구로구':'11530','금천구':'11545','영등포구':'11560','동작구':'11590',
    '관악구':'11620','서초구':'11650','강남구':'11680','송파구':'11710','강동구':'11740',
}
import sys; sys.path.insert(0, W)
from windows import RENT_MONTHS as MONTHS
FIELDS = ['gu','ym','umdNm','aptNm','excluUseAr','deposit','monthlyRent','floor','contractType']

def fetch_month(code, ym):
    rows, page = [], 1
    while page <= 15:
        root = None
        for attempt in range(6):
            time.sleep(0.3)
            try:
                r = requests.get(RTMS, params={'serviceKey': KEY, 'LAWD_CD': code, 'DEAL_YMD': ym,
                                               'numOfRows': 1000, 'pageNo': page}, verify=False, timeout=30)
                doc = ET.fromstring(r.text)
            except Exception:
                time.sleep(2); continue
            if doc.findtext('.//returnReasonCode') or doc.findtext('.//resultCode') not in ('000', None):
                time.sleep(2 + attempt * 2); continue
            root = doc; break
        if root is None:
            raise RuntimeError(f'{code} {ym} p{page}: 재시도 초과')
        for it in root.findall('.//item'):
            rows.append({c.tag: (c.text or '').strip() for c in it})
        total = int(root.findtext('.//totalCount') or 0)
        if page * 1000 >= total: break
        page += 1
    return rows

for gu in (sys.argv[1:] or list(GUS)):
    out = os.path.join(W, f'rent_{gu}.csv')
    if os.path.exists(out) and os.path.getsize(out) > 200:
        print(f'skip {gu}', flush=True)
        continue
    all_rows = []
    for ym in MONTHS:
        for d in fetch_month(GUS[gu], ym):
            all_rows.append({'gu': gu, 'ym': f"{d.get('dealYear')}{int(d.get('dealMonth') or 0):02d}",
                             'umdNm': d.get('umdNm'), 'aptNm': d.get('aptNm'),
                             'excluUseAr': d.get('excluUseAr'), 'deposit': d.get('deposit'),
                             'monthlyRent': d.get('monthlyRent'), 'floor': d.get('floor'),
                             'contractType': d.get('contractType')})
    w = csv.DictWriter(open(out, 'w', encoding='utf-8-sig', newline=''), fieldnames=FIELDS)
    w.writeheader(); w.writerows(all_rows)
    print(f'{gu}: {len(all_rows)}건', flush=True)
print('done')
