# -*- coding: utf-8 -*-
"""후보 물건을 사용자 우선순위 기준으로 평가:
   1) 최근 12개월 실거래량/세대수 >= 4%  2) 동일평형(±2㎡) 실거래 최고가 > 감정가
   3) 역세권·학세권 (K-apt 상세정보)
결과 → priority_eval.json

사용법: 아래 ITEMS 를 후보 물건으로 채운 뒤 실행 (프로젝트 루트, .env 필요).
PublicDataReader 는 segfault 나므로 쓰지 말 것 — RTMS XML 직접 호출.
data.go.kr 초당 제한: 병렬 금지, 호출당 sleep 0.35s + 에러XML 백오프."""
import json, os, re, time, warnings, xml.etree.ElementTree as ET
warnings.filterwarnings('ignore')
import requests, urllib3
urllib3.disable_warnings()
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(usecwd=True))
KEY = os.getenv('PUBLIC_DATA_SERVICE_KEY')
LIST = 'https://apis.data.go.kr/1613000/AptListService3/getSigunguAptList3'
DTL  = 'https://apis.data.go.kr/1613000/AptBasisInfoServiceV4/getAphusDtlInfoV4'
RTMS = 'https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev'

# ▼▼ 후보 물건 입력: (사건번호, K-apt 정확명, RTMS 이름키워드, 시군구코드들, 법정동, 전용㎡,
#                   감정가(만원), 최저가(만원), 유찰, 매각기일, 준공, 세대수)
ITEMS = [
    # ('수원 2025타경58196', '수원하늘채더퍼스트2단지', '하늘채더퍼스트', ['41113'], '곡반정동',
    #  84.96, 66000, 46200, 1, '8.24', '2022.06', 1833),
]

# 최근 12개월 (실행 시점 기준)
from datetime import date
def month_list(n=12):
    y, m = date.today().year, date.today().month
    out = []
    for _ in range(n):
        out.append(f'{y}{m:02d}')
        m -= 1
        if m == 0: y, m = y - 1, 12
    return list(reversed(out))
MONTHS = month_list()

def norm(s):
    return re.sub(r'[\s,()\-·.]+', '', str(s or '')).replace('이편한세상', 'e편한세상').lower()

def jget(url, params):
    r = requests.get(url, params={**params, 'serviceKey': KEY, '_type': 'json'}, verify=False, timeout=30)
    return (r.json().get('response') or {}).get('body') or {}

APT = {}
def apt_list(code):
    if code in APT: return APT[code]
    out, page = [], 1
    while page <= 20:
        b = jget(LIST, {'sigunguCode': code, 'pageNo': page, 'numOfRows': 500})
        its = b.get('items') or []
        if isinstance(its, dict): its = its.get('item') or []
        if not its: break
        out += its
        if len(its) < 500: break
        page += 1
    APT[code] = out
    return out

TR = {}
def trades(code):
    if code in TR: return TR[code]
    rows = []
    for ym in MONTHS:
        page = 1
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
                break
            for it in root.findall('.//item'):
                rows.append({c.tag: (c.text or '').strip() for c in it})
            total = int(root.findtext('.//totalCount') or 0)
            if page * 1000 >= total: break
            page += 1
    TR[code] = rows
    print(f'  [RTMS] {code}: 12개월 {len(rows)}건')
    return rows

results = []
for (case, kname, tkey, sggs, dong, area, appr, low, flbd, day, built, hh) in ITEMS:
    rec = {'case': case, 'name': kname, 'dong': dong, 'area': area, 'appr': appr, 'low': low,
           'flbd': flbd, 'day': day, 'built': built, 'households': hh}
    kapt = None
    for c in sggs:
        for a in apt_list(c):
            if norm(a.get('kaptName')) == norm(kname):
                kapt = a['kaptCode']; break
        if kapt: break
    if kapt:
        d = jget(DTL, {'kaptCode': kapt}).get('item') or {}
        rec['subway'] = f"{d.get('subwayLine') or ''} {d.get('subwayStation') or ''}".strip()
        rec['subway_time'] = d.get('kaptdWtimesub')
        rec['edu'] = d.get('educationFacility')
    allrows = []
    for c in sggs: allrows += trades(c)
    nk = norm(tkey)
    m = [t for t in allrows if nk in norm(t.get('aptNm')) and t.get('umdNm', '') == dong]
    if not m:
        m = [t for t in allrows if nk in norm(t.get('aptNm'))]
    m = [t for t in m if t.get('cdealType') != 'O']
    same = []
    for t in m:
        try: ar = float(t.get('excluUseAr') or 0)
        except ValueError: continue
        if abs(ar - area) <= 2.0:
            same.append(int(t['dealAmount'].replace(',', '')))
    rec['trades_12m'] = len(m)
    rec['turnover_pct'] = round(len(m) / hh * 100, 2)
    rec['same_cnt'] = len(same)
    rec['same_max'] = max(same) if same else None
    rec['same_med'] = sorted(same)[len(same)//2] if same else None
    rec['pass_turnover'] = rec['turnover_pct'] >= 4.0
    rec['pass_price'] = bool(rec['same_max'] and rec['same_max'] > appr)
    rec['PASS'] = rec['pass_turnover'] and rec['pass_price']
    print(f"{kname[:16]:18s} 거래 {len(m):3d}건 ({rec['turnover_pct']:.1f}%) | 동평형 최고 {rec['same_max']} vs 감정 {appr}"
          f" | {'✅통과' if rec['PASS'] else '탈락'} | 역 {rec.get('subway','?')} {rec.get('subway_time','')}")
    results.append(rec)

json.dump(results, open('priority_eval.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('\n저장: priority_eval.json — 이름매칭 0건이면 RTMS 표기 변형을 의심하고 법정동 전체 aptNm을 덤프해 대조하라.')
