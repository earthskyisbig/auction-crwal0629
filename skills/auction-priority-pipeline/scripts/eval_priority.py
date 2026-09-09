# -*- coding: utf-8 -*-
"""후보 물건을 사용자 우선순위 기준으로 평가:
   1) 최근 12개월 실거래량/세대수 >= 4%  2) 동일평형(±2㎡) 실거래 최고가 > 감정가
   3) 역세권·학세권 (K-apt 상세정보)
결과 → priority_eval.json

사용법 (프로젝트 루트에서, .env 필요):
  python3 eval_priority.py --items items.json [-o priority_eval.json]
  items.json: 아래 ITEM_FIELDS 순서의 리스트(배열) 또는 같은 키를 가진 객체들의 배열.
  (--items 를 생략하면 이 파일의 ITEMS 상수를 쓴다 — 예전 방식과 호환)

PublicDataReader 는 segfault 나므로 쓰지 말 것 — RTMS XML 직접 호출.
data.go.kr 초당 제한: 병렬 금지, 호출당 sleep 0.35s + 에러XML 백오프."""
import argparse, json, os, re, sys, time, warnings, xml.etree.ElementTree as ET
from datetime import date
warnings.filterwarnings('ignore')
import requests, urllib3
urllib3.disable_warnings()
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(usecwd=True))
KEY = os.getenv('PUBLIC_DATA_SERVICE_KEY')
LIST = 'https://apis.data.go.kr/1613000/AptListService4/getSigunguAptList4'
DTL  = 'https://apis.data.go.kr/1613000/AptBasisInfoServiceV5/getAphusDtlInfoV5'
RTMS = 'https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev'

TURNOVER_MIN_PCT = 4.0     # 연간 실거래량 / 세대수
AREA_TOL = 2.0             # 동일평형 판정 허용 오차(㎡)

ITEM_FIELDS = ('case', 'name', 'tkey', 'sggs', 'dong', 'area',
               'appr', 'low', 'flbd', 'day', 'built', 'households')
# ▼▼ 후보 물건 입력(구방식): (사건번호, K-apt 정확명, RTMS 이름키워드, 시군구코드들, 법정동, 전용㎡,
#                   감정가(만원), 최저가(만원), 유찰, 매각기일, 준공, 세대수)
ITEMS = [
    # ('수원 2025타경58196', '수원하늘채더퍼스트2단지', '하늘채더퍼스트', ['41113'], '곡반정동',
    #  84.96, 66000, 46200, 1, '8.24', '2022.06', 1833),
]


def month_list(n=12, end=None):
    """end 가 속한 달을 마지막으로 하는 최근 n개월 YYYYMM. end 생략 시 '지난달'까지
    (이번 달은 신고 지연 30일로 거의 비어 있어 회전율을 과소평가한다)."""
    if end is None:
        t = date.today()
        end = date(t.year, t.month, 1) - __import__('datetime').timedelta(days=1)
    y, m = end.year, end.month
    out = []
    for _ in range(n):
        out.append(f'{y}{m:02d}')
        m -= 1
        if m == 0: y, m = y - 1, 12
    return list(reversed(out))


def norm(s):
    return re.sub(r'[\s,()\-·.]+', '', str(s or '')).replace('이편한세상', 'e편한세상').lower()


def to_item(x):
    """튜플/리스트/딕셔너리 입력을 표준 dict 로."""
    if isinstance(x, dict):
        missing = [k for k in ITEM_FIELDS if k not in x]
        if missing:
            raise ValueError(f'items 항목에 필드 누락: {missing}')
        return {k: x[k] for k in ITEM_FIELDS}
    if len(x) != len(ITEM_FIELDS):
        raise ValueError(f'items 항목은 {len(ITEM_FIELDS)}개 값이어야 합니다: {ITEM_FIELDS}')
    return dict(zip(ITEM_FIELDS, x))


def summarize_trades(allrows, tkey, dong, area, appr, households,
                     turnover_min=TURNOVER_MIN_PCT, area_tol=AREA_TOL):
    """RTMS 행 목록 → 회전율·동평형 최고/중앙값·통과 여부 (순수 함수).
    allrows: RTMS item dict 목록(aptNm, umdNm, excluUseAr, dealAmount[만원], cdealType)."""
    nk = norm(tkey)
    m = [t for t in allrows if nk in norm(t.get('aptNm'))]
    dong_m = [t for t in m if t.get('umdNm', '') == dong]
    if dong_m:
        m = dong_m
    m = [t for t in m if t.get('cdealType') != 'O']          # 해제거래 제외
    same = []
    for t in m:
        try:
            ar = float(t.get('excluUseAr') or 0)
            amt = int(str(t.get('dealAmount') or '').replace(',', '').strip())
        except ValueError:
            continue
        if abs(ar - area) <= area_tol:
            same.append(amt)
    same.sort()
    rec = {
        'trades_12m': len(m),
        'turnover_pct': round(len(m) / households * 100, 2) if households else None,
        'same_cnt': len(same),
        'same_max': same[-1] if same else None,
        'same_med': same[len(same) // 2] if same else None,
    }
    rec['pass_turnover'] = rec['turnover_pct'] is not None and rec['turnover_pct'] >= turnover_min
    rec['pass_price'] = bool(rec['same_max'] and appr and rec['same_max'] > appr)
    rec['PASS'] = rec['pass_turnover'] and rec['pass_price']
    return rec


# ── 네트워크 ───────────────────────────────────────────────────────
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
        if not isinstance(its, list): its = [its]
        if not its: break
        out += its
        if len(its) < 500: break
        page += 1
    APT[code] = out
    return out


TR = {}
MISSING = {}   # code → 재시도 초과로 건너뛴 월 목록 (회전율 신뢰도 표시용)
def trades(code, months):
    if code in TR: return TR[code]
    rows = []
    MISSING[code] = []
    for ym in months:
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
                print(f'  [RTMS] {code} {ym} p{page}: 6회 재시도 실패 — 이 달은 건너뜀')
                MISSING[code].append(ym)
                break
            for it in root.findall('.//item'):
                rows.append({c.tag: (c.text or '').strip() for c in it})
            total = int(root.findtext('.//totalCount') or 0)
            if page * 1000 >= total: break
            page += 1
    TR[code] = rows
    print(f'  [RTMS] {code}: {len(months)}개월 {len(rows)}건')
    return rows


def kapt_profile(kname, sggs):
    """K-apt 상세(역·통학시설). 매칭 실패 시 빈 dict."""
    for c in sggs:
        for a in apt_list(c):
            if norm(a.get('kaptName')) == norm(kname):
                d = jget(DTL, {'kaptCode': a['kaptCode']}).get('item') or {}
                return {'subway': f"{d.get('subwayLine') or ''} {d.get('subwayStation') or ''}".strip(),
                        'subway_time': d.get('kaptdWtimesub'), 'edu': d.get('educationFacility')}
    return {}


def evaluate(items, months):
    results = []
    for it in items:
        rec = {**it}
        rec.update(kapt_profile(it['name'], it['sggs']))
        allrows = []
        for c in it['sggs']:
            allrows += trades(c, months)
        rec.update(summarize_trades(allrows, it['tkey'], it['dong'], it['area'], it['appr'], it['households']))
        rec['missing_months'] = sorted({m for c in it['sggs'] for m in MISSING.get(c, [])})
        rec['reliable'] = not rec['missing_months'] and rec['turnover_pct'] is not None
        tp = rec['turnover_pct']
        print(f"{it['name'][:16]:18s} 거래 {rec['trades_12m']:3d}건 ({tp if tp is not None else '?'}%) | "
              f"동평형 최고 {rec['same_max']} vs 감정 {it['appr']} | {'✅통과' if rec['PASS'] else '탈락'}{'' if rec['reliable'] else ' (⚠️수집 누락월 있음)'} | "
              f"역 {rec.get('subway') or '?'} {rec.get('subway_time') or ''}")
        results.append(rec)
    return results


def main(argv=None):
    ap = argparse.ArgumentParser(description='경매 후보 물건 실거래 관문 평가')
    ap.add_argument('--items', help='후보 물건 JSON (배열). 생략 시 파일 내 ITEMS 사용')
    ap.add_argument('-o', '--out', default='priority_eval.json')
    ap.add_argument('--months', type=int, default=12, help='조회 개월 수 (기본 12)')
    a = ap.parse_args(argv)
    if not KEY:
        sys.exit('.env 의 PUBLIC_DATA_SERVICE_KEY 가 없습니다 (프로젝트 루트에서 실행)')
    raw = json.load(open(a.items, encoding='utf-8')) if a.items else ITEMS
    items = [to_item(x) for x in raw]
    if not items:
        sys.exit('평가할 후보가 없습니다 — --items 파일을 주거나 ITEMS 를 채우세요')
    results = evaluate(items, month_list(a.months))
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    print(f'\n저장: {a.out} — 이름매칭 0건이면 RTMS 표기 변형을 의심하고 법정동 전체 aptNm을 덤프해 대조하라.')


if __name__ == '__main__':
    main()
