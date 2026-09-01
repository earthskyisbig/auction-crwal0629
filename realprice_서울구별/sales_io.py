# -*- coding: utf-8 -*-
"""실거래 CSV 공용 로더 — 해제거래·중복 처리를 한 곳에서.

RTMS 는 해제된 계약을 '원본 행(cdealType 빈값)' + '해제 표시 행(cdealType=O)' 두 줄로 내보내는 경우가 많다
(2026-09 실측: 강남구 546개 O행 중 341개가 동일 내용의 빈값 쌍둥이 행을 가짐). O행만 버리면 해제된 거래의 원본이
통계에 남아 평당가·매칭지수가 위로 치우친다. 그래서 (ym, umdNm, aptNm, excluUseAr, dealAmount, floor, dealDay) 그룹
안에 O 가 하나라도 있으면 그룹 전체를 버리고, 완전 중복 행은 하나만 남긴다.
"""
import csv, os

W = os.path.dirname(os.path.abspath(__file__))
_SALE_KEY = ('ym', 'umdNm', 'aptNm', 'excluUseAr', 'dealAmount', 'floor', 'dealDay')


def drop_cancelled(rows, key_fields=_SALE_KEY, cancel_field='cdealType', cancel_value='O'):
    """행 목록 → 해제 그룹 제거 + 완전 중복 제거 (입력 순서 유지). 순수 함수."""
    groups = {}
    order = []
    for r in rows:
        k = tuple((r.get(f) or '').strip() for f in key_fields)
        if k not in groups:
            groups[k] = {'rows': [], 'cancelled': False}
            order.append(k)
        g = groups[k]
        g['rows'].append(r)
        if (r.get(cancel_field) or '').strip() == cancel_value:
            g['cancelled'] = True
    out = []
    for k in order:
        g = groups[k]
        if g['cancelled']:
            continue
        out.append(g['rows'][0])   # 완전 중복은 첫 행만
    return out


def load_sales(gu, workdir=W):
    """sale_<구>.csv → 해제·중복 정리된 행 목록. 파일이 없으면 FileNotFoundError."""
    path = os.path.join(workdir, f'sale_{gu}.csv')
    with open(path, encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    return drop_cancelled(rows)


def load_rent(gu, workdir=W):
    """rent_<구>.csv → 행 목록 (전월세는 해제 플래그가 없다; 완전 중복만 제거)."""
    path = os.path.join(workdir, f'rent_{gu}.csv')
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    seen, out = set(), []
    for r in rows:
        k = tuple(sorted(r.items()))
        if k in seen:
            continue
        seen.add(k); out.append(r)
    return out


def list_gus(workdir=W):
    """sale_*.csv 가 있는 구 이름 목록 (정렬)."""
    return sorted(f[5:-4] for f in os.listdir(workdir) if f.startswith('sale_') and f.endswith('.csv'))
