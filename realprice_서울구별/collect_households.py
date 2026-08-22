# -*- coding: utf-8 -*-
"""서울 구별 공동주택(아파트) 세대수 합산 — AptListService3 + AptBasisInfoServiceV4.
   구별 hh_<구>.json 증분 저장(재실행 시 스킵). K-apt 등재(의무관리대상) 단지 기준."""
import json, os, sys, time, warnings
warnings.filterwarnings('ignore')
import requests, urllib3
urllib3.disable_warnings()
from dotenv import load_dotenv
load_dotenv('/Users/leomyung/auction-crwal0629/.env')
KEY = os.getenv('PUBLIC_DATA_SERVICE_KEY')
LIST = 'https://apis.data.go.kr/1613000/AptListService3/getSigunguAptList3'
BASS = 'https://apis.data.go.kr/1613000/AptBasisInfoServiceV4/getAphusBassInfoV4'
W = os.path.dirname(os.path.abspath(__file__))

GUS = {
    '종로구':'11110','중구':'11140','용산구':'11170','성동구':'11200','광진구':'11215',
    '동대문구':'11230','중랑구':'11260','성북구':'11290','강북구':'11305','도봉구':'11320',
    '노원구':'11350','은평구':'11380','서대문구':'11410','마포구':'11440','양천구':'11470',
    '강서구':'11500','구로구':'11530','금천구':'11545','영등포구':'11560','동작구':'11590',
    '관악구':'11620','서초구':'11650','강남구':'11680','송파구':'11710','강동구':'11740',
}

def jget(url, params, tries=5):
    for a in range(tries):
        time.sleep(0.25)
        try:
            r = requests.get(url, params={**params, 'serviceKey': KEY, '_type': 'json'},
                             verify=False, timeout=30)
            j = r.json()
            body = (j.get('response') or {}).get('body')
            if body is not None: return body
        except Exception:
            pass
        time.sleep(1.5 + a)
    return None

def apt_list(code):
    out, page = [], 1
    while page <= 20:
        b = jget(LIST, {'sigunguCode': code, 'pageNo': page, 'numOfRows': 500})
        its = (b or {}).get('items') or []
        if isinstance(its, dict): its = its.get('item') or []
        if not its: break
        out += its
        if len(its) < 500: break
        page += 1
    return out

for gu in (sys.argv[1:] or list(GUS)):
    out = os.path.join(W, f'hh_{gu}.json')
    if os.path.exists(out):
        print(f'skip {gu}', flush=True)
        continue
    lst = apt_list(GUS[gu])
    total, done, miss = 0, 0, 0
    for a in lst:
        b = jget(BASS, {'kaptCode': a['kaptCode']})
        it = (b or {}).get('item') or {}
        hh = it.get('kaptdaCnt') or it.get('hoCnt') or 0
        try: hh = int(float(hh))
        except (TypeError, ValueError): hh = 0
        if hh > 0: total += hh; done += 1
        else: miss += 1
    json.dump({'gu': gu, 'complexes': len(lst), 'with_data': done, 'missing': miss,
               'households': total}, open(out, 'w', encoding='utf-8'), ensure_ascii=False)
    print(f'{gu}: 단지 {len(lst)}개, 세대수 {total:,} (누락 {miss})', flush=True)
print('done')
