# -*- coding: utf-8 -*-
"""경매 CSV → 유찰1~2회·59~84㎡ 필터 → 단지 세대수·준공년도 보강 (국토부 공동주택 API)
사용: python3 enrich_complex.py <입력.csv> <출력.csv> [--flbd 1,2] [--area 59-84.99]
입력 CSV 컬럼: 사건번호,물건소재지,전용면적,감정가,최저가,저감율,유찰횟수,매각기일 (court-auction-scraper 출력)
.env 의 PUBLIC_DATA_SERVICE_KEY 필요 (프로젝트 루트에서 실행)"""
import csv, json, os, re, sys, warnings
warnings.filterwarnings('ignore')
import requests, urllib3
urllib3.disable_warnings()
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(usecwd=True))
KEY = os.getenv('PUBLIC_DATA_SERVICE_KEY')

LIST = 'https://apis.data.go.kr/1613000/AptListService3/getSigunguAptList3'
INFO = 'https://apis.data.go.kr/1613000/AptBasisInfoServiceV4/getAphusBassInfoV4'

# 경기도 시군구코드 (화성 2026 분구 반영: 41591 만세 / 41593 효행 / 41595 병점 / 41597 동탄)
SGG_CODES = {
    '수원시 장안구': '41111', '수원시 권선구': '41113', '수원시 팔달구': '41115', '수원시 영통구': '41117',
    '성남시 수정구': '41131', '성남시 중원구': '41133', '성남시 분당구': '41135',
    '의정부시': '41150', '안양시 만안구': '41171', '안양시 동안구': '41173',
    '부천시': '41190', '부천시 원미구': '41192', '부천시 소사구': '41194', '부천시 오정구': '41196',
    '광명시': '41210', '평택시': '41220', '동두천시': '41250',
    '안산시 상록구': '41271', '안산시 단원구': '41273',
    '고양시 덕양구': '41281', '고양시 일산동구': '41285', '고양시 일산서구': '41287',
    '과천시': '41290', '구리시': '41310', '남양주시': '41360', '오산시': '41370',
    '시흥시': '41390', '군포시': '41410', '의왕시': '41430', '하남시': '41450',
    '용인시 처인구': '41461', '용인시 기흥구': '41463', '용인시 수지구': '41465',
    '파주시': '41480', '이천시': '41500', '안성시': '41550', '김포시': '41570',
    '화성시': '41591', '화성만세구': '41591', '화성효행구': '41593', '화성병점구': '41595', '화성동탄구': '41597',
    '광주시': '41610', '양주시': '41630', '포천시': '41650',
    '여주시': '41670', '연천군': '41800', '가평군': '41820', '양평군': '41830',
}
HWASEONG = ['41591', '41593', '41595', '41597']

def norm(s):
    s = re.sub(r'\s+', '', s or '')
    s = s.replace('이편한세상', 'e편한세상')
    s = re.sub(r'(아파트|APT|apt)$', '', s)
    return s.lower()

def parse_row(row):
    addr = row['물건소재지']
    m = re.match(r'경기도\s+(\S+[시군])\s*(\S+구)?', addr)   # 군(양평·가평·연천) 포함
    if not m: return None
    sgg = m.group(1) + ((' ' + m.group(2)) if m.group(2) else '')
    name, dong = None, None
    pm = re.search(r'\(([^)]*)\)', addr)
    if pm and ',' in pm.group(1):
        dong = pm.group(1).split(',')[0].strip()
        name = pm.group(1).split(',')[-1].strip()
    if not dong:
        dm = re.search(r'\s(\S+[동리읍면])\s+\d', addr)
        if dm: dong = dm.group(1)
    name_from_token = False
    if not name:
        for tok in addr.split():
            if re.search(r'(아파트|파크|캐슬|자이|푸르지오|e?편한세상|힐스테이트|아이파크|더샵|센트럴|위브|해링턴|베르디움|리슈빌|스위첸|포레나|데시앙|엘크루|써밋)', tok) and tok[-1] != '동':
                name = tok; name_from_token = True; break
    try:
        area = float(re.sub(r'[^\d.]', '', row['전용면적']))
    except Exception:
        area = None
    return {'sgg': sgg, 'name': name, 'dong': dong, 'area': area, 'name_from_token': name_from_token}

def sgg_code(sgg_name):
    if sgg_name.startswith('화성'): return HWASEONG
    if sgg_name in SGG_CODES: return [SGG_CODES[sgg_name]]
    base = sgg_name.split()[0]
    return [v for k, v in SGG_CODES.items() if k.split()[0] == base]

def jget(url, params, tries=5):
    """data.go.kr JSON 호출 — 초당 제한(429)·에러 XML(OpenAPI_ServiceResponse)·타임아웃을 백오프 재시도.
    실패가 계속되면 None (호출부는 빈 결과로 처리하고 다음 행으로 진행)."""
    import time
    for a in range(tries):
        time.sleep(0.3)
        try:
            r = requests.get(url, params={**params, 'serviceKey': KEY, '_type': 'json'}, verify=False, timeout=30)
            body = (r.json().get('response') or {}).get('body')
            if body is not None:
                return body
        except (requests.RequestException, ValueError):
            pass
        time.sleep(1.5 + a * 1.5)
    return None


APT_CACHE = {}
def apt_list(code):
    if code in APT_CACHE: return APT_CACHE[code]
    out, page = [], 1
    while page <= 20:
        its = (jget(LIST, {'sigunguCode': code, 'pageNo': page, 'numOfRows': 500}) or {}).get('items') or []
        if isinstance(its, dict): its = its.get('item') or []
        if not isinstance(its, list): its = [its]
        if not its: break
        out += its
        if len(its) < 500: break
        page += 1
    APT_CACHE[code] = out
    return out

BASIS_CACHE = {}
def basis(kapt):
    if kapt in BASIS_CACHE: return BASIS_CACHE[kapt]
    it = (jget(INFO, {'kaptCode': kapt}) or {}).get('item') or {}
    BASIS_CACHE[kapt] = it
    return it

def match_kapt(codes, name, dong=None, strict_dong=False):
    """K-apt 단지 매칭. strict_dong=True(브랜드 토큰만으로 추정한 이름)면 같은 법정동 안에서만 찾는다 —
    '더샵'·'자이' 같은 토큰이 시군구 전체의 다른 단지에 붙는 오매칭 방지."""
    n = norm(name)
    if not n: return None
    cands = []
    for code in codes:
        cands += apt_list(code)
    dong_pool = [c for c in cands if str(c.get('as3', '')).strip() == dong] if dong else []
    if strict_dong:
        pools = [dong_pool] if dong_pool else []
    else:
        pools = ([dong_pool] if dong_pool else []) + [cands]
    for pool in pools:
        exact = [c for c in pool if norm(c.get('kaptName')) == n]
        if exact: return exact[0]
        contain = [c for c in pool if n in norm(c.get('kaptName')) or norm(c.get('kaptName')) in n]
        if contain:
            return max(contain, key=lambda c: len(norm(c.get('kaptName'))))
    return None

def passes_basic_filter(row, flbd=(1, 2), area_range=(59.0, 84.99)):
    """기본 필터(유찰횟수·전용면적) — 순수 함수. 통과 시 parse_row 결과, 아니면 None."""
    # 유찰추정(저감율 역산, 스크래퍼 2026-09 컬럼)이 있으면 우선 — yuchalCnt 필드는 신경매/재매각 시 부정확
    try:
        yc = int(str(row.get('유찰추정') or row.get('유찰횟수', '')).strip())
    except ValueError:
        return None
    p = parse_row(row)
    if not p or p['area'] is None:
        return None
    if yc not in flbd:
        return None
    if not (area_range[0] <= p['area'] <= area_range[1]):
        return None
    p['yc'] = yc
    return p


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description='경매 CSV 기본 필터 + K-apt 단지 보강')
    ap.add_argument('src', help='court-auction-scraper 출력 CSV')
    ap.add_argument('out', help='보강 결과 CSV')
    ap.add_argument('--flbd', default='1,2', help='허용 유찰횟수 (콤마 구분, 기본 1,2)')
    ap.add_argument('--area', default='59-84.99', help='전용면적 범위 ㎡ (기본 59-84.99)')
    a = ap.parse_args(argv)
    if not KEY:
        sys.exit('.env 의 PUBLIC_DATA_SERVICE_KEY 가 없습니다 (프로젝트 루트에서 실행)')
    flbd = tuple(int(x) for x in a.flbd.split(',') if x.strip())
    lo, hi = (float(x) for x in a.area.split('-'))

    with open(a.src, encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    print(f'원본 {len(rows)}건')
    results = []
    for row in rows:
        p = passes_basic_filter(row, flbd, (lo, hi))
        if not p:
            continue
        yc = p['yc']
        rec = dict(row)
        rec.update({'시군구': p['sgg'], '단지명추정': p['name'] or '', '세대수': '', '준공': '', 'kapt단지명': ''})
        if p['name']:
            codes = sgg_code(p['sgg'])
            if codes:
                try:
                    hit = match_kapt(codes, p['name'], p.get('dong'), strict_dong=p.get('name_from_token', False))
                except (requests.RequestException, ValueError) as e:
                    print(f'  [API 오류] {p["name"]}: {e}')
                    hit = None
                if hit:
                    b = basis(hit['kaptCode'])
                    hh = b.get('kaptdaCnt') or b.get('hoCnt') or ''
                    rec['세대수'] = hh
                    rec['준공'] = (b.get('kaptUsedate') or '')[:6]
                    rec['kapt단지명'] = b.get('kaptName') or hit.get('kaptName')
        results.append(rec)
        print(f"  {rec['시군구']} | {rec['단지명추정'] or '?'} → {rec['kapt단지명'] or '미매칭'} | {rec['세대수']}세대 | {rec['준공']} | {row['전용면적']} | 유찰{yc}")

    if results:
        with open(a.out, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
            w.writeheader(); w.writerows(results)
    print(f'\n필터 통과 {len(results)}건 → {a.out}')
    print('※ 미매칭 단지는 이름 변형(띄어쓰기·차수·브랜드 표기)이 원인일 수 있음 — difflib 유사도 재매칭 또는 건축년도 대조로 보완하라.')


if __name__ == '__main__':
    main()
