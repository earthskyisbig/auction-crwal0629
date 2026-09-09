# -*- coding: utf-8 -*-
"""경매 목록 CSV에 K-apt 공동주택 기본정보(세대수·준공연도)를 붙여 조건 필터.

오늘의 핵심 교훈 (SKILL.md 참조):
  - 시군구별 목록(getSigunguAptList3)은 코드가 취약: 수원 41110(상위) → 0건, 부천은 구 폐지·복수코드.
    → **시도 전역 목록(getSidoAptList3, sidoCode)** 로 한 번에 받아 이름 매칭하면 코드 문제가 사라진다.
  - 단지명 매칭 난제: 다어절 이름("이안 평택안중역"), "N블록" 접두, 괄호 "(동명,단지명)".
    → 주소요소를 걸러내고 뒤쪽 어절을 단지명으로, as2(시군구)로 동명이 단지 구분.
  - K-apt 두 서비스(기본정보 V4, 단지목록) 각각 data.go.kr 활용신청 필요(미신청 403).

입력 CSV 컬럼: 사건번호,물건소재지,전용면적,감정가,최저가,저감율,유찰횟수,매각기일
출력: <base>_final.csv(조건충족) + <base>_review.csv(미달·매칭실패, 사유)

사용:
  python enrich_apt.py in.csv --sido 경기 --min-households 500 --min-built-year 2015
  python enrich_apt.py in.csv --sido 서울 --min-households 300 --min-built-year 2010 --max-built-year 2020
"""
import os, re, csv, sys, json, time, argparse, warnings
warnings.filterwarnings('ignore')
import requests, urllib3
urllib3.disable_warnings()
from dotenv import load_dotenv, find_dotenv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sido_codes import resolve

# 2026-09-09: 구버전(List3 / BasisInfoV4)이 data.go.kr에서 폐기되어 NO_OPENAPI_SERVICE_ERROR(400) 반환.
# 목록은 V4, 기본정보는 V5가 현행. 버전은 예고 없이 올라가므로 400이면 인접 버전을 먼저 의심할 것.
LIST = 'https://apis.data.go.kr/1613000/AptListService4/getSidoAptList4'
INFO = 'https://apis.data.go.kr/1613000/AptBasisInfoServiceV5/getAphusBassInfoV5'


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument('csv')
    ap.add_argument('--sido', required=True, help='시도명 (예: 경기)')
    ap.add_argument('--min-households', type=int, default=0, help='세대수 하한')
    ap.add_argument('--min-built-year', type=int, default=0, help='준공연도 하한(포함)')
    ap.add_argument('--max-built-year', type=int, default=9999, help='준공연도 상한(포함)')
    ap.add_argument('--area-min', type=float, default=None, help='(재확인용) 전용면적 하한')
    ap.add_argument('--area-max', type=float, default=None)
    ap.add_argument('--flbd-min', type=int, default=None, help='(재확인용) 유찰 하한(저감율 역산)')
    ap.add_argument('--flbd-max', type=int, default=None)
    ap.add_argument('--price-min', type=int, default=None); ap.add_argument('--price-max', type=int, default=None)
    ap.add_argument('--cache', default=None, help='시도 단지 인덱스 캐시 JSON 경로')
    return ap.parse_args()


load_dotenv(find_dotenv(usecwd=True))
KEY = os.getenv('PUBLIC_DATA_SERVICE_KEY')

def to_won(s): d = re.sub(r'[^\d]', '', s or ''); return int(d) if d else 0
def to_area(s): m = re.search(r'([\d.]+)', s or ''); return float(m.group(1)) if m else None
def yuchal_from_rate(rate):
    """저감율(%) → 실제 유찰횟수 역산. yuchalCnt 필드는 부정확하므로 이 방식 사용."""
    m = re.search(r'([\d.]+)', rate or '')
    if not m: return None
    r = float(m.group(1))
    tbl = [(100,0),(80,1),(70,1),(64,2),(49,2),(51,3),(34,3),(41,4),(24,4),(33,5),(17,5)]
    return min(tbl, key=lambda t: abs(t[0]-r))[1]

SGG_RE = re.compile(r'(?:특별시|광역시|특별자치시|도|특별자치도)\s+([가-힣]+시\s+[가-힣]+구|[가-힣]+시|[가-힣]+군|[가-힣]+구)')
def parse_sigungu(a):
    m = SGG_RE.search(a or ''); return m.group(1).strip() if m else None

ADDR_TOK = re.compile(r'[가-힣]+도|[가-힣]+시|[가-힣]+구|[가-힣]+군|[가-힣]+읍|[가-힣]+면|[가-힣]+동|'
                      r'[가-힣]+리|[가-힣]+로\d*|[가-힣]+길\d*|\d+(?:-\d+)?|\d+번지|산\d+|'
                      r'[가-힣]*\d*지구\d*블?록?|\d+블록|특별시|광역시|특별자치시|특별자치도')
def parse_name(addr):
    if not addr: return None
    for grp in re.findall(r'\(([^)]*)\)', addr):
        if ',' in grp:
            c = grp.split(',')[-1].strip(); c = re.sub(r'\d+동.*$', '', c).strip()
            if c and not c[0].isdigit(): return c
    m = re.search(r'(.+?)\s*(?:제?\d+동|\d+층|\d+호|\s외\s|\[)', addr)
    head = re.sub(r'\([^)]*\)', ' ', (m.group(1) if m else addr))
    keep = []
    for t in head.split():
        if ADDR_TOK.fullmatch(t): keep = []
        else: keep.append(t)
    return (' '.join(keep).strip()) or None

def norm(s):
    s = re.sub(r'[\s\(\)\[\].·\-,]', '', s or '')
    for w in ['아파트', '단지', '제', '차']: s = s.replace(w, '')
    return s
def norm_sgg(s): return re.sub(r'[\s시]', '', s or '')

def build_index(sido_code, cache):
    if cache and os.path.exists(cache):
        return json.load(open(cache, encoding='utf-8'))
    out, page = [], 1
    while page <= 30:
        r = requests.get(LIST, params={'serviceKey': KEY, 'sidoCode': sido_code, 'pageNo': page,
                                       'numOfRows': 500, '_type': 'json'}, verify=False, timeout=30)
        if r.status_code == 403:
            sys.exit('403 — "공동주택 단지 목록제공 서비스(AptListService3)" 활용신청 필요. references/kapt-api.md')
        body = r.json().get('response', {}).get('body', {}) or {}
        its = body.get('items', {}); its = its.get('item') if isinstance(its, dict) else its
        if not its: break
        its = its if isinstance(its, list) else [its]
        out.extend([{'code': it.get('kaptCode'), 'name': it.get('kaptName'), 'as2': it.get('as2', '')} for it in its])
        if len(its) < 500: break
        page += 1
    if cache: json.dump(out, open(cache, 'w', encoding='utf-8'), ensure_ascii=False)
    return out

_info = {}
def kinfo(code):
    if code in _info: return _info[code]
    try:
        r = requests.get(INFO, params={'serviceKey': KEY, 'kaptCode': code, '_type': 'json'}, verify=False, timeout=20)
        if r.status_code == 403:
            sys.exit('403 — "공동주택 기본 정보제공 서비스(AptBasisInfoServiceV5)" 활용신청 필요.')
        it = (r.json().get('response', {}).get('body', {}) or {}).get('item') or {}
    except Exception:
        it = {}
    _info[code] = it; return it

def match(index, sgg, name):
    if not name: return None
    n = norm(name)
    if len(n) < 2: return None
    sg = norm_sgg(sgg) if sgg else ''
    cands = []
    for it in index:
        kn = norm(it['name'])
        if not kn: continue
        sc = 3 if kn == n else 2 if (n in kn or kn in n) else 1 if (len(n) >= 4 and (n[:5] in kn or kn[:5] in n)) else 0
        if sc:
            if sg and sg[:2] and sg[:2] in norm_sgg(it['as2']): sc += 2
            cands.append((sc, len(kn), it))
    if not cands: return None
    cands.sort(key=lambda t: (-t[0], abs(t[1]-len(n))))
    return cands[0][2]


def main():
    args = parse_args()
    if not KEY: sys.exit('.env 의 PUBLIC_DATA_SERVICE_KEY 필요')
    r = resolve(args.sido)
    if not r: sys.exit(f'시도 "{args.sido}" 인식 실패')
    _, sido_code, _ = r
    rows = list(csv.DictReader(open(args.csv, encoding='utf-8-sig')))
    print(f'▶ 원본 {len(rows)}건')

    # 선택적 재확인 필터 (수집 때 서버필터를 안 걸었을 경우 대비)
    st = []
    for row in rows:
        if args.price_min is not None or args.price_max is not None:
            p = to_won(row.get('최저가'))
            if args.price_min is not None and p < args.price_min: continue
            if args.price_max is not None and p > args.price_max: continue
        if args.area_min is not None or args.area_max is not None:
            a = to_area(row.get('전용면적'))
            if a is None: continue
            if args.area_min is not None and a < args.area_min: continue
            if args.area_max is not None and a > args.area_max: continue
        if args.flbd_min is not None or args.flbd_max is not None:
            y = yuchal_from_rate(row.get('저감율'))
            if y is None: continue
            if args.flbd_min is not None and y < args.flbd_min: continue
            if args.flbd_max is not None and y > args.flbd_max: continue
            row['_유찰역산'] = y
        st.append(row)
    print(f'▶ 재확인 필터 후 {len(st)}건')

    cache = args.cache or (os.path.splitext(args.csv)[0] + f'_apt_index_{sido_code}.json')
    index = build_index(sido_code, cache)
    print(f'▶ 시도({sido_code}) 단지 인덱스 {len(index)}개')

    final, review = [], []
    for i, row in enumerate(st, 1):
        try:
            addr = row['물건소재지']; sgg = parse_sigungu(addr); name = parse_name(addr)
            row['_시군구'] = sgg or ''; row['_단지추정'] = name or ''
            hit = match(index, sgg, name)
            if not hit:
                row['_매칭단지'] = ''; row['_사유'] = '단지매칭실패'; review.append(row)
                print(f'  [{i}] 실패 {sgg}/{name}', flush=True); continue
            info = kinfo(hit['code'])
            h = info.get('kaptdaCnt'); u = info.get('kaptUsedate')
            by = int(str(u)[:4]) if u and str(u)[:4].isdigit() else None
            try: h = int(h)
            except: h = None
            row['_매칭단지'] = hit['name']; row['_세대수'] = h if h is not None else ''
            row['_준공연도'] = by if by else ''
            print(f'  [{i}] {name} -> {hit["name"]}({hit["as2"]}) 세대 {h} 준공 {by}', flush=True)
            if h is None or by is None:
                row['_사유'] = '세대수/준공 조회불가'; review.append(row); continue
            if h >= args.min_households and args.min_built_year <= by <= args.max_built_year:
                final.append(row)
            else:
                row['_사유'] = f'조건미달(세대 {h}, 준공 {by})'; review.append(row)
        except Exception as e:
            row['_사유'] = f'오류:{e}'; review.append(row); print(f'  [{i}] 오류 {e}', flush=True)
        time.sleep(0.03)

    base = os.path.splitext(args.csv)[0]
    cols = ['사건번호','물건소재지','전용면적','감정가','최저가','저감율','_시군구','_매칭단지','_세대수','_준공연도','매각기일']
    def wr(path, data, extra=None):
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.DictWriter(f, fieldnames=cols+(extra or []), extrasaction='ignore'); w.writeheader(); w.writerows(data)
    final.sort(key=lambda r: -(int(r['_세대수']) if str(r['_세대수']).isdigit() else 0))
    wr(base+'_final.csv', final); wr(base+'_review.csv', review, ['_단지추정','_사유'])
    print(f'\n✅ 최종 {len(final)}건 → {base}_final.csv')
    print(f'⚠️  검토 {len(review)}건 → {base}_review.csv')


if __name__ == '__main__':
    main()
