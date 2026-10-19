# -*- coding: utf-8 -*-
"""gongmae-redev-review 순수 함수: 해제 쌍둥이 제거·블록 추이·인수액·입찰 상한·공매 회차."""
import conftest  # noqa: F401
import villa_block_comps as vb
import bid_calc as bc


def _t(jibun, ar, amt, y=2025, m=3, d=1, built=2016, fl='3', o=''):
    return {'dealYear': str(y), 'dealMonth': str(m), 'dealDay': str(d), 'jibun': jibun, 'excluUseAr': str(ar),
            'floor': fl, 'dealAmount': amt, 'buildYear': str(built), 'cdealType': o}


def test_drop_cancelled_removes_o_row_and_its_twin():
    keep = _t('241-8', 29.04, '31,500')
    twin = _t('241-8', 39.98, '48,000', m=10, d=4)
    rows = [keep, twin, dict(twin, cdealType='O')]
    assert vb.drop_cancelled(rows) == [keep]


def test_block_trend_filters_block_area_and_newbuild():
    rows = [_t('241-8', 27.36, '27,360'),              # 블록·면적·연식 OK → 1000만/㎡
            _t('241-8', 27.36, '30,000', built=2024),  # 신축 분양(연식<2) 제외
            _t('300-1', 27.36, '50,000'),              # 블록 밖
            _t('242-1', 59.0, '50,000'),               # 면적 밖
            _t('242-1', 20.0, '30,000', m=8)]          # 2025H2 1500만/㎡
    g = vb.block_trend(rows, {'241', '242'})
    assert g == {'2025H1': [1000.0], '2025H2': [1500.0]}


def test_assumed_is_function_of_bid_with_floor():
    dep, senior = 262_500_000, 4_000_000
    assert bc.assumed(333_500_000, dep, senior) == 0
    assert bc.assumed(266_500_000, dep, senior) == 0                    # 바닥 정확히
    assert bc.assumed(200_000_000, dep, senior) == 66_500_000
    assert bc.effective_cost(100_000_000, dep, senior) == 266_500_000    # 바닥 아래는 원가 불변
    assert bc.assumed(1_000_000, dep, senior) == dep                     # 선순위도 못 채우면 전액


def test_rounds_decline_10pct_to_half():
    assert bc.rounds(100_000_000, 7) == [100_000_000, 90_000_000, 80_000_000, 70_000_000,
                                         60_000_000, 50_000_000, 50_000_000]


def test_bid_cap_formula():
    # (3.83억×0.9 − 1,300만) / 1.014
    assert round(bc.bid_cap(383_000_000, 0.10, 13_000_000, 0.011), -5) == 327_100_000


def test_no_claim_means_full_assumption():
    assert bc.assumed(333_500_000, 262_500_000, 4_000_000, claimed=False) == 262_500_000
