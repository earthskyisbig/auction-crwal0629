# -*- coding: utf-8 -*-
"""분석 기간 계산 — 실행 시점 기준 롤링 24개월.
   months: 이번 달 포함 최근 24개월 (YYYYMM 문자열)
   A: 첫 6개월(비교 기준), B: 최근 6개월(현재), rent_months == B
"""
from datetime import date

def month_list(end=None, n=24):
    end = end or date.today()
    y, m = end.year, end.month
    out = []
    for _ in range(n):
        out.append(f'{y}{m:02d}')
        m -= 1
        if m == 0: y, m = y - 1, 12
    return list(reversed(out))

MONTHS = month_list()
A = set(MONTHS[:6])
B = set(MONTHS[-6:])
RENT_MONTHS = MONTHS[-6:]

if __name__ == '__main__':
    print('MONTHS:', MONTHS[0], '~', MONTHS[-1])
    print('A:', sorted(A))
    print('B:', sorted(B))
