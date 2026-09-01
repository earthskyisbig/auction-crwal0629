# -*- coding: utf-8 -*-
"""filter_listings.py 순수 함수 테스트 (저감율 기반 유찰 판정·금액·면적 파싱)."""
import conftest  # noqa: F401
import filter_listings as fl


def test_parse_money_handles_korean_formats():
    assert fl.parse_money('350,000,000원') == 350_000_000
    assert fl.parse_money('') == 0
    assert fl.parse_money(None) == 0


def test_real_yuchal_from_price_ratio():
    def r(gam, low):
        return fl.real_yuchal({'감정가': f'{gam:,}원', '최저가': f'{low:,}원'})
    assert r(500_000_000, 500_000_000) == 0
    assert r(500_000_000, 400_000_000) == 1   # 20% 저감 1회
    assert r(500_000_000, 350_000_000) == 1   # 30% 저감 1회
    assert r(500_000_000, 245_000_000) == 2   # 30% 저감 2회 (0.49)
    assert r(500_000_000, 320_000_000) == 2   # 20% 저감 2회 (0.64)
    assert r(500_000_000, 171_500_000) == 3   # 30% 저감 3회 (0.343)
    assert r(0, 100) is None


def test_parse_area_prefers_dedicated_column():
    assert fl.parse_area({'전용면적': '84.97㎡', '물건소재지': '건물 120㎡'}) == 84.97
    assert fl.parse_area({'전용면적': '', '물건소재지': '토지 30㎡ 건물 59.9㎡'}) == 59.9
    assert fl.parse_area({'전용면적': '', '물건소재지': '면적 없음'}) is None
    assert fl.parse_area({'전용면적': '1,234.5㎡'}) == 1234.5
