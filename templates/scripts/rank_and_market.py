# -*- coding: utf-8 -*-
"""비규제 경매 후보 랭킹 + 국토부 실거래 시세 대조.

CLAUDE.md 규칙 준수: PublicDataReader 미사용(직접 requests), 병렬 금지, 호출당 sleep 0.3s.
K-apt 목록은 2026-09 기준 AptListService4(getSidoAptList4)가 현행(V3 폐기).
"""
import os, csv, re, json, time, statistics, sys
import requests
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))
KEY = os.getenv('PUBLIC_DATA_SERVICE_KEY')
LIST = 'https://apis.data.go.kr/1613000/AptListService4/getSidoAptList4'
RTMS = 'https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev'
BASE = os.path.dirname(os.path.abspath(__file__))
SLEEP = 0.32

def norm(s):
    return re.sub(r'(아파트|단지|차)|\s|[·\-()]', '', str(s or ''))

# ── 1. 경기 단지 인덱스(법정동코드 포함) ──────────────────────────────
def build_index(cache):
    if os.path.exists(cache):
        return json.load(open(cache, encoding='utf-8'))
    out, page = [], 1
    while True:
        r = requests.get(LIST, params={'serviceKey': KEY, 'sidoCode': '41',
                                       'pageNo': page, 'numOfRows': 500, '_type': 'json'}, timeout=25)
        its = (r.json().get('response', {}).get('body', {}) or {}).get('items') or []
        if isinstance(its, dict):
            its = its.get('item', [])
        if not its:
            break
        for it in its:
            out.append({'code': it.get('kaptCode'), 'name': it.get('kaptName'),
                        'as2': it.get('as2'), 'bjd': it.get('bjdCode')})
        if len(its) < 500:
            break
        page += 1
        time.sleep(SLEEP)
    json.dump(out, open(cache, 'w', encoding='utf-8'), ensure_ascii=False)
    return out

# ── 2. 실거래 조회 (최근 N개월, 동일 단지·평형) ────────────────────────
def recent_yms(n=12, end_year=2026, end_month=8):
    yms, y, m = [], end_year, end_month
    for _ in range(n):
        yms.append(f'{y}{m:02d}')
        m -= 1
        if m < 1:
            y, m = y - 1, 12
    return yms[::-1]

def fetch_trades(lawd, complex_name, area, tol=3.0, months=12):
    core = norm(complex_name)
    if not (lawd and core and area):
        return []
    rows = []
    for ym in recent_yms(months):
        try:
            r = requests.get(RTMS, params={'serviceKey': KEY, 'LAWD_CD': lawd,
                                           'DEAL_YMD': ym, 'numOfRows': 800, '_type': 'json'}, timeout=25)
            body = (r.json().get('response', {}).get('body', {}) or {})
            its = (body.get('items') or {})
            its = its.get('item', []) if isinstance(its, dict) else its
            if isinstance(its, dict):
                its = [its]
        except Exception:
            its = []
        for it in its or []:
            nm = norm(it.get('aptNm'))
            if not nm or not (core in nm or nm in core):
                continue
            try:
                a = float(it.get('excluUseAr'))
                amt = int(re.sub(r'[^\d]', '', str(it.get('dealAmount'))))  # 만원
            except (TypeError, ValueError):
                continue
            if abs(a - area) > tol:
                continue
            if str(it.get('cdealType', '')).strip() == 'O':      # 해제거래 제외
                continue
            rows.append({'ym': ym, 'amt': amt, 'area': a,
                         'floor': it.get('floor'), 'umd': it.get('umdNm')})
        time.sleep(SLEEP)
    return rows

def load_rows():
    """enriched final(세대수 有) + review(無) 병합."""
    out = {}
    for path, enriched in ((os.path.join(BASE, 'data/gg_nonreg_0909_final.csv'), True),
                           (os.path.join(BASE, 'data/gg_nonreg_0909_review.csv'), False)):
        if not os.path.exists(path):
            continue
        for r in csv.DictReader(open(path, encoding='utf-8-sig')):
            key = (r['사건번호'], r['물건소재지'])
            if key in out:
                continue
            def num(v):
                try:
                    return int(v)
                except (TypeError, ValueError):
                    return None
            r['_세대수n'] = num(r.get('_세대수'))
            r['_준공n'] = num(r.get('_준공연도'))
            r['_enriched'] = enriched
            out[key] = r
    return list(out.values())

def won(v):
    return int(re.sub(r'[^\d]', '', v or '0'))

def area_of(r):
    m = re.search(r'([\d.]+)', r.get('전용면적') or '')
    return float(m.group(1)) if m else None

def flbd(rate):
    return 0 if rate >= 95 else 1 if rate >= 60 else 2 if rate >= 42 else 3

def score(r):
    """단기매도 관점 스크리닝 점수. 환금성(세대수) 최우선 — apt-location-kit 환금성 원칙."""
    s = 0.0
    hh = r['_세대수n'] or 0
    s += min(hh / 1000, 3.0) * 25                       # 세대수(환금성 프록시) 최대 75
    yr = r['_준공n'] or 0
    if yr:
        age = 2026 - yr
        s += max(0, 30 - age) * 1.2                     # 연식 최대 36
    rate = int(re.sub(r'[^\d]', '', r['저감율'] or '100'))
    s += (100 - rate) * 0.6                             # 할인폭 최대 ~40
    a = area_of(r) or 0
    if 50 <= a <= 90:
        s += 12                                          # 국민평형 선호
    return round(s, 1)

def main():
    idx = build_index(os.path.join(BASE, 'gg_index_bjd.json'))
    by_code = {}
    for it in idx:
        by_code.setdefault(norm(it['name']), []).append(it)

    rows = load_rows()
    for r in rows:
        r['_점수'] = score(r)
        r['_면적'] = area_of(r)
        r['_최저가'] = won(r['최저가'])
        r['_감정가'] = won(r['감정가'])
        r['_유찰'] = flbd(int(re.sub(r'[^\d]', '', r['저감율'] or '100')))
    rows.sort(key=lambda x: -x['_점수'])

    top = [r for r in rows if r['_세대수n']][:14]
    print(f'후보 {len(rows)}건 → 시세조회 대상 {len(top)}건', flush=True)

    for i, r in enumerate(top, 1):
        cands = by_code.get(norm(r.get('_매칭단지')), [])
        lawd = cands[0]['bjd'][:5] if cands and cands[0].get('bjd') else None
        tr = fetch_trades(lawd, r.get('_매칭단지'), r['_면적']) if lawd else []
        prices = [t['amt'] for t in tr]
        if prices:
            prices_sorted = sorted(prices)
            cut = max(1, len(prices) // 100)
            core_p = prices_sorted[cut:-cut] if len(prices_sorted) > 4 else prices_sorted
            r['_시세중앙'] = int(statistics.median(core_p)) * 10000
            r['_시세표본'] = len(prices)
            r['_시세최저'] = min(core_p) * 10000
            r['_시세최고'] = max(core_p) * 10000
            r['_할인율'] = round(r['_최저가'] / r['_시세중앙'] * 100, 1)
            r['_최근거래'] = [[t['ym'], f"{t['area']:g}㎡", f"{t['floor']}층", t['amt']]
                            for t in sorted(tr, key=lambda x: x['ym'], reverse=True)[:5]]
            r['_월별'] = [[ym, sum(1 for t in tr if t['ym'] == ym),
                          int(statistics.mean([t['amt'] for t in tr if t['ym'] == ym]))
                          if any(t['ym'] == ym for t in tr) else 0] for ym in recent_yms(12)]
        else:
            r['_시세중앙'] = 0; r['_시세표본'] = 0; r['_할인율'] = None
            r['_최근거래'] = []; r['_월별'] = []
        print(f"  [{i:02d}] {r.get('_매칭단지')} {r['_면적']}㎡ 세대{r['_세대수n']} "
              f"준공{r['_준공n']} 최저{r['_최저가']//10000:,}만 시세{r['_시세중앙']//10000:,}만 "
              f"({r['_시세표본']}건) 할인{r['_할인율']}%", flush=True)

    json.dump({'all': rows, 'top': top}, open(os.path.join(BASE, 'ranked_0909.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('saved ranked_0909.json')

if __name__ == '__main__':
    main()
