# -*- coding: utf-8 -*-
"""auction-priority-pipeline 순수 함수: 주소 파싱·시군구 코드·실거래 관문 판정."""
from datetime import date
import conftest  # noqa: F401
import enrich_complex as ec
import eval_priority as ep


def test_parse_row_extracts_sgg_dong_name_area():
    p = ec.parse_row({'물건소재지': '경기도 수원시 권선구 곡반정동 123 (곡반정동, 수원하늘채더퍼스트2단지) 101동 5층',
                      '전용면적': '84.96㎡'})
    assert {k: p[k] for k in ('sgg', 'dong', 'name', 'area')} == {'sgg': '수원시 권선구', 'dong': '곡반정동', 'name': '수원하늘채더퍼스트2단지', 'area': 84.96}
    assert p['name_from_token'] is False


def test_parse_row_falls_back_to_brand_token():
    p = ec.parse_row({'물건소재지': '경기도 양주시 옥정동 999 양주옥정푸르지오 102동', '전용면적': '59.9'})
    assert p['sgg'] == '양주시' and p['name'] == '양주옥정푸르지오' and p['area'] == 59.9


def test_parse_row_rejects_non_gyeonggi():
    assert ec.parse_row({'물건소재지': '서울특별시 금천구 시흥동 1', '전용면적': '59'}) is None


def test_sgg_code_lookup():
    assert ec.sgg_code('수원시 권선구') == ['41113']
    assert ec.sgg_code('화성시') == ec.HWASEONG
    assert sorted(ec.sgg_code('용인시')) == ['41461', '41463', '41465']
    assert ec.sgg_code('없는시') == []


def test_norm_strips_suffix_and_unifies_brand():
    assert ec.norm('래미안 아파트') == '래미안'
    assert ec.norm('이편한세상 1차') == 'e편한세상1차'


def test_passes_basic_filter():
    row = {'물건소재지': '경기도 양주시 옥정동 1 양주옥정푸르지오', '전용면적': '84.9', '유찰횟수': '1'}
    assert ec.passes_basic_filter(row)['yc'] == 1
    assert ec.passes_basic_filter({**row, '유찰횟수': '3'}) is None
    assert ec.passes_basic_filter({**row, '전용면적': '101'}) is None
    assert ec.passes_basic_filter({**row, '유찰횟수': ''}) is None


def _t(apt, dong, area, amt, cancel=''):
    return {'aptNm': apt, 'umdNm': dong, 'excluUseAr': str(area), 'dealAmount': amt, 'cdealType': cancel}


def test_summarize_trades_gate_logic():
    rows = [_t('수원하늘채더퍼스트2단지', '곡반정동', 84.96, '70,000'),
            _t('수원하늘채더퍼스트2단지', '곡반정동', 84.96, '65,000'),
            _t('수원하늘채더퍼스트2단지', '곡반정동', 59.9, '50,000'),
            _t('수원하늘채더퍼스트2단지', '곡반정동', 84.96, '90,000', cancel='O'),   # 해제 → 제외
            _t('다른단지', '곡반정동', 84.96, '99,000')]
    r = ep.summarize_trades(rows, '하늘채더퍼스트', '곡반정동', 84.96, appr=66000, households=50)
    assert r['trades_12m'] == 3
    assert r['turnover_pct'] == 6.0
    assert r['same_cnt'] == 2 and r['same_max'] == 70000 and r['same_med'] == 70000
    assert r['PASS'] is True


def test_summarize_trades_fails_when_turnover_low_or_price_below_appraisal():
    rows = [_t('A단지', '동', 84.0, '50,000')]
    r = ep.summarize_trades(rows, 'A단지', '동', 84.0, appr=60000, households=1000)
    assert r['pass_turnover'] is False and r['pass_price'] is False and r['PASS'] is False


def test_summarize_trades_zero_households_does_not_crash():
    r = ep.summarize_trades([], 'A', '동', 84.0, appr=1, households=0)
    assert r['turnover_pct'] is None and r['PASS'] is False


def test_to_item_accepts_tuple_and_dict():
    tup = ('c', 'n', 'k', ['41113'], '동', 84.96, 66000, 46200, 1, '8.24', '2022.06', 1833)
    d = ep.to_item(tup)
    assert d['households'] == 1833 and ep.to_item(d) == d


def test_month_list_fixed_end():
    assert ep.month_list(3, end=date(2026, 2, 1)) == ['202512', '202601', '202602']


def test_parse_row_accepts_gun():
    p = ec.parse_row({'물건소재지': '경기도 양평군 양평읍 1 양평자이 101동', '전용면적': '84'})
    assert p['sgg'] == '양평군' and ec.sgg_code('양평군') == ['41830']
    assert p['name_from_token'] is True


def test_basic_filter_prefers_estimated_yuchal_column():
    row = {'물건소재지': '경기도 양주시 옥정동 1 양주옥정푸르지오', '전용면적': '84.9', '유찰횟수': '7', '유찰추정': '2'}
    assert ec.passes_basic_filter(row)['yc'] == 2


def test_month_list_default_ends_last_month(monkeypatch):
    import datetime as dt
    class FakeDate(dt.date):
        @classmethod
        def today(cls): return cls(2026, 9, 2)
    monkeypatch.setattr(ep, 'date', FakeDate)
    assert ep.month_list(3) == ['202606', '202607', '202608']
