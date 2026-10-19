# -*- coding: utf-8 -*-
"""빌라(연립다세대) 블록 시세 — 동일 지번 거래·임대 + 블록 반기별 ㎡당 중앙값 + 블록 전세.

재개발 후보지 안 빌라는 '동일 단지'가 없다. 같은 건물 거래는 드물고, 구 전체 비교군은
구역 프리미엄을 못 잡는다. 그래서 구역 대표지번 주변 본번 묶음(블록)으로 반기 추이를 본다.
  - 해제거래: 'O' 행과 표시 없는 쌍둥이 행이 함께 온다 → 둘 다 제거
  - 신축 분양 오염: 거래연도 - 준공연도 < 2 는 추이에서 제외
CLAUDE.md: PublicDataReader 금지(requests 직접), 병렬 금지, sleep 0.33s, .env PUBLIC_DATA_SERVICE_KEY.

사용(프로젝트 루트에서):
  python skills/gongmae-redev-review/scripts/villa_block_comps.py fetch --lawd 11215 --umd 구의 -o raw.json
  python skills/gongmae-redev-review/scripts/villa_block_comps.py stats raw.json --jibun 241-8 --area 27.36 \
      --block 221,224,226,229,239,241,242,243,246,248,249,251 [--csv block_trades.csv]
raw JSON 은 커밋하지 않는다.
"""
import argparse, csv, json, os, re, statistics as st, sys, time
from collections import defaultdict

EP = {'trade': 'https://apis.data.go.kr/1613000/RTMSDataSvcRHTrade/getRTMSDataSvcRHTrade',
      'rent': 'https://apis.data.go.kr/1613000/RTMSDataSvcRHRent/getRTMSDataSvcRHRent'}


def yms(n, ey, em):
    out, y, m = [], ey, em
    for _ in range(n):
        out.append('%d%02d' % (y, m))
        m -= 1
        if m < 1:
            y, m = y - 1, 12
    return out[::-1]


def num(x):
    return int(re.sub(r'[^\d]', '', str(x)) or 0)


def bon(t):
    return str(t.get('jibun', '')).strip().split('-')[0]


def half(t):
    return '%sH%d' % (t['dealYear'], 1 if int(t['dealMonth']) <= 6 else 2)


def _sig(t):
    return (str(t.get('dealYear')), str(t.get('dealMonth')), str(t.get('dealDay')), str(t.get('jibun', '')).strip(),
            str(t.get('excluUseAr')), str(t.get('floor')), str(t.get('dealAmount')))


def drop_cancelled(trades):
    """해제 'O' 행과 그 쌍둥이(표시 없는 동일 거래) 행을 모두 제거."""
    cancelled = {_sig(t) for t in trades if str(t.get('cdealType', '')).strip() == 'O'}
    return [t for t in trades if _sig(t) not in cancelled]


def block_trend(trades, block, lo=20.0, hi=40.0, min_age=2):
    """블록 본번·면적대 거래의 반기별 ㎡당 가격(만원) 리스트. 신축 분양(연식<min_age) 제외."""
    g = defaultdict(list)
    for t in drop_cancelled(trades):
        try:
            a, y = float(t['excluUseAr']), int(t.get('buildYear') or 0)
        except (TypeError, ValueError):
            continue
        if bon(t) in block and lo <= a <= hi and int(t['dealYear']) - y >= min_age:
            g[half(t)].append(num(t['dealAmount']) / a)
    return dict(g)


def fetch(lawd, umd, months, ey, em, path):
    import requests
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv(usecwd=True))
    key = os.getenv('PUBLIC_DATA_SERVICE_KEY')
    out = {}
    for kind, url in EP.items():
        rows = []
        for ym in yms(months, ey, em):
            page = 1
            while True:
                b = {}
                for _ in range(3):
                    try:
                        r = requests.get(url, params={'serviceKey': key, 'LAWD_CD': lawd, 'DEAL_YMD': ym,
                                                      'numOfRows': 1000, 'pageNo': page, '_type': 'json'}, timeout=30)
                        b = r.json().get('response', {}).get('body', {}) or {}
                        break
                    except Exception:
                        time.sleep(2)
                its = b.get('items') or {}
                its = its.get('item', []) if isinstance(its, dict) else its
                if isinstance(its, dict):
                    its = [its]
                rows += [dict(it, _ym=ym) for it in its or [] if umd in str(it.get('umdNm', ''))]
                time.sleep(0.33)
                if page * 1000 >= int(b.get('totalCount') or 0) or not its:
                    break
                page += 1
            print(kind, ym, len(rows), file=sys.stderr)
        out[kind] = rows
    json.dump(out, open(path, 'w', encoding='utf-8'), ensure_ascii=False)


def stats(path, jibun, area, block, csv_out=None, rent_from=None):
    d = json.load(open(path, encoding='utf-8'))
    T, R = d['trade'], d['rent']
    print('== 동일 지번 매매 (O=해제)')
    for t in sorted([t for t in T if str(t.get('jibun')).strip() == jibun], key=lambda t: t['_ym']):
        print(t['dealYear'], t['dealMonth'], t['excluUseAr'], '%s층' % t['floor'], t['dealAmount'], t.get('cdealType') or '')
    print('== 동일 지번 임대 (보증금/월세 만원)')
    for t in sorted([t for t in R if str(t.get('jibun')).strip() == jibun], key=lambda t: t['_ym']):
        print(t['dealYear'], t['dealMonth'], t['excluUseAr'], '%s층' % t['floor'], t['deposit'], t['monthlyRent'], t.get('contractType'))
    g = block_trend(T, block)
    print('== 블록 ㎡당 중앙값(만원) → %.2f㎡ 환산' % area)
    for k in sorted(g):
        print(k, 'n=%d' % len(g[k]), round(st.median(g[k])), round(st.median(g[k]) * area))
    rent_from = rent_from or min((r['_ym'] for r in R), default='000000')
    J = [num(r['deposit']) for r in R if bon(r) in block and 20 <= float(r['excluUseAr']) <= area * 1.2
         and num(r['monthlyRent']) == 0 and r['_ym'] >= rent_from]
    if len(J) >= 4:
        print('== 블록 전세(%s~) n=%d 중앙 %d 사분위 %s' % (rent_from, len(J), st.median(J), st.quantiles(J, n=4)))
    if csv_out:
        cols = ['dealYear', 'dealMonth', 'dealDay', 'jibun', 'mhouseNm', 'excluUseAr', 'landAr', 'floor', 'buildYear', 'dealAmount']
        rows = [t for t in drop_cancelled(T) if bon(t) in block and 20 <= float(t['excluUseAr']) <= 40]
        with open(csv_out, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f)
            w.writerow(cols)
            for t in sorted(rows, key=lambda t: (int(t['dealYear']), int(t['dealMonth']), int(t['dealDay']))):
                w.writerow([str(t.get(c, '')).strip() for c in cols])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    f = sp.add_parser('fetch')
    f.add_argument('--lawd', required=True, help='시군구코드 5자리 (광진구 11215)')
    f.add_argument('--umd', required=True, help='법정동명 부분일치 (예: 구의)')
    f.add_argument('--months', type=int, default=30)
    f.add_argument('--end', default=time.strftime('%Y%m'), help='마지막 계약월 YYYYMM')
    f.add_argument('-o', required=True)
    s = sp.add_parser('stats')
    s.add_argument('raw')
    s.add_argument('--jibun', required=True)
    s.add_argument('--area', type=float, required=True)
    s.add_argument('--block', required=True, help='본번 콤마 목록')
    s.add_argument('--csv')
    s.add_argument('--rent-from', help='전세 집계 시작 YYYYMM')
    a = ap.parse_args()
    if a.cmd == 'fetch':
        fetch(a.lawd, a.umd, a.months, int(a.end[:4]), int(a.end[4:]), a.o)
    else:
        stats(a.raw, a.jibun, a.area, set(a.block.split(',')), a.csv, a.rent_from)


if __name__ == '__main__':
    main()
