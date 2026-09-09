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


# ── 명세서 비고/특별매각조건 기반 인수 면제 판정 (2026-09-09 광진 실측 3건 기준) ──
def test_waiver_detected_in_special_condition():
    assert ac.is_deposit_waived('특별매각조건 채권자의 보증금반환청구권 포기', '') == '특별매각조건상 보증금반환청구권 포기'


def test_waiver_detected_in_remarks_hug_undertaking():
    # 2025타경51818: HUG 가 대항력 포기·임차권등기 말소 동의 확약서를 제출한 사례
    bg = ("주택도시보증공사로부터 2026.06.26.자에 '임차보증금에 대하여 우선변제권만 주장하고 대항력은 포기하며, "
          "임대차 보증금 전액을 변제받지 못하더라도 임차권등기를 말소하는 데 동의한다'는 내용의 확약서가 제출됨")
    assert ac.is_deposit_waived('', bg) == '비고상 대항력 포기 확약서 제출'


def test_remarks_stating_assumption_is_not_a_waiver():
    # 2025타경51897: 비고가 오히려 '전액을 매수인이 인수함' 을 명시 → 면제 아님
    bg = '매수인에게 대항할 수 있는 을구 순위 9번 주택임차권 등기(배당에서 보증금이 전액 변제되지 아니하면 전액을 매수인이 인수함)'
    assert ac.is_deposit_waived('', bg) is None
    assert ac.is_deposit_waived('', '') is None


def test_compute_investment_zeroes_deposit_when_remarks_waive_it():
    dxdy = {'aeeEvlAmt': '198000000', 'fstPbancLwsDspslPrc': '158400000'}
    myse = {'임차인': [{'성명': '이주현', '보증금': 220_000_000, '배당요구일': '2025.7.22.', '확정일자': '2022.04.11'}],
            '대항력앞선임차인': ['이주현'],
            '비고': "주택도시보증공사로부터 '대항력은 포기하며 임차권등기를 말소하는 데 동의한다'는 확약서가 제출됨"}
    iv = ac.compute_investment(dxdy, myse, {'동일단지사례': []}, {})
    assert iv['인수보증금'] == 0
    assert '확약서 원본' in iv['인수주석']


def test_compute_investment_keeps_deposit_when_remarks_confirm_assumption():
    dxdy = {'aeeEvlAmt': '304000000', 'fstPbancLwsDspslPrc': '194560000'}
    myse = {'임차인': [{'성명': '백은실', '보증금': 280_000_000}], '대항력앞선임차인': ['백은실'],
            '비고': '배당에서 보증금이 전액 변제되지 아니하면 전액을 매수인이 인수함'}
    iv = ac.compute_investment(dxdy, myse, {'동일단지사례': []}, {})
    assert iv['인수보증금'] == 280_000_000
    assert '전액 인수 위험' in iv['인수주석']


def test_dividend_adjusted_assumption_leaves_only_the_shortfall():
    # 감정 3.04억·최저 1.95억, 선순위 임차인 보증금 2.8억을 HUG 가 대위변제·경매신청 → 배당 후 잔액만 인수
    dxdy = {'aeeEvlAmt': '304000000', 'fstPbancLwsDspslPrc': '194560000'}
    myse = {'임차인': [{'성명': '백은실', '보증금': 280_000_000}], '대항력앞선임차인': ['백은실'],
            '비고': '주택도시보증공사 : 경매신청채권자로 임차보증금반환채권 전액을 대위변제로 승계함'}
    iv = ac.compute_investment(dxdy, myse, {'동일단지사례': []}, {'sale_rate': 64})
    bid = iv['예상낙찰가']
    assert iv['인수보증금'] == 280_000_000                     # 최악 상한은 그대로
    assert iv['배당후예상인수'] == 280_000_000 - (bid - round(bid * 0.015))
    assert iv['실질취득원가'] < iv['총취득원가']
    assert iv['손익분기매도가'] == iv['실질취득원가']


def test_no_dividend_claim_keeps_full_assumption():
    dxdy = {'aeeEvlAmt': '300000000', 'fstPbancLwsDspslPrc': '200000000'}
    myse = {'임차인': [{'성명': 'A', '보증금': 100_000_000}], '대항력앞선임차인': ['A'], '비고': ''}
    iv = ac.compute_investment(dxdy, myse, {'동일단지사례': []}, {'sale_rate': 66.7})
    assert iv['배당후예상인수'] == 100_000_000
    assert iv['실질취득원가'] == iv['총취득원가']
    assert '전액 인수 가정' in iv['배당근거']


def test_profit_uses_dividend_adjusted_cost():
    dxdy = {'aeeEvlAmt': '304000000', 'fstPbancLwsDspslPrc': '194560000'}
    myse = {'임차인': [{'성명': 'B', '보증금': 280_000_000, '배당요구일': '2025.7.1.', '확정일자': '2022.1.1.'}],
            '대항력앞선임차인': ['B'], '비고': ''}
    iv = ac.compute_investment(dxdy, myse, {'동일단지사례': []}, {'sale_rate': 64, 'market': 330_000_000})
    assert iv['예상순수익'] == 330_000_000 - iv['실질취득원가'] - iv['매도중개보수']
