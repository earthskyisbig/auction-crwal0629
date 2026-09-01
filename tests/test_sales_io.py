# -*- coding: utf-8 -*-
"""realprice_서울구별/sales_io.py — 해제거래 쌍둥이 행·중복 제거."""
import conftest  # noqa: F401
import sales_io


def _r(ym, apt, amt, cancel='', floor='5', day='3'):
    return {'ym': ym, 'umdNm': '대치동', 'aptNm': apt, 'excluUseAr': '84.9', 'dealAmount': amt,
            'floor': floor, 'dealDay': day, 'cdealType': cancel}


def test_cancelled_twin_rows_are_both_dropped():
    rows = [_r('202601', 'A', '100,000'), _r('202601', 'A', '100,000', cancel='O'),   # 원본+해제 → 둘 다 제거
            _r('202601', 'A', '90,000'),                                             # 정상
            _r('202602', 'B', '50,000', cancel='O')]                                 # 해제만 → 제거
    out = sales_io.drop_cancelled(rows)
    assert [(r['aptNm'], r['dealAmount']) for r in out] == [('A', '90,000')]


def test_exact_duplicates_collapse_to_one():
    rows = [_r('202601', 'A', '100,000'), _r('202601', 'A', '100,000'), _r('202601', 'A', '100,000', floor='6')]
    out = sales_io.drop_cancelled(rows)
    assert len(out) == 2


def test_load_sales_from_dir(tmp_path):
    import csv
    p = tmp_path / 'sale_테스트구.csv'
    with open(p, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(_r('1', 'A', '1').keys()))
        w.writeheader(); w.writerows([_r('202601', 'A', '100,000'), _r('202601', 'A', '100,000', cancel='O')])
    assert sales_io.load_sales('테스트구', str(tmp_path)) == []
    assert sales_io.list_gus(str(tmp_path)) == ['테스트구']
    assert sales_io.load_rent('없는구', str(tmp_path)) == []
