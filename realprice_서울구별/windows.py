# -*- coding: utf-8 -*-
"""분석 기간 계산 — 롤링 24개월.
   months: 지난달을 마지막으로 하는 최근 24개월 (YYYYMM). 이번 달은 신고 지연(30일)으로 표본이 거의 없어 제외한다.
   A: 첫 6개월(비교 기준), B: 최근 6개월(현재), rent_months == B

   windows_manifest.json 이 있으면(collect_seoul.py 가 수집 완료 시 기록) 그 기간을 그대로 쓴다 —
   수집 뒤 달이 바뀐 상태에서 분석 스크립트를 단독 실행해도 CSV 와 기간이 어긋나지 않게.
"""
import json, os
from datetime import date, timedelta

W = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(W, 'windows_manifest.json')


def last_complete_month(today=None):
    t = today or date.today()
    return date(t.year, t.month, 1) - timedelta(days=1)


def month_list(end=None, n=24):
    """end(기본: 지난달)를 마지막으로 하는 n개월."""
    end = end or last_complete_month()
    y, m = end.year, end.month
    out = []
    for _ in range(n):
        out.append(f'{y}{m:02d}')
        m -= 1
        if m == 0: y, m = y - 1, 12
    return list(reversed(out))


def write_manifest(months, path=MANIFEST):
    json.dump({'months': months, 'written': date.today().isoformat()}, open(path, 'w', encoding='utf-8'))


def _load():
    if os.path.exists(MANIFEST):
        try:
            m = json.load(open(MANIFEST, encoding='utf-8')).get('months')
            if m and len(m) >= 12:
                return list(m)
        except (ValueError, OSError):
            pass
    return month_list()


MONTHS = _load()
A = set(MONTHS[:6])
B = set(MONTHS[-6:])
RENT_MONTHS = MONTHS[-6:]

if __name__ == '__main__':
    print('MONTHS:', MONTHS[0], '~', MONTHS[-1], '(manifest)' if os.path.exists(MANIFEST) else '(계산)')
    print('A:', sorted(A))
    print('B:', sorted(B))
