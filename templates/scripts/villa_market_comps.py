# -*- coding: utf-8 -*-
"""서울 다세대(연립) 실거래 비교군 산출.

빌라는 아파트처럼 '동일 단지 동일 평형'이 성립하지 않는다. 그래서 비교군을
  ① 동일 지번(같은 건물) → 최우선 근거
  ② 동일 법정동 + 전용면적 ±20% + 준공 ±7년 → 표준 비교군
순으로 잡는다. 해제거래(cdealType='O') 제외, 상하위 5% 절사.
CLAUDE.md 준수: PublicDataReader 미사용(직접 requests), 병렬 금지, sleep 0.32s.
"""
import os, re, json, time, statistics
import requests
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))
KEY = os.getenv('PUBLIC_DATA_SERVICE_KEY')
RH = 'https://apis.data.go.kr/1613000/RTMSDataSvcRHTrade/getRTMSDataSvcRHTrade'
SLEEP = 0.32

GU = {'종로구':'11110','중구':'11140','용산구':'11170','성동구':'11200','광진구':'11215',
      '동대문구':'11230','중랑구':'11260','성북구':'11290','강북구':'11305','도봉구':'11320',
      '노원구':'11350','은평구':'11380','서대문구':'11410','마포구':'11440','양천구':'11470',
      '강서구':'11500','구로구':'11530','금천구':'11545','영등포구':'11560','동작구':'11590',
      '관악구':'11620','서초구':'11650','강남구':'11680','송파구':'11710','강동구':'11740'}

def yms(n=24, ey=2026, em=8):
    out, y, m = [], ey, em
    for _ in range(n):
        out.append('%d%02d' % (y, m))
        m -= 1
        if m < 1:
            y, m = y - 1, 12
    return out[::-1]

_cache = {}
def fetch_gu(lawd, months=24):
    if lawd in _cache:
        return _cache[lawd]
    rows = []
    for ym in yms(months):
        page = 1
        while True:
            try:
                r = requests.get(RH, params={'serviceKey': KEY, 'LAWD_CD': lawd, 'DEAL_YMD': ym,
                                             'numOfRows': 1000, 'pageNo': page, '_type': 'json'}, timeout=25)
                b = (r.json().get('response', {}).get('body', {}) or {})
                its = b.get('items') or {}
                its = its.get('item', []) if isinstance(its, dict) else its
                if isinstance(its, dict):
                    its = [its]
                total = int(b.get('totalCount') or 0)
            except Exception:
                its, total = [], 0
            for it in its or []:
                if str(it.get('cdealType', '')).strip() == 'O':
                    continue
                try:
                    amt = int(re.sub(r'[^\d]', '', str(it.get('dealAmount'))))
                    ar = float(it.get('excluUseAr'))
                except (TypeError, ValueError):
                    continue
                rows.append({'ym': ym, 'amt': amt, 'ar': ar,
                             'umd': str(it.get('umdNm') or '').strip(),
                             'jibun': str(it.get('jibun') or '').strip(),
                             'nm': str(it.get('mhouseNm') or '').strip(),
                             'yr': it.get('buildYear'), 'fl': it.get('floor'),
                             'land': it.get('landAr')})
            time.sleep(SLEEP)
            if page * 1000 >= total or not its:
                break
            page += 1
    _cache[lawd] = rows
    return rows

def band(vals, cut=0.05):
    v = sorted(vals)
    k = int(len(v) * cut)
    return v[k:len(v)-k] if len(v) > 8 else v

def comps(gu, umd, jibun, area, built=None):
    lawd = GU.get(gu)
    if not lawd:
        return None
    rows = fetch_gu(lawd)
    same_bld = [r for r in rows if jibun and r['jibun'] == jibun]
    lo, hi = area * 0.8, area * 1.2
    peer = [r for r in rows if (not umd or r['umd'] == umd) and lo <= r['ar'] <= hi
            and (not built or not r['yr'] or abs(int(r['yr']) - built) <= 7)]
    if len(peer) < 5:   # 표본 부족 → 연식 조건 해제
        peer = [r for r in rows if (not umd or r['umd'] == umd) and lo <= r['ar'] <= hi]
    if len(peer) < 5:   # 그래도 부족 → 구 전체 면적대
        peer = [r for r in rows if lo <= r['ar'] <= hi]
    p = band([r['amt'] for r in peer])
    sb = [r['amt'] for r in same_bld]
    return {
        '동일지번건수': len(same_bld),
        '동일지번중앙': int(statistics.median(sb)) if sb else 0,
        '동일지번거래': [[r['ym'], '%g㎡' % r['ar'], '%s층' % r['fl'], r['amt']] for r in
                     sorted(same_bld, key=lambda x: x['ym'], reverse=True)[:5]],
        '비교군건수': len(p),
        '중앙': int(statistics.median(p)) if p else 0,
        '보수': int(statistics.quantiles(p, n=4)[0]) if len(p) >= 4 else (min(p) if p else 0),
        '낙관': int(statistics.quantiles(p, n=4)[2]) if len(p) >= 4 else (max(p) if p else 0),
        '최저': min(p) if p else 0, '최고': max(p) if p else 0,
        '기준': ('동일법정동+면적±20%%' if umd else '구전체+면적±20%%'),
    }

# 분석 대상 (구, 법정동, 지번, 전용면적, 준공추정)
TARGETS = [
    ('2025타경13004',  '강서구',  '화곡동', '372-48',  68.9, None),
    ('2025타경8670',   '양천구',  '신월동', '229-31',  62.5, None),
    ('2025타경11168',  '금천구',  '시흥동', '3-20',    58.9, None),
    ('2025타경103194', '관악구',  '봉천동', '1615-21', 60.5, None),
    ('2025타경52250',  '서대문구','연희동', '1-64',    64.0, None),
    ('2025타경10752',  '구로구',  '오류동', '81-171',  53.7, None),
    ('2025타경12457',  '강서구',  '화곡동', '102-26',  57.7, None),
    ('2023타경108446', '구로구',  '오류동', '',        33.5, None),
    ('2025타경10965',  '강서구',  '화곡동', '504-9',   46.6, None),
]

def main():
    out = {}
    for case, gu, umd, jibun, area, built in TARGETS:
        c = comps(gu, umd, jibun, area, built)
        out[case] = dict(gu=gu, umd=umd, jibun=jibun, area=area, **(c or {}))
        if c:
            print('%s %s %s %s %.1f㎡ | 동일지번 %d건(중앙 %s만) | 비교군 %d건 보수/중앙/낙관 %s/%s/%s만' % (
                case, gu, umd, jibun or '-', area, c['동일지번건수'],
                format(c['동일지번중앙'], ','), c['비교군건수'],
                format(c['보수'], ','), format(c['중앙'], ','), format(c['낙관'], ',')), flush=True)
    json.dump(out, open('_workspace/villa_market.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('saved villa_market.json')

if __name__ == '__main__':
    main()
