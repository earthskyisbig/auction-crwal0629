# -*- coding: utf-8 -*-
"""단지 단위 환금성(회전율) 산출 — apt-location-kit 원칙.

회전율 = 최근 12개월 전체 평형 매매 거래건수 ÷ 세대수
해제거래(cdealType='O') 제외. 대조군으로 같은 시군구 전체 아파트 회전율도 계산.
CLAUDE.md 준수: PublicDataReader 미사용, 병렬 금지, sleep 0.32s.
"""
import os, re, json, time, statistics
import requests
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))
KEY = os.getenv('PUBLIC_DATA_SERVICE_KEY')
RTMS = 'https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev'
BASE = os.path.dirname(os.path.abspath(__file__))
SLEEP = 0.32

def norm(s):
    return re.sub(r'(아파트|단지|차)|\s|[·\-()]', '', str(s or ''))

def yms(n=12, ey=2026, em=8):
    out, y, m = [], ey, em
    for _ in range(n):
        out.append(f'{y}{m:02d}')
        m -= 1
        if m < 1:
            y, m = y - 1, 12
    return out[::-1]

# 분석 대상: (라벨, 단지명, LAWD_CD, 세대수)
TARGETS = [
    ('안성롯데캐슬',   '안성 롯데캐슬 아파트',   '41550', 2320),
    ('팜스프링',       '팜스프링',               '41480', 2944),
    ('공도주은풍림',   '공도주은풍림',           '41550', 2615),
    ('원곡제일오투',   '안성원곡제일오투그란데', '41550', 797),
    ('그린시티동문',   '그린시티동문',           '41480', 1759),
    ('청북이지더원',   '청북이지더원',           '41220', 513),
    ('세창리베하우스', '세창리베하우스',         '41630', 998),
    ('동광모닝스카이', '파주동광모닝스카이',     '41480', 227),
]

def fetch_all(lawd, months=12):
    """시군구 전체 아파트 거래(해제 제외) 원본 수집 — 단지별 집계 + 대조군 동시 사용."""
    rows = []
    for ym in yms(months):
        page = 1
        while True:
            try:
                r = requests.get(RTMS, params={'serviceKey': KEY, 'LAWD_CD': lawd, 'DEAL_YMD': ym,
                                               'numOfRows': 1000, 'pageNo': page, '_type': 'json'}, timeout=25)
                body = (r.json().get('response', {}).get('body', {}) or {})
                its = body.get('items') or {}
                its = its.get('item', []) if isinstance(its, dict) else its
                if isinstance(its, dict):
                    its = [its]
                total = int(body.get('totalCount') or 0)
            except Exception:
                its, total = [], 0
            for it in its or []:
                if str(it.get('cdealType', '')).strip() == 'O':
                    continue
                try:
                    amt = int(re.sub(r'[^\d]', '', str(it.get('dealAmount'))))
                    area = float(it.get('excluUseAr'))
                except (TypeError, ValueError):
                    continue
                rows.append({'ym': ym, 'apt': it.get('aptNm'), 'amt': amt, 'area': area})
            time.sleep(SLEEP)
            if page * 1000 >= total or not its:
                break
            page += 1
    return rows

def main():
    cache = {}
    out = {}
    for label, name, lawd, hh in TARGETS:
        if lawd not in cache:
            print(f'  시군구 {lawd} 전체 거래 수집...', flush=True)
            cache[lawd] = fetch_all(lawd)
        allrows = cache[lawd]
        core = norm(name)
        mine = [r for r in allrows if core in norm(r['apt']) or norm(r['apt']) in core]
        cnt = len(mine)
        rate = round(cnt / hh * 100, 2) if hh else None
        # 대조군: 같은 시군구에서 거래 20건 이상인 단지들의 건수 중앙값(세대수 미상이라 건수 기준)
        bycomplex = {}
        for r in allrows:
            bycomplex.setdefault(norm(r['apt']), []).append(r)
        peer_counts = sorted(len(v) for v in bycomplex.values())
        out[label] = {
            '단지': name, 'LAWD': lawd, '세대수': hh,
            '12개월거래': cnt, '회전율%': rate,
            '시군구총거래': len(allrows), '시군구단지수': len(bycomplex),
            '시군구단지당중앙거래': int(statistics.median(peer_counts)) if peer_counts else 0,
            '월별': [[ym, sum(1 for r in mine if r['ym'] == ym)] for ym in yms()],
        }
        print(f"  {label}: 12개월 {cnt}건 / {hh}세대 = 회전율 {rate}% "
              f"(시군구 단지당 중앙 {out[label]['시군구단지당중앙거래']}건)", flush=True)
    json.dump(out, open(os.path.join(BASE, 'turnover_0909.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('saved turnover_0909.json')

if __name__ == '__main__':
    main()
