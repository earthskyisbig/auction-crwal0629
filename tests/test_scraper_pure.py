# -*- coding: utf-8 -*-
"""scrape_auction_filtered.py 순수 함수 (Playwright 불필요)."""
import conftest  # noqa: F401
import scrape_auction_filtered as sf


def test_infer_yuchal_court_aware():
    assert sf.infer_yuchal(500_000_000, 500_000_000, '서울중앙지방법원') == '0'
    assert sf.infer_yuchal(500_000_000, 400_000_000, '서울중앙지방법원') == '1'   # 20%
    assert sf.infer_yuchal(500_000_000, 256_000_000, '서울남부지방법원') == '3'   # 0.8^3
    assert sf.infer_yuchal(500_000_000, 350_000_000, '의정부지방법원') == '1'    # 30%
    assert sf.infer_yuchal(500_000_000, 171_500_000, '수원지방법원') == '3'      # 0.7^3
    assert sf.infer_yuchal('', 1, '') == '' and sf.infer_yuchal(0, 0, '') == ''


def test_convert_item_keeps_multi_object_fields():
    item = {'printCsNo': '서울남부지방법원 2025타경1<br/>(중복)', 'dspslGdsSeq': '2', 'printSt': '서울 금천구 시흥동 1',
            'gamevalAmt': '500000000', 'notifyMinmaePrice1': '400000000', 'minmaePrice': '500000000',
            'notifyMinmaePriceRate1': '80', 'yuchalCnt': '5', 'maeGiil': '20260915', 'jiwonNm': '서울남부지방법원',
            'convAddr': '건물 59.9㎡ 토지 30㎡'}
    r = sf.convert_item(item)
    assert r['사건번호'] == '서울남부지방법원 2025타경1 (중복)'
    assert r['물건번호'] == '2' and r['최저가'] == '400,000,000원'
    assert r['전용면적'] == '59.9㎡' and r['유찰추정'] == '1' and r['유찰횟수'] == '5'
    assert r['매각기일'] == '2026.09.15'


def test_make_output_path_tolerates_missing_court():
    from types import SimpleNamespace
    a = SimpleNamespace(output=None, court=None, sido='경기도', sgg=None, scl='아파트', mcl='주거용건물', flbd_min=None, max_price=None)
    assert sf.make_output_path(a).endswith('auction_전국_경기_아파트_유찰전체유찰.csv')
