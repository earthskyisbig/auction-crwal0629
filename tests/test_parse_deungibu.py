# -*- coding: utf-8 -*-
"""등기부 파서(skill_detail/scripts/parse_deungibu.py) — 합성 텍스트 기반 (pdfplumber 불필요)."""
import conftest  # noqa: F401
import parse_deungibu as pd_
from rights_analysis import analyze_rights


def _parse(text):
    orig = pd_.extract_pages
    pd_.extract_pages = lambda p: [text]
    try:
        return pd_.parse_deungibu('synthetic')
    finally:
        pd_.extract_pages = orig


def test_synthetic_register_end_to_end():
    d = _parse(pd_._SYNTH)
    r = analyze_rights(d['분석대상'], 경매개시일=(2025, 6, 25))
    assert r['말소기준일'] == (2020, 11, 4)
    assert r['정밀인수금'] == 200_000_000
    assert all('말소' not in e['등기목적'] for e in d['분석대상'])
    assert [x['등기목적'] for x in r['인수권리']] == ['전세권설정']


def test_cancellation_entry_marks_target_rank():
    d = _parse(pd_._SYNTH)
    eul3 = [e for e in d['을구'] if e['순위번호'] == '3'][0]
    assert eul3['말소여부'] is True
    assert eul3['접수일'] == (2018, 1, 5)


def test_amount_prefers_keyworded_value():
    assert pd_._find_amount('채권최고액 금120,000,000원 기타 금5,000,000원') == 120_000_000
    assert pd_._find_amount('금 5,000,000원 금 9,000,000원') == 9_000_000
    assert pd_._find_amount('금액 없음') is None


def test_purpose_prefers_cancellation_in_head():
    assert pd_._purpose('4 3번근저당권설정등기말소 2021년6월1일') == '말소'
    assert pd_._purpose('2 근저당권설정 2020년11월4일') == '근저당권설정'
    assert pd_._purpose('1 주택임차권 2019년5월5일') == '주택임차권'


def test_person_extraction():
    assert pd_._extract_person('근저당권자 국민은행 채권최고액') .startswith('국민은행')
    assert pd_._extract_person('아무 정보 없음') == ''


def test_purpose_classifies_provisional_registrations_and_annex_entries():
    assert pd_._purpose('2 소유권이전청구권가등기 2019년1월1일 제100호') == '소유권이전청구권가등기'
    assert pd_._purpose('3 담보가등기 2019년1월1일') == '담보가등기'
    assert pd_._purpose('2-1 2번근저당권이전 2022년1월5일 제10호') == '부기등기'
    assert pd_._purpose('4 3번근저당권설정등기말소 2021년6월1일') == '말소'


def test_annex_entries_excluded_from_analysis_targets():
    synth = pd_._SYNTH + "2-1 2번근저당권이전 2022년1월5일 제10호 근저당권자 하나은행\n"
    d = _parse(synth)
    assert all(e['등기목적'] != '부기등기' for e in d['분석대상'])
    assert any(e['등기목적'] == '부기등기' for e in d['전체'])


def test_person_extraction_stops_at_next_field():
    assert pd_._extract_person('채권자 우리은행 청구금액 금50,000,000원') == '우리은행'
