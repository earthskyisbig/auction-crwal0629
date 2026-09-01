# -*- coding: utf-8 -*-
"""권리분석 엔진(skill_detail/scripts/rights_analysis.py) 단위 테스트.
기존 _selftest 5시나리오를 pytest로 옮기고, 경계 케이스(같은 날 전입·말소기준 없음·임차권등기)를 추가."""
import conftest  # noqa: F401  (sys.path 설정)
from rights_analysis import analyze_rights


def _e(목적, 접수일, 금액=None, 구분='을구', 순위='1', 말소=False):
    return {'구분': 구분, '순위번호': 순위, '등기목적': 목적, '접수일': 접수일,
            '금액': 금액, '권리자': 'X', '말소여부': 말소}


def test_senior_mortgage_is_base_and_everything_after_extinguishes():
    r = analyze_rights([
        _e('근저당권설정', (2020, 11, 4), 100_000_000),
        _e('가압류', (2023, 5, 1), 50_000_000, 구분='갑구', 순위='3'),
        _e('강제경매개시결정', (2025, 6, 25), 구분='갑구', 순위='4'),
    ], 경매개시일=(2025, 6, 25))
    assert r['말소기준권리'].startswith('근저당권')
    assert r['말소기준일'] == (2020, 11, 4)
    assert r['정밀인수금'] == 0
    assert r['인수권리'] == []


def test_senior_jeonse_right_is_assumed_with_amount():
    r = analyze_rights([
        _e('전세권설정', (2019, 3, 1), 200_000_000),
        _e('근저당권설정', (2021, 7, 10), 80_000_000, 순위='2'),
    ], 경매개시일=(2025, 1, 1))
    assert r['말소기준일'] == (2021, 7, 10)
    assert [x['등기목적'] for x in r['인수권리']] == ['전세권설정']
    assert r['정밀인수금'] == 200_000_000


def test_cancelled_rights_are_ignored():
    r = analyze_rights([
        _e('근저당권설정', (2018, 1, 1), 300_000_000, 말소=True),
        _e('근저당권설정', (2022, 2, 2), 90_000_000, 순위='2'),
    ], 경매개시일=(2025, 1, 1))
    assert r['말소기준일'] == (2022, 2, 2)
    assert r['정밀인수금'] == 0


def test_tenant_moved_in_before_base_is_assumed():
    tenant = [{'성명': '홍길동', '보증금': 315_000_000, '전입신고일': (2022, 3, 25),
               '확정일자': (2022, 2, 28), '배당요구일': None}]
    r = analyze_rights([_e('근저당권설정', (2023, 11, 7), 50_000_000)],
                       경매개시일=(2025, 6, 25), 명세서임차인=tenant)
    assert len(r['대항력임차인']) == 1
    assert r['대항력임차인'][0]['회수가능성'] is False
    assert r['정밀인수금'] == 315_000_000


def test_tenant_moved_in_same_day_as_base_is_not_assumed():
    # 대항력은 전입 다음날 0시 발생 → 말소기준권리와 같은 날 전입은 후순위
    tenant = [{'성명': 'A', '보증금': 100_000_000, '전입신고일': (2023, 11, 7)}]
    r = analyze_rights([_e('근저당권설정', (2023, 11, 7), 50_000_000)],
                       경매개시일=(2025, 6, 25), 명세서임차인=tenant)
    assert r['대항력임차인'] == []
    assert r['정밀인수금'] == 0


def test_tenant_with_dividend_demand_and_fixed_date_is_flagged_recoverable():
    tenant = [{'성명': 'B', '보증금': 50_000_000, '전입신고일': (2020, 1, 1),
               '확정일자': (2020, 1, 2), '배당요구일': (2025, 7, 1)}]
    r = analyze_rights([_e('근저당권설정', (2021, 1, 1), 10_000_000)],
                       경매개시일=(2025, 6, 1), 명세서임차인=tenant)
    assert r['대항력임차인'][0]['회수가능성'] is True
    assert r['정밀인수금'] == 50_000_000  # 보수적 상한 유지


def test_senior_provisional_disposition_is_assumed_without_amount():
    r = analyze_rights([
        _e('가처분', (2020, 1, 1), 구분='갑구', 순위='2'),
        _e('근저당권설정', (2021, 1, 1), 100_000_000),
    ], 경매개시일=(2025, 1, 1))
    assert [x['등기목적'] for x in r['인수권리']] == ['가처분']
    assert r['정밀인수금'] == 0


def test_senior_lease_registration_is_assumed_with_deposit():
    r = analyze_rights([
        _e('주택임차권', (2019, 5, 5), 70_000_000),
        _e('근저당권설정', (2020, 1, 1), 100_000_000, 순위='2'),
    ], 경매개시일=(2025, 1, 1))
    assert r['정밀인수금'] == 70_000_000


def test_no_base_right_falls_back_to_auction_start_date():
    r = analyze_rights([_e('전세권설정', (2019, 3, 1), 200_000_000)], 경매개시일=(2025, 1, 1))
    assert r['말소기준권리'] == '경매개시결정'
    assert r['말소기준일'] == (2025, 1, 1)
    assert r['정밀인수금'] == 200_000_000


def test_no_base_right_and_no_start_date_is_undeterminable():
    r = analyze_rights([_e('전세권설정', (2019, 3, 1), 200_000_000)])
    assert r['말소기준권리'].startswith('판정불가')
    assert r['말소기준일'] is None
    # 기준일이 없으면 선순위 판정 불가 → 인수로 잡지 않는다
    assert r['정밀인수금'] == 0


def test_ownership_transfer_is_not_analyzed():
    r = analyze_rights([
        _e('소유권이전', (2015, 1, 1), 구분='갑구'),
        _e('근저당권설정', (2020, 1, 1), 1),
    ], 경매개시일=(2025, 1, 1))
    assert r['권리목록'][0]['판정'] == '해당없음'


def test_no_base_and_no_start_marks_rights_undeterminable_not_extinguished():
    r = analyze_rights([_e('전세권설정', (2019, 3, 1), 200_000_000), _e('가처분', (2020, 1, 1), 구분='갑구')])
    assert {x['판정'] for x in r['권리목록']} == {'판정불가'}
    assert r['소멸권리'] == []


def test_base_right_without_date_does_not_crash():
    r = analyze_rights([_e('근저당권설정', None, 100_000_000), _e('전세권설정', (2019, 1, 1), 50_000_000, 순위='2')],
                       경매개시일=None)
    assert r['말소기준권리'].endswith('(접수일 미상)')
    assert r['말소기준일'] is None


def test_senior_reservation_provisional_registration_is_assumed_and_collateral_one_is_base():
    r = analyze_rights([
        _e('소유권이전청구권가등기', (2019, 1, 1), 구분='갑구', 순위='2'),
        _e('근저당권설정', (2021, 1, 1), 100_000_000),
    ], 경매개시일=(2025, 1, 1))
    assert [x['등기목적'] for x in r['인수권리']] == ['소유권이전청구권가등기']
    r2 = analyze_rights([_e('담보가등기', (2019, 1, 1), 구분='갑구'), _e('전세권설정', (2020, 1, 1), 1, 순위='2')],
                        경매개시일=(2025, 1, 1))
    assert r2['말소기준일'] == (2019, 1, 1) and r2['정밀인수금'] == 0
