# -*- coding: utf-8 -*-
"""realprice_서울구별/compute_complex.py 순수 함수."""
import conftest  # noqa: F401
import compute_complex as cc
from windows import MONTHS


def test_matched_change_requires_two_each_and_uses_median_ratio():
    a = {84: [100, 100], 59: [50, 50], 33: [30]}
    b = {84: [120, 120], 59: [55, 55], 33: [60, 60]}
    chg, pairs = cc.matched_change(a, b)
    assert pairs == 2 and chg == 15.0            # ratios 1.2, 1.1 → median 1.15
    assert cc.matched_change({84: [1]}, {84: [2]}) == (None, 0)


def test_summarize_complex_representative_area_and_gap():
    A0, B0 = MONTHS[0], MONTHS[-1]
    rows = [(A0, 100000, 84.9, 3900)] * 2 + [(B0, 120000, 84.9, 4680)] * 3 + [(B0, 80000, 59.9, 4400)]
    r = cc.summarize_complex(rows, rent_by_area={84: [70000, 72000]})
    assert r['t'] == 6 and r['tb'] == 4 and r['pairs'] == 1 and r['chg'] == 20.0
    assert r['ar'] == 84 and r['price'] == 120000 and r['n_ar'] == 3
    assert r['jeonse'] == 71000 and r['jr'] == 59.2 and r['gap'] == 49000
    assert len(r['s']) == len(MONTHS)


def test_summarize_complex_without_recent_trades():
    r = cc.summarize_complex([(MONTHS[0], 100000, 84.9, 3900)])
    assert r['pp'] is None and r['ar'] is None and r['chg'] is None
