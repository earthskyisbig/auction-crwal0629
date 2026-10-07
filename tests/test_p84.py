# -*- coding: utf-8 -*-
"""p84_compute.py(재건축 분류)·p84_build.py(조사 선택) 순수 로직."""
import conftest  # noqa: F401
import p84_build as pb
import p84_compute as pc


def test_josa():
    assert pb.josa('양천') == '양천은'
    assert pb.josa('강서') == '강서는'
    assert pb.josa('<b>구로·관악</b>') == '<b>구로·관악</b>은'
    assert pb.josa('33%', '으로로') == '33%로'
    assert pb.josa('30', '으로로') == '30으로'
    assert pb.josa('17%') == '17%는'


def test_pct_uses_minus_sign():
    assert pb.pct(-0.07) == '−7%'
    assert pb.pct(0.35) == '+35%'


def test_name_match_requires_same_numbers():
    n = pc.norm
    assert pc.name_match(n('목동신시가지7'), n('목동7단지아파트'))
    assert not pc.name_match(n('창동주공1단지'), n('창동주공18단지아파트'))
    assert pc.name_match(n('은마'), n('은마아파트'))


def _zone(**kw):
    z = dict(id=1, gu='강남구', dong='대치동', name='은마아파트', stage='조합설립', type='재건축',
             jb_dong='대치동', bonbun=316, bubun=None)
    z.update(kw)
    return z


def test_classify_by_jibun_and_year():
    idx = pc.build_index([_zone()])
    r = {'gu': '강남구', 'umdNm': '대치동', 'aptNm': '은마'}
    assert pc.classify(r, 1979, idx, (316, 0))['name'] == '은마아파트'
    idx = pc.build_index([_zone()])
    assert pc.classify(r, 2015, idx, (316, 0)) is None          # 2003년 이후 준공은 재건축 아님


def test_classify_prefers_exact_bubun():
    zs = [_zone(id=1, name='여의도 목화아파트', dong='여의도동', jb_dong='여의도동', gu='영등포구', bonbun=30, bubun=None),
          _zone(id=2, name='삼부아파트', dong='여의도동', jb_dong='여의도동', gu='영등포구', bonbun=30, bubun=2)]
    idx = pc.build_index(zs)
    r = {'gu': '영등포구', 'umdNm': '여의도동', 'aptNm': '삼부'}
    assert pc.classify(r, 1975, idx, (30, 2))['name'] == '삼부아파트'


def test_classify_bad_pair_rejected():
    idx = pc.build_index([_zone(gu='강서구', dong='내발산동', jb_dong='내발산동', name='경남1차', bonbun=700)])
    r = {'gu': '강서구', 'umdNm': '내발산동', 'aptNm': '명진에버그린'}
    assert pc.classify(r, 2003, idx, (700, 0)) is None
