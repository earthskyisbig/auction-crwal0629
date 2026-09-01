# -*- coding: utf-8 -*-
"""analyze_case.py 의 순수 로직: 사건번호 파싱·날짜 튜플·시세 요약·취득세율·투자분석."""
from datetime import date
from types import SimpleNamespace
import conftest  # noqa: F401
import analyze_case as ac


def test_parse_case_formats():
    assert ac.parse_case(SimpleNamespace(case='2025타경2412', year=None, caseno=None)) == ('2025', '2412')
    assert ac.parse_case(SimpleNamespace(case=' 2025 타경 41952', year=None, caseno=None)) == ('2025', '41952')
    assert ac.parse_case(SimpleNamespace(case=None, year='2025', caseno='no.2412')) == ('2025', '2412')


def test_ymd_tuple_variants():
    assert ac._ymd_tuple('2022.3.25.') == (2022, 3, 25)
    assert ac._ymd_tuple('20220325') == (2022, 3, 25)
    assert ac._ymd_tuple('2022-03-25') == (2022, 3, 25)
    assert ac._ymd_tuple('') is None and ac._ymd_tuple(None) is None


def test_recent_months_excludes_current_month():
    assert ac._recent_months(3, today=date(2026, 9, 2)) == ['202608', '202607', '202606']
    assert ac._recent_months(2, today=date(2026, 1, 10)) == ['202512', '202511']


def _row(apt, area, amt, cancel='', ym='202608'):
    return {'aptNm': apt, 'excluUseAr': str(area), 'dealAmount': amt, 'floor': '7',
            'dealYear': ym[:4], 'dealMonth': ym[4:], 'cdealType': cancel, 'ym': ym}


def test_summarize_market_median_and_filters():
    rows = [_row('양주 푸르지오', 84.9, '45,000'),
            _row('양주푸르지오', 84.9, '47,000', ym='202607'),
            _row('양주푸르지오', 84.9, '99,000', cancel='O'),     # 해제 제외
            _row('양주푸르지오', 59.9, '30,000'),                  # 평형 불일치
            _row('다른단지', 84.9, '10,000')]
    s = ac.summarize_market(rows, '양주푸르지오', 84.9)
    assert s['표본수'] == 2
    assert s['시세중앙값'] == 460_000_000
    assert s['최근거래'][0]['ym'] == '202608'
    assert ac.summarize_market(rows, '없는단지', 84.9) is None
    assert ac.summarize_market(rows, '', 84.9) is None


def test_acq_tax_rate_follows_local_tax_act():
    assert ac._acq_tax_rate(500_000_000) == 0.011
    assert ac._acq_tax_rate(750_000_000) == 0.022          # (7.5×2/3 − 3) = 2.00% → ×1.1
    assert round(ac._acq_tax_rate(800_000_000), 5) == round(2.33 * 1.1 / 100, 5)
    assert ac._acq_tax_rate(1_000_000_000) == 0.033


def test_compute_investment_uses_floor_price_when_comps_below_minimum():
    dxdy = {'aeeEvlAmt': '500000000', 'fstPbancLwsDspslPrc': '400000000'}
    near = {'동일읍면동_평균매각가율': 70.0, '동일단지사례': []}
    iv = ac.compute_investment(dxdy, {'임차인': []}, near, {})
    assert iv['예상낙찰가'] == 400_000_000          # 70% = 3.5억 < 최저가 4억 → 하한
    assert iv['인수보증금'] == 0
    assert iv['총취득원가'] == 400_000_000 + iv['취득세'] + iv['법무등기비'] + iv['명도비']


def test_compute_investment_assumes_senior_tenant_deposit_and_profit():
    dxdy = {'aeeEvlAmt': '500000000', 'fstPbancLwsDspslPrc': '350000000'}
    myse = {'임차인': [{'성명': '홍길동', '보증금': 100_000_000, '배당요구일': '', '확정일자': ''}],
            '대항력앞선임차인': ['홍길동']}
    iv = ac.compute_investment(dxdy, myse, {'동일단지사례': [], '동일읍면동_평균매각가율': 80.0}, {'market': 600_000_000})
    assert iv['예상낙찰가'] == 400_000_000 and iv['인수보증금'] == 100_000_000
    assert '전액 인수 위험' in iv['인수주석']
    assert iv['예상순수익'] == 600_000_000 - iv['총취득원가'] - iv['매도중개보수']


def test_compute_investment_special_condition_waives_deposit():
    dxdy = {'aeeEvlAmt': '500000000', 'fstPbancLwsDspslPrc': '350000000'}
    myse = {'임차인': [{'성명': 'A', '보증금': 100_000_000}], '대항력앞선임차인': ['A'],
            '특별매각조건': '채권자 보증금반환청구권 포기'}
    iv = ac.compute_investment(dxdy, myse, {'동일단지사례': []}, {})
    assert iv['인수보증금'] == 0


def test_tenant_table_from_coordinates():
    def run(text, x, y):
        return {'text': text, 'rect': [{'left': x, 'bottom': y}]}
    runs = [run('성  명', 10, 500), run('점유부분', 100, 500),
            run('홍길동', 10, 450), run('2022.1.1.', 60, 450), run('315,000,000', 150, 450),
            run('2022.3.25.', 250, 450), run('2022.2.28.', 320, 450),
            run('<비고>', 10, 100)]
    r = ac.parse_tenant_table(runs, '2023.11.7. 근저당권')
    assert r['없음'] is False and len(r['임차인']) == 1
    t = r['임차인'][0]
    assert t['성명'] == '홍길동' and t['보증금'] == 315_000_000
    assert t['전입신고일'] == '2022.3.25.' and t['확정일자'] == '2022.2.28.'
    assert r['인수위험'] is True and r['대항력앞선임차인'] == ['홍길동']


def test_tenant_table_none():
    runs = [{'text': '조사된 임차내역없음', 'rect': [{'left': 10, 'bottom': 300}]},
            {'text': '성  명', 'rect': [{'left': 10, 'bottom': 500}]},
            {'text': '<비고>', 'rect': [{'left': 10, 'bottom': 100}]}]
    assert ac.parse_tenant_table(runs, '')['없음'] is True


def test_fmt_won_blank_for_missing():
    assert ac.fmt_won(None) == '' and ac.fmt_won('') == '' and ac.fmt_won('1500') == '1,500원'


def _run(text, x, y):
    return {'text': text, 'rect': [{'left': x, 'bottom': y}]}


def test_tenant_table_keeps_1990s_move_in_dates():
    runs = [_run('성  명', 10, 500), _run('홍길동', 10, 450), _run('315,000,000', 150, 450),
            _run('1998.05.01.', 250, 450), _run('1998.05.02.', 320, 450), _run('<비고>', 10, 100)]
    r = ac.parse_tenant_table(runs, '2023-11-07 근저당권')
    assert len(r['임차인']) == 1 and r['임차인'][0]['전입신고일'] == '1998.05.01.'
    assert r['인수위험'] is True


def test_tenant_table_merges_two_row_tenant():
    runs = [_run('성  명', 10, 500),
            _run('홍길동 현황조사', 10, 450), _run('315,000,000', 150, 450), _run('2022.3.25.', 250, 450),
            _run('권리신고', 10, 430), _run('315,000,000', 150, 430), _run('2022.3.25.', 250, 430),
            _run('2022.2.28.', 320, 430), _run('2025.7.1.', 380, 430),
            _run('<비고>', 10, 100)]
    r = ac.parse_tenant_table(runs, '2023.11.7.')
    assert len(r['임차인']) == 1
    t = r['임차인'][0]
    assert t['성명'] == '홍길동' and t['확정일자'] == '2022.2.28.' and t['배당요구일'] == '2025.7.1.'
    iv = ac.compute_investment({'aeeEvlAmt': '500000000', 'fstPbancLwsDspslPrc': '350000000'},
                               {'임차인': r['임차인'], '대항력앞선임차인': r['대항력앞선임차인']},
                               {'동일단지사례': []}, {})
    assert iv['인수보증금'] == 315_000_000


def test_summarize_market_restricts_to_dong_when_given():
    rows = [_row('e편한세상A', 84.9, '50,000'), _row('e편한세상B', 84.9, '90,000')]
    rows[0]['umdNm'] = '옥정동'; rows[1]['umdNm'] = '덕정동'
    s = ac.summarize_market(rows, 'e편한세상', 84.9, dong='옥정동')
    assert s['표본수'] == 1 and s['시세중앙값'] == 500_000_000


def test_acq_tax_adds_rural_special_tax_over_85m2():
    assert ac._acq_tax_rate(500_000_000, area_m2=84.9) == 0.011
    assert ac._acq_tax_rate(500_000_000, area_m2=101.0) == 0.013
