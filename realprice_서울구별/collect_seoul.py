# -*- coding: utf-8 -*-
"""서울 25개 구 아파트 매매 실거래 24개월 수집 (RTMS 직접 호출, 구별 증분 CSV 저장)"""
import csv, os, sys, time, warnings, xml.etree.ElementTree as ET
warnings.filterwarnings('ignore')
import requests, urllib3
urllib3.disable_warnings()
from dotenv import load_dotenv
_ENV = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env')
load_dotenv(_ENV if os.path.exists(_ENV) else None)   # 저장소 루트 .env (경로 하드코딩 제거, 클라우드 루틴 호환)
KEY = os.getenv('PUBLIC_DATA_SERVICE_KEY')
if not KEY:
    sys.exit('PUBLIC_DATA_SERVICE_KEY 가 없습니다 — 저장소 루트 .env 확인 (.env.example 참고)')
RTMS = 'https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev'
WORKDIR = os.path.dirname(os.path.abspath(__file__))

GUS = {
    '종로구':'11110','중구':'11140','용산구':'11170','성동구':'11200','광진구':'11215',
    '동대문구':'11230','중랑구':'11260','성북구':'11290','강북구':'11305','도봉구':'11320',
    '노원구':'11350','은평구':'11380','서대문구':'11410','마포구':'11440','양천구':'11470',
    '강서구':'11500','구로구':'11530','금천구':'11545','영등포구':'11560','동작구':'11590',
    '관악구':'11620','서초구':'11650','강남구':'11680','송파구':'11710','강동구':'11740',
}
import sys as _sys; _sys.path.insert(0, WORKDIR)
from windows import MONTHS
FIELDS = ['gu','ym','umdNm','aptNm','excluUseAr','dealAmount','floor','buildYear','dealDay','cdealType','jibun','bonbun','bubun']  # 지번: 정비구역 대표지번 대조용(p84_compute.py)

def fetch_month(code, ym):
    """순차 호출 + 초당제한(429/에러XML) 백오프. 실패 시 예외 → 상위에서 구 단위 재시도."""
    rows, page = [], 1
    while page <= 10:
        root = None
        for attempt in range(6):
            time.sleep(0.35)
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
        items = root.findall('.//item')
        for it in items:
            d = {c.tag: (c.text or '').strip() for c in it}
            rows.append(d)
        total = int(root.findtext('.//totalCount') or 0)
        if page * 1000 >= total: break
        page += 1
    return rows

def collect_gu(gu):
    code = GUS[gu]
    out = os.path.join(WORKDIR, f'sale_{gu}.csv')
    if os.path.exists(out) and os.path.getsize(out) > 200:
        print(f'skip {gu}', flush=True)
        return
    all_rows = []
    for ym in MONTHS:
        rows = fetch_month(code, ym)
        for d in rows:
            all_rows.append({'gu': gu, 'ym': f"{d.get('dealYear')}{int(d.get('dealMonth') or 0):02d}",
                             'umdNm': d.get('umdNm'), 'aptNm': d.get('aptNm'),
                             'excluUseAr': d.get('excluUseAr'), 'dealAmount': d.get('dealAmount'),
                             'floor': d.get('floor'), 'buildYear': d.get('buildYear'),
                             'dealDay': d.get('dealDay'), 'cdealType': d.get('cdealType'),
                             'jibun': d.get('jibun'), 'bonbun': d.get('bonbun'), 'bubun': d.get('bubun')})
    w = csv.DictWriter(open(out, 'w', encoding='utf-8-sig', newline=''), fieldnames=FIELDS)
    w.writeheader(); w.writerows(all_rows)
    print(f'{gu}: {len(all_rows)}건', flush=True)

def collect_gu_retry(gu, attempts=2):
    """fetch_month 의 '재시도 초과'는 구 단위로 한 번 더 시도한다(refresh_all.sh 의 set -e 로 전체가 죽지 않게)."""
    for i in range(1, attempts + 1):
        try:
            return collect_gu(gu)
        except RuntimeError as e:
            print(f'  [{gu}] 시도 {i}/{attempts} 실패: {e}', flush=True)
            if i == attempts:
                raise
            time.sleep(10)


if __name__ == '__main__':
    targets = sys.argv[1:] or list(GUS)
    for gu in targets:
        collect_gu_retry(gu)
    if not sys.argv[1:]:
        # 25개 구 전부 끝났을 때만 기간 매니페스트 기록 → 이후 분석 스크립트는 이 기간을 쓴다
        from windows import write_manifest
        write_manifest(MONTHS)
    print('done')
