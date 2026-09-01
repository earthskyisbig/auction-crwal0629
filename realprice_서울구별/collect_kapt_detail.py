# -*- coding: utf-8 -*-
"""서울 전체 공동주택 단지 상세 프로파일 수집 → kapt_<구>.json
   (세대수·동수·준공·최고층·지하철·교육시설·주차)"""
import json, os, sys, time, warnings
warnings.filterwarnings('ignore')
import requests, urllib3
urllib3.disable_warnings()
from dotenv import load_dotenv
_ENV = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env')
load_dotenv(_ENV if os.path.exists(_ENV) else None)   # 저장소 루트 .env (경로 하드코딩 제거, 클라우드 루틴 호환)
KEY = os.getenv('PUBLIC_DATA_SERVICE_KEY')
if not KEY:
    sys.exit('PUBLIC_DATA_SERVICE_KEY 가 없습니다 — 저장소 루트 .env 확인 (.env.example 참고)')
LIST = 'https://apis.data.go.kr/1613000/AptListService3/getSigunguAptList3'
BASS = 'https://apis.data.go.kr/1613000/AptBasisInfoServiceV4/getAphusBassInfoV4'
DTL  = 'https://apis.data.go.kr/1613000/AptBasisInfoServiceV4/getAphusDtlInfoV4'
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

def g(d, k):
    v = (d or {}).get(k)
    return None if v in (None, '', ' ', 'null') else v

def main():
    """구별 증분 수집 (파일 있으면 스킵). import 만으로 실행되지 않도록 가드."""
    for gu in (sys.argv[1:] or list(GUS)):
        out = os.path.join(W, f'kapt_{gu}.json')
        if os.path.exists(out) and os.path.getsize(out) > 500:
            print(f'skip {gu}', flush=True)
            continue
        lst, page = [], 1
        while page <= 20:
            b = jget(LIST, {'sigunguCode': GUS[gu], 'pageNo': page, 'numOfRows': 500})
            its = (b or {}).get('items') or []
            if isinstance(its, dict): its = its.get('item') or []
            if not its: break
            lst += its
            if len(its) < 500: break
            page += 1
        recs = []
        for a in lst:
            kc = a['kaptCode']
            base = (jget(BASS, {'kaptCode': kc}) or {}).get('item') or {}
            dtl = (jget(DTL, {'kaptCode': kc}) or {}).get('item') or {}
            hh = g(base, 'kaptdaCnt') or g(base, 'hoCnt') or 0
            try: hh = int(float(hh))
            except (TypeError, ValueError): hh = 0
            ud = g(base, 'kaptUsedate') or ''
            recs.append({
                'code': kc, 'name': g(base, 'kaptName') or a.get('kaptName'),
                'dong_nm': a.get('as3'), 'hh': hh,
                'dongs': g(base, 'kaptDongCnt'), 'built': ud[:6],
                'top_floor': g(base, 'kaptTopFloor'),
                'heat': g(base, 'codeHeatNm'), 'hall': g(base, 'codeHallNm'),
                'subway_line': g(dtl, 'subwayLine'), 'subway_st': g(dtl, 'subwayStation'),
                'subway_time': g(dtl, 'kaptdWtimesub'),
                'edu': g(dtl, 'educationFacility'),
                'park': g(dtl, 'kaptdPcnt'), 'park_u': g(dtl, 'kaptdPcntu'),
            })
        json.dump(recs, open(out, 'w', encoding='utf-8'), ensure_ascii=False)
        print(f'{gu}: {len(recs)}개 단지', flush=True)
    print('done')


if __name__ == '__main__':
    main()
