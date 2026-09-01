# -*- coding: utf-8 -*-
"""realprice_서울구별/windows.py 분석 기간 계산."""
from datetime import date
import conftest  # noqa: F401
import windows


def test_month_list_rolls_over_year_boundary():
    ms = windows.month_list(end=date(2026, 1, 15), n=3)
    assert ms == ['202511', '202512', '202601']


def test_month_list_default_length_is_24():
    assert len(windows.month_list(end=date(2026, 9, 2))) == 24


def test_windows_A_and_B_do_not_overlap():
    assert not (windows.A & windows.B)
    assert len(windows.A) == 6 and len(windows.B) == 6
    assert windows.RENT_MONTHS == sorted(windows.B)


def test_default_window_ends_last_complete_month():
    assert windows.last_complete_month(date(2026, 9, 2)) == date(2026, 8, 31)
    assert windows.last_complete_month(date(2026, 1, 1)) == date(2025, 12, 31)
    ms = windows.month_list(end=windows.last_complete_month(date(2026, 9, 2)))
    assert ms[0] == '202409' and ms[-1] == '202608'
